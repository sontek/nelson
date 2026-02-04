"""Tests for Claude provider implementation."""

import json
import subprocess
from unittest.mock import MagicMock, patch

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


def _create_mock_popen(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    pid: int = 12345,
) -> MagicMock:
    """Create a mock Popen object."""
    mock_process = MagicMock()
    mock_process.pid = pid
    mock_process.returncode = returncode
    mock_process.poll.return_value = returncode
    mock_process.communicate.return_value = (stdout, stderr)
    return mock_process


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

        mock_process = _create_mock_popen(
            stdout=json.dumps(mock_response),
            returncode=0,
        )

        with patch("subprocess.Popen", return_value=mock_process):
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

        with patch("subprocess.Popen", side_effect=FileNotFoundError()):
            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet")

            assert "not found" in exc_info.value.message.lower()
            assert not exc_info.value.is_retryable

    def test_execute_non_zero_exit_code(self) -> None:
        """Test execution when claude returns non-zero exit code."""
        provider = ClaudeProvider()

        mock_process = _create_mock_popen(
            stdout="Error occurred",
            returncode=1,
        )

        with patch("subprocess.Popen", return_value=mock_process), patch("time.sleep"):
            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=1)

            # After max retries, error becomes non-retryable
            assert "Max retries reached" in exc_info.value.message
            assert not exc_info.value.is_retryable

    def test_execute_json_parse_error(self) -> None:
        """Test execution when output is not valid JSON."""
        provider = ClaudeProvider()

        mock_process = _create_mock_popen(
            stdout="Not valid JSON",
            returncode=0,
        )

        with patch("subprocess.Popen", return_value=mock_process):
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

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        with patch("subprocess.Popen", return_value=mock_process), patch("time.sleep"):
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

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        with patch("subprocess.Popen", return_value=mock_process):
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

        mock_process = _create_mock_popen(
            stdout=json.dumps(response_json),
            returncode=0,
        )

        with patch("subprocess.Popen", return_value=mock_process), patch("time.sleep"):
            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=1)

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

        mock_process_fail = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )
        mock_process_success = _create_mock_popen(
            stdout=json.dumps(success_response),
            returncode=0,
        )

        call_count = [0]

        def mock_popen_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_process_fail
            return mock_process_success

        with patch("subprocess.Popen", side_effect=mock_popen_side_effect), patch(
            "time.sleep"
        ):
            response = provider.execute(
                "system", "user", "sonnet", max_retries=3, initial_retry_delay=0.1
            )

            assert not response.is_error
            assert "Success" in response.content
            assert call_count[0] == 2

    def test_execute_max_retries_exceeded(self) -> None:
        """Test retry logic when max retries exceeded."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Persistent error"],
        }

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        call_count = [0]

        def mock_popen_counting(*args, **kwargs):
            call_count[0] += 1
            return mock_process

        with patch("subprocess.Popen", side_effect=mock_popen_counting), patch(
            "time.sleep"
        ):
            with pytest.raises(ProviderError) as exc_info:
                provider.execute("system", "user", "sonnet", max_retries=2)

            assert "Max retries reached" in exc_info.value.message
            assert not exc_info.value.is_retryable
            assert call_count[0] == 2

    def test_exponential_backoff_delays(self) -> None:
        """Test that exponential backoff calculates delays correctly."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Persistent error"],
        }

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        sleep_delays = []

        def mock_sleep(delay):
            sleep_delays.append(delay)

        with patch("subprocess.Popen", return_value=mock_process), patch(
            "time.sleep", side_effect=mock_sleep
        ):
            with pytest.raises(ProviderError):
                provider.execute(
                    "system",
                    "user",
                    "sonnet",
                    max_retries=5,
                    initial_retry_delay=2.0,
                    exponential_base=2.0,
                    max_retry_delay=1000.0,
                    jitter=False,  # Disable jitter for predictable testing
                )

        # With initial_delay=2.0, base=2.0, we expect: 2, 4, 8, 16
        assert len(sleep_delays) == 4  # 5 attempts = 4 retries
        assert sleep_delays[0] == 2.0  # 2.0 * 2^0
        assert sleep_delays[1] == 4.0  # 2.0 * 2^1
        assert sleep_delays[2] == 8.0  # 2.0 * 2^2
        assert sleep_delays[3] == 16.0  # 2.0 * 2^3

    def test_exponential_backoff_with_cap(self) -> None:
        """Test that exponential backoff respects max_retry_delay cap."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Persistent error"],
        }

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        sleep_delays = []

        def mock_sleep(delay):
            sleep_delays.append(delay)

        with patch("subprocess.Popen", return_value=mock_process), patch(
            "time.sleep", side_effect=mock_sleep
        ):
            with pytest.raises(ProviderError):
                provider.execute(
                    "system",
                    "user",
                    "sonnet",
                    max_retries=6,
                    initial_retry_delay=10.0,
                    exponential_base=2.0,
                    max_retry_delay=50.0,  # Cap at 50 seconds
                    jitter=False,
                )

        # With initial_delay=10.0, base=2.0, cap=50.0
        # Expected: 10, 20, 40, 50 (capped), 50 (capped)
        assert len(sleep_delays) == 5
        assert sleep_delays[0] == 10.0  # 10 * 2^0
        assert sleep_delays[1] == 20.0  # 10 * 2^1
        assert sleep_delays[2] == 40.0  # 10 * 2^2
        assert sleep_delays[3] == 50.0  # 10 * 2^3 = 80, but capped at 50
        assert sleep_delays[4] == 50.0  # 10 * 2^4 = 160, but capped at 50

    def test_exponential_backoff_with_jitter(self) -> None:
        """Test that jitter adds randomness to delays."""
        provider = ClaudeProvider()
        error_response = {
            "type": "error",
            "is_error": True,
            "errors": ["Persistent error"],
        }

        mock_process = _create_mock_popen(
            stdout=json.dumps(error_response),
            returncode=0,
        )

        sleep_delays = []

        def mock_sleep(delay):
            sleep_delays.append(delay)

        with patch("subprocess.Popen", return_value=mock_process), patch(
            "time.sleep", side_effect=mock_sleep
        ):
            with pytest.raises(ProviderError):
                provider.execute(
                    "system",
                    "user",
                    "sonnet",
                    max_retries=4,
                    initial_retry_delay=10.0,
                    exponential_base=2.0,
                    max_retry_delay=1000.0,
                    jitter=True,  # Enable jitter
                )

        # With jitter, delays should be 50-100% of calculated value
        # Expected ranges: [5-10], [10-20], [20-40]
        assert len(sleep_delays) == 3
        assert 5.0 <= sleep_delays[0] <= 10.0  # 10.0 * 2^0 with jitter
        assert 10.0 <= sleep_delays[1] <= 20.0  # 10.0 * 2^1 with jitter
        assert 20.0 <= sleep_delays[2] <= 40.0  # 10.0 * 2^2 with jitter


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

        text_with_ansi = (
            "\x1b[31mRed text\x1b[0m Normal text \x1b[1;32mBold green\x1b[0m"
        )
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
