"""Tests for depth mode configuration."""


import pytest
from pytest import MonkeyPatch

from nelson.depth import (
    DepthConfig,
    DepthMode,
    get_phases_for_depth,
    should_skip_phase,
)


class TestDepthMode:
    """Tests for DepthMode enum."""

    def test_mode_values(self) -> None:
        """Test depth mode enum values."""
        assert DepthMode.QUICK.value == "quick"
        assert DepthMode.STANDARD.value == "standard"
        assert DepthMode.COMPREHENSIVE.value == "comprehensive"

    def test_mode_from_string(self) -> None:
        """Test creating mode from string."""
        assert DepthMode("quick") == DepthMode.QUICK
        assert DepthMode("standard") == DepthMode.STANDARD
        assert DepthMode("comprehensive") == DepthMode.COMPREHENSIVE

    def test_invalid_mode_raises(self) -> None:
        """Test that invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            DepthMode("invalid")


class TestDepthConfig:
    """Tests for DepthConfig dataclass."""

    def test_quick_mode_defaults(self) -> None:
        """Test QUICK mode default configuration."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert config.mode == DepthMode.QUICK
        assert config.skip_final_review is True
        assert config.skip_roadmap is True
        assert config.include_research is False
        assert config.max_planning_questions == 0
        assert config.lean_prompts is True

    def test_standard_mode_defaults(self) -> None:
        """Test STANDARD mode default configuration."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        assert config.mode == DepthMode.STANDARD
        assert config.skip_final_review is False
        assert config.skip_roadmap is True
        assert config.include_research is False
        assert config.max_planning_questions == 3
        assert config.lean_prompts is False

    def test_comprehensive_mode_defaults(self) -> None:
        """Test COMPREHENSIVE mode default configuration."""
        config = DepthConfig.for_mode(DepthMode.COMPREHENSIVE)

        assert config.mode == DepthMode.COMPREHENSIVE
        assert config.skip_final_review is False
        assert config.skip_roadmap is False
        assert config.include_research is True
        assert config.max_planning_questions == 5
        assert config.lean_prompts is False

    def test_from_env_quick(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading QUICK mode from environment."""
        monkeypatch.setenv("NELSON_DEPTH", "quick")

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.QUICK
        assert config.skip_final_review is True

    def test_from_env_standard(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading STANDARD mode from environment."""
        monkeypatch.setenv("NELSON_DEPTH", "standard")

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.STANDARD

    def test_from_env_comprehensive(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading COMPREHENSIVE mode from environment."""
        monkeypatch.setenv("NELSON_DEPTH", "comprehensive")

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.COMPREHENSIVE

    def test_from_env_case_insensitive(self, monkeypatch: MonkeyPatch) -> None:
        """Test environment variable parsing is case insensitive."""
        monkeypatch.setenv("NELSON_DEPTH", "QUICK")

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.QUICK

    def test_from_env_invalid_defaults_to_standard(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Test invalid mode defaults to STANDARD."""
        monkeypatch.setenv("NELSON_DEPTH", "invalid_mode")

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.STANDARD

    def test_from_env_default_is_standard(self, monkeypatch: MonkeyPatch) -> None:
        """Test default mode is STANDARD when not set."""
        monkeypatch.delenv("NELSON_DEPTH", raising=False)

        config = DepthConfig.from_env()

        assert config.mode == DepthMode.STANDARD

    def test_to_dict(self) -> None:
        """Test DepthConfig serialization."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        data = config.to_dict()

        assert data["mode"] == "quick"
        assert data["skip_final_review"] is True
        assert data["skip_roadmap"] is True
        assert data["include_research"] is False
        assert data["max_planning_questions"] == 0
        assert data["lean_prompts"] is True

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        with pytest.raises(Exception):  # FrozenInstanceError
            config.mode = DepthMode.QUICK  # type: ignore


class TestGetPhasesForDepth:
    """Tests for get_phases_for_depth function."""

    def test_quick_mode_phases(self) -> None:
        """Test QUICK mode has 4 phases."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        phases = get_phases_for_depth(config)

        assert phases == ["PLAN", "IMPLEMENT", "TEST", "COMMIT"]
        assert len(phases) == 4
        assert "REVIEW" not in phases
        assert "FINAL_REVIEW" not in phases

    def test_standard_mode_phases(self) -> None:
        """Test STANDARD mode has 6 phases."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        phases = get_phases_for_depth(config)

        assert phases == [
            "PLAN",
            "IMPLEMENT",
            "REVIEW",
            "TEST",
            "FINAL_REVIEW",
            "COMMIT",
        ]
        assert len(phases) == 6

    def test_comprehensive_mode_phases(self) -> None:
        """Test COMPREHENSIVE mode has 8 phases."""
        config = DepthConfig.for_mode(DepthMode.COMPREHENSIVE)

        phases = get_phases_for_depth(config)

        assert phases == [
            "DISCOVER",
            "ROADMAP",
            "PLAN",
            "IMPLEMENT",
            "REVIEW",
            "TEST",
            "FINAL_REVIEW",
            "COMMIT",
        ]
        assert len(phases) == 8


class TestShouldSkipPhase:
    """Tests for should_skip_phase function."""

    def test_quick_mode_skips_review(self) -> None:
        """Test QUICK mode skips REVIEW."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("REVIEW", config) is True

    def test_quick_mode_skips_final_review(self) -> None:
        """Test QUICK mode skips FINAL_REVIEW."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("FINAL_REVIEW", config) is True

    def test_quick_mode_runs_plan(self) -> None:
        """Test QUICK mode runs PLAN."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("PLAN", config) is False

    def test_quick_mode_runs_implement(self) -> None:
        """Test QUICK mode runs IMPLEMENT."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("IMPLEMENT", config) is False

    def test_quick_mode_runs_test(self) -> None:
        """Test QUICK mode runs TEST."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("TEST", config) is False

    def test_quick_mode_runs_commit(self) -> None:
        """Test QUICK mode runs COMMIT."""
        config = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("COMMIT", config) is False

    def test_standard_mode_runs_all(self) -> None:
        """Test STANDARD mode runs all standard phases."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        for phase in ["PLAN", "IMPLEMENT", "REVIEW", "TEST", "FINAL_REVIEW", "COMMIT"]:
            assert should_skip_phase(phase, config) is False, f"{phase} should run"

    def test_standard_mode_skips_discover(self) -> None:
        """Test STANDARD mode skips DISCOVER."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        assert should_skip_phase("DISCOVER", config) is True

    def test_standard_mode_skips_roadmap(self) -> None:
        """Test STANDARD mode skips ROADMAP."""
        config = DepthConfig.for_mode(DepthMode.STANDARD)

        assert should_skip_phase("ROADMAP", config) is True

    def test_comprehensive_mode_runs_all(self) -> None:
        """Test COMPREHENSIVE mode runs all phases."""
        config = DepthConfig.for_mode(DepthMode.COMPREHENSIVE)

        for phase in [
            "DISCOVER",
            "ROADMAP",
            "PLAN",
            "IMPLEMENT",
            "REVIEW",
            "TEST",
            "FINAL_REVIEW",
            "COMMIT",
        ]:
            assert should_skip_phase(phase, config) is False, f"{phase} should run"
