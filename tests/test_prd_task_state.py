"""Tests for prd_task_state module."""

import json
from pathlib import Path

import pytest

from nelson.prd_task_state import TaskState, TaskStatus, _utc_timestamp


def test_task_state_initialization():
    """Test TaskState initialization with defaults."""
    state = TaskState(task_id="PRD-001", task_text="Add authentication", priority="high")

    assert state.task_id == "PRD-001"
    assert state.task_text == "Add authentication"
    assert state.priority == "high"
    assert state.status == TaskStatus.PENDING
    assert state.branch is None
    assert state.blocking_reason is None
    assert state.resume_context is None
    assert state.nelson_run_id is None
    assert state.started_at is None
    assert state.completed_at is None
    assert state.blocked_at is None
    assert state.cost_usd == 0.0
    assert state.iterations == 0
    assert state.phase is None
    assert state.phase_name is None
    assert state.updated_at is not None


def test_task_state_start():
    """Test starting a task."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")

    state.start("run-001", "feature/PRD-001-test-task")

    assert state.status == TaskStatus.IN_PROGRESS
    assert state.nelson_run_id == "run-001"
    assert state.branch == "feature/PRD-001-test-task"
    assert state.started_at is not None


def test_task_state_complete():
    """Test completing a task."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    state.start("run-001", "feature/PRD-001-test")

    state.complete()

    assert state.status == TaskStatus.COMPLETED
    assert state.completed_at is not None


def test_task_state_fail():
    """Test failing a task."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    state.start("run-001", "feature/PRD-001-test")

    state.fail()

    assert state.status == TaskStatus.FAILED


def test_task_state_block():
    """Test blocking a task."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    state.start("run-001", "feature/PRD-001-test")

    state.block("Waiting for API keys")

    assert state.status == TaskStatus.BLOCKED
    assert state.blocking_reason == "Waiting for API keys"
    assert state.blocked_at is not None


def test_task_state_unblock():
    """Test unblocking a task."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    state.start("run-001", "feature/PRD-001-test")
    state.block("Waiting for API keys")

    state.unblock("Keys added to .env")

    assert state.status == TaskStatus.PENDING
    assert state.resume_context == "Keys added to .env"
    # blocked_at is kept for history
    assert state.blocked_at is not None


def test_task_state_update_cost():
    """Test updating task cost."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")

    state.update_cost(1.5)
    assert state.cost_usd == 1.5

    state.update_cost(0.75)
    assert state.cost_usd == 2.25


def test_task_state_update_phase():
    """Test updating phase tracking."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")

    state.update_phase(2, "IMPLEMENT")

    assert state.phase == 2
    assert state.phase_name == "IMPLEMENT"


def test_task_state_increment_iterations():
    """Test incrementing iteration counter."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")

    state.increment_iterations()
    assert state.iterations == 1

    state.increment_iterations(5)
    assert state.iterations == 6


def test_task_state_to_dict():
    """Test converting TaskState to dictionary."""
    state = TaskState(
        task_id="PRD-001",
        task_text="Test task",
        priority="high",
        status=TaskStatus.IN_PROGRESS,
    )
    state.branch = "feature/PRD-001-test"
    state.cost_usd = 1.5

    data = state.to_dict()

    assert data["task_id"] == "PRD-001"
    assert data["task_text"] == "Test task"
    assert data["priority"] == "high"
    assert data["status"] == "in_progress"  # Enum converted to value
    assert data["branch"] == "feature/PRD-001-test"
    assert data["cost_usd"] == 1.5


def test_task_state_from_dict():
    """Test creating TaskState from dictionary."""
    data = {
        "task_id": "PRD-001",
        "task_text": "Test task",
        "priority": "high",
        "status": "in_progress",
        "branch": "feature/PRD-001-test",
        "cost_usd": 1.5,
        "iterations": 5,
        "updated_at": "2025-01-15T14:00:00Z",
    }

    state = TaskState.from_dict(data)

    assert state.task_id == "PRD-001"
    assert state.task_text == "Test task"
    assert state.priority == "high"
    assert state.status == TaskStatus.IN_PROGRESS
    assert state.branch == "feature/PRD-001-test"
    assert state.cost_usd == 1.5
    assert state.iterations == 5


def test_task_state_save_load(tmp_path: Path):
    """Test saving and loading TaskState."""
    state_file = tmp_path / "PRD-001" / "state.json"

    # Create and save state
    state = TaskState(
        task_id="PRD-001",
        task_text="Test task",
        priority="high",
        status=TaskStatus.IN_PROGRESS,
    )
    state.branch = "feature/PRD-001-test"
    state.cost_usd = 2.5
    state.save(state_file)

    # Verify file exists
    assert state_file.exists()

    # Load state
    loaded = TaskState.load(state_file)

    assert loaded.task_id == state.task_id
    assert loaded.task_text == state.task_text
    assert loaded.priority == state.priority
    assert loaded.status == state.status
    assert loaded.branch == state.branch
    assert loaded.cost_usd == state.cost_usd


def test_task_state_load_or_create_existing(tmp_path: Path):
    """Test load_or_create with existing file."""
    state_file = tmp_path / "PRD-001" / "state.json"

    # Create and save state
    original = TaskState(
        task_id="PRD-001", task_text="Original task", priority="high"
    )
    original.cost_usd = 5.0
    original.save(state_file)

    # Load or create should load existing
    loaded = TaskState.load_or_create(state_file, "PRD-001", "New task", "low")

    assert loaded.task_text == "Original task"
    assert loaded.priority == "high"
    assert loaded.cost_usd == 5.0


def test_task_state_load_or_create_new(tmp_path: Path):
    """Test load_or_create with non-existent file."""
    state_file = tmp_path / "PRD-001" / "state.json"

    # Load or create should create new
    state = TaskState.load_or_create(state_file, "PRD-001", "New task", "high")

    assert state.task_id == "PRD-001"
    assert state.task_text == "New task"
    assert state.priority == "high"
    assert state.status == TaskStatus.PENDING


def test_task_state_update_timestamp():
    """Test that operations update timestamp."""
    state = TaskState(task_id="PRD-001", task_text="Test task", priority="high")
    original_timestamp = state.updated_at

    # Small delay to ensure timestamp changes
    import time
    time.sleep(0.01)

    state.update_cost(1.0)
    assert state.updated_at != original_timestamp


def test_utc_timestamp_format():
    """Test UTC timestamp format."""
    timestamp = _utc_timestamp()

    # Should be ISO 8601 format ending with Z
    assert timestamp.endswith("Z")
    assert "T" in timestamp

    # Should be parseable
    from datetime import datetime
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed is not None
