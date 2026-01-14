"""Tests for prd_parser module."""

from pathlib import Path

import pytest

from nelson.prd_parser import PRDParser, PRDTaskStatus, parse_prd_file

# Sample PRD content
VALID_PRD = """# My PRD

## High Priority
- [ ] PRD-001 Add user authentication
- [~] PRD-002 Create user profile management
- [x] PRD-003 Add payment integration

## Medium Priority
- [!] PRD-004 Add email notifications (blocked: waiting for API keys)
- [ ] PRD-005 Implement search functionality

## Low Priority
- [ ] PRD-006 Dark mode toggle
"""

DUPLICATE_IDS_PRD = """## High Priority
- [ ] PRD-001 Task one
- [ ] PRD-001 Task two (duplicate!)
"""

INVALID_FORMAT_PRD = """## High Priority
- [ ] PRD-1 Invalid format (not 3 digits)
- [ ] PRD-ABC Invalid format (not numeric)
"""

MISSING_IDS_PRD = """## High Priority
- [ ] Task without ID
- [ ] PRD-001 Task with ID
"""

NO_PRIORITY_PRD = """- [ ] PRD-001 Task outside priority section"""


def test_parse_valid_prd(tmp_path: Path):
    """Test parsing a valid PRD file."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    tasks = parser.parse()

    assert len(tasks) == 6

    # Check first task
    assert tasks[0].task_id == "PRD-001"
    assert tasks[0].task_text == "Add user authentication"
    assert tasks[0].status == PRDTaskStatus.PENDING
    assert tasks[0].priority == "high"

    # Check in-progress task
    assert tasks[1].task_id == "PRD-002"
    assert tasks[1].status == PRDTaskStatus.IN_PROGRESS

    # Check completed task
    assert tasks[2].task_id == "PRD-003"
    assert tasks[2].status == PRDTaskStatus.COMPLETED

    # Check blocked task with reason
    assert tasks[3].task_id == "PRD-004"
    assert tasks[3].status == PRDTaskStatus.BLOCKED
    assert tasks[3].blocking_reason == "waiting for API keys"
    assert tasks[3].task_text == "Add email notifications"  # reason removed from text


def test_parse_duplicate_ids(tmp_path: Path):
    """Test that duplicate IDs raise ValueError."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(DUPLICATE_IDS_PRD)

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError, match="Duplicate task ID"):
        parser.parse()


def test_parse_invalid_format(tmp_path: Path):
    """Test that invalid ID format raises ValueError."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(INVALID_FORMAT_PRD)

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError, match="Invalid task ID format"):
        parser.parse()


def test_parse_no_priority_section(tmp_path: Path):
    """Test that tasks outside priority sections raise ValueError."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(NO_PRIORITY_PRD)

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError, match="outside priority section"):
        parser.parse()


def test_parse_nonexistent_file():
    """Test that missing file raises FileNotFoundError."""
    parser = PRDParser(Path("/nonexistent/file.md"))

    with pytest.raises(FileNotFoundError):
        parser.parse()


def test_get_tasks_by_priority(tmp_path: Path):
    """Test filtering tasks by priority."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    high_tasks = parser.get_tasks_by_priority("high")
    assert len(high_tasks) == 3
    assert all(t.priority == "high" for t in high_tasks)

    medium_tasks = parser.get_tasks_by_priority("medium")
    assert len(medium_tasks) == 2

    low_tasks = parser.get_tasks_by_priority("low")
    assert len(low_tasks) == 1


def test_get_tasks_by_status(tmp_path: Path):
    """Test filtering tasks by status."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    pending = parser.get_tasks_by_status(PRDTaskStatus.PENDING)
    assert len(pending) == 3

    in_progress = parser.get_tasks_by_status(PRDTaskStatus.IN_PROGRESS)
    assert len(in_progress) == 1

    completed = parser.get_tasks_by_status(PRDTaskStatus.COMPLETED)
    assert len(completed) == 1

    blocked = parser.get_tasks_by_status(PRDTaskStatus.BLOCKED)
    assert len(blocked) == 1


def test_get_task_by_id(tmp_path: Path):
    """Test getting task by ID."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    task = parser.get_task_by_id("PRD-003")
    assert task is not None
    assert task.task_id == "PRD-003"
    assert task.task_text == "Add payment integration"

    nonexistent = parser.get_task_by_id("PRD-999")
    assert nonexistent is None


def test_update_task_status(tmp_path: Path):
    """Test updating task status in PRD file."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    # Update status from pending to in-progress
    parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)

    # Re-read file to verify change
    content = prd_file.read_text()
    assert "[~] PRD-001 Add user authentication" in content


def test_update_task_status_to_blocked_with_reason(tmp_path: Path):
    """Test updating task to blocked with reason."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    # Block task with reason
    parser.update_task_status(
        "PRD-001", PRDTaskStatus.BLOCKED, "Need database schema approved"
    )

    # Re-read file
    content = prd_file.read_text()
    assert "[!] PRD-001 Add user authentication (blocked: Need database schema approved)" in content


def test_update_task_status_from_blocked_removes_reason(tmp_path: Path):
    """Test that unblocking removes blocking reason."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    # Update blocked task to pending (should remove reason)
    parser.update_task_status("PRD-004", PRDTaskStatus.PENDING)

    # Re-read file
    content = prd_file.read_text()
    assert "- [ ] PRD-004 Add email notifications\n" in content
    assert "blocked:" not in content.split("PRD-004")[1].split("\n")[0]


def test_update_task_status_nonexistent_task(tmp_path: Path):
    """Test that updating nonexistent task raises ValueError."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    with pytest.raises(ValueError, match="Task not found"):
        parser.update_task_status("PRD-999", PRDTaskStatus.COMPLETED)


def test_validate_all_tasks_valid(tmp_path: Path):
    """Test validation passes for valid PRD."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    parser.parse()

    issues = parser.validate_all_tasks()
    assert len(issues) == 0


def test_validate_all_tasks_missing_ids(tmp_path: Path):
    """Test validation detects tasks without IDs."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(MISSING_IDS_PRD)

    parser = PRDParser(prd_file)
    # This will fail during parse, but validate_all_tasks can detect it

    issues = parser.validate_all_tasks()
    assert len(issues) > 0
    assert any("missing explicit ID" in issue for issue in issues)


def test_parse_prd_file_convenience_function(tmp_path: Path):
    """Test convenience function for parsing."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    tasks = parse_prd_file(prd_file)

    assert len(tasks) == 6
    assert tasks[0].task_id == "PRD-001"


def test_task_id_validation():
    """Test task ID format validation."""
    parser = PRDParser(Path("dummy.md"))

    # Valid formats
    assert parser._is_valid_task_id("PRD-001")
    assert parser._is_valid_task_id("PRD-999")
    assert parser._is_valid_task_id("PRD-042")

    # Invalid formats
    assert not parser._is_valid_task_id("PRD-1")  # Too few digits
    assert not parser._is_valid_task_id("PRD-0001")  # Too many digits
    assert not parser._is_valid_task_id("PRD-ABC")  # Not numeric
    assert not parser._is_valid_task_id("PR-001")  # Wrong prefix
    assert not parser._is_valid_task_id("prd-001")  # Wrong case


def test_blocking_reason_extraction(tmp_path: Path):
    """Test extraction of blocking reasons from task text."""
    content = """## High Priority
- [!] PRD-001 Task name (blocked: very long reason with special chars @#$)
- [!] PRD-002 Another task (Blocked: mixed case reason)
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(content)

    parser = PRDParser(prd_file)
    tasks = parser.parse()

    assert tasks[0].blocking_reason == "very long reason with special chars @#$"
    assert tasks[0].task_text == "Task name"

    assert tasks[1].blocking_reason == "mixed case reason"
    assert tasks[1].task_text == "Another task"


def test_priority_case_insensitive(tmp_path: Path):
    """Test that priority headers are case-insensitive."""
    content = """## high priority
- [ ] PRD-001 Task 1

## MEDIUM PRIORITY
- [ ] PRD-002 Task 2

## Low Priority
- [ ] PRD-003 Task 3
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(content)

    parser = PRDParser(prd_file)
    tasks = parser.parse()

    assert len(tasks) == 3
    assert tasks[0].priority == "high"
    assert tasks[1].priority == "medium"
    assert tasks[2].priority == "low"


def test_line_number_tracking(tmp_path: Path):
    """Test that line numbers are tracked correctly."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    parser = PRDParser(prd_file)
    tasks = parser.parse()

    # Line numbers should be 1-indexed
    assert all(t.line_number > 0 for t in tasks)

    # Tasks should have different line numbers
    line_numbers = [t.line_number for t in tasks]
    assert len(set(line_numbers)) == len(line_numbers)


def test_update_preserves_file_structure(tmp_path: Path):
    """Test that updating status preserves file structure."""
    original_content = """# My PRD

Some intro text here.

## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task

Some notes here.

## Medium Priority
- [ ] PRD-003 Third task
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(original_content)

    parser = PRDParser(prd_file)
    parser.parse()

    # Update one task
    parser.update_task_status("PRD-002", PRDTaskStatus.COMPLETED)

    # Read back
    updated_content = prd_file.read_text()

    # Check that structure is preserved
    assert "# My PRD" in updated_content
    assert "Some intro text here" in updated_content
    assert "Some notes here" in updated_content
    assert "[x] PRD-002 Second task" in updated_content
    assert "[ ] PRD-001 First task" in updated_content
    assert "[ ] PRD-003 Third task" in updated_content


def test_parse_error_messages_are_helpful(tmp_path: Path):
    """Test that validation errors provide helpful, actionable error messages."""
    # Test multiple error types at once
    content = """## High Priority
- [ ] PRD-1 Invalid ID format (not 3 digits)
- [ ] PRD-002 Valid task
- [ ] PRD-002 Duplicate ID
- [ ] Task without ID
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(content)

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError) as exc_info:
        parser.parse()

    error_msg = str(exc_info.value)

    # Check that error message contains:
    # 1. Count of total errors (3 in this case)
    assert "3 validation error(s)" in error_msg

    # 2. Line numbers for each error
    assert "Line 2" in error_msg  # Invalid format
    assert "Line 4" in error_msg  # Duplicate
    assert "Line 5" in error_msg  # Missing ID

    # 3. Specific error descriptions
    assert "Invalid task ID format 'PRD-1'" in error_msg
    assert "Duplicate task ID 'PRD-002'" in error_msg
    assert "Task missing explicit ID" in error_msg

    # 4. Helpful fixes
    assert "Expected format: PRD-NNN where NNN is exactly 3 digits" in error_msg
    assert "Fix:" in error_msg
    assert "Change to a unique ID like" in error_msg

    # 5. Shows the problematic line content
    assert "Found:" in error_msg


def test_parse_error_task_outside_priority_section(tmp_path: Path):
    """Test error message for task outside priority section."""
    content = """- [ ] PRD-001 Task before any priority section

## High Priority
- [ ] PRD-002 Valid task
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(content)

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError) as exc_info:
        parser.parse()

    error_msg = str(exc_info.value)

    # Should mention the task is outside priority section
    assert "outside priority section" in error_msg
    assert "Line 1" in error_msg
    assert "PRD-001" in error_msg
    assert "Fix:" in error_msg
    assert "## High Priority" in error_msg  # Should suggest adding priority header


def test_suggest_next_id(tmp_path: Path):
    """Test that _suggest_next_id provides appropriate suggestions."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("")
    parser = PRDParser(prd_file)

    # Empty - should suggest PRD-001
    assert parser._suggest_next_id() == "PRD-001"

    # After adding some IDs
    parser._task_ids.add("PRD-001")
    parser._task_ids.add("PRD-002")
    assert parser._suggest_next_id() == "PRD-003"

    # Non-sequential IDs - should suggest max + 1
    parser._task_ids.add("PRD-010")
    assert parser._suggest_next_id() == "PRD-011"


def test_file_not_found_error_is_helpful(tmp_path: Path):
    """Test that FileNotFoundError includes helpful guidance."""
    prd_file = tmp_path / "nonexistent.md"
    parser = PRDParser(prd_file)

    with pytest.raises(FileNotFoundError) as exc_info:
        parser.parse()

    error_msg = str(exc_info.value)

    # Should include helpful guidance about format
    assert "Please create a PRD markdown file" in error_msg
    assert "## High Priority" in error_msg
    assert "- [ ] PRD-001" in error_msg


def test_backup_created_on_update(tmp_path: Path):
    """Test that backup is created when updating task status."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    backup_dir = tmp_path / "backups"
    parser = PRDParser(prd_file, backup_dir=backup_dir)
    parser.parse()

    # Update a task status
    parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)

    # Verify backup was created
    assert backup_dir.exists()
    backups = list(backup_dir.glob("test-*.md"))
    assert len(backups) == 1

    # Verify backup contains original content
    backup_content = backups[0].read_text()
    assert "[ ] PRD-001 Add user authentication" in backup_content


def test_backup_cleanup_keeps_max_backups(tmp_path: Path):
    """Test that old backups are cleaned up, keeping only MAX_BACKUPS."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    backup_dir = tmp_path / "backups"
    parser = PRDParser(prd_file, backup_dir=backup_dir)
    parser.parse()

    # Create more backups than MAX_BACKUPS (10)
    for i in range(12):
        parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)
        # Need to re-read to update tasks after modification
        parser._tasks = []
        parser._task_ids = set()
        parser._current_priority = None
        parser.parse()

    # Verify only MAX_BACKUPS remain
    backups = list(backup_dir.glob("test-*.md"))
    assert len(backups) == PRDParser.MAX_BACKUPS


def test_backup_restores_on_failure(tmp_path: Path):
    """Test that backup can be used to restore after corruption."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    backup_dir = tmp_path / "backups"
    parser = PRDParser(prd_file, backup_dir=backup_dir)
    parser.parse()

    # Create a backup
    parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)

    # Verify original file was modified
    modified_content = prd_file.read_text()
    assert "[~] PRD-001" in modified_content

    # Get backup file
    backups = list(backup_dir.glob("test-*.md"))
    assert len(backups) == 1
    backup_file = backups[0]

    # Verify backup has original content
    backup_content = backup_file.read_text()
    assert "[ ] PRD-001 Add user authentication" in backup_content

    # Simulate restoration
    prd_file.write_text(backup_content)

    # Verify we can parse the restored file
    parser2 = PRDParser(prd_file)
    tasks = parser2.parse()
    task_001 = next(t for t in tasks if t.task_id == "PRD-001")
    assert task_001.status == PRDTaskStatus.PENDING


def test_backup_with_blocking_reason(tmp_path: Path):
    """Test that backup is created when blocking task with reason."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    backup_dir = tmp_path / "backups"
    parser = PRDParser(prd_file, backup_dir=backup_dir)
    parser.parse()

    # Block a task with reason
    parser.update_task_status("PRD-001", PRDTaskStatus.BLOCKED, "waiting for API")

    # Verify backup was created
    backups = list(backup_dir.glob("test-*.md"))
    assert len(backups) == 1

    # Verify backup has original content without blocking reason
    backup_content = backups[0].read_text()
    assert "[ ] PRD-001 Add user authentication" in backup_content
    assert "blocked:" not in backup_content or "PRD-004" in backup_content  # Only existing blocked task


def test_backup_directory_created_automatically(tmp_path: Path):
    """Test that backup directory is created if it doesn't exist."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(VALID_PRD)

    backup_dir = tmp_path / "nested" / "backups"
    assert not backup_dir.exists()

    parser = PRDParser(prd_file, backup_dir=backup_dir)
    parser.parse()

    # Update task status (should create backup dir)
    parser.update_task_status("PRD-001", PRDTaskStatus.COMPLETED)

    # Verify directory was created
    assert backup_dir.exists()
    assert backup_dir.is_dir()

    # Verify backup exists
    backups = list(backup_dir.glob("test-*.md"))
    assert len(backups) == 1


def test_parse_empty_file_error(tmp_path: Path):
    """Test that empty PRD files produce helpful error message."""
    prd_file = tmp_path / "empty.md"
    prd_file.write_text("")  # Completely empty file

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError) as exc_info:
        parser.parse()

    error_msg = str(exc_info.value)

    # Should mention file is empty
    assert "empty" in error_msg.lower()
    assert str(prd_file) in error_msg

    # Should provide format examples
    assert "## High Priority" in error_msg
    assert "PRD-001" in error_msg
    assert "PRD-002" in error_msg

    # Should reference example file
    assert "examples/sample-prd.md" in error_msg


def test_parse_whitespace_only_file_error(tmp_path: Path):
    """Test that files with only whitespace are treated as empty."""
    prd_file = tmp_path / "whitespace.md"
    prd_file.write_text("\n\n   \n\t\n  \n")  # Only whitespace and newlines

    parser = PRDParser(prd_file)

    with pytest.raises(ValueError) as exc_info:
        parser.parse()

    error_msg = str(exc_info.value)

    # Should mention file is empty
    assert "empty" in error_msg.lower()

    # Should provide helpful guidance
    assert "## High Priority" in error_msg
    assert "PRD-001" in error_msg


def test_parse_file_with_headers_but_no_tasks(tmp_path: Path):
    """Test that files with only priority headers but no tasks are handled."""
    prd_file = tmp_path / "no-tasks.md"
    prd_file.write_text("""# My PRD

## High Priority

## Medium Priority

## Low Priority
""")

    parser = PRDParser(prd_file)

    # Should parse successfully but return empty list
    tasks = parser.parse()
    assert tasks == []
