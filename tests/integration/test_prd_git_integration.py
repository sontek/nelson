"""Integration tests for nelson-prd with real git operations.

These tests use actual git commands in temporary repositories to validate
branch creation, switching, and other git operations work correctly.
Nelson subprocess calls are still mocked to avoid heavy integration overhead.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nelson.git_utils import GitError
from nelson.prd_branch import (
    branch_exists,
    create_branch,
    generate_branch_name,
    switch_branch,
)
from nelson.prd_orchestrator import PRDOrchestrator


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
        from nelson.prd_branch import ensure_branch_for_task

        # Change to git repo directory so ensure_branch works
        import os
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
