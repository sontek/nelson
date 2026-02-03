"""Tests for phase transition logic and completion detection."""

from pathlib import Path

import pytest

from nelson.phases import Phase
from nelson.transitions import (
    determine_next_phase,
    has_unchecked_tasks,
    is_phase_complete,
    should_transition_phase,
)


@pytest.fixture
def sample_plan_file(tmp_path: Path) -> Path:
    """Create a sample plan.md file for testing."""
    plan_content = """# Implementation Plan

## Phase 1: PLAN
- [x] Task 1 complete
- [x] Task 2 complete
- [~] Task 3 skipped

## Phase 2: IMPLEMENT
- [x] Completed task
- [ ] Unchecked task
- [x] Another completed task

## Phase 3: REVIEW
- [ ] Review task 1
- [ ] Review task 2

## Phase 4: TEST
- [x] All tests complete

## Phase 5: FINAL_REVIEW
- [x] Final review complete

## Phase 6: COMMIT
- [ ] Commit task
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content)
    return plan_file


@pytest.fixture
def all_complete_plan_file(tmp_path: Path) -> Path:
    """Create a plan.md file where all tasks are complete."""
    plan_content = """# Implementation Plan

## Phase 1: PLAN
- [x] Task 1 complete
- [x] Task 2 complete

## Phase 2: IMPLEMENT
- [x] Task 1 complete
- [x] Task 2 complete

## Phase 3: REVIEW
- [x] Review complete

## Phase 4: TEST
- [x] Tests passing

## Phase 5: FINAL_REVIEW
- [x] Final review done

## Phase 6: COMMIT
- [x] Committed
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content)
    return plan_file


@pytest.fixture
def empty_plan_file(tmp_path: Path) -> Path:
    """Create an empty plan.md file."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("")
    return plan_file


class TestHasUncheckedTasks:
    """Tests for has_unchecked_tasks function."""

    def test_phase_with_unchecked_tasks(self, sample_plan_file: Path) -> None:
        """Phase 2 has unchecked tasks."""
        assert has_unchecked_tasks(Phase.IMPLEMENT, sample_plan_file)

    def test_phase_with_all_checked(self, sample_plan_file: Path) -> None:
        """Phase 1 has all tasks checked or skipped."""
        assert not has_unchecked_tasks(Phase.PLAN, sample_plan_file)

    def test_phase_4_all_complete(self, sample_plan_file: Path) -> None:
        """Phase 4 has all tasks complete."""
        assert not has_unchecked_tasks(Phase.TEST, sample_plan_file)

    def test_phase_3_has_unchecked(self, sample_plan_file: Path) -> None:
        """Phase 3 has unchecked tasks."""
        assert has_unchecked_tasks(Phase.REVIEW, sample_plan_file)

    def test_nonexistent_plan_file(self, tmp_path: Path) -> None:
        """Returns False when plan file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.md"
        assert not has_unchecked_tasks(Phase.PLAN, nonexistent)

    def test_empty_plan_file(self, empty_plan_file: Path) -> None:
        """Returns False for empty plan file."""
        assert not has_unchecked_tasks(Phase.PLAN, empty_plan_file)

    def test_all_phases_checked(self, all_complete_plan_file: Path) -> None:
        """All phases return False when all tasks checked."""
        for phase in Phase:
            assert not has_unchecked_tasks(phase, all_complete_plan_file)


class TestIsPhaseComplete:
    """Tests for is_phase_complete function."""

    def test_complete_phase(self, sample_plan_file: Path) -> None:
        """Phase 1 is complete."""
        assert is_phase_complete(Phase.PLAN, sample_plan_file)

    def test_incomplete_phase(self, sample_plan_file: Path) -> None:
        """Phase 2 is incomplete."""
        assert not is_phase_complete(Phase.IMPLEMENT, sample_plan_file)

    def test_all_complete(self, all_complete_plan_file: Path) -> None:
        """All phases complete."""
        for phase in Phase:
            assert is_phase_complete(phase, all_complete_plan_file)


class TestDetermineNextPhase:
    """Tests for determine_next_phase function."""

    def test_plan_to_implement(self, sample_plan_file: Path) -> None:
        """Phase 1 always advances to Phase 2."""
        next_phase = determine_next_phase(Phase.PLAN, sample_plan_file)
        assert next_phase == Phase.IMPLEMENT

    def test_implement_to_review(self, sample_plan_file: Path) -> None:
        """Phase 2 always advances to Phase 3."""
        next_phase = determine_next_phase(Phase.IMPLEMENT, sample_plan_file)
        assert next_phase == Phase.REVIEW

    def test_review_loops_when_unchecked(self, sample_plan_file: Path) -> None:
        """Phase 3 loops when it has unchecked tasks."""
        next_phase = determine_next_phase(Phase.REVIEW, sample_plan_file)
        assert next_phase == Phase.REVIEW

    def test_review_advances_when_complete(self, all_complete_plan_file: Path) -> None:
        """Phase 3 advances to Phase 4 when all tasks checked."""
        next_phase = determine_next_phase(Phase.REVIEW, all_complete_plan_file)
        assert next_phase == Phase.TEST

    def test_test_loops_when_unchecked(self, tmp_path: Path) -> None:
        """Phase 4 loops when it has unchecked tasks."""
        plan_content = """
## Phase 4: TEST
- [ ] Test not passing
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan_content)
        next_phase = determine_next_phase(Phase.TEST, plan_file)
        assert next_phase == Phase.TEST

    def test_test_advances_when_complete(self, all_complete_plan_file: Path) -> None:
        """Phase 4 advances to Phase 5 when all tests pass."""
        next_phase = determine_next_phase(Phase.TEST, all_complete_plan_file)
        assert next_phase == Phase.FINAL_REVIEW

    def test_final_review_returns_to_implement_when_fixes_needed(self, tmp_path: Path) -> None:
        """Phase 5 returns to Phase 2 when it adds Fix tasks to Phase 2 (critical issues found)."""
        plan_content = """
## Phase 2: IMPLEMENT
- [ ] Fix: Critical bug in auth.py:123

## Phase 5: FINAL_REVIEW
- [x] Review completed
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan_content)
        next_phase = determine_next_phase(Phase.FINAL_REVIEW, plan_file)
        assert next_phase == Phase.IMPLEMENT

    def test_final_review_advances_when_complete(self, all_complete_plan_file: Path) -> None:
        """Phase 5 advances to Phase 6 when all tasks checked."""
        next_phase = determine_next_phase(Phase.FINAL_REVIEW, all_complete_plan_file)
        assert next_phase == Phase.COMMIT

    def test_commit_returns_none(self, sample_plan_file: Path) -> None:
        """Phase 6 returns None (workflow complete)."""
        next_phase = determine_next_phase(Phase.COMMIT, sample_plan_file)
        assert next_phase is None

    def test_should_advance_false_on_looping_phase(self, sample_plan_file: Path) -> None:
        """When should_advance=False, looping phases stay in current phase."""
        next_phase = determine_next_phase(Phase.REVIEW, sample_plan_file, should_advance=False)
        assert next_phase == Phase.REVIEW

    def test_should_advance_false_on_non_looping_phase(self, sample_plan_file: Path) -> None:
        """When should_advance=False, non-looping phases still advance."""
        next_phase = determine_next_phase(Phase.PLAN, sample_plan_file, should_advance=False)
        assert next_phase == Phase.IMPLEMENT


class TestShouldTransitionPhase:
    """Tests for should_transition_phase function."""

    def test_no_transition_without_exit_signal(self, sample_plan_file: Path) -> None:
        """Never transition when EXIT_SIGNAL is False."""
        # Even if phase is complete
        assert not should_transition_phase(Phase.PLAN, sample_plan_file, exit_signal=False)
        assert not should_transition_phase(Phase.TEST, sample_plan_file, exit_signal=False)

    def test_non_looping_phase_transitions_with_exit_signal(self, sample_plan_file: Path) -> None:
        """Non-looping phases always transition when EXIT_SIGNAL is True."""
        # Phase 1 (PLAN) is non-looping
        assert should_transition_phase(Phase.PLAN, sample_plan_file, exit_signal=True)
        # Phase 2 (IMPLEMENT) is non-looping
        assert should_transition_phase(Phase.IMPLEMENT, sample_plan_file, exit_signal=True)

    def test_looping_phase_with_complete_tasks(self, all_complete_plan_file: Path) -> None:
        """Looping phase transitions when EXIT_SIGNAL=True and all tasks checked."""
        # Phase 3 (REVIEW) is looping and complete
        assert should_transition_phase(Phase.REVIEW, all_complete_plan_file, exit_signal=True)
        # Phase 4 (TEST) is looping and complete
        assert should_transition_phase(Phase.TEST, all_complete_plan_file, exit_signal=True)

    def test_looping_phase_with_incomplete_tasks(self, sample_plan_file: Path) -> None:
        """Looping phase does NOT transition when tasks are incomplete."""
        # Phase 3 (REVIEW) is looping and has unchecked tasks
        assert not should_transition_phase(Phase.REVIEW, sample_plan_file, exit_signal=True)
        # Phase 4 (TEST) is looping - check with incomplete phase
        plan_content = """
## Phase 4: TEST
- [ ] Test not passing
"""
        plan_file = sample_plan_file.parent / "incomplete_test.md"
        plan_file.write_text(plan_content)
        assert not should_transition_phase(Phase.TEST, plan_file, exit_signal=True)

    def test_commit_phase_with_complete_tasks(self, all_complete_plan_file: Path) -> None:
        """Phase 6 (COMMIT) transitions when complete and EXIT_SIGNAL=True."""
        assert should_transition_phase(Phase.COMMIT, all_complete_plan_file, exit_signal=True)


class TestTransitionIntegration:
    """Integration tests for complete transition workflows."""

    def test_complete_workflow_progression(self, all_complete_plan_file: Path) -> None:
        """Test complete workflow from PLAN to COMMIT with all tasks complete."""
        phases = [
            (Phase.PLAN, Phase.IMPLEMENT),
            (Phase.IMPLEMENT, Phase.REVIEW),
            (Phase.REVIEW, Phase.TEST),
            (Phase.TEST, Phase.FINAL_REVIEW),
            (Phase.FINAL_REVIEW, Phase.COMMIT),
            (Phase.COMMIT, None),
        ]

        for current, expected_next in phases:
            next_phase = determine_next_phase(current, all_complete_plan_file)
            assert next_phase == expected_next

    def test_review_loop_until_complete(self, tmp_path: Path) -> None:
        """Test Phase 3 (REVIEW) loops until tasks are complete."""
        # Start with incomplete review
        plan_content = """
## Phase 3: REVIEW
- [ ] Review task
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan_content)

        # Should loop
        next_phase = determine_next_phase(Phase.REVIEW, plan_file)
        assert next_phase == Phase.REVIEW

        # Mark complete
        plan_content = """
## Phase 3: REVIEW
- [x] Review task
"""
        plan_file.write_text(plan_content)

        # Should advance
        next_phase = determine_next_phase(Phase.REVIEW, plan_file)
        assert next_phase == Phase.TEST

    def test_final_review_returns_to_implement(self, tmp_path: Path) -> None:
        """Test Phase 5 returns to Phase 2 when critical issues found."""
        plan_content = """
## Phase 2: IMPLEMENT
- [ ] Fix: Critical issue found during final review

## Phase 5: FINAL_REVIEW
- [x] Review completed
"""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(plan_content)

        next_phase = determine_next_phase(Phase.FINAL_REVIEW, plan_file)
        assert next_phase == Phase.IMPLEMENT

    def test_transition_decision_with_exit_signal(self, sample_plan_file: Path) -> None:
        """Test transition decision based on EXIT_SIGNAL and phase completion."""
        # Phase 1 (non-looping) with EXIT_SIGNAL
        assert should_transition_phase(Phase.PLAN, sample_plan_file, exit_signal=True)
        next_phase = determine_next_phase(Phase.PLAN, sample_plan_file, should_advance=True)
        assert next_phase == Phase.IMPLEMENT

        # Phase 3 (looping) with EXIT_SIGNAL but incomplete tasks
        assert not should_transition_phase(Phase.REVIEW, sample_plan_file, exit_signal=True)
        # Should stay in REVIEW due to incomplete tasks
        next_phase = determine_next_phase(Phase.REVIEW, sample_plan_file)
        assert next_phase == Phase.REVIEW


class TestComprehensiveMode:
    """Tests for comprehensive mode (8 phases) transitions."""

    def test_discover_to_plan(self, sample_plan_file: Path) -> None:
        """DISCOVER phase always advances to PLAN."""
        next_phase = determine_next_phase(Phase.DISCOVER, sample_plan_file)
        assert next_phase == Phase.PLAN

    def test_discover_to_plan_comprehensive(self, sample_plan_file: Path) -> None:
        """DISCOVER phase advances to PLAN in comprehensive mode."""
        next_phase = determine_next_phase(Phase.DISCOVER, sample_plan_file, comprehensive=True)
        assert next_phase == Phase.PLAN

    def test_commit_returns_none_standard(self, sample_plan_file: Path) -> None:
        """COMMIT returns None in standard mode."""
        next_phase = determine_next_phase(Phase.COMMIT, sample_plan_file, comprehensive=False)
        assert next_phase is None

    def test_commit_to_roadmap_comprehensive(self, sample_plan_file: Path) -> None:
        """COMMIT advances to ROADMAP in comprehensive mode."""
        next_phase = determine_next_phase(Phase.COMMIT, sample_plan_file, comprehensive=True)
        assert next_phase == Phase.ROADMAP

    def test_roadmap_returns_none(self, sample_plan_file: Path) -> None:
        """ROADMAP returns None (workflow complete)."""
        next_phase = determine_next_phase(Phase.ROADMAP, sample_plan_file)
        assert next_phase is None

    def test_roadmap_returns_none_comprehensive(self, sample_plan_file: Path) -> None:
        """ROADMAP returns None even in comprehensive mode."""
        next_phase = determine_next_phase(Phase.ROADMAP, sample_plan_file, comprehensive=True)
        assert next_phase is None

    def test_complete_comprehensive_workflow(self, all_complete_plan_file: Path) -> None:
        """Test complete 8-phase workflow in comprehensive mode."""
        phases = [
            (Phase.DISCOVER, Phase.PLAN),
            (Phase.PLAN, Phase.IMPLEMENT),
            (Phase.IMPLEMENT, Phase.REVIEW),
            (Phase.REVIEW, Phase.TEST),
            (Phase.TEST, Phase.FINAL_REVIEW),
            (Phase.FINAL_REVIEW, Phase.COMMIT),
            (Phase.COMMIT, Phase.ROADMAP),
            (Phase.ROADMAP, None),
        ]

        for current, expected_next in phases:
            next_phase = determine_next_phase(
                current, all_complete_plan_file, comprehensive=True
            )
            assert next_phase == expected_next

    def test_middle_phases_same_in_both_modes(self, all_complete_plan_file: Path) -> None:
        """Middle phases (IMPLEMENT through FINAL_REVIEW) work same in both modes."""
        middle_phases = [
            (Phase.IMPLEMENT, Phase.REVIEW),
            (Phase.REVIEW, Phase.TEST),
            (Phase.TEST, Phase.FINAL_REVIEW),
            (Phase.FINAL_REVIEW, Phase.COMMIT),
        ]

        for current, expected_next in middle_phases:
            # Standard mode
            standard_next = determine_next_phase(
                current, all_complete_plan_file, comprehensive=False
            )
            # Comprehensive mode
            comprehensive_next = determine_next_phase(
                current, all_complete_plan_file, comprehensive=True
            )
            assert standard_next == expected_next
            assert comprehensive_next == expected_next
