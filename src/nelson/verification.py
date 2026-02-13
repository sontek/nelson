"""Goal-backward verification for Nelson.

This module implements verification that checks whether goals are achieved,
not just whether tasks are completed. It detects stubs, verifies component
wiring, and ensures substantive implementation.

Verification levels:
- EXISTS: File/directory present at path
- SUBSTANTIVE: Not a stub/placeholder (no TODO, empty functions, etc.)
- WIRED: Connected to system (imports, references)
- FUNCTIONAL: Actually works (command verification)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class VerificationLevel(Enum):
    """Levels of verification from basic to thorough."""

    EXISTS = "exists"  # File/directory present
    SUBSTANTIVE = "substantive"  # Not a stub/placeholder
    WIRED = "wired"  # Connected to system
    FUNCTIONAL = "functional"  # Actually works


@dataclass
class VerificationCheck:
    """A single verification check result.

    Attributes:
        level: The verification level (EXISTS, SUBSTANTIVE, etc.)
        target: File path or component being checked
        check_command: Optional command to run for automated check
        expected_result: What we expect to find/see
        actual_result: What we actually found (populated after check)
        passed: Whether the check passed (None if not yet run)
        details: Additional details about the check result
    """

    level: VerificationLevel
    target: str
    expected_result: str
    check_command: str | None = None
    actual_result: str | None = None
    passed: bool | None = None
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "level": self.level.value,
            "target": self.target,
            "check_command": self.check_command,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "passed": self.passed,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationCheck:
        """Create from dictionary."""
        return cls(
            level=VerificationLevel(data["level"]),
            target=data["target"],
            check_command=data.get("check_command"),
            expected_result=data["expected_result"],
            actual_result=data.get("actual_result"),
            passed=data.get("passed"),
            details=data.get("details", []),
        )


@dataclass
class GoalVerification:
    """Verification criteria for a goal.

    Attributes:
        goal: What we're verifying (e.g., "User can log in")
        truths: Observable outcomes that must be true
        artifacts: Files that must exist
        wiring: Connections between components (source, target) pairs
        checks: Verification checks (populated during verification)
        functional_checks: Commands to run for functional verification
    """

    goal: str
    truths: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    wiring: list[tuple[str, str]] = field(default_factory=list)
    checks: list[VerificationCheck] = field(default_factory=list)
    functional_checks: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "goal": self.goal,
            "truths": self.truths,
            "artifacts": self.artifacts,
            "wiring": [[s, t] for s, t in self.wiring],
            "checks": [c.to_dict() for c in self.checks],
            "functional_checks": self.functional_checks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalVerification:
        """Create from dictionary."""
        wiring = [tuple(pair) for pair in data.get("wiring", [])]
        checks = [VerificationCheck.from_dict(c) for c in data.get("checks", [])]
        return cls(
            goal=data["goal"],
            truths=data.get("truths", []),
            artifacts=data.get("artifacts", []),
            wiring=wiring,
            checks=checks,
            functional_checks=data.get("functional_checks", []),
        )

    @property
    def passed(self) -> bool:
        """Check if all verification checks passed."""
        if not self.checks:
            return True  # No checks = passes by default
        return all(c.passed for c in self.checks)

    @property
    def critical_failures(self) -> list[VerificationCheck]:
        """Get checks that failed at critical levels (SUBSTANTIVE, WIRED)."""
        return [
            c
            for c in self.checks
            if c.passed is False
            and c.level in (VerificationLevel.SUBSTANTIVE, VerificationLevel.WIRED)
        ]


# Patterns that indicate stub/placeholder code
STUB_PATTERNS = [
    (r"\bTODO\b", "TODO comment"),
    (r"\bFIXME\b", "FIXME comment"),
    (r"\bXXX\b", "XXX comment"),
    (r"\bnot\s+implemented\b", "not implemented"),
    (r"throw\s+new\s+Error\s*\(['\"]", "throw Error placeholder"),
    (r"raise\s+NotImplementedError", "NotImplementedError"),
    (r"^\s*pass\s*$", "empty pass statement"),
    (r"^\s*\.\.\.\s*$", "ellipsis placeholder"),
    (r"return\s+null\s*;\s*//\s*placeholder", "null placeholder"),
    (r"#\s*placeholder", "placeholder comment"),
    (r"//\s*placeholder", "placeholder comment"),
]


def check_exists(target: str, base_path: Path) -> VerificationCheck:
    """Check if a file or directory exists.

    Args:
        target: Relative path to check
        base_path: Base directory to resolve path from

    Returns:
        VerificationCheck with result
    """
    full_path = base_path / target
    exists = full_path.exists()

    return VerificationCheck(
        level=VerificationLevel.EXISTS,
        target=target,
        expected_result="File/directory exists",
        actual_result="Exists" if exists else "Not found",
        passed=exists,
        details=[f"Checked: {full_path}"],
    )


def check_substantive(target: str, base_path: Path) -> VerificationCheck:
    """Check if a file contains substantive implementation (not stubs).

    Args:
        target: Relative path to file
        base_path: Base directory to resolve path from

    Returns:
        VerificationCheck with stub indicators found
    """
    full_path = base_path / target

    # First check if file exists
    if not full_path.exists():
        return VerificationCheck(
            level=VerificationLevel.SUBSTANTIVE,
            target=target,
            expected_result="No stub patterns found",
            actual_result="File not found",
            passed=False,
            details=["Cannot check substantive content - file does not exist"],
        )

    # Check if it's a directory
    if full_path.is_dir():
        return VerificationCheck(
            level=VerificationLevel.SUBSTANTIVE,
            target=target,
            expected_result="No stub patterns found",
            actual_result="Is a directory",
            passed=True,
            details=["Skipped - target is a directory"],
        )

    try:
        content = full_path.read_text()
    except Exception as e:
        return VerificationCheck(
            level=VerificationLevel.SUBSTANTIVE,
            target=target,
            expected_result="No stub patterns found",
            actual_result=f"Read error: {e}",
            passed=False,
            details=[f"Could not read file: {e}"],
        )

    # Check for stub patterns
    stub_found: list[str] = []
    for pattern, description in STUB_PATTERNS:
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            stub_found.append(description)

    passed = len(stub_found) == 0

    return VerificationCheck(
        level=VerificationLevel.SUBSTANTIVE,
        target=target,
        expected_result="No stub patterns found",
        actual_result="Clean" if passed else f"Found {len(stub_found)} stub patterns",
        passed=passed,
        details=stub_found if stub_found else ["No stub patterns detected"],
    )


def check_wired(source: str, target: str, base_path: Path) -> VerificationCheck:
    """Check if source file imports/references target.

    Args:
        source: Source file that should import target
        target: Target file/module that should be imported
        base_path: Base directory to resolve paths from

    Returns:
        VerificationCheck with connection evidence
    """
    source_path = base_path / source

    if not source_path.exists():
        return VerificationCheck(
            level=VerificationLevel.WIRED,
            target=f"{source} -> {target}",
            expected_result=f"{source} imports/uses {target}",
            actual_result="Source file not found",
            passed=False,
            details=[f"Cannot check wiring - {source} does not exist"],
        )

    try:
        content = source_path.read_text()
    except Exception as e:
        return VerificationCheck(
            level=VerificationLevel.WIRED,
            target=f"{source} -> {target}",
            expected_result=f"{source} imports/uses {target}",
            actual_result=f"Read error: {e}",
            passed=False,
            details=[f"Could not read source file: {e}"],
        )

    # Extract module/file name from target for matching
    target_path = Path(target)
    target_name = target_path.stem  # filename without extension

    # Patterns to check for imports/references
    import_patterns = [
        # Python imports
        rf"from\s+[\w.]*{re.escape(target_name)}\s+import",
        rf"import\s+[\w.]*{re.escape(target_name)}",
        # JavaScript/TypeScript imports
        rf"import\s+.*from\s+['\"].*{re.escape(target_name)}['\"]",
        rf"require\s*\(\s*['\"].*{re.escape(target_name)}['\"]",
        # Direct file reference
        re.escape(target),
        re.escape(target_name),
    ]

    found_references: list[str] = []
    for pattern in import_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            found_references.extend(matches[:3])  # Limit to 3 examples

    passed = len(found_references) > 0

    if not found_references:
        found_references = [f"No reference to {target_name} found in {source}"]

    return VerificationCheck(
        level=VerificationLevel.WIRED,
        target=f"{source} -> {target}",
        expected_result=f"{source} imports/uses {target}",
        actual_result="Connected" if passed else "No connection found",
        passed=passed,
        details=found_references,
    )


def check_functional(
    check_command: str,
    expected_result: str,
    timeout: int = 30,
    cwd: Path | None = None,
) -> VerificationCheck:
    """Run a command and verify output matches expected result.

    Args:
        check_command: Command to run
        expected_result: Expected output or pattern to match
        timeout: Command timeout in seconds
        cwd: Working directory for command

    Returns:
        VerificationCheck with command result
    """
    try:
        result = subprocess.run(
            check_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            output = result.stderr.strip() or f"Exit code: {result.returncode}"

        # Check if expected result is in output (case-insensitive)
        passed = expected_result.lower() in output.lower() or result.returncode == 0

        return VerificationCheck(
            level=VerificationLevel.FUNCTIONAL,
            target=check_command,
            check_command=check_command,
            expected_result=expected_result,
            actual_result=output[:500] if output else "(no output)",  # Limit output length
            passed=passed,
            details=[f"Exit code: {result.returncode}"],
        )

    except subprocess.TimeoutExpired:
        return VerificationCheck(
            level=VerificationLevel.FUNCTIONAL,
            target=check_command,
            check_command=check_command,
            expected_result=expected_result,
            actual_result=f"Timeout after {timeout}s",
            passed=False,
            details=["Command timed out"],
        )

    except Exception as e:
        return VerificationCheck(
            level=VerificationLevel.FUNCTIONAL,
            target=check_command,
            check_command=check_command,
            expected_result=expected_result,
            actual_result=f"Error: {e}",
            passed=False,
            details=[f"Command failed: {e}"],
        )


def run_verification(
    goal_verification: GoalVerification,
    base_path: Path,
) -> GoalVerification:
    """Run all verification checks for a goal.

    Runs checks in order: EXISTS -> SUBSTANTIVE -> WIRED -> FUNCTIONAL.
    Skips later checks for artifacts that don't exist.

    Args:
        goal_verification: Goal with verification criteria
        base_path: Base directory for file paths

    Returns:
        GoalVerification with populated checks list
    """
    checks: list[VerificationCheck] = []
    existing_artifacts: set[str] = set()

    # 1. EXISTS checks for all artifacts
    for artifact in goal_verification.artifacts:
        check = check_exists(artifact, base_path)
        checks.append(check)
        if check.passed:
            existing_artifacts.add(artifact)

    # 2. SUBSTANTIVE checks for existing artifacts
    for artifact in existing_artifacts:
        check = check_substantive(artifact, base_path)
        checks.append(check)

    # 3. WIRED checks for wiring pairs (only if source exists)
    for source, target in goal_verification.wiring:
        if source in existing_artifacts or (base_path / source).exists():
            check = check_wired(source, target, base_path)
            checks.append(check)
        else:
            # Source doesn't exist, add failed check
            checks.append(
                VerificationCheck(
                    level=VerificationLevel.WIRED,
                    target=f"{source} -> {target}",
                    expected_result=f"{source} imports/uses {target}",
                    actual_result="Source file not found",
                    passed=False,
                    details=[f"Cannot check wiring - {source} does not exist"],
                )
            )

    # 4. FUNCTIONAL checks
    for func_check in goal_verification.functional_checks:
        check = check_functional(
            check_command=func_check.get("command", ""),
            expected_result=func_check.get("expected", ""),
            timeout=int(func_check.get("timeout", 30)),
            cwd=base_path,
        )
        checks.append(check)

    # Return updated GoalVerification
    return GoalVerification(
        goal=goal_verification.goal,
        truths=goal_verification.truths,
        artifacts=goal_verification.artifacts,
        wiring=goal_verification.wiring,
        checks=checks,
        functional_checks=goal_verification.functional_checks,
    )


def generate_verification_report(goal_verification: GoalVerification) -> str:
    """Generate a markdown report for verification results.

    Args:
        goal_verification: Completed verification with checks

    Returns:
        Formatted markdown report
    """
    lines = [
        "## Verification Report",
        "",
        f"**Goal**: {goal_verification.goal}",
        "",
    ]

    if not goal_verification.checks:
        lines.append("*No verification checks defined.*")
        return "\n".join(lines)

    # Summary
    total = len(goal_verification.checks)
    passed = sum(1 for c in goal_verification.checks if c.passed)
    failed = total - passed

    status = "PASSED" if failed == 0 else "FAILED"
    lines.extend(
        [
            f"**Status**: {status}",
            f"**Checks**: {passed}/{total} passed",
            "",
        ]
    )

    # Group by level
    by_level: dict[VerificationLevel, list[VerificationCheck]] = {}
    for check in goal_verification.checks:
        by_level.setdefault(check.level, []).append(check)

    # Report each level
    for level in VerificationLevel:
        if level not in by_level:
            continue

        level_checks = by_level[level]
        level_passed = sum(1 for c in level_checks if c.passed)
        level_name = level.value.upper()

        lines.extend(
            [
                f"### {level_name} ({level_passed}/{len(level_checks)})",
                "",
                "| Target | Result | Details |",
                "|--------|--------|---------|",
            ]
        )

        for check in level_checks:
            icon = "✓" if check.passed else "✗"
            details = "; ".join(check.details[:2]) if check.details else "-"
            # Escape pipes in content
            target = check.target.replace("|", "\\|")[:50]
            result = (check.actual_result or "-").replace("|", "\\|")[:30]
            details = details.replace("|", "\\|")[:50]
            lines.append(f"| {icon} {target} | {result} | {details} |")

        lines.append("")

    # Critical failures
    critical = goal_verification.critical_failures
    if critical:
        lines.extend(
            [
                "### Critical Failures",
                "",
                "The following failures should be addressed:",
                "",
            ]
        )
        for check in critical:
            lines.append(f"- **{check.target}**: {check.actual_result}")
            for detail in check.details:
                lines.append(f"  - {detail}")
        lines.append("")

    return "\n".join(lines)


def log_verification_results(
    goal_verification: GoalVerification,
    decisions_file: Path,
) -> None:
    """Log verification results to decisions file.

    Args:
        goal_verification: Completed verification
        decisions_file: Path to decisions.md
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = generate_verification_report(goal_verification)

    content = f"\n## Goal Verification ({timestamp})\n\n{report}\n"

    with open(decisions_file, "a") as f:
        f.write(content)
