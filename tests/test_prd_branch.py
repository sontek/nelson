"""Tests for prd_branch module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nelson.git_utils import GitError
from nelson.prd_branch import (
    branch_exists,
    create_and_switch_branch,
    create_branch,
    delete_branch,
    ensure_branch_for_task,
    generate_branch_name,
    slugify_task_text,
    switch_branch,
)


def test_slugify_basic() -> None:
    """Test basic slugification."""
    assert slugify_task_text("Add User Authentication") == "add-user-authentication"
    assert slugify_task_text("Fix Bug in API") == "fix-bug-in-api"


def test_slugify_special_characters() -> None:
    """Test slugification removes special characters."""
    assert slugify_task_text("Add feature (issue #123)") == "add-feature-issue-123"
    assert slugify_task_text("Update API @ endpoint") == "update-api-endpoint"
    assert slugify_task_text("Fix $$$") == "fix"


def test_slugify_multiple_spaces() -> None:
    """Test slugification handles multiple spaces."""
    assert slugify_task_text("Add   multiple    spaces") == "add-multiple-spaces"
    assert slugify_task_text("  Leading and trailing  ") == "leading-and-trailing"


def test_slugify_max_length() -> None:
    """Test slugification respects max length."""
    long_text = "This is a very long task description that should be truncated"
    slug = slugify_task_text(long_text, max_length=20)

    assert len(slug) <= 20
    assert not slug.endswith("-")  # Should not end with hyphen


def test_slugify_empty_after_filtering() -> None:
    """Test slugification handles text that becomes empty."""
    assert slugify_task_text("!!!") == ""
    assert slugify_task_text("@@@") == ""


def test_generate_branch_name() -> None:
    """Test branch name generation."""
    branch = generate_branch_name("PRD-001", "Add user authentication")

    assert branch == "feature/PRD-001-add-user-authentication"


def test_generate_branch_name_with_special_chars() -> None:
    """Test branch name with special characters."""
    branch = generate_branch_name("PRD-042", "Fix bug (issue #123)")

    assert branch == "feature/PRD-042-fix-bug-issue-123"


def test_generate_branch_name_long_description() -> None:
    """Test branch name with long description gets truncated."""
    long_desc = "This is a very long task description that will be truncated to fit"
    branch = generate_branch_name("PRD-001", long_desc)

    assert branch.startswith("feature/PRD-001-")
    # Should be reasonable length (not excessively long)
    assert len(branch) < 100


def test_slugify_unicode() -> None:
    """Test slugification handles unicode characters."""
    # Unicode should be removed
    assert slugify_task_text("Add café feature") == "add-caf-feature"


def test_slugify_numbers() -> None:
    """Test slugification preserves numbers."""
    assert slugify_task_text("Update API v2") == "update-api-v2"
    assert slugify_task_text("Add Python 3.12 support") == "add-python-312-support"


def test_slugify_hyphens() -> None:
    """Test slugification handles existing hyphens."""
    assert slugify_task_text("Add well-known endpoint") == "add-well-known-endpoint"
    assert slugify_task_text("Fix pre-commit hook") == "fix-pre-commit-hook"


def test_slugify_consecutive_hyphens() -> None:
    """Test slugification collapses consecutive hyphens."""
    assert slugify_task_text("Add -- multiple --- hyphens") == "add-multiple-hyphens"


def test_generate_branch_name_preserves_task_id() -> None:
    """Test that task ID is preserved in branch name."""
    branch1 = generate_branch_name("PRD-001", "Task description")
    branch2 = generate_branch_name("PRD-999", "Task description")

    assert "PRD-001" in branch1
    assert "PRD-999" in branch2


def test_generate_branch_name_format() -> None:
    """Test branch name follows feature/ format."""
    branch = generate_branch_name("PRD-001", "Test task")

    assert branch.startswith("feature/")
    assert branch.count("/") == 1  # Only one slash


def test_slugify_edge_cases() -> None:
    """Test slugification edge cases."""
    # Only special characters
    assert slugify_task_text("!@#$%^&*()") == ""

    # Single character
    assert slugify_task_text("A") == "a"

    # Already slugified
    assert slugify_task_text("already-slugified") == "already-slugified"


def test_slugify_preserves_readability() -> None:
    """Test that slugification preserves readability."""
    result = slugify_task_text("Add User Authentication System")

    # Should be readable
    assert "user" in result
    assert "authentication" in result
    assert "system" in result

    # Should be hyphen-separated
    assert "-" in result


def test_generate_branch_name_consistency() -> None:
    """Test that same inputs produce same branch name."""
    branch1 = generate_branch_name("PRD-001", "Add authentication")
    branch2 = generate_branch_name("PRD-001", "Add authentication")

    assert branch1 == branch2


def test_slugify_truncation_doesnt_break_words_badly() -> None:
    """Test that truncation doesn't leave trailing hyphens."""
    long_text = "Add very-long-hyphenated-task-name-here"
    slug = slugify_task_text(long_text, max_length=25)

    # Should not end with hyphen
    assert not slug.endswith("-")


# Git Repository Validation Tests


@patch("nelson.prd_branch.is_git_repo")
def test_branch_exists_requires_git_repo(mock_is_git_repo) -> None:
    """Test that branch_exists validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        branch_exists("feature/test", Path("/tmp/not-a-repo"))

    assert "Not a git repository" in str(excinfo.value)
    assert "nelson-prd requires a git repository" in str(excinfo.value)
    assert "git init" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(Path("/tmp/not-a-repo"))


@patch("nelson.prd_branch.is_git_repo")
def test_create_branch_requires_git_repo(mock_is_git_repo) -> None:
    """Test that create_branch validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        create_branch("feature/test")

    assert "Not a git repository" in str(excinfo.value)
    assert "current directory" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(None)


@patch("nelson.prd_branch.is_git_repo")
def test_switch_branch_requires_git_repo(mock_is_git_repo) -> None:
    """Test that switch_branch validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        switch_branch("feature/test")

    assert "Not a git repository" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(None)


@patch("nelson.prd_branch.is_git_repo")
def test_create_and_switch_branch_requires_git_repo(mock_is_git_repo) -> None:
    """Test that create_and_switch_branch validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        create_and_switch_branch("feature/test", Path("/tmp/not-a-repo"))

    assert "Not a git repository" in str(excinfo.value)
    assert "/tmp/not-a-repo" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(Path("/tmp/not-a-repo"))


@patch("nelson.prd_branch.is_git_repo")
def test_delete_branch_requires_git_repo(mock_is_git_repo) -> None:
    """Test that delete_branch validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        delete_branch("feature/test")

    assert "Not a git repository" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(None)


@patch("nelson.prd_branch.is_git_repo")
def test_ensure_branch_for_task_requires_git_repo(mock_is_git_repo) -> None:
    """Test that ensure_branch_for_task validates git repository."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        ensure_branch_for_task("PRD-001", "Add authentication")

    assert "Not a git repository" in str(excinfo.value)
    mock_is_git_repo.assert_called_once_with(None)


@patch("nelson.prd_branch.is_git_repo")
def test_git_repo_validation_with_valid_repo(mock_is_git_repo) -> None:
    """Test that functions proceed when in a valid git repository."""
    mock_is_git_repo.return_value = True

    # branch_exists should proceed to git command (which will fail without real git)
    # We're just testing that the validation passes
    with patch("nelson.prd_branch.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1  # Branch doesn't exist
        result = branch_exists("test-branch")
        assert result is False
        mock_is_git_repo.assert_called_with(None)


@patch("nelson.prd_branch.is_git_repo")
def test_git_repo_validation_error_message_for_path(mock_is_git_repo) -> None:
    """Test error message includes path when provided."""
    mock_is_git_repo.return_value = False
    test_path = Path("/tmp/my-project")

    with pytest.raises(GitError) as excinfo:
        branch_exists("test", test_path)

    error_msg = str(excinfo.value)
    assert "/tmp/my-project" in error_msg
    assert "Not a git repository" in error_msg


@patch("nelson.prd_branch.is_git_repo")
def test_git_repo_validation_error_message_for_current_dir(mock_is_git_repo) -> None:
    """Test error message mentions current directory when no path provided."""
    mock_is_git_repo.return_value = False

    with pytest.raises(GitError) as excinfo:
        branch_exists("test", None)

    error_msg = str(excinfo.value)
    assert "current directory" in error_msg
    assert "Not a git repository" in error_msg


# Note: Full integration tests with real git operations are in
# tests/integration/test_prd_git_integration.py
