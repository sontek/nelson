"""Audit logging with tee-like functionality for full session capture.

This module provides a context manager that captures all stdout/stderr to both
the console and a log file, similar to the Unix tee command. This provides a
complete audit trail of Nelson's execution.
"""

import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO


class TeeOutput:
    """Write to multiple file-like objects simultaneously (like Unix tee).

    This class wraps multiple file-like objects and writes to all of them when
    write() or flush() is called. Used for capturing stdout/stderr while still
    displaying to console.
    """

    def __init__(self, *files: TextIO) -> None:
        """Initialize with multiple file-like objects to write to.

        Args:
            *files: Variable number of file-like objects (must have write/flush methods)
        """
        self.files = files

    def write(self, data: str) -> int:
        """Write data to all wrapped file objects.

        Args:
            data: String to write

        Returns:
            Number of characters written (from first file)
        """
        result = 0
        for f in self.files:
            result = f.write(data)
        return result

    def flush(self) -> None:
        """Flush all wrapped file objects."""
        for f in self.files:
            f.flush()

    def fileno(self) -> int:
        """Return file descriptor of first file (required by some operations).

        Returns:
            File descriptor of first file object
        """
        return self.files[0].fileno()


@contextmanager
def audit_log(log_path: Path) -> Generator[Path, None, None]:
    """Context manager that captures all stdout/stderr to log file and console.

    Usage:
        with audit_log(Path(".ralph/audit/ralph-20260113-101253.log")):
            print("This goes to both console and log file")

    The log file is created (with parent directories) if it doesn't exist.
    All output is flushed immediately (unbuffered) for real-time logging.

    Args:
        log_path: Path to audit log file

    Yields:
        Path to the audit log file
    """
    # Ensure parent directories exist
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Save original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        # Open log file in append mode with unbuffered writing
        with open(log_path, "a", encoding="utf-8", buffering=1) as log_file:
            # Create tee objects that write to both console and log
            tee_stdout = TeeOutput(original_stdout, log_file)
            tee_stderr = TeeOutput(original_stderr, log_file)

            # Replace sys.stdout/stderr with tee objects
            sys.stdout = tee_stdout
            sys.stderr = tee_stderr

            yield log_path
    finally:
        # Always restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def generate_audit_log_path(audit_dir: Path) -> Path:
    """Generate a unique audit log path with timestamp.

    Args:
        audit_dir: Directory to store audit logs (e.g., .ralph/audit)

    Returns:
        Path to new audit log file (e.g., .ralph/audit/ralph-20260113-101253.log)
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return audit_dir / f"ralph-{timestamp}.log"
