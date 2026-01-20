"""Tests for prd_cli module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from nelson.prd_cli import main
from nelson.prd_task_state import TaskState, TaskStatus

# Sample PRD content for testing
SAMPLE_PRD = """# Test PRD

## High Priority
- [ ] PRD-001 Implement user authentication
- [ ] PRD-002 Create API endpoints

## Medium Priority
- [ ] PRD-003 Add logging system

## Low Priority
- [ ] PRD-004 Add dark mode
"""

MIXED_STATUS_PRD = """# Test PRD

## High Priority
- [x] PRD-001 Completed task
- [~] PRD-002 In progress task
- [!] PRD-003 Blocked task (blocked: waiting for approval)

## Medium Priority
- [ ] PRD-004 Pending task
"""


@pytest.fixture
def temp_prd_file(tmp_path: Path) -> Path:
    """Create a temporary PRD file."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(SAMPLE_PRD)
    return prd_file


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


def test_cli_help(cli_runner: CliRunner) -> None:
    """Test that CLI help displays correctly."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Execute tasks from a PRD" in result.output
    assert "--status" in result.output
    assert "--block" in result.output
    assert "--unblock" in result.output
    assert "--resume-task" in result.output
    assert "--task-info" in result.output
    assert "--dry-run" in result.output
    assert "--nelson-args" in result.output


def test_cli_missing_prd_file(cli_runner: CliRunner) -> None:
    """Test CLI error handling for missing PRD file."""
    result = cli_runner.invoke(main, ["nonexistent.md"])
    assert result.exit_code == 2  # Click's file not found error
    assert "does not exist" in result.output.lower() or "error" in result.output.lower()


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_status_command(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --status command displays task summary."""
    # Setup mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    # Create mock task states
    task1 = TaskState(
        task_id="PRD-001",
        task_text="Test task 1",
        status=TaskStatus.COMPLETED,
        priority="high",
        branch="feature/PRD-001-test-task-1",
        cost_usd=1.23,
        iterations=5,
        phase=4,
        phase_name="TEST",
    )
    task2 = TaskState(
        task_id="PRD-002",
        task_text="Test task 2",
        status=TaskStatus.IN_PROGRESS,
        priority="medium",
        branch="feature/PRD-002-test-task-2",
        cost_usd=0.45,
    )

    mock_orchestrator.get_status_summary.return_value = {
        "prd_file": str(temp_prd_file),
        "total_tasks": 2,
        "completed": 1,
        "in_progress": 1,
        "blocked": 0,
        "pending": 0,
        "failed": 0,
        "total_cost": 1.68,
        "tasks": [task1.to_dict(), task2.to_dict()],
    }

    # Run status command
    result = cli_runner.invoke(main, ["--status", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "PRD Status:" in result.output
    assert "Total: 2 tasks" in result.output
    assert "Completed: 1" in result.output
    assert "In Progress: 1" in result.output
    assert "Total Cost: $1.68" in result.output
    assert "PRD-001" in result.output
    assert "PRD-002" in result.output
    assert "feature/PRD-001-test-task-1" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_status_command_with_filter(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --status command with --filter option."""
    # Setup mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    # Create mock task states with mixed statuses
    completed_task = TaskState(
        task_id="PRD-001",
        task_text="Completed task",
        status=TaskStatus.COMPLETED,
        priority="high",
    )
    in_progress_task = TaskState(
        task_id="PRD-002",
        task_text="In progress task",
        status=TaskStatus.IN_PROGRESS,
        priority="high",
    )
    blocked_task = TaskState(
        task_id="PRD-003",
        task_text="Blocked task",
        status=TaskStatus.BLOCKED,
        priority="medium",
    )
    pending_task = TaskState(
        task_id="PRD-004",
        task_text="Pending task",
        status=TaskStatus.PENDING,
        priority="low",
    )

    mock_orchestrator.get_status_summary.return_value = {
        "prd_file": str(temp_prd_file),
        "total_tasks": 4,
        "completed": 1,
        "in_progress": 1,
        "blocked": 1,
        "pending": 1,
        "failed": 0,
        "total_cost": 1.23,
        "tasks": [
            completed_task.to_dict(),
            in_progress_task.to_dict(),
            blocked_task.to_dict(),
            pending_task.to_dict(),
        ],
    }

    # Test filter=active (should show 3 tasks: in-progress, blocked, pending)
    result = cli_runner.invoke(main, ["--status", "--filter", "active", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Filtered by: active (3 tasks shown)" in result.output
    assert "Tasks (filtered: active)" in result.output
    # Should show non-completed tasks
    assert "PRD-002" in result.output  # in-progress
    assert "PRD-003" in result.output  # blocked
    assert "PRD-004" in result.output  # pending
    # Should NOT show completed task
    assert "PRD-001" not in result.output  # completed

    # Test filter=pending (should show 1 task)
    result = cli_runner.invoke(main, ["--status", "--filter", "pending", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Filtered by: pending (1 tasks shown)" in result.output
    assert "PRD-004" in result.output  # pending
    assert "PRD-001" not in result.output  # completed
    assert "PRD-002" not in result.output  # in-progress
    assert "PRD-003" not in result.output  # blocked

    # Test filter=completed (should show 1 task)
    result = cli_runner.invoke(main, ["--status", "--filter", "completed", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Filtered by: completed (1 tasks shown)" in result.output
    assert "PRD-001" in result.output  # completed
    assert "PRD-002" not in result.output
    assert "PRD-003" not in result.output
    assert "PRD-004" not in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_block_command_success(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --block command with reason."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.block_task.return_value = True

    result = cli_runner.invoke(
        main,
        [
            "--block",
            "PRD-001",
            "--reason",
            "Waiting for API keys",
            str(temp_prd_file),
        ],
    )

    assert result.exit_code == 0
    mock_orchestrator.block_task.assert_called_once_with("PRD-001", "Waiting for API keys")


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_block_command_failure(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --block command failure (nonexistent task)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.block_task.return_value = False

    result = cli_runner.invoke(
        main,
        [
            "--block",
            "PRD-999",
            "--reason",
            "Some reason",
            str(temp_prd_file),
        ],
    )

    assert result.exit_code == 1


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_block_command_missing_reason(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --block command error when --reason is missing."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    result = cli_runner.invoke(main, ["--block", "PRD-001", str(temp_prd_file)])

    assert result.exit_code == 1
    assert "--reason is required" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_unblock_command_success(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --unblock command without context."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.unblock_task.return_value = True

    result = cli_runner.invoke(main, ["--unblock", "PRD-001", str(temp_prd_file)])

    assert result.exit_code == 0
    mock_orchestrator.unblock_task.assert_called_once_with("PRD-001", None)


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_unblock_command_with_context(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --unblock command with resume context."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.unblock_task.return_value = True

    result = cli_runner.invoke(
        main,
        [
            "--unblock",
            "PRD-001",
            "--context",
            "API keys added to .env",
            str(temp_prd_file),
        ],
    )

    assert result.exit_code == 0
    mock_orchestrator.unblock_task.assert_called_once_with("PRD-001", "API keys added to .env")


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_unblock_command_failure(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --unblock command failure."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.unblock_task.return_value = False

    result = cli_runner.invoke(main, ["--unblock", "PRD-999", str(temp_prd_file)])

    assert result.exit_code == 1


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_resume_task_command_success(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --resume-task command."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.resume_task.return_value = True

    result = cli_runner.invoke(main, ["--resume-task", "PRD-001", str(temp_prd_file)])

    assert result.exit_code == 0
    mock_orchestrator.resume_task.assert_called_once_with(
        "PRD-001", None, no_branch_setup=False
    )


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_resume_task_command_failure(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --resume-task command failure."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.resume_task.return_value = False

    result = cli_runner.invoke(main, ["--resume-task", "PRD-999", str(temp_prd_file)])

    assert result.exit_code == 1


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_task_info_command_success(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --task-info command displays detailed information."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    mock_orchestrator.get_task_info.return_value = {
        "task_id": "PRD-001",
        "task_text": "Test task",
        "status": "completed",
        "priority": "high",
        "branch": "feature/PRD-001-test-task",
        "nelson_run_id": "run-123",
        "cost_usd": 2.34,
        "iterations": 10,
        "phase": 6,
        "phase_name": "COMMIT",
        "started_at": "2025-01-15T10:00:00Z",
        "completed_at": "2025-01-15T12:00:00Z",
        "blocked_at": None,
        "blocking_reason": None,
        "resume_context": None,
    }

    result = cli_runner.invoke(main, ["--task-info", "PRD-001", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Task Details: PRD-001" in result.output
    assert "Test task" in result.output  # Description is in table format
    assert "Status" in result.output
    assert "HIGH" in result.output  # Priority is uppercase in display
    assert "feature/PRD-001-test-task" in result.output
    assert "run-123" in result.output
    assert "$2.34" in result.output
    assert "10" in result.output  # Iterations value
    assert "6 (COMMIT)" in result.output  # Phase is in table format


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_task_info_command_not_found(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --task-info command for nonexistent task."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.get_task_info.return_value = None

    result = cli_runner.invoke(main, ["--task-info", "PRD-999", str(temp_prd_file)])

    assert result.exit_code == 1
    assert "Task not found" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_task_info_with_blocking_info(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --task-info command displays blocking information."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    mock_orchestrator.get_task_info.return_value = {
        "task_id": "PRD-003",
        "task_text": "Blocked task",
        "status": "blocked",
        "priority": "high",
        "branch": "feature/PRD-003-blocked-task",
        "nelson_run_id": None,
        "cost_usd": 0.5,
        "iterations": 2,
        "phase": None,
        "phase_name": None,
        "started_at": "2025-01-15T10:00:00Z",
        "completed_at": None,
        "blocked_at": "2025-01-15T10:30:00Z",
        "blocking_reason": "Waiting for API keys",
        "resume_context": "Keys added to .env as API_KEY",
    }

    result = cli_runner.invoke(main, ["--task-info", "PRD-003", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Blocking Reason" in result.output  # In box format, no colon
    assert "Waiting for API keys" in result.output
    assert "Resume Context" in result.output  # In box format, no colon
    assert "Keys added to .env as API_KEY" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_dry_run_command(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --dry-run command previews tasks without executing."""
    from nelson.prd_parser import PRDTask, PRDTaskStatus

    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_file = temp_prd_file

    # Create mock pending tasks
    mock_orchestrator.tasks = [
        PRDTask(
            task_id="PRD-001",
            task_text="High priority task",
            status=PRDTaskStatus.PENDING,
            priority="high",
            line_number=3,
        ),
        PRDTask(
            task_id="PRD-002",
            task_text="Medium priority task",
            status=PRDTaskStatus.PENDING,
            priority="medium",
            line_number=6,
        ),
        PRDTask(
            task_id="PRD-003",
            task_text="Already completed",
            status=PRDTaskStatus.COMPLETED,
            priority="high",
            line_number=4,
        ),
    ]

    result = cli_runner.invoke(main, ["--dry-run", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Dry run for:" in result.output
    assert "Would execute 2 tasks:" in result.output
    assert "PRD-001" in result.output
    assert "PRD-002" in result.output
    # Completed task should not be shown
    assert "PRD-003" not in result.output or "Already completed" not in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_dry_run_no_pending_tasks(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --dry-run command when no tasks are pending."""
    from nelson.prd_parser import PRDTask, PRDTaskStatus

    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_file = temp_prd_file

    # All tasks completed
    mock_orchestrator.tasks = [
        PRDTask(
            task_id="PRD-001",
            task_text="Completed task",
            status=PRDTaskStatus.COMPLETED,
            priority="high",
            line_number=3,
        ),
    ]

    result = cli_runner.invoke(main, ["--dry-run", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "No pending tasks to execute" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_main_execution_flow(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test main execution flow (no flags)."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    # Mock execution results
    mock_orchestrator.execute_all_pending.return_value = {
        "PRD-001": True,
        "PRD-002": True,
    }

    # Mock status summary
    mock_orchestrator.get_status_summary.return_value = {
        "total_tasks": 4,
        "completed": 2,
        "in_progress": 0,
        "blocked": 0,
        "pending": 2,
        "failed": 0,
        "total_cost": 3.45,
    }

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Starting PRD execution:" in result.output
    assert "PRD directory:" in result.output
    assert "Execution Summary" in result.output
    assert "Tasks executed: 2" in result.output
    assert "Succeeded: 2" in result.output
    assert "Total cost: $3.45" in result.output
    mock_orchestrator.execute_all_pending.assert_called_once_with(
        nelson_args=None, stop_on_failure=False, no_branch_setup=False
    )


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_main_execution_with_stop_on_failure(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test main execution with --stop-on-failure flag."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.execute_all_pending.return_value = {
        "PRD-001": True,
        "PRD-002": False,
    }

    mock_orchestrator.get_status_summary.return_value = {
        "total_tasks": 4,
        "completed": 1,
        "in_progress": 0,
        "blocked": 0,
        "pending": 2,
        "failed": 1,
        "total_cost": 1.23,
    }

    result = cli_runner.invoke(main, ["--stop-on-failure", str(temp_prd_file)])

    assert result.exit_code == 1  # Exit code 1 because a task failed
    assert "Tasks executed: 2" in result.output
    assert "Succeeded: 1" in result.output
    assert "Failed: 1" in result.output
    mock_orchestrator.execute_all_pending.assert_called_once_with(
        nelson_args=None, stop_on_failure=True, no_branch_setup=False
    )


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_main_execution_no_tasks(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test main execution when no tasks are executed."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.execute_all_pending.return_value = {}

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 0
    assert "No tasks were executed" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_resume_from_last(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --resume flag continues from last incomplete task."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.get_next_pending_task.return_value = (
        "PRD-003",
        "Resume this task",
        "medium",
    )
    mock_orchestrator.execute_all_pending.return_value = {"PRD-003": True}
    mock_orchestrator.get_status_summary.return_value = {
        "total_tasks": 5,
        "completed": 3,
        "in_progress": 0,
        "blocked": 0,
        "pending": 2,
        "failed": 0,
        "total_cost": 2.5,
    }

    result = cli_runner.invoke(main, ["--resume", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Resuming from task: PRD-003" in result.output
    mock_orchestrator.get_next_pending_task.assert_called_once()


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_resume_from_last_no_pending(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --resume flag when no pending tasks exist."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.get_next_pending_task.return_value = None

    result = cli_runner.invoke(main, ["--resume", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "No pending tasks to resume" in result.output
    mock_orchestrator.execute_all_pending.assert_not_called()


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_custom_prd_dir(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path, tmp_path: Path
) -> None:
    """Test --prd-dir option to override directory."""
    custom_dir = tmp_path / "custom_prd"

    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = custom_dir

    mock_orchestrator.execute_all_pending.return_value = {}

    result = cli_runner.invoke(main, ["--prd-dir", str(custom_dir), str(temp_prd_file)])

    assert result.exit_code == 0
    mock_orchestrator_class.assert_called_once_with(temp_prd_file, custom_dir)


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_keyboard_interrupt_handling(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test CLI handles keyboard interrupt gracefully."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.execute_all_pending.side_effect = KeyboardInterrupt()

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 130
    assert "interrupted by user" in result.output.lower()


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_value_error_handling(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test CLI handles ValueError (invalid PRD format)."""
    mock_orchestrator_class.side_effect = ValueError("Invalid PRD format")

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 1
    assert "Error: Invalid PRD format" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_file_not_found_error_handling(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test CLI handles FileNotFoundError."""
    mock_orchestrator_class.side_effect = FileNotFoundError("State file not found")

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 1
    assert "Error: State file not found" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_unexpected_error_handling(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test CLI handles unexpected exceptions."""
    mock_orchestrator_class.side_effect = RuntimeError("Unexpected error occurred")

    result = cli_runner.invoke(main, [str(temp_prd_file)])

    assert result.exit_code == 1
    assert "Unexpected error" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_status_with_failed_tasks(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --status command displays failed tasks count."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    task1 = TaskState(
        task_id="PRD-001",
        task_text="Failed task",
        status=TaskStatus.FAILED,
        priority="high",
    )

    mock_orchestrator.get_status_summary.return_value = {
        "prd_file": str(temp_prd_file),
        "total_tasks": 1,
        "completed": 0,
        "in_progress": 0,
        "blocked": 0,
        "pending": 0,
        "failed": 1,
        "total_cost": 0.5,
        "tasks": [task1.to_dict()],
    }

    result = cli_runner.invoke(main, ["--status", str(temp_prd_file)])

    assert result.exit_code == 0
    assert "Failed: 1" in result.output


def test_cli_get_status_icon() -> None:
    """Test status icon helper function."""
    from nelson.prd_cli import _get_status_icon

    assert _get_status_icon(TaskStatus.COMPLETED) == "✓"
    assert _get_status_icon(TaskStatus.IN_PROGRESS) == "~"
    assert _get_status_icon(TaskStatus.BLOCKED) == "!"
    assert _get_status_icon(TaskStatus.FAILED) == "✗"
    assert _get_status_icon(TaskStatus.PENDING) == "○"


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_nelson_args_passed_to_execute_all_pending(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --nelson-args option passes arguments to execute_all_pending."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.prd_dir = Path(".nelson/prd")

    mock_orchestrator.execute_all_pending.return_value = {"PRD-001": True}
    mock_orchestrator.get_status_summary.return_value = {
        "total_tasks": 1,
        "completed": 1,
        "in_progress": 0,
        "blocked": 0,
        "pending": 0,
        "failed": 0,
        "total_cost": 1.5,
    }

    result = cli_runner.invoke(
        main,
        ["--nelson-args", "--model opus --max-iterations 100", str(temp_prd_file)],
    )

    assert result.exit_code == 0
    mock_orchestrator.execute_all_pending.assert_called_once_with(
        nelson_args=["--model", "opus", "--max-iterations", "100"],
        stop_on_failure=False,
        no_branch_setup=False,
    )


@patch("nelson.prd_cli.PRDOrchestrator")
def test_cli_nelson_args_passed_to_resume_task(
    mock_orchestrator_class: Mock, cli_runner: CliRunner, temp_prd_file: Path
) -> None:
    """Test --nelson-args option passes arguments to resume_task."""
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator
    mock_orchestrator.resume_task.return_value = True

    result = cli_runner.invoke(
        main,
        [
            "--resume-task",
            "PRD-001",
            "--nelson-args",
            "--model haiku",
            str(temp_prd_file),
        ],
    )

    assert result.exit_code == 0
    mock_orchestrator.resume_task.assert_called_once_with(
        "PRD-001", ["--model", "haiku"], no_branch_setup=False
    )


@patch("nelson.prd_cli.PRDOrchestrator")
def test_status_shows_text_change_warnings(
    mock_orchestrator_class: Mock,
    cli_runner: CliRunner,
    temp_prd_file: Path,
):
    """Test that status command displays warnings for changed task text."""
    # Setup mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    # Mock status summary
    mock_orchestrator.get_status_summary.return_value = {
        "prd_file": str(temp_prd_file),
        "total_tasks": 2,
        "completed": 0,
        "in_progress": 0,
        "blocked": 0,
        "pending": 2,
        "failed": 0,
        "total_cost": 0.0,
        "tasks": [
            {
                "task_id": "PRD-001",
                "task_text": "Implement authentication with OAuth",
                "status": "pending",
                "branch": None,
                "blocking_reason": None,
                "cost_usd": 0.0,
                "iterations": 0,
                "phase": None,
                "phase_name": None,
            },
            {
                "task_id": "PRD-002",
                "task_text": "Create API endpoints",
                "status": "pending",
                "branch": None,
                "blocking_reason": None,
                "cost_usd": 0.0,
                "iterations": 0,
                "phase": None,
                "phase_name": None,
            },
        ],
    }

    # Mock text changes
    mock_orchestrator.check_task_text_changes.return_value = [
        {
            "task_id": "PRD-001",
            "original_text": "Implement user authentication",
            "current_text": "Implement authentication with OAuth",
        }
    ]

    # Run status command
    result = cli_runner.invoke(main, ["--status", str(temp_prd_file)])

    # Verify warning is displayed
    assert result.exit_code == 0
    assert "Task text changes detected:" in result.output  # Warning box format
    assert "PRD-001" in result.output
    assert "Implement user authentication" in result.output
    assert "Implement authentication with OAuth" in result.output
    assert "Task descriptions have been modified" in result.output


@patch("nelson.prd_cli.PRDOrchestrator")
def test_status_no_warnings_when_no_changes(
    mock_orchestrator_class: Mock,
    cli_runner: CliRunner,
    temp_prd_file: Path,
):
    """Test that status command shows no warnings when text hasn't changed."""
    # Setup mock orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator_class.return_value = mock_orchestrator

    # Mock status summary
    mock_orchestrator.get_status_summary.return_value = {
        "prd_file": str(temp_prd_file),
        "total_tasks": 1,
        "completed": 0,
        "in_progress": 0,
        "blocked": 0,
        "pending": 1,
        "failed": 0,
        "total_cost": 0.0,
        "tasks": [
            {
                "task_id": "PRD-001",
                "task_text": "Implement user authentication",
                "status": "pending",
                "branch": None,
                "blocking_reason": None,
                "cost_usd": 0.0,
                "iterations": 0,
                "phase": None,
                "phase_name": None,
            }
        ],
    }

    # Mock no text changes
    mock_orchestrator.check_task_text_changes.return_value = []

    # Run status command
    result = cli_runner.invoke(main, ["--status", str(temp_prd_file)])

    # Verify no warning is displayed
    assert result.exit_code == 0
    assert "WARNING: Task text changes detected" not in result.output
