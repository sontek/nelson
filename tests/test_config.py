"""Tests for configuration management."""

import os
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from nelson.config import NelsonConfig


class TestNelsonConfig:
    """Tests for NelsonConfig class."""

    def test_default_configuration(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading configuration with all defaults."""
        # Clear all RALPH_ environment variables
        for key in list(os.environ.keys()):
            if key.startswith("RALPH_"):
                monkeypatch.delenv(key, raising=False)

        config = NelsonConfig.from_environment()

        assert config.max_iterations == 50
        assert config.max_iterations_explicit is False
        assert config.cost_limit == 10.0
        assert config.ralph_dir == Path(".ralph")
        assert config.audit_dir == Path(".ralph/audit")
        assert config.runs_dir == Path(".ralph/runs")
        assert config.claude_command == "claude-jail"
        assert config.model == "sonnet"
        assert config.plan_model == "sonnet"
        assert config.review_model == "sonnet"
        assert config.auto_approve_push is False

    def test_explicit_max_iterations(self, monkeypatch: MonkeyPatch) -> None:
        """Test that max_iterations_explicit is set when user provides value."""
        monkeypatch.setenv("RALPH_MAX_ITERATIONS", "100")

        config = NelsonConfig.from_environment()

        assert config.max_iterations == 100
        assert config.max_iterations_explicit is True

    def test_environment_override(self, monkeypatch: MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("RALPH_MAX_ITERATIONS", "30")
        monkeypatch.setenv("RALPH_COST_LIMIT", "25.50")
        monkeypatch.setenv("RALPH_DIR", ".custom-ralph")
        monkeypatch.setenv("RALPH_AUDIT_DIR", ".custom-audit")
        monkeypatch.setenv("RALPH_RUNS_DIR", ".custom-runs")
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")
        monkeypatch.setenv("RALPH_MODEL", "opus")
        monkeypatch.setenv("RALPH_AUTO_APPROVE_PUSH", "true")

        config = NelsonConfig.from_environment()

        assert config.max_iterations == 30
        assert config.cost_limit == 25.50
        assert config.ralph_dir == Path(".custom-ralph")
        assert config.audit_dir == Path(".custom-audit")
        assert config.runs_dir == Path(".custom-runs")
        assert config.claude_command == "claude"
        assert config.model == "opus"
        assert config.plan_model == "opus"  # Inherits from RALPH_MODEL
        assert config.review_model == "opus"  # Inherits from RALPH_MODEL
        assert config.auto_approve_push is True

    def test_model_cascading(self, monkeypatch: MonkeyPatch) -> None:
        """Test that plan_model and review_model cascade from model if not set."""
        monkeypatch.setenv("RALPH_MODEL", "haiku")

        config = NelsonConfig.from_environment()

        assert config.model == "haiku"
        assert config.plan_model == "haiku"
        assert config.review_model == "haiku"

    def test_model_override(self, monkeypatch: MonkeyPatch) -> None:
        """Test that plan_model and review_model can be overridden independently."""
        monkeypatch.setenv("RALPH_MODEL", "sonnet")
        monkeypatch.setenv("RALPH_PLAN_MODEL", "opus")
        monkeypatch.setenv("RALPH_REVIEW_MODEL", "sonnet")

        config = NelsonConfig.from_environment()

        assert config.model == "sonnet"
        assert config.plan_model == "opus"
        assert config.review_model == "sonnet"

    def test_auto_approve_push_variants(self, monkeypatch: MonkeyPatch) -> None:
        """Test various true/false values for auto_approve_push."""
        # Test true variants
        for value in ["true", "TRUE", "True", "1", "yes", "YES"]:
            monkeypatch.setenv("RALPH_AUTO_APPROVE_PUSH", value)
            config = NelsonConfig.from_environment()
            assert config.auto_approve_push is True, f"Failed for value: {value}"

        # Test false variants
        for value in ["false", "FALSE", "False", "0", "no", "NO", ""]:
            monkeypatch.setenv("RALPH_AUTO_APPROVE_PUSH", value)
            config = NelsonConfig.from_environment()
            assert config.auto_approve_push is False, f"Failed for value: {value}"

    def test_claude_jail_path_resolution(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test claude-jail path resolution with script_dir."""
        # Clear environment
        for key in list(os.environ.keys()):
            if key.startswith("RALPH_"):
                monkeypatch.delenv(key, raising=False)

        script_dir = tmp_path / "bin"
        script_dir.mkdir()

        config = NelsonConfig.from_environment(script_dir=script_dir)

        assert config.claude_command == "claude-jail"
        assert config.claude_command_path == script_dir / "claude-jail"

    def test_claude_native_path_resolution(self, monkeypatch: MonkeyPatch) -> None:
        """Test that native claude command has no explicit path."""
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()

        assert config.claude_command == "claude"
        assert config.claude_command_path is None

    def test_custom_claude_path_resolution(self, monkeypatch: MonkeyPatch) -> None:
        """Test custom claude command path resolution."""
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "/custom/path/to/claude")

        config = NelsonConfig.from_environment()

        assert config.claude_command == "/custom/path/to/claude"
        assert config.claude_command_path == Path("/custom/path/to/claude")

    def test_validate_success(self, monkeypatch: MonkeyPatch) -> None:
        """Test that validate passes with valid configuration."""
        # Clear environment
        for key in list(os.environ.keys()):
            if key.startswith("RALPH_"):
                monkeypatch.delenv(key, raising=False)

        # Use native claude to avoid path validation
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()
        config.validate()  # Should not raise

    def test_validate_negative_max_iterations(self, monkeypatch: MonkeyPatch) -> None:
        """Test validation fails with negative max_iterations."""
        monkeypatch.setenv("RALPH_MAX_ITERATIONS", "-5")
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()

        with pytest.raises(ValueError, match="max_iterations must be > 0"):
            config.validate()

    def test_validate_zero_cost_limit(self, monkeypatch: MonkeyPatch) -> None:
        """Test validation fails with zero cost_limit."""
        monkeypatch.setenv("RALPH_COST_LIMIT", "0")
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()

        with pytest.raises(ValueError, match="cost_limit must be > 0"):
            config.validate()

    def test_validate_nonexistent_claude_path(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test validation fails with non-existent claude path."""
        nonexistent_path = tmp_path / "nonexistent" / "claude"
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", str(nonexistent_path))

        config = NelsonConfig.from_environment()

        with pytest.raises(ValueError, match="Claude command path does not exist"):
            config.validate()

    def test_ensure_directories(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that ensure_directories creates necessary directories."""
        # Set custom paths in temporary directory
        ralph_dir = tmp_path / ".ralph"
        audit_dir = tmp_path / ".ralph" / "audit"
        runs_dir = tmp_path / ".ralph" / "runs"

        monkeypatch.setenv("RALPH_DIR", str(ralph_dir))
        monkeypatch.setenv("RALPH_AUDIT_DIR", str(audit_dir))
        monkeypatch.setenv("RALPH_RUNS_DIR", str(runs_dir))
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()

        # Directories should not exist yet
        assert not ralph_dir.exists()
        assert not audit_dir.exists()
        assert not runs_dir.exists()

        # Create directories
        config.ensure_directories()

        # Now they should exist
        assert ralph_dir.exists()
        assert ralph_dir.is_dir()
        assert audit_dir.exists()
        assert audit_dir.is_dir()
        assert runs_dir.exists()
        assert runs_dir.is_dir()

    def test_ensure_directories_idempotent(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Test that ensure_directories can be called multiple times safely."""
        ralph_dir = tmp_path / ".ralph"
        monkeypatch.setenv("RALPH_DIR", str(ralph_dir))
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config = NelsonConfig.from_environment()

        # Create directories twice
        config.ensure_directories()
        config.ensure_directories()

        # Should still be fine
        assert ralph_dir.exists()
        assert ralph_dir.is_dir()

    def test_config_immutability(self, monkeypatch: MonkeyPatch) -> None:
        """Test that config is immutable (frozen dataclass)."""
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")
        config = NelsonConfig.from_environment()

        # Should not be able to modify attributes
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            config.max_iterations = 100  # type: ignore

    def test_config_equality(self, monkeypatch: MonkeyPatch) -> None:
        """Test that configs with same values are equal."""
        monkeypatch.setenv("RALPH_MODEL", "opus")
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")

        config1 = NelsonConfig.from_environment()
        config2 = NelsonConfig.from_environment()

        assert config1 == config2

    def test_config_repr(self, monkeypatch: MonkeyPatch) -> None:
        """Test that config has a useful repr."""
        monkeypatch.setenv("RALPH_CLAUDE_COMMAND", "claude")
        config = NelsonConfig.from_environment()

        repr_str = repr(config)
        assert "NelsonConfig" in repr_str
        assert "max_iterations" in repr_str
