"""Git utilities for Nelson workflow integration.

This module provides git operations needed by Nelson:
- Check if we're in a git repository
- Get current branch name
- Get starting commit for run tracking
- Get commit range (starting → current)
- Unstage unwanted files (.claude/, .ralph/)
- Check for uncommitted changes
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitStatus:
    """Git repository status information."""

    is_repo: bool
    branch: str | None
    has_uncommitted_changes: bool
    staged_files: list[str]
    modified_files: list[str]


class GitError(Exception):
    """Raised when git operations fail."""

    pass


def is_git_repo(path: Path | None = None) -> bool:
    """Check if the given path (or current directory) is in a git repository.

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        True if in a git repository, False otherwise.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["rev-parse", "--git-dir"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # git command not found
        return False


def get_current_branch(path: Path | None = None) -> str | None:
    """Get the current git branch name.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        Branch name, or None if not in a repo or detached HEAD.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["rev-parse", "--abbrev-ref", "HEAD"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        # Return None for detached HEAD
        return branch if branch != "HEAD" else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_git_status(path: Path | None = None) -> GitStatus:
    """Get comprehensive git status information.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        GitStatus object with repository status.
    """
    if not is_git_repo(path):
        return GitStatus(
            is_repo=False,
            branch=None,
            has_uncommitted_changes=False,
            staged_files=[],
            modified_files=[],
        )

    branch = get_current_branch(path)

    # Get staged files
    cmd_staged = ["git"]
    if path:
        cmd_staged.extend(["-C", str(path)])
    cmd_staged.extend(["diff", "--cached", "--name-only"])
    result_staged = subprocess.run(cmd_staged, capture_output=True, text=True, check=True)
    staged_files = [f for f in result_staged.stdout.strip().split("\n") if f]

    # Get modified files (unstaged changes)
    cmd_modified = ["git"]
    if path:
        cmd_modified.extend(["-C", str(path)])
    cmd_modified.extend(["diff", "--name-only"])
    result_modified = subprocess.run(cmd_modified, capture_output=True, text=True, check=True)
    modified_files = [f for f in result_modified.stdout.strip().split("\n") if f]

    # Get untracked files
    cmd_untracked = ["git"]
    if path:
        cmd_untracked.extend(["-C", str(path)])
    cmd_untracked.extend(["ls-files", "--others", "--exclude-standard"])
    result_untracked = subprocess.run(cmd_untracked, capture_output=True, text=True, check=True)
    untracked_files = [f for f in result_untracked.stdout.strip().split("\n") if f]

    has_changes = bool(staged_files or modified_files or untracked_files)

    return GitStatus(
        is_repo=True,
        branch=branch,
        has_uncommitted_changes=has_changes,
        staged_files=staged_files,
        modified_files=modified_files,
    )


def get_current_commit(path: Path | None = None) -> str:
    """Get the current commit SHA.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        Current commit SHA (full 40-character hash).

    Raises:
        GitError: If not in a git repo or git command fails.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["rev-parse", "HEAD"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to get current commit: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def get_commit_range(start_commit: str, path: Path | None = None) -> list[str]:
    """Get list of commit SHAs from start_commit to HEAD.

    Args:
        start_commit: Starting commit SHA.
        path: Repository path. Defaults to current directory.

    Returns:
        List of commit SHAs from start_commit (exclusive) to HEAD (inclusive).
        Returns empty list if start_commit is HEAD or doesn't exist.

    Raises:
        GitError: If git command fails.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["rev-list", f"{start_commit}..HEAD"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        commits = [c for c in result.stdout.strip().split("\n") if c]
        return commits
    except subprocess.CalledProcessError as e:
        # Empty range is not an error
        if "Invalid revision range" in e.stderr or not e.stderr:
            return []
        raise GitError(f"Failed to get commit range: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def unstage_files(patterns: list[str], path: Path | None = None) -> int:
    """Unstage files matching the given patterns.

    Args:
        patterns: List of file patterns to unstage (e.g., [".claude/", ".ralph/"]).
        path: Repository path. Defaults to current directory.

    Returns:
        Number of files unstaged.

    Raises:
        GitError: If git command fails.
    """
    if not patterns:
        return 0

    # First, check if there are any staged files matching the patterns
    cmd_check = ["git"]
    if path:
        cmd_check.extend(["-C", str(path)])
    cmd_check.extend(["diff", "--cached", "--name-only"])

    try:
        result = subprocess.run(
            cmd_check,
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f]

        # Filter to only files matching our patterns
        files_to_unstage = [
            f for f in staged_files if any(f.startswith(p) for p in patterns)
        ]

        if not files_to_unstage:
            return 0

        # Unstage the files
        cmd_unstage = ["git"]
        if path:
            cmd_unstage.extend(["-C", str(path)])
        cmd_unstage.extend(["reset", "HEAD", "--"] + files_to_unstage)

        subprocess.run(
            cmd_unstage,
            capture_output=True,
            text=True,
            check=True,
        )

        return len(files_to_unstage)
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to unstage files: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def unstage_ralph_files(path: Path | None = None) -> int:
    """Unstage .claude/ and .ralph/ files if they were accidentally staged.

    This is a convenience wrapper around unstage_files() for Nelson's specific use case.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        Number of files unstaged.

    Raises:
        GitError: If git command fails.
    """
    return unstage_files([".claude/", ".ralph/"], path)
