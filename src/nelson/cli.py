"""CLI entry point for nelson.

This module provides the Click-based command-line interface for Nelson,
matching the bash implementation's interface while adding rich formatting.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click

from nelson.config import NelsonConfig
from nelson.logging_config import get_logger
from nelson.phases import Phase
from nelson.providers.claude import ClaudeProvider
from nelson.state import NelsonState
from nelson.workflow import WorkflowError, WorkflowOrchestrator

logger = get_logger()


@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--resume",
    "resume_path",
    type=click.Path(exists=True, path_type=Path),
    is_flag=False,
    flag_value="",  # Empty string means "last run"
    default=None,
    help="Resume from last checkpoint or specific run directory",
)
@click.option(
    "--max-iterations",
    type=int,
    envvar="NELSON_MAX_ITERATIONS",
    help="Max complete cycles through all 6 phases (env: NELSON_MAX_ITERATIONS)",
)
@click.option(
    "--cost-limit",
    type=float,
    envvar="NELSON_COST_LIMIT",
    help="Max cost in USD (env: NELSON_COST_LIMIT)",
)
@click.option(
    "--model",
    envvar="NELSON_MODEL",
    help="Model to use for all phases (env: NELSON_MODEL). Options: opus, sonnet, haiku",
)
@click.option(
    "--plan-model",
    envvar="NELSON_PLAN_MODEL",
    help="Model for Phase 1 planning (env: NELSON_PLAN_MODEL). Defaults to --model",
)
@click.option(
    "--review-model",
    envvar="NELSON_REVIEW_MODEL",
    help="Model for Phase 3 & 5 reviews (env: NELSON_REVIEW_MODEL). Defaults to --model",
)
@click.option(
    "--claude-command",
    envvar="NELSON_CLAUDE_COMMAND",
    help='Claude command (env: NELSON_CLAUDE_COMMAND). Options: "claude", "claude-jail", or path',
)
@click.option(
    "--auto-approve-push",
    is_flag=True,
    envvar="NELSON_AUTO_APPROVE_PUSH",
    help="Skip push approval prompt (env: NELSON_AUTO_APPROVE_PUSH)",
)
@click.version_option(version="0.1.0", prog_name="nelson")
def main(
    prompt: str | None,
    resume_path: Path | str | None,
    max_iterations: int | None,
    cost_limit: float | None,
    model: str | None,
    plan_model: str | None,
    review_model: str | None,
    claude_command: str | None,
    auto_approve_push: bool,
) -> None:
    """Nelson: AI orchestration CLI for autonomous development workflows.

    PROMPT can be:
      - A string: nelson "implement feature X"
      - A file path: nelson tasks/task1.md
      - Stdin: echo "task" | nelson

    \b
    Examples:
      nelson "Add user authentication"
      nelson docs/implementation.md
      nelson --resume                                    # Resume from last run
      nelson --resume .nelson/runs/nelson-20260112-120125  # Resume from specific run
      nelson --max-iterations 30 "complex task"
      nelson --claude-command claude "use native claude"
      nelson --model opus "complex planning task"
      nelson --model haiku "simple refactoring"
      nelson --plan-model opus "use opus for planning phase"

    \b
    Environment Variables:
      NELSON_MAX_ITERATIONS      Max complete cycles through all 6 phases (default: 50)
                                 One cycle = PLAN → IMPLEMENT → REVIEW → TEST → FINAL-REVIEW → COMMIT
      NELSON_COST_LIMIT          Max cost in USD (default: 10.00)
      NELSON_AUTO_APPROVE_PUSH   Skip push approval (default: false)
      NELSON_CLAUDE_COMMAND      Claude command (default: claude-jail)
      NELSON_MODEL               Model for all phases (default: sonnet)
      NELSON_PLAN_MODEL          Model for Phase 1 (default: NELSON_MODEL)
      NELSON_REVIEW_MODEL        Model for Phase 3 & 5 (default: NELSON_MODEL)
    """
    # Validate that we have either a prompt or --resume
    if not prompt and resume_path is None:
        # Check if we have stdin input
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
            if not prompt:
                logger.error("No prompt provided via stdin, file, or argument")
                raise click.UsageError(
                    "PROMPT is required unless using --resume. "
                    "Provide a prompt as an argument, file path, or via stdin."
                )
        else:
            logger.error("No prompt or --resume flag provided")
            raise click.UsageError(
                "PROMPT is required unless using --resume. "
                "Use 'nelson --help' for usage information."
            )

    # Get prompt from file if it's a path
    if prompt and Path(prompt).is_file():
        logger.info(f"Reading prompt from file: {prompt}")
        prompt = Path(prompt).read_text().strip()

    # Handle resume mode
    if resume_path is not None:
        if resume_path == "":
            # --resume flag without value: resume from last run
            _resume_from_last()
        else:
            # --resume with specific path
            _resume_from_path(Path(resume_path))
        return

    # Build configuration with CLI overrides
    config = _build_config(
        max_iterations=max_iterations,
        cost_limit=cost_limit,
        model=model,
        plan_model=plan_model,
        review_model=review_model,
        claude_command=claude_command,
        auto_approve_push=auto_approve_push,
    )

    # Run the workflow
    logger.info("Starting Nelson workflow")
    # Safely truncate prompt for display
    if prompt:
        prompt_display = prompt[:100] + ("..." if len(prompt) > 100 else "")
        logger.info(f"Prompt: {prompt_display}")
    logger.info(f"Model: {config.model}")
    logger.info(f"Max iterations: {config.max_iterations}")
    logger.info(f"Cost limit: ${config.cost_limit:.2f}")

    try:
        _execute_workflow(prompt, config)
    except WorkflowError as e:
        logger.error(f"Workflow failed: {e}")
        raise click.Abort()
    except KeyboardInterrupt:
        logger.warning("Workflow interrupted by user")
        raise click.Abort()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


def _execute_workflow(prompt: str, config: NelsonConfig) -> None:
    """Execute the main workflow with proper initialization and error handling.

    Args:
        prompt: User's task prompt
        config: Nelson configuration

    Raises:
        WorkflowError: If workflow fails
    """
    # Initialize provider
    claude_command = (
        str(config.claude_command_path)
        if config.claude_command_path
        else config.claude_command
    )
    provider = ClaudeProvider(claude_command=claude_command)

    # Check provider availability
    if not provider.is_available():
        logger.error(f"Claude command not available: {claude_command}")
        raise WorkflowError(f"Claude command not found or not executable: {claude_command}")

    logger.info(f"Using Claude command: {claude_command}")

    # Get starting commit for audit trail
    try:
        starting_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        logger.warning("Not in a git repository - starting_commit will be empty")
        starting_commit = ""

    # Create run directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = config.runs_dir / f"ralph-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Run directory: {run_dir}")

    # Initialize files
    decisions_file = run_dir / "decisions.md"
    state_file = run_dir / "state.json"

    # Initialize decisions log
    decisions_file.write_text("# Nelson Implementation - Decisions Log\n\n")

    # Create initial state
    state = NelsonState(
        cycle_iterations=0,
        total_iterations=0,
        phase_iterations=0,
        cost_usd=0.0,
        prompt=prompt,
        starting_commit=starting_commit,
        current_phase=Phase.PLAN.value,
        phase_name=Phase.PLAN.name_str,
    )

    # Save initial state
    state.save(state_file)

    # Create workflow orchestrator
    orchestrator = WorkflowOrchestrator(
        config=config,
        state=state,
        provider=provider,
        run_dir=run_dir,
    )

    # Run the workflow
    orchestrator.run(prompt)


def _build_config(
    max_iterations: int | None,
    cost_limit: float | None,
    model: str | None,
    plan_model: str | None,
    review_model: str | None,
    claude_command: str | None,
    auto_approve_push: bool,
) -> NelsonConfig:
    """Build configuration with CLI overrides."""
    # Load base config from environment
    config = NelsonConfig.from_environment()

    # Determine final values with CLI overrides
    final_max_iterations = max_iterations if max_iterations is not None else config.max_iterations
    final_max_iterations_explicit = max_iterations is not None or config.max_iterations_explicit
    final_cost_limit = cost_limit if cost_limit is not None else config.cost_limit
    final_claude_command = claude_command if claude_command is not None else config.claude_command
    final_model = model if model is not None else config.model
    final_auto_approve_push = auto_approve_push or config.auto_approve_push

    # Re-resolve claude command path if it changed
    final_claude_command_path: Path | None
    if claude_command is not None:
        final_claude_command_path = NelsonConfig._resolve_claude_path(claude_command, None)
    else:
        final_claude_command_path = config.claude_command_path

    # Handle model cascading: plan_model and review_model default to model
    final_plan_model = plan_model if plan_model is not None else (
        final_model if model is not None else config.plan_model
    )
    final_review_model = review_model if review_model is not None else (
        final_model if model is not None else config.review_model
    )

    return NelsonConfig(
        max_iterations=final_max_iterations,
        max_iterations_explicit=final_max_iterations_explicit,
        cost_limit=final_cost_limit,
        nelson_dir=config.nelson_dir,
        audit_dir=config.audit_dir,
        runs_dir=config.runs_dir,
        claude_command=final_claude_command,
        claude_command_path=final_claude_command_path,
        model=final_model,
        plan_model=final_plan_model,
        review_model=final_review_model,
        auto_approve_push=final_auto_approve_push,
    )


def _resume_from_last() -> None:
    """Resume from the most recent run."""
    logger.info("Resuming from last checkpoint...")

    # Load base config to get runs_dir
    config = NelsonConfig.from_environment()

    # Find most recent run directory
    if not config.runs_dir.exists():
        logger.error(f"No runs directory found at: {config.runs_dir}")
        raise click.Abort()

    run_dirs = sorted(
        [d for d in config.runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )

    if not run_dirs:
        logger.error("No previous runs found to resume from")
        raise click.Abort()

    last_run = run_dirs[0]
    logger.info(f"Found last run: {last_run.name}")

    _resume_from_path(last_run)


def _resume_from_path(run_dir: Path) -> None:
    """Resume from a specific run directory.

    Args:
        run_dir: Path to run directory containing state.json

    Raises:
        click.Abort: If validation fails or workflow error occurs
    """
    logger.info(f"Resuming from run: {run_dir}")

    # Validate run directory and required files
    state_file = run_dir / "state.json"
    if not state_file.exists():
        logger.error(f"No state file found at: {state_file}")
        raise click.Abort()

    # Load state from the run directory
    try:
        state = NelsonState.load(state_file)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to load state file: {e}")
        raise click.Abort()

    logger.info(f"Loaded state: Phase {state.current_phase} ({state.phase_name})")
    logger.info(f"Completed cycles: {state.cycle_iterations}")
    logger.info(f"Total iterations: {state.total_iterations}")
    logger.info(f"Current cost: ${state.cost_usd:.2f}")

    # Load base config from environment
    config = NelsonConfig.from_environment()

    # Check if we're at or past the cycle limit
    if state.cycle_iterations >= config.max_iterations:
        if not config.max_iterations_explicit:
            # User didn't explicitly set limit - auto-extend by 10 cycles
            old_limit = config.max_iterations
            new_limit = state.cycle_iterations + 10
            logger.warning(
                f"Current run has {state.cycle_iterations} complete cycles, "
                f"at limit of {old_limit}"
            )
            logger.info(f"Auto-extending cycle limit to {new_limit}")
            logger.info(
                "To set a custom limit, use: NELSON_MAX_ITERATIONS=<number> nelson --resume"
            )

            # Update config with new limit
            config = NelsonConfig(
                max_iterations=new_limit,
                max_iterations_explicit=False,
                cost_limit=config.cost_limit,
                nelson_dir=config.nelson_dir,
                audit_dir=config.audit_dir,
                runs_dir=config.runs_dir,
                claude_command=config.claude_command,
                claude_command_path=config.claude_command_path,
                model=config.model,
                plan_model=config.plan_model,
                review_model=config.review_model,
                auto_approve_push=config.auto_approve_push,
            )
        else:
            # User explicitly set limit but it's still too low
            logger.error(
                f"Current run has {state.cycle_iterations} complete cycles, "
                f"but limit is {config.max_iterations}"
            )
            logger.error(
                f"Increase the limit to continue: "
                f"NELSON_MAX_ITERATIONS={state.cycle_iterations + 10} nelson --resume"
            )
            raise click.Abort()
    elif state.cycle_iterations > config.max_iterations - 3:
        # Within 3 cycles of the limit - warn them
        remaining = config.max_iterations - state.cycle_iterations
        logger.warning(
            f"Approaching cycle limit: {state.cycle_iterations}/{config.max_iterations} "
            f"({remaining} remaining)"
        )

    # Initialize provider
    claude_command = (
        str(config.claude_command_path)
        if config.claude_command_path
        else config.claude_command
    )
    provider = ClaudeProvider(claude_command=claude_command)

    # Check provider availability
    if not provider.is_available():
        logger.error(f"Claude command not available: {claude_command}")
        raise WorkflowError(f"Claude command not found or not executable: {claude_command}")

    logger.info(f"Using Claude command: {claude_command}")

    # Create workflow orchestrator with loaded state
    orchestrator = WorkflowOrchestrator(
        config=config,
        state=state,
        provider=provider,
        run_dir=run_dir,
    )

    # Resume the workflow from where it left off
    try:
        orchestrator.run(state.prompt)
    except WorkflowError as e:
        logger.error(f"Workflow failed: {e}")
        raise click.Abort()
    except KeyboardInterrupt:
        logger.warning("Workflow interrupted by user")
        raise click.Abort()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
