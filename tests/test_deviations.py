"""Tests for deviation handling module."""

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from nelson.deviations import (
    Deviation,
    DeviationConfig,
    DeviationRule,
    extract_deviations_from_response,
    format_deviation_summary,
    get_enabled_rules_description,
    log_deviations,
    validate_deviations,
)


class TestDeviationRule:
    """Tests for DeviationRule enum."""

    def test_rule_values(self) -> None:
        """Test deviation rule enum values."""
        assert DeviationRule.AUTO_FIX_BUGS.value == "auto_fix_bugs"
        assert DeviationRule.AUTO_ADD_CRITICAL.value == "auto_add_critical"
        assert DeviationRule.AUTO_INSTALL_DEPS.value == "auto_install_deps"
        assert DeviationRule.AUTO_HANDLE_AUTH.value == "auto_handle_auth"

    def test_rule_from_string(self) -> None:
        """Test creating rule from string."""
        assert DeviationRule("auto_fix_bugs") == DeviationRule.AUTO_FIX_BUGS
        assert DeviationRule("auto_add_critical") == DeviationRule.AUTO_ADD_CRITICAL


class TestDeviation:
    """Tests for Deviation dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic Deviation creation."""
        deviation = Deviation(
            rule=DeviationRule.AUTO_FIX_BUGS,
            issue="Type error in function",
            fix_applied="Added type annotation",
        )

        assert deviation.rule == DeviationRule.AUTO_FIX_BUGS
        assert deviation.issue == "Type error in function"
        assert deviation.fix_applied == "Added type annotation"
        assert deviation.files_affected == []
        assert deviation.task_id is None
        assert deviation.commit_sha is None

    def test_full_creation(self) -> None:
        """Test Deviation with all fields."""
        deviation = Deviation(
            rule=DeviationRule.AUTO_INSTALL_DEPS,
            issue="Missing package",
            fix_applied="pip install requests",
            files_affected=["main.py", "utils.py"],
            task_id="01",
            commit_sha="abc123",
        )

        assert deviation.rule == DeviationRule.AUTO_INSTALL_DEPS
        assert deviation.files_affected == ["main.py", "utils.py"]
        assert deviation.task_id == "01"
        assert deviation.commit_sha == "abc123"

    def test_to_dict(self) -> None:
        """Test Deviation serialization."""
        deviation = Deviation(
            rule=DeviationRule.AUTO_FIX_BUGS,
            issue="Test issue",
            fix_applied="Test fix",
            files_affected=["file.py"],
            task_id="02",
        )

        data = deviation.to_dict()

        assert data["rule"] == "auto_fix_bugs"
        assert data["issue"] == "Test issue"
        assert data["fix_applied"] == "Test fix"
        assert data["files_affected"] == ["file.py"]
        assert data["task_id"] == "02"
        assert "timestamp" in data

    def test_from_dict(self) -> None:
        """Test Deviation deserialization."""
        data = {
            "rule": "auto_add_critical",
            "issue": "Missing validation",
            "fix_applied": "Added null check",
            "files_affected": ["handler.py"],
            "task_id": "03",
            "commit_sha": "def456",
            "timestamp": "2024-01-15T10:30:00",
        }

        deviation = Deviation.from_dict(data)

        assert deviation.rule == DeviationRule.AUTO_ADD_CRITICAL
        assert deviation.issue == "Missing validation"
        assert deviation.task_id == "03"
        assert deviation.commit_sha == "def456"


class TestDeviationConfig:
    """Tests for DeviationConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default DeviationConfig values."""
        config = DeviationConfig()

        assert config.auto_fix_bugs is True
        assert config.auto_add_critical is True
        assert config.auto_install_deps is True
        assert config.auto_handle_auth is False  # Default off
        assert config.max_deviations_per_task == 5

    def test_custom_config(self) -> None:
        """Test custom DeviationConfig values."""
        config = DeviationConfig(
            auto_fix_bugs=False,
            auto_install_deps=False,
            auto_handle_auth=True,
            max_deviations_per_task=10,
        )

        assert config.auto_fix_bugs is False
        assert config.auto_install_deps is False
        assert config.auto_handle_auth is True
        assert config.max_deviations_per_task == 10

    def test_is_rule_enabled(self) -> None:
        """Test rule enablement checking."""
        config = DeviationConfig(
            auto_fix_bugs=True,
            auto_add_critical=False,
            auto_install_deps=True,
            auto_handle_auth=False,
        )

        assert config.is_rule_enabled(DeviationRule.AUTO_FIX_BUGS) is True
        assert config.is_rule_enabled(DeviationRule.AUTO_ADD_CRITICAL) is False
        assert config.is_rule_enabled(DeviationRule.AUTO_INSTALL_DEPS) is True
        assert config.is_rule_enabled(DeviationRule.AUTO_HANDLE_AUTH) is False

    def test_to_dict(self) -> None:
        """Test DeviationConfig serialization."""
        config = DeviationConfig(auto_fix_bugs=True, max_deviations_per_task=3)

        data = config.to_dict()

        assert data["auto_fix_bugs"] is True
        assert data["max_deviations_per_task"] == 3

    def test_from_env_defaults(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading config from environment with defaults."""
        # Clear relevant env vars
        for key in ["NELSON_AUTO_FIX_BUGS", "NELSON_AUTO_HANDLE_AUTH"]:
            monkeypatch.delenv(key, raising=False)

        config = DeviationConfig.from_env()

        assert config.auto_fix_bugs is True  # Default
        assert config.auto_handle_auth is False  # Default

    def test_from_env_override(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading config from environment with overrides."""
        monkeypatch.setenv("NELSON_AUTO_FIX_BUGS", "false")
        monkeypatch.setenv("NELSON_AUTO_HANDLE_AUTH", "true")
        monkeypatch.setenv("NELSON_MAX_DEVIATIONS_PER_TASK", "10")

        config = DeviationConfig.from_env()

        assert config.auto_fix_bugs is False
        assert config.auto_handle_auth is True
        assert config.max_deviations_per_task == 10

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable."""
        config = DeviationConfig()

        with pytest.raises(Exception):  # FrozenInstanceError
            config.auto_fix_bugs = False  # type: ignore


class TestExtractDeviationsFromResponse:
    """Tests for extract_deviations_from_response function."""

    def test_extract_single_deviation(self) -> None:
        """Test extracting a single deviation."""
        response = """
Some text before.

```deviations
[
  {
    "rule": "auto_fix_bugs",
    "issue": "Type error in main.py",
    "fix_applied": "Added type annotation",
    "files_affected": ["main.py"]
  }
]
```

Some text after.
"""
        deviations = extract_deviations_from_response(response, task_id="01")

        assert len(deviations) == 1
        assert deviations[0].rule == DeviationRule.AUTO_FIX_BUGS
        assert deviations[0].issue == "Type error in main.py"
        assert deviations[0].task_id == "01"

    def test_extract_multiple_deviations(self) -> None:
        """Test extracting multiple deviations."""
        response = """
```deviations
[
  {
    "rule": "auto_fix_bugs",
    "issue": "Fix 1",
    "fix_applied": "Applied 1",
    "files_affected": ["a.py"]
  },
  {
    "rule": "auto_add_critical",
    "issue": "Fix 2",
    "fix_applied": "Applied 2",
    "files_affected": ["b.py"]
  }
]
```
"""
        deviations = extract_deviations_from_response(response)

        assert len(deviations) == 2
        assert deviations[0].rule == DeviationRule.AUTO_FIX_BUGS
        assert deviations[1].rule == DeviationRule.AUTO_ADD_CRITICAL

    def test_extract_no_deviations_block(self) -> None:
        """Test extraction when no deviations block present."""
        response = "Just regular text without deviations."

        deviations = extract_deviations_from_response(response)

        assert deviations == []

    def test_extract_empty_block(self) -> None:
        """Test extraction with empty deviations block."""
        response = """
```deviations
[]
```
"""
        deviations = extract_deviations_from_response(response)

        assert deviations == []

    def test_extract_invalid_json(self) -> None:
        """Test extraction with invalid JSON."""
        response = """
```deviations
not valid json
```
"""
        deviations = extract_deviations_from_response(response)

        assert deviations == []

    def test_extract_single_object(self) -> None:
        """Test extraction with single object (not array)."""
        response = """
```deviations
{
  "rule": "auto_install_deps",
  "issue": "Missing package",
  "fix_applied": "pip install foo"
}
```
"""
        deviations = extract_deviations_from_response(response)

        assert len(deviations) == 1
        assert deviations[0].rule == DeviationRule.AUTO_INSTALL_DEPS


class TestValidateDeviations:
    """Tests for validate_deviations function."""

    def test_all_allowed(self) -> None:
        """Test when all deviations are allowed."""
        config = DeviationConfig()
        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Bug",
                fix_applied="Fixed",
            ),
            Deviation(
                rule=DeviationRule.AUTO_ADD_CRITICAL,
                issue="Missing",
                fix_applied="Added",
            ),
        ]

        allowed, blocked = validate_deviations(deviations, config)

        assert len(allowed) == 2
        assert len(blocked) == 0

    def test_disabled_rule_blocked(self) -> None:
        """Test that disabled rules are blocked."""
        config = DeviationConfig(auto_fix_bugs=False)
        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Bug",
                fix_applied="Fixed",
            ),
        ]

        allowed, blocked = validate_deviations(deviations, config)

        assert len(allowed) == 0
        assert len(blocked) == 1

    def test_max_deviations_exceeded(self) -> None:
        """Test that max deviations limit is enforced."""
        config = DeviationConfig(max_deviations_per_task=2)
        deviations = [
            Deviation(rule=DeviationRule.AUTO_FIX_BUGS, issue="1", fix_applied="1"),
            Deviation(rule=DeviationRule.AUTO_FIX_BUGS, issue="2", fix_applied="2"),
            Deviation(rule=DeviationRule.AUTO_FIX_BUGS, issue="3", fix_applied="3"),
        ]

        allowed, blocked = validate_deviations(deviations, config)

        assert len(allowed) == 2
        assert len(blocked) == 1

    def test_existing_task_deviations_counted(self) -> None:
        """Test that existing task deviations count toward limit."""
        config = DeviationConfig(max_deviations_per_task=3)
        deviations = [
            Deviation(rule=DeviationRule.AUTO_FIX_BUGS, issue="1", fix_applied="1"),
            Deviation(rule=DeviationRule.AUTO_FIX_BUGS, issue="2", fix_applied="2"),
        ]

        # Already 2 deviations for this task
        allowed, blocked = validate_deviations(deviations, config, task_deviation_count=2)

        assert len(allowed) == 1  # Only 1 more allowed
        assert len(blocked) == 1


class TestLogDeviations:
    """Tests for log_deviations function."""

    def test_log_deviations(self, tmp_path: Path) -> None:
        """Test logging deviations to file."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Decisions\n")

        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Type error",
                fix_applied="Added annotation",
                files_affected=["main.py"],
            ),
        ]

        log_deviations(deviations, decisions_file)

        content = decisions_file.read_text()
        assert "## Auto-Applied Deviations" in content
        assert "Auto Fix Bugs" in content
        assert "Type error" in content
        assert "main.py" in content

    def test_log_blocked_deviations(self, tmp_path: Path) -> None:
        """Test logging blocked deviations."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_HANDLE_AUTH,
                issue="401 response",
                fix_applied="Would add auth",
                files_affected=["api.py"],
            ),
        ]

        log_deviations(deviations, decisions_file, blocked=True)

        content = decisions_file.read_text()
        assert "## Blocked Deviations" in content

    def test_log_empty_deviations(self, tmp_path: Path) -> None:
        """Test that empty deviations don't modify file."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("Original content")

        log_deviations([], decisions_file)

        content = decisions_file.read_text()
        assert content == "Original content"


class TestFormatDeviationSummary:
    """Tests for format_deviation_summary function."""

    def test_format_empty(self) -> None:
        """Test formatting empty deviations."""
        summary = format_deviation_summary([])

        assert summary == "No deviations applied."

    def test_format_with_deviations(self) -> None:
        """Test formatting deviations."""
        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Bug 1",
                fix_applied="Fix 1",
                files_affected=["a.py", "b.py"],
            ),
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Bug 2",
                fix_applied="Fix 2",
                files_affected=["a.py"],
            ),
            Deviation(
                rule=DeviationRule.AUTO_ADD_CRITICAL,
                issue="Missing",
                fix_applied="Added",
                files_affected=["c.py"],
            ),
        ]

        summary = format_deviation_summary(deviations)

        assert "Total deviations: 3" in summary
        assert "Auto Fix Bugs: 2" in summary
        assert "Auto Add Critical: 1" in summary
        assert "Files affected: 3" in summary


class TestGetEnabledRulesDescription:
    """Tests for get_enabled_rules_description function."""

    def test_all_enabled(self) -> None:
        """Test description with all rules enabled."""
        config = DeviationConfig(
            auto_fix_bugs=True,
            auto_add_critical=True,
            auto_install_deps=True,
            auto_handle_auth=True,
        )

        desc = get_enabled_rules_description(config)

        assert "AUTO_FIX_BUGS" in desc
        assert "AUTO_ADD_CRITICAL" in desc
        assert "AUTO_INSTALL_DEPS" in desc
        assert "AUTO_HANDLE_AUTH" in desc

    def test_none_enabled(self) -> None:
        """Test description with no rules enabled."""
        config = DeviationConfig(
            auto_fix_bugs=False,
            auto_add_critical=False,
            auto_install_deps=False,
            auto_handle_auth=False,
        )

        desc = get_enabled_rules_description(config)

        assert "No deviation rules enabled" in desc

    def test_some_enabled(self) -> None:
        """Test description with some rules enabled."""
        config = DeviationConfig(
            auto_fix_bugs=True,
            auto_add_critical=False,
            auto_install_deps=True,
            auto_handle_auth=False,
        )

        desc = get_enabled_rules_description(config)

        assert "AUTO_FIX_BUGS" in desc
        assert "AUTO_ADD_CRITICAL" not in desc
        assert "AUTO_INSTALL_DEPS" in desc
        assert "AUTO_HANDLE_AUTH" not in desc
