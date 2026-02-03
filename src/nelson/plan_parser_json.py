"""JSON plan parser and writer.

This module provides functions to read, write, and extract structured JSON plans.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from nelson.plan_models import Plan, Task

logger = logging.getLogger(__name__)


class PlanParseError(Exception):
    """Error parsing a plan file."""

    pass


def parse_json_plan(file_path: Path) -> Plan:
    """Parse a JSON plan file and return a Plan object.

    Args:
        file_path: Path to the JSON plan file

    Returns:
        Plan object with all tasks

    Raises:
        PlanParseError: If file cannot be read or parsed
        FileNotFoundError: If file does not exist
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise PlanParseError(f"Invalid JSON in {file_path}: {e}")
    except OSError as e:
        raise PlanParseError(f"Cannot read {file_path}: {e}")

    return _parse_plan_data(data, str(file_path))


def _parse_plan_data(data: dict[str, Any], source: str = "unknown") -> Plan:
    """Parse plan data dictionary into Plan object.

    Args:
        data: Dictionary containing plan data
        source: Source description for error messages

    Returns:
        Plan object

    Raises:
        PlanParseError: If required fields are missing or invalid
    """
    # Validate required fields
    if "name" not in data:
        raise PlanParseError(f"Plan from {source} missing required field: name")

    if "tasks" not in data:
        raise PlanParseError(f"Plan from {source} missing required field: tasks")

    if not isinstance(data["tasks"], list):
        raise PlanParseError(f"Plan from {source}: 'tasks' must be a list")

    # Validate each task has required fields
    for i, task_data in enumerate(data["tasks"]):
        if not isinstance(task_data, dict):
            raise PlanParseError(f"Plan from {source}: task {i} must be an object")

        required_task_fields = ["id", "name", "action", "done_when"]
        for field in required_task_fields:
            if field not in task_data:
                raise PlanParseError(
                    f"Plan from {source}: task {i} missing required field: {field}"
                )

    try:
        return Plan.from_dict(data)
    except (KeyError, TypeError) as e:
        raise PlanParseError(f"Plan from {source} has invalid structure: {e}")


def write_json_plan(plan: Plan, file_path: Path) -> None:
    """Write a Plan object to a JSON file.

    Args:
        plan: Plan object to write
        file_path: Path to write the JSON file

    Raises:
        OSError: If file cannot be written
    """
    data = plan.to_dict()

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Trailing newline


def extract_plan_from_response(response: str) -> Plan | None:
    """Extract a JSON plan from a Claude response.

    Looks for a ```json...``` code block containing a plan object.

    Args:
        response: Full Claude response text

    Returns:
        Plan object if found and valid, None otherwise
    """
    # Find JSON code blocks (flexible pattern to handle various whitespace)
    json_blocks = re.findall(r"```json\s*(.*?)```", response, re.DOTALL)

    if not json_blocks:
        logger.debug("No JSON code blocks found in response")
        return None

    # Try each JSON block
    for block in json_blocks:
        block = block.strip()
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON block failed to parse: {e}")
            continue

        # Check if this looks like a plan (has tasks field)
        if not isinstance(data, dict):
            continue

        if "tasks" not in data:
            continue

        try:
            plan = _parse_plan_data(data, "response")
            logger.debug(f"Successfully extracted plan: {plan.name}")
            return plan
        except PlanParseError as e:
            logger.warning(f"Found plan block but failed to parse: {e}")
            continue

    logger.debug("No valid plan found in JSON blocks")
    return None


def plan_to_markdown(plan: Plan) -> str:
    """Convert a Plan to markdown format for human readability.

    Args:
        plan: Plan to convert

    Returns:
        Markdown string representation of the plan
    """
    lines = [
        f"# {plan.name}",
        "",
        f"**Phase:** {plan.phase}",
        f"**Goal:** {plan.goal}",
        "",
        "## Tasks",
        "",
    ]

    # Group tasks by wave
    waves: dict[int, list[Task]] = {}
    for task in plan.tasks:
        if task.wave not in waves:
            waves[task.wave] = []
        waves[task.wave].append(task)

    for wave_num in sorted(waves.keys()):
        lines.append(f"### Wave {wave_num}")
        lines.append("")

        for task in waves[wave_num]:
            status_char = {
                "pending": " ",
                "in_progress": "~",
                "completed": "x",
                "skipped": "-",
            }.get(task.status.value, " ")

            lines.append(f"- [{status_char}] **{task.id}**: {task.name}")
            lines.append(f"  - Action: {task.action}")
            lines.append(f"  - Done when: {task.done_when}")

            if task.depends_on:
                lines.append(f"  - Depends on: {', '.join(task.depends_on)}")

            if task.files:
                lines.append(f"  - Files: {', '.join(task.files)}")

            if task.verify:
                lines.append(f"  - Verify: `{task.verify}`")

            lines.append("")

    return "\n".join(lines)
