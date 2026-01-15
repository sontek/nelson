"""Git author validation for Nelson commit attribution.

This module validates that git user.name and user.email are configured
before Nelson creates commits, ensuring proper attribution of all
Nelson-generated commits.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitAuthor:
    """Git author information."""

    name: str | None
    email: str | None
    is_configured: bool


class GitAuthError(Exception):
    """Raised when git author validation fails."""

    pass


def get_git_author(path: Path | None = None) -> GitAuthor:
    """Get git author information from git config.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        GitAuthor object with name, email, and configuration status.
    """
    name = _get_git_config("user.name", path)
    email = _get_git_config("user.email", path)
    is_configured = name is not None and email is not None

    return GitAuthor(name=name, email=email, is_configured=is_configured)


def validate_git_author(path: Path | None = None) -> GitAuthor:
    """Validate that git author information is configured.

    Args:
        path: Repository path. Defaults to current directory.

    Returns:
        GitAuthor object with validated author information.

    Raises:
        GitAuthError: If user.name or user.email is not configured.
    """
    author = get_git_author(path)

    if not author.is_configured:
        missing = []
        if author.name is None:
            missing.append("user.name")
        if author.email is None:
            missing.append("user.email")

        raise GitAuthError(
            f"Git author not configured. Missing: {', '.join(missing)}.\n"
            f"Configure with:\n"
            f"  git config --global user.name 'Your Name'\n"
            f"  git config --global user.email 'your.email@example.com'"
        )

    return author


def _get_git_config(key: str, path: Path | None = None) -> str | None:
    """Get a git config value.

    This checks all config levels (local, global, system) as git would
    when creating a commit. This ensures we get the same author info
    that git will use.

    Args:
        key: Git config key (e.g., "user.name", "user.email").
        path: Repository path. Defaults to current directory.

    Returns:
        Config value as string, or None if not set at any level.
    """
    cmd = ["git"]
    if path:
        cmd.extend(["-C", str(path)])
    cmd.extend(["config", "--get", key])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()
        return value if value else None
    except subprocess.CalledProcessError:
        # Config key not set (exit code 1)
        return None
    except FileNotFoundError:
        # git command not found
        return None
