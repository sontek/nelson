"""Tests for status block parser."""

import pytest

from nelson.status_parser import (
    ExecutionStatus,
    StatusBlock,
    StatusBlockError,
    TestsStatus,
    WorkType,
    extract_status_block_text,
    parse_status_block,
    status_block_to_dict,
)


class TestEnums:
    """Test enum definitions."""

    def test_execution_status_values(self) -> None:
        """Test ExecutionStatus enum has correct values."""
        assert ExecutionStatus.IN_PROGRESS == "IN_PROGRESS"
        assert ExecutionStatus.COMPLETE == "COMPLETE"
        assert ExecutionStatus.BLOCKED == "BLOCKED"

    def test_test_status_values(self) -> None:
        """Test TestStatus enum has correct values."""
        assert TestsStatus.PASSING == "PASSING"
        assert TestsStatus.FAILING == "FAILING"
        assert TestsStatus.NOT_RUN == "NOT_RUN"

    def test_work_type_values(self) -> None:
        """Test WorkType enum has correct values."""
        assert WorkType.IMPLEMENTATION == "IMPLEMENTATION"
        assert WorkType.TESTING == "TESTING"
        assert WorkType.DOCUMENTATION == "DOCUMENTATION"
        assert WorkType.REFACTORING == "REFACTORING"


class TestStatusBlockDataclass:
    """Test StatusBlock dataclass."""

    def test_status_block_creation(self) -> None:
        """Test creating a StatusBlock instance."""
        block = StatusBlock(
            status=ExecutionStatus.IN_PROGRESS,
            tasks_completed_this_loop=2,
            files_modified=3,
            tests_status=TestsStatus.PASSING,
            work_type=WorkType.IMPLEMENTATION,
            exit_signal=False,
            recommendation="Continue with next task",
            raw_block="RAW DATA",
        )

        assert block.status == ExecutionStatus.IN_PROGRESS
        assert block.tasks_completed_this_loop == 2
        assert block.files_modified == 3
        assert block.tests_status == TestsStatus.PASSING
        assert block.work_type == WorkType.IMPLEMENTATION
        assert block.exit_signal is False
        assert block.recommendation == "Continue with next task"
        assert block.raw_block == "RAW DATA"

    def test_status_block_immutable(self) -> None:
        """Test StatusBlock is immutable (frozen dataclass)."""
        block = StatusBlock(
            status=ExecutionStatus.COMPLETE,
            tasks_completed_this_loop=1,
            files_modified=1,
            tests_status=TestsStatus.PASSING,
            work_type=WorkType.IMPLEMENTATION,
            exit_signal=True,
            recommendation="Done",
            raw_block="RAW",
        )

        with pytest.raises(AttributeError):
            block.status = ExecutionStatus.BLOCKED  # type: ignore


class TestExtractStatusBlockText:
    """Test extracting raw status block text."""

    def test_extract_complete_status_block(self) -> None:
        """Test extracting status block with valid delimiters."""
        content = """
Some text before
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
---END_RALPH_STATUS---
Some text after
        """

        result = extract_status_block_text(content)
        assert "STATUS: IN_PROGRESS" in result
        assert "TASKS_COMPLETED_THIS_LOOP: 1" in result
        assert "Some text before" not in result
        assert "Some text after" not in result

    def test_extract_missing_start_marker(self) -> None:
        """Test error when start marker is missing."""
        content = "STATUS: IN_PROGRESS\n---END_RALPH_STATUS---"

        with pytest.raises(StatusBlockError, match="start marker not found"):
            extract_status_block_text(content)

    def test_extract_missing_end_marker(self) -> None:
        """Test error when end marker is missing."""
        content = "---RALPH_STATUS---\nSTATUS: IN_PROGRESS"

        with pytest.raises(StatusBlockError, match="end marker not found"):
            extract_status_block_text(content)

    def test_extract_empty_content(self) -> None:
        """Test error with empty content."""
        with pytest.raises(StatusBlockError, match="start marker not found"):
            extract_status_block_text("")


class TestParseStatusBlock:
    """Test parsing complete status blocks."""

    def test_parse_valid_in_progress_block(self) -> None:
        """Test parsing a valid IN_PROGRESS status block."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 2
FILES_MODIFIED: 3
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Continue with next Phase 2 task
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.status == ExecutionStatus.IN_PROGRESS
        assert block.tasks_completed_this_loop == 2
        assert block.files_modified == 3
        assert block.tests_status == TestsStatus.PASSING
        assert block.work_type == WorkType.IMPLEMENTATION
        assert block.exit_signal is False
        assert block.recommendation == "Continue with next Phase 2 task"
        assert "STATUS: IN_PROGRESS" in block.raw_block

    def test_parse_valid_complete_block(self) -> None:
        """Test parsing a COMPLETE status block with EXIT_SIGNAL."""
        content = """
---RALPH_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: All tasks complete, tests passing, workflow finished
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.status == ExecutionStatus.COMPLETE
        assert block.tasks_completed_this_loop == 1
        assert block.files_modified == 1
        assert block.tests_status == TestsStatus.PASSING
        assert block.work_type == WorkType.IMPLEMENTATION
        assert block.exit_signal is True
        assert "All tasks complete" in block.recommendation

    def test_parse_blocked_status(self) -> None:
        """Test parsing a BLOCKED status block."""
        content = """
---RALPH_STATUS---
STATUS: BLOCKED
TASKS_COMPLETED_THIS_LOOP: 0
FILES_MODIFIED: 0
TESTS_STATUS: FAILING
WORK_TYPE: DEBUGGING
EXIT_SIGNAL: false
RECOMMENDATION: Same import error 3x, needs investigation
---END_RALPH_STATUS---
        """

        # Note: DEBUGGING is not a valid WorkType, this should raise an error
        with pytest.raises(StatusBlockError, match="Invalid work_type value"):
            parse_status_block(content)

    def test_parse_testing_work_type(self) -> None:
        """Test parsing TESTING work type."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 0
FILES_MODIFIED: 0
TESTS_STATUS: PASSING
WORK_TYPE: TESTING
EXIT_SIGNAL: false
RECOMMENDATION: Running test suite
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.work_type == WorkType.TESTING
        assert block.tests_status == TestsStatus.PASSING

    def test_parse_failing_tests(self) -> None:
        """Test parsing with failing tests."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 2
TESTS_STATUS: FAILING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Fix test failures
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.tests_status == TestsStatus.FAILING
        assert block.exit_signal is False

    def test_parse_not_run_tests(self) -> None:
        """Test parsing with tests not run."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: NOT_RUN
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Tests not required for this phase
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.tests_status == TestsStatus.NOT_RUN

    def test_parse_exit_signal_variants(self) -> None:
        """Test parsing different EXIT_SIGNAL values."""
        # Test 'true'
        content_true = """
---RALPH_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: Done
---END_RALPH_STATUS---
        """
        assert parse_status_block(content_true).exit_signal is True

        # Test 'false'
        content_false = content_true.replace("EXIT_SIGNAL: true", "EXIT_SIGNAL: false")
        assert parse_status_block(content_false).exit_signal is False

        # Test '1'
        content_one = content_true.replace("EXIT_SIGNAL: true", "EXIT_SIGNAL: 1")
        assert parse_status_block(content_one).exit_signal is True

        # Test '0'
        content_zero = content_true.replace("EXIT_SIGNAL: true", "EXIT_SIGNAL: 0")
        assert parse_status_block(content_zero).exit_signal is False

        # Test 'yes'
        content_yes = content_true.replace("EXIT_SIGNAL: true", "EXIT_SIGNAL: yes")
        assert parse_status_block(content_yes).exit_signal is True

    def test_parse_invalid_numeric_fields(self) -> None:
        """Test parsing with invalid numeric values defaults to 0."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: invalid
FILES_MODIFIED: not_a_number
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Numbers were invalid
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        # Should default to 0 when parsing fails
        assert block.tasks_completed_this_loop == 0
        assert block.files_modified == 0

    def test_parse_missing_required_field(self) -> None:
        """Test error when required field is missing."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Missing tasks_completed_this_loop
---END_RALPH_STATUS---
        """

        with pytest.raises(
            StatusBlockError, match="Missing required fields.*tasks_completed_this_loop"
        ):
            parse_status_block(content)

    def test_parse_invalid_status_value(self) -> None:
        """Test error when status value is invalid."""
        content = """
---RALPH_STATUS---
STATUS: UNKNOWN
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Invalid status
---END_RALPH_STATUS---
        """

        with pytest.raises(StatusBlockError, match="Invalid status value"):
            parse_status_block(content)

    def test_parse_invalid_tests_status_value(self) -> None:
        """Test error when tests_status value is invalid."""
        content = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: UNKNOWN
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Invalid test status
---END_RALPH_STATUS---
        """

        with pytest.raises(StatusBlockError, match="Invalid tests_status value"):
            parse_status_block(content)

    def test_parse_with_extra_whitespace(self) -> None:
        """Test parsing with extra whitespace is handled correctly."""
        content = """
---RALPH_STATUS---
STATUS:    IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP:   2
FILES_MODIFIED:  3
TESTS_STATUS:     PASSING
WORK_TYPE:   IMPLEMENTATION
EXIT_SIGNAL:    false
RECOMMENDATION:   Continue with next task
---END_RALPH_STATUS---
        """

        block = parse_status_block(content)

        assert block.status == ExecutionStatus.IN_PROGRESS
        assert block.tasks_completed_this_loop == 2
        assert block.files_modified == 3

    def test_parse_with_surrounding_text(self) -> None:
        """Test parsing works with text before and after status block."""
        content = """
This is some output from the AI.

Here are my thoughts about the task...

---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 2
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Continue implementation
---END_RALPH_STATUS---

And here is some more text after the status block.
        """

        block = parse_status_block(content)

        assert block.status == ExecutionStatus.IN_PROGRESS
        assert block.recommendation == "Continue implementation"


class TestStatusBlockToDict:
    """Test converting StatusBlock to dictionary."""

    def test_convert_to_dict(self) -> None:
        """Test converting StatusBlock to dictionary format."""
        block = StatusBlock(
            status=ExecutionStatus.IN_PROGRESS,
            tasks_completed_this_loop=2,
            files_modified=3,
            tests_status=TestsStatus.PASSING,
            work_type=WorkType.IMPLEMENTATION,
            exit_signal=False,
            recommendation="Continue",
            raw_block="RAW",
        )

        result = status_block_to_dict(block)

        assert result == {
            "status": "IN_PROGRESS",
            "tasks_completed": 2,
            "files_modified": 3,
            "tests_status": "PASSING",
            "work_type": "IMPLEMENTATION",
            "exit_signal": False,
            "recommendation": "Continue",
        }

    def test_convert_complete_to_dict(self) -> None:
        """Test converting COMPLETE status to dict."""
        block = StatusBlock(
            status=ExecutionStatus.COMPLETE,
            tasks_completed_this_loop=1,
            files_modified=1,
            tests_status=TestsStatus.PASSING,
            work_type=WorkType.IMPLEMENTATION,
            exit_signal=True,
            recommendation="All done",
            raw_block="RAW",
        )

        result = status_block_to_dict(block)

        assert result["status"] == "COMPLETE"
        assert result["exit_signal"] is True
