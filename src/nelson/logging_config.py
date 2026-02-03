"""Logging configuration for Nelson using rich for colored console output.

This module provides structured logging with colored output levels matching
the bash implementation's log_info, log_success, log_warning, log_error.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.theme import Theme

# Custom theme matching bash nelson color scheme
NELSON_THEME = Theme(
    {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "debug": "dim",
        # Phase-specific colors
        "phase.discover": "magenta",
        "phase.plan": "cyan",
        "phase.implement": "blue",
        "phase.review": "yellow",
        "phase.test": "green",
        "phase.final_review": "yellow bold",
        "phase.commit": "green bold",
        "phase.roadmap": "magenta bold",
        # Progress/status colors
        "progress.active": "cyan",
        "progress.complete": "green",
        "progress.pending": "dim",
        "cost": "yellow",
        "iteration": "blue",
    }
)


# Phase color mapping
PHASE_COLORS = {
    0: "phase.discover",
    1: "phase.plan",
    2: "phase.implement",
    3: "phase.review",
    4: "phase.test",
    5: "phase.final_review",
    6: "phase.commit",
    7: "phase.roadmap",
}


def get_phase_color(phase_number: int) -> str:
    """Get the color style for a phase number.

    Args:
        phase_number: Phase number (0-7)

    Returns:
        Rich style name for the phase
    """
    return PHASE_COLORS.get(phase_number, "info")


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

    def phase(self, phase_number: int, phase_name: str, message: str) -> None:
        """Log message with phase-specific color.

        Args:
            phase_number: Phase number (0-7)
            phase_name: Human-readable phase name
            message: Message to log
        """
        color = get_phase_color(phase_number)
        self.console.print(f"[{color}][Phase {phase_number}: {phase_name}][/{color}] {message}")

    def status(
        self,
        cycle: int,
        phase: int,
        phase_name: str,
        iteration: int,
        cost: float | None = None,
    ) -> None:
        """Log a status line with cycle/phase/iteration info.

        Args:
            cycle: Current cycle number
            phase: Current phase number
            phase_name: Human-readable phase name
            iteration: Total iteration count
            cost: Cost in USD (optional)
        """
        phase_color = get_phase_color(phase)
        parts = [
            f"[iteration]Cycle {cycle}[/iteration]",
            f"[{phase_color}]Phase {phase}: {phase_name}[/{phase_color}]",
            f"[iteration]Iteration #{iteration}[/iteration]",
        ]
        if cost is not None:
            parts.append(f"[cost]${cost:.2f}[/cost]")
        self.console.print(" | ".join(parts))

    @contextmanager
    def spinner(self, message: str = "Working...") -> Generator[Status, None, None]:
        """Context manager for showing a spinner during long operations.

        Args:
            message: Initial message to display

        Yields:
            Status object that can be updated with status.update()

        Example:
            with logger.spinner("Calling Claude...") as status:
                result = api_call()
                status.update("Processing response...")
        """
        with self.console.status(f"[progress.active]{message}[/progress.active]") as status:
            yield status

    def summary_panel(
        self,
        title: str,
        data: dict[str, Any],
        style: str = "green",
    ) -> None:
        """Display a summary panel with key-value data.

        Args:
            title: Panel title
            data: Dictionary of key-value pairs to display
            style: Border style (default: green)
        """
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold")
        table.add_column("Value")

        for key, value in data.items():
            table.add_row(key, str(value))

        panel = Panel(
            table,
            title=f"[bold]{title}[/bold]",
            border_style=style,
            padding=(1, 2),
        )
        self.console.print(panel)

    def workflow_complete(
        self,
        cycles: int,
        iterations: int,
        cost: float | None = None,
        elapsed: str | None = None,
        success: bool = True,
    ) -> None:
        """Display workflow completion summary.

        Args:
            cycles: Number of completed cycles
            iterations: Total iterations
            cost: Total cost in USD (optional)
            elapsed: Elapsed time string (optional)
            success: Whether workflow completed successfully
        """
        title = "✓ Workflow Complete" if success else "✗ Workflow Failed"
        style = "green" if success else "red"

        data = {
            "Cycles": str(cycles),
            "Total Iterations": str(iterations),
        }
        if cost is not None:
            data["Total Cost"] = f"${cost:.2f}"
        if elapsed is not None:
            data["Elapsed Time"] = elapsed

        self.summary_panel(title, data, style)


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
