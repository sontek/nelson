"""Tests for Claude provider implementation."""

import json
import subprocess
from unittest.mock import patch

import pytest

from nelson.providers.base import AIResponse, ProviderError
from nelson.providers.claude import ClaudeProvider


def _create_status_block(
    status: str = "COMPLETE",
    tasks: int = 1,
    files: int = 1,
    tests: str = "PASSING",
    work: str = "IMPLEMENTATION",
    exit_signal: bool = True,
    recommendation: str = "Done",
) -> str:
    """Helper to create a status block string."""
    return (
        f"---NELSON_STATUS---\n"
        f"STATUS: {status}\n"
        f"TASKS_COMPLETED_THIS_LOOP: {tasks}\n"
        f"FILES_MODIFIED: {files}\n"
        f"TESTS_STATUS: {tests}\n"
        f"WORK_TYPE: {work}\n"
        f"EXIT_SIGNAL: {str(exit_signal).lower()}\n"
        f"RECOMMENDATION: {recommendation}\n"
        f"---END_NELSON_STATUS---"
    )


class TestClaudeProviderInit:
    """Test Claude provider initialization."""

    def test_init_default_command(self) -> None:
        """Test initialization with default claude command."""
        provider = ClaudeProvider()
        assert provider.claude_command == "claude"
        assert not provider._uses_jail_mode

    def test_init_custom_command(self) -> None:
        """Test initialization with custom command path."""
        provider = ClaudeProvider("/usr/local/bin/claude")
        assert provider.claude_command == "/usr/local/bin/claude"
        assert not provider._uses_jail_mode

    def test_init_jail_mode(self) -> None:
        """Test initialization detects jail mode."""
        provider = ClaudeProvider("/path/to/claude-jail")
        assert "claude-jail" in provider.claude_command
        assert provider._uses_jail_mode


class TestClaudeProviderExecution:
    """Test Claude command execution."""

    def test_execute_success(self) -> None:
        """Test successful Claude execution."""
        provider = ClaudeProvider()
        status_block = _create_status_block(files=2)
        mock_response = {
            "type": "result",
            "result": f"Test response\n{status_block}",
            "is_error": False,
            "errors": [],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr="",
            )

            response = provider.execute(
                system_prompt="System prompt",
                user_prompt="User prompt",
                model="sonnet",
            )

            assert not response.is_error
            assert "Test response" in response.content
            assert response.metadata["model"] == "sonnet"

    def test_execute_command_not_found(self) -> None:
        """Test execution when claude command doesn't exist."""
        provider = ClaudeProvider("/nonexistent/claude")

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet")

            assert "not found" in exc_info.value.message.lower()
            assert not exc_info.value.is_retryable

    def test_execute_non_zero_exit_code(self) -> None:
        """Test execution when claude returns non-zero exit code."""
        provider = ClaudeProvider()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="Error occurred",
                stderr="",
            )

            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet")

            # After max retries, error becomes non-retryable
            assert "Max retries reached" in exc_info.value.message
            assert not exc_info.value.is_retryable

    def test_execute_json_parse_error(self) -> None:
        """Test execution when output is not valid JSON."""
        provider = ClaudeProvider()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Not valid JSON",
                stderr="",
            )

            response = provider.execute("system", "user", "sonnet")

            assert response.is_error
            assert response.error_message is not None
            assert "Failed to parse JSON" in response.error_message

    def test_execute_claude_error_retryable(self) -> None:
        """Test execution when Claude returns retryable error."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Connection timeout"],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(error_response),
                stderr="",
            )

            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=1)

            # After max retries, error becomes non-retryable
            assert "Max retries reached" in exc_info.value.message
            assert "Connection timeout" in exc_info.value.message
            assert not exc_info.value.is_retryable

    def test_execute_claude_error_non_retryable(self) -> None:
        """Test execution when Claude returns non-retryable error."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Authentication failed"],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(error_response),
                stderr="",
            )

            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=1)

            assert "Authentication failed" in exc_info.value.message
            assert not exc_info.value.is_retryable

    def test_execute_empty_result(self) -> None:
        """Test execution when Claude returns empty result."""
        provider = ClaudeProvider()
        response_json = {
            "type": "result",
            "result": "",
            "is_error": False,
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(response_json),
                stderr="",
            )

            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet")

            # After max retries, error becomes non-retryable
            assert "Max retries reached" in exc_info.value.message
            assert "empty result" in exc_info.value.message.lower()
            assert not exc_info.value.is_retryable

    def test_execute_retry_logic(self) -> None:
        """Test retry logic with transient errors."""
        provider = ClaudeProvider()

        # First call fails, second succeeds
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Temporary error"],
        }
        status_block = _create_status_block()
        success_response = {
            "type": "result",
            "result": f"Success\n{status_block}",
            "is_error": False,
        }

        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(error_response),
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(success_response),
                    stderr="",
                ),
            ]

            response = provider.execute("system", "user", "sonnet", max_retries=3, retry_delay=0.1)

            assert not response.is_error
            assert "Success" in response.content
            assert mock_run.call_count == 2

    def test_execute_max_retries_exceeded(self) -> None:
        """Test retry logic when max retries exceeded."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Persistent error"],
        }

        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(error_response),
                stderr="",
            )

            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=2)

            assert "Max retries reached" in exc_info.value.message
            assert not exc_info.value.is_retryable
            assert mock_run.call_count == 2


class TestClaudeProviderJailMode:
    """Test jail mode execution."""

    def test_jail_mode_uses_script_wrapper(self) -> None:
        """Test that jail mode uses script command."""
        provider = ClaudeProvider("/path/to/claude-jail")
        assert provider._uses_jail_mode

        status_block = _create_status_block()
        with patch.object(provider, "_execute_with_script") as mock_script:
            mock_script.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps(
                    {
                        "type": "result",
                        "result": f"Test\n{status_block}",
                        "is_error": False,
                    }
                ),
                stderr="",
            )

            provider.execute("system", "user", "sonnet")
            assert mock_script.called


class TestStripAnsiCodes:
    """Test ANSI code stripping."""

    def test_strip_ansi_codes(self) -> None:
        """Test stripping ANSI escape sequences."""
        provider = ClaudeProvider()

        text_with_ansi = "\x1b[31mRed text\x1b[0m Normal text \x1b[1;32mBold green\x1b[0m"
        clean_text = provider._strip_ansi_codes(text_with_ansi)

        assert "\x1b" not in clean_text
        assert "Red text" in clean_text
        assert "Normal text" in clean_text
        assert "Bold green" in clean_text

    def test_strip_ansi_codes_no_codes(self) -> None:
        """Test stripping when no ANSI codes present."""
        provider = ClaudeProvider()

        text = "Plain text without codes"
        clean_text = provider._strip_ansi_codes(text)

        assert clean_text == text


class TestValidateResponse:
    """Test response validation."""

    def test_validate_response_valid(self) -> None:
        """Test validation with valid status block."""
        provider = ClaudeProvider()
        status_block = _create_status_block(files=2)
        response = AIResponse(
            content=f"Response\n{status_block}",
            raw_output="",
            metadata={},
        )

        assert provider.validate_response(response)

    def test_validate_response_missing_status_block(self) -> None:
        """Test validation with missing status block."""
        provider = ClaudeProvider()
        response = AIResponse(
            content="Response without status block",
            raw_output="",
            metadata={},
        )

        assert not provider.validate_response(response)


class TestExtractStatusBlock:
    """Test status block extraction."""

    def test_extract_status_block_complete(self) -> None:
        """Test extracting complete status block."""
        provider = ClaudeProvider()
        content = """
Response text here.

---NELSON_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 3
FILES_MODIFIED: 5
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: All tasks complete
---END_NELSON_STATUS---

More text after.
"""
        response = AIResponse(content=content, raw_output="", metadata={})
        status = provider.extract_status_block(response)

        assert status["status"] == "COMPLETE"
        assert status["tasks_completed"] == 3
        assert status["files_modified"] == 5
        assert status["tests_status"] == "PASSING"
        assert status["work_type"] == "IMPLEMENTATION"
        assert status["exit_signal"] is True
        assert status["recommendation"] == "All tasks complete"

    def test_extract_status_block_in_progress(self) -> None:
        """Test extracting in-progress status block."""
        provider = ClaudeProvider()
        content = """
---NELSON_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 2
TESTS_STATUS: NOT_RUN
WORK_TYPE: TESTING
EXIT_SIGNAL: false
RECOMMENDATION: Continue testing
---END_NELSON_STATUS---
"""
        response = AIResponse(content=content, raw_output="", metadata={})
        status = provider.extract_status_block(response)

        assert status["status"] == "IN_PROGRESS"
        assert status["exit_signal"] is False

    def test_extract_status_block_missing(self) -> None:
        """Test extraction when status block is missing."""
        provider = ClaudeProvider()
        response = AIResponse(
            content="No status block here",
            raw_output="",
            metadata={},
        )

        with pytest.raises(ProviderError) as exc_info:
            provider.extract_status_block(response)

        assert "not found" in exc_info.value.message.lower()
        assert not exc_info.value.is_retryable

    def test_extract_status_block_incomplete(self) -> None:
        """Test extraction when status block is missing required fields."""
        provider = ClaudeProvider()
        content = """
---NELSON_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
---END_NELSON_STATUS---
"""
        response = AIResponse(content=content, raw_output="", metadata={})

        with pytest.raises(ProviderError) as exc_info:
            provider.extract_status_block(response)

        assert "missing required fields" in exc_info.value.message.lower()
        assert not exc_info.value.is_retryable

    def test_extract_status_block_invalid_numbers(self) -> None:
        """Test extraction with invalid numeric values."""
        provider = ClaudeProvider()
        content = """
---NELSON_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: not_a_number
FILES_MODIFIED: also_not_a_number
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: Done
---END_NELSON_STATUS---
"""
        response = AIResponse(content=content, raw_output="", metadata={})
        status = provider.extract_status_block(response)

        # Should default to 0 for invalid numbers
        assert status["tasks_completed"] == 0
        assert status["files_modified"] == 0


class TestIsAvailable:
    """Test provider availability check."""

    def test_is_available_success(self) -> None:
        """Test availability check when claude exists."""
        provider = ClaudeProvider()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Claude version 1.0",
                stderr="",
            )

            assert provider.is_available()

    def test_is_available_not_found(self) -> None:
        """Test availability check when claude doesn't exist."""
        provider = ClaudeProvider()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert not provider.is_available()

    def test_is_available_permission_error(self) -> None:
        """Test availability check when no permission."""
        provider = ClaudeProvider()

        with patch("subprocess.run", side_effect=PermissionError()):
            assert not provider.is_available()


class TestGetCost:
    """Test cost extraction."""

    def test_get_cost_no_metadata(self) -> None:
        """Test cost extraction when no cost in metadata."""
        provider = ClaudeProvider()
        response = AIResponse(
            content="Test",
            raw_output="",
            metadata={},
        )

        assert provider.get_cost(response) == 0.0

    def test_get_cost_with_metadata(self) -> None:
        """Test cost extraction when cost in metadata."""
        provider = ClaudeProvider()
        response = AIResponse(
            content="Test",
            raw_output="",
            metadata={"cost": 0.05},
        )

        assert provider.get_cost(response) == 0.05
