"""Integration tests for nelson-prd with real git operations.

These tests use actual git commands in temporary repositories to validate
branch creation, switching, and other git operations work correctly.
Nelson subprocess calls are still mocked to avoid heavy integration overhead.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from nelson.git_utils import GitError
from nelson.prd_branch import (
    branch_exists,
    create_branch,
    generate_branch_name,
    switch_branch,
)

# Sample PRD content for testing
SAMPLE_PRD = """# Git Integration Test PRD

## High Priority
- [ ] PRD-001 Implement user authentication
- [ ] PRD-002 Create API endpoints

## Medium Priority
- [ ] PRD-003 Add logging system
"""


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Configure git identity (required for commits)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    # Create .gitignore to ignore .nelson directory
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".nelson/\n")

    # Create initial commit
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    return tmp_path


@pytest.fixture
def prd_file(git_repo: Path) -> Path:
    """Create PRD file in git repository."""
    prd_file = git_repo / "requirements.md"
    prd_file.write_text(SAMPLE_PRD)

    # Commit the PRD file to avoid uncommitted changes
    subprocess.run(
        ["git", "add", "requirements.md"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Add PRD file"],
        cwd=git_repo,
        capture_output=True,
        check=True,
    )

    return prd_file


@pytest.fixture
def prd_dir(git_repo: Path) -> Path:
    """Create .nelson/prd directory in git repository."""
    prd_dir = git_repo / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)
    return prd_dir


@pytest.fixture
def mock_nelson_success():
    """Create a mock for successful Nelson execution."""
    def _mock_run(*args, **kwargs):
        result = Mock()
        result.returncode = 0
        result.stdout = "Nelson execution completed successfully"
        result.stderr = ""
        return result
    return _mock_run


class TestGitBranchOperations:
    """Test real git branch operations."""

    def test_branch_creation_and_existence_check(self, git_repo: Path):
        """Test creating a branch and checking if it exists."""
        branch_name = "feature/PRD-001-test-branch"

        # Branch should not exist initially
        assert not branch_exists(branch_name, git_repo)

        # Create branch
        create_branch(branch_name, git_repo)

        # Branch should now exist
        assert branch_exists(branch_name, git_repo)

    def test_branch_creation_fails_if_exists(self, git_repo: Path):
        """Test that creating an existing branch fails without force."""
        branch_name = "feature/PRD-001-test-branch"

        # Create branch
        create_branch(branch_name, git_repo)

        # Trying to create again should fail
        with pytest.raises(ValueError, match="Branch already exists"):
            create_branch(branch_name, git_repo, force=False)

    def test_branch_creation_with_force_overwrites(self, git_repo: Path):
        """Test that force flag allows overwriting existing branch."""
        branch_name = "feature/PRD-001-test-branch"

        # Create branch
        create_branch(branch_name, git_repo)

        # Should succeed with force=True
        create_branch(branch_name, git_repo, force=True)
        assert branch_exists(branch_name, git_repo)

    def test_switch_branch(self, git_repo: Path):
        """Test switching between branches."""
        branch_name = "feature/PRD-001-test-branch"

        # Create and switch to new branch
        create_branch(branch_name, git_repo)
        switch_branch(branch_name, git_repo)

        # Verify we're on the new branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = result.stdout.strip()
        assert current_branch == branch_name

    def test_switch_branch_fails_with_uncommitted_changes(self, git_repo: Path):
        """Test that switching branches fails with uncommitted changes."""
        branch_name = "feature/PRD-001-test-branch"

        # Create branch
        create_branch(branch_name, git_repo)

        # Create uncommitted changes
        test_file = git_repo / "test.txt"
        test_file.write_text("uncommitted changes")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Switching should fail
        with pytest.raises(GitError, match="uncommitted changes"):
            switch_branch(branch_name, git_repo)

    def test_generate_branch_name_format(self):
        """Test branch name generation follows correct format."""
        branch_name = generate_branch_name("PRD-001", "Add user authentication")
        assert branch_name == "feature/PRD-001-add-user-authentication"

        # Test with special characters and truncation
        long_text = "Fix critical bug in payment system that affects checkout"
        branch_name = generate_branch_name("PRD-042", long_text)
        assert branch_name.startswith("feature/PRD-042-")
        assert len(branch_name) <= 60  # feature/ (8) + PRD-042- (8) + slug (40) = 56


class TestPRDOrchestratorWithRealGit:
    """Test PRD orchestrator with real git operations."""

    def test_ensure_branch_for_task_with_real_git(self, git_repo: Path):
        """Test that ensure_branch_for_task works with real git repo."""
        # Change to git repo directory so ensure_branch works
        import os

        from nelson.prd_branch import ensure_branch_for_task
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            # Create and switch to branch for task
            branch_name = ensure_branch_for_task("PRD-001", "Implement user authentication")

            # Verify branch was created and we switched to it
            assert branch_name == "feature/PRD-001-implement-user-authentication"
            assert branch_exists(branch_name, git_repo)

            # Verify we're on the branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()
            assert current_branch == branch_name
        finally:
            os.chdir(original_cwd)

    def test_multiple_branches_can_be_created(self, git_repo: Path):
        """Test creating multiple branches for different tasks."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            from nelson.prd_branch import ensure_branch_for_task

            # Create first branch
            branch1 = ensure_branch_for_task("PRD-001", "Implement user authentication")
            assert branch_exists(branch1, git_repo)

            # Switch back to master to create second branch
            switch_branch("master", git_repo)

            # Create second branch
            branch2 = ensure_branch_for_task("PRD-002", "Create API endpoints")
            assert branch_exists(branch2, git_repo)

            # Both branches should exist
            assert branch_exists(branch1, git_repo)
            assert branch_exists(branch2, git_repo)
            assert branch1 != branch2
        finally:
            os.chdir(original_cwd)

    def test_branch_switching_between_tasks(self, git_repo: Path):
        """Test switching between task branches."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            from nelson.prd_branch import ensure_branch_for_task

            # Create first branch
            branch1 = ensure_branch_for_task("PRD-001", "Implement user authentication")

            # Switch back to master
            switch_branch("master", git_repo)

            # Create and switch to second branch
            branch2 = ensure_branch_for_task("PRD-002", "Create API endpoints")

            # Verify we're on branch2
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == branch2

            # Switch back to branch1
            switch_branch(branch1, git_repo)

            # Verify we're on branch1
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == branch1
        finally:
            os.chdir(original_cwd)


class TestGitBranchAdditionalOperations:
    """Test additional git branch operations with real git."""

    def test_slugify_task_text_basic(self):
        """Test basic task text slugification."""
        from nelson.prd_branch import slugify_task_text

        # Basic conversion
        assert slugify_task_text("Add User Authentication") == "add-user-authentication"

        # With special characters
        assert slugify_task_text("Fix bug #123 (critical)") == "fix-bug-123-critical"

        # Multiple spaces
        assert slugify_task_text("Add   multiple    spaces") == "add-multiple-spaces"

        # Leading/trailing spaces and hyphens
        assert slugify_task_text("  -- Fix issue --  ") == "fix-issue"

    def test_slugify_task_text_truncation(self):
        """Test task text truncation to max length."""
        from nelson.prd_branch import slugify_task_text

        long_text = "This is a very long task description that exceeds the maximum length limit"
        slug = slugify_task_text(long_text, max_length=20)
        assert len(slug) <= 20
        assert slug == "this-is-a-very-long"

        # Ensure no trailing hyphens after truncation
        text_with_hyphen_boundary = "word-boundary-test-with-more-content"
        slug = slugify_task_text(text_with_hyphen_boundary, max_length=15)
        assert len(slug) <= 15
        assert not slug.endswith("-")

    def test_slugify_task_text_special_characters(self):
        """Test slugification handles various special characters."""
        from nelson.prd_branch import slugify_task_text

        # Parentheses, brackets, quotes
        assert slugify_task_text("Fix [bug] in \"API\" (v2.0)") == "fix-bug-in-api-v20"

        # Punctuation
        assert slugify_task_text("Update README.md, docs, etc.") == "update-readmemd-docs-etc"

        # Unicode and accents (removed)
        assert slugify_task_text("Add café feature") == "add-caf-feature"

    def test_create_and_switch_branch_new_branch(self, git_repo: Path):
        """Test create_and_switch_branch with a new branch."""
        from nelson.prd_branch import create_and_switch_branch

        branch_name = "feature/PRD-001-test-new-branch"

        # Should create and switch to new branch
        create_and_switch_branch(branch_name, git_repo)

        # Verify we're on the new branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == branch_name

    def test_create_and_switch_branch_existing_branch_no_force(self, git_repo: Path):
        """Test create_and_switch_branch with existing branch without force."""
        from nelson.prd_branch import create_and_switch_branch, create_branch

        branch_name = "feature/PRD-001-existing-branch"

        # Create branch first
        create_branch(branch_name, git_repo)

        # Switch back to master
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Should just switch to existing branch (not error)
        create_and_switch_branch(branch_name, git_repo, force=False)

        # Verify we're on the branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == branch_name

    def test_create_and_switch_branch_existing_branch_with_force(self, git_repo: Path):
        """Test create_and_switch_branch with force flag recreates branch."""
        from nelson.prd_branch import create_and_switch_branch

        branch_name = "feature/PRD-001-force-recreate"

        # Create branch and make a commit
        create_and_switch_branch(branch_name, git_repo)
        test_file = git_repo / "test.txt"
        test_file.write_text("test content")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test commit"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Get current commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        original_commit = result.stdout.strip()

        # Switch back to master
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Force recreate branch
        create_and_switch_branch(branch_name, git_repo, force=True)

        # Get new commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        new_commit = result.stdout.strip()

        # Should be different commit (branch was recreated from master)
        assert new_commit != original_commit

        # Verify we're on the branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == branch_name

    def test_delete_branch_success(self, git_repo: Path):
        """Test successful branch deletion."""
        from nelson.prd_branch import branch_exists, create_branch, delete_branch

        branch_name = "feature/PRD-001-to-delete"

        # Create branch
        create_branch(branch_name, git_repo)
        assert branch_exists(branch_name, git_repo)

        # Delete branch
        delete_branch(branch_name, git_repo)

        # Branch should no longer exist
        assert not branch_exists(branch_name, git_repo)

    def test_delete_branch_fails_on_current_branch(self, git_repo: Path):
        """Test that deleting current branch fails."""
        from nelson.prd_branch import create_and_switch_branch, delete_branch

        branch_name = "feature/PRD-001-current-branch"

        # Create and switch to branch
        create_and_switch_branch(branch_name, git_repo)

        # Should fail to delete current branch
        with pytest.raises(GitError, match="Cannot delete current branch"):
            delete_branch(branch_name, git_repo)

    def test_delete_branch_with_unmerged_commits(self, git_repo: Path):
        """Test deleting branch with unmerged commits requires force."""
        from nelson.prd_branch import branch_exists, create_and_switch_branch, delete_branch

        branch_name = "feature/PRD-001-unmerged"

        # Create branch and add commit
        create_and_switch_branch(branch_name, git_repo)
        test_file = git_repo / "unmerged.txt"
        test_file.write_text("unmerged content")
        subprocess.run(
            ["git", "add", "unmerged.txt"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "unmerged commit"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Switch back to master
        subprocess.run(
            ["git", "checkout", "master"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Non-force delete should fail
        with pytest.raises(GitError):
            delete_branch(branch_name, git_repo, force=False)

        # Branch should still exist
        assert branch_exists(branch_name, git_repo)

        # Force delete should succeed
        delete_branch(branch_name, git_repo, force=True)
        assert not branch_exists(branch_name, git_repo)

    def test_ensure_branch_for_task_existing_branch(self, git_repo: Path):
        """Test ensure_branch_for_task with existing branch just switches."""
        import os

        from nelson.prd_branch import create_branch, ensure_branch_for_task

        original_cwd = os.getcwd()
        try:
            os.chdir(git_repo)

            # Create branch manually first
            branch_name = "feature/PRD-001-existing-task"
            create_branch(branch_name, git_repo)

            # ensure_branch_for_task should just switch to it
            result_branch = ensure_branch_for_task("PRD-001", "Existing task")

            # Should return same branch name and we should be on it
            assert result_branch == branch_name
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_repo,
                capture_output=True,
                text=True,
                check=True,
            )
            assert result.stdout.strip() == branch_name
        finally:
            os.chdir(original_cwd)


class TestGitErrorHandling:
    """Test error handling for git operations."""

    def test_operations_fail_outside_git_repo(self, tmp_path: Path):
        """Test that git operations fail gracefully outside a git repo."""
        from nelson.prd_branch import (
            branch_exists,
            create_branch,
            ensure_branch_for_task,
            switch_branch,
        )

        # Create a non-git directory
        non_git_dir = tmp_path / "not-a-repo"
        non_git_dir.mkdir()

        # All operations should raise GitError
        with pytest.raises(GitError, match="Not a git repository"):
            branch_exists("test-branch", non_git_dir)

        with pytest.raises(GitError, match="Not a git repository"):
            create_branch("test-branch", non_git_dir)

        with pytest.raises(GitError, match="Not a git repository"):
            switch_branch("test-branch", non_git_dir)

        # Test with ensure_branch_for_task
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(non_git_dir)
            with pytest.raises(GitError, match="Not a git repository"):
                ensure_branch_for_task("PRD-001", "Test task")
        finally:
            os.chdir(original_cwd)

    def test_switch_to_nonexistent_branch_fails(self, git_repo: Path):
        """Test switching to a non-existent branch fails."""
        from nelson.prd_branch import switch_branch

        with pytest.raises(GitError, match="Failed to switch to branch"):
            switch_branch("nonexistent-branch", git_repo)

    def test_branch_name_generation_with_empty_text(self):
        """Test branch name generation handles edge cases."""
        from nelson.prd_branch import generate_branch_name

        # Empty text after slugification
        branch_name = generate_branch_name("PRD-001", "!@#$%^&*()")
        # Should still have feature/PRD-001 prefix even with no valid slug
        assert branch_name.startswith("feature/PRD-001")

        # Just spaces
        branch_name = generate_branch_name("PRD-002", "     ")
        assert branch_name.startswith("feature/PRD-002")
