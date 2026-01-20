"""Tests for prd_state module."""

import json
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
    task_state = manager.block_task("PRD-001", "Test task", "high", "Waiting for API")

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
    manager.block_task("PRD-001", "Test task", "high", "Waiting for API")
    task_state = manager.unblock_task("PRD-001", "Test task", "high", "API ready")

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


# Corruption recovery tests


def test_prd_state_load_corrupted_json(tmp_path: Path):
    """Test loading corrupted PRD state JSON file raises JSONDecodeError.

    When prd-state.json is corrupted with invalid JSON, the load method
    should raise JSONDecodeError, allowing the caller to handle recovery.
    """
    state_file = tmp_path / "prd-state.json"

    # Write corrupted JSON (missing closing brace, invalid syntax)
    state_file.write_text('{"prd_file": "test.md", "total_cost_usd": 5.5, invalid json')

    with pytest.raises(json.JSONDecodeError):
        PRDState.load(state_file)


def test_prd_state_load_partially_written_json(tmp_path: Path):
    """Test loading partially written PRD state file.

    Simulates scenario where write was interrupted (power loss, kill signal).
    File exists but contains incomplete JSON.
    """
    state_file = tmp_path / "prd-state.json"

    # Write partial JSON (cut off mid-write)
    state_file.write_text('{"prd_file": "test.md", "started_at": "2025-01-')

    with pytest.raises(json.JSONDecodeError):
        PRDState.load(state_file)


def test_prd_state_load_empty_file(tmp_path: Path):
    """Test loading empty PRD state file.

    Empty file could result from failed write or filesystem issues.
    """
    state_file = tmp_path / "prd-state.json"
    state_file.write_text("")

    with pytest.raises(json.JSONDecodeError):
        PRDState.load(state_file)


def test_prd_state_load_or_create_handles_corruption(tmp_path: Path):
    """Test load_or_create does NOT handle corruption gracefully.

    Important: load_or_create only creates new state if file doesn't exist.
    If file exists but is corrupted, it raises JSONDecodeError.
    Caller must explicitly handle corruption and delete/recover the file.
    """
    state_file = tmp_path / "prd-state.json"

    # Write corrupted JSON
    state_file.write_text('{"invalid": json}')

    # load_or_create should raise error, not silently create new state
    with pytest.raises(json.JSONDecodeError):
        PRDState.load_or_create(state_file, "new.md")


def test_prd_state_recovery_by_deleting_corrupted_file(tmp_path: Path):
    """Test recovery pattern: delete corrupted file and recreate.

    This demonstrates the recommended recovery pattern when corruption is detected.
    """
    state_file = tmp_path / "prd-state.json"

    # Write corrupted JSON
    state_file.write_text('{"bad": json}')

    # Attempt to load, catch error, delete, and recreate
    try:
        PRDState.load(state_file)
    except json.JSONDecodeError:
        # Recovery: delete corrupted file
        state_file.unlink()

        # Now load_or_create will create fresh state
        recovered_state = PRDState.load_or_create(state_file, "recovered.md")

        assert recovered_state.prd_file == "recovered.md"
        assert recovered_state.total_cost_usd == 0.0
        assert len(recovered_state.task_mapping) == 0


def test_task_state_load_corrupted_json(tmp_path: Path):
    """Test loading corrupted task state JSON file raises JSONDecodeError.

    When PRD-NNN/state.json is corrupted, load should raise error.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write corrupted JSON
    task_state_file.write_text('{"task_id": "PRD-001", "status": invalid}')

    with pytest.raises(json.JSONDecodeError):
        TaskState.load(task_state_file)


def test_task_state_load_partially_written_json(tmp_path: Path):
    """Test loading partially written task state file.

    Simulates interrupted write during task state persistence.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write partial JSON
    task_state_file.write_text('{"task_id": "PRD-001", "task_text": "Incomplete')

    with pytest.raises(json.JSONDecodeError):
        TaskState.load(task_state_file)


def test_task_state_load_with_missing_required_fields(tmp_path: Path):
    """Test loading task state with missing required fields.

    Valid JSON but missing required dataclass fields should raise error.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write valid JSON but missing required fields (task_id, task_text)
    task_state_file.write_text('{"status": "pending", "cost_usd": 0.0}')

    with pytest.raises(TypeError):
        TaskState.load(task_state_file)


def test_task_state_load_or_create_handles_corruption(tmp_path: Path):
    """Test task state load_or_create does NOT handle corruption.

    Like PRD state, if file exists but is corrupted, it raises error.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write corrupted JSON
    task_state_file.write_text("{invalid json}")

    # Should raise error, not create new state
    with pytest.raises(json.JSONDecodeError):
        TaskState.load_or_create(task_state_file, "PRD-001", "Test task", "high")


def test_task_state_recovery_by_deleting_corrupted_file(tmp_path: Path):
    """Test recovery pattern for corrupted task state.

    Demonstrates recommended recovery: detect corruption, delete, recreate.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write corrupted JSON
    task_state_file.write_text('{"corrupted": data}')

    # Attempt to load, catch error, delete, and recreate
    try:
        TaskState.load(task_state_file)
    except json.JSONDecodeError:
        # Recovery: delete corrupted file
        task_state_file.unlink()

        # Now load_or_create will create fresh state
        recovered = TaskState.load_or_create(task_state_file, "PRD-001", "Recovered task", "high")

        assert recovered.task_id == "PRD-001"
        assert recovered.task_text == "Recovered task"
        assert recovered.status == TaskStatus.PENDING
        assert recovered.cost_usd == 0.0


def test_prd_state_manager_handles_corrupted_task_state(tmp_path: Path):
    """Test PRDStateManager behavior when task state file is corrupted.

    Manager's load_task_state should propagate the JSONDecodeError to caller.
    """
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Test task", "high", 1)

    # Create corrupted task state file
    task_state_path = manager.get_task_state_path("PRD-001")
    task_state_path.parent.mkdir(parents=True)
    task_state_path.write_text("{bad json}")

    # Manager should propagate the error
    with pytest.raises(json.JSONDecodeError):
        manager.load_task_state("PRD-001", "Test task", "high")


def test_prd_state_with_extra_fields_is_compatible(tmp_path: Path):
    """Test PRD state gracefully handles extra fields (forward compatibility).

    If a newer version adds fields, older version should still load.
    """
    state_file = tmp_path / "prd-state.json"

    # Write state with extra future fields
    state_data = {
        "prd_file": "test.md",
        "started_at": "2025-01-15T14:00:00Z",
        "updated_at": "2025-01-15T15:00:00Z",
        "total_cost_usd": 2.5,
        "task_mapping": {},
        "tasks": {},
        "current_task_id": None,
        "completed_count": 0,
        "in_progress_count": 0,
        "blocked_count": 0,
        "pending_count": 0,
        "failed_count": 0,
        # Future fields that don't exist yet
        "future_field_1": "some_value",
        "future_field_2": 123,
    }

    with open(state_file, "w") as f:
        json.dump(state_data, f)

    # Should load successfully, ignoring extra fields
    state = PRDState.load(state_file)

    assert state.prd_file == "test.md"
    assert state.total_cost_usd == 2.5


def test_task_state_with_extra_fields_is_compatible(tmp_path: Path):
    """Test task state gracefully handles extra fields (forward compatibility).

    Newer versions may add fields; older versions should still load.
    """
    task_state_file = tmp_path / "PRD-001" / "state.json"
    task_state_file.parent.mkdir(parents=True)

    # Write state with extra future fields
    state_data = {
        "task_id": "PRD-001",
        "task_text": "Test task",
        "status": "pending",
        "priority": "high",
        "branch": None,
        "blocking_reason": None,
        "resume_context": None,
        "nelson_run_id": None,
        "started_at": None,
        "updated_at": "2025-01-15T14:00:00Z",
        "completed_at": None,
        "blocked_at": None,
        "cost_usd": 0.0,
        "iterations": 0,
        "phase": None,
        "phase_name": None,
        # Future fields
        "future_metric": 42,
        "future_data": {"nested": "value"},
    }

    with open(task_state_file, "w") as f:
        json.dump(state_data, f)

    # Should load successfully, ignoring extra fields
    state = TaskState.load(task_state_file)

    assert state.task_id == "PRD-001"
    assert state.task_text == "Test task"
    assert state.status == TaskStatus.PENDING


def test_state_file_persistence_across_workflow_operations(tmp_path: Path):
    """Test state persistence across multiple workflow operations."""
    prd_dir = tmp_path / "prd"
    state_file = prd_dir / "prd-state.json"

    # Phase 1: Initialize manager with 3 tasks
    manager = PRDStateManager(prd_dir, "test.md")
    manager.prd_state.add_task("PRD-001", "Task 1", "high", 1)
    manager.prd_state.add_task("PRD-002", "Task 2", "medium", 2)
    manager.prd_state.add_task("PRD-003", "Task 3", "low", 3)
    manager.save_prd_state()

    # Verify state file exists and is valid JSON
    assert state_file.exists()
    loaded_data = json.loads(state_file.read_text())
    assert len(loaded_data["task_mapping"]) == 3
    assert loaded_data["pending_count"] == 3

    # Phase 2: Start task PRD-001
    task_state_1 = manager.start_task(
        "PRD-001", "Task 1", "high", "run-001", "feature/PRD-001-task-1"
    )
    task_state_1.update_cost(1.5)
    task_state_1.increment_iterations(10)
    manager.save_task_state(task_state_1)

    # Verify both PRD state and task state persisted
    task_state_file_1 = prd_dir / "PRD-001" / "state.json"
    assert task_state_file_1.exists()
    task_data = json.loads(task_state_file_1.read_text())
    assert task_data["task_id"] == "PRD-001"
    assert task_data["status"] == "in_progress"
    assert task_data["cost_usd"] == 1.5
    assert task_data["iterations"] == 10

    loaded_prd_state = json.loads(state_file.read_text())
    assert loaded_prd_state["in_progress_count"] == 1
    assert loaded_prd_state["pending_count"] == 2
    assert loaded_prd_state["current_task_id"] == "PRD-001"

    # Phase 3: Complete task PRD-001 and start PRD-002
    task_state_1 = manager.complete_task("PRD-001")
    task_state_1.update_cost(0.5)  # Additional cost
    manager.save_task_state(task_state_1)

    task_state_2 = manager.start_task(
        "PRD-002", "Task 2", "medium", "run-002", "feature/PRD-002-task-2"
    )
    manager.save_task_state(task_state_2)

    # Verify state transitions persisted correctly
    task_data_1 = json.loads(task_state_file_1.read_text())
    assert task_data_1["status"] == "completed"
    assert task_data_1["cost_usd"] == 2.0  # 1.5 + 0.5 accumulated
    assert task_data_1["completed_at"] is not None

    task_state_file_2 = prd_dir / "PRD-002" / "state.json"
    assert task_state_file_2.exists()
    task_data_2 = json.loads(task_state_file_2.read_text())
    assert task_data_2["status"] == "in_progress"

    loaded_prd_state = json.loads(state_file.read_text())
    assert loaded_prd_state["completed_count"] == 1
    assert loaded_prd_state["in_progress_count"] == 1
    assert loaded_prd_state["pending_count"] == 1

    # Phase 4: Block task PRD-002
    task_state_2 = manager.block_task("PRD-002", "Task 2", "medium", "Waiting for API keys")
    task_state_2.resume_context = "API keys added to .env"
    manager.save_task_state(task_state_2)

    # Verify blocking persisted with resume context
    task_data_2 = json.loads(task_state_file_2.read_text())
    assert task_data_2["status"] == "blocked"
    assert task_data_2["blocking_reason"] == "Waiting for API keys"
    assert task_data_2["resume_context"] == "API keys added to .env"
    assert task_data_2["blocked_at"] is not None

    loaded_prd_state = json.loads(state_file.read_text())
    assert loaded_prd_state["blocked_count"] == 1
    assert loaded_prd_state["in_progress_count"] == 0

    # Phase 5: Unblock and complete PRD-002
    task_state_2 = manager.unblock_task("PRD-002", "Task 2", "medium", "Ready to resume")
    manager.save_task_state(task_state_2)

    task_data_2 = json.loads(task_state_file_2.read_text())
    assert task_data_2["status"] == "pending"
    assert task_data_2["resume_context"] == "Ready to resume"

    # Resume and complete
    task_state_2.status = TaskStatus.IN_PROGRESS
    manager.save_task_state(task_state_2)
    task_state_2 = manager.complete_task("PRD-002")
    manager.save_task_state(task_state_2)

    # Verify final state
    loaded_prd_state = json.loads(state_file.read_text())
    assert loaded_prd_state["completed_count"] == 2
    assert loaded_prd_state["blocked_count"] == 0
    assert loaded_prd_state["pending_count"] == 1


def test_state_file_recovery_after_process_restart(tmp_path: Path):
    """Test that state can be recovered after simulated process restart."""
    prd_dir = tmp_path / "prd"
    prd_file = "test.md"

    # Session 1: Create manager, add tasks, start work
    manager1 = PRDStateManager(prd_dir, prd_file)
    manager1.prd_state.add_task("PRD-001", "Task 1", "high", 1)
    manager1.prd_state.add_task("PRD-002", "Task 2", "medium", 2)
    manager1.save_prd_state()

    task_state_1 = manager1.start_task(
        "PRD-001", "Task 1", "high", "run-001", "feature/PRD-001-task-1"
    )
    task_state_1.update_cost(2.5)
    task_state_1.increment_iterations(15)
    task_state_1.update_phase(2, "IMPLEMENT")
    manager1.save_task_state(task_state_1)

    # Simulate process restart: Create new manager instance
    manager2 = PRDStateManager(prd_dir, prd_file)

    # Verify PRD state recovered correctly
    assert manager2.prd_state.prd_file == prd_file
    assert len(manager2.prd_state.task_mapping) == 2
    assert manager2.prd_state.in_progress_count == 1
    assert manager2.prd_state.pending_count == 1
    assert manager2.prd_state.current_task_id == "PRD-001"

    # Verify task state can be loaded
    recovered_task = manager2.load_task_state("PRD-001", "Task 1", "high")
    assert recovered_task.task_id == "PRD-001"
    assert recovered_task.status == TaskStatus.IN_PROGRESS
    assert recovered_task.cost_usd == 2.5
    assert recovered_task.iterations == 15
    assert recovered_task.phase == 2
    assert recovered_task.phase_name == "IMPLEMENT"
    assert recovered_task.nelson_run_id == "run-001"
    assert recovered_task.branch == "feature/PRD-001-task-1"

    # Continue work in session 2
    recovered_task.update_cost(1.0)  # Additional cost
    recovered_task.increment_iterations(5)  # More iterations
    manager2.save_task_state(recovered_task)

    # Complete task
    completed_task = manager2.complete_task("PRD-001")
    manager2.save_task_state(completed_task)

    # Simulate another restart and verify final state
    manager3 = PRDStateManager(prd_dir, prd_file)
    assert manager3.prd_state.completed_count == 1
    assert manager3.prd_state.in_progress_count == 0

    final_task = manager3.load_task_state("PRD-001", "Task 1", "high")
    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.cost_usd == 3.5  # 2.5 + 1.0 accumulated
    assert final_task.iterations == 20  # 15 + 5 accumulated
    assert final_task.completed_at is not None


def test_multiple_task_state_independence(tmp_path: Path):
    """Test that multiple tasks maintain independent state files."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    # Create and persist 5 tasks simultaneously
    tasks = []
    for i in range(1, 6):
        task_id = f"PRD-00{i}"
        manager.prd_state.add_task(task_id, f"Task {i}", "high", i)

        task_state = manager.start_task(
            task_id, f"Task {i}", "high", f"run-00{i}", f"feature/{task_id}"
        )
        task_state.update_cost(i * 1.5)  # Different costs
        task_state.increment_iterations(i * 10)  # Different iterations
        manager.save_task_state(task_state)
        tasks.append(task_state)

    # Verify each task has independent state file
    for i in range(1, 6):
        task_id = f"PRD-00{i}"
        task_state_file = prd_dir / task_id / "state.json"
        assert task_state_file.exists()

        # Load and verify independence
        loaded = manager.load_task_state(task_id, f"Task {i}", "high")
        assert loaded.task_id == task_id
        assert loaded.cost_usd == i * 1.5
        assert loaded.iterations == i * 10
        assert loaded.nelson_run_id == f"run-00{i}"
        assert loaded.branch == f"feature/{task_id}"

    # Complete tasks in different order and verify independence
    manager.complete_task("PRD-003")
    manager.save_task_state(manager.load_task_state("PRD-003", "Task 3", "high"))

    manager.complete_task("PRD-001")
    manager.save_task_state(manager.load_task_state("PRD-001", "Task 1", "high"))

    # Verify PRD-003 and PRD-001 are completed, others still in progress
    assert manager.load_task_state("PRD-001", "Task 1", "high").status == TaskStatus.COMPLETED
    assert manager.load_task_state("PRD-002", "Task 2", "high").status == TaskStatus.IN_PROGRESS
    assert manager.load_task_state("PRD-003", "Task 3", "high").status == TaskStatus.COMPLETED
    assert manager.load_task_state("PRD-004", "Task 4", "high").status == TaskStatus.IN_PROGRESS
    assert manager.load_task_state("PRD-005", "Task 5", "high").status == TaskStatus.IN_PROGRESS

    # Verify PRD state reflects correct counts
    assert manager.prd_state.completed_count == 2
    assert manager.prd_state.in_progress_count == 3


def test_state_synchronization_between_prd_and_task_states(tmp_path: Path):
    """Test that PRD state and task states stay synchronized."""
    prd_dir = tmp_path / "prd"
    manager = PRDStateManager(prd_dir, "test.md")

    # Add task
    manager.prd_state.add_task("PRD-001", "Task 1", "high", 1)
    manager.save_prd_state()

    # Start task - should update both PRD state and task state
    task_state = manager.start_task("PRD-001", "Task 1", "high", "run-001", "feature/PRD-001")

    # Verify synchronization: PRD state
    assert manager.prd_state.tasks["PRD-001"]["status"] == "in_progress"
    assert manager.prd_state.in_progress_count == 1
    assert manager.prd_state.current_task_id == "PRD-001"

    # Verify synchronization: Task state
    assert task_state.status == TaskStatus.IN_PROGRESS
    assert task_state.started_at is not None

    # Update cost and save
    task_state.update_cost(3.5)
    manager.save_task_state(task_state)

    # Verify cost synchronized to PRD state
    assert manager.prd_state.tasks["PRD-001"]["cost_usd"] == 3.5
    assert manager.prd_state.total_cost_usd == 3.5

    # Block task
    blocked_task = manager.block_task("PRD-001", "Task 1", "high", "Blocked reason")

    # Verify blocking synchronized
    assert manager.prd_state.tasks["PRD-001"]["status"] == "blocked"
    assert manager.prd_state.blocked_count == 1
    assert manager.prd_state.in_progress_count == 0
    assert blocked_task.status == TaskStatus.BLOCKED
    assert blocked_task.blocking_reason == "Blocked reason"

    # Unblock task
    unblocked_task = manager.unblock_task("PRD-001", "Task 1", "high", "Resume context")

    # Verify unblocking synchronized
    assert manager.prd_state.tasks["PRD-001"]["status"] == "pending"
    assert manager.prd_state.blocked_count == 0
    assert manager.prd_state.pending_count == 1
    assert unblocked_task.status == TaskStatus.PENDING
    assert unblocked_task.resume_context == "Resume context"

    # Complete task
    task_state.status = TaskStatus.IN_PROGRESS
    manager.save_task_state(task_state)
    completed_task = manager.complete_task("PRD-001")

    # Verify completion synchronized
    assert manager.prd_state.tasks["PRD-001"]["status"] == "completed"
    assert manager.prd_state.completed_count == 1
    assert manager.prd_state.in_progress_count == 0
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.completed_at is not None

    # Reload from disk and verify persistence
    manager_reloaded = PRDStateManager(prd_dir, "test.md")
    assert manager_reloaded.prd_state.completed_count == 1
    assert manager_reloaded.prd_state.tasks["PRD-001"]["status"] == "completed"
    assert manager_reloaded.prd_state.tasks["PRD-001"]["cost_usd"] == 3.5

    reloaded_task = manager_reloaded.load_task_state("PRD-001", "Task 1", "high")
    assert reloaded_task.status == TaskStatus.COMPLETED
    assert reloaded_task.cost_usd == 3.5


def test_state_recovery_after_execution_interruption(tmp_path: Path):
    """Test state recovery after simulated interruption during execution."""
    prd_dir = tmp_path / "prd"
    prd_file = "test.md"

    # Setup: Manager with task in progress
    manager1 = PRDStateManager(prd_dir, prd_file)
    manager1.prd_state.add_task("PRD-001", "Task 1", "high", 1)
    manager1.prd_state.add_task("PRD-002", "Task 2", "medium", 2)
    manager1.save_prd_state()

    task_state = manager1.start_task("PRD-001", "Task 1", "high", "run-001", "feature/PRD-001")
    task_state.update_cost(1.5)
    task_state.increment_iterations(10)
    manager1.save_task_state(task_state)

    # Simulate interruption: Task is in progress but process dies
    # State files remain on disk

    # Recovery: Create new manager
    manager2 = PRDStateManager(prd_dir, prd_file)

    # Verify we can detect in-progress task
    assert manager2.prd_state.in_progress_count == 1
    assert manager2.prd_state.current_task_id == "PRD-001"

    # Load the interrupted task state
    recovered_task = manager2.load_task_state("PRD-001", "Task 1", "high")

    # Verify task state preserved from before interruption
    assert recovered_task.status == TaskStatus.IN_PROGRESS
    assert recovered_task.cost_usd == 1.5
    assert recovered_task.iterations == 10
    assert recovered_task.nelson_run_id == "run-001"
    assert recovered_task.branch == "feature/PRD-001"

    # User can choose to:
    # Option 1: Complete the task (assuming it actually finished)
    recovered_task = manager2.complete_task("PRD-001")
    manager2.save_task_state(recovered_task)
    assert recovered_task.status == TaskStatus.COMPLETED

    # OR Option 2: Mark as failed and restart
    # (We'll test Option 1 here)

    # Verify state after recovery action
    assert manager2.prd_state.completed_count == 1
    assert manager2.prd_state.in_progress_count == 0

    # Continue with next task
    task_state_2 = manager2.start_task("PRD-002", "Task 2", "medium", "run-002", "feature/PRD-002")
    manager2.save_task_state(task_state_2)

    # Verify workflow continues normally after recovery
    assert manager2.prd_state.current_task_id == "PRD-002"
    assert manager2.prd_state.in_progress_count == 1

    # Final verification: Full restart can load all state
    manager3 = PRDStateManager(prd_dir, prd_file)
    assert manager3.prd_state.completed_count == 1
    assert manager3.prd_state.in_progress_count == 1
    assert len(manager3.prd_state.task_mapping) == 2
