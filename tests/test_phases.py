"""Tests for phase definitions and metadata."""

import pytest

from nelson.phases import (
    PHASE_METADATA,
    Phase,
    determine_next_phase,
    get_phase_name,
    get_starting_phase,
)


class TestPhaseEnum:
    """Test Phase enum values and properties."""

    def test_phase_values(self) -> None:
        """Phases should have correct integer values."""
        # Comprehensive mode only
        assert Phase.DISCOVER.value == 0
        # Standard phases (1-5)
        assert Phase.PLAN.value == 1
        assert Phase.IMPLEMENT.value == 2
        assert Phase.TEST.value == 3
        assert Phase.REVIEW.value == 4
        assert Phase.COMMIT.value == 5
        # Comprehensive mode only
        assert Phase.ROADMAP.value == 6

    def test_phase_name_str(self) -> None:
        """Each phase should return its human-readable name."""
        assert Phase.DISCOVER.name_str == "DISCOVER"
        assert Phase.PLAN.name_str == "PLAN"
        assert Phase.IMPLEMENT.name_str == "IMPLEMENT"
        assert Phase.TEST.name_str == "TEST"
        assert Phase.REVIEW.name_str == "REVIEW"
        assert Phase.COMMIT.name_str == "COMMIT"
        assert Phase.ROADMAP.name_str == "ROADMAP"

    def test_phase_can_loop(self) -> None:
        """Phases that can loop should be correctly identified."""
        # Cannot loop (always advance)
        assert not Phase.DISCOVER.can_loop
        assert not Phase.PLAN.can_loop
        assert not Phase.IMPLEMENT.can_loop
        assert not Phase.COMMIT.can_loop
        assert not Phase.ROADMAP.can_loop

        # Can loop (may stay in phase or go back)
        assert Phase.TEST.can_loop
        assert Phase.REVIEW.can_loop

    def test_phase_model_type(self) -> None:
        """Phases should use correct model types."""
        assert Phase.DISCOVER.model_type == "plan"
        assert Phase.PLAN.model_type == "plan"
        assert Phase.IMPLEMENT.model_type == "default"
        assert Phase.TEST.model_type == "default"
        assert Phase.REVIEW.model_type == "review"
        assert Phase.COMMIT.model_type == "default"
        assert Phase.ROADMAP.model_type == "plan"


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
        assert PHASE_METADATA[Phase.DISCOVER].number == 0
        assert PHASE_METADATA[Phase.PLAN].number == 1
        assert PHASE_METADATA[Phase.IMPLEMENT].number == 2
        assert PHASE_METADATA[Phase.TEST].number == 3
        assert PHASE_METADATA[Phase.REVIEW].number == 4
        assert PHASE_METADATA[Phase.COMMIT].number == 5
        assert PHASE_METADATA[Phase.ROADMAP].number == 6


class TestPhaseTransitions:
    """Test phase transition logic."""

    def test_discover_to_plan(self) -> None:
        """DISCOVER should always advance to PLAN."""
        assert determine_next_phase(Phase.DISCOVER) == Phase.PLAN

    def test_plan_to_implement(self) -> None:
        """PLAN should always advance to IMPLEMENT."""
        assert determine_next_phase(Phase.PLAN) == Phase.IMPLEMENT

    def test_implement_to_test(self) -> None:
        """IMPLEMENT should always advance to TEST."""
        assert determine_next_phase(Phase.IMPLEMENT) == Phase.TEST

    def test_test_to_review(self) -> None:
        """TEST should advance to REVIEW (looping handled by workflow)."""
        assert determine_next_phase(Phase.TEST) == Phase.REVIEW

    def test_review_to_commit(self) -> None:
        """REVIEW should advance to COMMIT (or back to IMPLEMENT if issues)."""
        assert determine_next_phase(Phase.REVIEW) == Phase.COMMIT

    def test_commit_to_done_standard(self) -> None:
        """COMMIT should mark workflow as complete in standard mode."""
        assert determine_next_phase(Phase.COMMIT) == "done"
        assert determine_next_phase(Phase.COMMIT, comprehensive=False) == "done"

    def test_commit_to_roadmap_comprehensive(self) -> None:
        """COMMIT should advance to ROADMAP in comprehensive mode."""
        assert determine_next_phase(Phase.COMMIT, comprehensive=True) == Phase.ROADMAP

    def test_roadmap_to_done(self) -> None:
        """ROADMAP should always mark workflow as complete."""
        assert determine_next_phase(Phase.ROADMAP) == "done"
        assert determine_next_phase(Phase.ROADMAP, comprehensive=True) == "done"

    def test_invalid_phase(self) -> None:
        """Invalid phase number should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown phase"):
            determine_next_phase(999)  # type: ignore[arg-type]


class TestGetStartingPhase:
    """Test get_starting_phase helper function."""

    def test_standard_mode_starts_at_plan(self) -> None:
        """Standard mode should start at PLAN phase."""
        assert get_starting_phase() == Phase.PLAN
        assert get_starting_phase(comprehensive=False) == Phase.PLAN

    def test_comprehensive_mode_starts_at_discover(self) -> None:
        """Comprehensive mode should start at DISCOVER phase."""
        assert get_starting_phase(comprehensive=True) == Phase.DISCOVER


class TestGetPhaseName:
    """Test get_phase_name helper function."""

    def test_get_all_phase_names(self) -> None:
        """Should return correct name for each phase."""
        assert get_phase_name(Phase.DISCOVER) == "DISCOVER"
        assert get_phase_name(Phase.PLAN) == "PLAN"
        assert get_phase_name(Phase.IMPLEMENT) == "IMPLEMENT"
        assert get_phase_name(Phase.TEST) == "TEST"
        assert get_phase_name(Phase.REVIEW) == "REVIEW"
        assert get_phase_name(Phase.COMMIT) == "COMMIT"
        assert get_phase_name(Phase.ROADMAP) == "ROADMAP"

    def test_phase_name_matches_name_str(self) -> None:
        """get_phase_name should match Phase.name_str property."""
        for phase in Phase:
            assert get_phase_name(phase) == phase.name_str


class TestPhaseWorkflowIntegration:
    """Test phase workflow patterns and integration."""

    def test_complete_standard_workflow_path(self) -> None:
        """Test walking through complete standard (5-phase) workflow path."""
        current: Phase | str = Phase.PLAN

        # PLAN → IMPLEMENT
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.IMPLEMENT

        # IMPLEMENT → TEST
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.TEST

        # TEST → REVIEW (assuming tests pass)
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.REVIEW

        # REVIEW → COMMIT (assuming no issues found)
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == Phase.COMMIT

        # COMMIT → done
        current = determine_next_phase(current)  # type: ignore[arg-type]
        assert current == "done"

    def test_complete_comprehensive_workflow_path(self) -> None:
        """Test walking through complete comprehensive (7-phase) workflow path."""
        current: Phase | str = Phase.DISCOVER

        # DISCOVER → PLAN
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.PLAN

        # PLAN → IMPLEMENT
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.IMPLEMENT

        # IMPLEMENT → TEST
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.TEST

        # TEST → REVIEW
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.REVIEW

        # REVIEW → COMMIT
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.COMMIT

        # COMMIT → ROADMAP (comprehensive mode)
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == Phase.ROADMAP

        # ROADMAP → done
        current = determine_next_phase(current, comprehensive=True)  # type: ignore[arg-type]
        assert current == "done"

    def test_looping_phases_identified(self) -> None:
        """Phases that can loop should be identifiable for workflow logic."""
        looping_phases = [p for p in Phase if p.can_loop]
        assert looping_phases == [Phase.TEST, Phase.REVIEW]

    def test_model_selection_by_phase(self) -> None:
        """Different phases should use appropriate models."""
        # Discovery and Plan phases use specialized plan model
        assert Phase.DISCOVER.model_type == "plan"
        assert Phase.PLAN.model_type == "plan"

        # Review phase uses specialized review model
        assert Phase.REVIEW.model_type == "review"

        # Other phases use default model
        assert Phase.IMPLEMENT.model_type == "default"
        assert Phase.TEST.model_type == "default"
        assert Phase.COMMIT.model_type == "default"

        # Roadmap uses plan model for documentation
        assert Phase.ROADMAP.model_type == "plan"

    def test_standard_vs_comprehensive_mode_count(self) -> None:
        """Standard mode has 5 phases, comprehensive has 7."""
        standard_phases = [Phase.PLAN, Phase.IMPLEMENT, Phase.TEST, Phase.REVIEW, Phase.COMMIT]
        comprehensive_phases = [Phase.DISCOVER] + standard_phases + [Phase.ROADMAP]

        assert len(standard_phases) == 5
        assert len(comprehensive_phases) == 7
