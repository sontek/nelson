"""Tests for state management module."""

import json
from pathlib import Path

import pytest

from nelson.state import RalphState, _utc_timestamp


class TestRalphState:
    """Tests for RalphState dataclass."""

    def test_default_initialization(self) -> None:
        """Test creating state with default values."""
        state = RalphState()

        assert state.total_iterations == 0
        assert state.phase_iterations == 0
        assert state.cost_usd == 0.0
        assert state.prompt == ""
        assert state.starting_commit == ""
        assert state.last_completed_count == 0
        assert state.no_progress_iterations == 0
        assert state.last_error_message == ""
        assert state.repeated_error_count == 0
        assert state.test_only_loop_count == 0
        assert state.current_phase == 1
        assert state.phase_name == "PLAN"
        assert state.exit_signal_received is False
        # Timestamps should be set to now
        assert state.started_at
        assert state.updated_at

    def test_custom_initialization(self) -> None:
        """Test creating state with custom values."""
        state = RalphState(
            total_iterations=5,
            phase_iterations=2,
            cost_usd=1.25,
            prompt="Fix bug",
            starting_commit="abc123",
            current_phase=2,
            phase_name="IMPLEMENT",
        )

        assert state.total_iterations == 5
        assert state.phase_iterations == 2
        assert state.cost_usd == 1.25
        assert state.prompt == "Fix bug"
        assert state.starting_commit == "abc123"
        assert state.current_phase == 2
        assert state.phase_name == "IMPLEMENT"

    def test_increment_iteration(self) -> None:
        """Test incrementing iteration counters."""
        state = RalphState()
        original_updated = state.updated_at

        state.increment_iteration()

        assert state.total_iterations == 1
        assert state.phase_iterations == 1
        # Timestamp should be updated (will be same or later than original)
        assert state.updated_at >= original_updated

        state.increment_iteration()

        assert state.total_iterations == 2
        assert state.phase_iterations == 2

    def test_reset_phase_iterations(self) -> None:
        """Test resetting phase iteration counter."""
        state = RalphState(total_iterations=10, phase_iterations=5)

        state.reset_phase_iterations()

        assert state.total_iterations == 10  # Unchanged
        assert state.phase_iterations == 0  # Reset

    def test_update_timestamp(self) -> None:
        """Test timestamp update."""
        state = RalphState()
        original_updated = state.updated_at

        state.update_timestamp()

        # Timestamp should be updated (will be same or later than original)
        assert state.updated_at >= original_updated
        # Verify format is still valid
        assert state.updated_at.endswith("Z")

    def test_update_cost(self) -> None:
        """Test cost accumulation."""
        state = RalphState()
        original_updated = state.updated_at

        state.update_cost(0.50)
        assert state.cost_usd == 0.50
        # Timestamp should be updated (will be same or later than original)
        assert state.updated_at >= original_updated

        state.update_cost(0.25)
        assert state.cost_usd == 0.75

        state.update_cost(1.00)
        assert state.cost_usd == 1.75

    def test_record_progress_with_advancement(self) -> None:
        """Test recording progress when tasks are completed."""
        state = RalphState(last_completed_count=5, no_progress_iterations=2)

        state.record_progress(7)

        assert state.last_completed_count == 7
        assert state.no_progress_iterations == 0  # Reset on progress

    def test_record_progress_without_advancement(self) -> None:
        """Test recording progress when no tasks completed."""
        state = RalphState(last_completed_count=5, no_progress_iterations=1)

        state.record_progress(5)  # Same count, no progress

        assert state.last_completed_count == 5
        assert state.no_progress_iterations == 2  # Incremented

        state.record_progress(5)  # Still no progress

        assert state.no_progress_iterations == 3

    def test_record_error_new_error(self) -> None:
        """Test recording a new error message."""
        state = RalphState()

        state.record_error("Connection timeout")

        assert state.last_error_message == "Connection timeout"
        assert state.repeated_error_count == 1

    def test_record_error_repeated_error(self) -> None:
        """Test recording repeated identical errors."""
        state = RalphState()

        state.record_error("Connection timeout")
        assert state.repeated_error_count == 1

        state.record_error("Connection timeout")
        assert state.repeated_error_count == 2

        state.record_error("Connection timeout")
        assert state.repeated_error_count == 3

    def test_record_error_different_error(self) -> None:
        """Test recording different error resets counter."""
        state = RalphState()

        state.record_error("Connection timeout")
        assert state.repeated_error_count == 1

        state.record_error("Connection timeout")
        assert state.repeated_error_count == 2

        state.record_error("File not found")  # Different error
        assert state.last_error_message == "File not found"
        assert state.repeated_error_count == 1  # Reset

    def test_record_test_only_iteration(self) -> None:
        """Test recording test-only iterations."""
        state = RalphState()

        state.record_test_only_iteration()
        assert state.test_only_loop_count == 1

        state.record_test_only_iteration()
        assert state.test_only_loop_count == 2

        state.record_test_only_iteration()
        assert state.test_only_loop_count == 3

    def test_reset_test_only_counter(self) -> None:
        """Test resetting test-only counter."""
        state = RalphState(test_only_loop_count=5)

        state.reset_test_only_counter()

        assert state.test_only_loop_count == 0

    def test_transition_phase(self) -> None:
        """Test phase transition."""
        state = RalphState(
            current_phase=1,
            phase_name="PLAN",
            phase_iterations=10,
            total_iterations=10,
        )
        original_updated = state.updated_at

        state.transition_phase(2, "IMPLEMENT")

        assert state.current_phase == 2
        assert state.phase_name == "IMPLEMENT"
        assert state.phase_iterations == 0  # Reset on phase change
        assert state.total_iterations == 10  # Unchanged
        # Timestamp should be updated (will be same or later than original)
        assert state.updated_at >= original_updated

    def test_to_dict(self) -> None:
        """Test converting state to dictionary."""
        state = RalphState(
            total_iterations=5,
            cost_usd=1.50,
            prompt="Test task",
            current_phase=2,
        )

        data = state.to_dict()

        assert isinstance(data, dict)
        assert data["total_iterations"] == 5
        assert data["cost_usd"] == 1.50
        assert data["prompt"] == "Test task"
        assert data["current_phase"] == 2
        assert "started_at" in data
        assert "updated_at" in data

    def test_from_dict(self) -> None:
        """Test creating state from dictionary."""
        data = {
            "total_iterations": 5,
            "phase_iterations": 2,
            "cost_usd": 1.50,
            "prompt": "Test task",
            "starting_commit": "abc123",
            "current_phase": 2,
            "phase_name": "IMPLEMENT",
            "started_at": "2024-01-13T10:00:00Z",
            "updated_at": "2024-01-13T10:30:00Z",
        }

        state = RalphState.from_dict(data)

        assert state.total_iterations == 5
        assert state.phase_iterations == 2
        assert state.cost_usd == 1.50
        assert state.prompt == "Test task"
        assert state.starting_commit == "abc123"
        assert state.current_phase == 2
        assert state.phase_name == "IMPLEMENT"
        assert state.started_at == "2024-01-13T10:00:00Z"
        assert state.updated_at == "2024-01-13T10:30:00Z"

    def test_from_dict_filters_invalid_keys(self) -> None:
        """Test from_dict ignores invalid/unknown keys."""
        data = {
            "total_iterations": 5,
            "cost_usd": 1.50,
            "invalid_key": "should be ignored",
            "another_invalid": 123,
        }

        state = RalphState.from_dict(data)

        assert state.total_iterations == 5
        assert state.cost_usd == 1.50
        # Should not raise error, invalid keys are filtered out

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading state from file."""
        state_file = tmp_path / "state.json"
        state = RalphState(
            total_iterations=10,
            phase_iterations=3,
            cost_usd=2.50,
            prompt="Test prompt",
            starting_commit="def456",
            current_phase=3,
            phase_name="REVIEW",
        )

        state.save(state_file)

        assert state_file.exists()

        loaded_state = RalphState.load(state_file)

        assert loaded_state.total_iterations == 10
        assert loaded_state.phase_iterations == 3
        assert loaded_state.cost_usd == 2.50
        assert loaded_state.prompt == "Test prompt"
        assert loaded_state.starting_commit == "def456"
        assert loaded_state.current_phase == 3
        assert loaded_state.phase_name == "REVIEW"

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test save creates parent directories if they don't exist."""
        state_file = tmp_path / "subdir" / "nested" / "state.json"
        state = RalphState()

        state.save(state_file)

        assert state_file.exists()
        assert state_file.parent.exists()

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Test loading from non-existent file raises error."""
        state_file = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError):
            RalphState.load(state_file)

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises error."""
        state_file = tmp_path / "invalid.json"
        state_file.write_text("not valid json{]")

        with pytest.raises(json.JSONDecodeError):
            RalphState.load(state_file)

    def test_load_or_create_existing_file(self, tmp_path: Path) -> None:
        """Test load_or_create loads existing file."""
        state_file = tmp_path / "state.json"
        state = RalphState(total_iterations=15, cost_usd=3.00)
        state.save(state_file)

        loaded_state = RalphState.load_or_create(state_file)

        assert loaded_state.total_iterations == 15
        assert loaded_state.cost_usd == 3.00

    def test_load_or_create_missing_file(self, tmp_path: Path) -> None:
        """Test load_or_create creates new state when file missing."""
        state_file = tmp_path / "missing.json"

        state = RalphState.load_or_create(state_file)

        assert state.total_iterations == 0
        assert state.cost_usd == 0.0
        assert state.current_phase == 1

    def test_json_format(self, tmp_path: Path) -> None:
        """Test JSON file is properly formatted."""
        state_file = tmp_path / "state.json"
        state = RalphState(total_iterations=5)
        state.save(state_file)

        # Read raw JSON to verify format
        with open(state_file) as f:
            data = json.load(f)

        assert "total_iterations" in data
        assert "cost_usd" in data
        assert "started_at" in data
        assert "updated_at" in data


class TestUtcTimestamp:
    """Tests for _utc_timestamp helper function."""

    def test_timestamp_format(self) -> None:
        """Test timestamp is in correct ISO 8601 format."""
        timestamp = _utc_timestamp()

        # Should end with Z for UTC
        assert timestamp.endswith("Z")

        # Should be parseable as datetime
        # Format: 2024-01-13T10:30:45Z
        assert len(timestamp) == 20
        assert timestamp[4] == "-"
        assert timestamp[7] == "-"
        assert timestamp[10] == "T"
        assert timestamp[13] == ":"
        assert timestamp[16] == ":"

    def test_timestamp_uniqueness(self) -> None:
        """Test consecutive timestamps are different (or at least can be)."""
        timestamp1 = _utc_timestamp()
        timestamp2 = _utc_timestamp()

        # They might be the same if called in same second, but format should be valid
        assert isinstance(timestamp1, str)
        assert isinstance(timestamp2, str)
        assert timestamp1.endswith("Z")
        assert timestamp2.endswith("Z")
