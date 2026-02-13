"""Blocked state handling for Nelson.

This module provides infrastructure for detecting and resolving blocked tasks
during workflow execution. When Claude reports STATUS: BLOCKED, Nelson can
prompt users for resolution instead of just stopping or skipping.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    from nelson.interaction import UserInteraction

logger = logging.getLogger(__name__)
console = Console()


class BlockedResolution(Enum):
    """User's choice for how to handle a blocked task."""

    RESOLVED = "resolved"  # User fixed the issue, retry
    SKIP = "skip"  # Skip this task and continue
    STOP = "stop"  # Stop execution entirely


@dataclass
class BlockedInfo:
    """Information about a blocked task.

    Attributes:
        task_id: ID of the blocked task (if known)
        reason: Why the task is blocked
        required_resources: List of resources needed (e.g., API keys, services)
        suggested_resolution: Hint for how to resolve the blocker
        phase: Current phase when blocked
        iteration: Iteration when blocked
    """

    task_id: str | None
    reason: str
    required_resources: list[str] = field(default_factory=list)
    suggested_resolution: str | None = None
    phase: str | None = None
    iteration: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "reason": self.reason,
            "required_resources": self.required_resources,
            "suggested_resolution": self.suggested_resolution,
            "phase": self.phase,
            "iteration": self.iteration,
        }


def extract_blocked_info(
    status_block: dict[str, Any],
    response_content: str,
) -> BlockedInfo | None:
    """Extract BlockedInfo from a status block and response.

    Args:
        status_block: Parsed status block from Claude response
        response_content: Full response content for additional context

    Returns:
        BlockedInfo if status is BLOCKED, None otherwise
    """
    status = status_block.get("status", "").upper()

    if status != "BLOCKED":
        return None

    # Get basic info from status block
    reason = status_block.get("blocked_reason", "")
    if not reason:
        reason = status_block.get("recommendation", "Task is blocked")

    # Parse resources from status block or extract from content
    resources_str = status_block.get("blocked_resources", "")
    if resources_str:
        required_resources = [r.strip() for r in resources_str.split(",") if r.strip()]
    else:
        required_resources = _extract_resources_from_content(response_content)

    suggested_resolution = status_block.get("blocked_resolution")

    return BlockedInfo(
        task_id=None,  # Will be set by caller if known
        reason=reason,
        required_resources=required_resources,
        suggested_resolution=suggested_resolution,
    )


def _extract_resources_from_content(content: str) -> list[str]:
    """Extract likely resource names from response content.

    Looks for patterns like:
    - Environment variables (ALL_CAPS_WITH_UNDERSCORES)
    - Service names after "need", "missing", "require"
    - API key patterns

    Args:
        content: Response content to search

    Returns:
        List of identified resource names
    """
    resources = []

    # Look for environment variable patterns (e.g., OPENAI_API_KEY)
    env_var_pattern = r"\b([A-Z][A-Z0-9_]{2,}(?:_KEY|_SECRET|_TOKEN|_PASSWORD|_URL|_URI)?)\b"
    env_vars = re.findall(env_var_pattern, content)
    # Filter out common words that match the pattern
    excluded = {"STATUS", "BLOCKED", "COMPLETE", "PASSING", "FAILING", "NOT_RUN", "TRUE", "FALSE"}
    resources.extend([v for v in env_vars if v not in excluded])

    # Look for "need(s) X" or "missing X" patterns
    need_pattern = r"(?:need|needs|missing|require|requires|waiting for)\s+([a-zA-Z0-9_\-\.]+)"
    needs = re.findall(need_pattern, content, re.IGNORECASE)
    resources.extend(needs)

    # Deduplicate while preserving order
    seen = set()
    unique_resources = []
    for r in resources:
        if r.lower() not in seen:
            seen.add(r.lower())
            unique_resources.append(r)

    return unique_resources[:5]  # Limit to 5 most relevant


def prompt_blocked_resolution(
    blocked_info: BlockedInfo,
    interaction: UserInteraction,
) -> tuple[BlockedResolution, str | None]:
    """Prompt user for how to handle a blocked task.

    Args:
        blocked_info: Information about the blocker
        interaction: UserInteraction instance

    Returns:
        Tuple of (resolution choice, optional resolution context)
    """
    from nelson.interaction import InteractionMode

    # In autonomous mode, auto-skip
    if interaction.config.mode == InteractionMode.AUTONOMOUS:
        logger.info("Autonomous mode: auto-skipping blocked task")
        return BlockedResolution.SKIP, None

    # Build display content
    content_parts = [
        "",
        f"[bold red]Reason:[/bold red] {blocked_info.reason}",
        "",
    ]

    if blocked_info.required_resources:
        content_parts.append("[bold yellow]Required Resources:[/bold yellow]")
        for resource in blocked_info.required_resources:
            content_parts.append(f"  • {resource}")
        content_parts.append("")

    if blocked_info.suggested_resolution:
        content_parts.append(
            f"[bold green]Suggested Resolution:[/bold green] {blocked_info.suggested_resolution}"
        )
        content_parts.append("")

    content_parts.extend(
        [
            "[dim]Options:[/dim]",
            "  [1] I've resolved this - continue",
            "  [2] Skip this task and continue",
            "  [3] Stop execution",
            "",
        ]
    )

    # Display panel
    console.print(
        Panel(
            "\n".join(content_parts),
            title="[bold red]Task Blocked[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )

    # Get user choice
    choice, was_default = interaction.ask_multiple_choice(
        question="How would you like to proceed?",
        options=["Continue (resolved)", "Skip task", "Stop execution"],
        default_index=1,  # Skip is safest default
        timeout_seconds=interaction.config.ambiguity_timeout_seconds,
    )

    if "Continue" in choice or "resolved" in choice.lower():
        # Ask for resolution context
        context, _ = interaction.ask_free_text(
            question="What did you do to resolve this? (optional, helps Claude continue)",
            default="",
            timeout_seconds=30,
        )
        return BlockedResolution.RESOLVED, context if context else None

    elif "Skip" in choice:
        return BlockedResolution.SKIP, None

    else:
        return BlockedResolution.STOP, None


def format_resolution_context(
    blocked_info: BlockedInfo,
    resolution_context: str | None,
) -> str:
    """Format resolution context for inclusion in next Claude prompt.

    Args:
        blocked_info: Original blocker information
        resolution_context: User's description of how they resolved it

    Returns:
        Formatted string for prompt continuation
    """
    lines = [
        "",
        "## Blocker Resolved",
        "",
        f"**Previous blocker:** {blocked_info.reason}",
    ]

    if resolution_context:
        lines.append(f"**User's resolution:** {resolution_context}")
    else:
        lines.append("**Status:** User confirmed the issue has been resolved")

    lines.extend(
        [
            "",
            "Please retry the blocked task with the issue now resolved.",
            "",
        ]
    )

    return "\n".join(lines)


def log_blocked_event(
    blocked_info: BlockedInfo,
    resolution: BlockedResolution,
    resolution_context: str | None,
    decisions_file: Path,
) -> None:
    """Log a blocked event and its resolution to decisions file.

    Args:
        blocked_info: Information about the blocker
        resolution: User's resolution choice
        resolution_context: Optional context about how it was resolved
        decisions_file: Path to decisions.md file
    """
    timestamp = datetime.now().isoformat()

    lines = [
        "",
        "## Task Blocked",
        "",
        f"*Timestamp: {timestamp}*",
        "",
        f"**Reason:** {blocked_info.reason}",
    ]

    if blocked_info.required_resources:
        resources_str = ", ".join(blocked_info.required_resources)
        lines.append(f"**Required Resources:** {resources_str}")

    if blocked_info.suggested_resolution:
        lines.append(f"**Suggested Resolution:** {blocked_info.suggested_resolution}")

    lines.append(f"**User's Choice:** {resolution.value}")

    if resolution_context:
        lines.append(f"**Resolution Context:** {resolution_context}")

    lines.append("")

    # Append to file
    with open(decisions_file, "a") as f:
        f.write("\n".join(lines))


# Common blocker patterns for detection
COMMON_BLOCKERS = {
    "api_key": {
        "patterns": [
            r"API[_\s]?KEY",
            r"SECRET[_\s]?KEY",
            r"ACCESS[_\s]?TOKEN",
        ],
        "hint": "Add the required API key to your .env file",
    },
    "database": {
        "patterns": [
            r"database.*connection",
            r"cannot connect to.*db",
            r"postgres|mysql|mongodb.*error",
        ],
        "hint": "Ensure the database is running and credentials are correct",
    },
    "service": {
        "patterns": [
            r"service.*unavailable",
            r"connection refused",
            r"redis|rabbitmq|kafka.*error",
        ],
        "hint": "Start the required service or check its configuration",
    },
    "permission": {
        "patterns": [
            r"permission denied",
            r"access denied",
            r"unauthorized",
        ],
        "hint": "Grant the required permissions or check authentication",
    },
    "dependency": {
        "patterns": [
            r"module not found",
            r"package.*not installed",
            r"import error",
        ],
        "hint": "Install the missing dependency",
    },
}


def detect_blocker_category(blocked_info: BlockedInfo) -> str | None:
    """Detect the category of blocker based on reason and resources.

    Args:
        blocked_info: Blocker information to categorize

    Returns:
        Category name if detected, None otherwise
    """
    content = blocked_info.reason.lower()
    for resource in blocked_info.required_resources:
        content += " " + resource.lower()

    for category, info in COMMON_BLOCKERS.items():
        for pattern in info["patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                return category

    return None


def get_blocker_hint(category: str) -> str | None:
    """Get resolution hint for a blocker category.

    Args:
        category: Blocker category name

    Returns:
        Hint string if category exists, None otherwise
    """
    if category in COMMON_BLOCKERS:
        hint = COMMON_BLOCKERS[category]["hint"]
        if isinstance(hint, str):
            return hint
    return None
