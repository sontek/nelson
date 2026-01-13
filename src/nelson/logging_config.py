"""Logging configuration for Nelson using rich for colored console output.

This module provides structured logging with colored output levels matching
the bash implementation's log_info, log_success, log_warning, log_error.
"""

import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Custom theme matching bash nelson color scheme
NELSON_THEME = Theme(
    {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "debug": "dim",
    }
)


class NelsonLogger:
    """Logger with colored console output using rich.

    Provides methods matching the bash nelson logging interface:
    - log_info()
    - log_success()
    - log_warning()
    - log_error()
    """

    def __init__(self, name: str = "nelson", level: int = logging.INFO) -> None:
        """Initialize logger with rich console handler.

        Args:
            name: Logger name (default: "nelson")
            level: Logging level (default: INFO)
        """
        self.console = Console(theme=NELSON_THEME)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Add rich handler with custom formatting
        handler = RichHandler(
            console=self.console,
            show_time=False,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log info message with blue [INFO] prefix.

        Args:
            message: Message to log
            *args: Format arguments
            **kwargs: Additional logging kwargs
        """
        self.console.print(f"[info][INFO][/info] {message}", *args, **kwargs)

    def success(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log success message with green [SUCCESS] prefix.

        Args:
            message: Message to log
            *args: Format arguments
            **kwargs: Additional logging kwargs
        """
        self.console.print(f"[success][SUCCESS][/success] {message}", *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message with yellow [WARNING] prefix.

        Args:
            message: Message to log
            *args: Format arguments
            **kwargs: Additional logging kwargs
        """
        self.console.print(f"[warning][WARNING][/warning] {message}", *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log error message with red bold [ERROR] prefix.

        Args:
            message: Message to log
            *args: Format arguments
            **kwargs: Additional logging kwargs
        """
        self.console.print(f"[error][ERROR][/error] {message}", *args, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message with dim [DEBUG] prefix.

        Args:
            message: Message to log
            *args: Format arguments
            **kwargs: Additional logging kwargs
        """
        if self.logger.level <= logging.DEBUG:
            self.console.print(f"[debug][DEBUG][/debug] {message}", *args, **kwargs)


# Global logger instance (singleton pattern)
_logger_instance: NelsonLogger | None = None


def get_logger(name: str = "nelson", level: int = logging.INFO) -> NelsonLogger:
    """Get or create the global Nelson logger instance.

    Args:
        name: Logger name (default: "nelson")
        level: Logging level (default: INFO)

    Returns:
        NelsonLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = NelsonLogger(name=name, level=level)
    return _logger_instance


def set_log_level(level: int) -> None:
    """Set the logging level for the global logger.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
    """
    logger = get_logger()
    logger.logger.setLevel(level)
