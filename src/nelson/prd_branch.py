"""Git branch management for nelson-prd.

This module provides utilities for creating and managing git branches
per PRD task, including branch name generation with slugification.
"""

import re
import subprocess
from pathlib import Path

from nelson.git_utils import GitError, get_current_branch, get_git_status


def slugify_task_text(text: str, max_length: int = 40) -> str:
    """Convert task text to URL-friendly slug.

    Converts to lowercase, removes special characters, replaces spaces
    with hyphens, and truncates to max_length.

    Args:
        text: Task description text
        max_length: Maximum slug length (default 40)

    Returns:
        Slugified text suitable for branch names

    Examples:
        >>> slugify_task_text("Add User Authentication System")
        'add-user-authentication-system'
        >>> slugify_task_text("Fix bug in API (issue #123)", max_length=20)
        'fix-bug-in-api-issue'
    """
    # Convert to lowercase
    slug = text.lower()

    # Remove special characters, keep alphanumeric and spaces
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)

    # Replace multiple spaces/hyphens with single hyphen
    slug = re.sub(r"[\s-]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def generate_branch_name(task_id: str, task_text: str) -> str:
    """Generate branch name for PRD task.

    Format: feature/PRD-NNN-{slugified-description}

    Args:
        task_id: Task ID (e.g., "PRD-001")
        task_text: Task description

    Returns:
        Branch name

    Examples:
        >>> generate_branch_name("PRD-001", "Add user authentication")
        'feature/PRD-001-add-user-authentication'
        >>> generate_branch_name("PRD-042", "Fix critical bug in payment system")
        'feature/PRD-042-fix-critical-bug-in-payment-system'
    """
    slug = slugify_task_text(task_text)
    return f"feature/{task_id}-{slug}"


def branch_exists(branch_name: str, path: Path | None = None) -> bool:
    """Check if a git branch exists.

    Args:
        branch_name: Branch name to check
        path: Repository path. Defaults to current directory.

    Returns:
        True if branch exists, False otherwise
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["rev-parse", "--verify", f"refs/heads/{branch_name}"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def create_branch(
    branch_name: str, path: Path | None = None, force: bool = False
) -> None:
    """Create a new git branch.

    Args:
        branch_name: Name of branch to create
        path: Repository path. Defaults to current directory.
        force: If True, overwrite existing branch

    Raises:
        GitError: If branch creation fails
        ValueError: If branch already exists and force=False
    """
    # Check if branch already exists
    if branch_exists(branch_name, path) and not force:
        raise ValueError(f"Branch already exists: {branch_name}")

    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.append("branch")
    if force:
        cmd.append("-f")
    cmd.append(branch_name)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to create branch {branch_name}: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def switch_branch(branch_name: str, path: Path | None = None) -> None:
    """Switch to a different git branch.

    Args:
        branch_name: Name of branch to switch to
        path: Repository path. Defaults to current directory.

    Raises:
        GitError: If branch switch fails or there are uncommitted changes
    """
    # Check for uncommitted changes
    status = get_git_status(path)
    if status.has_uncommitted_changes:
        raise GitError(
            "Cannot switch branches: You have uncommitted changes. "
            "Please commit or stash your changes first."
        )

    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["checkout", branch_name])

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to switch to branch {branch_name}: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def create_and_switch_branch(
    branch_name: str, path: Path | None = None, force: bool = False
) -> None:
    """Create a new branch and switch to it.

    Args:
        branch_name: Name of branch to create and switch to
        path: Repository path. Defaults to current directory.
        force: If True, overwrite existing branch

    Raises:
        GitError: If operation fails
        ValueError: If branch already exists and force=False
    """
    # Check if branch exists
    exists = branch_exists(branch_name, path)

    if exists:
        if not force:
            # Branch exists, just switch to it
            switch_branch(branch_name, path)
            return
        else:
            # Force recreate - delete and recreate
            delete_branch(branch_name, path, force=True)

    # Create new branch and switch to it
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["checkout", "-b", branch_name])

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(
            f"Failed to create and switch to branch {branch_name}: {e.stderr}"
        ) from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def delete_branch(
    branch_name: str, path: Path | None = None, force: bool = False
) -> None:
    """Delete a git branch.

    Args:
        branch_name: Name of branch to delete
        path: Repository path. Defaults to current directory.
        force: If True, force delete even if unmerged

    Raises:
        GitError: If branch deletion fails
    """
    # Check if we're on the branch we're trying to delete
    current = get_current_branch(path)
    if current == branch_name:
        raise GitError(f"Cannot delete current branch: {branch_name}")

    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.append("branch")
    cmd.append("-D" if force else "-d")
    cmd.append(branch_name)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise GitError(f"Failed to delete branch {branch_name}: {e.stderr}") from e
    except FileNotFoundError as e:
        raise GitError("git command not found") from e


def ensure_branch_for_task(
    task_id: str, task_text: str, path: Path | None = None
) -> str:
    """Ensure a branch exists for the task and switch to it.

    If the branch already exists, just switch to it.
    Otherwise, create it and switch.

    Args:
        task_id: Task ID (e.g., "PRD-001")
        task_text: Task description
        path: Repository path. Defaults to current directory.

    Returns:
        Branch name that was created/switched to

    Raises:
        GitError: If operation fails
    """
    branch_name = generate_branch_name(task_id, task_text)

    # Check if branch exists
    if branch_exists(branch_name, path):
        # Branch exists, switch to it
        switch_branch(branch_name, path)
    else:
        # Create and switch to new branch
        create_and_switch_branch(branch_name, path)

    return branch_name
