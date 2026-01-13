"""State file archiving for Nelson runs.

This module handles archiving old state files from previous runs before starting
a new run. This prevents state file conflicts and preserves history.
"""

from pathlib import Path

from nelson.config import STATE_FILE_NAME, NelsonConfig
from nelson.logging_config import get_logger
from nelson.run_manager import RunManager


def archive_old_state(config: NelsonConfig) -> None:
    """Archive old state files from previous run before starting new run.

    Looks for state.json in the ralph_dir (from a previous non-resumed run).
    If found, moves it to the most recent run directory, or creates a
    "ralph-previous-TIMESTAMP" archive directory if no runs exist yet.

    Args:
        config: Nelson configuration with directory paths
    """
    logger = get_logger()

    # Check for old state file in ralph_dir (from previous non-resumed run)
    old_state_file = config.ralph_dir / STATE_FILE_NAME

    if not old_state_file.exists():
        # No old state file to archive
        return

    # Find the most recent run directory to archive into
    last_run = RunManager.find_last_run(config)

    if last_run is not None:
        # Archive into most recent run directory
        archive_dir = last_run.run_dir
        logger.info(f"Archiving previous run state to: {archive_dir}")
    else:
        # First run ever, create a special archive directory
        from datetime import UTC, datetime

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        archive_dir = config.runs_dir / f"ralph-previous-{timestamp}"
        archive_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving previous run state to: {archive_dir}")

    # Move old state file to archive directory
    archive_state_path = archive_dir / STATE_FILE_NAME

    # If archive already has a state file, don't overwrite it
    if archive_state_path.exists():
        logger.debug(f"Archive already contains {STATE_FILE_NAME}, skipping move")
        old_state_file.unlink()  # Just delete the old one
    else:
        old_state_file.rename(archive_state_path)
        logger.debug(f"Moved {STATE_FILE_NAME} to archive")


def archive_file_if_exists(file_path: Path, archive_dir: Path) -> bool:
    """Archive a single file if it exists.

    Args:
        file_path: Path to file to archive
        archive_dir: Directory to move file into

    Returns:
        True if file was archived, False if it didn't exist
    """
    if not file_path.exists():
        return False

    archive_path = archive_dir / file_path.name

    # If archive already has this file, just delete the old one
    if archive_path.exists():
        file_path.unlink()
    else:
        file_path.rename(archive_path)

    return True
