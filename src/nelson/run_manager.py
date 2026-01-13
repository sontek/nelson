"""Run directory management for Ralph.

This module handles creation and management of unique run directories in .ralph/runs/.
Each run gets a unique timestamped directory containing its state, plan, decisions, and audit log.
"""

from datetime import UTC, datetime
from pathlib import Path

from nelson.config import (
    AUDIT_FILE_NAME,
    DECISIONS_FILE_NAME,
    PLAN_FILE_NAME,
    STATE_FILE_NAME,
    NelsonConfig,
)


class RunManager:
    """Manages unique run directories for Ralph execution.

    Each run gets a unique directory like .ralph/runs/ralph-20260113-101253/
    containing state.json, plan.md, decisions.md, and audit.log.
    """

    def __init__(self, config: NelsonConfig, run_id: str | None = None) -> None:
        """Initialize run manager.

        Args:
            config: Ralph configuration
            run_id: Optional explicit run ID (for resume).
                   If None, generates new timestamp-based ID.
        """
        self.config = config
        self.run_id = run_id or self._generate_run_id()
        self.run_dir = config.runs_dir / f"ralph-{self.run_id}"

    def _generate_run_id(self) -> str:
        """Generate unique run ID from current timestamp.

        Returns:
            Run ID in format YYYYMMDD-HHMMSS (e.g., "20260113-101253")
        """
        now = datetime.now(UTC)
        return now.strftime("%Y%m%d-%H%M%S")

    def create_run_directory(self) -> None:
        """Create the run directory and ensure parent directories exist.

        Raises:
            FileExistsError: If run directory already exists (shouldn't happen with timestamps)
        """
        # Ensure parent directories exist
        self.config.ensure_directories()

        # Create the specific run directory
        self.run_dir.mkdir(parents=False, exist_ok=False)

    def get_state_path(self) -> Path:
        """Get path to state.json for this run."""
        return self.run_dir / STATE_FILE_NAME

    def get_plan_path(self) -> Path:
        """Get path to plan.md for this run."""
        return self.run_dir / PLAN_FILE_NAME

    def get_decisions_path(self) -> Path:
        """Get path to decisions.md for this run."""
        return self.run_dir / DECISIONS_FILE_NAME

    def get_audit_path(self) -> Path:
        """Get path to audit.log for this run."""
        return self.run_dir / AUDIT_FILE_NAME

    def run_exists(self) -> bool:
        """Check if run directory exists.

        Returns:
            True if run directory exists, False otherwise
        """
        return self.run_dir.exists()

    @classmethod
    def find_last_run(cls, config: NelsonConfig) -> "RunManager | None":
        """Find the most recent run directory.

        Args:
            config: Ralph configuration

        Returns:
            RunManager for most recent run, or None if no runs exist
        """
        runs_dir = config.runs_dir
        if not runs_dir.exists():
            return None

        # Find all run directories (format: ralph-YYYYMMDD-HHMMSS)
        run_dirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("ralph-")]

        if not run_dirs:
            return None

        # Sort by name (timestamp) to get most recent
        run_dirs.sort(reverse=True)
        last_run_dir = run_dirs[0]

        # Extract run ID from directory name (remove "ralph-" prefix)
        run_id = last_run_dir.name.replace("ralph-", "")

        return cls(config, run_id=run_id)

    @classmethod
    def from_run_path(cls, config: NelsonConfig, run_path: Path) -> "RunManager":
        """Create RunManager from an existing run directory path.

        Args:
            config: Ralph configuration
            run_path: Path to existing run directory

        Returns:
            RunManager instance for the given run

        Raises:
            ValueError: If run_path doesn't match expected format or doesn't exist
        """
        if not run_path.exists():
            raise ValueError(f"Run directory does not exist: {run_path}")

        if not run_path.is_dir():
            raise ValueError(f"Run path is not a directory: {run_path}")

        # Extract run ID from directory name
        if not run_path.name.startswith("ralph-"):
            raise ValueError(
                f"Invalid run directory name: {run_path.name} "
                "(expected format: ralph-YYYYMMDD-HHMMSS)"
            )

        run_id = run_path.name.replace("ralph-", "")

        return cls(config, run_id=run_id)
