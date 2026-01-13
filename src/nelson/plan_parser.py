"""Plan file parser for tracking task status in Nelson's plan.md files.

This module provides utilities to parse plan.md files, extract tasks by phase,
and track task completion status. It supports the markdown format used by Nelson:

    ## Phase N: PHASE_NAME
    - [x] Completed task
    - [ ] Unchecked task
    - [~] Skipped task

The parser handles:
- Phase section detection
- Task checkbox state tracking ([x], [ ], [~])
- Task counting per phase
- Overall completion tracking
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    """Task completion status from checkbox state."""

    COMPLETE = "x"  # [x] - Task is complete
    INCOMPLETE = " "  # [ ] - Task is not yet started
    SKIPPED = "~"  # [~] - Task is skipped


@dataclass(frozen=True)
class Task:
    """A single task from the plan file."""

    line_number: int
    status: TaskStatus
    content: str
    phase: int | None  # None if task is not under a phase header


@dataclass(frozen=True)
class PhaseTaskSummary:
    """Summary of tasks for a specific phase."""

    phase: int
    phase_name: str
    total_tasks: int
    complete_tasks: int
    incomplete_tasks: int
    skipped_tasks: int

    @property
    def is_complete(self) -> bool:
        """True if all tasks are complete or skipped (no incomplete tasks)."""
        return self.incomplete_tasks == 0

    @property
    def completion_percentage(self) -> float:
        """Percentage of non-skipped tasks that are complete."""
        if self.total_tasks == 0:
            return 100.0
        non_skipped = self.total_tasks - self.skipped_tasks
        if non_skipped == 0:
            return 100.0
        return (self.complete_tasks / non_skipped) * 100.0


class PlanParser:
    """Parser for Nelson's plan.md files."""

    # Regex patterns for parsing
    PHASE_HEADER_PATTERN = re.compile(r"^##\s+Phase\s+(\d+):\s+(.+)$")
    TASK_PATTERN = re.compile(r"^-\s+\[([x ~])\]\s+(.+)$")

    def __init__(self, plan_file: Path) -> None:
        """Initialize parser with path to plan.md file.

        Args:
            plan_file: Path to plan.md file
        """
        self.plan_file = plan_file
        self._tasks: list[Task] = []
        self._current_phase: int | None = None
        self._current_phase_name: str | None = None

    def parse(self) -> list[Task]:
        """Parse the plan file and return all tasks.

        Returns:
            List of Task objects in order of appearance

        Raises:
            FileNotFoundError: If plan file doesn't exist
        """
        if not self.plan_file.exists():
            raise FileNotFoundError(f"Plan file not found: {self.plan_file}")

        self._tasks = []
        self._current_phase = None
        self._current_phase_name = None

        with self.plan_file.open() as f:
            for line_number, line in enumerate(f, start=1):
                line = line.rstrip()
                self._parse_line(line, line_number)

        return self._tasks

    def _parse_line(self, line: str, line_number: int) -> None:
        """Parse a single line from the plan file.

        Args:
            line: The line content
            line_number: Line number in file
        """
        # Check for phase header
        phase_match = self.PHASE_HEADER_PATTERN.match(line)
        if phase_match:
            self._current_phase = int(phase_match.group(1))
            self._current_phase_name = phase_match.group(2).strip()
            return

        # Check for task
        task_match = self.TASK_PATTERN.match(line)
        if task_match:
            status_char = task_match.group(1)
            content = task_match.group(2).strip()

            # Map checkbox character to TaskStatus
            if status_char == "x":
                status = TaskStatus.COMPLETE
            elif status_char == "~":
                status = TaskStatus.SKIPPED
            else:
                status = TaskStatus.INCOMPLETE

            task = Task(
                line_number=line_number,
                status=status,
                content=content,
                phase=self._current_phase,
            )
            self._tasks.append(task)

    def get_tasks_by_phase(self, phase: int) -> list[Task]:
        """Get all tasks for a specific phase.

        Args:
            phase: Phase number (1-6)

        Returns:
            List of tasks in the specified phase
        """
        return [task for task in self._tasks if task.phase == phase]

    def get_phase_summary(self, phase: int) -> PhaseTaskSummary | None:
        """Get summary statistics for a specific phase.

        Args:
            phase: Phase number (1-6)

        Returns:
            PhaseTaskSummary or None if phase has no tasks
        """
        tasks = self.get_tasks_by_phase(phase)
        if not tasks:
            return None

        complete = sum(1 for t in tasks if t.status == TaskStatus.COMPLETE)
        incomplete = sum(1 for t in tasks if t.status == TaskStatus.INCOMPLETE)
        skipped = sum(1 for t in tasks if t.status == TaskStatus.SKIPPED)

        # Find phase name from first task (all tasks in phase have same phase context)
        phase_name = f"Phase {phase}"  # Default
        # We need to search the file for the phase name
        if self.plan_file.exists():
            with self.plan_file.open() as f:
                for line in f:
                    match = self.PHASE_HEADER_PATTERN.match(line.rstrip())
                    if match and int(match.group(1)) == phase:
                        phase_name = match.group(2).strip()
                        break

        return PhaseTaskSummary(
            phase=phase,
            phase_name=phase_name,
            total_tasks=len(tasks),
            complete_tasks=complete,
            incomplete_tasks=incomplete,
            skipped_tasks=skipped,
        )

    def get_all_phase_summaries(self) -> list[PhaseTaskSummary]:
        """Get summary statistics for all phases.

        Returns:
            List of PhaseTaskSummary objects, one per phase that has tasks
        """
        phases = sorted(set(t.phase for t in self._tasks if t.phase is not None))
        summaries = []
        for phase in phases:
            summary = self.get_phase_summary(phase)
            if summary:
                summaries.append(summary)
        return summaries

    def has_unchecked_tasks(self, phase: int) -> bool:
        """Check if a phase has any unchecked (incomplete) tasks.

        Args:
            phase: Phase number (1-6)

        Returns:
            True if phase has at least one incomplete task
        """
        tasks = self.get_tasks_by_phase(phase)
        return any(t.status == TaskStatus.INCOMPLETE for t in tasks)

    def get_first_unchecked_task(self, phase: int) -> Task | None:
        """Get the first unchecked task in a phase.

        Args:
            phase: Phase number (1-6)

        Returns:
            First incomplete task or None if all tasks are complete/skipped
        """
        tasks = self.get_tasks_by_phase(phase)
        for task in tasks:
            if task.status == TaskStatus.INCOMPLETE:
                return task
        return None

    def count_tasks_completed_recently(self, recent_lines: int = 5) -> int:
        """Count how many tasks were recently marked complete.

        This is useful for detecting progress in the workflow. We look at the
        last N tasks in the file and count how many are marked complete.

        Args:
            recent_lines: Number of recent tasks to check

        Returns:
            Number of recently completed tasks
        """
        if not self._tasks:
            return 0

        recent_tasks = self._tasks[-recent_lines:]
        return sum(1 for t in recent_tasks if t.status == TaskStatus.COMPLETE)


def load_plan(plan_file: Path) -> PlanParser:
    """Load and parse a plan file.

    Args:
        plan_file: Path to plan.md

    Returns:
        Parsed PlanParser instance
    """
    parser = PlanParser(plan_file)
    parser.parse()
    return parser
