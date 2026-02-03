"""Deviation handling for Nelson.

This module provides deviation rules that allow Claude to auto-fix certain issues
inline during implementation without stopping, maintaining momentum while keeping
a full audit trail.

Deviation rules:
- AUTO_FIX_BUGS: Fix type errors, logic bugs, undefined variables
- AUTO_ADD_CRITICAL: Add missing input validation, error handling, null checks
- AUTO_INSTALL_DEPS: Install missing packages
- AUTO_HANDLE_AUTH: Handle 401 responses with provided credentials
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DeviationRule(Enum):
    """Types of auto-fix deviations Claude can apply."""

    AUTO_FIX_BUGS = "auto_fix_bugs"  # Type errors, logic bugs, undefined vars
    AUTO_ADD_CRITICAL = "auto_add_critical"  # Missing validation, error handling
    AUTO_INSTALL_DEPS = "auto_install_deps"  # Missing packages
    AUTO_HANDLE_AUTH = "auto_handle_auth"  # 401 response handling


@dataclass
class Deviation:
    """A deviation applied during implementation.

    Attributes:
        rule: The type of deviation rule applied
        issue: Description of the issue encountered
        fix_applied: Description of the fix that was applied
        files_affected: List of files modified by this deviation
        task_id: Optional task ID this deviation is associated with
        commit_sha: Optional commit SHA if deviation was committed
        timestamp: When the deviation was applied
    """

    rule: DeviationRule
    issue: str
    fix_applied: str
    files_affected: list[str] = field(default_factory=list)
    task_id: str | None = None
    commit_sha: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule": self.rule.value,
            "issue": self.issue,
            "fix_applied": self.fix_applied,
            "files_affected": self.files_affected,
            "task_id": self.task_id,
            "commit_sha": self.commit_sha,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Deviation:
        """Create Deviation from dictionary."""
        return cls(
            rule=DeviationRule(data["rule"]),
            issue=data["issue"],
            fix_applied=data["fix_applied"],
            files_affected=data.get("files_affected", []),
            task_id=data.get("task_id"),
            commit_sha=data.get("commit_sha"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(),
        )


@dataclass(frozen=True)
class DeviationConfig:
    """Configuration for deviation handling.

    Controls which deviation rules are enabled and limits.

    Attributes:
        auto_fix_bugs: Allow auto-fixing type errors, logic bugs
        auto_add_critical: Allow adding missing validation, error handling
        auto_install_deps: Allow installing missing packages
        auto_handle_auth: Allow handling 401 responses (higher risk)
        max_deviations_per_task: Maximum deviations allowed per task
    """

    auto_fix_bugs: bool = True
    auto_add_critical: bool = True
    auto_install_deps: bool = True  # Medium risk, but useful
    auto_handle_auth: bool = False  # Higher risk, opt-in
    max_deviations_per_task: int = 5

    def is_rule_enabled(self, rule: DeviationRule) -> bool:
        """Check if a deviation rule is enabled.

        Args:
            rule: The rule to check

        Returns:
            True if the rule is enabled
        """
        rule_map = {
            DeviationRule.AUTO_FIX_BUGS: self.auto_fix_bugs,
            DeviationRule.AUTO_ADD_CRITICAL: self.auto_add_critical,
            DeviationRule.AUTO_INSTALL_DEPS: self.auto_install_deps,
            DeviationRule.AUTO_HANDLE_AUTH: self.auto_handle_auth,
        }
        return rule_map.get(rule, False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "auto_fix_bugs": self.auto_fix_bugs,
            "auto_add_critical": self.auto_add_critical,
            "auto_install_deps": self.auto_install_deps,
            "auto_handle_auth": self.auto_handle_auth,
            "max_deviations_per_task": self.max_deviations_per_task,
        }

    @classmethod
    def from_env(cls) -> DeviationConfig:
        """Load DeviationConfig from environment variables.

        Environment variables:
            NELSON_AUTO_FIX_BUGS: Enable auto-fixing bugs (default: true)
            NELSON_AUTO_ADD_CRITICAL: Enable adding critical code (default: true)
            NELSON_AUTO_INSTALL_DEPS: Enable installing deps (default: true)
            NELSON_AUTO_HANDLE_AUTH: Enable auth handling (default: false)
            NELSON_MAX_DEVIATIONS_PER_TASK: Max deviations per task (default: 5)

        Returns:
            DeviationConfig with values from environment
        """
        import os

        def parse_bool(key: str, default: bool) -> bool:
            val = os.environ.get(key, "").lower()
            if not val:
                return default
            return val in ("true", "1", "yes")

        return cls(
            auto_fix_bugs=parse_bool("NELSON_AUTO_FIX_BUGS", True),
            auto_add_critical=parse_bool("NELSON_AUTO_ADD_CRITICAL", True),
            auto_install_deps=parse_bool("NELSON_AUTO_INSTALL_DEPS", True),
            auto_handle_auth=parse_bool("NELSON_AUTO_HANDLE_AUTH", False),
            max_deviations_per_task=int(
                os.environ.get("NELSON_MAX_DEVIATIONS_PER_TASK", "5")
            ),
        )


def extract_deviations_from_response(
    response: str, task_id: str | None = None
) -> list[Deviation]:
    """Extract deviations from Claude's response.

    Looks for a ```deviations block containing JSON array of deviation objects.

    Args:
        response: Claude's response text
        task_id: Optional task ID to associate with deviations

    Returns:
        List of Deviation objects, empty if no block found
    """
    # Look for deviations code block
    pattern = r"```deviations\s*(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)

    if not matches:
        return []

    deviations = []
    for block in matches:
        block = block.strip()
        if not block:
            continue

        try:
            data = json.loads(block)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                # Parse rule from string
                rule_str = item.get("rule", "").lower()
                try:
                    rule = DeviationRule(rule_str)
                except ValueError:
                    # Try matching by prefix
                    rule = None
                    for r in DeviationRule:
                        if rule_str in r.value or r.value in rule_str:
                            rule = r
                            break
                    if rule is None:
                        continue

                # rule is guaranteed to be non-None at this point
                deviation = Deviation(
                    rule=rule,  # type: ignore[arg-type]
                    issue=item.get("issue", ""),
                    fix_applied=item.get("fix_applied", item.get("fix", "")),
                    files_affected=item.get("files_affected", item.get("files", [])),
                    task_id=task_id,
                )
                deviations.append(deviation)

        except (json.JSONDecodeError, KeyError, TypeError):
            # Invalid JSON or missing fields, skip
            continue

    return deviations


def validate_deviations(
    deviations: list[Deviation],
    config: DeviationConfig,
    task_deviation_count: int = 0,
) -> tuple[list[Deviation], list[Deviation]]:
    """Validate deviations against configuration.

    Args:
        deviations: List of deviations to validate
        config: DeviationConfig with enabled rules and limits
        task_deviation_count: Number of deviations already applied for this task

    Returns:
        Tuple of (allowed_deviations, blocked_deviations)
    """
    allowed: list[Deviation] = []
    blocked: list[Deviation] = []

    remaining_slots = config.max_deviations_per_task - task_deviation_count

    for deviation in deviations:
        # Check if rule is enabled
        if not config.is_rule_enabled(deviation.rule):
            blocked.append(deviation)
            continue

        # Check if we've exceeded max deviations
        if remaining_slots <= 0:
            blocked.append(deviation)
            continue

        allowed.append(deviation)
        remaining_slots -= 1

    return allowed, blocked


def log_deviations(
    deviations: list[Deviation],
    decisions_file: Path,
    blocked: bool = False,
) -> None:
    """Log deviations to the decisions file.

    Args:
        deviations: List of deviations to log
        decisions_file: Path to decisions.md file
        blocked: Whether these deviations were blocked
    """
    if not deviations:
        return

    header = "## Blocked Deviations" if blocked else "## Auto-Applied Deviations"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"\n{header}",
        f"*{timestamp}*\n",
        "| Rule | Issue | Fix | Files |",
        "|------|-------|-----|-------|",
    ]

    for dev in deviations:
        rule_name = dev.rule.value.replace("_", " ").title()
        files = ", ".join(dev.files_affected) if dev.files_affected else "-"
        # Escape pipes in content
        issue = dev.issue.replace("|", "\\|")
        fix = dev.fix_applied.replace("|", "\\|")
        lines.append(f"| {rule_name} | {issue} | {fix} | {files} |")

    lines.append("")

    # Append to decisions file
    with open(decisions_file, "a") as f:
        f.write("\n".join(lines))


def format_deviation_summary(deviations: list[Deviation]) -> str:
    """Format a summary of deviations for display.

    Args:
        deviations: List of deviations to summarize

    Returns:
        Formatted summary string
    """
    if not deviations:
        return "No deviations applied."

    # Count by rule type
    by_rule: dict[DeviationRule, int] = {}
    all_files: set[str] = set()

    for dev in deviations:
        by_rule[dev.rule] = by_rule.get(dev.rule, 0) + 1
        all_files.update(dev.files_affected)

    lines = [f"Total deviations: {len(deviations)}"]

    for rule, count in sorted(by_rule.items(), key=lambda x: -x[1]):
        rule_name = rule.value.replace("_", " ").title()
        lines.append(f"  - {rule_name}: {count}")

    if all_files:
        lines.append(f"Files affected: {len(all_files)}")
        for f in sorted(all_files)[:5]:  # Show top 5
            lines.append(f"  - {f}")
        if len(all_files) > 5:
            lines.append(f"  ... and {len(all_files) - 5} more")

    return "\n".join(lines)


def get_enabled_rules_description(config: DeviationConfig) -> str:
    """Get a description of enabled deviation rules for prompts.

    Args:
        config: DeviationConfig to describe

    Returns:
        Formatted description of enabled rules
    """
    rules = []

    if config.auto_fix_bugs:
        rules.append("- **AUTO_FIX_BUGS**: Fix type errors, logic bugs, undefined variables")

    if config.auto_add_critical:
        rules.append(
            "- **AUTO_ADD_CRITICAL**: Add missing input validation, error handling, null checks"
        )

    if config.auto_install_deps:
        rules.append(
            "- **AUTO_INSTALL_DEPS**: Install missing packages (npm install / pip install)"
        )

    if config.auto_handle_auth:
        rules.append("- **AUTO_HANDLE_AUTH**: Handle 401 responses with provided credentials")

    if not rules:
        return "No deviation rules enabled. Report all issues without auto-fixing."

    return "\n".join(rules)
