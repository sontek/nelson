"""Phase transition logic and completion detection for Nelson workflow.

This module handles determining when to advance phases vs loop, based on:
- Current phase
- Completion status of phase tasks
- EXIT_SIGNAL from status block
- Circuit breaker conditions
"""

from pathlib import Path

from nelson.phases import Phase


def has_unchecked_tasks(phase: Phase, plan_file: Path) -> bool:
    """Check if a phase section has unchecked tasks.

    Scans the plan file for the phase section and counts unchecked tasks.
    Only checks top-level tasks (not indented sub-tasks).
    Tasks are marked as:
    - [ ] = unchecked
    - [x] = checked (complete)
    - [~] = skipped (also considered complete)

    Args:
        phase: Phase to check
        plan_file: Path to plan.md file

    Returns:
        True if phase has at least one unchecked top-level task, False otherwise
    """
    if not plan_file.exists():
        return False

    content = plan_file.read_text()
    lines = content.splitlines()

    # Find the phase section
    in_target_phase = False
    phase_header = f"## Phase {phase.value}:"

    for line in lines:
        # Check if we hit a phase header
        if line.startswith("## Phase "):
            # Are we entering the target phase?
            in_target_phase = line.startswith(phase_header)
            continue

        # If we're in the target phase, check for unchecked tasks
        if in_target_phase:
            # Only check top-level tasks (not indented)
            # Top-level tasks start with "- [ ]" at column 0
            # Sub-tasks are indented with spaces/tabs
            if line.startswith("- [ ]") or line.startswith("-  [ ]"):
                # Found an unchecked top-level task
                return True

    return False


def determine_next_phase(
    current: Phase,
    plan_file: Path,
    should_advance: bool = True,
    comprehensive: bool = False,
) -> Phase | None:
    """Determine the next phase based on current phase and completion status.

    Standard Mode Phase transitions:
    - PLAN → IMPLEMENT (when all Phase 1 tasks checked)
    - IMPLEMENT → TEST (when all Phase 2 tasks checked)
    - TEST → TEST (if unchecked tasks remain) OR REVIEW (if all checked)
    - REVIEW → IMPLEMENT (if issues found) OR COMMIT (if all checked)
    - COMMIT → None (workflow complete)

    Comprehensive Mode Phase transitions (adds DISCOVER and ROADMAP):
    - DISCOVER → PLAN
    - PLAN → ... → COMMIT (same as standard)
    - COMMIT → ROADMAP
    - ROADMAP → None (workflow complete)

    Args:
        current: Current phase
        plan_file: Path to plan.md file
        should_advance: Whether phase should advance (from EXIT_SIGNAL/completion check)
        comprehensive: If True, use comprehensive mode (7 phases)

    Returns:
        Next phase, or None if workflow is complete
    """
    # If should_advance is False, stay in current phase (unless it's a non-looping phase)
    if not should_advance and current.can_loop:
        return current

    # Phase 0 (DISCOVER) → Phase 1 (PLAN) [comprehensive mode only]
    if current == Phase.DISCOVER:
        return Phase.PLAN

    # Phase 1 (PLAN) → Phase 2 (IMPLEMENT)
    if current == Phase.PLAN:
        return Phase.IMPLEMENT

    # Phase 2 (IMPLEMENT) → Phase 3 (TEST)
    if current == Phase.IMPLEMENT:
        return Phase.TEST

    # Phase 3 (TEST) → Phase 3 (loop if unchecked) OR Phase 4 (REVIEW)
    if current == Phase.TEST:
        if has_unchecked_tasks(Phase.TEST, plan_file):
            return Phase.TEST
        return Phase.REVIEW

    # Phase 4 (REVIEW) → Phase 2 (IMPLEMENT if issues found) OR Phase 5 (COMMIT)
    if current == Phase.REVIEW:
        # Check if REVIEW added Fix tasks to Phase 2 (IMPLEMENT)
        if has_unchecked_tasks(Phase.IMPLEMENT, plan_file):
            # Review found issues and added Fix tasks to Phase 2
            # Loop back to IMPLEMENT for full SDLC cycle: IMPLEMENT → TEST → REVIEW
            # This ensures fixes get tested and re-reviewed
            return Phase.IMPLEMENT
        return Phase.COMMIT

    # Phase 5 (COMMIT) → ROADMAP (comprehensive) OR None (standard)
    if current == Phase.COMMIT:
        if comprehensive:
            return Phase.ROADMAP
        return None

    # Phase 6 (ROADMAP) → None (workflow complete) [comprehensive mode only]
    if current == Phase.ROADMAP:
        return None

    raise ValueError(f"Unknown phase: {current}")


def is_phase_complete(phase: Phase, plan_file: Path) -> bool:
    """Check if a phase is complete (all tasks checked).

    A phase is complete when it has no unchecked tasks.

    Args:
        phase: Phase to check
        plan_file: Path to plan.md file

    Returns:
        True if phase is complete, False otherwise
    """
    return not has_unchecked_tasks(phase, plan_file)


def should_transition_phase(
    current_phase: Phase,
    plan_file: Path,
    exit_signal: bool = False,
) -> bool:
    """Determine if workflow should transition to next phase.

    Transition occurs when:
    1. EXIT_SIGNAL is True (from status block), AND
    2. Current phase has all tasks checked, OR
    3. Current phase is non-looping (PLAN, IMPLEMENT, COMMIT)

    Args:
        current_phase: Current workflow phase
        plan_file: Path to plan.md file
        exit_signal: EXIT_SIGNAL value from status block

    Returns:
        True if workflow should transition to next phase
    """
    # If EXIT_SIGNAL is False, never transition
    if not exit_signal:
        return False

    # Non-looping phases always advance when EXIT_SIGNAL is true
    if not current_phase.can_loop:
        return True

    # Looping phases only advance when all tasks are checked
    return is_phase_complete(current_phase, plan_file)
