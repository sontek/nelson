"""Tests for blocked state handling module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from nelson.blocked_handling import (
    COMMON_BLOCKERS,
    BlockedInfo,
    BlockedResolution,
    detect_blocker_category,
    extract_blocked_info,
    format_resolution_context,
    get_blocker_hint,
    log_blocked_event,
    prompt_blocked_resolution,
)
from nelson.interaction import InteractionConfig, InteractionMode, UserInteraction


class TestBlockedResolution:
    """Tests for BlockedResolution enum."""

    def test_resolution_values(self) -> None:
        """Test resolution enum values."""
        assert BlockedResolution.RESOLVED.value == "resolved"
        assert BlockedResolution.SKIP.value == "skip"
        assert BlockedResolution.STOP.value == "stop"


class TestBlockedInfo:
    """Tests for BlockedInfo dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic BlockedInfo creation."""
        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["OPENAI_API_KEY"],
            suggested_resolution="Add to .env",
        )

        assert blocked.task_id == "01"
        assert blocked.reason == "Missing API key"
        assert blocked.required_resources == ["OPENAI_API_KEY"]
        assert blocked.suggested_resolution == "Add to .env"
        assert blocked.phase is None
        assert blocked.iteration is None

    def test_full_creation(self) -> None:
        """Test BlockedInfo with all fields."""
        blocked = BlockedInfo(
            task_id="02",
            reason="Database offline",
            required_resources=["DATABASE_URL", "POSTGRES_PASSWORD"],
            suggested_resolution="Start PostgreSQL",
            phase="IMPLEMENT",
            iteration=5,
        )

        assert blocked.phase == "IMPLEMENT"
        assert blocked.iteration == 5
        assert len(blocked.required_resources) == 2

    def test_to_dict(self) -> None:
        """Test BlockedInfo serialization."""
        blocked = BlockedInfo(
            task_id="01",
            reason="Test reason",
            required_resources=["RES1", "RES2"],
            suggested_resolution="Fix it",
            phase="TEST",
            iteration=3,
        )

        data = blocked.to_dict()

        assert data["task_id"] == "01"
        assert data["reason"] == "Test reason"
        assert data["required_resources"] == ["RES1", "RES2"]
        assert data["suggested_resolution"] == "Fix it"
        assert data["phase"] == "TEST"
        assert data["iteration"] == 3


class TestExtractBlockedInfo:
    """Tests for extract_blocked_info function."""

    def test_extract_from_status_block(self) -> None:
        """Test extracting info from status block."""
        status_block = {
            "status": "BLOCKED",
            "blocked_reason": "Cannot connect to database",
            "blocked_resources": "DATABASE_URL, POSTGRES_PASSWORD",
            "blocked_resolution": "Start PostgreSQL service",
            "recommendation": "Database connection failed",
        }
        response = ""

        info = extract_blocked_info(status_block, response)

        assert info is not None
        assert info.reason == "Cannot connect to database"
        assert info.required_resources == ["DATABASE_URL", "POSTGRES_PASSWORD"]
        assert info.suggested_resolution == "Start PostgreSQL service"

    def test_extract_uses_recommendation_fallback(self) -> None:
        """Test fallback to recommendation for reason."""
        status_block = {
            "status": "BLOCKED",
            "recommendation": "Need API key to continue",
        }
        response = ""

        info = extract_blocked_info(status_block, response)

        assert info is not None
        assert info.reason == "Need API key to continue"

    def test_extract_extracts_resources_from_content(self) -> None:
        """Test extracting resources from response content."""
        status_block = {
            "status": "BLOCKED",
            "recommendation": "Missing credentials",
        }
        response = "Need OPENAI_API_KEY and STRIPE_SECRET_KEY to proceed"

        info = extract_blocked_info(status_block, response)

        assert info is not None
        assert "OPENAI_API_KEY" in info.required_resources
        assert "STRIPE_SECRET_KEY" in info.required_resources

    def test_extract_returns_none_for_non_blocked(self) -> None:
        """Test returns None when status is not BLOCKED."""
        status_block = {
            "status": "COMPLETE",
            "recommendation": "All done",
        }
        response = ""

        info = extract_blocked_info(status_block, response)

        assert info is None

    def test_extract_handles_in_progress(self) -> None:
        """Test returns None for IN_PROGRESS status."""
        status_block = {
            "status": "IN_PROGRESS",
            "recommendation": "Continue working",
        }
        response = ""

        info = extract_blocked_info(status_block, response)

        assert info is None


class TestPromptBlockedResolution:
    """Tests for prompt_blocked_resolution function."""

    def test_autonomous_mode_returns_skip(self) -> None:
        """Test autonomous mode auto-skips."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["API_KEY"],
        )

        resolution, context = prompt_blocked_resolution(blocked, interaction)

        assert resolution == BlockedResolution.SKIP
        assert context is None

    @patch("nelson.blocked_handling.console")
    def test_interactive_resolved_with_context(self, mock_console: MagicMock) -> None:
        """Test interactive mode with resolved choice."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["API_KEY"],
        )

        with patch.object(
            interaction, "ask_multiple_choice", return_value=("Continue (resolved)", False)
        ):
            with patch.object(interaction, "ask_free_text", return_value=("Added the key", False)):
                resolution, context = prompt_blocked_resolution(blocked, interaction)

        assert resolution == BlockedResolution.RESOLVED
        assert context == "Added the key"

    @patch("nelson.blocked_handling.console")
    def test_interactive_skip(self, mock_console: MagicMock) -> None:
        """Test interactive mode with skip choice."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["API_KEY"],
        )

        with patch.object(interaction, "ask_multiple_choice", return_value=("Skip task", False)):
            resolution, context = prompt_blocked_resolution(blocked, interaction)

        assert resolution == BlockedResolution.SKIP
        assert context is None

    @patch("nelson.blocked_handling.console")
    def test_interactive_stop(self, mock_console: MagicMock) -> None:
        """Test interactive mode with stop choice."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["API_KEY"],
        )

        with patch.object(
            interaction, "ask_multiple_choice", return_value=("Stop execution", False)
        ):
            resolution, context = prompt_blocked_resolution(blocked, interaction)

        assert resolution == BlockedResolution.STOP
        assert context is None


class TestFormatResolutionContext:
    """Tests for format_resolution_context function."""

    def test_format_with_context(self) -> None:
        """Test formatting with resolution context."""
        blocked = BlockedInfo(
            task_id="01",
            reason="Database connection failed",
            required_resources=["DATABASE_URL"],
        )

        formatted = format_resolution_context(blocked, "Started the database")

        assert "## Blocker Resolved" in formatted
        assert "Database connection failed" in formatted
        assert "Started the database" in formatted

    def test_format_without_context(self) -> None:
        """Test formatting without resolution context."""
        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["API_KEY"],
        )

        formatted = format_resolution_context(blocked, None)

        assert "## Blocker Resolved" in formatted
        assert "Missing API key" in formatted
        assert "User confirmed the issue has been resolved" in formatted


class TestLogBlockedEvent:
    """Tests for log_blocked_event function."""

    def test_log_basic_event(self, tmp_path: Path) -> None:
        """Test logging basic blocked event."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        blocked = BlockedInfo(
            task_id="01",
            reason="Missing API key",
            required_resources=["OPENAI_API_KEY"],
        )

        log_blocked_event(blocked, BlockedResolution.RESOLVED, "Added the key", decisions_file)

        content = decisions_file.read_text()
        assert "## Task Blocked" in content
        assert "Missing API key" in content
        assert "OPENAI_API_KEY" in content
        assert "resolved" in content
        assert "Added the key" in content

    def test_log_skip_event(self, tmp_path: Path) -> None:
        """Test logging skip event."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        blocked = BlockedInfo(
            task_id="01",
            reason="Service unavailable",
            required_resources=[],
        )

        log_blocked_event(blocked, BlockedResolution.SKIP, None, decisions_file)

        content = decisions_file.read_text()
        assert "skip" in content
        assert "Resolution Context" not in content

    def test_log_with_suggestion(self, tmp_path: Path) -> None:
        """Test logging with suggested resolution."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        blocked = BlockedInfo(
            task_id="01",
            reason="Database offline",
            required_resources=["DATABASE_URL"],
            suggested_resolution="Start PostgreSQL service",
        )

        log_blocked_event(blocked, BlockedResolution.STOP, None, decisions_file)

        content = decisions_file.read_text()
        assert "Start PostgreSQL service" in content
        assert "stop" in content

    def test_log_appends_to_existing(self, tmp_path: Path) -> None:
        """Test logging appends to existing content."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Previous Content\n")

        blocked = BlockedInfo(
            task_id="01",
            reason="Test reason",
            required_resources=[],
        )

        log_blocked_event(blocked, BlockedResolution.SKIP, None, decisions_file)

        content = decisions_file.read_text()
        assert "# Previous Content" in content
        assert "## Task Blocked" in content


class TestDetectBlockerCategory:
    """Tests for detect_blocker_category function."""

    def test_detect_api_key(self) -> None:
        """Test detecting API key blocker."""
        blocked = BlockedInfo(
            task_id=None,
            reason="Need OPENAI_API_KEY to continue",
            required_resources=["OPENAI_API_KEY"],
        )

        category = detect_blocker_category(blocked)

        assert category == "api_key"

    def test_detect_database(self) -> None:
        """Test detecting database blocker."""
        blocked = BlockedInfo(
            task_id=None,
            reason="Cannot connect to postgres database",
            required_resources=[],
        )

        category = detect_blocker_category(blocked)

        assert category == "database"

    def test_detect_permission(self) -> None:
        """Test detecting permission blocker."""
        blocked = BlockedInfo(
            task_id=None,
            reason="Permission denied accessing file",
            required_resources=[],
        )

        category = detect_blocker_category(blocked)

        assert category == "permission"

    def test_detect_unknown(self) -> None:
        """Test returns None for unknown blocker."""
        blocked = BlockedInfo(
            task_id=None,
            reason="Something weird happened",
            required_resources=[],
        )

        category = detect_blocker_category(blocked)

        assert category is None


class TestGetBlockerHint:
    """Tests for get_blocker_hint function."""

    def test_get_hint_for_api_key(self) -> None:
        """Test getting hint for API key."""
        hint = get_blocker_hint("api_key")
        assert hint is not None
        assert ".env" in hint.lower()

    def test_get_hint_for_database(self) -> None:
        """Test getting hint for database."""
        hint = get_blocker_hint("database")
        assert hint is not None
        assert "database" in hint.lower()

    def test_get_hint_for_unknown(self) -> None:
        """Test returns None for unknown category."""
        hint = get_blocker_hint("unknown_category")
        assert hint is None


class TestCommonBlockers:
    """Tests for COMMON_BLOCKERS dictionary."""

    def test_common_blockers_exist(self) -> None:
        """Test common blocker categories exist."""
        assert "api_key" in COMMON_BLOCKERS
        assert "database" in COMMON_BLOCKERS
        assert "service" in COMMON_BLOCKERS
        assert "permission" in COMMON_BLOCKERS
        assert "dependency" in COMMON_BLOCKERS

    def test_common_blockers_have_patterns_and_hints(self) -> None:
        """Test each blocker has patterns and hints."""
        for name, info in COMMON_BLOCKERS.items():
            assert "patterns" in info, f"{name} missing patterns"
            assert "hint" in info, f"{name} missing hint"
            assert len(info["patterns"]) > 0, f"{name} has no patterns"
            assert info["hint"], f"{name} has empty hint"
