"""Tests for commit summary generation."""

import subprocess
from pathlib import Path

import pytest

from nelson.commit_summary import (
    CommitSummary,
    display_commit_summary,
    generate_commit_summary,
    get_commit_messages,
)
from nelson.git_utils import GitError


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (repo / "file1.txt").write_text("content1")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True
    )

    return repo


class TestCommitSummary:
    """Tests for CommitSummary dataclass."""

    def test_commit_summary_creation(self):
        """Test creating a CommitSummary object."""
        summary = CommitSummary(
            starting_commit="abc123",
            current_commit="def456",
            commit_count=5,
            commit_messages=["commit 1", "commit 2"],
        )
        assert summary.starting_commit == "abc123"
        assert summary.current_commit == "def456"
        assert summary.commit_count == 5
        assert len(summary.commit_messages) == 2

    def test_has_commits_property(self):
        """Test has_commits property."""
        summary_with_commits = CommitSummary(
            starting_commit="abc123",
            current_commit="def456",
            commit_count=3,
            commit_messages=["msg1", "msg2", "msg3"],
        )
        assert summary_with_commits.has_commits is True

        summary_without_commits = CommitSummary(
            starting_commit="abc123",
            current_commit="abc123",
            commit_count=0,
            commit_messages=[],
        )
        assert summary_without_commits.has_commits is False

    def test_immutability(self):
        """Test that CommitSummary is immutable."""
        summary = CommitSummary(
            starting_commit="abc123",
            current_commit="def456",
            commit_count=1,
            commit_messages=["msg"],
        )
        with pytest.raises(AttributeError):
            summary.commit_count = 5  # type: ignore[misc]


class TestGetCommitMessages:
    """Tests for get_commit_messages function."""

    def test_get_commit_messages_with_commits(self, temp_git_repo: Path):
        """Test getting commit messages when commits exist."""
        # Get starting commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        start_commit = result.stdout.strip()

        # Create a few more commits
        for i in range(2, 4):
            (temp_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(
                ["git", "add", f"file{i}.txt"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )

        messages = get_commit_messages(start_commit, path=temp_git_repo)
        assert len(messages) == 2
        assert "Commit 3" in messages[0]
        assert "Commit 2" in messages[1]

    def test_get_commit_messages_no_commits(self, temp_git_repo: Path):
        """Test getting commit messages when no new commits exist."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        current_commit = result.stdout.strip()

        messages = get_commit_messages(current_commit, path=temp_git_repo)
        assert messages == []

    def test_get_commit_messages_with_end_commit(self, temp_git_repo: Path):
        """Test getting commit messages with explicit end commit."""
        # Get starting commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        start_commit = result.stdout.strip()

        # Create commits
        for i in range(2, 4):
            (temp_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(
                ["git", "add", f"file{i}.txt"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )

        # Get current commit as end_commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        end_commit = result.stdout.strip()

        messages = get_commit_messages(start_commit, end_commit, temp_git_repo)
        assert len(messages) == 2

    def test_get_commit_messages_git_error(self):
        """Test error handling when git command fails."""
        with pytest.raises(GitError, match="Failed to get commit messages"):
            get_commit_messages("invalid_commit_sha", path=Path("/nonexistent"))


class TestGenerateCommitSummary:
    """Tests for generate_commit_summary function."""

    def test_generate_summary_with_commits(self, temp_git_repo: Path):
        """Test generating summary when commits were made."""
        # Get starting commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        starting_commit = result.stdout.strip()

        # Create commits
        for i in range(2, 5):
            (temp_git_repo / f"file{i}.txt").write_text(f"content{i}")
            subprocess.run(
                ["git", "add", f"file{i}.txt"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Add file {i}"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )

        summary = generate_commit_summary(starting_commit, temp_git_repo)
        assert summary is not None
        assert summary.starting_commit == starting_commit
        assert summary.commit_count == 3
        assert len(summary.commit_messages) == 3
        assert summary.has_commits is True

    def test_generate_summary_no_commits(self, temp_git_repo: Path):
        """Test generating summary when no commits were made."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        current_commit = result.stdout.strip()

        summary = generate_commit_summary(current_commit, temp_git_repo)
        assert summary is not None
        assert summary.commit_count == 0
        assert summary.commit_messages == []
        assert summary.has_commits is False

    def test_generate_summary_no_starting_commit(self, temp_git_repo: Path):
        """Test generating summary with empty starting commit."""
        summary = generate_commit_summary("", temp_git_repo)
        assert summary is None

    def test_generate_summary_not_in_repo(self, tmp_path: Path):
        """Test generating summary when not in a git repo."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()

        summary = generate_commit_summary("abc123", non_repo)
        assert summary is None

    def test_generate_summary_git_error(self, temp_git_repo: Path):
        """Test handling git errors during summary generation."""
        # Use invalid commit SHA
        summary = generate_commit_summary("invalid_sha", temp_git_repo)
        # Should return None on GitError
        assert summary is None


class TestDisplayCommitSummary:
    """Tests for display_commit_summary function."""

    def test_display_none_summary(self, capsys):
        """Test displaying None summary does nothing."""
        display_commit_summary(None)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_display_no_commits(self, capsys):
        """Test displaying summary with no commits."""
        summary = CommitSummary(
            starting_commit="abc123",
            current_commit="abc123",
            commit_count=0,
            commit_messages=[],
        )
        display_commit_summary(summary)
        captured = capsys.readouterr()
        assert "No commits made during this Nelson session" in captured.out

    def test_display_with_commits(self, capsys):
        """Test displaying summary with commits."""
        summary = CommitSummary(
            starting_commit="abc123",
            current_commit="def456",
            commit_count=2,
            commit_messages=["abc1234 Fix bug", "def5678 Add feature"],
        )
        display_commit_summary(summary)
        captured = capsys.readouterr()

        # Check for header
        assert "Commits made during this Nelson session" in captured.out
        assert "━" in captured.out

        # Check for commit range
        assert "Commit range: abc123..def456" in captured.out

        # Check for commit messages
        assert "abc1234 Fix bug" in captured.out
        assert "def5678 Add feature" in captured.out

        # Check for commit count
        assert "Total commits: 2" in captured.out

    def test_display_with_single_commit(self, capsys):
        """Test displaying summary with single commit."""
        summary = CommitSummary(
            starting_commit="abc123",
            current_commit="def456",
            commit_count=1,
            commit_messages=["def456 Initial commit"],
        )
        display_commit_summary(summary)
        captured = capsys.readouterr()

        assert "Total commits: 1" in captured.out
        assert "def456 Initial commit" in captured.out
