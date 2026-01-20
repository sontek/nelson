"""Overall PRD state management for nelson-prd.

This module handles orchestration-level state tracking across all tasks
in a PRD, including task mapping, aggregate metrics, and coordination.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nelson.prd_task_state import TaskState, TaskStatus


@dataclass
class TaskMapping:
    """Mapping information for a PRD task."""

    original_text: str  # Original task description
    priority: str  # "high", "medium", "low"
    line_number: int  # Line number in PRD file


@dataclass
class TaskSummary:
    """Summary of task state for PRD-level tracking."""

    status: str  # TaskStatus value
    cost_usd: float = 0.0


@dataclass
class PRDState:
    """Overall state for PRD orchestration.

    Stored at .nelson/prd/prd-state.json with high-level tracking
    and task mapping information.
    """

    # PRD file tracking
    prd_file: str  # Path to PRD markdown file

    # Timestamps
    started_at: str = field(default_factory=lambda: _utc_timestamp())
    updated_at: str = field(default_factory=lambda: _utc_timestamp())

    # Cost tracking
    total_cost_usd: float = 0.0

    # Task mapping: task_id -> mapping info
    task_mapping: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Task summaries: task_id -> summary
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Current execution state
    current_task_id: str | None = None

    # Aggregate counts
    completed_count: int = 0
    in_progress_count: int = 0
    blocked_count: int = 0
    pending_count: int = 0
    failed_count: int = 0

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = _utc_timestamp()

    def add_task(self, task_id: str, task_text: str, priority: str, line_number: int) -> None:
        """Add a new task to the mapping.

        Args:
            task_id: Task ID (e.g., "PRD-001")
            task_text: Task description
            priority: Task priority ("high", "medium", "low")
            line_number: Line number in PRD file
        """
        self.task_mapping[task_id] = {
            "original_text": task_text,
            "priority": priority,
            "line_number": line_number,
        }
        self.tasks[task_id] = {"status": TaskStatus.PENDING.value, "cost_usd": 0.0}
        self.pending_count += 1
        self.update_timestamp()

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status and recalculate counts.

        Args:
            task_id: Task ID
            status: New status
        """
        if task_id not in self.tasks:
            return

        # Get old status
        old_status_str = self.tasks[task_id]["status"]
        old_status = TaskStatus(old_status_str)

        # Decrement old status count
        self._decrement_status_count(old_status)

        # Update status
        self.tasks[task_id]["status"] = status.value

        # Increment new status count
        self._increment_status_count(status)

        self.update_timestamp()

    def update_task_cost(self, task_id: str, cost_usd: float) -> None:
        """Update task cost and recalculate total.

        Args:
            task_id: Task ID
            cost_usd: New total cost for task
        """
        if task_id not in self.tasks:
            return

        old_cost = self.tasks[task_id]["cost_usd"]
        self.tasks[task_id]["cost_usd"] = cost_usd
        self.total_cost_usd += cost_usd - old_cost
        self.update_timestamp()

    def set_current_task(self, task_id: str | None) -> None:
        """Set the currently executing task.

        Args:
            task_id: Task ID or None if no task is executing
        """
        self.current_task_id = task_id
        self.update_timestamp()

    def _increment_status_count(self, status: TaskStatus) -> None:
        """Increment count for given status."""
        if status == TaskStatus.PENDING:
            self.pending_count += 1
        elif status == TaskStatus.IN_PROGRESS:
            self.in_progress_count += 1
        elif status == TaskStatus.BLOCKED:
            self.blocked_count += 1
        elif status == TaskStatus.COMPLETED:
            self.completed_count += 1
        elif status == TaskStatus.FAILED:
            self.failed_count += 1

    def _decrement_status_count(self, status: TaskStatus) -> None:
        """Decrement count for given status."""
        if status == TaskStatus.PENDING:
            self.pending_count = max(0, self.pending_count - 1)
        elif status == TaskStatus.IN_PROGRESS:
            self.in_progress_count = max(0, self.in_progress_count - 1)
        elif status == TaskStatus.BLOCKED:
            self.blocked_count = max(0, self.blocked_count - 1)
        elif status == TaskStatus.COMPLETED:
            self.completed_count = max(0, self.completed_count - 1)
        elif status == TaskStatus.FAILED:
            self.failed_count = max(0, self.failed_count - 1)

    def get_task_ids_by_status(self, status: TaskStatus) -> list[str]:
        """Get all task IDs with given status.

        Args:
            status: Status to filter by

        Returns:
            List of task IDs
        """
        return [task_id for task_id, task in self.tasks.items() if task["status"] == status.value]

    def get_task_ids_by_priority(
        self, priority: str, status: TaskStatus | None = None
    ) -> list[str]:
        """Get task IDs by priority, optionally filtered by status.

        Args:
            priority: Priority level ("high", "medium", "low")
            status: Optional status filter

        Returns:
            List of task IDs
        """
        matching_ids = [
            task_id
            for task_id, mapping in self.task_mapping.items()
            if mapping["priority"] == priority
        ]

        if status is not None:
            matching_ids = [
                task_id for task_id in matching_ids if self.tasks[task_id]["status"] == status.value
            ]

        return matching_ids

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of state
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PRDState":
        """Create state from dictionary.

        Args:
            data: Dictionary from JSON deserialization

        Returns:
            PRDState instance
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
    def load(cls, path: Path) -> "PRDState":
        """Load state from JSON file.

        Args:
            path: Path to state file

        Returns:
            PRDState instance

        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_or_create(cls, path: Path, prd_file: str) -> "PRDState":
        """Load state from file, or create new state if file doesn't exist.

        Args:
            path: Path to state file
            prd_file: Path to PRD markdown file

        Returns:
            PRDState instance (loaded or newly created)
        """
        if path.exists():
            return cls.load(path)
        return cls(prd_file=prd_file)


class PRDStateManager:
    """Manages PRD state and task state coordination.

    Coordinates updates between overall PRD state and individual task states,
    ensuring consistency across the state tree.
    """

    def __init__(self, prd_dir: Path, prd_file: str):
        """Initialize state manager.

        Args:
            prd_dir: Path to .nelson/prd directory
            prd_file: Path to PRD markdown file
        """
        self.prd_dir = prd_dir
        self.prd_state_path = prd_dir / "prd-state.json"
        self.prd_state = PRDState.load_or_create(self.prd_state_path, prd_file)

    def get_task_state_path(self, task_id: str) -> Path:
        """Get path to task state file.

        Args:
            task_id: Task ID (e.g., "PRD-001")

        Returns:
            Path to task state JSON file
        """
        return self.prd_dir / task_id / "state.json"

    def load_task_state(self, task_id: str, task_text: str, priority: str) -> TaskState:
        """Load or create task state.

        Args:
            task_id: Task ID
            task_text: Task description
            priority: Task priority

        Returns:
            TaskState instance
        """
        path = self.get_task_state_path(task_id)
        return TaskState.load_or_create(path, task_id, task_text, priority)

    def save_task_state(self, task_state: TaskState) -> None:
        """Save task state and update PRD state.

        Args:
            task_state: TaskState to save
        """
        # Save task state
        path = self.get_task_state_path(task_state.task_id)
        task_state.save(path)

        # Update PRD state with task status and cost
        self.prd_state.update_task_status(task_state.task_id, task_state.status)
        self.prd_state.update_task_cost(task_state.task_id, task_state.cost_usd)
        self.save_prd_state()

    def save_prd_state(self) -> None:
        """Save PRD state to disk."""
        self.prd_state.save(self.prd_state_path)

    def start_task(
        self, task_id: str, task_text: str, priority: str, nelson_run_id: str, branch: str
    ) -> TaskState:
        """Start a task and update state.

        Args:
            task_id: Task ID
            task_text: Task description
            priority: Task priority
            nelson_run_id: Nelson run ID
            branch: Git branch name

        Returns:
            Updated TaskState
        """
        task_state = self.load_task_state(task_id, task_text, priority)
        task_state.start(nelson_run_id, branch)
        self.prd_state.set_current_task(task_id)
        self.save_task_state(task_state)
        return task_state

    def complete_task(self, task_id: str) -> TaskState:
        """Mark task as completed.

        Args:
            task_id: Task ID

        Returns:
            Updated TaskState
        """
        task_state = TaskState.load(self.get_task_state_path(task_id))
        task_state.complete()
        self.save_task_state(task_state)
        return task_state

    def fail_task(self, task_id: str) -> TaskState:
        """Mark task as failed.

        Args:
            task_id: Task ID

        Returns:
            Updated TaskState
        """
        task_state = TaskState.load(self.get_task_state_path(task_id))
        task_state.fail()
        self.save_task_state(task_state)
        return task_state

    def block_task(self, task_id: str, task_text: str, priority: str, reason: str) -> TaskState:
        """Block a task with reason.

        Args:
            task_id: Task ID
            task_text: Task description
            priority: Task priority
            reason: Blocking reason

        Returns:
            Updated TaskState
        """
        task_state = self.load_task_state(task_id, task_text, priority)
        task_state.block(reason)
        self.save_task_state(task_state)
        return task_state

    def unblock_task(
        self, task_id: str, task_text: str, priority: str, context: str | None = None
    ) -> TaskState:
        """Unblock a task with optional resume context.

        Args:
            task_id: Task ID
            task_text: Task description
            priority: Task priority
            context: Optional resume context

        Returns:
            Updated TaskState
        """
        task_state = self.load_task_state(task_id, task_text, priority)
        task_state.unblock(context)
        self.save_task_state(task_state)
        return task_state

    def get_next_task(self) -> tuple[str, TaskState] | None:
        """Get next pending task by priority.

        Returns:
            Tuple of (task_id, task_state) or None if no pending tasks
        """
        # Check priorities in order: high, medium, low
        for priority in ["high", "medium", "low"]:
            task_ids = self.prd_state.get_task_ids_by_priority(priority, TaskStatus.PENDING)
            if task_ids:
                # Return first pending task in this priority
                task_id = task_ids[0]
                mapping = self.prd_state.task_mapping[task_id]
                task_state = self.load_task_state(task_id, mapping["original_text"], priority)
                return (task_id, task_state)

        return None

    def get_all_task_states(self) -> dict[str, TaskState]:
        """Load all task states.

        Returns:
            Dictionary mapping task_id to TaskState
        """
        states = {}
        for task_id, mapping in self.prd_state.task_mapping.items():
            task_state = self.load_task_state(
                task_id, mapping["original_text"], mapping["priority"]
            )
            states[task_id] = task_state
        return states


def _utc_timestamp() -> str:
    """Generate UTC timestamp in ISO 8601 format.

    Returns:
        Timestamp string like "2024-01-13T14:30:45Z"
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
