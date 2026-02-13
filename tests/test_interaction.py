"""Tests for user interaction system."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest import MonkeyPatch

from nelson.interaction import (
    Answer,
    InteractionConfig,
    InteractionMode,
    Question,
    UserInteraction,
    log_interaction,
)


class TestInteractionMode:
    """Tests for InteractionMode enum."""

    def test_mode_values(self) -> None:
        """Test that all modes have correct string values."""
        assert InteractionMode.AUTONOMOUS.value == "autonomous"
        assert InteractionMode.INTERACTIVE.value == "interactive"
        assert InteractionMode.SUPERVISED.value == "supervised"

    def test_mode_from_string(self) -> None:
        """Test creating mode from string value."""
        assert InteractionMode("autonomous") == InteractionMode.AUTONOMOUS
        assert InteractionMode("interactive") == InteractionMode.INTERACTIVE
        assert InteractionMode("supervised") == InteractionMode.SUPERVISED

    def test_invalid_mode_raises(self) -> None:
        """Test that invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            InteractionMode("invalid")


class TestInteractionConfig:
    """Tests for InteractionConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = InteractionConfig()

        assert config.mode == InteractionMode.INTERACTIVE
        assert config.planning_timeout_seconds == 60
        assert config.ambiguity_timeout_seconds == 120
        assert config.prompt_on_blocked is True
        assert config.skip_planning_questions is False

    def test_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = InteractionConfig(
            mode=InteractionMode.SUPERVISED,
            planning_timeout_seconds=120,
            ambiguity_timeout_seconds=45,
            prompt_on_blocked=False,
            skip_planning_questions=True,
        )

        assert config.mode == InteractionMode.SUPERVISED
        assert config.planning_timeout_seconds == 120
        assert config.ambiguity_timeout_seconds == 45
        assert config.prompt_on_blocked is False
        assert config.skip_planning_questions is True

    def test_from_env_defaults(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with all defaults."""
        # Clear relevant environment variables
        for key in list(os.environ.keys()):
            if key.startswith("NELSON_"):
                monkeypatch.delenv(key, raising=False)

        config = InteractionConfig.from_env()

        assert config.mode == InteractionMode.INTERACTIVE
        assert config.planning_timeout_seconds == 60
        assert config.ambiguity_timeout_seconds == 120
        assert config.prompt_on_blocked is True
        assert config.skip_planning_questions is False

    def test_from_env_mode_autonomous(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with autonomous mode."""
        monkeypatch.setenv("NELSON_INTERACTION_MODE", "autonomous")

        config = InteractionConfig.from_env()

        assert config.mode == InteractionMode.AUTONOMOUS

    def test_from_env_mode_supervised(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with supervised mode."""
        monkeypatch.setenv("NELSON_INTERACTION_MODE", "supervised")

        config = InteractionConfig.from_env()

        assert config.mode == InteractionMode.SUPERVISED

    def test_from_env_mode_case_insensitive(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env mode parsing is case insensitive."""
        monkeypatch.setenv("NELSON_INTERACTION_MODE", "AUTONOMOUS")

        config = InteractionConfig.from_env()

        assert config.mode == InteractionMode.AUTONOMOUS

    def test_from_env_invalid_mode_defaults_to_interactive(self, monkeypatch: MonkeyPatch) -> None:
        """Test that invalid mode defaults to interactive."""
        monkeypatch.setenv("NELSON_INTERACTION_MODE", "invalid_mode")

        config = InteractionConfig.from_env()

        assert config.mode == InteractionMode.INTERACTIVE

    def test_from_env_timeouts(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with custom timeouts."""
        monkeypatch.setenv("NELSON_PLANNING_TIMEOUT", "90")
        monkeypatch.setenv("NELSON_AMBIGUITY_TIMEOUT", "45")

        config = InteractionConfig.from_env()

        assert config.planning_timeout_seconds == 90
        assert config.ambiguity_timeout_seconds == 45

    def test_from_env_prompt_on_blocked_false(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with prompt_on_blocked disabled."""
        monkeypatch.setenv("NELSON_PROMPT_ON_BLOCKED", "false")

        config = InteractionConfig.from_env()

        assert config.prompt_on_blocked is False

    def test_from_env_skip_planning_questions(self, monkeypatch: MonkeyPatch) -> None:
        """Test from_env with skip_planning_questions enabled."""
        monkeypatch.setenv("NELSON_SKIP_PLANNING_QUESTIONS", "true")

        config = InteractionConfig.from_env()

        assert config.skip_planning_questions is True

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable."""
        config = InteractionConfig()

        with pytest.raises(Exception):  # FrozenInstanceError
            config.mode = InteractionMode.AUTONOMOUS  # type: ignore


class TestQuestion:
    """Tests for Question dataclass."""

    def test_basic_question(self) -> None:
        """Test creating a basic question."""
        q = Question(
            id="test_q",
            question="What is your name?",
            options=None,
            default="",
        )

        assert q.id == "test_q"
        assert q.question == "What is your name?"
        assert q.options is None
        assert q.default == ""
        assert q.context == ""
        assert q.timeout_seconds is None

    def test_question_with_options(self) -> None:
        """Test creating a question with options."""
        q = Question(
            id="color_q",
            question="What is your favorite color?",
            options=["Red", "Blue", "Green"],
            default="Blue",
            context="This will determine the theme.",
            timeout_seconds=30,
        )

        assert q.id == "color_q"
        assert q.options == ["Red", "Blue", "Green"]
        assert q.default == "Blue"
        assert q.context == "This will determine the theme."
        assert q.timeout_seconds == 30


class TestAnswer:
    """Tests for Answer dataclass."""

    def test_basic_answer(self) -> None:
        """Test creating a basic answer."""
        a = Answer(
            question_id="test_q",
            response="John",
        )

        assert a.question_id == "test_q"
        assert a.response == "John"
        assert a.was_timeout is False
        assert a.was_default is False
        assert isinstance(a.timestamp, datetime)

    def test_timeout_answer(self) -> None:
        """Test creating a timeout answer."""
        a = Answer(
            question_id="test_q",
            response="default_value",
            was_timeout=True,
            was_default=True,
        )

        assert a.was_timeout is True
        assert a.was_default is True

    def test_answer_with_custom_timestamp(self) -> None:
        """Test creating answer with custom timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        a = Answer(
            question_id="test_q",
            response="response",
            timestamp=ts,
        )

        assert a.timestamp == ts


class TestUserInteraction:
    """Tests for UserInteraction class."""

    def test_autonomous_mode_returns_default(self) -> None:
        """Test that autonomous mode returns default immediately."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        q = Question(
            id="test",
            question="Choose something",
            options=["A", "B"],
            default="A",
        )

        answer = interaction.ask_question(q)

        assert answer.response == "A"
        assert answer.was_default is True
        assert answer.was_timeout is False

    def test_parse_option_numeric(self) -> None:
        """Test parsing numeric option selection."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("1", options, "Red") == "Red"
        assert interaction._parse_option_response("2", options, "Red") == "Blue"
        assert interaction._parse_option_response("3", options, "Red") == "Green"

    def test_parse_option_text_exact(self) -> None:
        """Test parsing exact text option selection."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("Red", options, "Blue") == "Red"
        assert interaction._parse_option_response("blue", options, "Red") == "Blue"
        assert interaction._parse_option_response("GREEN", options, "Red") == "Green"

    def test_parse_option_text_partial(self) -> None:
        """Test parsing partial text option selection."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("r", options, "Blue") == "Red"
        assert interaction._parse_option_response("bl", options, "Red") == "Blue"
        assert interaction._parse_option_response("gr", options, "Red") == "Green"

    def test_parse_option_empty_returns_default(self) -> None:
        """Test that empty response returns default."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("", options, "Blue") == "Blue"

    def test_parse_option_invalid_returns_default(self) -> None:
        """Test that invalid response returns default."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("Yellow", options, "Blue") == "Blue"
        assert interaction._parse_option_response("99", options, "Blue") == "Blue"

    def test_parse_option_out_of_range_returns_default(self) -> None:
        """Test that out of range numeric returns default."""
        config = InteractionConfig()
        interaction = UserInteraction(config)

        options = ["Red", "Blue", "Green"]

        assert interaction._parse_option_response("0", options, "Blue") == "Blue"
        assert interaction._parse_option_response("4", options, "Blue") == "Blue"

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_interactive_mode_with_input(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test interactive mode with user input."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)
        mock_input.return_value = "user response"

        q = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
        )

        answer = interaction.ask_question(q)

        assert answer.response == "user response"
        assert answer.was_default is False
        assert answer.was_timeout is False
        mock_display.assert_called_once()
        mock_input.assert_called_once()

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_interactive_mode_timeout(self, mock_display: MagicMock, mock_input: MagicMock) -> None:
        """Test interactive mode on timeout."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)
        mock_input.return_value = None  # Timeout

        q = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
        )

        answer = interaction.ask_question(q)

        assert answer.response == "default"
        assert answer.was_default is True
        assert answer.was_timeout is True

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_supervised_mode_no_timeout(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test supervised mode has no timeout."""
        config = InteractionConfig(mode=InteractionMode.SUPERVISED)
        interaction = UserInteraction(config)
        mock_input.return_value = "response"

        q = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
        )

        interaction.ask_question(q)

        # Should be called with None timeout
        mock_input.assert_called_once_with(None, "default")

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_question_timeout_override(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test that question-specific timeout overrides config."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE, planning_timeout_seconds=60)
        interaction = UserInteraction(config)
        mock_input.return_value = "response"

        q = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
            timeout_seconds=30,  # Override
        )

        interaction.ask_question(q)

        # Should use question timeout, not config timeout
        mock_input.assert_called_once_with(30, "default")


class TestConvenienceMethods:
    """Tests for convenience methods on UserInteraction."""

    def test_ask_multiple_choice_autonomous(self) -> None:
        """Test ask_multiple_choice in autonomous mode."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        response, was_default = interaction.ask_multiple_choice(
            question="Choose a color",
            options=["Red", "Blue", "Green"],
            default_index=1,
        )

        assert response == "Blue"
        assert was_default is True

    def test_ask_yes_no_autonomous_yes(self) -> None:
        """Test ask_yes_no in autonomous mode with default yes."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        response, was_default = interaction.ask_yes_no(
            question="Continue?",
            default=True,
        )

        assert response is True
        assert was_default is True

    def test_ask_yes_no_autonomous_no(self) -> None:
        """Test ask_yes_no in autonomous mode with default no."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        response, was_default = interaction.ask_yes_no(
            question="Continue?",
            default=False,
        )

        assert response is False
        assert was_default is True

    def test_ask_free_text_autonomous(self) -> None:
        """Test ask_free_text in autonomous mode."""
        config = InteractionConfig(mode=InteractionMode.AUTONOMOUS)
        interaction = UserInteraction(config)

        response, was_default = interaction.ask_free_text(
            question="Enter your name",
            default="Anonymous",
        )

        assert response == "Anonymous"
        assert was_default is True

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_ask_yes_no_interactive_yes_response(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test ask_yes_no with yes response."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        # Test various yes responses
        for yes_response in ["Yes", "yes", "y", "Y", "1"]:
            mock_input.return_value = yes_response

            response, was_default = interaction.ask_yes_no(
                question="Continue?",
                default=False,
            )

            assert response is True, f"Failed for '{yes_response}'"
            assert was_default is False

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_ask_yes_no_interactive_no_response(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test ask_yes_no with no response."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        # Test various no responses (option 2 = No)
        for no_response in ["No", "no", "n", "N", "2"]:
            mock_input.return_value = no_response

            response, was_default = interaction.ask_yes_no(
                question="Continue?",
                default=True,
            )

            assert response is False, f"Failed for '{no_response}'"

    @patch("nelson.interaction.UserInteraction._get_input_with_timeout")
    @patch("nelson.interaction.UserInteraction._display_question")
    def test_ask_yes_no_invalid_uses_default(
        self, mock_display: MagicMock, mock_input: MagicMock
    ) -> None:
        """Test that invalid input uses default."""
        config = InteractionConfig(mode=InteractionMode.INTERACTIVE)
        interaction = UserInteraction(config)

        # Invalid responses should use default
        mock_input.return_value = "invalid"

        response, was_default = interaction.ask_yes_no(
            question="Continue?",
            default=True,
        )

        # Invalid input falls back to default (Yes)
        assert response is True


class TestLogInteraction:
    """Tests for log_interaction function."""

    def test_log_basic_interaction(self, tmp_path: Path) -> None:
        """Test logging a basic interaction."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        question = Question(
            id="test",
            question="What is your name?",
            options=None,
            default="Anonymous",
        )
        answer = Answer(
            question_id="test",
            response="John",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        log_interaction(question, answer, decisions_file)

        content = decisions_file.read_text()
        assert "## User Interaction" in content
        assert "**Question**: What is your name?" in content
        assert "**Answer**: John" in content
        assert "2024-01-01" in content

    def test_log_interaction_with_options(self, tmp_path: Path) -> None:
        """Test logging interaction with options."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        question = Question(
            id="color",
            question="Choose a color",
            options=["Red", "Blue", "Green"],
            default="Blue",
        )
        answer = Answer(
            question_id="color",
            response="Red",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        log_interaction(question, answer, decisions_file)

        content = decisions_file.read_text()
        assert "**Options**: Red, Blue, Green" in content
        assert "**Answer**: Red" in content

    def test_log_interaction_timeout(self, tmp_path: Path) -> None:
        """Test logging timeout interaction."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        question = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
        )
        answer = Answer(
            question_id="test",
            response="default",
            was_timeout=True,
            was_default=True,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        log_interaction(question, answer, decisions_file)

        content = decisions_file.read_text()
        assert "**Note**: Timeout - used default" in content

    def test_log_interaction_autonomous(self, tmp_path: Path) -> None:
        """Test logging autonomous mode interaction."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.touch()

        question = Question(
            id="test",
            question="Enter something",
            options=None,
            default="default",
        )
        answer = Answer(
            question_id="test",
            response="default",
            was_timeout=False,
            was_default=True,  # Autonomous mode uses default without timeout
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        log_interaction(question, answer, decisions_file)

        content = decisions_file.read_text()
        assert "**Note**: Autonomous mode - used default" in content

    def test_log_interaction_appends(self, tmp_path: Path) -> None:
        """Test that logging appends to existing content."""
        decisions_file = tmp_path / "decisions.md"
        decisions_file.write_text("# Existing Content\n")

        question = Question(
            id="test",
            question="New question",
            options=None,
            default="default",
        )
        answer = Answer(
            question_id="test",
            response="response",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

        log_interaction(question, answer, decisions_file)

        content = decisions_file.read_text()
        assert "# Existing Content" in content
        assert "## User Interaction" in content
        assert "New question" in content


class TestNelsonConfigInteraction:
    """Tests for interaction integration in NelsonConfig."""

    def test_config_interaction_property(self, monkeypatch: MonkeyPatch) -> None:
        """Test that NelsonConfig has interaction property."""
        from nelson.config import NelsonConfig

        # Clear environment
        for key in list(os.environ.keys()):
            if key.startswith("NELSON_"):
                monkeypatch.delenv(key, raising=False)

        config = NelsonConfig.from_environment()

        # Should return an InteractionConfig
        interaction = config.interaction
        assert isinstance(interaction, InteractionConfig)
        assert interaction.mode == InteractionMode.INTERACTIVE

    def test_config_interaction_from_env(self, monkeypatch: MonkeyPatch) -> None:
        """Test that interaction config respects environment."""
        from nelson.config import NelsonConfig

        monkeypatch.setenv("NELSON_INTERACTION_MODE", "autonomous")
        monkeypatch.setenv("NELSON_PLANNING_TIMEOUT", "120")

        config = NelsonConfig.from_environment()
        interaction = config.interaction

        assert interaction.mode == InteractionMode.AUTONOMOUS
        assert interaction.planning_timeout_seconds == 120
