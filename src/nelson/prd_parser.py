"""PRD file parser for nelson-prd markdown files.

This module provides utilities to parse PRD markdown files with explicit
task IDs, extract tasks by priority, validate task IDs, and update status
indicators in the PRD file.

Supported format:
    ## High Priority
    - [ ] PRD-001 Add user authentication
    - [~] PRD-002 Create user profile (in progress)
    - [x] PRD-003 Add payment integration (completed)
    - [!] PRD-004 Add email notifications (blocked: waiting for API keys)

The parser handles:
- Task ID validation (PRD-NNN format)
- Duplicate ID detection
- Status indicator parsing ([ ], [~], [x], [!])
- Priority section parsing (High/Medium/Low)
- Blocking reason extraction
- PRD file updates with status changes
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class PRDTaskStatus(Enum):
    """Task status from checkbox indicator."""

    PENDING = " "  # [ ] - Task not started
    IN_PROGRESS = "~"  # [~] - Task in progress
    COMPLETED = "x"  # [x] - Task completed
    BLOCKED = "!"  # [!] - Task blocked


@dataclass(frozen=True)
class PRDTask:
    """A single task from the PRD file."""

    line_number: int  # Line number in file (1-indexed)
    task_id: str  # e.g., "PRD-001"
    task_text: str  # Task description (without ID)
    status: PRDTaskStatus  # Current status
    priority: str  # "high", "medium", or "low"
    blocking_reason: str | None = None  # Reason if blocked


class PRDParser:
    """Parser for PRD markdown files with explicit task IDs."""

    # Regex patterns
    PRIORITY_HEADER_PATTERN = re.compile(
        r"^##\s+(High|Medium|Low)\s+Priority\s*$", re.IGNORECASE
    )
    TASK_PATTERN = re.compile(r"^-\s+\[([x~! ])\]\s+(PRD-\d+)\s+(.+)$")
    BLOCKING_REASON_PATTERN = re.compile(r"\(blocked:\s*(.+?)\)\s*$", re.IGNORECASE)

    # Backup configuration
    MAX_BACKUPS = 10  # Keep last N backups

    def __init__(self, prd_file: Path, backup_dir: Path | None = None) -> None:
        """Initialize parser with path to PRD file.

        Args:
            prd_file: Path to PRD markdown file
            backup_dir: Directory for backups (default: .nelson/prd/backups)
        """
        self.prd_file = prd_file
        self.backup_dir = backup_dir or Path(".nelson/prd/backups")
        self._tasks: list[PRDTask] = []
        self._current_priority: str | None = None
        self._task_ids: set[str] = set()

    def parse(self) -> list[PRDTask]:
        """Parse the PRD file and return all tasks.

        Returns:
            List of PRDTask objects in order of appearance

        Raises:
            FileNotFoundError: If PRD file doesn't exist
            ValueError: If validation fails (duplicate IDs, invalid format)
        """
        if not self.prd_file.exists():
            raise FileNotFoundError(
                f"PRD file not found: {self.prd_file}\n\n"
                f"Please create a PRD markdown file with tasks in format:\n"
                f"  ## High Priority\n"
                f"  - [ ] PRD-001 Task description"
            )

        self._tasks = []
        self._task_ids = set()
        self._current_priority = None
        errors: list[str] = []

        with open(self.prd_file) as f:
            lines = f.readlines()

        # Check for empty file
        content_lines = [line.strip() for line in lines if line.strip()]
        if not content_lines:
            raise ValueError(
                f"PRD file is empty: {self.prd_file}\n\n"
                f"Please add tasks in the following format:\n\n"
                f"  ## High Priority\n"
                f"  - [ ] PRD-001 Add user authentication\n"
                f"  - [ ] PRD-002 Create user profile\n\n"
                f"  ## Medium Priority\n"
                f"  - [ ] PRD-003 Add email notifications\n\n"
                f"See examples/sample-prd.md for a complete example."
            )

        # First pass: collect all errors
        for line_num, line in enumerate(lines, start=1):
            line = line.rstrip()

            # Check for priority header
            priority_match = self.PRIORITY_HEADER_PATTERN.match(line)
            if priority_match:
                self._current_priority = priority_match.group(1).lower()
                continue

            # Check for task
            task_match = self.TASK_PATTERN.match(line)
            if task_match:
                status_char = task_match.group(1)
                task_id = task_match.group(2)
                task_text = task_match.group(3)

                # Validate task ID
                if not self._is_valid_task_id(task_id):
                    errors.append(
                        f"Line {line_num}: Invalid task ID format '{task_id}'\n"
                        f"  Found: {line.strip()}\n"
                        f"  Expected format: PRD-NNN where NNN is exactly 3 digits (e.g., PRD-001, PRD-042)\n"
                        f"  Fix: Change '{task_id}' to format like 'PRD-001'"
                    )
                    continue

                # Check for duplicate ID
                if task_id in self._task_ids:
                    # Find the first occurrence
                    first_line = next(
                        (t.line_number for t in self._tasks if t.task_id == task_id),
                        None,
                    )
                    errors.append(
                        f"Line {line_num}: Duplicate task ID '{task_id}'\n"
                        f"  Current line: {line.strip()}\n"
                        f"  First used at line {first_line}\n"
                        f"  Fix: Change to a unique ID like '{self._suggest_next_id()}'"
                    )
                    continue

                self._task_ids.add(task_id)

                # Parse status
                status = self._parse_status(status_char)

                # Extract blocking reason if present
                blocking_reason = None
                if status == PRDTaskStatus.BLOCKED:
                    reason_match = self.BLOCKING_REASON_PATTERN.search(task_text)
                    if reason_match:
                        blocking_reason = reason_match.group(1).strip()
                        # Remove blocking reason from task text
                        task_text = self.BLOCKING_REASON_PATTERN.sub("", task_text).strip()

                # Require priority context
                if self._current_priority is None:
                    errors.append(
                        f"Line {line_num}: Task '{task_id}' found outside priority section\n"
                        f"  Found: {line.strip()}\n"
                        f"  Fix: Add a priority header before this task:\n"
                        f"    ## High Priority\n"
                        f"    {line.strip()}"
                    )
                    continue

                task = PRDTask(
                    line_number=line_num,
                    task_id=task_id,
                    task_text=task_text,
                    status=status,
                    priority=self._current_priority,
                    blocking_reason=blocking_reason,
                )
                self._tasks.append(task)

        # Check for tasks without IDs
        validation_errors = self.validate_all_tasks()
        if validation_errors:
            errors.extend(validation_errors)

        # If we collected any errors, raise them all together
        if errors:
            error_msg = (
                f"\nFound {len(errors)} validation error(s) in PRD file: {self.prd_file}\n\n"
                + "\n\n".join(errors)
                + "\n\nPlease fix these errors and try again."
            )
            raise ValueError(error_msg)

        return self._tasks

    def _is_valid_task_id(self, task_id: str) -> bool:
        """Validate task ID format (PRD-NNN).

        Args:
            task_id: Task ID to validate

        Returns:
            True if valid format
        """
        pattern = re.compile(r"^PRD-\d{3}$")
        return pattern.match(task_id) is not None

    def _suggest_next_id(self) -> str:
        """Suggest the next available task ID.

        Returns:
            Suggested task ID in format PRD-NNN
        """
        if not self._task_ids:
            return "PRD-001"

        # Extract numeric parts and find max
        max_num = 0
        for task_id in self._task_ids:
            match = re.match(r"PRD-(\d+)", task_id)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

        # Suggest next number with proper padding
        next_num = max_num + 1
        return f"PRD-{next_num:03d}"

    def _parse_status(self, status_char: str) -> PRDTaskStatus:
        """Parse status character to enum.

        Args:
            status_char: Character from checkbox ([x], [ ], [~], [!])

        Returns:
            PRDTaskStatus enum value
        """
        if status_char == "x":
            return PRDTaskStatus.COMPLETED
        elif status_char == "~":
            return PRDTaskStatus.IN_PROGRESS
        elif status_char == "!":
            return PRDTaskStatus.BLOCKED
        else:  # space or any other character defaults to pending
            return PRDTaskStatus.PENDING

    def get_tasks_by_priority(self, priority: str) -> list[PRDTask]:
        """Get all tasks for a given priority.

        Args:
            priority: Priority level ("high", "medium", or "low")

        Returns:
            List of tasks with that priority
        """
        return [t for t in self._tasks if t.priority == priority]

    def get_tasks_by_status(self, status: PRDTaskStatus) -> list[PRDTask]:
        """Get all tasks with a given status.

        Args:
            status: Task status to filter by

        Returns:
            List of tasks with that status
        """
        return [t for t in self._tasks if t.status == status]

    def get_task_by_id(self, task_id: str) -> PRDTask | None:
        """Get task by ID.

        Args:
            task_id: Task ID (e.g., "PRD-001")

        Returns:
            PRDTask if found, None otherwise
        """
        for task in self._tasks:
            if task.task_id == task_id:
                return task
        return None

    def _create_backup(self) -> None:
        """Create timestamped backup of PRD file.

        Backs up to backup_dir with timestamp in filename.
        Cleans up old backups to keep only MAX_BACKUPS most recent.

        Raises:
            IOError: If backup creation fails
        """
        if not self.prd_file.exists():
            return  # Nothing to backup

        # Create backup directory if needed
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped backup filename with microseconds for uniqueness
        now = datetime.now(UTC)
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        microseconds = now.strftime("%f")
        backup_name = f"{self.prd_file.stem}-{timestamp}-{microseconds}{self.prd_file.suffix}"
        backup_path = self.backup_dir / backup_name

        # Copy file to backup location
        shutil.copy2(self.prd_file, backup_path)

        # Clean up old backups
        self._cleanup_old_backups()

    def _cleanup_old_backups(self) -> None:
        """Remove old backup files, keeping only MAX_BACKUPS most recent."""
        if not self.backup_dir.exists():
            return

        # Find all backup files for this PRD
        pattern = f"{self.prd_file.stem}-*{self.prd_file.suffix}"
        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Remove oldest backups if we exceed MAX_BACKUPS
        for old_backup in backups[self.MAX_BACKUPS :]:
            try:
                old_backup.unlink()
            except OSError:
                # Ignore errors during cleanup
                pass

    def update_task_status(
        self,
        task_id: str,
        new_status: PRDTaskStatus,
        blocking_reason: str | None = None,
    ) -> None:
        """Update task status in PRD file.

        Reads the file, updates the status indicator for the specified task,
        and writes back atomically. Creates a timestamped backup before modification.

        Args:
            task_id: Task ID to update
            new_status: New status
            blocking_reason: Optional blocking reason (if status is BLOCKED)

        Raises:
            ValueError: If task ID not found
            IOError: If backup or file write fails
        """
        task = self.get_task_by_id(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        # Create backup before modification
        self._create_backup()

        # Read all lines
        with open(self.prd_file) as f:
            lines = f.readlines()

        # Update the task line
        line_idx = task.line_number - 1  # Convert to 0-indexed

        # Build new status indicator
        status_char = self._status_to_char(new_status)

        # Build new task text with blocking reason if needed
        task_text = task.task_text
        if new_status == PRDTaskStatus.BLOCKED and blocking_reason:
            task_text = f"{task_text} (blocked: {blocking_reason})"
        elif new_status != PRDTaskStatus.BLOCKED:
            # Remove any existing blocking reason
            task_text = self.BLOCKING_REASON_PATTERN.sub("", task_text).strip()

        # Build new line
        new_line = f"- [{status_char}] {task_id} {task_text}\n"
        lines[line_idx] = new_line

        # Write back atomically (write to temp, then rename)
        temp_file = self.prd_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as f:
                f.writelines(lines)
            temp_file.replace(self.prd_file)
        except Exception:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise

    def _status_to_char(self, status: PRDTaskStatus) -> str:
        """Convert status enum to checkbox character.

        Args:
            status: PRDTaskStatus enum

        Returns:
            Character for checkbox
        """
        if status == PRDTaskStatus.COMPLETED:
            return "x"
        elif status == PRDTaskStatus.IN_PROGRESS:
            return "~"
        elif status == PRDTaskStatus.BLOCKED:
            return "!"
        else:
            return " "

    def validate_all_tasks(self) -> list[str]:
        """Validate all tasks and return list of issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []

        # Check for tasks without IDs
        with open(self.prd_file) as f:
            lines = f.readlines()

        task_line_pattern = re.compile(r"^-\s+\[([x~! ])\]\s+(.+)$")
        for line_num, line in enumerate(lines, start=1):
            match = task_line_pattern.match(line.rstrip())
            if match:
                text_after_checkbox = match.group(2)
                # Check if it starts with PRD-NNN
                if not text_after_checkbox.startswith("PRD-"):
                    # Truncate long task text for error message
                    task_preview = (
                        text_after_checkbox[:60] + "..."
                        if len(text_after_checkbox) > 60
                        else text_after_checkbox
                    )
                    issues.append(
                        f"Line {line_num}: Task missing explicit ID\n"
                        f"  Found: - [ ] {task_preview}\n"
                        f"  Expected: - [ ] PRD-NNN Task description\n"
                        f"  Fix: Add an ID like '{self._suggest_next_id()}' before the task text:\n"
                        f"    - [ ] {self._suggest_next_id()} {task_preview}"
                    )

        return issues


def parse_prd_file(prd_file: Path) -> list[PRDTask]:
    """Convenience function to parse PRD file.

    Args:
        prd_file: Path to PRD markdown file

    Returns:
        List of PRDTask objects

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If validation fails
    """
    parser = PRDParser(prd_file)
    return parser.parse()
