"""CLI entry point for nelson-prd.

This module provides the Click-based command-line interface for nelson-prd,
enabling multi-task PRD orchestration with blocking, resume, and status features.
"""

import sys
from pathlib import Path

import click

from nelson.prd_orchestrator import PRDOrchestrator
from nelson.prd_task_state import TaskStatus


@click.command()
@click.argument(
    "prd_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--status",
    "show_status",
    is_flag=True,
    help="Show status of all tasks without executing",
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
    show_status: bool,
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

    PRD_FILE should be a markdown file with tasks organized by priority:

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

      # Show status
      nelson-prd --status requirements.md

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
        # Initialize orchestrator
        orchestrator = PRDOrchestrator(prd_file, prd_dir)

        # Parse nelson_args string into list
        parsed_nelson_args: list[str] | None = None
        if nelson_args:
            parsed_nelson_args = nelson_args.split()

        # Handle status command
        if show_status:
            _show_status(orchestrator)
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


def _show_status(orchestrator: PRDOrchestrator) -> None:
    """Display status of all tasks."""
    summary = orchestrator.get_status_summary()

    click.echo(f"\nPRD Status: {summary['prd_file']}")
    click.echo(f"{'='*60}")
    click.echo(
        f"Total: {summary['total_tasks']} tasks | "
        f"Completed: {summary['completed']} | "
        f"In Progress: {summary['in_progress']} | "
        f"Blocked: {summary['blocked']} | "
        f"Pending: {summary['pending']}"
    )
    if summary['failed'] > 0:
        click.echo(f"Failed: {summary['failed']}")
    click.echo(f"Total Cost: ${summary['total_cost']:.2f}")
    click.echo(f"{'='*60}\n")

    # Print task details
    click.echo("Tasks:\n")

    for task_id, task_state in summary["tasks"].items():
        status_icon = _get_status_icon(task_state.status)
        click.echo(f"  {status_icon} {task_id}: {task_state.task_text}")

        if task_state.branch:
            click.echo(f"     Branch: {task_state.branch}")
        if task_state.status == TaskStatus.BLOCKED and task_state.blocking_reason:
            click.echo(f"     Blocked: {task_state.blocking_reason}")
        if task_state.cost_usd > 0:
            click.echo(f"     Cost: ${task_state.cost_usd:.2f}")
        if task_state.iterations > 0:
            click.echo(f"     Iterations: {task_state.iterations}")
        if task_state.phase:
            click.echo(f"     Phase: {task_state.phase} ({task_state.phase_name})")

        click.echo()


def _show_task_info(orchestrator: PRDOrchestrator, task_id: str) -> None:
    """Display detailed information about a task."""
    info = orchestrator.get_task_info(task_id)

    if info is None:
        click.echo(f"Error: Task not found: {task_id}", err=True)
        sys.exit(1)

    click.echo(f"\nTask Details: {task_id}")
    click.echo(f"{'='*60}")
    click.echo(f"Description: {info['task_text']}")
    click.echo(f"Status: {info['status']}")
    click.echo(f"Priority: {info['priority']}")

    if info["branch"]:
        click.echo(f"Branch: {info['branch']}")
    if info["nelson_run_id"]:
        click.echo(f"Nelson Run ID: {info['nelson_run_id']}")

    click.echo(f"\nCost: ${info['cost_usd']:.2f}")
    click.echo(f"Iterations: {info['iterations']}")

    if info["phase"]:
        click.echo(f"Phase: {info['phase']} ({info['phase_name']})")

    if info["started_at"]:
        click.echo(f"\nStarted: {info['started_at']}")
    if info["completed_at"]:
        click.echo(f"Completed: {info['completed_at']}")
    if info["blocked_at"]:
        click.echo(f"Blocked: {info['blocked_at']}")

    if info["blocking_reason"]:
        click.echo("\nBlocking Reason:")
        click.echo(f"  {info['blocking_reason']}")

    if info["resume_context"]:
        click.echo("\nResume Context:")
        click.echo(f"  {info['resume_context']}")

    click.echo()


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
    """Print summary of execution results."""
    if not results:
        click.echo("No tasks were executed")
        return

    summary = orchestrator.get_status_summary()

    click.echo(f"\n{'='*60}")
    click.echo("Execution Summary")
    click.echo(f"{'='*60}")

    succeeded = sum(1 for success in results.values() if success)
    failed = sum(1 for success in results.values() if not success)

    click.echo(f"Tasks executed: {len(results)}")
    click.echo(f"  Succeeded: {succeeded}")
    if failed > 0:
        click.echo(f"  Failed: {failed}")

    click.echo(f"\nTotal cost: ${summary['total_cost']:.2f}")
    click.echo("\nOverall progress:")
    click.echo(f"  Completed: {summary['completed']}/{summary['total_tasks']}")
    click.echo(f"  Pending: {summary['pending']}")
    if summary['blocked'] > 0:
        click.echo(f"  Blocked: {summary['blocked']}")
    if summary['failed'] > 0:
        click.echo(f"  Failed: {summary['failed']}")
    click.echo(f"{'='*60}\n")


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


if __name__ == "__main__":
    main()
