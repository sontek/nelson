"""
Plan validation for Nelson workflow.

This module validates plans before transitioning from PLAN to IMPLEMENT phase,
ensuring no unresolved questions or ambiguities remain.
"""

import re
from pathlib import Path

from nelson.logging_config import get_logger

logger = get_logger()


# Patterns that indicate unresolved questions or decisions
UNRESOLVED_PATTERNS = [
    # Direct questions
    r"\?\s*$",  # Lines ending with ?
    r"^\s*-\s*\?\s*",  # Bullet points that are just ?
    # TBD/TBA markers
    r"\bTBD\b",
    r"\bTBA\b",
    r"\bTO\s*BE\s*DETERMINED\b",
    r"\bTO\s*BE\s*DECIDED\b",
    # Placeholder markers
    r"\bPLACEHOLDER\b",
    r"\bTODO:\s*decide\b",
    r"\bTODO:\s*clarify\b",
    r"\bTODO:\s*confirm\b",
    # Uncertainty markers
    r"\bUNSURE\b",
    r"\bUNCLEAR\b",
    r"\bNEED\s*TO\s*CONFIRM\b",
    r"\bNEED\s*TO\s*CLARIFY\b",
    r"\bNEED\s*TO\s*DECIDE\b",
    r"\bPENDING\s*DECISION\b",
    r"\bAWAITING\s*INPUT\b",
    # Option markers without resolution
    r"\bOPTION\s*[AB12]\b.*\bOR\b.*\bOPTION\s*[AB12]\b",
    r"\bEITHER\b.*\bOR\b.*\?",
    # Question sections
    r"^#+\s*(?:Open\s*)?Questions?\s*$",
    r"^#+\s*Unresolved\s*$",
    r"^#+\s*Decisions\s*Needed\s*$",
]

# Compiled patterns for efficiency
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in UNRESOLVED_PATTERNS]


class PlanValidationResult:
    """Result of plan validation."""

    def __init__(self, is_valid: bool, issues: list[str] | None = None) -> None:
        """
        Initialize validation result.

        Args:
            is_valid: Whether the plan passed validation
            issues: List of validation issues found (if any)
        """
        self.is_valid = is_valid
        self.issues = issues or []

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.is_valid


def validate_plan_for_questions(plan_file: Path) -> PlanValidationResult:
    """
    Validate that a plan has no unresolved questions.

    Checks for patterns indicating open questions, TBD items, or
    unresolved decisions that should be clarified before implementation.

    Args:
        plan_file: Path to plan.md file

    Returns:
        PlanValidationResult with is_valid=True if no issues found
    """
    if not plan_file.exists():
        return PlanValidationResult(
            is_valid=False,
            issues=["Plan file does not exist"]
        )

    content = plan_file.read_text()
    lines = content.splitlines()
    issues: list[str] = []

    for line_num, line in enumerate(lines, start=1):
        # Skip code blocks
        if line.strip().startswith("```"):
            continue

        # Skip lines that are already marked complete
        if "- [x]" in line or "- [~]" in line:
            continue

        # Check each pattern
        for pattern in COMPILED_PATTERNS:
            match = pattern.search(line)
            if match:
                # Extract a clean snippet for the issue message
                snippet = line.strip()[:80]
                if len(line.strip()) > 80:
                    snippet += "..."
                issues.append(f"Line {line_num}: {snippet}")
                break  # Only report once per line

    return PlanValidationResult(
        is_valid=len(issues) == 0,
        issues=issues
    )


def validate_plan_has_implementation_tasks(plan_file: Path) -> PlanValidationResult:
    """
    Validate that a plan has actual implementation tasks in Phase 2.

    Args:
        plan_file: Path to plan.md file

    Returns:
        PlanValidationResult with is_valid=True if Phase 2 has tasks
    """
    if not plan_file.exists():
        return PlanValidationResult(
            is_valid=False,
            issues=["Plan file does not exist"]
        )

    content = plan_file.read_text()
    lines = content.splitlines()

    # Find Phase 2 section
    in_phase_2 = False
    has_tasks = False

    for line in lines:
        # Check for phase headers
        if "## Phase 2" in line or "## IMPLEMENT" in line.upper():
            in_phase_2 = True
            continue
        elif line.startswith("## Phase") or line.startswith("## "):
            if in_phase_2:
                break  # Left Phase 2 section
            continue

        # Count tasks in Phase 2
        if in_phase_2 and line.strip().startswith("- ["):
            has_tasks = True
            break

    if not has_tasks:
        return PlanValidationResult(
            is_valid=False,
            issues=["Phase 2 (IMPLEMENT) has no tasks defined"]
        )

    return PlanValidationResult(is_valid=True)


def validate_plan(plan_file: Path, strict: bool = False) -> PlanValidationResult:
    """
    Run all plan validations.

    Args:
        plan_file: Path to plan.md file
        strict: If True, treat warnings as errors

    Returns:
        PlanValidationResult combining all validations
    """
    all_issues: list[str] = []

    # Check for unresolved questions
    questions_result = validate_plan_for_questions(plan_file)
    if not questions_result.is_valid:
        all_issues.extend([f"Unresolved: {issue}" for issue in questions_result.issues])

    # Check for implementation tasks
    tasks_result = validate_plan_has_implementation_tasks(plan_file)
    if not tasks_result.is_valid:
        all_issues.extend([f"Structure: {issue}" for issue in tasks_result.issues])

    # In non-strict mode, unresolved questions are warnings (logged but don't block)
    if all_issues and not strict:
        for issue in all_issues:
            logger.warning(f"Plan validation: {issue}")
        # Only fail if structural issues (no tasks)
        return PlanValidationResult(
            is_valid=tasks_result.is_valid,
            issues=all_issues
        )

    return PlanValidationResult(
        is_valid=len(all_issues) == 0,
        issues=all_issues
    )


def log_validation_warnings(plan_file: Path) -> None:
    """
    Log any plan validation issues as warnings.

    Useful for non-blocking validation that still informs the user.

    Args:
        plan_file: Path to plan.md file
    """
    result = validate_plan_for_questions(plan_file)
    if not result.is_valid:
        logger.warning("Plan contains unresolved questions:")
        for issue in result.issues[:5]:  # Limit to first 5
            logger.warning(f"  {issue}")
        if len(result.issues) > 5:
            logger.warning(f"  ... and {len(result.issues) - 5} more")
