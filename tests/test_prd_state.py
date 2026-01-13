"""Tests for prd_state module."""

from pathlib import Path

import pytest

from nelson.prd_state import PRDState, PRDStateManager
from nelson.prd_task_state import TaskState, TaskStatus


def test_prd_state_initialization():
    """Test PRDState initialization."""
    state = PRDState(prd_file="requirements.md")

    assert state.prd_file == "requirements.md"
    assert state.total_cost_usd == 0.0
    assert state.task_mapping == {}
    assert state.tasks == {}
    assert state.current_task_id is None
    assert state.completed_count == 0
    assert state.in_progress_count == 0
    assert state.blocked_count == 0
    assert state.pending_count == 0
    assert state.failed_count == 0
    assert state.started_at is not None
    assert state.updated_at is not None


def test_prd_state_add_task():
    """Test adding a task to PRD state."""
    state = PRDState(prd_file="test.md")

    state.add_task("PRD-001", "Add authentication", "high", 5)

    assert "PRD-001" in state.task_mapping
    assert state.task_mapping["PRD-001"]["original_text"] == "Add authentication"
    assert state.task_mapping["PRD-001"]["priority"] == "high"
    assert state.task_mapping["PRD-001"]["line_number"] == 5

    assert "PRD-001" in state.tasks
    assert state.tasks["PRD-001"]["status"] == "pending"
    assert state.tasks["PRD-001"]["cost_usd"] == 0.0
    assert state.pending_count == 1


def test_prd_state_update_task_status():
    """Test updating task status."""
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Test task", "high", 1)

    # Start task
    state.update_task_status("PRD-001", TaskStatus.IN_PROGRESS)

    assert state.tasks["PRD-001"]["status"] == "in_progress"
    assert state.pending_count == 0
    assert state.in_progress_count == 1

    # Complete task
    state.update_task_status("PRD-001", TaskStatus.COMPLETED)

    assert state.tasks["PRD-001"]["status"] == "completed"
    assert state.in_progress_count == 0
    assert state.completed_count == 1


def test_prd_state_update_task_cost():
    """Test updating task cost."""
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Test task", "high", 1)

    state.update_task_cost("PRD-001", 2.5)

    assert state.tasks["PRD-001"]["cost_usd"] == 2.5
    assert state.total_cost_usd == 2.5

    state.update_task_cost("PRD-001", 3.0)

    assert state.tasks["PRD-001"]["cost_usd"] == 3.0
    assert state.total_cost_usd == 3.0


def test_prd_state_set_current_task():
    """Test setting current task."""
    state = PRDState(prd_file="test.md")

    state.set_current_task("PRD-001")
    assert state.current_task_id == "PRD-001"

    state.set_current_task(None)
    assert state.current_task_id is None


def test_prd_state_get_task_ids_by_status():
    """Test getting task IDs by status."""
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Task 1", "high", 1)
    state.add_task("PRD-002", "Task 2", "high", 2)
    state.add_task("PRD-003", "Task 3", "medium", 3)

    state.update_task_status("PRD-001", TaskStatus.IN_PROGRESS)
    state.update_task_status("PRD-002", TaskStatus.COMPLETED)

    pending = state.get_task_ids_by_status(TaskStatus.PENDING)
    assert "PRD-003" in pending

    in_progress = state.get_task_ids_by_status(TaskStatus.IN_PROGRESS)
    assert "PRD-001" in in_progress

    completed = state.get_task_ids_by_status(TaskStatus.COMPLETED)
    assert "PRD-002" in completed


def test_prd_state_get_task_ids_by_priority():
    """Test getting task IDs by priority."""
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Task 1", "high", 1)
    state.add_task("PRD-002", "Task 2", "high", 2)
    state.add_task("PRD-003", "Task 3", "medium", 3)

    high_tasks = state.get_task_ids_by_priority("high")
    assert len(high_tasks) == 2
    assert "PRD-001" in high_tasks
    assert "PRD-002" in high_tasks

    medium_tasks = state.get_task_ids_by_priority("medium")
    assert len(medium_tasks) == 1
    assert "PRD-003" in medium_tasks


def test_prd_state_get_task_ids_by_priority_and_status():
    """Test getting task IDs by priority and status."""
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Task 1", "high", 1)
    state.add_task("PRD-002", "Task 2", "high", 2)
    state.add_task("PRD-003", "Task 3", "high", 3)

    state.update_task_status("PRD-002", TaskStatus.COMPLETED)

    high_pending = state.get_task_ids_by_priority("high", TaskStatus.PENDING)
    assert len(high_pending) == 2
    assert "PRD-001" in high_pending
    assert "PRD-003" in high_pending


def test_prd_state_save_load(tmp_path: Path):
    """Test saving and loading PRD state."""
    state_file = tmp_path / "prd-state.json"

    # Create and save state
    state = PRDState(prd_file="test.md")
    state.add_task("PRD-001", "Task 1", "high", 1)
    state.add_task("PRD-002", "Task 2", "medium", 2)
    state.total_cost_usd = 5.5
    state.save(state_file)

    # Load state
    loaded = PRDState.load(state_file)

    assert loaded.prd_file == "test.md"
    assert len(loaded.task_mapping) == 2
    assert len(loaded.tasks) == 2
    assert loaded.total_cost_usd == 5.5
    assert loaded.pending_count == 2


def test_prd_state_load_or_create_existing(tmp_path: Path):
    """Test load_or_create with existing file."""
    state_file = tmp_path / "prd-state.json"

    # Create and save
    original = PRDState(prd_file="original.md")
    original.add_task("PRD-001", "Task", "high", 1)
    original.save(state_file)

    # Load or create should load existing
    loaded = PRDState.load_or_create(state_file, "new.md")

    assert loaded.prd_file == "original.md"
    assert len(loaded.task_mapping) == 1


def test_prd_state_load_or_create_new(tmp_path: Path):
    """Test load_or_create with non-existent file."""
    state_file = tmp_path / "prd-state.json"

    # Load or create should create new
    state = PRDState.load_or_create(state_file, "new.md")

    assert state.prd_file == "new.md"
    assert len(state.task_mapping) == 0


def test_prd_state_manager_initialization(tmp_path: Path):
    """Test PRDStateManager initialization."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    assert manager.prd_dir == prd_dir
    assert manager.prd_state_path == prd_dir / "prd-state.json"
    assert manager.prd_state.prd_file == "test.md"


def test_prd_state_manager_get_task_state_path(tmp_path: Path):
    """Test getting task state path."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    path = manager.get_task_state_path("PRD-001")

    assert path == prd_dir / "PRD-001" / "state.json"


def test_prd_state_manager_load_task_state(tmp_path: Path):
    """Test loading task state."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    # Create a task state file
    task_state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    task_state.cost_usd = 2.5
    task_state_path = manager.get_task_state_path("PRD-001")
    task_state.save(task_state_path)

    # Load it
    loaded = manager.load_task_state("PRD-001", "Different text", "low")

    # Should load existing state, not create new
    assert loaded.task_text == "Test task"
    assert loaded.priority == "high"
    assert loaded.cost_usd == 2.5


def test_prd_state_manager_save_task_state(tmp_path: Path):
    """Test saving task state updates PRD state."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    # Add task to PRD state
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    # Create and save task state
    task_state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    task_state.status = TaskStatus.IN_PROGRESS
    task_state.cost_usd = 3.5

    manager.save_task_state(task_state)

    # Check PRD state was updated
    assert manager.prd_state.tasks["PRD-001"]["status"] == "in_progress"
    assert manager.prd_state.tasks["PRD-001"]["cost_usd"] == 3.5
    assert manager.prd_state.in_progress_count == 1


def test_prd_state_manager_start_task(tmp_path: Path):
    """Test starting a task."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    task_state = manager.start_task(
        "PRD-001", "Test task", "high", "run-123", "feature/PRD-001-test"
    )

    assert task_state.status == TaskStatus.IN_PROGRESS
    assert task_state.nelson_run_id == "run-123"
    assert task_state.branch == "feature/PRD-001-test"
    assert manager.prd_state.current_task_id == "PRD-001"
    assert manager.prd_state.in_progress_count == 1


def test_prd_state_manager_complete_task(tmp_path: Path):
    """Test completing a task."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    # Start then complete
    manager.start_task("PRD-001", "Test task", "high", "run-123", "feature/test")
    task_state = manager.complete_task("PRD-001")

    assert task_state.status == TaskStatus.COMPLETED
    assert manager.prd_state.completed_count == 1
    assert manager.prd_state.in_progress_count == 0


def test_prd_state_manager_block_task(tmp_path: Path):
    """Test blocking a task."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    manager.start_task("PRD-001", "Test task", "high", "run-123", "feature/test")
    task_state = manager.block_task("PRD-001", "Waiting for API")

    assert task_state.status == TaskStatus.BLOCKED
    assert task_state.blocking_reason == "Waiting for API"
    assert manager.prd_state.blocked_count == 1


def test_prd_state_manager_unblock_task(tmp_path: Path):
    """Test unblocking a task."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    # Start, block, then unblock
    manager.start_task("PRD-001", "Test task", "high", "run-123", "feature/test")
    manager.block_task("PRD-001", "Waiting for API")
    task_state = manager.unblock_task("PRD-001", "API ready")

    assert task_state.status == TaskStatus.PENDING
    assert task_state.resume_context == "API ready"
    assert manager.prd_state.pending_count == 1
    assert manager.prd_state.blocked_count == 0


def test_prd_state_manager_get_next_task(tmp_path: Path):
    """Test getting next task by priority."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    # Add tasks in different priorities
    manager.prd_state.add_task("PRD-001", "Low task", "low", 1)
    manager.prd_state.add_task("PRD-002", "High task", "high", 2)
    manager.prd_state.add_task("PRD-003", "Medium task", "medium", 3)

    # Should return high priority first
    task_id, task_state = manager.get_next_task()

    assert task_id == "PRD-002"
    assert task_state.priority == "high"


def test_prd_state_manager_get_all_task_states(tmp_path: Path):
    """Test getting all task states."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    manager.prd_state.add_task("PRD-001", "Task 1", "high", 1)
    manager.prd_state.add_task("PRD-002", "Task 2", "medium", 2)

    states = manager.get_all_task_states()

    assert len(states) == 2
    assert "PRD-001" in states
    assert "PRD-002" in states
    assert states["PRD-001"].task_text == "Task 1"
    assert states["PRD-002"].task_text == "Task 2"
