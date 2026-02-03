"""Status block parser for Nelson's execution output.

This module provides utilities to parse the NELSON_STATUS block from AI provider
responses. The status block contains critical information about execution progress,
including task completion, file modifications, test status, and the EXIT_SIGNAL.

Example status block format:
    ---NELSON_STATUS---
    STATUS: IN_PROGRESS|COMPLETE|BLOCKED
    TASKS_COMPLETED_THIS_LOOP: N
    FILES_MODIFIED: N
    TESTS_STATUS: PASSING|FAILING|NOT_RUN
    WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
    EXIT_SIGNAL: true|false
    RECOMMENDATION: one-line next step
    ---END_NELSON_STATUS---
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    """Execution status values from status block."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class RunTestsStatus(str, Enum):
    """Test status values from status block."""

    PASSING = "PASSING"
    FAILING = "FAILING"
    NOT_RUN = "NOT_RUN"


class WorkType(str, Enum):
    """Work type values from status block."""

    IMPLEMENTATION = "IMPLEMENTATION"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    REFACTORING = "REFACTORING"


@dataclass(frozen=True)
class StatusBlock:
    """Parsed status block from Nelson execution.

    This represents the structured data extracted from the NELSON_STATUS block
    in the AI provider's response.

    Attributes:
        status: Current execution status
        tasks_completed_this_loop: Number of tasks completed in this iteration
        files_modified: Number of files modified in this iteration
        tests_status: Status of test execution
        work_type: Type of work performed
        exit_signal: Whether workflow should exit (all work complete)
        recommendation: One-line recommendation for next steps
        raw_block: Original text of the status block
        blocked_reason: Detailed reason for blockage (only if STATUS: BLOCKED)
        blocked_resources: List of required resources (only if STATUS: BLOCKED)
        blocked_resolution: Suggested fix (only if STATUS: BLOCKED)
    """

    status: ExecutionStatus
    tasks_completed_this_loop: int
    files_modified: int
    tests_status: RunTestsStatus
    work_type: WorkType
    exit_signal: bool
    recommendation: str
    raw_block: str
    blocked_reason: str | None = None
    blocked_resources: list[str] | None = None
    blocked_resolution: str | None = None


class StatusBlockError(Exception):
    """Raised when status block cannot be parsed."""

    pass


def extract_status_block_text(content: str) -> str:
    """Extract the raw status block text from content.

    Args:
        content: Full text content containing status block

    Returns:
        Raw status block text between delimiters

    Raises:
        StatusBlockError: If status block delimiters not found
    """
    start_marker = "---NELSON_STATUS---"
    end_marker = "---END_NELSON_STATUS---"

    if start_marker not in content:
        raise StatusBlockError("Status block start marker not found")

    if end_marker not in content:
        raise StatusBlockError("Status block end marker not found")

    start_idx = content.index(start_marker) + len(start_marker)
    end_idx = content.index(end_marker)

    return content[start_idx:end_idx].strip()


def parse_status_block(content: str) -> StatusBlock:
    """Parse status block from AI provider response.

    Args:
        content: Full text content containing status block

    Returns:
        Parsed StatusBlock object

    Raises:
        StatusBlockError: If status block is missing or invalid
    """
    # Extract raw status block text
    raw_block = extract_status_block_text(content)

    # Parse into dictionary
    status_dict: dict[str, Any] = {}
    for line in raw_block.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        status_dict[key] = value

    # Validate required fields
    required_fields = [
        "status",
        "tasks_completed_this_loop",
        "files_modified",
        "tests_status",
        "work_type",
        "exit_signal",
        "recommendation",
    ]

    missing_fields = [field for field in required_fields if field not in status_dict]
    if missing_fields:
        raise StatusBlockError(
            f"Missing required fields in status block: {', '.join(missing_fields)}"
        )

    # Parse and validate each field
    try:
        status = ExecutionStatus(status_dict["status"])
    except ValueError as e:
        raise StatusBlockError(f"Invalid status value: {status_dict['status']}") from e

    try:
        tasks_completed = int(status_dict["tasks_completed_this_loop"])
    except ValueError:
        tasks_completed = 0

    try:
        files_modified = int(status_dict["files_modified"])
    except ValueError:
        files_modified = 0

    try:
        tests_status = RunTestsStatus(status_dict["tests_status"])
    except ValueError as e:
        raise StatusBlockError(f"Invalid tests_status value: {status_dict['tests_status']}") from e

    try:
        work_type = WorkType(status_dict["work_type"])
    except ValueError as e:
        raise StatusBlockError(f"Invalid work_type value: {status_dict['work_type']}") from e

    exit_signal_str = status_dict["exit_signal"].lower()
    exit_signal = exit_signal_str in ("true", "1", "yes")

    recommendation = status_dict["recommendation"]

    # Parse optional blocked fields (only present when STATUS: BLOCKED)
    blocked_reason = status_dict.get("blocked_reason")
    blocked_resources_str = status_dict.get("blocked_resources")
    blocked_resources = None
    if blocked_resources_str:
        blocked_resources = [r.strip() for r in blocked_resources_str.split(",") if r.strip()]
    blocked_resolution = status_dict.get("blocked_resolution")

    return StatusBlock(
        status=status,
        tasks_completed_this_loop=tasks_completed,
        files_modified=files_modified,
        tests_status=tests_status,
        work_type=work_type,
        exit_signal=exit_signal,
        recommendation=recommendation,
        raw_block=raw_block,
        blocked_reason=blocked_reason,
        blocked_resources=blocked_resources,
        blocked_resolution=blocked_resolution,
    )


def status_block_to_dict(status_block: StatusBlock) -> dict[str, Any]:
    """Convert StatusBlock to dictionary format.

    This is useful for serialization and compatibility with existing code
    that expects dictionary format.

    Args:
        status_block: Parsed status block

    Returns:
        Dictionary with status block fields
    """
    result = {
        "status": status_block.status.value,
        "tasks_completed": status_block.tasks_completed_this_loop,
        "files_modified": status_block.files_modified,
        "tests_status": status_block.tests_status.value,
        "work_type": status_block.work_type.value,
        "exit_signal": status_block.exit_signal,
        "recommendation": status_block.recommendation,
    }

    # Add blocked fields if present
    if status_block.blocked_reason:
        result["blocked_reason"] = status_block.blocked_reason
    if status_block.blocked_resources:
        result["blocked_resources"] = ",".join(status_block.blocked_resources)
    if status_block.blocked_resolution:
        result["blocked_resolution"] = status_block.blocked_resolution

    return result
