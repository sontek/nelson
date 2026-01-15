"""CLI entry point for nelson-prd.

This module provides the Click-based command-line interface for nelson-prd,
enabling multi-task PRD orchestration with blocking, resume, and status features.
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from nelson.prd_orchestrator import PRDOrchestrator
from nelson.prd_task_state import TaskStatus

console = Console()


@click.command()
@click.argument(
    "prd_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--status",
    "show_status",
    is_flag=True,
    help="Show status of all tasks without executing",
)
@click.option(
    "--filter",
    "status_filter",
    type=click.Choice(
        ["pending", "in-progress", "blocked", "completed", "failed", "active"],
        case_sensitive=False,
    ),
    help="Filter tasks by status (active = pending + in-progress + blocked)",
)
@click.option(
    "--block",
    "block_task_id",
    type=str,
    help="Block a task with given ID (use with --reason)",
)
@click.option(
    "--reason",
    type=str,
    help="Blocking reason (required with --block)",
)
@click.option(
    "--unblock",
    "unblock_task_id",
    type=str,
    help="Unblock a task with given ID (optionally use with --context)",
)
@click.option(
    "--context",
    type=str,
    help="Resume context when unblocking (optional with --unblock)",
)
@click.option(
    "--resume-task",
    "resume_task_id",
    type=str,
    help="Resume a specific task by ID",
)
@click.option(
    "--task-info",
    "task_info_id",
    type=str,
    help="Show detailed information about a specific task",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview tasks without executing",
)
@click.option(
    "--resume",
    "resume_from_last",
    is_flag=True,
    help="Continue from last incomplete task",
)
@click.option(
    "--stop-on-failure",
    is_flag=True,
    help="Stop execution on first task failure",
)
@click.option(
    "--prd-dir",
    type=click.Path(path_type=Path),
    help="Override .nelson/prd directory location",
)
@click.option(
    "--nelson-args",
    type=str,
    help="Additional arguments to pass to Nelson CLI (space-separated)",
)
def main(
    prd_file: Path,
    path: Path | None,
    show_status: bool,
    status_filter: str | None,
    block_task_id: str | None,
    reason: str | None,
    unblock_task_id: str | None,
    context: str | None,
    resume_task_id: str | None,
    task_info_id: str | None,
    dry_run: bool,
    resume_from_last: bool,
    stop_on_failure: bool,
    prd_dir: Path | None,
    nelson_args: str | None,
) -> None:
    """Execute tasks from a PRD (Product Requirements Document) file.

    PRD_FILE should be a markdown file with tasks organized by priority.

    PATH is an optional target repository directory. If not provided, nelson-prd
    works in the current directory. When provided, all git operations and
    Nelson commands execute in the target directory.

    \b
    ## High Priority
    - [ ] PRD-001 Add user authentication
    - [~] PRD-002 Create user profile (in progress)
    - [x] PRD-003 Add payment integration
    - [!] PRD-004 Add email notifications (blocked: waiting for API)

    \b
    Status indicators:
      [ ] - Pending (not started)
      [~] - In progress
      [x] - Completed
      [!] - Blocked

    \b
    Examples:
      # Execute all pending tasks
      nelson-prd requirements.md

      # Target a specific repository
      nelson-prd requirements.md /path/to/repo

      # Show status
      nelson-prd --status requirements.md

      # Show status for another repo
      nelson-prd --status requirements.md /path/to/repo

      # Show only non-completed tasks (pending, in-progress, blocked)
      nelson-prd --status --filter active requirements.md

      # Show only pending tasks
      nelson-prd --status --filter pending requirements.md

      # Block a task
      nelson-prd --block PRD-003 --reason "Waiting for API keys" requirements.md

      # Unblock with context
      nelson-prd --unblock PRD-003 --context "Keys added to .env" requirements.md

      # Resume specific task
      nelson-prd --resume-task PRD-003 requirements.md

      # Get task details
      nelson-prd --task-info PRD-001 requirements.md

      # Pass arguments to Nelson
      nelson-prd --nelson-args "--model opus --max-iterations 100" requirements.md
    """
    try:
        # Validate and resolve target path if provided
        target_path: Path | None = None
        if path is not None:
            # Resolve to absolute path
            target_path = path.resolve()

            # Verify it's a git repository
            from nelson.git_utils import is_git_repo
            if not is_git_repo(target_path):
                click.echo(
                    f"Error: The specified path is not a git repository: {target_path}\n"
                    "nelson-prd requires a git repository to track changes.",
                    err=True,
                )
                sys.exit(1)

        # Initialize orchestrator
        if target_path is not None:
            orchestrator = PRDOrchestrator(prd_file, prd_dir, target_path)
        else:
            orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Parse nelson_args string into list
        parsed_nelson_args: list[str] | None = None
        if nelson_args:
            parsed_nelson_args = nelson_args.split()

        # Handle status command
        if show_status:
            _show_status(orchestrator, status_filter)
            return

        # Handle block command
        if block_task_id:
            if not reason:
                click.echo("Error: --reason is required when using --block", err=True)
                sys.exit(1)
            success = orchestrator.block_task(block_task_id, reason)
            sys.exit(0 if success else 1)

        # Handle unblock command
        if unblock_task_id:
            success = orchestrator.unblock_task(unblock_task_id, context)
            sys.exit(0 if success else 1)

        # Handle task-info command
        if task_info_id:
            _show_task_info(orchestrator, task_info_id)
            return

        # Handle resume-task command
        if resume_task_id:
            success = orchestrator.resume_task(resume_task_id, parsed_nelson_args)
            sys.exit(0 if success else 1)

        # Handle dry-run
        if dry_run:
            _show_dry_run(orchestrator)
            return

        # Handle resume (continue from last incomplete)
        if resume_from_last:
            # Get first in-progress or pending task
            next_task = orchestrator.get_next_pending_task()
            if next_task is None:
                click.echo("No pending tasks to resume")
                return
            task_id, task_text, priority = next_task
            click.echo(f"Resuming from task: {task_id}")
            # Fall through to normal execution

        # Execute all pending tasks
        click.echo(f"Starting PRD execution: {prd_file}")
        click.echo(f"PRD directory: {orchestrator.prd_dir}\n")

        results = orchestrator.execute_all_pending(
            nelson_args=parsed_nelson_args, stop_on_failure=stop_on_failure
        )

        # Print summary
        _print_execution_summary(results, orchestrator)

        # Exit with appropriate code based on results
        failed = sum(1 for success in results.values() if not success)
        sys.exit(0 if failed == 0 else 1)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n\nExecution interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def _show_status(orchestrator: PRDOrchestrator, status_filter: str | None = None) -> None:
    """Display status of all tasks using rich formatting.

    Args:
        orchestrator: PRD orchestrator instance
        status_filter: Optional filter by status (pending, in-progress, blocked, completed, failed, active)
    """
    summary = orchestrator.get_status_summary()

    # Filter tasks if requested
    filtered_tasks = summary["tasks"]
    if status_filter:
        status_filter_lower = status_filter.lower()
        if status_filter_lower == "active":
            # Active = pending + in-progress + blocked (not completed)
            filtered_tasks = [
                task for task in summary["tasks"]
                if task["status"] in [
                    TaskStatus.PENDING.value,
                    TaskStatus.IN_PROGRESS.value,
                    TaskStatus.BLOCKED.value,
                ]
            ]
        else:
            # Map filter string to TaskStatus value
            status_map = {
                "pending": TaskStatus.PENDING.value,
                "in-progress": TaskStatus.IN_PROGRESS.value,
                "blocked": TaskStatus.BLOCKED.value,
                "completed": TaskStatus.COMPLETED.value,
                "failed": TaskStatus.FAILED.value,
            }
            target_status = status_map.get(status_filter_lower)
            if target_status:
                filtered_tasks = [
                    task for task in summary["tasks"]
                    if task["status"] == target_status
                ]

    # Create header panel
    console.print()
    header_text = (
        f"[bold cyan]Total:[/] {summary['total_tasks']} tasks | "
        f"[bold green]✓ Completed:[/] {summary['completed']} | "
        f"[bold yellow]~ In Progress:[/] {summary['in_progress']} | "
        f"[bold red]! Blocked:[/] {summary['blocked']} | "
        f"[bold]○ Pending:[/] {summary['pending']}"
    )
    if summary['failed'] > 0:
        header_text += f" | [bold red]✗ Failed:[/] {summary['failed']}"
    header_text += f"\n[bold]Total Cost:[/] ${summary['total_cost']:.2f}"

    # Add filter info if active
    if status_filter:
        header_text += f"\n[dim]Filtered by: {status_filter} ({len(filtered_tasks)} tasks shown)[/dim]"

    title = f"[bold]PRD Status: {summary['prd_file']}[/bold]"
    console.print(
        Panel(
            header_text,
            title=title,
            border_style="cyan",
        )
    )

    # Check for task text changes and warn
    text_changes = orchestrator.check_task_text_changes()
    if text_changes:
        warning_lines = ["[bold yellow]⚠️  Task text changes detected:[/bold yellow]\n"]
        for change in text_changes:
            warning_lines.append(f"[bold]{change['task_id']}[/bold]")
            warning_lines.append(f"  [dim]Original:[/dim] {change['original_text']}")
            warning_lines.append(f"  [dim]Current:[/dim]  {change['current_text']}")
            warning_lines.append("")

        warning_lines.append(
            "[dim]Task descriptions have been modified. This may affect "
            "branch names and task tracking.[/dim]"
        )
        warning_lines.append(
            "[dim]Consider reviewing these changes or creating new task IDs "
            "if the task scope has changed significantly.[/dim]"
        )

        console.print(
            Panel(
                "\n".join(warning_lines),
                border_style="yellow",
                title="[bold yellow]Warning[/bold yellow]",
            )
        )

    # Create tasks table
    table_title = "Tasks"
    if status_filter:
        table_title = f"Tasks (filtered: {status_filter})"

    table = Table(
        title=table_title,
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        title_style="bold",
    )
    table.add_column("Status", style="bold", width=6)
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Description", style="white")
    table.add_column("Details", style="dim", width=40)

    for task_dict in filtered_tasks:
        # Extract fields from dict
        task_id = task_dict["task_id"]
        task_text = task_dict["task_text"]
        status_str = task_dict["status"]
        branch = task_dict.get("branch")
        blocking_reason = task_dict.get("blocking_reason")
        cost_usd = task_dict.get("cost_usd", 0.0)
        iterations = task_dict.get("iterations", 0)
        phase = task_dict.get("phase")
        phase_name = task_dict.get("phase_name")

        # Convert status string to TaskStatus enum
        status = TaskStatus(status_str)
        status_display = _get_status_display(status)

        # Build details column
        details = []
        if branch:
            details.append(f"Branch: {branch}")
        if status == TaskStatus.BLOCKED and blocking_reason:
            details.append(f"[red]Blocked: {blocking_reason}[/red]")
        if cost_usd > 0:
            details.append(f"Cost: ${cost_usd:.2f}")
        if iterations > 0:
            details.append(f"Iterations: {iterations}")
        if phase:
            details.append(f"Phase: {phase} ({phase_name})")

        details_text = "\n".join(details) if details else "-"

        table.add_row(status_display, task_id, task_text, details_text)

    console.print(table)
    console.print()


def _show_task_info(orchestrator: PRDOrchestrator, task_id: str) -> None:
    """Display detailed information about a task using rich formatting."""
    info = orchestrator.get_task_info(task_id)

    if info is None:
        console.print(f"[red]Error: Task not found: {task_id}[/red]", style="bold")
        sys.exit(1)

    # Create info table
    table = Table(
        title=f"Task Details: {task_id}",
        show_header=False,
        border_style="cyan",
        title_style="bold cyan",
        box=None,
        padding=(0, 2),
    )
    table.add_column("Field", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    # Add basic info
    status = TaskStatus(info["status"])
    status_display = _get_status_display(status)

    table.add_row("Description", info["task_text"])
    table.add_row("Status", status_display)
    table.add_row("Priority", info["priority"].upper())

    if info["branch"]:
        table.add_row("Branch", info["branch"])
    if info["nelson_run_id"]:
        table.add_row("Nelson Run ID", info["nelson_run_id"])

    table.add_row("Cost", f"${info['cost_usd']:.2f}")
    table.add_row("Iterations", str(info["iterations"]))

    if info["phase"]:
        table.add_row("Phase", f"{info['phase']} ({info['phase_name']})")

    # Timestamps
    if info["started_at"]:
        table.add_row("Started", info["started_at"])
    if info["completed_at"]:
        table.add_row("Completed", info["completed_at"])
    if info["blocked_at"]:
        table.add_row("Blocked", info["blocked_at"])

    console.print()
    console.print(table)

    # Additional context sections
    if info["blocking_reason"]:
        console.print()
        console.print(
            Panel(
                info["blocking_reason"],
                title="[bold red]Blocking Reason[/bold red]",
                border_style="red",
            )
        )

    if info["resume_context"]:
        console.print()
        console.print(
            Panel(
                info["resume_context"],
                title="[bold yellow]Resume Context[/bold yellow]",
                border_style="yellow",
            )
        )

    console.print()


def _show_dry_run(orchestrator: PRDOrchestrator) -> None:
    """Display tasks that would be executed without running them."""
    click.echo(f"\nDry run for: {orchestrator.prd_file}")
    click.echo(f"{'='*60}\n")

    pending_tasks = []

    # Get pending tasks in priority order
    for priority in ["high", "medium", "low"]:
        tasks = [
            t
            for t in orchestrator.tasks
            if t.priority == priority
            and t.status.value == " "  # PRDTaskStatus.PENDING
        ]
        pending_tasks.extend(tasks)

    if not pending_tasks:
        click.echo("No pending tasks to execute")
        return

    click.echo(f"Would execute {len(pending_tasks)} tasks:\n")

    for i, task in enumerate(pending_tasks, 1):
        click.echo(f"{i}. {task.task_id}: {task.task_text}")
        click.echo(f"   Priority: {task.priority}")
        click.echo()


def _print_execution_summary(
    results: dict[str, bool], orchestrator: PRDOrchestrator
) -> None:
    """Print summary of execution results using rich formatting."""
    if not results:
        console.print("[yellow]No tasks were executed[/yellow]")
        return

    summary = orchestrator.get_status_summary()

    succeeded = sum(1 for success in results.values() if success)
    failed = sum(1 for success in results.values() if not success)

    # Build summary text
    summary_text = (
        f"[bold]Tasks executed:[/bold] {len(results)}\n"
        f"  [green]Succeeded:[/green] {succeeded}"
    )
    if failed > 0:
        summary_text += f"\n  [red]Failed:[/red] {failed}"

    summary_text += f"\n\n[bold]Total cost:[/bold] ${summary['total_cost']:.2f}"
    summary_text += "\n\n[bold]Overall progress:[/bold]"
    summary_text += (
        f"\n  [green]Completed:[/green] {summary['completed']}/{summary['total_tasks']}"
    )
    summary_text += f"\n  [bold]Pending:[/bold] {summary['pending']}"
    if summary['blocked'] > 0:
        summary_text += f"\n  [yellow]Blocked:[/yellow] {summary['blocked']}"
    if summary['failed'] > 0:
        summary_text += f"\n  [red]Failed:[/red] {summary['failed']}"

    console.print()
    console.print(
        Panel(
            summary_text,
            title="[bold]Execution Summary[/bold]",
            border_style="green" if failed == 0 else "yellow",
        )
    )
    console.print()


def _get_status_icon(status: TaskStatus) -> str:
    """Get visual icon for task status."""
    if status == TaskStatus.COMPLETED:
        return "✓"
    elif status == TaskStatus.IN_PROGRESS:
        return "~"
    elif status == TaskStatus.BLOCKED:
        return "!"
    elif status == TaskStatus.FAILED:
        return "✗"
    else:  # PENDING
        return "○"


def _get_status_display(status: TaskStatus) -> str:
    """Get colored status display for task status."""
    if status == TaskStatus.COMPLETED:
        return "[green]✓[/green]"
    elif status == TaskStatus.IN_PROGRESS:
        return "[yellow]~[/yellow]"
    elif status == TaskStatus.BLOCKED:
        return "[red]![/red]"
    elif status == TaskStatus.FAILED:
        return "[red]✗[/red]"
    else:  # PENDING
        return "[dim]○[/dim]"


if __name__ == "__main__":
    main()
