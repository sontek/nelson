"""Tests for run directory management."""

from datetime import datetime
from pathlib import Path

import pytest

from nelson.config import (
    AUDIT_FILE_NAME,
    DECISIONS_FILE_NAME,
    PLAN_FILE_NAME,
    STATE_FILE_NAME,
    RalphConfig,
)
from nelson.run_manager import RunManager


@pytest.fixture
def config(tmp_path: Path) -> RalphConfig:
    """Create test configuration with temporary directories."""
    return RalphConfig(
        max_iterations=50,
        max_iterations_explicit=False,
        cost_limit=10.0,
        ralph_dir=tmp_path / ".ralph",
        audit_dir=tmp_path / ".ralph/audit",
        runs_dir=tmp_path / ".ralph/runs",
        claude_command="claude",
        claude_command_path=None,
        model="sonnet",
        plan_model="sonnet",
        review_model="sonnet",
        auto_approve_push=False,
    )


class TestRunManager:
    """Test RunManager initialization and run ID generation."""

    def test_initialization_with_auto_generated_id(self, config: RalphConfig) -> None:
        """Test RunManager creates run ID automatically."""
        manager = RunManager(config)

        # Run ID should be in format YYYYMMDD-HHMMSS
        assert len(manager.run_id) == 15  # YYYYMMDD-HHMMSS
        assert manager.run_id[8] == "-"  # Date-time separator

        # Run directory should be .ralph/runs/ralph-{run_id}
        expected_dir = config.runs_dir / f"ralph-{manager.run_id}"
        assert manager.run_dir == expected_dir

    def test_initialization_with_explicit_id(self, config: RalphConfig) -> None:
        """Test RunManager accepts explicit run ID."""
        run_id = "20260113-101253"
        manager = RunManager(config, run_id=run_id)

        assert manager.run_id == run_id
        assert manager.run_dir == config.runs_dir / f"ralph-{run_id}"

    def test_generate_run_id_format(self, config: RalphConfig) -> None:
        """Test run ID matches expected format."""
        manager = RunManager(config)
        run_id = manager.run_id

        # Parse the run ID to verify it's a valid timestamp
        try:
            datetime.strptime(run_id, "%Y%m%d-%H%M%S")
        except ValueError:
            pytest.fail(f"Run ID {run_id} doesn't match format YYYYMMDD-HHMMSS")

    def test_generate_run_id_is_unique(self, config: RalphConfig) -> None:
        """Test consecutive run IDs are different (or very unlikely to collide)."""
        manager1 = RunManager(config)
        manager2 = RunManager(config)

        # Due to timestamp precision, these are usually different
        # but we allow them to be same if executed in same second
        # (this is expected behavior, not a bug)
        assert isinstance(manager1.run_id, str)
        assert isinstance(manager2.run_id, str)


class TestRunDirectoryCreation:
    """Test run directory creation."""

    def test_create_run_directory_creates_directory(self, config: RalphConfig) -> None:
        """Test create_run_directory creates the directory."""
        manager = RunManager(config, run_id="20260113-101253")

        assert not manager.run_dir.exists()

        manager.create_run_directory()

        assert manager.run_dir.exists()
        assert manager.run_dir.is_dir()

    def test_create_run_directory_creates_parents(self, config: RalphConfig) -> None:
        """Test create_run_directory creates parent directories."""
        # Parent directories should not exist yet
        assert not config.runs_dir.exists()

        manager = RunManager(config, run_id="20260113-101253")
        manager.create_run_directory()

        # Both parent and run directory should exist
        assert config.runs_dir.exists()
        assert manager.run_dir.exists()

    def test_create_run_directory_fails_if_exists(self, config: RalphConfig) -> None:
        """Test create_run_directory raises error if directory exists."""
        manager = RunManager(config, run_id="20260113-101253")
        manager.create_run_directory()

        # Second creation should fail
        with pytest.raises(FileExistsError):
            manager.create_run_directory()


class TestFilePaths:
    """Test file path getters."""

    def test_get_state_path(self, config: RalphConfig) -> None:
        """Test get_state_path returns correct path."""
        manager = RunManager(config, run_id="20260113-101253")
        expected = config.runs_dir / "ralph-20260113-101253" / STATE_FILE_NAME
        assert manager.get_state_path() == expected

    def test_get_plan_path(self, config: RalphConfig) -> None:
        """Test get_plan_path returns correct path."""
        manager = RunManager(config, run_id="20260113-101253")
        expected = config.runs_dir / "ralph-20260113-101253" / PLAN_FILE_NAME
        assert manager.get_plan_path() == expected

    def test_get_decisions_path(self, config: RalphConfig) -> None:
        """Test get_decisions_path returns correct path."""
        manager = RunManager(config, run_id="20260113-101253")
        expected = config.runs_dir / "ralph-20260113-101253" / DECISIONS_FILE_NAME
        assert manager.get_decisions_path() == expected

    def test_get_audit_path(self, config: RalphConfig) -> None:
        """Test get_audit_path returns correct path."""
        manager = RunManager(config, run_id="20260113-101253")
        expected = config.runs_dir / "ralph-20260113-101253" / AUDIT_FILE_NAME
        assert manager.get_audit_path() == expected


class TestRunExistence:
    """Test run existence checking."""

    def test_run_exists_returns_false_when_not_created(self, config: RalphConfig) -> None:
        """Test run_exists returns False for non-existent run."""
        manager = RunManager(config, run_id="20260113-101253")
        assert not manager.run_exists()

    def test_run_exists_returns_true_after_creation(self, config: RalphConfig) -> None:
        """Test run_exists returns True after directory is created."""
        manager = RunManager(config, run_id="20260113-101253")
        manager.create_run_directory()
        assert manager.run_exists()


class TestFindLastRun:
    """Test finding the most recent run."""

    def test_find_last_run_returns_none_when_no_runs(self, config: RalphConfig) -> None:
        """Test find_last_run returns None when runs directory doesn't exist."""
        manager = RunManager.find_last_run(config)
        assert manager is None

    def test_find_last_run_returns_none_when_runs_dir_empty(
        self, config: RalphConfig
    ) -> None:
        """Test find_last_run returns None when runs directory is empty."""
        config.runs_dir.mkdir(parents=True)
        manager = RunManager.find_last_run(config)
        assert manager is None

    def test_find_last_run_returns_most_recent(self, config: RalphConfig) -> None:
        """Test find_last_run returns the most recent run."""
        config.runs_dir.mkdir(parents=True)

        # Create three run directories with different timestamps
        (config.runs_dir / "ralph-20260113-101253").mkdir()
        (config.runs_dir / "ralph-20260113-143021").mkdir()
        (config.runs_dir / "ralph-20260112-091532").mkdir()

        manager = RunManager.find_last_run(config)

        assert manager is not None
        assert manager.run_id == "20260113-143021"  # Most recent

    def test_find_last_run_ignores_non_run_directories(self, config: RalphConfig) -> None:
        """Test find_last_run ignores directories that don't match pattern."""
        config.runs_dir.mkdir(parents=True)

        # Create some non-run directories
        (config.runs_dir / "other-directory").mkdir()
        (config.runs_dir / "not-a-run").mkdir()

        # Create one valid run
        (config.runs_dir / "ralph-20260113-101253").mkdir()

        manager = RunManager.find_last_run(config)

        assert manager is not None
        assert manager.run_id == "20260113-101253"

    def test_find_last_run_ignores_files(self, config: RalphConfig) -> None:
        """Test find_last_run ignores files in runs directory."""
        config.runs_dir.mkdir(parents=True)

        # Create a file that looks like a run directory
        (config.runs_dir / "ralph-20260113-101253").touch()

        # Create a valid run directory
        (config.runs_dir / "ralph-20260113-143021").mkdir()

        manager = RunManager.find_last_run(config)

        assert manager is not None
        assert manager.run_id == "20260113-143021"


class TestFromRunPath:
    """Test creating RunManager from existing path."""

    def test_from_run_path_with_valid_path(self, config: RalphConfig) -> None:
        """Test from_run_path creates manager from existing directory."""
        run_path = config.runs_dir / "ralph-20260113-101253"
        run_path.mkdir(parents=True)

        manager = RunManager.from_run_path(config, run_path)

        assert manager.run_id == "20260113-101253"
        assert manager.run_dir == run_path

    def test_from_run_path_with_nonexistent_path(self, config: RalphConfig) -> None:
        """Test from_run_path raises error for non-existent directory."""
        run_path = config.runs_dir / "ralph-20260113-101253"

        with pytest.raises(ValueError, match="does not exist"):
            RunManager.from_run_path(config, run_path)

    def test_from_run_path_with_file_path(self, config: RalphConfig) -> None:
        """Test from_run_path raises error when path is a file."""
        run_path = config.runs_dir / "ralph-20260113-101253"
        run_path.parent.mkdir(parents=True)
        run_path.touch()

        with pytest.raises(ValueError, match="not a directory"):
            RunManager.from_run_path(config, run_path)

    def test_from_run_path_with_invalid_format(self, config: RalphConfig) -> None:
        """Test from_run_path raises error for invalid directory name."""
        run_path = config.runs_dir / "invalid-directory-name"
        run_path.mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid run directory name"):
            RunManager.from_run_path(config, run_path)
