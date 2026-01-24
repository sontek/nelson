"""Progress monitor for long-running Claude subprocess calls.

This module provides a background thread that monitors file activity
and prints periodic heartbeats during long-running Claude API calls,
giving users visibility into what's happening.
"""

import threading
import time
from datetime import datetime
from pathlib import Path

from nelson.logging_config import get_logger

logger = get_logger()


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as human-readable string.

    Args:
        seconds: Elapsed time in seconds

    Returns:
        Formatted string like "1h 23m" or "45s"
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def _format_bytes(bytes_count: int) -> str:
    """Format byte count as human-readable string.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string like "+1.2 KB" or "-500 B"
    """
    sign = "+" if bytes_count >= 0 else ""
    abs_bytes = abs(bytes_count)

    if abs_bytes < 1024:
        return f"{sign}{bytes_count} B"
    elif abs_bytes < 1024 * 1024:
        return f"{sign}{bytes_count / 1024:.1f} KB"
    else:
        return f"{sign}{bytes_count / (1024 * 1024):.1f} MB"


def _format_time_ago(seconds: float) -> str:
    """Format seconds as 'time ago' string.

    Args:
        seconds: Seconds since event

    Returns:
        Formatted string like "2m ago" or "just now"
    """
    if seconds < 5:
        return "just now"
    elif seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    else:
        return f"{int(seconds // 3600)}h ago"


class ProgressMonitor:
    """Monitor file activity and print heartbeats during long-running operations.

    This class runs a background thread that:
    1. Watches a directory for file changes (create, modify, delete)
    2. Prints file change notifications with timestamp and size delta
    3. Prints periodic heartbeat messages showing elapsed time
    4. Detects stalled processes (no activity for too long)

    Usage:
        monitor = ProgressMonitor(run_dir, heartbeat_interval=30.0)
        monitor.start()
        try:
            # Long-running operation
            subprocess.run(...)
        finally:
            monitor.stop()
    """

    def __init__(
        self,
        watch_dir: Path,
        heartbeat_interval: float = 60.0,
        check_interval: float = 2.0,
        max_idle_minutes: float = 15.0,
    ) -> None:
        """Initialize progress monitor.

        Args:
            watch_dir: Directory to watch for file changes
            heartbeat_interval: Seconds between heartbeat messages (default: 60)
            check_interval: Seconds between file checks (default: 2)
            max_idle_minutes: Minutes of no activity before flagging as stalled (default: 15)
        """
        self.watch_dir = Path(watch_dir)
        self.heartbeat_interval = heartbeat_interval
        self.check_interval = check_interval
        self.max_idle_seconds = max_idle_minutes * 60.0

        self._stop_event = threading.Event()
        self._stall_event = threading.Event()  # Set when stall detected
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._last_heartbeat: float = 0.0
        self._last_activity_time: float = 0.0
        self._last_activity_file: str = ""

        # File snapshots: path -> (mtime, size)
        self._file_snapshots: dict[str, tuple[float, int]] = {}

        # Track subprocess PID for display
        self._subprocess_pid: int | None = None

    @property
    def is_stalled(self) -> bool:
        """Check if the monitored process appears stalled.

        Returns:
            True if no file activity for longer than max_idle_seconds
        """
        return self._stall_event.is_set()

    def get_idle_seconds(self) -> float:
        """Get the number of seconds since last activity.

        Returns:
            Seconds since last file activity
        """
        if self._last_activity_time == 0:
            return 0.0
        return time.time() - self._last_activity_time

    def set_subprocess_pid(self, pid: int) -> None:
        """Set the subprocess PID for display in heartbeats.

        Args:
            pid: Process ID of the subprocess
        """
        self._subprocess_pid = pid

    def start(self) -> None:
        """Start the progress monitor background thread."""
        self._start_time = time.time()
        self._last_heartbeat = self._start_time
        self._last_activity_time = self._start_time
        self._stop_event.clear()
        self._stall_event.clear()

        # Take initial snapshot of files
        self._take_snapshot()

        # Start background thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the progress monitor background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _take_snapshot(self) -> None:
        """Take a snapshot of all files in the watch directory."""
        self._file_snapshots.clear()

        if not self.watch_dir.exists():
            return

        for path in self.watch_dir.iterdir():
            if path.is_file():
                try:
                    stat = path.stat()
                    self._file_snapshots[str(path)] = (stat.st_mtime, stat.st_size)
                except OSError:
                    # File may have been deleted between iterdir and stat
                    pass

    def _run(self) -> None:
        """Main loop for the background thread."""
        while not self._stop_event.is_set():
            now = time.time()

            # Check for file changes
            self._check_files()

            # Check for stall condition
            idle_seconds = self.get_idle_seconds()
            if idle_seconds >= self.max_idle_seconds and not self._stall_event.is_set():
                self._stall_event.set()
                idle_minutes = idle_seconds / 60.0
                logger.warning(
                    f"[STALL DETECTED] No file activity for {idle_minutes:.1f} minutes. "
                    f"Process may be hung."
                )

            # Print heartbeat if interval has passed
            if now - self._last_heartbeat >= self.heartbeat_interval:
                self._print_heartbeat()
                self._last_heartbeat = now

            # Wait for check interval or stop signal
            self._stop_event.wait(self.check_interval)

    def _check_files(self) -> None:
        """Check for file changes and print notifications."""
        if not self.watch_dir.exists():
            return

        now = time.time()
        current_files: dict[str, tuple[float, int]] = {}

        # Scan current files
        for path in self.watch_dir.iterdir():
            if path.is_file():
                try:
                    stat = path.stat()
                    current_files[str(path)] = (stat.st_mtime, stat.st_size)
                except OSError:
                    pass

        # Check for new or modified files
        for filepath, (mtime, size) in current_files.items():
            path = Path(filepath)
            filename = path.name

            if filepath not in self._file_snapshots:
                # New file
                self._print_file_change(filename, "created", size, None)
                self._last_activity_time = now
                self._last_activity_file = filename
            else:
                old_mtime, old_size = self._file_snapshots[filepath]
                if mtime > old_mtime:
                    # Modified file
                    size_delta = size - old_size
                    self._print_file_change(filename, "modified", size, size_delta)
                    self._last_activity_time = now
                    self._last_activity_file = filename

        # Check for deleted files
        for filepath in self._file_snapshots:
            if filepath not in current_files:
                path = Path(filepath)
                self._print_file_change(path.name, "deleted", None, None)
                self._last_activity_time = now
                self._last_activity_file = path.name

        # Update snapshot
        self._file_snapshots = current_files

    def _print_file_change(
        self,
        filename: str,
        action: str,
        size: int | None,
        size_delta: int | None,
    ) -> None:
        """Print a file change notification.

        Args:
            filename: Name of the file
            action: Action type (created, modified, deleted)
            size: Current file size (None for deleted)
            size_delta: Change in size (None for created/deleted)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        if action == "created":
            size_str = f" ({_format_bytes(size or 0)})" if size else ""
            logger.info(f"[{timestamp}] {filename} created{size_str}")
        elif action == "modified":
            if size_delta is not None and size_delta != 0:
                logger.info(f"[{timestamp}] {filename} modified ({_format_bytes(size_delta)})")
            else:
                logger.info(f"[{timestamp}] {filename} modified")
        elif action == "deleted":
            logger.info(f"[{timestamp}] {filename} deleted")

    def _print_heartbeat(self) -> None:
        """Print a heartbeat status message."""
        now = time.time()
        elapsed = now - self._start_time
        elapsed_str = _format_elapsed(elapsed)

        # Build heartbeat message
        parts = [f"Running... {elapsed_str} elapsed"]

        # Add last activity info if we have it
        if self._last_activity_file:
            activity_ago = now - self._last_activity_time
            time_ago = _format_time_ago(activity_ago)
            parts.append(f"last activity: {time_ago} ({self._last_activity_file})")

        # Add PID if we have it
        if self._subprocess_pid:
            parts.append(f"PID: {self._subprocess_pid}")

        # Add stall warning if stalled
        if self._stall_event.is_set():
            parts.append("STALLED")

        message = " | ".join(parts)
        logger.info(f"[heartbeat] {message}")
