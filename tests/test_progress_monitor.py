"""Tests for the progress_monitor module."""

import tempfile
import time
from pathlib import Path

import pytest

from nelson.progress_monitor import (
    ProgressMonitor,
    _format_bytes,
    _format_elapsed,
    _format_time_ago,
)


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_format_elapsed_seconds(self) -> None:
        """Test formatting seconds."""
        assert _format_elapsed(5) == "5s"
        assert _format_elapsed(45) == "45s"

    def test_format_elapsed_minutes(self) -> None:
        """Test formatting minutes."""
        assert _format_elapsed(60) == "1m 0s"
        assert _format_elapsed(90) == "1m 30s"
        assert _format_elapsed(3599) == "59m 59s"

    def test_format_elapsed_hours(self) -> None:
        """Test formatting hours."""
        assert _format_elapsed(3600) == "1h 0m"
        assert _format_elapsed(3660) == "1h 1m"
        assert _format_elapsed(7200) == "2h 0m"

    def test_format_bytes_small(self) -> None:
        """Test formatting small byte counts."""
        assert _format_bytes(0) == "+0 B"
        assert _format_bytes(100) == "+100 B"
        assert _format_bytes(1023) == "+1023 B"

    def test_format_bytes_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert _format_bytes(1024) == "+1.0 KB"
        assert _format_bytes(1536) == "+1.5 KB"

    def test_format_bytes_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert _format_bytes(1024 * 1024) == "+1.0 MB"
        assert _format_bytes(1024 * 1024 * 2) == "+2.0 MB"

    def test_format_bytes_negative(self) -> None:
        """Test formatting negative byte counts."""
        assert _format_bytes(-100) == "-100 B"
        assert _format_bytes(-1024) == "-1.0 KB"

    def test_format_time_ago_just_now(self) -> None:
        """Test 'just now' formatting."""
        assert _format_time_ago(0) == "just now"
        assert _format_time_ago(4) == "just now"

    def test_format_time_ago_seconds(self) -> None:
        """Test seconds ago formatting."""
        assert _format_time_ago(5) == "5s ago"
        assert _format_time_ago(59) == "59s ago"

    def test_format_time_ago_minutes(self) -> None:
        """Test minutes ago formatting."""
        assert _format_time_ago(60) == "1m ago"
        assert _format_time_ago(120) == "2m ago"

    def test_format_time_ago_hours(self) -> None:
        """Test hours ago formatting."""
        assert _format_time_ago(3600) == "1h ago"
        assert _format_time_ago(7200) == "2h ago"


class TestProgressMonitor:
    """Tests for the ProgressMonitor class."""

    def test_init(self) -> None:
        """Test monitor initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=30.0,
                check_interval=1.0,
            )
            assert monitor.watch_dir == Path(tmp_dir)
            assert monitor.heartbeat_interval == 30.0
            assert monitor.check_interval == 1.0

    def test_start_stop(self) -> None:
        """Test starting and stopping the monitor."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=60.0,
                check_interval=0.1,
            )
            monitor.start()
            assert monitor._thread is not None
            thread = monitor._thread  # Save reference before stop
            assert thread.is_alive()

            monitor.stop()
            # Give thread time to stop
            time.sleep(0.3)
            assert not thread.is_alive()

    def test_set_subprocess_pid(self) -> None:
        """Test setting subprocess PID."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(watch_dir=Path(tmp_dir))
            monitor.set_subprocess_pid(12345)
            assert monitor._subprocess_pid == 12345

    def test_detects_new_file(self, capsys: pytest.CaptureFixture) -> None:
        """Test that monitor detects new files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=60.0,
                check_interval=0.1,
            )
            monitor.start()

            # Create a new file
            time.sleep(0.2)
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("hello world")

            # Wait for detection
            time.sleep(0.3)
            monitor.stop()

            # Check output
            captured = capsys.readouterr()
            assert "test.txt created" in captured.out

    def test_detects_file_modification(self, capsys: pytest.CaptureFixture) -> None:
        """Test that monitor detects file modifications."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create file before starting monitor
            test_file = Path(tmp_dir) / "existing.txt"
            test_file.write_text("initial content")

            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=60.0,
                check_interval=0.1,
            )
            monitor.start()

            # Modify the file
            time.sleep(0.2)
            test_file.write_text("modified content with more data")

            # Wait for detection
            time.sleep(0.3)
            monitor.stop()

            # Check output
            captured = capsys.readouterr()
            assert "existing.txt modified" in captured.out

    def test_detects_file_deletion(self, capsys: pytest.CaptureFixture) -> None:
        """Test that monitor detects file deletions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create file before starting monitor
            test_file = Path(tmp_dir) / "deleteme.txt"
            test_file.write_text("content")

            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=60.0,
                check_interval=0.1,
            )
            monitor.start()

            # Delete the file
            time.sleep(0.2)
            test_file.unlink()

            # Wait for detection
            time.sleep(0.3)
            monitor.stop()

            # Check output
            captured = capsys.readouterr()
            assert "deleteme.txt deleted" in captured.out

    def test_heartbeat_includes_pid(self, capsys: pytest.CaptureFixture) -> None:
        """Test that heartbeat includes PID when set."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                heartbeat_interval=0.1,  # Short interval for testing
                check_interval=0.05,
            )
            monitor.set_subprocess_pid(99999)
            monitor.start()

            # Wait for heartbeat
            time.sleep(0.3)
            monitor.stop()

            # Check output - heartbeat shows elapsed time and PID
            captured = capsys.readouterr()
            assert "Running..." in captured.out
            assert "PID: 99999" in captured.out

    def test_nonexistent_directory_handled(self) -> None:
        """Test that monitor handles non-existent directories gracefully."""
        monitor = ProgressMonitor(
            watch_dir=Path("/nonexistent/directory"),
            heartbeat_interval=60.0,
            check_interval=0.1,
        )
        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        # Should not raise any errors


class TestStallDetection:
    """Tests for stall detection functionality."""

    def test_not_stalled_initially(self) -> None:
        """Test that monitor is not stalled when first started."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                max_idle_minutes=0.01,  # Very short for testing (0.6 seconds)
            )
            monitor.start()
            # Should not be stalled immediately
            assert not monitor.is_stalled
            monitor.stop()

    def test_stall_detected_after_idle(self) -> None:
        """Test that monitor detects stall after max_idle_minutes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                max_idle_minutes=0.01,  # 0.6 seconds
                check_interval=0.1,
            )
            monitor.start()

            # Wait for stall detection
            time.sleep(1.0)

            assert monitor.is_stalled
            monitor.stop()

    def test_activity_resets_stall(self) -> None:
        """Test that file activity prevents stall detection."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                max_idle_minutes=0.05,  # 3 seconds
                check_interval=0.1,
            )
            monitor.start()

            # Create file activity before stall threshold
            time.sleep(1.0)
            test_file = Path(tmp_dir) / "activity.txt"
            test_file.write_text("keeping alive")

            # Wait a bit more but not past threshold
            time.sleep(1.0)

            # Should not be stalled because we had activity
            assert not monitor.is_stalled
            monitor.stop()

    def test_get_idle_seconds(self) -> None:
        """Test that get_idle_seconds returns correct value."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                check_interval=0.1,
            )
            monitor.start()

            # Wait a bit
            time.sleep(0.5)

            idle = monitor.get_idle_seconds()
            assert idle >= 0.4  # Should be at least 0.4 seconds
            assert idle < 2.0  # But not too long

            monitor.stop()

    def test_stall_warning_logged(self, capsys: pytest.CaptureFixture) -> None:
        """Test that stall detection logs a warning."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            monitor = ProgressMonitor(
                watch_dir=Path(tmp_dir),
                max_idle_minutes=0.01,  # 0.6 seconds
                check_interval=0.1,
            )
            monitor.start()

            # Wait for stall detection
            time.sleep(1.0)
            monitor.stop()

            captured = capsys.readouterr()
            assert "STALL DETECTED" in captured.out

    def test_max_idle_minutes_configurable(self) -> None:
        """Test that max_idle_minutes can be configured."""
        monitor = ProgressMonitor(
            watch_dir=Path("/tmp"),
            max_idle_minutes=30.0,
        )
        assert monitor.max_idle_seconds == 30.0 * 60.0  # 1800 seconds
