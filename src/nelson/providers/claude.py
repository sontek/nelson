"""Claude provider implementation for Nelson.

This module implements the Claude provider, supporting both native and jail (Docker) modes.
It handles calling the Claude command-line tool, parsing JSON output, and extracting
the Nelson status block from responses.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nelson.logging_config import get_logger
from nelson.providers.base import AIProvider, AIResponse, ProviderError

if TYPE_CHECKING:
    from nelson.config import NelsonConfig
    from nelson.progress_monitor import ProgressMonitor

logger = get_logger()


class ClaudeProvider(AIProvider):
    """Claude provider implementation.

    This provider supports two modes:
    - Native mode: Calls `claude` command directly
    - Jail mode: Calls `claude-jail` script (Docker sandbox)

    Both modes use the Claude Code CLI with these flags:
    - `-p`: Prompt mode (non-interactive)
    - `--model <model>`: Model selection (sonnet, opus, haiku)
    - `--output-format json`: Get structured JSON output
    - `--system-prompt <prompt>`: System-level instructions
    - `--permission-mode bypassPermissions`: Skip permission prompts for automation

    The JSON output format from Claude:
    {
        "type": "result",
        "result": "actual response text...",
        "is_error": false,
        "errors": []
    }
    """

    def __init__(
        self,
        claude_command: str | None = None,
        target_path: Path | None = None,
        config: NelsonConfig | None = None,
    ) -> None:
        """Initialize Claude provider.

        Args:
            claude_command: Path to claude command (None = system 'claude', or custom path)
            target_path: Optional target repository path for command execution
            config: Optional NelsonConfig for error handling configuration
        """
        self.claude_command = claude_command or "claude"
        self._uses_jail_mode = "claude-jail" in str(self.claude_command)
        self.target_path = target_path
        self.config = config

    def execute(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_retries: int = 3,
        retry_delay: float = 3.0,
        progress_monitor: ProgressMonitor | None = None,
    ) -> AIResponse:
        """Execute Claude call with retry logic.

        Args:
            system_prompt: System-level prompt with Nelson instructions
            user_prompt: User/task-specific prompt
            model: Model identifier (sonnet, opus, haiku)
            max_retries: Maximum retry attempts for transient errors
            retry_delay: Delay between retries in seconds
            progress_monitor: Optional progress monitor to notify with subprocess PID

        Returns:
            AIResponse with Claude's output

        Raises:
            ProviderError: If call fails after all retries
        """
        retry_count = 0
        last_error: ProviderError | None = None

        while retry_count < max_retries:
            try:
                # Build augmented prompt with error context from previous attempt
                augmented_prompt = user_prompt
                # Only add error context if enabled in config (default: True)
                error_aware_enabled = self.config.error_aware_retries if self.config else True
                if error_aware_enabled and last_error and retry_count > 0:
                    # Truncate error message if too long to avoid excessive token usage
                    error_msg = last_error.message
                    max_error_length = (
                        self.config.max_error_context_chars if self.config else 2000
                    )
                    if len(error_msg) > max_error_length:
                        error_msg = error_msg[:max_error_length] + "\n... (truncated)"

                    augmented_prompt = f"""{user_prompt}

<previous_attempt_error>
IMPORTANT: The previous attempt (#{retry_count}) failed with the following error:

{error_msg}

Please analyze this error and adjust your approach before proceeding. Common issues to check:
- Commands or recipe names that don't exist (e.g., 'just run' when only 'just dev' exists)
- File paths that are incorrect or don't exist
- Processes that timeout due to waiting for non-existent resources
- Missing dependencies or incorrect configuration

Before retrying the task, diagnose and fix the root cause of this error.
</previous_attempt_error>"""
                    logger.info(f"[RETRY] Including error context from previous attempt in prompt")

                return self._execute_once(system_prompt, augmented_prompt, model, progress_monitor)
            except ProviderError as e:
                if not e.is_retryable:
                    # Non-retryable error - fail immediately
                    raise

                # Transient error - save for next retry and retry
                last_error = e
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(
                        f"Error detected (attempt {retry_count}/{max_retries}): {e.message}"
                    )
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)

                    # Reset progress monitor timer for the retry attempt
                    if progress_monitor:
                        progress_monitor.reset()
                        logger.debug("Progress monitor timer reset for retry attempt")
                else:
                    # Max retries reached
                    raise ProviderError(
                        f"Max retries reached. Last error: {e.message}",
                        is_retryable=False,
                        original_error=e.original_error,
                    )

        # Should never reach here, but satisfy type checker
        raise ProviderError(
            "Unexpected error: retry loop exited without result",
            is_retryable=False,
        )

    def _execute_once(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        progress_monitor: ProgressMonitor | None = None,
    ) -> AIResponse:
        """Execute a single Claude call (no retry logic).

        Args:
            system_prompt: System-level prompt
            user_prompt: User prompt
            model: Model identifier
            progress_monitor: Optional progress monitor to notify with subprocess PID

        Returns:
            AIResponse with Claude's output

        Raises:
            ProviderError: If call fails
        """
        # Build command
        cmd = [
            str(self.claude_command),
            "-p",  # Prompt mode (non-interactive)
            "--model",
            model,
            "--output-format",
            "json",
            "--system-prompt",
            system_prompt,
            "--permission-mode",
            "bypassPermissions",
            user_prompt,
        ]

        logger.info(
            f"Executing: {self.claude_command} -p --model {model} "
            f'--output-format json --system-prompt "..." '
            f"--permission-mode bypassPermissions"
        )

        # Execute command using Popen for PID access
        try:
            if self._uses_jail_mode:
                # claude-jail needs script wrapper for pseudo-TTY
                result = self._execute_with_script(cmd, progress_monitor)
            else:
                # Native claude - use Popen for PID access
                result = self._execute_with_popen(cmd, progress_monitor)
        except FileNotFoundError as e:
            raise ProviderError(
                f"Claude command not found: {self.claude_command}",
                is_retryable=False,
                original_error=e,
            )
        except Exception as e:
            raise ProviderError(
                f"Failed to execute claude command: {e}",
                is_retryable=True,
                original_error=e,
            )

        # Check exit code
        if result.returncode != 0:
            raise ProviderError(
                f"Claude command failed with exit code {result.returncode}",
                is_retryable=True,
            )

        # Parse JSON output
        raw_output = result.stdout
        try:
            output_json = json.loads(raw_output)
        except json.JSONDecodeError as e:
            # Not JSON - might be raw text output or error
            return AIResponse(
                content=raw_output,
                raw_output=raw_output,
                metadata={},
                is_error=True,
                error_message=f"Failed to parse JSON output: {e}",
            )

        # Check for errors in JSON
        if output_json.get("is_error", False):
            error_messages = output_json.get("errors", [])
            if error_messages:
                error_text = " ".join(str(e) for e in error_messages)
            else:
                error_text = "Unknown error"

            # Check for non-retryable errors
            non_retryable_patterns = [
                "authentication",
                "unauthorized",
                "invalid api key",
                "permission denied",
                "forbidden",
            ]
            is_retryable = not any(
                pattern in error_text.lower() for pattern in non_retryable_patterns
            )

            raise ProviderError(
                f"Claude returned error: {error_text}",
                is_retryable=is_retryable,
            )

        # Extract result text
        content = output_json.get("result", "")
        if not content:
            raise ProviderError(
                "Claude returned empty result",
                is_retryable=True,
            )

        # Strip ANSI escape codes (from script command or Claude output)
        content = self._strip_ansi_codes(content)

        # Build metadata
        metadata: dict[str, Any] = {
            "model": model,
            "output_format": "json",
        }

        return AIResponse(
            content=content,
            raw_output=raw_output,
            metadata=metadata,
            is_error=False,
        )

    def _execute_with_popen(
        self,
        cmd: list[str],
        progress_monitor: ProgressMonitor | None = None,
        stall_check_interval: float = 5.0,
    ) -> subprocess.CompletedProcess[str]:
        """Execute command using Popen for PID access and stall detection.

        This method uses Popen instead of subprocess.run() so we can:
        1. Get the subprocess PID immediately
        2. Notify the progress monitor
        3. Check for stalls and kill hung processes
        4. Wait for completion

        Args:
            cmd: Command to execute
            progress_monitor: Optional progress monitor to notify with PID
            stall_check_interval: Seconds between stall checks (default: 5)

        Returns:
            CompletedProcess with command result

        Raises:
            ProviderError: If process is killed due to stall (retryable)
        """
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.target_path,
        )

        # Log and notify progress monitor with PID
        logger.info(f"Claude subprocess started (PID: {process.pid})")
        if progress_monitor:
            progress_monitor.set_subprocess_pid(process.pid)

        # Wait for completion with stall checking
        stdout_data = ""
        stderr_data = ""

        if progress_monitor:
            # Use polling loop to check for stalls
            while True:
                # Check if process has finished
                retcode = process.poll()
                if retcode is not None:
                    # Process finished - read remaining output
                    remaining_stdout, remaining_stderr = process.communicate()
                    stdout_data += remaining_stdout or ""
                    stderr_data += remaining_stderr or ""
                    break

                # Check for stall
                if progress_monitor.is_stalled:
                    idle_seconds = progress_monitor.get_idle_seconds()
                    idle_minutes = idle_seconds / 60.0

                    # Capture any output before killing to help with debugging
                    try:
                        # Read what we have so far (non-blocking)
                        if process.stdout:
                            import select
                            ready, _, _ = select.select([process.stdout], [], [], 0)
                            if ready:
                                partial_stdout = process.stdout.read()
                                if partial_stdout:
                                    stdout_data += partial_stdout
                        if process.stderr:
                            ready, _, _ = select.select([process.stderr], [], [], 0)
                            if ready:
                                partial_stderr = process.stderr.read()
                                if partial_stderr:
                                    stderr_data += partial_stderr
                    except Exception:
                        # Ignore errors reading output - not critical
                        pass

                    logger.warning(
                        f"Killing stalled Claude process (PID: {process.pid}) "
                        f"after {idle_minutes:.1f} minutes of inactivity"
                    )
                    process.kill()
                    process.wait()  # Clean up zombie

                    # Build error message with captured output
                    error_parts = [
                        f"Claude process stalled (no activity for {idle_minutes:.1f} minutes).",
                        "Process was killed and will be retried.",
                    ]

                    # Include last output if available
                    if stdout_data or stderr_data:
                        error_parts.append("\nLast output before stall:")
                        if stdout_data:
                            # Get last 1000 chars to avoid huge error messages
                            last_stdout = stdout_data[-1000:]
                            error_parts.append(f"\nSTDOUT (last 1000 chars):\n{last_stdout}")
                        if stderr_data:
                            last_stderr = stderr_data[-1000:]
                            error_parts.append(f"\nSTDERR (last 1000 chars):\n{last_stderr}")

                    raise ProviderError(
                        "".join(error_parts),
                        is_retryable=True,
                    )

                # Sleep before next check
                time.sleep(stall_check_interval)
        else:
            # No progress monitor - just wait normally
            stdout_data, stderr_data = process.communicate()

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout=stdout_data,
            stderr=stderr_data or "",
        )

    def _execute_with_script(
        self,
        cmd: list[str],
        progress_monitor: ProgressMonitor | None = None,
        stall_check_interval: float = 5.0,
    ) -> subprocess.CompletedProcess[str]:
        """Execute command with script wrapper (for claude-jail).

        The script command creates a pseudo-TTY, which is required for
        Docker containers to work properly with interactive commands.

        Args:
            cmd: Command to execute
            progress_monitor: Optional progress monitor to notify with PID
            stall_check_interval: Seconds between stall checks (default: 5)

        Returns:
            CompletedProcess with command result

        Raises:
            ProviderError: If process is killed due to stall (retryable)
        """
        # Create temporary file for output
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            # Run with script command using Popen for PID access
            script_cmd = ["script", "-q", output_file] + cmd
            process = subprocess.Popen(
                script_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.target_path,
            )

            # Log and notify progress monitor with PID
            logger.info(f"Claude subprocess started (PID: {process.pid})")
            if progress_monitor:
                progress_monitor.set_subprocess_pid(process.pid)

            # Wait for completion with stall checking
            stderr_data = ""

            if progress_monitor:
                # Use polling loop to check for stalls
                while True:
                    # Check if process has finished
                    retcode = process.poll()
                    if retcode is not None:
                        # Process finished - read remaining stderr
                        _, remaining_stderr = process.communicate()
                        stderr_data += remaining_stderr or ""
                        break

                    # Check for stall
                    if progress_monitor.is_stalled:
                        idle_seconds = progress_monitor.get_idle_seconds()
                        idle_minutes = idle_seconds / 60.0

                        # Capture any output before killing to help with debugging
                        stdout_data = ""
                        try:
                            # Read what we have so far from stderr (non-blocking)
                            if process.stderr:
                                import select
                                ready, _, _ = select.select([process.stderr], [], [], 0)
                                if ready:
                                    partial_stderr = process.stderr.read()
                                    if partial_stderr:
                                        stderr_data += partial_stderr

                            # Try to read partial stdout from the output file
                            if Path(output_file).exists():
                                with open(output_file) as f:
                                    stdout_data = f.read()
                        except Exception:
                            # Ignore errors reading output - not critical
                            pass

                        logger.warning(
                            f"Killing stalled Claude process (PID: {process.pid}) "
                            f"after {idle_minutes:.1f} minutes of inactivity"
                        )
                        process.kill()
                        process.wait()  # Clean up zombie

                        # Build error message with captured output
                        error_parts = [
                            f"Claude process stalled (no activity for {idle_minutes:.1f} minutes).",
                            "Process was killed and will be retried.",
                        ]

                        # Include last output if available
                        if stdout_data or stderr_data:
                            error_parts.append("\nLast output before stall:")
                            if stdout_data:
                                # Get last 1000 chars to avoid huge error messages
                                last_stdout = stdout_data[-1000:]
                                error_parts.append(f"\nSTDOUT (last 1000 chars):\n{last_stdout}")
                            if stderr_data:
                                last_stderr = stderr_data[-1000:]
                                error_parts.append(f"\nSTDERR (last 1000 chars):\n{last_stderr}")

                        raise ProviderError(
                            "".join(error_parts),
                            is_retryable=True,
                        )

                    # Sleep before next check
                    time.sleep(stall_check_interval)
            else:
                # No progress monitor - just wait normally
                _, stderr_data = process.communicate()

            # Read output from file
            with open(output_file) as f:
                stdout = f.read()

            # Return as CompletedProcess
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr_data or "",
            )
        finally:
            # Clean up temp file
            Path(output_file).unlink(missing_ok=True)

    def _strip_ansi_codes(self, text: str) -> str:
        """Strip ANSI escape codes from text.

        Args:
            text: Text potentially containing ANSI codes

        Returns:
            Text with ANSI codes removed
        """
        # Remove ANSI escape sequences: ESC [ ... m
        ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
        return ansi_pattern.sub("", text)

    def validate_response(self, response: AIResponse) -> bool:
        """Validate that response contains required Nelson status block.

        Args:
            response: AIResponse to validate

        Returns:
            True if response contains valid status block
        """
        try:
            self.extract_status_block(response)
            return True
        except ProviderError:
            return False

    def extract_status_block(self, response: AIResponse) -> dict[str, Any]:
        """Extract Nelson status block from response.

        The status block format:
            ---NELSON_STATUS---
            STATUS: IN_PROGRESS|COMPLETE|BLOCKED
            TASKS_COMPLETED_THIS_LOOP: N
            FILES_MODIFIED: N
            TESTS_STATUS: PASSING|FAILING|NOT_RUN
            WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
            EXIT_SIGNAL: true|false
            RECOMMENDATION: one-line text
            ---END_NELSON_STATUS---

        Args:
            response: AIResponse containing status block

        Returns:
            Dictionary with parsed status fields

        Raises:
            ProviderError: If status block is missing or malformed
        """
        content = response.content

        # Find status block
        start_marker = "---NELSON_STATUS---"
        end_marker = "---END_NELSON_STATUS---"

        if start_marker not in content or end_marker not in content:
            raise ProviderError(
                "Status block not found in response",
                is_retryable=False,
            )

        # Extract block content
        start_idx = content.index(start_marker) + len(start_marker)
        end_idx = content.index(end_marker)
        block_content = content[start_idx:end_idx].strip()

        # Parse fields
        status_dict: dict[str, Any] = {}

        for line in block_content.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            # Map keys to dict
            if key == "status":
                status_dict["status"] = value
            elif key == "tasks_completed_this_loop":
                try:
                    status_dict["tasks_completed"] = int(value)
                except ValueError:
                    status_dict["tasks_completed"] = 0
            elif key == "files_modified":
                try:
                    status_dict["files_modified"] = int(value)
                except ValueError:
                    status_dict["files_modified"] = 0
            elif key == "tests_status":
                status_dict["tests_status"] = value
            elif key == "work_type":
                status_dict["work_type"] = value
            elif key == "exit_signal":
                status_dict["exit_signal"] = value.lower() == "true"
            elif key == "recommendation":
                status_dict["recommendation"] = value

        # Validate required fields
        required_fields = [
            "status",
            "tasks_completed",
            "files_modified",
            "tests_status",
            "work_type",
            "exit_signal",
            "recommendation",
        ]
        missing_fields = [f for f in required_fields if f not in status_dict]
        if missing_fields:
            raise ProviderError(
                f"Status block missing required fields: {', '.join(missing_fields)}",
                is_retryable=False,
            )

        return status_dict

    def is_available(self) -> bool:
        """Check if Claude provider is available.

        Returns:
            True if claude command exists and is executable
        """
        try:
            # Check if command exists
            result = subprocess.run(
                [str(self.claude_command), "--version"],
                capture_output=True,
                check=False,
                cwd=self.target_path,
            )
            return result.returncode == 0
        except (FileNotFoundError, PermissionError):
            return False

    def get_cost(self, response: AIResponse) -> float:
        """Extract cost from response metadata.

        Note: Claude Code CLI doesn't currently provide cost information
        in its output, so this always returns 0.0. In the future, we could
        add cost estimation based on token counts if available.

        Args:
            response: AIResponse to extract cost from

        Returns:
            Cost in USD (currently always 0.0)
        """
        cost = response.metadata.get("cost", 0.0)
        return float(cost) if cost is not None else 0.0
