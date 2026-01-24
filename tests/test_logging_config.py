"""Tests for logging configuration module."""

import logging
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from nelson.logging_config import (
    NELSON_THEME,
    PHASE_COLORS,
    NelsonLogger,
    get_logger,
    get_phase_color,
    set_log_level,
)


class TestNelsonLogger:
    """Test NelsonLogger class."""

    def test_logger_initialization(self) -> None:
        """Test that logger initializes with correct defaults."""
        logger = NelsonLogger()
        assert logger.logger.name == "nelson"
        assert logger.logger.level == logging.INFO
        assert logger.console is not None

    def test_logger_custom_name_and_level(self) -> None:
        """Test logger with custom name and level."""
        logger = NelsonLogger(name="test_logger", level=logging.DEBUG)
        assert logger.logger.name == "test_logger"
        assert logger.logger.level == logging.DEBUG

    def test_info_message(self) -> None:
        """Test info message output."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.info("Test info message")
            mock_print.assert_called_once_with("[info][INFO][/info] Test info message")

    def test_success_message(self) -> None:
        """Test success message output."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.success("Test success message")
            mock_print.assert_called_once_with("[success][SUCCESS][/success] Test success message")

    def test_warning_message(self) -> None:
        """Test warning message output."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.warning("Test warning message")
            mock_print.assert_called_once_with("[warning][WARNING][/warning] Test warning message")

    def test_error_message(self) -> None:
        """Test error message output."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.error("Test error message")
            mock_print.assert_called_once_with("[error][ERROR][/error] Test error message")

    def test_debug_message_when_debug_enabled(self) -> None:
        """Test debug message is shown when debug level is enabled."""
        logger = NelsonLogger(level=logging.DEBUG)
        with patch.object(logger.console, "print") as mock_print:
            logger.debug("Test debug message")
            mock_print.assert_called_once_with("[debug][DEBUG][/debug] Test debug message")

    def test_debug_message_when_debug_disabled(self) -> None:
        """Test debug message is hidden when debug level is disabled."""
        logger = NelsonLogger(level=logging.INFO)
        with patch.object(logger.console, "print") as mock_print:
            logger.debug("Test debug message")
            mock_print.assert_not_called()

    def test_message_with_format_args(self) -> None:
        """Test logging with additional format arguments."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.info("Test message", style="bold")
            mock_print.assert_called_once_with("[info][INFO][/info] Test message", style="bold")

    def test_no_duplicate_handlers(self) -> None:
        """Test that creating multiple loggers doesn't create duplicate handlers."""
        logger1 = NelsonLogger(name="test_dup")
        handler_count_1 = len(logger1.logger.handlers)

        logger2 = NelsonLogger(name="test_dup")
        handler_count_2 = len(logger2.logger.handlers)

        # Should have same number of handlers (old ones cleared)
        assert handler_count_2 == handler_count_1 == 1

    def test_console_theme_applied(self) -> None:
        """Test that custom theme is applied to console."""
        logger = NelsonLogger()
        # Console was initialized with a theme, verify by checking it exists
        # We can't directly access theme attribute, but we can verify console exists
        assert logger.console is not None
        assert isinstance(logger.console, Console)


class TestGlobalLogger:
    """Test global logger functions."""

    def test_get_logger_singleton(self) -> None:
        """Test that get_logger returns singleton instance."""
        # Reset global logger
        import nelson.logging_config

        nelson.logging_config._logger_instance = None

        logger1 = get_logger()
        logger2 = get_logger()

        # Should be the same instance
        assert logger1 is logger2

    def test_get_logger_with_custom_params(self) -> None:
        """Test get_logger with custom parameters on first call."""
        import nelson.logging_config

        nelson.logging_config._logger_instance = None

        logger = get_logger(name="custom", level=logging.DEBUG)
        assert logger.logger.name == "custom"
        assert logger.logger.level == logging.DEBUG

    def test_set_log_level(self) -> None:
        """Test changing log level on global logger."""
        import nelson.logging_config

        nelson.logging_config._logger_instance = None

        logger = get_logger(level=logging.INFO)
        assert logger.logger.level == logging.INFO

        set_log_level(logging.DEBUG)
        assert logger.logger.level == logging.DEBUG

        set_log_level(logging.WARNING)
        assert logger.logger.level == logging.WARNING


class TestRealOutput:
    """Test actual console output (integration-style tests)."""

    def test_info_output_format(self) -> None:
        """Test that info messages produce expected format."""
        # Create logger with StringIO console to capture output
        from nelson.logging_config import NELSON_THEME

        string_io = StringIO()
        logger = NelsonLogger()
        logger.console = Console(
            file=string_io, theme=NELSON_THEME, force_terminal=True, legacy_windows=False
        )

        logger.info("Test message")
        output = string_io.getvalue()

        # Should contain INFO prefix and message (checking for "INFO" without brackets
        # because ANSI codes may split the brackets)
        assert "INFO" in output
        assert "Test message" in output

    def test_multiple_log_levels(self) -> None:
        """Test multiple log levels produce different prefixes."""
        from nelson.logging_config import NELSON_THEME

        string_io = StringIO()
        logger = NelsonLogger(level=logging.DEBUG)
        logger.console = Console(
            file=string_io, theme=NELSON_THEME, force_terminal=True, legacy_windows=False
        )

        logger.info("Info test")
        logger.success("Success test")
        logger.warning("Warning test")
        logger.error("Error test")
        logger.debug("Debug test")

        output = string_io.getvalue()

        # All prefixes should be present (checking without brackets due to ANSI codes)
        assert "INFO" in output
        assert "SUCCESS" in output
        assert "WARNING" in output
        assert "ERROR" in output
        assert "DEBUG" in output

        # All messages should be present
        assert "Info test" in output
        assert "Success test" in output
        assert "Warning test" in output
        assert "Error test" in output
        assert "Debug test" in output


class TestPhaseColors:
    """Tests for phase color mapping."""

    def test_phase_colors_mapping_exists(self) -> None:
        """Test that all phase colors are defined."""
        assert 0 in PHASE_COLORS  # DISCOVER
        assert 1 in PHASE_COLORS  # PLAN
        assert 2 in PHASE_COLORS  # IMPLEMENT
        assert 3 in PHASE_COLORS  # REVIEW
        assert 4 in PHASE_COLORS  # TEST
        assert 5 in PHASE_COLORS  # FINAL_REVIEW
        assert 6 in PHASE_COLORS  # COMMIT
        assert 7 in PHASE_COLORS  # ROADMAP

    def test_get_phase_color_returns_correct_style(self) -> None:
        """Test get_phase_color returns correct style for each phase."""
        assert get_phase_color(0) == "phase.discover"
        assert get_phase_color(1) == "phase.plan"
        assert get_phase_color(2) == "phase.implement"
        assert get_phase_color(3) == "phase.review"
        assert get_phase_color(4) == "phase.test"
        assert get_phase_color(5) == "phase.final_review"
        assert get_phase_color(6) == "phase.commit"
        assert get_phase_color(7) == "phase.roadmap"

    def test_get_phase_color_fallback(self) -> None:
        """Test get_phase_color returns fallback for unknown phases."""
        assert get_phase_color(99) == "info"
        assert get_phase_color(-1) == "info"


class TestPhaseLogging:
    """Tests for phase-specific logging."""

    def test_phase_message(self) -> None:
        """Test phase logging produces correct format."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.phase(1, "PLAN", "Creating implementation plan")
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Phase 1: PLAN" in call_args
            assert "Creating implementation plan" in call_args

    def test_status_message(self) -> None:
        """Test status line produces correct format."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.status(cycle=1, phase=2, phase_name="IMPLEMENT", iteration=5)
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "Cycle 1" in call_args
            assert "Phase 2" in call_args
            assert "IMPLEMENT" in call_args
            assert "Iteration #5" in call_args

    def test_status_message_with_cost(self) -> None:
        """Test status line includes cost when provided."""
        logger = NelsonLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.status(cycle=2, phase=3, phase_name="REVIEW", iteration=10, cost=1.23)
            call_args = mock_print.call_args[0][0]
            assert "$1.23" in call_args


class TestSpinner:
    """Tests for spinner context manager."""

    def test_spinner_context_manager(self) -> None:
        """Test spinner context manager works."""
        logger = NelsonLogger()
        with patch.object(logger.console, "status") as mock_status:
            mock_status.return_value.__enter__ = lambda x: x
            mock_status.return_value.__exit__ = lambda x, y, z, w: None

            with logger.spinner("Testing...") as status:
                assert status is not None

            mock_status.assert_called_once()


class TestSummaryPanel:
    """Tests for summary panel display."""

    def test_summary_panel(self) -> None:
        """Test summary panel is displayed correctly."""
        string_io = StringIO()
        logger = NelsonLogger()
        logger.console = Console(
            file=string_io, theme=NELSON_THEME, force_terminal=True, legacy_windows=False
        )

        logger.summary_panel("Test Summary", {"Key1": "Value1", "Key2": "Value2"})
        output = string_io.getvalue()

        assert "Test Summary" in output
        assert "Key1" in output
        assert "Value1" in output
        assert "Key2" in output
        assert "Value2" in output

    def test_workflow_complete_success(self) -> None:
        """Test workflow complete panel for success case."""
        string_io = StringIO()
        logger = NelsonLogger()
        logger.console = Console(
            file=string_io, theme=NELSON_THEME, force_terminal=True, legacy_windows=False
        )

        logger.workflow_complete(cycles=3, iterations=25, cost=5.67, elapsed="2m 30s")
        output = string_io.getvalue()

        assert "Workflow Complete" in output
        assert "3" in output  # cycles
        assert "25" in output  # iterations
        assert "$5.67" in output
        assert "2m 30s" in output

    def test_workflow_complete_failure(self) -> None:
        """Test workflow complete panel for failure case."""
        string_io = StringIO()
        logger = NelsonLogger()
        logger.console = Console(
            file=string_io, theme=NELSON_THEME, force_terminal=True, legacy_windows=False
        )

        logger.workflow_complete(cycles=1, iterations=3, success=False)
        output = string_io.getvalue()

        assert "Workflow Failed" in output
        assert "1" in output  # cycles
        assert "3" in output  # iterations
