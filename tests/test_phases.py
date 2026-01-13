"""Tests for phase definitions and metadata."""

import pytest

from nelson.phases import (
    PHASE_METADATA,
    Phase,
    determine_next_phase,
    get_phase_name,
)


class TestPhaseEnum:
    """Test Phase enum values and properties."""

    def test_phase_values(self) -> None:
        """Phases should have correct integer values."""
        assert Phase.PLAN.value == 1
        assert Phase.IMPLEMENT.value == 2
        assert Phase.REVIEW.value == 3
        assert Phase.TEST.value == 4
        assert Phase.FINAL_REVIEW.value == 5
        assert Phase.COMMIT.value == 6

    def test_phase_name_str(self) -> None:
        """Each phase should return its human-readable name."""
        assert Phase.PLAN.name_str == "PLAN"
        assert Phase.IMPLEMENT.name_str == "IMPLEMENT"
        assert Phase.REVIEW.name_str == "REVIEW"
        assert Phase.TEST.name_str == "TEST"
        assert Phase.FINAL_REVIEW.name_str == "FINAL-REVIEW"
        assert Phase.COMMIT.name_str == "COMMIT"

    def test_phase_can_loop(self) -> None:
        """Phases that can loop should be correctly identified."""
        # Cannot loop (always advance)
        assert not Phase.PLAN.can_loop
        assert not Phase.IMPLEMENT.can_loop
        assert not Phase.COMMIT.can_loop

        # Can loop (may stay in phase or go back)
        assert Phase.REVIEW.can_loop
        assert Phase.TEST.can_loop
        assert Phase.FINAL_REVIEW.can_loop

    def test_phase_model_type(self) -> None:
        """Phases should use correct model types."""
        assert Phase.PLAN.model_type == "plan"
        assert Phase.IMPLEMENT.model_type == "default"
        assert Phase.REVIEW.model_type == "review"
        assert Phase.TEST.model_type == "default"
        assert Phase.FINAL_REVIEW.model_type == "review"
        assert Phase.COMMIT.model_type == "default"


class TestPhaseMetadata:
    """Test PhaseMetadata dataclass and registry."""

    def test_phase_metadata_frozen(self) -> None:
        """PhaseMetadata should be immutable."""
        metadata = PHASE_METADATA[Phase.PLAN]
        with pytest.raises(AttributeError):
            metadata.name = "NEW_NAME"  # type: ignore[misc]

    def test_phase_metadata_complete(self) -> None:
        """All phases should have metadata."""
        for phase in Phase:
            assert phase in PHASE_METADATA

    def test_phase_metadata_structure(self) -> None:
        """Metadata should have all required fields."""
        for phase, metadata in PHASE_METADATA.items():
            assert metadata.number == phase.value
            assert isinstance(metadata.name, str)
            assert isinstance(metadata.short_description, str)
            assert isinstance(metadata.can_loop, bool)
            assert metadata.model_type in ("default", "plan", "review")
            assert isinstance(metadata.completion_check, str)

    def test_phase_metadata_numbers_match(self) -> None:
        """Metadata numbers should match phase enum values."""
        assert PHASE_METADATA[Phase.PLAN].number == 1
        assert PHASE_METADATA[Phase.IMPLEMENT].number == 2
        assert PHASE_METADATA[Phase.REVIEW].number == 3
        assert PHASE_METADATA[Phase.TEST].number == 4
        assert PHASE_METADATA[Phase.FINAL_REVIEW].number == 5
        assert PHASE_METADATA[Phase.COMMIT].number == 6


class TestPhaseTransitions:
    """Test phase transition logic."""

    def test_plan_to_implement(self) -> None:
        """PLAN should always advance to IMPLEMENT."""
        assert determine_next_phase(Phase.PLAN) == Phase.IMPLEMENT

    def test_implement_to_review(self) -> None:
        """IMPLEMENT should always advance to REVIEW."""
        assert determine_next_phase(Phase.IMPLEMENT) == Phase.REVIEW

    def test_review_to_test(self) -> None:
        """REVIEW should advance to TEST (looping handled by workflow)."""
        assert determine_next_phase(Phase.REVIEW) == Phase.TEST

    def test_test_to_final_review(self) -> None:
        """TEST should advance to FINAL_REVIEW (looping handled by workflow)."""
        assert determine_next_phase(Phase.TEST) == Phase.FINAL_REVIEW

    def test_final_review_to_commit(self) -> None:
        """FINAL_REVIEW should advance to COMMIT (or back to TEST if fixes)."""
        assert determine_next_phase(Phase.FINAL_REVIEW) == Phase.COMMIT

    def test_commit_to_done(self) -> None:
        """COMMIT should mark workflow as complete."""
        assert determine_next_phase(Phase.COMMIT) == "done"

    def test_invalid_phase(self) -> None:
        """Invalid phase number should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown phase"):
            determine_next_phase(999)  # type: ignore[arg-type]


class TestGetPhaseName:
    """Test get_phase_name helper function."""

    def test_get_all_phase_names(self) -> None:
        """Should return correct name for each phase."""
        assert get_phase_name(Phase.PLAN) == "PLAN"
        assert get_phase_name(Phase.IMPLEMENT) == "IMPLEMENT"
        assert get_phase_name(Phase.REVIEW) == "REVIEW"
        assert get_phase_name(Phase.TEST) == "TEST"
        assert get_phase_name(Phase.FINAL_REVIEW) == "FINAL-REVIEW"
        assert get_phase_name(Phase.COMMIT) == "COMMIT"

    def test_phase_name_matches_name_str(self) -> None:
        """get_phase_name should match Phase.name_str property."""
        for phase in Phase:
            assert get_phase_name(phase) == phase.name_str


class TestPhaseWorkflowIntegration:
    """Test phase workflow patterns and integration."""

    def test_complete_workflow_path(self) -> None:
        """Test walking through complete workflow path."""
        current: Phase | str = Phase.PLAN

        # PLAN → IMPLEMENT
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.IMPLEMENT

        # IMPLEMENT → REVIEW
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.REVIEW

        # REVIEW → TEST (assuming no fixes needed)
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.TEST

        # TEST → FINAL_REVIEW (assuming tests pass)
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.FINAL_REVIEW

        # FINAL_REVIEW → COMMIT (assuming no fixes needed)
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.COMMIT

        # COMMIT → done
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == "done"

    def test_looping_phases_identified(self) -> None:
        """Phases that can loop should be identifiable for workflow logic."""
        looping_phases = [p for p in Phase if p.can_loop]
        assert looping_phases == [Phase.REVIEW, Phase.TEST, Phase.FINAL_REVIEW]

    def test_model_selection_by_phase(self) -> None:
        """Different phases should use appropriate models."""
        # Plan phase uses specialized plan model
        assert Phase.PLAN.model_type == "plan"

        # Review phases use specialized review model
        assert Phase.REVIEW.model_type == "review"
        assert Phase.FINAL_REVIEW.model_type == "review"

        # Other phases use default model
        assert Phase.IMPLEMENT.model_type == "default"
        assert Phase.TEST.model_type == "default"
        assert Phase.COMMIT.model_type == "default"
