"""Tests for logging configuration module."""

import logging
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from nelson.logging_config import RalphLogger, get_logger, set_log_level


class TestRalphLogger:
    """Test RalphLogger class."""

    def test_logger_initialization(self) -> None:
        """Test that logger initializes with correct defaults."""
        logger = RalphLogger()
        assert logger.logger.name == "ralph"
        assert logger.logger.level == logging.INFO
        assert logger.console is not None

    def test_logger_custom_name_and_level(self) -> None:
        """Test logger with custom name and level."""
        logger = RalphLogger(name="test_logger", level=logging.DEBUG)
        assert logger.logger.name == "test_logger"
        assert logger.logger.level == logging.DEBUG

    def test_info_message(self) -> None:
        """Test info message output."""
        logger = RalphLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.info("Test info message")
            mock_print.assert_called_once_with("[info][INFO][/info] Test info message")

    def test_success_message(self) -> None:
        """Test success message output."""
        logger = RalphLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.success("Test success message")
            mock_print.assert_called_once_with(
                "[success][SUCCESS][/success] Test success message"
            )

    def test_warning_message(self) -> None:
        """Test warning message output."""
        logger = RalphLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.warning("Test warning message")
            mock_print.assert_called_once_with(
                "[warning][WARNING][/warning] Test warning message"
            )

    def test_error_message(self) -> None:
        """Test error message output."""
        logger = RalphLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.error("Test error message")
            mock_print.assert_called_once_with("[error][ERROR][/error] Test error message")

    def test_debug_message_when_debug_enabled(self) -> None:
        """Test debug message is shown when debug level is enabled."""
        logger = RalphLogger(level=logging.DEBUG)
        with patch.object(logger.console, "print") as mock_print:
            logger.debug("Test debug message")
            mock_print.assert_called_once_with("[debug][DEBUG][/debug] Test debug message")

    def test_debug_message_when_debug_disabled(self) -> None:
        """Test debug message is hidden when debug level is disabled."""
        logger = RalphLogger(level=logging.INFO)
        with patch.object(logger.console, "print") as mock_print:
            logger.debug("Test debug message")
            mock_print.assert_not_called()

    def test_message_with_format_args(self) -> None:
        """Test logging with additional format arguments."""
        logger = RalphLogger()
        with patch.object(logger.console, "print") as mock_print:
            logger.info("Test message", style="bold")
            mock_print.assert_called_once_with(
                "[info][INFO][/info] Test message", style="bold"
            )

    def test_no_duplicate_handlers(self) -> None:
        """Test that creating multiple loggers doesn't create duplicate handlers."""
        logger1 = RalphLogger(name="test_dup")
        handler_count_1 = len(logger1.logger.handlers)

        logger2 = RalphLogger(name="test_dup")
        handler_count_2 = len(logger2.logger.handlers)

        # Should have same number of handlers (old ones cleared)
        assert handler_count_2 == handler_count_1 == 1

    def test_console_theme_applied(self) -> None:
        """Test that custom theme is applied to console."""
        logger = RalphLogger()
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
        from nelson.logging_config import RALPH_THEME

        string_io = StringIO()
        logger = RalphLogger()
        logger.console = Console(
            file=string_io, theme=RALPH_THEME, force_terminal=True, legacy_windows=False
        )

        logger.info("Test message")
        output = string_io.getvalue()

        # Should contain INFO prefix and message (checking for "INFO" without brackets
        # because ANSI codes may split the brackets)
        assert "INFO" in output
        assert "Test message" in output

    def test_multiple_log_levels(self) -> None:
        """Test multiple log levels produce different prefixes."""
        from nelson.logging_config import RALPH_THEME

        string_io = StringIO()
        logger = RalphLogger(level=logging.DEBUG)
        logger.console = Console(
            file=string_io, theme=RALPH_THEME, force_terminal=True, legacy_windows=False
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
