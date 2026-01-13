"""Tests for git utilities module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nelson.git_utils import (
    GitError,
    GitStatus,
    get_commit_range,
    get_current_branch,
    get_current_commit,
    get_git_status,
    is_git_repo,
    unstage_files,
    unstage_ralph_files,
)


class TestIsGitRepo:
    """Tests for is_git_repo()."""

    def test_is_git_repo_in_repo(self, tmp_path: Path) -> None:
        """Test detecting when in a git repository."""
        # Initialize a real git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        assert is_git_repo(tmp_path) is True

    def test_is_git_repo_not_in_repo(self, tmp_path: Path) -> None:
        """Test detecting when not in a git repository."""
        assert is_git_repo(tmp_path) is False

    @patch("subprocess.run")
    def test_is_git_repo_git_not_found(self, mock_run: MagicMock) -> None:
        """Test when git command is not available."""
        mock_run.side_effect = FileNotFoundError()
        assert is_git_repo() is False


class TestGetCurrentBranch:
    """Tests for get_current_branch()."""

    def test_get_current_branch_success(self, tmp_path: Path) -> None:
        """Test getting current branch name."""
        # Initialize git repo and create a branch
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        # Should be on main or master branch
        branch = get_current_branch(tmp_path)
        assert branch in ("main", "master")

    def test_get_current_branch_not_in_repo(self, tmp_path: Path) -> None:
        """Test getting branch when not in a repo."""
        assert get_current_branch(tmp_path) is None

    @patch("subprocess.run")
    def test_get_current_branch_detached_head(self, mock_run: MagicMock) -> None:
        """Test detached HEAD state returns None."""
        mock_run.return_value = MagicMock(stdout="HEAD\n", returncode=0)
        assert get_current_branch() is None


class TestGetGitStatus:
    """Tests for get_git_status()."""

    def test_get_git_status_not_in_repo(self, tmp_path: Path) -> None:
        """Test status when not in a repository."""
        status = get_git_status(tmp_path)
        assert status.is_repo is False
        assert status.branch is None
        assert status.has_uncommitted_changes is False
        assert status.staged_files == []
        assert status.modified_files == []

    def test_get_git_status_clean_repo(self, tmp_path: Path) -> None:
        """Test status in clean repository."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        status = get_git_status(tmp_path)
        assert status.is_repo is True
        assert status.branch in ("main", "master")
        assert status.has_uncommitted_changes is False
        assert status.staged_files == []
        assert status.modified_files == []

    def test_get_git_status_with_changes(self, tmp_path: Path) -> None:
        """Test status with staged and modified files."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        # Make changes
        (tmp_path / "staged.txt").write_text("staged")
        subprocess.run(["git", "add", "staged.txt"], cwd=tmp_path, check=True, capture_output=True)

        (tmp_path / "test.txt").write_text("modified")

        (tmp_path / "untracked.txt").write_text("untracked")

        status = get_git_status(tmp_path)
        assert status.is_repo is True
        assert status.has_uncommitted_changes is True
        assert "staged.txt" in status.staged_files
        assert "test.txt" in status.modified_files


class TestGetCurrentCommit:
    """Tests for get_current_commit()."""

    def test_get_current_commit_success(self, tmp_path: Path) -> None:
        """Test getting current commit SHA."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        commit = get_current_commit(tmp_path)
        assert len(commit) == 40  # Full SHA
        assert commit.isalnum()

    def test_get_current_commit_not_in_repo(self, tmp_path: Path) -> None:
        """Test error when not in a repository."""
        with pytest.raises(GitError, match="Failed to get current commit"):
            get_current_commit(tmp_path)

    @patch("subprocess.run")
    def test_get_current_commit_git_not_found(self, mock_run: MagicMock) -> None:
        """Test error when git command is not available."""
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(GitError, match="git command not found"):
            get_current_commit()


class TestGetCommitRange:
    """Tests for get_commit_range()."""

    def test_get_commit_range_success(self, tmp_path: Path) -> None:
        """Test getting commit range."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create first commit
        (tmp_path / "test1.txt").write_text("test1")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "commit1"], cwd=tmp_path, check=True, capture_output=True
        )
        start_commit = get_current_commit(tmp_path)

        # Create second commit
        (tmp_path / "test2.txt").write_text("test2")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "commit2"], cwd=tmp_path, check=True, capture_output=True
        )

        # Create third commit
        (tmp_path / "test3.txt").write_text("test3")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "commit3"], cwd=tmp_path, check=True, capture_output=True
        )

        # Get commit range
        commits = get_commit_range(start_commit, tmp_path)
        assert len(commits) == 2  # commit2 and commit3

    def test_get_commit_range_empty(self, tmp_path: Path) -> None:
        """Test empty commit range when start is HEAD."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "commit1"], cwd=tmp_path, check=True, capture_output=True
        )
        current_commit = get_current_commit(tmp_path)

        # Get commit range from HEAD to HEAD
        commits = get_commit_range(current_commit, tmp_path)
        assert commits == []

    @patch("subprocess.run")
    def test_get_commit_range_git_not_found(self, mock_run: MagicMock) -> None:
        """Test error when git command is not available."""
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(GitError, match="git command not found"):
            get_commit_range("abc123")


class TestUnstageFiles:
    """Tests for unstage_files()."""

    def test_unstage_files_no_patterns(self, tmp_path: Path) -> None:
        """Test unstaging with no patterns returns 0."""
        count = unstage_files([], tmp_path)
        assert count == 0

    def test_unstage_files_success(self, tmp_path: Path) -> None:
        """Test unstaging files matching patterns."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        # Create and stage files
        nelson_dir = tmp_path / ".nelson"
        nelson_dir.mkdir()
        (nelson_dir / "state.json").write_text("{}")
        (tmp_path / "source.py").write_text("code")

        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

        # Unstage .nelson/ files
        count = unstage_files([".nelson/"], tmp_path)
        assert count == 1

        # Verify .nelson/state.json was unstaged but source.py is still staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        staged = result.stdout.strip().split("\n")
        assert ".nelson/state.json" not in staged
        assert "source.py" in staged

    def test_unstage_files_no_matches(self, tmp_path: Path) -> None:
        """Test unstaging when no files match patterns."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        # Stage a file
        (tmp_path / "source.py").write_text("code")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

        # Try to unstage .nelson/ files (none exist)
        count = unstage_files([".nelson/"], tmp_path)
        assert count == 0

    @patch("subprocess.run")
    def test_unstage_files_git_error(self, mock_run: MagicMock) -> None:
        """Test error handling when git command fails."""
        # First call succeeds (diff --cached), second call fails (reset)
        mock_run.side_effect = [
            MagicMock(stdout=".nelson/state.json\n", returncode=0),
            subprocess.CalledProcessError(1, "git", stderr="error"),
        ]
        with pytest.raises(GitError, match="Failed to unstage files"):
            unstage_files([".nelson/"])


class TestUnstageRalphFiles:
    """Tests for unstage_ralph_files()."""

    def test_unstage_ralph_files_success(self, tmp_path: Path) -> None:
        """Test unstaging .claude/ and .nelson/ files."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit
        (tmp_path / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True
        )

        # Create and stage Nelson files
        nelson_dir = tmp_path / ".nelson"
        nelson_dir.mkdir()
        (nelson_dir / "state.json").write_text("{}")

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "config.json").write_text("{}")

        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)

        # Unstage Nelson files
        count = unstage_ralph_files(tmp_path)
        assert count == 2

        # Verify files were unstaged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )
        staged = result.stdout.strip()
        assert ".nelson/state.json" not in staged
        assert ".claude/config.json" not in staged


class TestGitStatus:
    """Tests for GitStatus dataclass."""

    def test_git_status_immutable(self) -> None:
        """Test that GitStatus is frozen/immutable."""
        status = GitStatus(
            is_repo=True,
            branch="main",
            has_uncommitted_changes=False,
            staged_files=[],
            modified_files=[],
        )
        with pytest.raises(AttributeError):
            status.branch = "develop"  # type: ignore

    def test_git_status_equality(self) -> None:
        """Test GitStatus equality comparison."""
        status1 = GitStatus(
            is_repo=True,
            branch="main",
            has_uncommitted_changes=False,
            staged_files=["test.py"],
            modified_files=[],
        )
        status2 = GitStatus(
            is_repo=True,
            branch="main",
            has_uncommitted_changes=False,
            staged_files=["test.py"],
            modified_files=[],
        )
        assert status1 == status2
