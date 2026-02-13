"""UI components for Nelson using Rich library.

This module provides visual components for better user experience:
- Phase progress indicators
- Task progress display
- Completion summaries
- Verbosity control
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from nelson.phases import Phase
    from nelson.state import NelsonState

console = Console()


def render_phase_progress(current_phase: Phase, total_phases: int = 6) -> str:
    """Render phase progress as visual indicator (●●●○○○).

    Args:
        current_phase: Current phase
        total_phases: Total number of phases (6 for standard, 4 for quick)

    Returns:
        String with filled/empty circles showing progress
    """
    filled = "●" * current_phase.value
    empty = "○" * (total_phases - current_phase.value)
    return f"{filled}{empty}"


def display_phase_header(
    current_phase: Phase,
    cycle: int,
    iteration: int,
    total_phases: int = 6,
) -> None:
    """Display phase header with progress indicator.

    Args:
        current_phase: Current phase
        cycle: Current cycle number (1-indexed for display)
        iteration: Current iteration number
        total_phases: Total number of phases
    """
    progress = render_phase_progress(current_phase, total_phases)
    timestamp = datetime.now().strftime("%H:%M:%S")

    header = (
        f"[bold yellow]Cycle {cycle} | "
        f"Phase {current_phase.value}: {current_phase.name_str} | "
        f"Progress: {progress} | "
        f"API Call #{iteration} | "
        f"{timestamp}[/bold yellow]"
    )

    console.rule(header, style="yellow")
    console.print()


def display_task_progress(task_number: int, total_tasks: int, task_name: str) -> None:
    """Display current task being worked on.

    Args:
        task_number: Current task number (1-indexed)
        total_tasks: Total number of tasks
        task_name: Name of the task
    """
    percent = int((task_number / total_tasks) * 100) if total_tasks > 0 else 0

    content = (
        f"[cyan]Task [{task_number}/{total_tasks}][/cyan] ({percent}%)\n[dim]{task_name}[/dim]"
    )

    console.print(Panel(content, border_style="cyan", padding=(0, 1)))


def display_completion_summary(
    state: NelsonState,
    start_time: datetime,
    success: bool = True,
) -> None:
    """Display completion summary with metrics.

    Args:
        state: Final workflow state
        start_time: When workflow started
        success: Whether workflow completed successfully
    """
    end_time = datetime.now()
    duration = end_time - start_time

    # Format duration nicely
    duration_str = _format_duration(duration)

    # Create summary table
    table = Table(title="Nelson Run Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan", width=25)
    table.add_column("Value", style="green" if success else "red", width=20)

    # Add metrics
    table.add_row("Status", "✓ Success" if success else "✗ Failed")
    table.add_row("Duration", duration_str)
    table.add_row("Total API Calls", str(state.total_iterations))
    table.add_row("Cycles Completed", str(state.cycle_iterations))
    table.add_row("Current Phase", f"{state.current_phase} ({state.phase_name})")

    # Optional metrics if available
    if hasattr(state, "deviations_count") and state.deviations_count > 0:
        table.add_row("Auto-Fix Deviations", str(state.deviations_count))

    if hasattr(state, "verification_retries") and state.verification_retries > 0:
        table.add_row("Verification Retries", str(state.verification_retries))

    # Cost if tracked
    if state.cost_usd > 0:
        table.add_row("Estimated Cost", f"${state.cost_usd:.4f}")

    console.print()
    console.print(Panel(table, border_style="green" if success else "red", padding=(1, 2)))
    console.print()


def _format_duration(duration: timedelta) -> str:
    """Format duration nicely.

    Args:
        duration: Time delta to format

    Returns:
        Human-readable duration string
    """
    total_seconds = int(duration.total_seconds())

    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours = minutes // 60
    minutes = minutes % 60

    return f"{hours}h {minutes}m {seconds}s"


def display_blocked_prompt(reason: str, resources: list[str], suggestion: str | None) -> None:
    """Display blocked task information.

    Args:
        reason: Why the task is blocked
        resources: Required resources
        suggestion: Suggested resolution
    """
    content_parts = [
        f"[bold red]Blocked:[/bold red] {reason}",
        "",
    ]

    if resources:
        content_parts.append("[bold yellow]Required Resources:[/bold yellow]")
        for resource in resources:
            content_parts.append(f"  • {resource}")
        content_parts.append("")

    if suggestion:
        content_parts.append(f"[bold green]Suggestion:[/bold green] {suggestion}")
        content_parts.append("")

    console.print(
        Panel(
            "\n".join(content_parts),
            title="[bold red]Task Blocked[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )


def display_verification_results(passed: int, failed: int, total: int) -> None:
    """Display verification results summary.

    Args:
        passed: Number of checks that passed
        failed: Number of checks that failed
        total: Total number of checks
    """
    status = "✓ PASSED" if failed == 0 else "✗ FAILED"
    style = "green" if failed == 0 else "red"

    content = (
        f"[bold {style}]{status}[/bold {style}]\n\n"
        f"[cyan]Checks Passed:[/cyan] {passed}/{total}\n"
        f"[red]Checks Failed:[/red] {failed}/{total}"
    )

    console.print(
        Panel(
            content,
            title="[bold cyan]Verification Results[/bold cyan]",
            border_style=style,
            padding=(1, 2),
        )
    )


def display_deviation_summary(auto_fixes: int, blocked: int) -> None:
    """Display deviation summary.

    Args:
        auto_fixes: Number of auto-fixes applied
        blocked: Number of deviations blocked
    """
    if auto_fixes == 0 and blocked == 0:
        return

    content_parts = []

    if auto_fixes > 0:
        content_parts.append(
            f"[green]✓ Applied {auto_fixes} auto-fix{'es' if auto_fixes != 1 else ''}[/green]"
        )

    if blocked > 0:
        plural = "s" if blocked != 1 else ""
        content_parts.append(
            f"[yellow]⚠ Blocked {blocked} deviation{plural} (rule disabled)[/yellow]"
        )

    console.print(
        Panel(
            "\n".join(content_parts),
            title="[bold cyan]Deviations[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        )
    )


def display_planning_questions(num_questions: int) -> None:
    """Display that planning questions were asked.

    Args:
        num_questions: Number of questions asked
    """
    content = (
        f"[cyan]Asked {num_questions} clarifying question{'s' if num_questions != 1 else ''}[/cyan]"
    )
    console.print(Panel(content, border_style="cyan", padding=(0, 1)))


class VerbosityLevel:
    """Verbosity levels for output control."""

    QUIET = 0  # Errors and final status only
    NORMAL = 1  # Standard output (default)
    VERBOSE = 2  # Extra detail


# Global verbosity setting (can be set via CLI)
_verbosity = VerbosityLevel.NORMAL


def set_verbosity(level: int) -> None:
    """Set global verbosity level.

    Args:
        level: Verbosity level (0=quiet, 1=normal, 2=verbose)
    """
    global _verbosity
    _verbosity = level


def get_verbosity() -> int:
    """Get current verbosity level.

    Returns:
        Current verbosity level
    """
    return _verbosity


def should_display(min_level: int = VerbosityLevel.NORMAL) -> bool:
    """Check if output should be displayed at current verbosity.

    Args:
        min_level: Minimum verbosity level required

    Returns:
        True if should display
    """
    return _verbosity >= min_level
