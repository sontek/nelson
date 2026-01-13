"""Phase definitions and metadata for Nelson's 6-phase workflow.

Phases:
1. PLAN: Analyze task and create implementation plan
2. IMPLEMENT: Execute atomic tasks from plan, one commit per task
3. REVIEW: Review all Phase 2 commits for bugs/quality issues
4. TEST: Run tests/linter/type-checker, fix failures
5. FINAL_REVIEW: Final verification before commit
6. COMMIT: Commit any remaining uncommitted changes

Phase Transitions:
- PLAN → IMPLEMENT (when plan.md exists with proper structure)
- IMPLEMENT → REVIEW (when all Phase 2 tasks are checked)
- REVIEW → REVIEW (loop if fixes added) OR → TEST (if clean)
- TEST → TEST (loop if fixes added) OR → FINAL_REVIEW (if passing)
- FINAL_REVIEW → TEST (if fixes needed) OR → COMMIT (if clean)
- COMMIT → Done (workflow complete)
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


class Phase(IntEnum):
    """6-phase workflow for Nelson orchestration.

    Each phase has a specific purpose and completion criteria.
    Phases can loop (REVIEW, TEST, FINAL_REVIEW) or always advance (PLAN, IMPLEMENT, COMMIT).
    """

    PLAN = 1
    IMPLEMENT = 2
    REVIEW = 3
    TEST = 4
    FINAL_REVIEW = 5
    COMMIT = 6

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
    Phase.PLAN: PhaseMetadata(
        number=1,
        name="PLAN",
        short_description="Analyze task and create implementation plan",
        can_loop=False,
        model_type="plan",
        completion_check=(
            "plan.md exists with proper structure (## Phase 1-6) "
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
    Phase.REVIEW: PhaseMetadata(
        number=3,
        name="REVIEW",
        short_description="Review Phase 2 commits for bugs/quality",
        can_loop=True,
        model_type="review",
        completion_check=(
            "All Phase 3 tasks [x]. Loops if review adds fix tasks, "
            "advances to TEST if clean"
        ),
    ),
    Phase.TEST: PhaseMetadata(
        number=4,
        name="TEST",
        short_description="Run tests/linter/type-checker",
        can_loop=True,
        model_type="default",
        completion_check=(
            "All Phase 4 tasks [x]. Loops if failures found, "
            "advances to FINAL_REVIEW if passing"
        ),
    ),
    Phase.FINAL_REVIEW: PhaseMetadata(
        number=5,
        name="FINAL-REVIEW",
        short_description="Final verification before commit",
        can_loop=True,
        model_type="review",
        completion_check=(
            "All Phase 5 tasks [x]. Returns to TEST if fixes needed, "
            "advances to COMMIT if clean"
        ),
    ),
    Phase.COMMIT: PhaseMetadata(
        number=6,
        name="COMMIT",
        short_description="Commit any remaining uncommitted changes",
        can_loop=False,
        model_type="default",
        completion_check="All Phase 6 tasks [x]. Workflow complete.",
    ),
}


def determine_next_phase(current: Phase) -> Phase | Literal["done"]:
    """Determine the next phase based on the current phase.

    Phase transitions:
    - PLAN → IMPLEMENT (always)
    - IMPLEMENT → REVIEW (always)
    - REVIEW → REVIEW (loop if fixes) OR TEST (if clean)
    - TEST → TEST (loop if fixes) OR FINAL_REVIEW (if passing)
    - FINAL_REVIEW → TEST (if fixes) OR COMMIT (if clean)
    - COMMIT → Done

    Note: The actual looping logic (checking for unchecked tasks) is handled
    by the workflow engine. This function just defines the advancement path.

    Args:
        current: Current phase

    Returns:
        Next phase, or "done" if workflow is complete
    """
    if current == Phase.PLAN:
        return Phase.IMPLEMENT
    elif current == Phase.IMPLEMENT:
        return Phase.REVIEW
    elif current == Phase.REVIEW:
        # Review advances to Test (looping happens if unchecked tasks remain)
        return Phase.TEST
    elif current == Phase.TEST:
        # Test advances to Final-Review (looping happens if unchecked tasks remain)
        return Phase.FINAL_REVIEW
    elif current == Phase.FINAL_REVIEW:
        # Final-Review can go back to Test (if fixes needed) or advance to Commit
        # The workflow engine decides based on whether fixes were added
        return Phase.COMMIT
    elif current == Phase.COMMIT:
        return "done"
    else:
        raise ValueError(f"Unknown phase: {current}")


def get_phase_name(phase: Phase) -> str:
    """Get the human-readable name for a phase.

    Args:
        phase: Phase enum value

    Returns:
        Human-readable name (e.g., "PLAN", "IMPLEMENT", "FINAL-REVIEW")
    """
    return PHASE_METADATA[phase].name
