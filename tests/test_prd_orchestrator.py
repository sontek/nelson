"""Tests for prd_orchestrator module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from nelson.prd_orchestrator import PRDOrchestrator
from nelson.prd_parser import PRDTaskStatus
from nelson.prd_task_state import TaskStatus

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


@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_nelson_cli_command_construction(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that nelson CLI commands are constructed correctly with all components."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Test 1: Basic command without args or resume context
    orchestrator.execute_task("PRD-001", "Implement feature", "high")

    args = mock_run.call_args[0][0]
    assert args[0] == "nelson", "First argument should be 'nelson' command"
    assert args[1] == "Implement feature", "Second argument should be the prompt"
    assert len(args) == 2, "Should only have nelson and prompt for basic command"

    # Verify check=False is used (allows us to handle exit codes)
    kwargs = mock_run.call_args[1]
    assert not kwargs.get("check"), "Should use check=False to handle exit codes"

    # Reset for next test
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)
    mock_run.reset_mock()

    # Test 2: Command with nelson args
    orchestrator.execute_task(
        "PRD-001",
        "Implement feature",
        "high",
        nelson_args=["--max-iterations", "100", "--model", "opus"]
    )

    args = mock_run.call_args[0][0]
    assert args[0] == "nelson", "First argument should be 'nelson' command"
    assert args[1] == "Implement feature", "Second argument should be the prompt"
    assert args[2] == "--max-iterations", "Nelson args should follow prompt"
    assert args[3] == "100"
    assert args[4] == "--model"
    assert args[5] == "opus"
    assert len(args) == 6, "Should have nelson, prompt, and 4 arg components"

    # Reset for next test
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)
    mock_run.reset_mock()

    # Test 3: Command with resume context (no nelson args)
    # Set up task state with resume context
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    task_state.start("test-run-001", "feature/PRD-001-test-task")
    task_state.resume_context = "API keys now in .env file"
    orchestrator.state_manager.save_task_state(task_state)

    # Reset PRD file to pending so execute_task will run
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    mock_run.reset_mock()

    # Now execute with resume context
    orchestrator.execute_task(
        "PRD-001",
        "Implement feature",
        "high"
    )

    args = mock_run.call_args[0][0]
    assert args[0] == "nelson", "First argument should be 'nelson' command"
    # Resume context should be prepended to prompt
    assert "RESUME CONTEXT:" in args[1], "Prompt should contain resume context prefix"
    assert "API keys now in .env file" in args[1], "Resume context should be in prompt"
    assert "Implement feature" in args[1], "Original prompt should follow resume context"
    assert len(args) == 2, "Should only have nelson and modified prompt"

    # Reset for next test
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)
    mock_run.reset_mock()

    # Test 4: Command with both resume context AND nelson args
    # Set up task state with resume context
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    task_state.start("test-run-002", "feature/PRD-001-test-task")
    task_state.resume_context = "Dependencies installed: requests, pytest"
    orchestrator.state_manager.save_task_state(task_state)

    # Reset PRD file to pending
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    mock_run.reset_mock()

    orchestrator.execute_task(
        "PRD-001",
        "Implement feature",
        "high",
        nelson_args=["--max-iterations", "50"]
    )

    args = mock_run.call_args[0][0]
    assert args[0] == "nelson", "First argument should be 'nelson' command"
    assert "RESUME CONTEXT:" in args[1], "Prompt should contain resume context"
    assert "Dependencies installed" in args[1], "Resume context should be in prompt"
    assert "Implement feature" in args[1], "Original prompt should follow context"
    assert args[2] == "--max-iterations", "Nelson args should follow modified prompt"
    assert args[3] == "50"
    assert len(args) == 4, "Should have nelson, modified prompt, and nelson args"


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
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

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


@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_when_nelson_state_file_missing(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that task completes successfully even when Nelson state file doesn't exist."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return False (state file doesn't exist)
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = False
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should still succeed even without Nelson state
    assert success is True

    # Task state should be completed but with no cost/iteration data
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cost_usd == 0.0  # No cost extracted
    assert task_state.iterations == 0  # No iterations extracted


@patch("nelson.state.NelsonState.load")
@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_handles_corrupted_nelson_state(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    mock_load: Mock,
    orchestrator: PRDOrchestrator,
    capsys,
):
    """Test that cost extraction handles corrupted Nelson state gracefully."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Mock NelsonState.load() to raise JSONDecodeError
    import json
    mock_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should still succeed even with corrupted state
    assert success is True

    # Verify warning was printed
    captured = capsys.readouterr()
    assert "Warning: Could not read Nelson state:" in captured.out

    # Task state should be completed but with no cost data
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cost_usd == 0.0  # No cost extracted


@patch("nelson.state.NelsonState.load")
@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_handles_missing_fields_in_nelson_state(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    mock_load: Mock,
    orchestrator: PRDOrchestrator,
    capsys,
):
    """Test that cost extraction handles Nelson state with missing fields."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Mock Nelson state with missing cost_usd attribute
    mock_nelson_state = MagicMock()
    del mock_nelson_state.cost_usd  # Remove the attribute
    mock_load.return_value = mock_nelson_state

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should still succeed even with incomplete state
    assert success is True

    # Verify warning was printed
    captured = capsys.readouterr()
    assert "Warning: Could not read Nelson state:" in captured.out

    # Task state should be completed but with no cost data
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cost_usd == 0.0  # No cost extracted


@patch("nelson.state.NelsonState.load")
@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_with_zero_cost(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    mock_load: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that cost extraction correctly handles zero cost from Nelson."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Mock Nelson state with zero cost (valid scenario for cached responses)
    mock_nelson_state = MagicMock()
    mock_nelson_state.cost_usd = 0.0
    mock_nelson_state.total_iterations = 3
    mock_nelson_state.current_phase = 2
    mock_nelson_state.phase_name = "IMPLEMENT"
    mock_load.return_value = mock_nelson_state

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should succeed
    assert success is True

    # Verify zero cost was correctly extracted
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.cost_usd == 0.0
    assert task_state.iterations == 3
    assert task_state.status == TaskStatus.COMPLETED


@patch("nelson.state.NelsonState.load")
@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_with_high_cost_values(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    mock_load: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that cost extraction handles large cost values correctly."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Mock Nelson state with high cost (100+ iterations, expensive task)
    mock_nelson_state = MagicMock()
    mock_nelson_state.cost_usd = 47.85  # High cost
    mock_nelson_state.total_iterations = 150
    mock_nelson_state.current_phase = 6
    mock_nelson_state.phase_name = "COMMIT"
    mock_load.return_value = mock_nelson_state

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should succeed
    assert success is True

    # Verify high cost was correctly extracted
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.cost_usd == 47.85
    assert task_state.iterations == 150
    assert task_state.phase == 6
    assert task_state.phase_name == "COMMIT"
    assert task_state.status == TaskStatus.COMPLETED


@patch("nelson.state.NelsonState.load")
@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
def test_cost_extraction_with_partial_phase_data(
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    mock_load: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that cost extraction handles partial phase data (None values)."""
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test-task"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    # Mock Nelson state with None phase (edge case)
    mock_nelson_state = MagicMock()
    mock_nelson_state.cost_usd = 2.50
    mock_nelson_state.total_iterations = 10
    mock_nelson_state.current_phase = None  # Missing phase
    mock_nelson_state.phase_name = "PLAN"
    mock_load.return_value = mock_nelson_state

    # Execute task
    success = orchestrator.execute_task("PRD-001", "Implement feature", "high")

    # Task should succeed
    assert success is True

    # Verify cost and iterations were extracted but phase update was skipped
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement feature", "high"
    )
    assert task_state.cost_usd == 2.50
    assert task_state.iterations == 10
    # Phase should remain at default (not updated due to None)
    assert task_state.phase is None
    assert task_state.status == TaskStatus.COMPLETED


@patch("nelson.prd_orchestrator.PRDOrchestrator.execute_task")
def test_execute_all_pending_runs_all_tasks(
    mock_execute: Mock,
    orchestrator: PRDOrchestrator,
):
    """Test that execute_all_pending runs all pending tasks."""
    # Track which tasks have been executed to simulate completion
    executed_tasks = set()

    def execute_side_effect(task_id, *args, **kwargs):
        # Mark task as executed
        executed_tasks.add(task_id)
        # Actually update the PRD file to mark as complete
        orchestrator.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)
        return True

    mock_execute.side_effect = execute_side_effect

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
    call_count = [0]

    def execute_side_effect(task_id, *args, **kwargs):
        call_count[0] += 1
        success = call_count[0] != 2  # Fail on second call
        if success:
            # Update PRD file to mark as complete
            orchestrator.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)
        return success

    mock_execute.side_effect = execute_side_effect

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
    call_count = [0]

    def execute_side_effect(task_id, *args, **kwargs):
        call_count[0] += 1
        success = call_count[0] != 2  # Fail on second call
        if success:
            # Update PRD file to mark as complete
            orchestrator.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)
        return success

    mock_execute.side_effect = execute_side_effect

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
    def execute_side_effect(task_id, *args, **kwargs):
        # Update PRD file to mark as complete
        orchestrator.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)
        return True

    mock_execute.side_effect = execute_side_effect

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




def test_full_prd_workflow_integration(tmp_path: Path):
    """Integration test for complete PRD orchestration workflow.

    This test simulates a full end-to-end workflow with mocked Nelson execution:
    1. Parse PRD with multiple priority tasks
    2. Execute tasks in priority order (High -> Medium -> Low)
    3. Verify branch creation and state tracking
    4. Test task blocking and unblocking with resume context
    5. Verify resume context prepending to Nelson prompt
    """
    # Create comprehensive test PRD
    prd_file = tmp_path / "integration_test.md"
    prd_file.write_text("""# Integration Test PRD

## High Priority
- [ ] PRD-001 Add user authentication system
- [ ] PRD-002 Create REST API endpoints

## Medium Priority
- [ ] PRD-003 Add email notification service

## Low Priority
- [ ] PRD-004 Add dark mode toggle
""")

    # Setup directories
    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    # Verify initial state
    assert len(orchestrator.tasks) == 4
    summary = orchestrator.get_status_summary()
    assert summary["total_tasks"] == 4
    assert summary["pending"] == 4

    # Mock git branch and Nelson operations
    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_ensure_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_nelson_run:

        # Setup branch mock to return branch name
        mock_ensure_branch.return_value = "feature/PRD-001-add-user-authentication"

        # Setup Nelson mock for successful execution
        mock_nelson_run.return_value = Mock(returncode=0)

        # Test 1: Execute first high-priority task
        next_task = orchestrator.get_next_pending_task()
        assert next_task is not None
        task_id, task_text, priority = next_task
        assert task_id == "PRD-001"
        assert priority == "high"

        success = orchestrator.execute_task(task_id, task_text, priority)
        assert success is True

        # Verify task state was saved and completed
        task_state = orchestrator.state_manager.load_task_state(task_id, task_text, priority)
        assert task_state.status.value == "completed"
        assert task_state.branch == "feature/PRD-001-add-user-authentication"

        # Verify PRD file updated to completed
        prd_content = prd_file.read_text()
        assert "[x] PRD-001" in prd_content

        # Test 2: Execute and block a medium-priority task
        # First we need to start the task to create its state
        task_state_003 = orchestrator.state_manager.load_task_state(
            "PRD-003", "Add email notification service", "medium"
        )
        orchestrator.state_manager.save_task_state(task_state_003)

        # Now block it
        block_success = orchestrator.block_task("PRD-003", "Waiting for API keys")
        assert block_success is True

        blocked_state = orchestrator.state_manager.load_task_state(
            "PRD-003", "Add email notification service", "medium"
        )
        assert blocked_state.status.value == "blocked"
        assert blocked_state.blocking_reason == "Waiting for API keys"

        # Verify PRD shows blocked status
        prd_content = prd_file.read_text()
        assert "[!] PRD-003" in prd_content

        # Test 3: Verify blocked task is skipped
        next_task = orchestrator.get_next_pending_task()
        task_id3, _, _ = next_task
        assert task_id3 != "PRD-003"  # Should skip blocked task
        assert task_id3 == "PRD-002"  # Should get next high priority

        # Test 4: Unblock with resume context
        resume_context = "API keys added to .env as EMAIL_API_KEY"
        unblock_success = orchestrator.unblock_task("PRD-003", resume_context)
        assert unblock_success is True

        unblocked_state = orchestrator.state_manager.load_task_state(
            "PRD-003", "Add email notification service", "medium"
        )
        assert unblocked_state.resume_context == resume_context
        assert unblocked_state.status.value == "pending"

        # Verify PRD file updated to pending
        prd_content = prd_file.read_text()
        assert "[ ] PRD-003" in prd_content

        # Test 5: Resume task and verify context prepending
        mock_nelson_run.reset_mock()
        resume_success = orchestrator.resume_task("PRD-003")
        assert resume_success is True

        # Verify resume context was prepended to Nelson prompt
        nelson_call = mock_nelson_run.call_args_list[0]
        nelson_cmd = nelson_call[0][0]
        prompt_arg = nelson_cmd[1]  # Second arg is the prompt
        assert "RESUME CONTEXT:" in prompt_arg
        assert "API keys added to .env" in prompt_arg
        assert "Add email notification service" in prompt_arg

        # Test 6: Verify final summary
        summary = orchestrator.get_status_summary()
        assert summary["completed"] == 2  # PRD-001, PRD-003


def test_full_workflow_with_failure_handling(tmp_path: Path):
    """Integration test for workflow with task failure scenarios."""
    prd_file = tmp_path / "failure_test.md"
    prd_file.write_text("""# Failure Test PRD

## High Priority
- [ ] PRD-001 Task that will succeed
- [ ] PRD-002 Task that will fail
- [ ] PRD-003 Task after failure
""")

    prd_dir = tmp_path / ".nelson/prd"
    orchestrator = PRDOrchestrator(prd_file, prd_dir)

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_ensure_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_nelson_run:

        # Setup branch mock
        mock_ensure_branch.return_value = "feature/PRD-001-task-that-will-succeed"

        # First task succeeds
        mock_nelson_run.return_value = Mock(returncode=0)
        success1 = orchestrator.execute_task("PRD-001", "Task that will succeed", "high")
        assert success1 is True

        # Second task fails
        mock_nelson_run.return_value = Mock(returncode=1)
        success2 = orchestrator.execute_task("PRD-002", "Task that will fail", "high")
        assert success2 is False

        # Verify failed task state
        failed_state = orchestrator.state_manager.load_task_state(
            "PRD-002", "Task that will fail", "high"
        )
        assert failed_state.status.value == "failed"  # Marked as failed

        # Verify PRD shows in-progress (not completed) - orchestrator marks as in_progress
        prd_content = prd_file.read_text()
        assert "[~] PRD-002" in prd_content

        # Summary should show failed task
        summary = orchestrator.get_status_summary()
        assert summary["failed"] == 1  # PRD-002 (failed)

        # Third task can still execute
        mock_nelson_run.return_value = Mock(returncode=0)
        success3 = orchestrator.execute_task("PRD-003", "Task after failure", "high")
        assert success3 is True

        # Verify final summary
        final_summary = orchestrator.get_status_summary()
        assert final_summary["completed"] == 2  # PRD-001, PRD-003
        assert final_summary["failed"] == 1  # PRD-002


def test_concurrent_state_file_read_write(tmp_path: Path):
    """Test that concurrent orchestrators can read shared state without corruption.

    Simulates scenario where two nelson-prd processes are reading the same
    PRD state directory. Each orchestrator should be able to read without
    interfering with the other.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
- [ ] PRD-003 Third task
""")

    prd_dir = tmp_path / ".nelson/prd"

    # Create first orchestrator and execute a task
    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-first-task"
        mock_run.return_value = Mock(returncode=0)

        # Orchestrator 1 completes PRD-001
        orchestrator1.execute_task("PRD-001", "First task", "high")

        # Create second orchestrator (simulates concurrent process)
        # This should read the updated state showing PRD-001 is complete
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

        # Verify orchestrator2 sees the completed task
        summary = orchestrator2.get_status_summary()
        assert summary["completed"] == 1

        # Verify orchestrator2 can read task state from orchestrator1
        task_info = orchestrator2.get_task_info("PRD-001")
        assert task_info is not None
        assert task_info["status"] == "completed"

        # Verify orchestrator2 gets a different pending task
        next_task = orchestrator2.get_next_pending_task()
        assert next_task is not None
        task_id, _, _ = next_task
        assert task_id != "PRD-001"  # Should skip completed task
        assert task_id == "PRD-002"  # Should get next pending


def test_concurrent_prd_file_modifications(tmp_path: Path):
    """Test that concurrent PRD file updates don't corrupt task statuses.

    Simulates scenario where one process is updating PRD file while another
    is reading it. Parser should handle this gracefully by re-parsing.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"
    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-first-task"
        mock_run.return_value = Mock(returncode=0)

        # Orchestrator 1 updates PRD-001 to in-progress
        orchestrator1.parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)

        # Simulate concurrent process reading the file
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

        # Verify orchestrator2 sees the in-progress task
        tasks = orchestrator2.parser.parse()
        task1 = next(t for t in tasks if t.task_id == "PRD-001")
        assert task1.status == PRDTaskStatus.IN_PROGRESS

        # Verify orchestrator2 skips in-progress task
        next_task = orchestrator2.get_next_pending_task()
        assert next_task is not None
        task_id, _, _ = next_task
        assert task_id == "PRD-002"  # Should skip in-progress task


def test_concurrent_task_double_execution_prevention(tmp_path: Path):
    """Test that task status markers prevent double-execution.

    When task is marked in-progress, a concurrent process should not
    pick it up for execution.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-first-task"
        mock_run.return_value = Mock(returncode=0)

        # Orchestrator 1 starts execution
        orchestrator1 = PRDOrchestrator(prd_file, prd_dir)

        # Get next task
        next_task = orchestrator1.get_next_pending_task()
        assert next_task is not None
        task_id1, task_text1, priority1 = next_task
        assert task_id1 == "PRD-001"

        # Mark as in-progress (happens at start of execute_task)
        orchestrator1.parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)

        # Before task completes, simulate concurrent process starting
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

        # Orchestrator 2 should NOT pick up PRD-001 (it's in-progress)
        next_task2 = orchestrator2.get_next_pending_task()
        assert next_task2 is not None
        task_id2, _, _ = next_task2
        assert task_id2 == "PRD-002"  # Should get different task

        # Both orchestrators see consistent state
        orchestrator1.get_status_summary()
        orchestrator2.get_status_summary()

        # Both should see PRD-001 as in-progress (via re-parsing)
        orchestrator1.tasks = orchestrator1.parser.parse()
        orchestrator2.tasks = orchestrator2.parser.parse()

        task1_orch1 = next(t for t in orchestrator1.tasks if t.task_id == "PRD-001")
        task1_orch2 = next(t for t in orchestrator2.tasks if t.task_id == "PRD-001")

        assert task1_orch1.status == PRDTaskStatus.IN_PROGRESS
        assert task1_orch2.status == PRDTaskStatus.IN_PROGRESS


def test_concurrent_blocked_task_handling(tmp_path: Path):
    """Test that blocked tasks are consistently skipped by concurrent processes."""
    # Create PRD with blocked task
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [!] PRD-001 Blocked task (blocked: waiting for API)
- [ ] PRD-002 Available task
- [ ] PRD-003 Another task
""")

    prd_dir = tmp_path / ".nelson/prd"

    # Both orchestrators should skip the blocked task
    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)
    orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

    # Both should get PRD-002 as next task (skipping blocked PRD-001)
    next1 = orchestrator1.get_next_pending_task()
    next2 = orchestrator2.get_next_pending_task()

    assert next1 is not None
    assert next2 is not None

    task_id1, _, _ = next1
    task_id2, _, _ = next2

    assert task_id1 == "PRD-002"
    assert task_id2 == "PRD-002"

    # Both should recognize PRD-001 as blocked
    orchestrator1.get_task_info("PRD-001")
    orchestrator2.get_task_info("PRD-001")

    # Tasks without state files will show as pending by default
    # The PRD file parser shows blocked, state shows pending for new tasks
    tasks1 = orchestrator1.parser.parse()
    tasks2 = orchestrator2.parser.parse()

    task1_orch1 = next(t for t in tasks1 if t.task_id == "PRD-001")
    task1_orch2 = next(t for t in tasks2 if t.task_id == "PRD-001")

    assert task1_orch1.status == PRDTaskStatus.BLOCKED
    assert task1_orch2.status == PRDTaskStatus.BLOCKED


def test_concurrent_cost_tracking_isolation(tmp_path: Path):
    """Test that cost tracking remains accurate with concurrent updates.

    Each task maintains its own cost state, so concurrent execution
    should not corrupt individual task costs.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"
    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-first-task"
        mock_run.return_value = Mock(returncode=0)

        # Orchestrator 1 completes PRD-001 - cost will be 0 since no Nelson state file
        orchestrator1.execute_task("PRD-001", "First task", "high")

        # Manually set cost to simulate what would happen with real Nelson execution
        task1_state = orchestrator1.state_manager.load_task_state("PRD-001", "First task", "high")
        task1_state.update_cost(1.50)
        task1_state.increment_iterations(10)
        orchestrator1.state_manager.save_task_state(task1_state)

        # Create second orchestrator
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

        # Orchestrator 2 completes PRD-002
        orchestrator2.execute_task("PRD-002", "Second task", "high")

        # Manually set cost for task 2
        task2_state = orchestrator2.state_manager.load_task_state("PRD-002", "Second task", "high")
        task2_state.update_cost(2.75)
        task2_state.increment_iterations(15)
        orchestrator2.state_manager.save_task_state(task2_state)

        # Verify each task has its own cost
        task1_info = orchestrator2.get_task_info("PRD-001")
        task2_info = orchestrator2.get_task_info("PRD-002")

        assert task1_info["cost_usd"] == 1.50
        assert task2_info["cost_usd"] == 2.75

        # Verify total cost is sum of both
        summary = orchestrator2.get_status_summary()
        assert summary["total_cost"] == 1.50 + 2.75


def test_concurrent_backup_file_creation(tmp_path: Path):
    """Test that concurrent backup creation doesn't corrupt files.

    Multiple processes updating the PRD file should each create their own
    timestamped backups without interfering.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"
    backup_dir = prd_dir / "backups"

    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)
    orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run"):

        mock_branch.return_value = "feature/PRD-001-first-task"

        # Both orchestrators update task status (creates backups)
        orchestrator1.parser.update_task_status("PRD-001", PRDTaskStatus.IN_PROGRESS)
        orchestrator2.parser.update_task_status("PRD-002", PRDTaskStatus.IN_PROGRESS)

        # Verify backup directory exists
        assert backup_dir.exists()

        # Verify backups were created
        backups = list(backup_dir.glob("concurrent-*.md"))
        assert len(backups) >= 2  # At least 2 backups from both updates

        # Verify backups are readable and not corrupted
        for backup in backups:
            content = backup.read_text()
            assert "PRD-001" in content
            assert "PRD-002" in content
            assert "## High Priority" in content


def test_concurrent_state_persistence_consistency(tmp_path: Path):
    """Test that state persistence remains consistent across concurrent processes.

    When multiple processes save state, the last write should win, and
    state should remain valid JSON.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"

    orchestrator1 = PRDOrchestrator(prd_file, prd_dir)
    orchestrator2 = PRDOrchestrator(prd_file, prd_dir)

    # Both orchestrators modify state
    orchestrator1.state_manager.prd_state.update_task_status("PRD-001", TaskStatus.IN_PROGRESS)
    orchestrator1.state_manager.save_prd_state()

    orchestrator2.state_manager.prd_state.update_task_status("PRD-002", TaskStatus.IN_PROGRESS)
    orchestrator2.state_manager.save_prd_state()

    # Create third orchestrator to verify state is valid
    orchestrator3 = PRDOrchestrator(prd_file, prd_dir)

    # Verify state is readable and valid
    prd_state = orchestrator3.state_manager.prd_state

    # State should be valid (last write wins)
    assert prd_state is not None
    assert "PRD-001" in prd_state.task_mapping
    assert "PRD-002" in prd_state.task_mapping

    # Verify state file is valid JSON
    state_file = prd_dir / "prd-state.json"
    assert state_file.exists()

    import json
    with open(state_file) as f:
        state_data = json.load(f)

    assert "task_mapping" in state_data
    assert "tasks" in state_data


def test_concurrent_branch_creation_same_task(tmp_path: Path):
    """Test that concurrent branch creation for same task is idempotent.

    If two processes try to create the same branch, git should handle it
    gracefully (branch already exists is not a fatal error).
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
""")

    prd_dir = tmp_path / ".nelson/prd"


    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_ensure_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        # First call succeeds
        mock_ensure_branch.return_value = "feature/PRD-001-first-task"
        mock_run.return_value = Mock(returncode=0)

        orchestrator1 = PRDOrchestrator(prd_file, prd_dir)
        success1 = orchestrator1.execute_task("PRD-001", "First task", "high")
        assert success1 is True

        # Reset task status for retry
        orchestrator1.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

        # Second call to same branch (simulates concurrent creation)
        # Should return existing branch name (idempotent)
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)
        success2 = orchestrator2.execute_task("PRD-001", "First task", "high")
        assert success2 is True

        # Both calls should result in same branch
        assert mock_ensure_branch.call_count == 2
        all_calls = mock_ensure_branch.call_args_list
        assert all_calls[0][0] == ("PRD-001", "First task")
        assert all_calls[1][0] == ("PRD-001", "First task")


def test_concurrent_execution_with_failures(tmp_path: Path):
    """Test that concurrent execution handles failures independently.

    If one process has a task failure, it shouldn't affect the other
    process's task execution.
    """
    # Create PRD file
    prd_file = tmp_path / "concurrent.md"
    prd_file.write_text("""## High Priority
- [ ] PRD-001 First task
- [ ] PRD-002 Second task
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-first-task"

        # Orchestrator 1 - task succeeds
        orchestrator1 = PRDOrchestrator(prd_file, prd_dir)
        mock_run.return_value = Mock(returncode=0)
        success1 = orchestrator1.execute_task("PRD-001", "First task", "high")
        assert success1 is True

        # Orchestrator 2 - task fails
        orchestrator2 = PRDOrchestrator(prd_file, prd_dir)
        mock_run.return_value = Mock(returncode=1)
        success2 = orchestrator2.execute_task("PRD-002", "Second task", "high")
        assert success2 is False

        # Verify independent state
        # Create fresh orchestrator to check final state
        orchestrator3 = PRDOrchestrator(prd_file, prd_dir)

        task1_info = orchestrator3.get_task_info("PRD-001")
        task2_info = orchestrator3.get_task_info("PRD-002")

        assert task1_info["status"] == "completed"
        assert task2_info["status"] == "failed"

        # Verify summary reflects both outcomes
        summary = orchestrator3.get_status_summary()
        assert summary["completed"] == 1
        assert summary["failed"] == 1


def test_resume_context_prepending_format(tmp_path: Path):
    """Test that resume context is prepended with correct format.

    Format: 'RESUME CONTEXT: {context}\\n\\n{prompt}'
    """
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Implement authentication
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Set resume context
        task_state = orchestrator.state_manager.load_task_state(
            "PRD-001", "Implement authentication", "high"
        )
        task_state.resume_context = "API keys have been added to .env file"
        orchestrator.state_manager.save_task_state(task_state)

        # Execute task
        orchestrator.execute_task("PRD-001", "Implement authentication", "high")

        # Verify exact format
        args = mock_run.call_args[0][0]
        prompt = args[1]

        # Check exact format with newlines
        expected_start = (
            "RESUME CONTEXT: API keys have been added to .env file\n\n"
            "Implement authentication"
        )
        assert prompt == expected_start, f"Expected: {expected_start!r}, Got: {prompt!r}"


def test_resume_context_prepending_order(tmp_path: Path):
    """Test that resume context appears BEFORE task text (prepending, not appending)."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Create user profile management
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Set resume context
        task_state = orchestrator.state_manager.load_task_state(
            "PRD-001", "Create user profile management", "high"
        )
        task_state.resume_context = "Database schema has been updated with users table"
        orchestrator.state_manager.save_task_state(task_state)

        # Execute task
        orchestrator.execute_task("PRD-001", "Create user profile management", "high")

        # Verify order
        args = mock_run.call_args[0][0]
        prompt = args[1]

        # Resume context should come before task text
        resume_idx = prompt.find("RESUME CONTEXT:")
        task_idx = prompt.find("Create user profile management")

        assert resume_idx != -1, "Resume context not found in prompt"
        assert task_idx != -1, "Task text not found in prompt"
        assert resume_idx < task_idx, "Resume context should appear BEFORE task text"


def test_resume_context_with_custom_prompt(tmp_path: Path):
    """Test that resume context is prepended to custom prompts as well."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Add payment integration
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Set resume context
        task_state = orchestrator.state_manager.load_task_state(
            "PRD-001", "Add payment integration", "high"
        )
        task_state.resume_context = "Stripe API credentials configured"
        orchestrator.state_manager.save_task_state(task_state)

        # Execute task with custom prompt
        custom_prompt = "Detailed instructions for payment integration with Stripe"
        orchestrator.execute_task(
            "PRD-001", "Add payment integration", "high", prompt=custom_prompt
        )

        # Verify resume context prepended to custom prompt
        args = mock_run.call_args[0][0]
        prompt = args[1]

        expected = (
            "RESUME CONTEXT: Stripe API credentials configured\n\n"
            "Detailed instructions for payment integration with Stripe"
        )
        assert prompt == expected


def test_no_resume_context_prepending_when_none(tmp_path: Path):
    """Test that no prepending occurs when resume_context is None."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Implement logging
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Execute task without setting resume context (defaults to None)
        orchestrator.execute_task("PRD-001", "Implement logging", "high")

        # Verify no prepending
        args = mock_run.call_args[0][0]
        prompt = args[1]

        # Should just be task text, no RESUME CONTEXT prefix
        assert prompt == "Implement logging"
        assert "RESUME CONTEXT:" not in prompt


def test_resume_context_with_special_characters(tmp_path: Path):
    """Test resume context prepending with special characters (newlines, quotes, etc)."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Setup CI/CD pipeline
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Set resume context with special characters
        task_state = orchestrator.state_manager.load_task_state(
            "PRD-001", "Setup CI/CD pipeline", "high"
        )
        # Context with newlines, quotes, and special chars
        task_state.resume_context = (
            'GitHub Actions configured:\n- API_KEY="secret123"\n- '
            "DEPLOY_ENV='production'"
        )
        orchestrator.state_manager.save_task_state(task_state)

        # Execute task
        orchestrator.execute_task("PRD-001", "Setup CI/CD pipeline", "high")

        # Verify special characters preserved
        args = mock_run.call_args[0][0]
        prompt = args[1]

        # Check that special characters are preserved
        assert 'GitHub Actions configured:\n- API_KEY="secret123"' in prompt
        assert "DEPLOY_ENV='production'" in prompt
        assert prompt.startswith("RESUME CONTEXT:")
        assert "Setup CI/CD pipeline" in prompt


def test_resume_context_with_long_text(tmp_path: Path):
    """Test resume context prepending with long text (hundreds of characters)."""
    prd_file = tmp_path / "test.md"
    prd_file.write_text("""# Test PRD

## High Priority
- [ ] PRD-001 Implement search functionality
""")

    prd_dir = tmp_path / ".nelson/prd"

    with patch("nelson.prd_orchestrator.ensure_branch_for_task") as mock_branch, \
         patch("nelson.prd_orchestrator.subprocess.run") as mock_run:

        mock_branch.return_value = "feature/PRD-001-test"
        mock_run.return_value = Mock(returncode=0)

        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Set very long resume context
        task_state = orchestrator.state_manager.load_task_state(
            "PRD-001", "Implement search functionality", "high"
        )
        long_context = (
            "The search infrastructure has been set up: "
            "1) Elasticsearch cluster with 3 nodes. "
            "2) Search indexer service as background worker. "
            "3) API endpoints at /api/v1/search with pagination. "
            "4) Frontend search UI with autocomplete and filters. "
            "5) Performance: sub-100ms response times for 95th percentile."
        )
        task_state.resume_context = long_context
        orchestrator.state_manager.save_task_state(task_state)

        # Execute task
        orchestrator.execute_task("PRD-001", "Implement search functionality", "high")

        # Verify long context preserved
        args = mock_run.call_args[0][0]
        prompt = args[1]

        # Full long context should be present
        assert long_context in prompt
        assert prompt.startswith("RESUME CONTEXT:")
        # Verify task text comes after
        assert prompt.endswith("Implement search functionality")
        # Verify double newline separator
        assert f"RESUME CONTEXT: {long_context}\n\nImplement search functionality" == prompt


@patch("nelson.prd_orchestrator.Path")
@patch("nelson.prd_orchestrator.ensure_branch_for_task")
@patch("nelson.prd_orchestrator.subprocess.run")
@patch("nelson.prd_orchestrator.NelsonState.load")
def test_cost_accumulation_across_multiple_runs(
    mock_load: Mock,
    mock_run: Mock,
    mock_ensure_branch: Mock,
    mock_path: Mock,
    temp_prd_file: Path,
    temp_prd_dir: Path,
):
    """Test that costs accumulate across multiple runs of the same task.

    Simulates scenario:
    1. Task runs, incurs $1.50 cost
    2. Task is blocked/resumed, incurs $2.25 more cost
    3. Task completes, incurs $0.75 more cost
    4. Total cost should be $4.50 (accumulated, not replaced)
    """
    # Setup mocks
    mock_ensure_branch.return_value = "feature/PRD-001-test"
    mock_run.return_value = Mock(returncode=0)

    # Mock Path.exists() to return True for Nelson state files
    mock_nelson_state_path = MagicMock()
    mock_nelson_state_path.exists.return_value = True
    mock_path.return_value.__truediv__.return_value.__truediv__.return_value = (
        mock_nelson_state_path
    )

    orchestrator = PRDOrchestrator(temp_prd_file, temp_prd_dir)

    # Run 1: Task incurs $1.50 cost
    mock_nelson_state_1 = Mock()
    mock_nelson_state_1.cost_usd = 1.50
    mock_nelson_state_1.total_iterations = 10
    mock_nelson_state_1.current_phase = 2
    mock_nelson_state_1.phase_name = "IMPLEMENT"
    mock_load.return_value = mock_nelson_state_1

    orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify first run cost
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.cost_usd == 1.50
    assert task_state.iterations == 10

    # Update PRD file to pending (simulate resume scenario)
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    # Run 2: Task resumes, incurs $2.25 more cost
    mock_nelson_state_2 = Mock()
    mock_nelson_state_2.cost_usd = 2.25
    mock_nelson_state_2.total_iterations = 15
    mock_nelson_state_2.current_phase = 3
    mock_nelson_state_2.phase_name = "REVIEW"
    mock_load.return_value = mock_nelson_state_2

    orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify accumulated cost after second run
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.cost_usd == 3.75  # 1.50 + 2.25
    assert task_state.iterations == 25  # 10 + 15

    # Update PRD file to pending again
    orchestrator.parser.update_task_status("PRD-001", PRDTaskStatus.PENDING)

    # Run 3: Task completes, incurs $0.75 more cost
    mock_nelson_state_3 = Mock()
    mock_nelson_state_3.cost_usd = 0.75
    mock_nelson_state_3.total_iterations = 5
    mock_nelson_state_3.current_phase = 6
    mock_nelson_state_3.phase_name = "COMMIT"
    mock_load.return_value = mock_nelson_state_3

    orchestrator.execute_task("PRD-001", "Implement user authentication", "high")

    # Verify final accumulated cost
    task_state = orchestrator.state_manager.load_task_state(
        "PRD-001", "Implement user authentication", "high"
    )
    assert task_state.cost_usd == 4.50  # 1.50 + 2.25 + 0.75
    assert task_state.iterations == 30  # 10 + 15 + 5


