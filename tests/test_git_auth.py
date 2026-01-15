"""Tests for git author validation module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nelson.git_auth import GitAuthError, GitAuthor, get_git_author, validate_git_author


class TestGetGitAuthor:
    """Tests for get_git_author()."""

    def test_get_git_author_configured(self, tmp_path: Path) -> None:
        """Test getting author info when properly configured."""
        # Initialize git repo with user config
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        author = get_git_author(tmp_path)
        assert author.name == "Test User"
        assert author.email == "test@example.com"
        assert author.is_configured is True

    @patch("subprocess.run")
    def test_get_git_author_no_name(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test when user.name is not configured."""
        # Mock git config responses: name returns error (not set), email returns value
        def side_effect(*args: tuple, **kwargs: dict) -> MagicMock:  # type: ignore
            cmd = args[0]
            if "user.name" in cmd:
                # Simulate config not set
                raise subprocess.CalledProcessError(1, cmd)
            elif "user.email" in cmd:
                return MagicMock(stdout="test@example.com\n", returncode=0)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        author = get_git_author(tmp_path)
        assert author.name is None
        assert author.email == "test@example.com"
        assert author.is_configured is False

    @patch("subprocess.run")
    def test_get_git_author_no_email(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test when user.email is not configured."""
        # Mock git config responses: name returns value, email returns error (not set)
        def side_effect(*args: tuple, **kwargs: dict) -> MagicMock:  # type: ignore
            cmd = args[0]
            if "user.name" in cmd:
                return MagicMock(stdout="Test User\n", returncode=0)
            elif "user.email" in cmd:
                # Simulate config not set
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        author = get_git_author(tmp_path)
        assert author.name == "Test User"
        assert author.email is None
        assert author.is_configured is False

    @patch("subprocess.run")
    def test_get_git_author_not_configured(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test when neither name nor email is configured."""
        # Mock git config to return errors (not set) for both
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "config"])

        author = get_git_author(tmp_path)
        assert author.name is None
        assert author.email is None
        assert author.is_configured is False

    @patch("subprocess.run")
    def test_get_git_author_not_in_repo(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test when not in a git repository."""
        # Mock git config to return errors (not in repo or not set)
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "config"])

        author = get_git_author(tmp_path)
        assert author.name is None
        assert author.email is None
        assert author.is_configured is False

    @patch("subprocess.run")
    def test_get_git_author_git_not_found(self, mock_run: MagicMock) -> None:
        """Test when git command is not available."""
        mock_run.side_effect = FileNotFoundError()
        author = get_git_author()
        assert author.name is None
        assert author.email is None
        assert author.is_configured is False


class TestValidateGitAuthor:
    """Tests for validate_git_author()."""

    def test_validate_git_author_success(self, tmp_path: Path) -> None:
        """Test validation passes when properly configured."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        author = validate_git_author(tmp_path)
        assert author.name == "Test User"
        assert author.email == "test@example.com"
        assert author.is_configured is True

    @patch("subprocess.run")
    def test_validate_git_author_missing_name(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validation fails when user.name is missing."""
        # Mock git config responses: name not set, email set
        def side_effect(*args: tuple, **kwargs: dict) -> MagicMock:  # type: ignore
            cmd = args[0]
            if "user.name" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            elif "user.email" in cmd:
                return MagicMock(stdout="test@example.com\n", returncode=0)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        with pytest.raises(GitAuthError) as exc_info:
            validate_git_author(tmp_path)
        assert "user.name" in str(exc_info.value)
        assert "git config --global" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_git_author_missing_email(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validation fails when user.email is missing."""
        # Mock git config responses: name set, email not set
        def side_effect(*args: tuple, **kwargs: dict) -> MagicMock:  # type: ignore
            cmd = args[0]
            if "user.name" in cmd:
                return MagicMock(stdout="Test User\n", returncode=0)
            elif "user.email" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        with pytest.raises(GitAuthError) as exc_info:
            validate_git_author(tmp_path)
        assert "user.email" in str(exc_info.value)
        assert "git config --global" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_git_author_missing_both(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validation fails when both name and email are missing."""
        # Mock git config to return errors (not set) for both
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git", "config"])

        with pytest.raises(GitAuthError) as exc_info:
            validate_git_author(tmp_path)
        error_msg = str(exc_info.value)
        assert "user.name" in error_msg
        assert "user.email" in error_msg
        assert "git config --global" in error_msg


class TestGitAuthor:
    """Tests for GitAuthor dataclass."""

    def test_git_author_immutable(self) -> None:
        """Test that GitAuthor is immutable (frozen)."""
        author = GitAuthor(name="Test User", email="test@example.com", is_configured=True)
        with pytest.raises(AttributeError):
            author.name = "New Name"  # type: ignore

    def test_git_author_equality(self) -> None:
        """Test GitAuthor equality comparison."""
        author1 = GitAuthor(name="Test User", email="test@example.com", is_configured=True)
        author2 = GitAuthor(name="Test User", email="test@example.com", is_configured=True)
        assert author1 == author2

    def test_git_author_none_values(self) -> None:
        """Test GitAuthor with None values."""
        author = GitAuthor(name=None, email=None, is_configured=False)
        assert author.name is None
        assert author.email is None
        assert author.is_configured is False
