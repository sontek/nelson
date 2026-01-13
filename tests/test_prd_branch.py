"""Tests for prd_branch module."""


from nelson.prd_branch import (
    generate_branch_name,
    slugify_task_text,
)


def test_slugify_basic():
    """Test basic slugification."""
    assert slugify_task_text("Add User Authentication") == "add-user-authentication"
    assert slugify_task_text("Fix Bug in API") == "fix-bug-in-api"


def test_slugify_special_characters():
    """Test slugification removes special characters."""
    assert slugify_task_text("Add feature (issue #123)") == "add-feature-issue-123"
    assert slugify_task_text("Update API @ endpoint") == "update-api-endpoint"
    assert slugify_task_text("Fix $$$") == "fix"


def test_slugify_multiple_spaces():
    """Test slugification handles multiple spaces."""
    assert slugify_task_text("Add   multiple    spaces") == "add-multiple-spaces"
    assert slugify_task_text("  Leading and trailing  ") == "leading-and-trailing"


def test_slugify_max_length():
    """Test slugification respects max length."""
    long_text = "This is a very long task description that should be truncated"
    slug = slugify_task_text(long_text, max_length=20)

    assert len(slug) <= 20
    assert not slug.endswith("-")  # Should not end with hyphen


def test_slugify_empty_after_filtering():
    """Test slugification handles text that becomes empty."""
    assert slugify_task_text("!!!") == ""
    assert slugify_task_text("@@@") == ""


def test_generate_branch_name():
    """Test branch name generation."""
    branch = generate_branch_name("PRD-001", "Add user authentication")

    assert branch == "feature/PRD-001-add-user-authentication"


def test_generate_branch_name_with_special_chars():
    """Test branch name with special characters."""
    branch = generate_branch_name("PRD-042", "Fix bug (issue #123)")

    assert branch == "feature/PRD-042-fix-bug-issue-123"


def test_generate_branch_name_long_description():
    """Test branch name with long description gets truncated."""
    long_desc = "This is a very long task description that will be truncated to fit"
    branch = generate_branch_name("PRD-001", long_desc)

    assert branch.startswith("feature/PRD-001-")
    # Should be reasonable length (not excessively long)
    assert len(branch) < 100


def test_slugify_unicode():
    """Test slugification handles unicode characters."""
    # Unicode should be removed
    assert slugify_task_text("Add café feature") == "add-caf-feature"


def test_slugify_numbers():
    """Test slugification preserves numbers."""
    assert slugify_task_text("Update API v2") == "update-api-v2"
    assert slugify_task_text("Add Python 3.12 support") == "add-python-312-support"


def test_slugify_hyphens():
    """Test slugification handles existing hyphens."""
    assert slugify_task_text("Add well-known endpoint") == "add-well-known-endpoint"
    assert slugify_task_text("Fix pre-commit hook") == "fix-pre-commit-hook"


def test_slugify_consecutive_hyphens():
    """Test slugification collapses consecutive hyphens."""
    assert slugify_task_text("Add -- multiple --- hyphens") == "add-multiple-hyphens"


def test_generate_branch_name_preserves_task_id():
    """Test that task ID is preserved in branch name."""
    branch1 = generate_branch_name("PRD-001", "Task description")
    branch2 = generate_branch_name("PRD-999", "Task description")

    assert "PRD-001" in branch1
    assert "PRD-999" in branch2


def test_generate_branch_name_format():
    """Test branch name follows feature/ format."""
    branch = generate_branch_name("PRD-001", "Test task")

    assert branch.startswith("feature/")
    assert branch.count("/") == 1  # Only one slash


def test_slugify_edge_cases():
    """Test slugification edge cases."""
    # Only special characters
    assert slugify_task_text("!@#$%^&*()") == ""

    # Single character
    assert slugify_task_text("A") == "a"

    # Already slugified
    assert slugify_task_text("already-slugified") == "already-slugified"


def test_slugify_preserves_readability():
    """Test that slugification preserves readability."""
    result = slugify_task_text("Add User Authentication System")

    # Should be readable
    assert "user" in result
    assert "authentication" in result
    assert "system" in result

    # Should be hyphen-separated
    assert "-" in result


def test_generate_branch_name_consistency():
    """Test that same inputs produce same branch name."""
    branch1 = generate_branch_name("PRD-001", "Add authentication")
    branch2 = generate_branch_name("PRD-001", "Add authentication")

    assert branch1 == branch2


def test_slugify_truncation_doesnt_break_words_badly():
    """Test that truncation doesn't leave trailing hyphens."""
    long_text = "Add very-long-hyphenated-task-name-here"
    slug = slugify_task_text(long_text, max_length=25)

    # Should not end with hyphen
    assert not slug.endswith("-")


# Note: Tests for actual git operations (branch_exists, create_branch, etc.)
# would require a git repository setup and are better suited for integration tests.
# The above tests cover the pure Python logic that doesn't require git.
