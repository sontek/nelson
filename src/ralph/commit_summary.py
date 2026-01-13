"""Commit summary generation for Ralph workflow.

This module generates formatted summaries of git commits made during a Ralph session.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ralph.git_utils import GitError, get_commit_range, get_current_commit, is_git_repo
from ralph.logging_config import get_logger

logger = get_logger()


@dataclass(frozen=True)
class CommitSummary:
    """Summary of commits made during a Ralph session."""

    starting_commit: str
    current_commit: str
    commit_count: int
    commit_messages: list[str]

    @property
    def has_commits(self) -> bool:
        """Check if any commits were made."""
        return self.commit_count > 0


def get_commit_messages(
    start_commit: str, end_commit: str | None = None, path: Path | None = None
) -> list[str]:
    """Get formatted commit messages from start to end commit.

    Args:
        start_commit: Starting commit SHA.
        end_commit: Ending commit SHA. Defaults to HEAD.
        path: Repository path. Defaults to current directory.

    Returns:
        List of formatted commit messages (oneline format with decoration).

    Raises:
        GitError: If git command fails.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])

    # Build commit range
    commit_range = f"{start_commit}..{end_commit or 'HEAD'}"
    cmd.extend(["log", "--oneline", "--decorate", "--no-merges", commit_range])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        # Split by lines and filter empty lines
        messages = [line for line in result.stdout.strip().split("\n") if line]
        return messages
    except subprocess.CalledProcessError as e:
        # Empty range is not an error
        if not e.stderr or "does not have any commits yet" in e.stderr:
            return []
        raise GitError(f"Failed to get commit messages: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def generate_commit_summary(
    starting_commit: str, path: Path | None = None
) -> CommitSummary | None:
    """Generate a summary of commits made since starting_commit.

    Args:
        starting_commit: Starting commit SHA from state.
        path: Repository path. Defaults to current directory.

    Returns:
        CommitSummary object if commits were made, None if no starting commit
        or not in a git repo.
    """
    # Validate we're in a git repo
    if not is_git_repo(path):
        return None

    # Validate starting commit is provided
    if not starting_commit:
        return None

    try:
        current_commit = get_current_commit(path)

        # Check if any commits were made
        if starting_commit == current_commit:
            return CommitSummary(
                starting_commit=starting_commit,
                current_commit=current_commit,
                commit_count=0,
                commit_messages=[],
            )

        # Get commit range
        commits = get_commit_range(starting_commit, path)
        commit_count = len(commits)

        # Get formatted commit messages
        commit_messages = get_commit_messages(starting_commit, current_commit, path)

        return CommitSummary(
            starting_commit=starting_commit,
            current_commit=current_commit,
            commit_count=commit_count,
            commit_messages=commit_messages,
        )
    except GitError:
        # If git operations fail, return None
        return None


def display_commit_summary(summary: CommitSummary | None) -> None:
    """Display a formatted commit summary to the console.

    Args:
        summary: CommitSummary object to display, or None to skip.
    """
    if summary is None:
        return

    if not summary.has_commits:
        logger.info("No commits made during this Ralph session")
        return

    # Display header
    print()
    print("━" * 60)
    logger.success("Commits made during this Ralph session:")
    print("━" * 60)
    print()

    # Display commit range
    logger.info(f"Commit range: {summary.starting_commit}..{summary.current_commit}")
    print()

    # Display commit messages
    for message in summary.commit_messages:
        print(message)
    print()

    # Display commit count
    logger.info(f"Total commits: {summary.commit_count}")
    print()
