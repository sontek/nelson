"""Tests for prd_orchestrator module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from nelson.prd_orchestrator import PRDOrchestrator
from nelson.prd_parser import PRDTaskStatus


# Sample PRD content for testing
SAMPLE_PRD = """# Test PRD

## High Priority
- [ ] PRD-001 Implement user authentication
- [ ] PRD-002 Create API endpoints

## Medium Priority
- [ ] PRD-003 Add logging system
- [ ] PRD-004 Write documentation

## Low Priority
- [ ] PRD-005 Add dark mode
"""

MIXED_STATUS_PRD = """# Test PRD

## High Priority
- [x] PRD-001 Completed task
- [~] PRD-002 In progress task
- [!] PRD-003 Blocked task (blocked: waiting for approval)

## Medium Priority
- [ ] PRD-004 Pending task

## Low Priority
- [ ] PRD-005 Another pending task
"""


@pytest.fixture
def temp_prd_file(tmp_path: Path) -> Path:
    """Create a temporary PRD file."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(SAMPLE_PRD)
    return prd_file


@pytest.fixture
def temp_prd_dir(tmp_path: Path) -> Path:
    """Create a temporary PRD directory."""
    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)
    return prd_dir


@pytest.fixture
def orchestrator(temp_prd_file: Path, temp_prd_dir: Path) -> PRDOrchestrator:
    """Create a PRDOrchestrator instance."""
    return PRDOrchestrator(temp_prd_file, temp_prd_dir)


def test_orchestrator_initialization(temp_prd_file: Path, temp_prd_dir: Path):
    """Test orchestrator initializes correctly."""
    orchestrator = PRDOrchestrator(temp_prd_file, temp_prd_dir)

    assert orchestrator.prd_file == temp_prd_file
    assert orchestrator.prd_dir == temp_prd_dir
    assert orchestrator.state_manager is not None
    assert orchestrator.parser is not None
    assert len(orchestrator.tasks) == 5


def test_orchestrator_initializes_task_mapping(
    temp_prd_file: Path, temp_prd_dir: Path
):
    """Test that orchestrator initializes task mapping in state."""
    orchestrator = PRDOrchestrator(temp_prd_file, temp_prd_dir)

    # Check that task mapping was initialized
    prd_state = orchestrator.state_manager.prd_state
    assert len(prd_state.task_mapping) == 5
    assert "PRD-001" in prd_state.task_mapping
    assert prd_state.task_mapping["PRD-001"]["original_text"] == "Implement user authentication"
    assert prd_state.task_mapping["PRD-001"]["priority"] == "high"


def test_get_next_pending_task_returns_high_priority_first(orchestrator: PRDOrchestrator):
    """Test that get_next_pending_task returns high priority tasks first."""
    result = orchestrator.get_next_pending_task()

    assert result is not None
    task_id, task_text, priority = result
    assert task_id == "PRD-001"
    assert task_text == "Implement user authentication"
    assert priority == "high"


def test_get_next_pending_task_priority_ordering(tmp_path: Path):
    """Test that tasks are returned in priority order."""
    # Create PRD with only medium and low tasks
    prd_content = """## Medium Priority
- [ ] PRD-001 Medium task

## Low Priority
- [ ] PRD-002 Low task
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Should get medium priority task first
    result = orchestrator.get_next_pending_task()
    assert result is not None
    assert result[0] == "PRD-001"
    assert result[2] == "medium"


def test_get_next_pending_task_skips_completed(tmp_path: Path):
    """Test that get_next_pending_task skips completed tasks."""
    prd_content = """## High Priority
- [x] PRD-001 Completed task
- [ ] PRD-002 Pending task
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    result = orchestrator.get_next_pending_task()
    assert result is not None
    assert result[0] == "PRD-002"


def test_get_next_pending_task_skips_blocked(tmp_path: Path):
    """Test that get_next_pending_task skips blocked tasks."""
    prd_content = """## High Priority
- [!] PRD-001 Blocked task (blocked: waiting)
- [ ] PRD-002 Pending task
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    result = orchestrator.get_next_pending_task()
    assert result is not None
    assert result[0] == "PRD-002"


def test_get_next_pending_task_returns_none_when_no_pending(tmp_path: Path):
    """Test that get_next_pending_task returns None when no pending tasks."""
    prd_content = """## High Priority
- [x] PRD-001 Completed task
- [!] PRD-002 Blocked task (blocked: waiting)
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    result = orchestrator.get_next_pending_task()
    assert result is None


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_success(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    tmp_path: Path,
):
    """Test successful task execution."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify success
    assert success is True

    # Verify branch creation was called
    mock_ensure_branch.assert_called_once_with("PRD-001", "Implement user authentication")

    # Verify subprocess was called with correct command
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "nelson"
    assert "Implement user authentication" in args[1]

    # Verify task state was saved
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.status.value == "completed"
    assert task_state.branch == "feature/PRD-001-implement-user-authentication"

    # Verify PRD file was updated
    updated_tasks = orchestrator.parser.parse()
    task = next(t for t in updated_tasks if t.task_id == "PRD-001")
    assert task.status == PRDTaskStatus.COMPLETED


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_failure(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test failed task execution."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=1)

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Verify task state shows failure
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.status.value == "failed"


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
def test_execute_task_branch_creation_failure(
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task handles branch creation failure."""
    from nelson.git_utils import GitError

    # Setup mock to raise GitError
    mock_ensure_branch.side_effect = GitError("Branch already exists")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_with_resume_context(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task prepends resume context to prompt."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Load task state and set resume context
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    task_state.resume_context = "API keys have been added to .env file"
    orchestrator.state_manager.save_task_state(task_state)

    # Execute task
    orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify resume context was prepended to prompt
    args = mock_run.call_args[0][0]
    prompt = args[1]
    assert "RESUME CONTEXT:" in prompt
    assert "API keys have been added to .env file" in prompt
    assert "Implement user authentication" in prompt


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_with_custom_prompt(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test execute_task with custom prompt."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Execute task with custom prompt
    custom_prompt = "Custom detailed instructions"
    orchestrator.execute_task(
        "PRD-001", "Implement user authentication", "high", prompt=custom_prompt
    )

    # Verify custom prompt was used
    args = mock_run.call_args[0][0]
    assert args[1] == custom_prompt


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_with_nelson_args(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test execute_task with additional Nelson arguments."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Execute task with Nelson args
    nelson_args = ["--max-iterations", "50"]
    orchestrator.execute_task(
        "PRD-001",
        "Implement user authentication",
        "high",
        nelson_args=nelson_args,
    )

    # Verify Nelson args were passed
    args = mock_run.call_args[0][0]
    assert "--max-iterations" in args
    assert "50" in args


@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
@patch("nelson.prd_orchestrator.NelsonState.load")
def test_execute_task_updates_cost_from_nelson_state(
    mock_load: Mock,
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task updates cost from Nelson state."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True so the Nelson state loading code runs
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    # Make Path() return the mock path when called with ".nelson/runs" division
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = mock_nelson_state_path

    # Mock Nelson state with cost data
    mock_nelson_state = MagicMock()
    mock_nelson_state.cost_usd = 1.23
    mock_nelson_state.total_iterations = 5
    mock_nelson_state.current_phase = 2
    mock_nelson_state.phase_name = "IMPLEMENT"
    mock_load.return_value = mock_nelson_state

    # Execute task
    orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify cost was updated in task state
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.cost_usd == 1.23
    assert task_state.iterations == 5
    assert task_state.phase == 2
    assert task_state.phase_name == "IMPLEMENT"


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_execute_all_pending_runs_all_tasks(
    mock_execute: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_all_pending runs all pending tasks."""
    # Setup mock to return success
    mock_execute.return_value = True

    # Execute all pending
    results = orchestrator.execute_all_pending()

    # Verify all tasks were executed
    assert len(results) == 5
    assert all(success for success in results.values())

    # Verify tasks were executed in priority order
    calls = mock_execute.call_args_list
    assert calls[0][0][0] == "PRD-001"  # High priority first
    assert calls[1][0][0] == "PRD-002"  # Second high priority
    assert calls[2][0][0] == "PRD-003"  # Medium priority
    assert calls[3][0][0] == "PRD-004"  # Second medium priority
    assert calls[4][0][0] == "PRD-005"  # Low priority


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_execute_all_pending_stops_on_failure(
    mock_execute: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_all_pending stops on failure when requested."""
    # Setup mock to fail on second task
    mock_execute.side_effect = [True, False, True, True, True]

    # Execute all pending with stop_on_failure
    results = orchestrator.execute_all_pending(stop_on_failure=True)

    # Verify only first two tasks were attempted
    assert len(results) == 2
    assert results["PRD-001"] is True
    assert results["PRD-002"] is False

    # Verify only two tasks were executed
    assert mock_execute.call_count == 2


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_execute_all_pending_continues_on_failure(
    mock_execute: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_all_pending continues on failure by default."""
    # Setup mock to fail on second task
    mock_execute.side_effect = [True, False, True, True, True]

    # Execute all pending without stop_on_failure
    results = orchestrator.execute_all_pending(stop_on_failure=False)

    # Verify all tasks were attempted
    assert len(results) == 5
    assert results["PRD-001"] is True
    assert results["PRD-002"] is False
    assert results["PRD-003"] is True


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_execute_all_pending_with_nelson_args(
    mock_execute: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_all_pending passes Nelson args to execute_task."""
    # Setup mock
    mock_execute.return_value = True

    # Execute with Nelson args
    nelson_args = ["--max-iterations", "75"]
    orchestrator.execute_all_pending(nelson_args=nelson_args)

    # Verify Nelson args were passed to each execute_task call
    for call_args in mock_execute.call_args_list:
        assert call_args[1]["nelson_args"] == nelson_args


def test_block_task(orchestrator: PRDOrchestrator):
    """Test blocking a task."""
    # Block task
    success = orchestrator.block_task("PRD-001", "Waiting for database schema")

    # Verify success
    assert success is True

    # Verify task state was updated
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.status.value == "blocked"
    assert task_state.blocking_reason == "Waiting for database schema"

    # Verify PRD file was updated
    updated_tasks = orchestrator.parser.parse()
    task = next(t for t in updated_tasks if t.task_id == "PRD-001")
    assert task.status == PRDTaskStatus.BLOCKED
    assert task.blocking_reason == "Waiting for database schema"


def test_block_task_nonexistent(orchestrator: PRDOrchestrator):
    """Test blocking a nonexistent task returns False."""
    success = orchestrator.block_task("PRD-999", "Some reason")
    assert success is False


def test_unblock_task(tmp_path: Path):
    """Test unblocking a task."""
    # Create PRD with blocked task
    prd_content = """## High Priority
- [!] PRD-001 Implement auth (blocked: waiting for keys)
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Unblock task with resume context
    success = orchestrator.unblock_task("PRD-001", "API keys added to .env")

    # Verify success
    assert success is True

    # Verify task state was updated
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement auth", "high"
    )
    assert task_state.status.value == "pending"
    assert task_state.resume_context == "API keys added to .env"

    # Verify PRD file was updated
    updated_tasks = orchestrator.parser.parse()
    task = next(t for t in updated_tasks if t.task_id == "PRD-001")
    assert task.status == PRDTaskStatus.PENDING


def test_unblock_task_nonexistent(orchestrator: PRDOrchestrator):
    """Test unblocking a nonexistent task returns False."""
    success = orchestrator.unblock_task("PRD-999")
    assert success is False


def test_unblock_task_not_blocked(orchestrator: PRDOrchestrator):
    """Test unblocking a non-blocked task returns False."""
    # PRD-001 is pending, not blocked
    success = orchestrator.unblock_task("PRD-001")
    assert success is False


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_resume_task(mock_execute: Mock, tmp_path: Path):
    """Test resuming a blocked task."""
    # Create PRD with blocked task
    prd_content = """## High Priority
- [!] PRD-001 Implement auth (blocked: waiting for keys)
"""
    prd_file = tmp_path / "test.md"
    prd_file.write_text(prd_content)

    prd_dir = tmp_path / ".nelson" / "prd"
    prd_dir.mkdir(parents=True)

    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Setup mock
    mock_execute.return_value = True

    # Resume task
    success = orchestrator.resume_task("PRD-001")

    # Verify success
    assert success is True

    # Verify execute_task was called
    mock_execute.assert_called_once_with(
        "PRD-001", "Implement auth", "high", nelson_args=None
    )

    # Verify task was updated to pending in PRD file before execution
    # (This happens inside resume_task before calling execute_task)


def test_resume_task_nonexistent(orchestrator: PRDOrchestrator):
    """Test resuming a nonexistent task returns False."""
    success = orchestrator.resume_task("PRD-999")
    assert success is False


def test_resume_task_wrong_status(orchestrator: PRDOrchestrator):
    """Test resuming a task in wrong status returns False."""
    # PRD-001 is pending, not blocked or in_progress
    success = orchestrator.resume_task("PRD-001")
    assert success is False


def test_get_status_summary(orchestrator: PRDOrchestrator):
    """Test getting status summary."""
    summary = orchestrator.get_status_summary()

    # Verify basic structure
    assert "prd_file" in summary
    assert "total_tasks" in summary
    assert "completed" in summary
    assert "in_progress" in summary
    assert "blocked" in summary
    assert "pending" in summary
    assert "failed" in summary
    assert "total_cost" in summary
    assert "tasks" in summary

    # Verify values
    assert summary["total_tasks"] == 5
    assert summary["pending"] == 5  # All tasks start as pending
    assert summary["completed"] == 0
    assert summary["blocked"] == 0
    assert summary["in_progress"] == 0


def test_get_task_info_existing(orchestrator: PRDOrchestrator):
    """Test getting info for an existing task."""
    info = orchestrator.get_task_info("PRD-001")

    # Verify info structure
    assert info is not None
    assert info["task_id"] == "PRD-001"
    assert info["task_text"] == "Implement user authentication"
    assert info["priority"] == "high"
    assert info["status"] == "pending"
    assert "branch" in info
    assert "nelson_run_id" in info
    assert "cost_usd" in info
    assert "iterations" in info


def test_get_task_info_nonexistent(orchestrator: PRDOrchestrator):
    """Test getting info for a nonexistent task."""
    info = orchestrator.get_task_info("PRD-999")
    assert info is None


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_keyboard_interrupt(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task handles keyboard interrupt gracefully."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.side_effect = KeyboardInterrupt()

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Verify task state shows failure
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.status.value == "failed"


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_exception(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task handles general exceptions."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.side_effect = Exception("Unexpected error")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
@patch("nelson.prd_orchestrator.NelsonState.load")
def test_execute_task_handles_missing_nelson_state(
    mock_load: Mock,
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_task handles missing Nelson state gracefully."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)
    mock_load.side_effect = FileNotFoundError("State file not found")

    # Execute task - should succeed despite missing state
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify success (task completion doesn't require state file)
    assert success is True

    # Task should still be marked as completed
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.status.value == "completed"


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_handles_file_not_found_error(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task handles FileNotFoundError (nelson not in PATH)."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.side_effect = FileNotFoundError("nelson command not found")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Check error message
    captured = capsys.readouterr()
    assert "'nelson' command not found in PATH" in captured.out
    assert "Install with: pip install nelson-cli" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_handles_permission_error(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task handles PermissionError."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.side_effect = PermissionError("Permission denied")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Check error message
    captured = capsys.readouterr()
    assert "Permission denied when executing Nelson" in captured.out
    assert "execute permissions" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_handles_os_error(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task handles OSError."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.side_effect = OSError("Too many open files")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Check error message
    captured = capsys.readouterr()
    assert "OS error when executing Nelson" in captured.out
    assert "system-level issues" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_provides_exit_code_feedback(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task provides specific feedback for exit codes."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"

    # Test exit code 1 (general error)
    mock_run.return_value = Mock(returncode=1)
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")
    assert success is False

    captured = capsys.readouterr()
    assert "Nelson exited with code 1" in captured.out
    assert "encountered an error" in captured.out

    # Reset parser state
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    # Test exit code 130 (SIGINT)
    mock_run.return_value = Mock(returncode=130)
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")
    assert success is False

    captured = capsys.readouterr()
    assert "Nelson exited with code 130" in captured.out
    assert "interrupted (SIGINT/Ctrl+C)" in captured.out

    # Reset parser state
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    # Test unexpected exit code
    mock_run.return_value = Mock(returncode=42)
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")
    assert success is False

    captured = capsys.readouterr()
    assert "Nelson exited with code 42" in captured.out
    assert "Unexpected exit code: 42" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_handles_unexpected_exception(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task handles unexpected exceptions gracefully."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"

    # Create an unexpected exception type
    class UnexpectedError(Exception):
        pass

    mock_run.side_effect = UnexpectedError("Something went wrong")

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify failure
    assert success is False

    # Check error message includes exception type and details
    captured = capsys.readouterr()
    assert "Unexpected error executing Nelson" in captured.out
    assert "UnexpectedError" in captured.out
    assert "Something went wrong" in captured.out
    assert "Please report this issue" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_all_pending_shows_progress_indicators(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_all_pending shows progress indicators during execution."""
    # Create PRD file with multiple pending tasks
    prd_file = tmp_path / "requirements.md"
    prd_content = """
## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task

## Medium Priority
- [ ] PRD-003 Third task
"""
    prd_file.write_text(prd_content)

    # Setup mocks
    mock_ensure_branch.return_value = "feature/test-branch"
    mock_run.return_value = Mock(returncode=0)

    # Create orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Execute all pending tasks
    results = orchestrator.execute_all_pending()

    # Verify all tasks executed
    assert len(results) == 3
    assert all(results.values())

    # Check progress indicators in output
    captured = capsys.readouterr()

    # Initial progress summary
    assert "PRD Execution Progress" in captured.out
    assert "Total tasks in PRD: 3" in captured.out
    assert "Already completed: 0" in captured.out
    assert "Pending to execute: 3" in captured.out

    # Individual task indicators (with emojis)
    assert "📋 Task 1 of 3 | Priority: HIGH" in captured.out
    assert "📋 Task 2 of 3 | Priority: HIGH" in captured.out
    assert "📋 Task 3 of 3 | Priority: MEDIUM" in captured.out

    # Interim progress after each task
    assert "📊 Progress:" in captured.out
    assert "% complete)" in captured.out
    assert "Remaining:" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_all_pending_shows_completion_percentage(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Test that progress shows completion percentage increasing."""
    # Create PRD with some already completed
    prd_file = tmp_path / "requirements.md"
    prd_content = """
## High Priority
- [x] PRD-001 Already done
- [ ] PRD-002 Pending task
- [ ] PRD-003 Another pending
"""
    prd_file.write_text(prd_content)

    # Setup mocks
    mock_ensure_branch.return_value = "feature/test-branch"
    mock_run.return_value = Mock(returncode=0)

    # Create orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Execute all pending tasks
    results = orchestrator.execute_all_pending()

    # Verify
    assert len(results) == 2

    # Check that progress shows completion percentages increasing
    captured = capsys.readouterr()
    assert "Pending to execute: 2" in captured.out

    # Should show increasing percentages as tasks complete
    # First task: 1/3 = 33.3%
    assert "33.3% complete" in captured.out
    # Second task: 2/3 = 66.7%
    assert "66.7% complete" in captured.out or "66.6% complete" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_shows_resume_indicator(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task shows resume indicator when resuming with context."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"
    mock_run.return_value = Mock(returncode=0)

    # Create task state with resume context
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    task_state.resume_context = "API keys added to .env file"
    orchestrator.state_manager.save_task_state(task_state)

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify success
    assert success is True

    # Check output includes resume indicator
    captured = capsys.readouterr()
    assert "🚀 Starting task: PRD-001" in captured.out
    assert "🔄 Resuming with context" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_task_shows_visual_status_icons(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_task shows visual status icons (success/failure)."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-implement-user-authentication"

    # Test success case
    mock_run.return_value = Mock(returncode=0)
    success = orchestrator.execute_task("PRD-001", "Implement user authentication", "high")
    assert success is True

    captured = capsys.readouterr()
    assert "✅ Task completed: PRD-001" in captured.out
    assert "🚀 Starting task: PRD-001" in captured.out

    # Test failure case
    mock_run.return_value = Mock(returncode=1)
    success = orchestrator.execute_task("PRD-002", "Another task", "high")
    assert success is False

    captured = capsys.readouterr()
    assert "❌ Task failed: PRD-002" in captured.out
    assert "Review the task and fix any issues before resuming" in captured.out


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_execute_all_pending_no_pending_tasks(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
):
    """Test that execute_all_pending handles case with no pending tasks gracefully."""
    # Create PRD with all completed tasks
    prd_file = tmp_path / "requirements.md"
    prd_content = """
## High Priority
- [x] PRD-001 Completed task
- [x] PRD-002 Another completed
"""
    prd_file.write_text(prd_content)

    # Create orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Execute all pending tasks
    results = orchestrator.execute_all_pending()

    # Verify no tasks executed
    assert len(results) == 0

    # Check that no progress summary is shown when there are no pending tasks
    captured = capsys.readouterr()
    assert "PRD Execution Progress" not in captured.out or "Pending to execute: 0" in captured.out


def test_check_task_text_changes_no_changes(orchestrator: PRDOrchestrator):
    """Test that check_task_text_changes returns empty list when no changes."""
    changes = orchestrator.check_task_text_changes()
    assert changes == []


def test_check_task_text_changes_with_change(tmp_path: Path):
    """Test that check_task_text_changes detects when task text is modified."""
    # Create initial PRD file
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Implement user authentication
- [ ] PRD-002 Add profile management
""")

    # Initialize orchestrator (will store original text)
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Verify no changes yet
    changes = orchestrator.check_task_text_changes()
    assert changes == []

    # Modify the PRD file
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Implement authentication with OAuth
- [ ] PRD-002 Add profile management
""")

    # Re-parse to get updated tasks
    orchestrator.tasks = orchestrator.parser.parse()

    # Check for changes
    changes = orchestrator.check_task_text_changes()

    # Verify change detected
    assert len(changes) == 1
    assert changes[0]["task_id"] == "PRD-001"
    assert changes[0]["original_text"] == "Implement user authentication"
    assert changes[0]["current_text"] == "Implement authentication with OAuth"


def test_check_task_text_changes_multiple_changes(tmp_path: Path):
    """Test detection of multiple task text changes."""
    # Create initial PRD file
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Task one
- [ ] PRD-002 Task two
- [ ] PRD-003 Task three
""")

    # Initialize orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Modify multiple tasks
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Task one modified
- [ ] PRD-002 Task two completely different
- [ ] PRD-003 Task three
""")

    # Re-parse
    orchestrator.tasks = orchestrator.parser.parse()

    # Check for changes
    changes = orchestrator.check_task_text_changes()

    # Verify both changes detected
    assert len(changes) == 2

    # Find changes by task_id
    changes_dict = {c["task_id"]: c for c in changes}

    assert "PRD-001" in changes_dict
    assert changes_dict["PRD-001"]["original_text"] == "Task one"
    assert changes_dict["PRD-001"]["current_text"] == "Task one modified"

    assert "PRD-002" in changes_dict
    assert changes_dict["PRD-002"]["original_text"] == "Task two"
    assert changes_dict["PRD-002"]["current_text"] == "Task two completely different"


def test_check_task_text_changes_whitespace_difference(tmp_path: Path):
    """Test that whitespace changes are detected (strict comparison)."""
    # Create initial PRD file
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Task description
""")

    # Initialize orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Modify with extra whitespace
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Task  description
""")

    # Re-parse
    orchestrator.tasks = orchestrator.parser.parse()

    # Check for changes
    changes = orchestrator.check_task_text_changes()

    # Verify whitespace change detected
    assert len(changes) == 1
    assert changes[0]["task_id"] == "PRD-001"
    assert changes[0]["original_text"] == "Task description"
    assert changes[0]["current_text"] == "Task  description"


def test_check_task_text_changes_new_task_not_reported(tmp_path: Path):
    """Test that new tasks (not in mapping yet) are not reported as changes."""
    # Create initial PRD file
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
""")

    # Initialize orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Add a new task
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    # Re-parse
    orchestrator.tasks = orchestrator.parser.parse()

    # Check for changes - new task should not be reported as change
    changes = orchestrator.check_task_text_changes()
    assert changes == []


def test_check_task_text_changes_case_sensitive(tmp_path: Path):
    """Test that text comparison is case-sensitive."""
    # Create initial PRD file
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 implement authentication
""")

    # Initialize orchestrator
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Change case
    prd_file.write_text("""## High Priority
- [ ] PRD-001 Implement Authentication
""")

    # Re-parse
    orchestrator.tasks = orchestrator.parser.parse()

    # Check for changes
    changes = orchestrator.check_task_text_changes()

    # Verify case change detected
    assert len(changes) == 1
    assert changes[0]["task_id"] == "PRD-001"
    assert changes[0]["original_text"] == "implement authentication"
    assert changes[0]["current_text"] == "Implement Authentication"
