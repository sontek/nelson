"""Tests for state file archiving."""

from pathlib import Path

from nelson.archiver import archive_file_if_exists, archive_old_state
from nelson.config import STATE_FILE_NAME, NelsonConfig


class TestArchiveOldState:
    """Tests for archive_old_state function."""

    def test_no_old_state_file(self, tmp_path: Path) -> None:
        """Test that nothing happens when no old state file exists."""
        config = NelsonConfig(
            max_iterations=10,
            max_iterations_explicit=False,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("/usr/local/bin/claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Create directories
        config.ralph_dir.mkdir(parents=True)
        config.runs_dir.mkdir(parents=True)

        # No old state file exists
        old_state = config.ralph_dir / STATE_FILE_NAME
        assert not old_state.exists()

        # Should do nothing
        archive_old_state(config)

        # Still no state file
        assert not old_state.exists()

    def test_archive_into_most_recent_run(self, tmp_path: Path) -> None:
        """Test archiving into most recent run directory."""
        config = NelsonConfig(
            max_iterations=10,
            max_iterations_explicit=False,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("/usr/local/bin/claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Create directories
        config.ralph_dir.mkdir(parents=True)
        config.runs_dir.mkdir(parents=True)

        # Create a previous run directory
        prev_run_dir = config.runs_dir / "ralph-20260113-100000"
        prev_run_dir.mkdir()

        # Create old state file
        old_state = config.ralph_dir / STATE_FILE_NAME
        old_state.write_text('{"test": "data"}')

        # Archive it
        archive_old_state(config)

        # Old state should be gone
        assert not old_state.exists()

        # Should be in previous run directory
        archived_state = prev_run_dir / STATE_FILE_NAME
        assert archived_state.exists()
        assert archived_state.read_text() == '{"test": "data"}'

    def test_archive_creates_previous_directory(self, tmp_path: Path) -> None:
        """Test creating ralph-previous-TIMESTAMP directory when no runs exist."""
        config = NelsonConfig(
            max_iterations=10,
            max_iterations_explicit=False,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("/usr/local/bin/claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Create directories
        config.ralph_dir.mkdir(parents=True)
        config.runs_dir.mkdir(parents=True)

        # Create old state file
        old_state = config.ralph_dir / STATE_FILE_NAME
        old_state.write_text('{"test": "data"}')

        # Archive it (no previous runs exist)
        archive_old_state(config)

        # Old state should be gone
        assert not old_state.exists()

        # Should have created ralph-previous-TIMESTAMP directory
        archive_dirs = list(config.runs_dir.glob("ralph-previous-*"))
        assert len(archive_dirs) == 1
        archive_dir = archive_dirs[0]

        # State file should be in archive
        archived_state = archive_dir / STATE_FILE_NAME
        assert archived_state.exists()
        assert archived_state.read_text() == '{"test": "data"}'

    def test_archive_deletes_if_target_exists(self, tmp_path: Path) -> None:
        """Test that old state is deleted if archive already has state.json."""
        config = NelsonConfig(
            max_iterations=10,
            max_iterations_explicit=False,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("/usr/local/bin/claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Create directories
        config.ralph_dir.mkdir(parents=True)
        config.runs_dir.mkdir(parents=True)

        # Create a previous run directory with existing state.json
        prev_run_dir = config.runs_dir / "ralph-20260113-100000"
        prev_run_dir.mkdir()
        existing_state = prev_run_dir / STATE_FILE_NAME
        existing_state.write_text('{"existing": "state"}')

        # Create old state file
        old_state = config.ralph_dir / STATE_FILE_NAME
        old_state.write_text('{"test": "data"}')

        # Archive it
        archive_old_state(config)

        # Old state should be gone
        assert not old_state.exists()

        # Archive should still have original state (not overwritten)
        assert existing_state.exists()
        assert existing_state.read_text() == '{"existing": "state"}'

    def test_archive_prefers_most_recent_run(self, tmp_path: Path) -> None:
        """Test that archiving uses most recent run directory."""
        config = NelsonConfig(
            max_iterations=10,
            max_iterations_explicit=False,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("/usr/local/bin/claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Create directories
        config.ralph_dir.mkdir(parents=True)
        config.runs_dir.mkdir(parents=True)

        # Create multiple previous run directories
        old_run_dir = config.runs_dir / "ralph-20260113-100000"
        old_run_dir.mkdir()
        recent_run_dir = config.runs_dir / "ralph-20260113-110000"
        recent_run_dir.mkdir()

        # Create old state file
        old_state = config.ralph_dir / STATE_FILE_NAME
        old_state.write_text('{"test": "data"}')

        # Archive it
        archive_old_state(config)

        # Old state should be gone
        assert not old_state.exists()

        # Should be in most recent run directory
        archived_state = recent_run_dir / STATE_FILE_NAME
        assert archived_state.exists()
        assert archived_state.read_text() == '{"test": "data"}'

        # Should NOT be in older run directory
        old_archived_state = old_run_dir / STATE_FILE_NAME
        assert not old_archived_state.exists()


class TestArchiveFileIfExists:
    """Tests for archive_file_if_exists helper function."""

    def test_archive_existing_file(self, tmp_path: Path) -> None:
        """Test archiving an existing file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test content")

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        result = archive_file_if_exists(file_path, archive_dir)

        assert result is True
        assert not file_path.exists()
        archived_file = archive_dir / "test.txt"
        assert archived_file.exists()
        assert archived_file.read_text() == "test content"

    def test_archive_nonexistent_file(self, tmp_path: Path) -> None:
        """Test archiving a file that doesn't exist."""
        file_path = tmp_path / "nonexistent.txt"
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        result = archive_file_if_exists(file_path, archive_dir)

        assert result is False
        assert not (archive_dir / "nonexistent.txt").exists()

    def test_archive_overwrites_existing_target(self, tmp_path: Path) -> None:
        """Test that existing file in archive is handled properly."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("new content")

        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        existing_file = archive_dir / "test.txt"
        existing_file.write_text("old content")

        result = archive_file_if_exists(file_path, archive_dir)

        assert result is True
        assert not file_path.exists()
        # Original file in archive should remain unchanged
        assert existing_file.exists()
        assert existing_file.read_text() == "old content"
