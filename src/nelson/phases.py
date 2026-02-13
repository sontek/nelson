"""Phase definitions and metadata for Nelson's workflow.

Standard Mode (5 phases):
1. PLAN: Analyze task and create implementation plan
2. IMPLEMENT: Execute atomic tasks from plan, one commit per task
3. TEST: Run tests/linter/type-checker, fix failures
4. REVIEW: Comprehensive code review for bugs, patterns, quality, security
5. COMMIT: Commit any remaining uncommitted changes

Comprehensive Mode (7 phases):
0. DISCOVER: Research and explore codebase before planning
1. PLAN: Analyze task and create implementation plan
2. IMPLEMENT: Execute atomic tasks from plan, one commit per task
3. TEST: Run tests/linter/type-checker, fix failures
4. REVIEW: Comprehensive code review for bugs, patterns, quality, security
5. COMMIT: Commit any remaining uncommitted changes
6. ROADMAP: Document future improvements and technical debt

Phase Transitions (Standard):
- PLAN → IMPLEMENT (when plan.md exists with proper structure)
- IMPLEMENT → TEST (when all Phase 2 tasks are checked)
- TEST → TEST (loop if fixes added) OR → REVIEW (if passing)
- REVIEW → IMPLEMENT (if issues found, loops back) OR → COMMIT (if clean)
- COMMIT → Done (workflow complete)

Phase Transitions (Comprehensive):
- DISCOVER → PLAN (after research complete)
- PLAN → IMPLEMENT → TEST → REVIEW → COMMIT (same as standard)
- COMMIT → ROADMAP (document future work)
- ROADMAP → Done (workflow complete)
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


class Phase(IntEnum):
    """Workflow phases for Nelson orchestration.

    Standard mode uses phases 1-5 (PLAN through COMMIT).
    Comprehensive mode adds DISCOVER (0) at the start and ROADMAP (6) at the end.

    Each phase has a specific purpose and completion criteria.
    Phases can loop (TEST, REVIEW) or always advance (others).
    """

    # Comprehensive mode only - research phase
    DISCOVER = 0

    # Standard phases (1-5)
    PLAN = 1
    IMPLEMENT = 2
    TEST = 3
    REVIEW = 4  # Consolidated review phase (runs after TEST)
    COMMIT = 5

    # Comprehensive mode only - future work documentation
    ROADMAP = 6

    @property
    def name_str(self) -> str:
        """Get the human-readable name for this phase."""
        return PHASE_METADATA[self].name

    @property
    def can_loop(self) -> bool:
        """Check if this phase can loop back to itself or earlier phases."""
        return PHASE_METADATA[self].can_loop

    @property
    def model_type(self) -> Literal["default", "plan", "review"]:
        """Get which model configuration this phase uses."""
        return PHASE_METADATA[self].model_type


@dataclass(frozen=True)
class PhaseMetadata:
    """Metadata describing a phase's behavior and characteristics."""

    number: int
    name: str
    short_description: str
    can_loop: bool  # Can this phase loop back to itself or earlier phases?
    model_type: Literal["default", "plan", "review"]  # Which model config to use
    completion_check: str  # Description of how to detect phase completion


# Phase metadata registry
PHASE_METADATA: dict[Phase, PhaseMetadata] = {
    Phase.DISCOVER: PhaseMetadata(
        number=0,
        name="DISCOVER",
        short_description="Research and explore codebase before planning",
        can_loop=False,
        model_type="plan",
        completion_check=(
            "Codebase exploration complete, key patterns documented, "
            "dependencies mapped, architecture understood"
        ),
    ),
    Phase.PLAN: PhaseMetadata(
        number=1,
        name="PLAN",
        short_description="Analyze task and create implementation plan",
        can_loop=False,
        model_type="plan",
        completion_check=(
            "plan.md exists with proper structure (## Phase 1-5) "
            "AND all Phase 1 tasks are marked [x]"
        ),
    ),
    Phase.IMPLEMENT: PhaseMetadata(
        number=2,
        name="IMPLEMENT",
        short_description="Execute atomic tasks, one commit per task",
        can_loop=False,
        model_type="default",
        completion_check="All Phase 2 tasks are marked [x] and committed",
    ),
    Phase.TEST: PhaseMetadata(
        number=3,
        name="TEST",
        short_description="Run tests/linter/type-checker",
        can_loop=True,
        model_type="default",
        completion_check=(
            "All Phase 3 tasks [x]. Loops if failures found, advances to REVIEW if passing"
        ),
    ),
    Phase.REVIEW: PhaseMetadata(
        number=4,
        name="REVIEW",
        short_description="Comprehensive code review: bugs, patterns, quality, security",
        can_loop=True,
        model_type="review",
        completion_check=(
            "All Phase 4 tasks [x]. Loops to IMPLEMENT if issues found, advances to COMMIT if clean"
        ),
    ),
    Phase.COMMIT: PhaseMetadata(
        number=5,
        name="COMMIT",
        short_description="Commit any remaining uncommitted changes",
        can_loop=False,
        model_type="default",
        completion_check="All Phase 5 tasks [x]. Workflow complete (standard mode).",
    ),
    Phase.ROADMAP: PhaseMetadata(
        number=6,
        name="ROADMAP",
        short_description="Document future improvements and technical debt",
        can_loop=False,
        model_type="plan",
        completion_check=(
            "Future work documented in roadmap, technical debt cataloged, "
            "improvement suggestions recorded"
        ),
    ),
}


def determine_next_phase(current: Phase, comprehensive: bool = False) -> Phase | Literal["done"]:
    """Determine the next phase based on the current phase.

    Standard Mode Phase Transitions:
    - PLAN → IMPLEMENT (always)
    - IMPLEMENT → TEST (always)
    - TEST → TEST (loop if fixes) OR REVIEW (if passing)
    - REVIEW → IMPLEMENT (if issues found) OR COMMIT (if clean)
    - COMMIT → Done

    Comprehensive Mode Phase Transitions (adds DISCOVER and ROADMAP):
    - DISCOVER → PLAN
    - PLAN → IMPLEMENT → TEST → REVIEW → COMMIT (same as standard)
    - COMMIT → ROADMAP
    - ROADMAP → Done

    Note: The actual looping logic (checking for unchecked tasks) is handled
    by the workflow engine. This function just defines the advancement path.

    Args:
        current: Current phase
        comprehensive: If True, use comprehensive mode transitions (7 phases)

    Returns:
        Next phase, or "done" if workflow is complete
    """
    if current == Phase.DISCOVER:
        return Phase.PLAN
    elif current == Phase.PLAN:
        return Phase.IMPLEMENT
    elif current == Phase.IMPLEMENT:
        return Phase.TEST
    elif current == Phase.TEST:
        # Test advances to Review (looping happens if unchecked tasks remain)
        return Phase.REVIEW
    elif current == Phase.REVIEW:
        # Review can go back to Implement (if issues found) or advance to Commit
        # The workflow engine decides based on whether fixes were added to Phase 2
        return Phase.COMMIT
    elif current == Phase.COMMIT:
        # In comprehensive mode, continue to ROADMAP; otherwise done
        if comprehensive:
            return Phase.ROADMAP
        return "done"
    elif current == Phase.ROADMAP:
        return "done"
    else:
        raise ValueError(f"Unknown phase: {current}")


def get_starting_phase(comprehensive: bool = False) -> Phase:
    """Get the starting phase for a workflow.

    Args:
        comprehensive: If True, start with DISCOVER phase; otherwise PLAN

    Returns:
        Starting phase for the workflow
    """
    if comprehensive:
        return Phase.DISCOVER
    return Phase.PLAN


def get_phase_name(phase: Phase) -> str:
    """Get the human-readable name for a phase.

    Args:
        phase: Phase enum value

    Returns:
        Human-readable name (e.g., "PLAN", "IMPLEMENT", "FINAL-REVIEW")
    """
    return PHASE_METADATA[phase].name
