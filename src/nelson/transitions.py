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
    Tasks are marked as:
    - [ ] = unchecked
    - [x] = checked (complete)
    - [~] = skipped (also considered complete)

    Args:
        phase: Phase to check
        plan_file: Path to plan.md file

    Returns:
        True if phase has at least one unchecked task, False otherwise
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
            # Unchecked task pattern: - [ ] or -  [ ] (with varying whitespace)
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("-  [ ]"):
                # Found an unchecked task
                return True

    return False


def determine_next_phase(
    current: Phase, plan_file: Path, should_advance: bool = True
) -> Phase | None:
    """Determine the next phase based on current phase and completion status.

    Phase transitions:
    - PLAN → IMPLEMENT (when all Phase 1 tasks checked)
    - IMPLEMENT → REVIEW (when all Phase 2 tasks checked)
    - REVIEW → REVIEW (if unchecked tasks remain) OR TEST (if all checked)
    - TEST → TEST (if unchecked tasks remain) OR FINAL_REVIEW (if all checked)
    - FINAL_REVIEW → TEST (if unchecked tasks remain) OR COMMIT (if all checked)
    - COMMIT → None (workflow complete)

    Args:
        current: Current phase
        plan_file: Path to plan.md file
        should_advance: Whether phase should advance (from EXIT_SIGNAL/completion check)

    Returns:
        Next phase, or None if workflow is complete
    """
    # If should_advance is False, stay in current phase (unless it's a non-looping phase)
    if not should_advance and current.can_loop:
        return current

    # Phase 1 (PLAN) → Phase 2 (IMPLEMENT)
    if current == Phase.PLAN:
        return Phase.IMPLEMENT

    # Phase 2 (IMPLEMENT) → Phase 3 (REVIEW)
    if current == Phase.IMPLEMENT:
        return Phase.REVIEW

    # Phase 3 (REVIEW) → Phase 3 (loop if unchecked) OR Phase 4 (TEST)
    if current == Phase.REVIEW:
        if has_unchecked_tasks(Phase.REVIEW, plan_file):
            return Phase.REVIEW
        return Phase.TEST

    # Phase 4 (TEST) → Phase 4 (loop if unchecked) OR Phase 5 (FINAL_REVIEW)
    if current == Phase.TEST:
        if has_unchecked_tasks(Phase.TEST, plan_file):
            return Phase.TEST
        return Phase.FINAL_REVIEW

    # Phase 5 (FINAL_REVIEW) → Phase 4 (TEST if unchecked) OR Phase 6 (COMMIT)
    if current == Phase.FINAL_REVIEW:
        if has_unchecked_tasks(Phase.FINAL_REVIEW, plan_file):
            # If final review found issues, go back to TEST to verify fixes
            return Phase.TEST
        return Phase.COMMIT

    # Phase 6 (COMMIT) → None (done)
    if current == Phase.COMMIT:
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
