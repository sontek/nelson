"""Plan models for structured task representation.

This module provides dataclasses for representing plans and tasks in a structured
JSON format that enables explicit verification criteria, dependency tracking,
and wave computation for parallel execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nelson.verification import GoalVerification


class TaskStatus(Enum):
    """Status of a task in the plan."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """A single task in a plan.

    Attributes:
        id: Unique identifier for the task (e.g., "02-01")
        name: Human-readable task name
        wave: Execution wave (tasks in same wave can run in parallel)
        depends_on: List of task IDs this task depends on
        files: List of files this task will create/modify
        action: Description of what needs to be done
        verify: Optional command to verify task completion
        done_when: Description of completion criteria
        status: Current status of the task
    """

    id: str
    name: str
    wave: int
    depends_on: list[str]
    files: list[str]
    action: str
    verify: str | None
    done_when: str
    status: TaskStatus = TaskStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "wave": self.wave,
            "depends_on": self.depends_on,
            "files": self.files,
            "action": self.action,
            "verify": self.verify,
            "done_when": self.done_when,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create task from dictionary."""
        status_str = data.get("status", "pending")
        try:
            status = TaskStatus(status_str)
        except ValueError:
            status = TaskStatus.PENDING

        return cls(
            id=data["id"],
            name=data["name"],
            wave=data.get("wave", 1),
            depends_on=data.get("depends_on", []),
            files=data.get("files", []),
            action=data["action"],
            verify=data.get("verify"),
            done_when=data["done_when"],
            status=status,
        )

    def is_ready(self, completed_ids: set[str]) -> bool:
        """Check if task is ready to execute (all dependencies completed)."""
        return all(dep_id in completed_ids for dep_id in self.depends_on)


@dataclass
class Plan:
    """A structured plan containing tasks.

    Attributes:
        phase: Phase number for this plan
        name: Human-readable plan name
        goal: Description of what this plan aims to achieve
        tasks: List of tasks in the plan
        verification: Optional goal-backward verification spec
    """

    phase: int
    name: str
    goal: str
    tasks: list[Task] = field(default_factory=list)
    verification: GoalVerification | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary for JSON serialization."""
        data = {
            "phase": self.phase,
            "name": self.name,
            "goal": self.goal,
            "tasks": [task.to_dict() for task in self.tasks],
        }
        if self.verification is not None:
            data["verification"] = self.verification.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        """Create plan from dictionary."""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]

        verification = None
        if "verification" in data:
            from nelson.verification import GoalVerification

            verification = GoalVerification.from_dict(data["verification"])

        return cls(
            phase=data.get("phase", 1),
            name=data["name"],
            goal=data.get("goal", ""),
            tasks=tasks,
            verification=verification,
        )

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: The task ID to find

        Returns:
            Task if found, None otherwise
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def mark_completed(self, task_id: str) -> bool:
        """Mark a task as completed.

        Args:
            task_id: The task ID to mark complete

        Returns:
            True if task was found and marked, False otherwise
        """
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            return True
        return False

    def mark_skipped(self, task_id: str) -> bool:
        """Mark a task as skipped.

        Args:
            task_id: The task ID to mark skipped

        Returns:
            True if task was found and marked, False otherwise
        """
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.SKIPPED
            return True
        return False

    def mark_in_progress(self, task_id: str) -> bool:
        """Mark a task as in progress.

        Args:
            task_id: The task ID to mark in progress

        Returns:
            True if task was found and marked, False otherwise
        """
        task = self.get_task(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            return True
        return False

    def get_pending_tasks(self) -> list[Task]:
        """Get all tasks that are pending."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    def get_completed_ids(self) -> set[str]:
        """Get set of completed task IDs."""
        return {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}

    def get_next_wave(self) -> list[Task] | None:
        """Get tasks in the next executable wave.

        Returns the lowest-wave tasks that are pending and have all
        dependencies completed.

        Returns:
            List of ready tasks, or None if no tasks are ready
        """
        completed_ids = self.get_completed_ids()
        pending = self.get_pending_tasks()

        if not pending:
            return None

        # Find ready tasks
        ready_tasks = [t for t in pending if t.is_ready(completed_ids)]

        if not ready_tasks:
            return None

        # Return only tasks in the lowest wave
        min_wave = min(t.wave for t in ready_tasks)
        return [t for t in ready_tasks if t.wave == min_wave]

    def is_complete(self) -> bool:
        """Check if all tasks are completed or skipped."""
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for t in self.tasks)

    def completion_percentage(self) -> float:
        """Calculate completion percentage.

        Returns:
            Percentage (0.0 to 100.0) of tasks completed or skipped
        """
        if not self.tasks:
            return 100.0

        done_count = sum(
            1 for t in self.tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        )
        return (done_count / len(self.tasks)) * 100.0


class WaveComputationError(Exception):
    """Error during wave computation (e.g., circular dependency)."""

    pass


def compute_waves(tasks: list[Task]) -> dict[int, list[Task]]:
    """Compute wave assignments from task dependencies.

    Uses topological sort to assign waves:
    - Tasks with no dependencies are wave 1
    - Tasks depending only on wave N tasks are wave N+1

    Args:
        tasks: List of tasks with dependencies

    Returns:
        Dictionary mapping wave number to list of tasks

    Raises:
        WaveComputationError: If circular dependencies detected
    """
    if not tasks:
        return {}

    # Build dependency graph
    task_map = {t.id: t for t in tasks}
    in_degree: dict[str, int] = {t.id: 0 for t in tasks}
    dependents: dict[str, list[str]] = {t.id: [] for t in tasks}

    for task in tasks:
        for dep_id in task.depends_on:
            if dep_id in task_map:
                in_degree[task.id] += 1
                dependents[dep_id].append(task.id)

    # Kahn's algorithm for topological sort with wave tracking
    waves: dict[int, list[Task]] = {}
    task_waves: dict[str, int] = {}
    processed = 0

    # Start with tasks having no dependencies
    current_wave = 1
    current_level = [tid for tid, deg in in_degree.items() if deg == 0]

    while current_level:
        waves[current_wave] = []
        next_level = []

        for task_id in current_level:
            task = task_map[task_id]
            task.wave = current_wave
            task_waves[task_id] = current_wave
            waves[current_wave].append(task)
            processed += 1

            # Reduce in-degree for dependents
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    next_level.append(dependent_id)

        current_level = next_level
        current_wave += 1

    # Check for circular dependencies
    if processed != len(tasks):
        unprocessed = [t.id for t in tasks if t.id not in task_waves]
        raise WaveComputationError(f"Circular dependency detected involving tasks: {unprocessed}")

    return waves
