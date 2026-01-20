"""Task state management for nelson-prd.

This module handles per-task state tracking for PRD orchestration,
including status, cost, branch information, and blocking context.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(Enum):
    """Status of a PRD task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskState:
    """State for a single PRD task.

    Each task gets its own state file at .nelson/prd/PRD-NNN/state.json
    with comprehensive tracking of execution, cost, and blocking information.
    """

    # Task identification
    task_id: str  # e.g., "PRD-001"
    task_text: str  # Full task description
    status: TaskStatus = TaskStatus.PENDING
    priority: str = ""  # "high", "medium", "low"

    # Git tracking
    branch: str | None = None  # Branch name for this task
    base_branch: str | None = None  # Base branch this was created from
    branch_reason: str | None = None  # Why this branch/base was chosen

    # Blocking and resume
    blocking_reason: str | None = None  # Why task is blocked
    resume_context: str | None = None  # Context for resuming after unblock

    # Nelson run tracking
    nelson_run_id: str | None = None  # Links to .nelson/runs/<run-id>

    # Timestamps
    started_at: str | None = None
    updated_at: str = field(default_factory=lambda: _utc_timestamp())
    completed_at: str | None = None
    blocked_at: str | None = None

    # Cost and iteration tracking
    cost_usd: float = 0.0
    iterations: int = 0

    # Phase tracking from Nelson
    phase: int | None = None
    phase_name: str | None = None

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = _utc_timestamp()

    def start(
        self,
        nelson_run_id: str,
        branch: str | None = None,
        base_branch: str | None = None,
        branch_reason: str | None = None,
    ) -> None:
        """Mark task as started.

        Args:
            nelson_run_id: ID of the Nelson run executing this task
            branch: Git branch name for this task (optional, will be detected if not provided)
            base_branch: Base branch this was created from (optional)
            branch_reason: Why this branch/base was chosen (optional)
        """
        self.status = TaskStatus.IN_PROGRESS
        self.nelson_run_id = nelson_run_id
        if branch:
            self.branch = branch
        if base_branch:
            self.base_branch = base_branch
        if branch_reason:
            self.branch_reason = branch_reason
        if self.started_at is None:
            self.started_at = _utc_timestamp()
        self.update_timestamp()

    def complete(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = _utc_timestamp()
        self.update_timestamp()

    def fail(self) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.update_timestamp()

    def block(self, reason: str) -> None:
        """Mark task as blocked.

        Args:
            reason: Why the task is blocked
        """
        self.status = TaskStatus.BLOCKED
        self.blocking_reason = reason
        self.blocked_at = _utc_timestamp()
        self.update_timestamp()

    def unblock(self, context: str | None = None) -> None:
        """Mark task as unblocked and ready to resume.

        Args:
            context: Optional context for resuming the task
        """
        self.status = TaskStatus.PENDING
        self.blocking_reason = None  # Clear the blocking reason
        if context:
            self.resume_context = context
        # Keep blocked_at for history, but task is now unblocked
        self.update_timestamp()

    def update_cost(self, additional_cost: float) -> None:
        """Add to task cost.

        Args:
            additional_cost: Cost in USD to add
        """
        self.cost_usd += additional_cost
        self.update_timestamp()

    def update_phase(self, phase: int, phase_name: str) -> None:
        """Update phase tracking from Nelson.

        Args:
            phase: Phase number (1-6)
            phase_name: Phase name (e.g., "PLAN", "IMPLEMENT")
        """
        self.phase = phase
        self.phase_name = phase_name
        self.update_timestamp()

    def increment_iterations(self, count: int = 1) -> None:
        """Increment iteration counter.

        Args:
            count: Number of iterations to add
        """
        self.iterations += count
        self.update_timestamp()

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization.

        Returns:
            Dictionary representation of state
        """
        data = asdict(self)
        # Convert enum to string
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        """Create state from dictionary.

        Args:
            data: Dictionary from JSON deserialization

        Returns:
            TaskState instance
        """
        # Convert status string to enum
        if "status" in data and isinstance(data["status"], str):
            data["status"] = TaskStatus(data["status"])

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
    def load(cls, path: Path) -> "TaskState":
        """Load state from JSON file.

        Args:
            path: Path to state file

        Returns:
            TaskState instance

        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_or_create(cls, path: Path, task_id: str, task_text: str, priority: str) -> "TaskState":
        """Load state from file, or create new state if file doesn't exist.

        Args:
            path: Path to state file
            task_id: Task ID (e.g., "PRD-001")
            task_text: Task description
            priority: Task priority ("high", "medium", "low")

        Returns:
            TaskState instance (loaded or newly created)
        """
        if path.exists():
            return cls.load(path)
        return cls(task_id=task_id, task_text=task_text, priority=priority)


def _utc_timestamp() -> str:
    """Generate UTC timestamp in ISO 8601 format.

    Returns:
        Timestamp string like "2024-01-13T14:30:45Z"
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
