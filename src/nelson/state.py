"""State management for Nelson orchestration.

This module handles JSON state persistence for tracking iterations, cost, phase,
and circuit breaker metrics across Nelson runs. State is saved to disk after each
iteration to enable resumption.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class NelsonState:
    """State for Nelson orchestration session.

    This state is persisted to disk after each iteration and can be loaded
    to resume a previous run.
    """

    # Iteration tracking
    cycle_iterations: int = 0  # Complete 6-phase cycles (0 = first cycle)
    total_iterations: int = 0
    phase_iterations: int = 0  # Iterations in current phase

    # Cost tracking
    cost_usd: float = 0.0

    # Timestamps
    started_at: str = field(default_factory=lambda: _utc_timestamp())
    updated_at: str = field(default_factory=lambda: _utc_timestamp())

    # Original task prompt
    prompt: str = ""

    # Git tracking
    starting_commit: str = ""

    # Circuit breaker state
    last_completed_count: int = 0  # Number of completed tasks from last status block
    no_progress_iterations: int = 0  # Consecutive iterations with zero progress
    last_error_message: str = ""  # Last error encountered
    repeated_error_count: int = 0  # Count of repeated identical errors
    test_only_loop_count: int = 0  # Count of consecutive test-only iterations
    same_phase_loop_count: int = 0  # Count of consecutive iterations in same phase
    last_phase_tracked: int = 1  # Last phase we tracked for loop detection
    no_work_cycles: int = 0  # Count of consecutive cycles with "no implementation work"
    blocked_iterations: int = 0  # Consecutive iterations with BLOCKED status

    # Phase tracking
    current_phase: int = 1
    phase_name: str = "PLAN"

    # Exit tracking
    exit_signal_received: bool = False

    # Deviation tracking
    deviations: list[dict[str, Any]] = field(default_factory=list)

    def increment_iteration(self) -> None:
        """Increment both total and phase iteration counters."""
        self.total_iterations += 1
        self.phase_iterations += 1
        self.update_timestamp()

    def reset_phase_iterations(self) -> None:
        """Reset phase iteration counter (called on phase transition)."""
        self.phase_iterations = 0

    def increment_cycle(self) -> None:
        """Increment cycle counter (called after Phase 6 completion)."""
        self.cycle_iterations += 1
        self.update_timestamp()

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = _utc_timestamp()

    def update_cost(self, additional_cost: float) -> None:
        """Add to cumulative cost and update timestamp.

        Args:
            additional_cost: Cost in USD to add to total
        """
        self.cost_usd += additional_cost
        self.update_timestamp()

    def record_progress(self, completed_count: int) -> None:
        """Record progress from status block.

        Updates circuit breaker state based on whether progress was made.

        Args:
            completed_count: Number of completed tasks from status block
        """
        if completed_count > self.last_completed_count:
            # Progress was made, reset no-progress counter
            self.no_progress_iterations = 0
            self.last_completed_count = completed_count
        else:
            # No progress, increment counter
            self.no_progress_iterations += 1
        self.update_timestamp()

    def record_error(self, error_message: str) -> None:
        """Record an error for circuit breaker tracking.

        If the error is identical to the last error, increment repeated count.
        Otherwise, reset to 1.

        Args:
            error_message: Error message to record
        """
        if error_message == self.last_error_message:
            self.repeated_error_count += 1
        else:
            self.last_error_message = error_message
            self.repeated_error_count = 1
        self.update_timestamp()

    def record_test_only_iteration(self) -> None:
        """Increment test-only loop counter for circuit breaker."""
        self.test_only_loop_count += 1
        self.update_timestamp()

    def reset_test_only_counter(self) -> None:
        """Reset test-only loop counter (called when non-test work happens)."""
        self.test_only_loop_count = 0

    def transition_phase(self, new_phase: int, phase_name: str) -> None:
        """Transition to a new phase.

        Args:
            new_phase: Phase number (1-6)
            phase_name: Human-readable phase name
        """
        self.current_phase = new_phase
        self.phase_name = phase_name
        self.reset_phase_iterations()
        self.update_timestamp()

    def record_deviation(self, deviation_dict: dict[str, Any]) -> None:
        """Record a deviation that was applied.

        Args:
            deviation_dict: Serialized Deviation object
        """
        self.deviations.append(deviation_dict)
        self.update_timestamp()

    def get_task_deviation_count(self, task_id: str | None) -> int:
        """Get number of deviations for a specific task.

        Args:
            task_id: Task ID to count deviations for, or None for all

        Returns:
            Number of deviations for the task
        """
        if task_id is None:
            return len(self.deviations)
        return sum(1 for d in self.deviations if d.get("task_id") == task_id)

    def get_all_deviations(self) -> list[dict[str, Any]]:
        """Get all recorded deviations.

        Returns:
            List of deviation dictionaries
        """
        return list(self.deviations)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of state
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NelsonState":
        """Create state from dictionary.

        Args:
            data: Dictionary from JSON deserialization

        Returns:
            NelsonState instance
        """
        # Filter out any keys that aren't valid fields
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

    def save(self, path: Path) -> None:
        """Save state to JSON file.

        Args:
            path: Path to state file
        """
        self.update_timestamp()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "NelsonState":
        """Load state from JSON file.

        Args:
            path: Path to state file

        Returns:
            NelsonState instance

        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_or_create(cls, path: Path) -> "NelsonState":
        """Load state from file, or create new state if file doesn't exist.

        Args:
            path: Path to state file

        Returns:
            NelsonState instance (loaded or newly created)
        """
        if path.exists():
            return cls.load(path)
        return cls()


def _utc_timestamp() -> str:
    """Generate UTC timestamp in ISO 8601 format.

    Returns:
        Timestamp string like "2024-01-13T14:30:45Z"
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
