"""Tests for audit log module with tee-like functionality."""

import sys
from io import StringIO
from pathlib import Path

import pytest

from nelson.audit_log import TeeOutput, audit_log, generate_audit_log_path


class TestTeeOutput:
    """Tests for TeeOutput class."""

    def test_write_to_multiple_files(self, tmp_path: Path) -> None:
        """Test writing to multiple file objects simultaneously."""
        file1 = StringIO()
        file2 = StringIO()
        tee = TeeOutput(file1, file2)

        tee.write("test message")

        assert file1.getvalue() == "test message"
        assert file2.getvalue() == "test message"

    def test_write_returns_length(self, tmp_path: Path) -> None:
        """Test that write returns number of characters written."""
        file1 = StringIO()
        tee = TeeOutput(file1)

        result = tee.write("hello")

        assert result == 5

    def test_flush_all_files(self, tmp_path: Path) -> None:
        """Test flushing all wrapped file objects."""
        # Create files that track flush calls
        file1 = StringIO()
        file2 = StringIO()
        tee = TeeOutput(file1, file2)

        tee.write("test")
        tee.flush()

        # StringIO doesn't have visible flush state, but we verify no errors
        assert file1.getvalue() == "test"
        assert file2.getvalue() == "test"

    def test_fileno_returns_first_file_descriptor(self) -> None:
        """Test fileno returns file descriptor of first file."""
        # Use actual stdout as first file (has real file descriptor)
        file2 = StringIO()
        tee = TeeOutput(sys.stdout, file2)

        fileno = tee.fileno()

        assert isinstance(fileno, int)
        assert fileno == sys.stdout.fileno()


class TestAuditLog:
    """Tests for audit_log context manager."""

    def test_creates_log_file(self, tmp_path: Path) -> None:
        """Test audit log creates log file if it doesn't exist."""
        log_path = tmp_path / "audit" / "test.log"

        with audit_log(log_path):
            pass

        assert log_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test audit log creates parent directories."""
        log_path = tmp_path / "nested" / "audit" / "test.log"

        with audit_log(log_path):
            pass

        assert log_path.parent.exists()
        assert log_path.exists()

    def test_captures_stdout_to_file(self, tmp_path: Path) -> None:
        """Test stdout is captured to log file."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path):
            print("test message")

        log_content = log_path.read_text()
        assert "test message" in log_content

    def test_captures_stderr_to_file(self, tmp_path: Path) -> None:
        """Test stderr is captured to log file."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path):
            print("error message", file=sys.stderr)

        log_content = log_path.read_text()
        assert "error message" in log_content

    def test_captures_multiple_outputs(self, tmp_path: Path) -> None:
        """Test multiple print statements are all captured."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path):
            print("line 1")
            print("line 2", file=sys.stderr)
            print("line 3")

        log_content = log_path.read_text()
        assert "line 1" in log_content
        assert "line 2" in log_content
        assert "line 3" in log_content

    def test_restores_stdout_after_context(self, tmp_path: Path) -> None:
        """Test stdout is restored after context exits."""
        log_path = tmp_path / "test.log"
        original_stdout = sys.stdout

        with audit_log(log_path):
            pass

        assert sys.stdout == original_stdout

    def test_restores_stderr_after_context(self, tmp_path: Path) -> None:
        """Test stderr is restored after context exits."""
        log_path = tmp_path / "test.log"
        original_stderr = sys.stderr

        with audit_log(log_path):
            pass

        assert sys.stderr == original_stderr

    def test_restores_stdout_on_exception(self, tmp_path: Path) -> None:
        """Test stdout is restored even if exception occurs in context."""
        log_path = tmp_path / "test.log"
        original_stdout = sys.stdout

        with pytest.raises(ValueError):
            with audit_log(log_path):
                raise ValueError("test error")

        assert sys.stdout == original_stdout

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        """Test audit log appends to existing file instead of overwriting."""
        log_path = tmp_path / "test.log"
        log_path.write_text("existing content\n")

        with audit_log(log_path):
            print("new content")

        log_content = log_path.read_text()
        assert "existing content" in log_content
        assert "new content" in log_content

    def test_yields_log_path(self, tmp_path: Path) -> None:
        """Test context manager yields the log path."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path) as returned_path:
            assert returned_path == log_path

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Test audit log handles unicode content correctly."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path):
            print("Unicode: 你好 🚀 émojis")

        log_content = log_path.read_text()
        assert "你好" in log_content
        assert "🚀" in log_content
        assert "émojis" in log_content

    def test_multiline_output(self, tmp_path: Path) -> None:
        """Test audit log handles multiline output."""
        log_path = tmp_path / "test.log"

        with audit_log(log_path):
            print("line 1\nline 2\nline 3")

        log_content = log_path.read_text()
        assert "line 1" in log_content
        assert "line 2" in log_content
        assert "line 3" in log_content


class TestGenerateAuditLogPath:
    """Tests for generate_audit_log_path function."""

    def test_generates_path_with_timestamp(self, tmp_path: Path) -> None:
        """Test generated path includes timestamp."""
        audit_dir = tmp_path / "audit"

        log_path = generate_audit_log_path(audit_dir)

        assert log_path.parent == audit_dir
        assert log_path.name.startswith("nelson-")
        assert log_path.name.endswith(".log")

    def test_generates_unique_paths(self, tmp_path: Path) -> None:
        """Test generated paths are unique (or at least different format check)."""
        audit_dir = tmp_path / "audit"

        log_path = generate_audit_log_path(audit_dir)

        # Check format: nelson-YYYYMMDD-HHMMSS.log
        name = log_path.name
        assert name.startswith("nelson-")
        assert name.endswith(".log")
        assert len(name) == len("nelson-20260113-101253.log")

    def test_respects_audit_dir(self, tmp_path: Path) -> None:
        """Test generated path is in specified audit directory."""
        audit_dir = tmp_path / "custom" / "audit"

        log_path = generate_audit_log_path(audit_dir)

        assert log_path.parent == audit_dir

    def test_timestamp_format(self, tmp_path: Path) -> None:
        """Test timestamp has correct format YYYYMMDD-HHMMSS."""
        audit_dir = tmp_path / "audit"

        log_path = generate_audit_log_path(audit_dir)

        # Extract timestamp from nelson-YYYYMMDD-HHMMSS.log
        name = log_path.stem  # Remove .log extension
        timestamp = name.replace("nelson-", "")

        # Should be 15 characters: YYYYMMDD-HHMMSS
        assert len(timestamp) == 15
        assert timestamp[8] == "-"  # Separator between date and time
