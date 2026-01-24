"""Workflow orchestrator for Nelson.

This module implements the main execution loop that coordinates:
- Phase transitions
- Provider (Claude) invocations
- Circuit breaker detection
- State management
- Decision logging
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.panel import Panel

from nelson.config import NelsonConfig
from nelson.decisions_log import (
    extract_recent_work,
    should_compact,
    write_progress_checkpoint,
)
from nelson.depth import DepthMode
from nelson.interaction import UserInteraction
from nelson.logging_config import get_logger
from nelson.phases import Phase
from nelson.plan_validation import log_validation_warnings
from nelson.progress_monitor import ProgressMonitor
from nelson.prompts import (
    build_full_prompt,
    build_loop_context,
    get_phase_prompt,
    get_system_prompt,
)
from nelson.providers.base import AIProvider, ProviderError
from nelson.state import NelsonState
from nelson.transitions import determine_next_phase, has_unchecked_tasks, should_transition_phase

logger = get_logger()


class CircuitBreakerResult(Enum):
    """Result of circuit breaker check."""

    OK = "ok"  # No issues, continue
    EXIT_SIGNAL = "exit_signal"  # Clean exit requested
    TRIGGERED = "triggered"  # Circuit breaker activated
    BLOCKED = "blocked"  # Task blocked on external dependency
    COMPLETE = "complete"  # All tasks complete, no more work to do


class WorkflowOrchestrator:
    """Main workflow orchestrator that coordinates Nelson's execution loop.

    The orchestrator follows the bash script's approach:
    1. Load state and context from previous iteration
    2. Build prompt with phase-specific instructions
    3. Call AI provider (Claude)
    4. Parse status block from response
    5. Check circuit breakers (stagnation, repeated errors, exit signal)
    6. Determine if phase transition is needed
    7. Update state and log decisions
    8. Repeat until EXIT_SIGNAL or circuit breaker triggers

    Attributes:
        config: Nelson configuration
        state: Current execution state
        provider: AI provider (Claude)
        run_dir: Directory for current run
    """

    def __init__(
        self,
        config: NelsonConfig,
        state: NelsonState,
        provider: AIProvider,
        run_dir: Path,
    ) -> None:
        """Initialize workflow orchestrator.

        Args:
            config: Nelson configuration
            state: Initial state
            provider: AI provider instance
            run_dir: Run directory for plan.md, decisions.md, etc.
        """
        self.config = config
        self.state = state
        self.provider = provider
        self.run_dir = run_dir

        # User interaction handler
        self.interaction = UserInteraction(config.interaction)

        # File paths - all run-specific files live in run_dir
        self.state_file = run_dir / "state.json"
        self.plan_file = run_dir / "plan.md"
        self.decisions_file = run_dir / "decisions.md"
        self.last_output_file = run_dir / "last_output.txt"

        # Check if comprehensive mode is enabled
        self._comprehensive = config.depth.mode == DepthMode.COMPREHENSIVE

    @property
    def comprehensive(self) -> bool:
        """Check if comprehensive mode (8 phases) is enabled."""
        return self._comprehensive

    def run(self, prompt: str) -> None:
        """Run the main workflow loop.

        Args:
            prompt: Original user prompt/task

        Raises:
            WorkflowError: If workflow fails due to limits or errors
        """
        logger.info("Starting Nelson autonomous workflow...")
        logger.info("")

        # Display prompt with rich Panel
        prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        logger.console.print(
            Panel(
                prompt_preview,
                title="[bold blue]Task",
                border_style="blue",
                padding=(1, 2),
            )
        )
        logger.console.print("")

        # Display system prompt summary at startup
        system_prompt = get_system_prompt(self.decisions_file)
        system_lines = system_prompt.split("\n")[:5]
        system_summary = (
            "\n".join(system_lines) + "\n\n[dim](Full system prompt sent to Claude)[/dim]"
        )
        logger.console.print(
            Panel(
                system_summary,
                title="[bold cyan]System Prompt",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        logger.console.print("")

        # Main loop - continues until EXIT_SIGNAL or circuit breaker
        while True:
            # Check limits before each iteration
            if not self._check_limits():
                # Save state before raising error
                state_file = self.state_file
                self.state.save(state_file)
                raise WorkflowError("Stopping due to limits")

            # Increment iteration counters
            self.state.increment_iteration()

            # Get current phase info
            current_phase = Phase(self.state.current_phase)
            phase_name = current_phase.name_str

            # Show clear cycle/phase/iteration info with rich Rule and timestamp
            # Cycles are 0-indexed internally, display as 1-indexed (Cycle 0 -> "Cycle 1")
            display_cycle = self.state.cycle_iterations + 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.console.rule(
                f"[bold yellow]Cycle {display_cycle} | "
                f"Phase {current_phase.value}: {phase_name} | "
                f"API Call #{self.state.total_iterations} | "
                f"{timestamp}[/bold yellow]",
                style="yellow",
            )
            logger.console.print("")

            # Build loop context (recent activity, task count)
            loop_context = self._build_loop_context()

            # Display loop context if this is not the first iteration
            if self.state.total_iterations > 1 and loop_context:
                lines = loop_context.split("\n")
                context_preview = "\n".join(lines[:8]) if len(lines) > 8 else loop_context
                logger.console.print(
                    Panel(
                        f"[dim]{context_preview}[/dim]",
                        title="[bold cyan]Context",
                        border_style="cyan",
                        padding=(0, 1),
                    )
                )
                logger.console.print("")

            # Build full prompt with phase instructions
            full_prompt = build_full_prompt(
                original_task=prompt,
                phase=current_phase,
                plan_file=self.plan_file,
                decisions_file=self.decisions_file,
                loop_context=loop_context,
            )

            # Display phase prompt being used
            phase_prompt = get_phase_prompt(current_phase, self.plan_file, self.decisions_file)
            prompt_preview = phase_prompt[:300] + "..." if len(phase_prompt) > 300 else phase_prompt
            logger.console.print(
                Panel(
                    f"[dim]{prompt_preview}[/dim]",
                    title=f"[bold magenta]Phase {current_phase.value} Instructions",
                    border_style="magenta",
                    padding=(0, 1),
                )
            )
            logger.console.print("")

            # Execute Claude with retry logic
            try:
                response = self._execute_provider(full_prompt, current_phase)
            except ProviderError as e:
                logger.error(f"Provider execution failed: {e.message}")
                # Save state before raising error
                state_file = self.state_file
                self.state.save(state_file)
                raise WorkflowError(f"Claude execution failed: {e.message}")

            # Save raw output for circuit breaker analysis
            self.last_output_file.write_text(response.content)

            # Parse status block from response
            try:
                status_block = self.provider.extract_status_block(response)
            except ProviderError as e:
                logger.warning(f"Could not extract status block: {e.message}")
                logger.warning("Continuing without status block validation")
                status_block = {}

            # Check circuit breakers
            breaker_result = self._check_circuit_breaker(status_block)

            if breaker_result == CircuitBreakerResult.EXIT_SIGNAL:
                # EXIT_SIGNAL means current phase is complete
                logger.success("EXIT_SIGNAL detected - phase complete")
                self._log_completion_status(status_block)

            elif breaker_result == CircuitBreakerResult.COMPLETE:
                # All tasks complete - graceful exit (success)
                logger.success("All tasks complete - workflow finished successfully")
                state_file = self.state_file
                self.state.save(state_file)
                break  # Exit loop gracefully

            elif breaker_result == CircuitBreakerResult.BLOCKED:
                # Task blocked on external dependency - graceful exit (not failure)
                logger.warning("Task blocked on external dependency - halting workflow")
                logger.info("Resolve the blocking issue and resume the task")
                logger.info(f"Review {self.last_output_file} and {self.decisions_file} for details")
                state_file = self.state_file
                self.state.save(state_file)
                break  # Exit loop gracefully (not an error)

            elif breaker_result == CircuitBreakerResult.TRIGGERED:
                # Circuit breaker tripped - stagnation detected
                logger.error("Circuit breaker triggered - halting workflow")
                logger.error(
                    f"Review {self.last_output_file} and {self.decisions_file} for details"
                )
                # Save state before raising error
                state_file = self.state_file
                self.state.save(state_file)
                raise WorkflowError("Circuit breaker triggered")

            # Update state with progress metrics
            self._update_progress_metrics(status_block)

            # Save state after each iteration to keep state.json synchronized
            state_file = self.state_file
            self.state.save(state_file)

            # Write progress checkpoint periodically for context compaction
            # This helps restore context efficiently for long-running tasks
            if should_compact(self.state.total_iterations, compact_interval=10):
                self._write_progress_checkpoint(prompt, current_phase, status_block)

            # Check if phase transition is needed
            # Parse exit_signal from status block (handle both boolean and string values)
            exit_signal_value = status_block.get("exit_signal", False)
            if isinstance(exit_signal_value, str):
                exit_signal = exit_signal_value.lower() in ("true", "1", "yes")
            else:
                exit_signal = bool(exit_signal_value)

            if should_transition_phase(current_phase, self.plan_file, exit_signal):
                next_phase = determine_next_phase(
                    current_phase, self.plan_file, comprehensive=self.comprehensive
                )

                # Special case: About to enter Phase 2 in a new cycle
                # Check if there's any implementation work to do
                # This check happens AFTER Phase 1 writes the plan, so it's safe to read
                # Only check if the plan file exists (Phase 1 may have returned EXIT_SIGNAL
                # before creating a plan file)
                if (
                    next_phase == Phase.IMPLEMENT
                    and current_phase == Phase.PLAN
                    and self.state.cycle_iterations > 0
                    and self.plan_file.exists()
                ):
                    # Check if Phase 2 has any unchecked tasks
                    if not has_unchecked_tasks(Phase.IMPLEMENT, self.plan_file):
                        # No implementation work - increment counter
                        self.state.no_work_cycles += 1

                        # Check if we've had too many consecutive "no work" cycles
                        if self.state.no_work_cycles >= 2:
                            logger.success(
                                f"No implementation work found for {self.state.no_work_cycles} "
                                "consecutive cycles"
                            )
                            logger.info("Task appears complete - stopping workflow")
                            # Save state and exit
                            state_file = self.state_file
                            self.state.save(state_file)
                            break  # Exit the main loop

                        # First "no work" cycle - log and continue
                        logger.success("Phase 1 in new cycle found no implementation work")
                        logger.info("Skipping phases 2-6 and advancing to next cycle")

                        # Complete the current cycle
                        self.state.increment_cycle()
                        new_cycle = self.state.cycle_iterations

                        # Display cycles as 1-indexed for user-friendliness (internal is 0-indexed)
                        logger.success(f"Cycle {new_cycle} complete - no implementation work")
                        logger.info(f"Starting cycle {new_cycle + 1} - returning to Phase 1 (PLAN)")

                        # Archive the old plan.md (use 1-indexed to match plan content)
                        if self.plan_file.exists():
                            archived_plan = self.run_dir / f"plan-cycle-{new_cycle}.md"
                            logger.info(f"Archiving plan to: {archived_plan.name}")
                            self.plan_file.rename(archived_plan)

                        # Log cycle completion to decisions file (use 1-indexed for display)
                        self._log_cycle_completion(new_cycle, new_cycle + 1)

                        # Reset to Phase 1
                        self.state.transition_phase(Phase.PLAN.value, Phase.PLAN.name_str)

                        # Continue loop - will start new cycle at Phase 1
                        continue
                    else:
                        # Phase 2 has unchecked tasks - reset no-work counter
                        self.state.no_work_cycles = 0

                if next_phase is None:
                    # Cycle complete - either after COMMIT (standard) or ROADMAP (comprehensive)
                    # Increment cycle counter and loop back to starting phase
                    self.state.increment_cycle()
                    new_cycle = self.state.cycle_iterations

                    # Reset no-work counter since we completed a full cycle with work
                    self.state.no_work_cycles = 0

                    # Determine which phase completed and which to start next cycle
                    if self.comprehensive:
                        completed_phase = "Phase 7 (ROADMAP)"
                        start_phase = Phase.DISCOVER
                    else:
                        completed_phase = "Phase 6 (COMMIT)"
                        start_phase = Phase.PLAN

                    # Display cycles as 1-indexed for user-friendliness (internal is 0-indexed)
                    logger.success(f"Cycle {new_cycle} complete - {completed_phase} finished")
                    logger.info(
                        f"Starting cycle {new_cycle + 1} - returning to "
                        f"Phase {start_phase.value} ({start_phase.name_str})"
                    )

                    # Archive the old plan.md (use 1-indexed to match plan content)
                    if self.plan_file.exists():
                        archived_plan = self.run_dir / f"plan-cycle-{new_cycle}.md"
                        logger.info(f"Archiving plan to: {archived_plan.name}")
                        self.plan_file.rename(archived_plan)

                    # Log cycle completion to decisions file (use 1-indexed for display)
                    self._log_cycle_completion(new_cycle, new_cycle + 1)

                    # Reset to starting phase
                    self.state.transition_phase(start_phase.value, start_phase.name_str)

                    # Continue loop (don't break) - will start new cycle at starting phase

                elif next_phase != current_phase:
                    # Phase transition
                    next_phase_name = next_phase.name_str

                    # Validate plan when transitioning from PLAN to IMPLEMENT
                    if current_phase == Phase.PLAN and next_phase == Phase.IMPLEMENT:
                        if self.plan_file.exists():
                            log_validation_warnings(self.plan_file)

                    logger.success(
                        f"Phase {current_phase.value} ({phase_name}) complete "
                        f"→ advancing to Phase {next_phase.value} ({next_phase_name})"
                    )

                    # Log transition to decisions file
                    self._log_phase_transition(current_phase, next_phase)

                    # Update state
                    self.state.transition_phase(next_phase.value, next_phase_name)
                    phase = self.state.current_phase
                    name = self.state.phase_name
                    logger.info(f"State updated: now in Phase {phase} ({name})")

        # Save final state
        state_file = self.state_file
        self.state.save(state_file)

        logger.success("All done!")

    def _check_limits(self) -> bool:
        """Check if iteration or cost limits have been reached.

        Returns:
            True if within limits, False if limits exceeded
        """
        # Check cycle limit (complete 6-phase cycles)
        if self.state.cycle_iterations >= self.config.max_iterations:
            logger.error(
                f"Reached max cycles: {self.state.cycle_iterations} >= {self.config.max_iterations}"
            )
            return False

        # Check cost limit
        if self.state.cost_usd >= self.config.cost_limit:
            logger.error(
                f"Reached cost limit: ${self.state.cost_usd:.2f} >= ${self.config.cost_limit:.2f}"
            )
            return False

        # Within limits
        return True

    def _build_loop_context(self) -> str:
        """Build loop context for prompt.

        Returns:
            Loop context string with iteration counts and recent activity
        """
        # Count tasks completed (from plan file)
        tasks_completed = 0
        if self.plan_file.exists():
            plan_content = self.plan_file.read_text()
            tasks_completed = plan_content.count("- [x]")

        # Read recent decisions (last 20 lines)
        recent_decisions = ""
        if self.decisions_file.exists():
            lines = self.decisions_file.read_text().splitlines()
            recent_lines = lines[-20:]
            recent_decisions = "\n".join(recent_lines)

        # Get current phase
        current_phase = Phase(self.state.current_phase)

        return build_loop_context(
            cycle_iterations=self.state.cycle_iterations,
            total_iterations=self.state.total_iterations,
            phase_iterations=self.state.phase_iterations,
            tasks_completed=tasks_completed,
            current_phase=current_phase,
            recent_decisions=recent_decisions,
        )

    def _read_plan_file(self) -> str:
        """Read plan file content.

        Returns:
            Plan file content, or empty string if file doesn't exist
        """
        if not self.plan_file.exists():
            return ""

        return self.plan_file.read_text()

    def _execute_provider(self, full_prompt: str, current_phase: Phase) -> Any:
        """Execute AI provider with appropriate model selection.

        Args:
            full_prompt: Complete prompt with phase instructions
            current_phase: Current phase

        Returns:
            AIResponse from provider
        """
        # Select model based on phase
        # DISCOVER, PLAN, and ROADMAP phases use the plan model
        if current_phase in (Phase.DISCOVER, Phase.PLAN, Phase.ROADMAP):
            model = self.config.plan_model
        elif current_phase in (Phase.REVIEW, Phase.FINAL_REVIEW):
            model = self.config.review_model
        else:
            model = self.config.model

        logger.info(f"Using model: {model}")

        # Execute with system prompt (from prompts.py)
        from nelson.prompts import get_system_prompt

        system_prompt = get_system_prompt(self.decisions_file)

        # Start progress monitor to show activity during long-running calls
        # Monitor the run directory for file changes (decisions.md, plan.md, etc.)
        # If no activity for configured timeout, flag as stalled and kill the process
        progress_monitor = ProgressMonitor(
            watch_dir=self.run_dir,
            heartbeat_interval=60.0,  # Print heartbeat every 60 seconds
            check_interval=2.0,  # Check for file changes every 2 seconds
            max_idle_minutes=self.config.stall_timeout_minutes,
        )
        progress_monitor.start()

        try:
            return self.provider.execute(
                system_prompt=system_prompt,
                user_prompt=full_prompt,
                model=model,
                max_retries=3,
                retry_delay=3.0,
                progress_monitor=progress_monitor,
            )
        finally:
            progress_monitor.stop()

    def _check_circuit_breaker(self, status_block: dict[str, Any]) -> "CircuitBreakerResult":
        """Check for circuit breaker conditions.

        Args:
            status_block: Parsed status block from Claude's response

        Returns:
            CircuitBreakerResult indicating what action to take
        """
        # Check for EXIT_SIGNAL first
        # Handle both boolean and string values (Claude may return "true"/"false" strings)
        exit_signal_value = status_block.get("exit_signal", False)
        if isinstance(exit_signal_value, str):
            exit_signal = exit_signal_value.lower() in ("true", "1", "yes")
        else:
            exit_signal = bool(exit_signal_value)

        # Track same-phase looping (for looping phases only)
        current_phase = Phase(self.state.current_phase)
        if self.state.last_phase_tracked == self.state.current_phase:
            self.state.same_phase_loop_count += 1
        else:
            # Phase changed, reset counter
            self.state.same_phase_loop_count = 0
            self.state.last_phase_tracked = self.state.current_phase

        # Check for excessive same-phase looping (10+ consecutive iterations in same looping phase)
        # This catches cases where EXIT_SIGNAL=true but plan tasks aren't being checked off
        if current_phase.can_loop and self.state.same_phase_loop_count >= 10:
            logger.error(
                f"Same-phase loop detected: {self.state.same_phase_loop_count} iterations "
                f"in Phase {current_phase.value} ({current_phase.name})"
            )
            return CircuitBreakerResult.TRIGGERED

        if exit_signal:
            return CircuitBreakerResult.EXIT_SIGNAL

        # Extract progress metrics
        # Convert to int, handling both string and int values
        tasks_completed = int(status_block.get("tasks_completed", 0) or 0)
        files_modified_value = status_block.get("files_modified", 0)

        # Parse files_modified, handling strings and ints
        if isinstance(files_modified_value, (int, str)) and str(files_modified_value).isdigit():
            files_modified = int(files_modified_value)
        else:
            files_modified = 0

        # Track blocked status (task waiting on external dependency)
        status = status_block.get("status", "")
        if "blocked" in status.lower():
            self.state.blocked_iterations += 1
        else:
            self.state.blocked_iterations = 0

        # Check for blocked status FIRST (external dependency - not a failure)
        # This allows graceful exit when task needs user intervention
        if self.state.blocked_iterations >= 3:
            logger.warning(
                f"Task blocked on external dependency "
                f"({self.state.blocked_iterations} consecutive BLOCKED iterations)"
            )
            return CircuitBreakerResult.BLOCKED

        # Check for progress this iteration
        # tasks_completed is per-loop count (TASKS_COMPLETED_THIS_LOOP), not cumulative
        # Any non-zero tasks or files means progress was made
        if tasks_completed > 0 or files_modified > 0:
            # Progress was made, reset counter
            self.state.no_progress_iterations = 0
        else:
            # No progress this iteration
            self.state.no_progress_iterations += 1

        # Update timestamp for state tracking
        self.state.update_timestamp()

        # Check for no progress (3+ iterations with 0 tasks, 0 files)
        if self.state.no_progress_iterations >= 3:
            # Before treating as failure, check if all tasks are complete
            # "No progress" because work is done is SUCCESS, not failure
            if not self._has_any_unchecked_tasks():
                logger.success("All tasks complete - no more work to do")
                return CircuitBreakerResult.COMPLETE

            # Actually stuck - no progress with remaining work
            logger.error(f"No progress detected for {self.state.no_progress_iterations} iterations")
            return CircuitBreakerResult.TRIGGERED

        # Check for test-only loops (3+ consecutive TESTING with no file changes)
        work_type = status_block.get("work_type", "")
        if work_type == "TESTING" and files_modified == 0:
            self.state.test_only_loop_count += 1
        else:
            self.state.test_only_loop_count = 0

        if self.state.test_only_loop_count >= 3:
            logger.error("Test-only loop detected (3+ iterations of TESTING with no changes)")
            return CircuitBreakerResult.TRIGGERED

        # Check for repeated errors
        recommendation = status_block.get("recommendation", "")
        # Note: Don't treat BLOCKED as an error - it's handled separately above
        if "error" in recommendation.lower():
            self.state.record_error(recommendation)

            if self.state.repeated_error_count >= 3:
                logger.error("Repeated error detected (same error pattern 3+ times)")
                return CircuitBreakerResult.TRIGGERED
        else:
            # No error in this iteration
            self.state.record_error("")

        # No circuit breaker conditions met
        return CircuitBreakerResult.OK

    def _update_progress_metrics(self, status_block: dict[str, Any]) -> None:
        """Update state with progress metrics from status block.

        Args:
            status_block: Parsed status block
        """
        # Cost tracking placeholder - would extract from actual response
        # when provider supports cost reporting
        # For now, no cost tracking implemented
        pass

    def _has_any_unchecked_tasks(self) -> bool:
        """Check if any phase has unchecked (incomplete) tasks.

        Used to distinguish between "no progress because stuck" vs
        "no progress because all work is complete".

        Returns:
            True if there are unchecked tasks in any phase, False if all done
        """
        if not self.plan_file.exists():
            # No plan file means we can't verify completion - assume work remains
            return True

        # Check all phases for unchecked tasks
        for phase in Phase:
            if has_unchecked_tasks(phase, self.plan_file):
                return True

        return False

    def _log_cycle_completion(self, completed_cycle: int, new_cycle: int) -> None:
        """Log cycle completion to decisions file.

        Args:
            completed_cycle: Cycle number that just completed
            new_cycle: Next cycle number
        """
        # Append to decisions file
        with open(self.decisions_file, "a") as f:
            f.write("\n")
            f.write(
                f"## Cycle {completed_cycle} Complete "
                f"(Phase Execution {self.state.total_iterations})\n"
            )
            f.write("\n")
            f.write("**Phase 6 (COMMIT)**: Complete\n")
            f.write(f"**Next**: Starting cycle {new_cycle} - Phase 1 (PLAN)\n")
            f.write("**Note**: Previous plan archived. Next cycle will start fresh (stateless).\n")
            f.write("\n")

    def _log_phase_transition(self, from_phase: Phase, to_phase: Phase) -> None:
        """Log phase transition to decisions file.

        Args:
            from_phase: Current phase
            to_phase: Next phase
        """
        # Append to decisions file
        with open(self.decisions_file, "a") as f:
            f.write("\n")
            f.write(f"## Phase Transition (Iteration {self.state.total_iterations})\n")
            f.write("\n")
            f.write(f"**From**: Phase {from_phase.value} ({from_phase.name_str})\n")
            f.write(f"**To**: Phase {to_phase.value}\n")
            f.write("\n")

    def _log_completion_status(self, status_block: dict[str, Any]) -> None:
        """Log final completion status.

        Args:
            status_block: Final status block
        """
        logger.info("")
        logger.info("Status Block:")
        for key, value in status_block.items():
            logger.info(f"  {key}: {value}")
        logger.info("")

    def _write_progress_checkpoint(
        self,
        original_task: str,
        current_phase: Phase,
        status_block: dict[str, Any],
    ) -> None:
        """Write a progress checkpoint for context compaction.

        This creates a condensed summary of progress that can be used to
        restore context efficiently after compaction or when resuming work.

        Args:
            original_task: The original user task
            current_phase: Current workflow phase
            status_block: Status block from last iteration
        """
        # Count tasks completed and remaining from plan
        tasks_completed = 0
        tasks_remaining = 0
        if self.plan_file.exists():
            plan_content = self.plan_file.read_text()
            tasks_completed = plan_content.count("- [x]")
            tasks_remaining = plan_content.count("- [ ]")

        # Determine current state from status block
        status = status_block.get("status", "IN_PROGRESS")
        recommendation = status_block.get("recommendation", "")
        current_state = f"Status: {status}. {recommendation}"

        # Extract recent work from decisions log
        recent_work = extract_recent_work(self.decisions_file, max_items=5)

        # Check for blockers
        blockers: list[str] = []
        blocked_reason = status_block.get("blocked_reason", "")
        if blocked_reason:
            blockers.append(blocked_reason)

        # Determine approach based on phase
        approach = f"Executing Phase {current_phase.value} ({current_phase.name_str})"
        if current_phase == Phase.PLAN:
            approach = "Analyzing task and creating implementation plan"
        elif current_phase == Phase.IMPLEMENT:
            approach = "Implementing plan tasks one by one with atomic commits"
        elif current_phase == Phase.REVIEW:
            approach = "Reviewing changes for bugs, patterns, and quality"
        elif current_phase == Phase.TEST:
            approach = "Running tests and fixing any failures"
        elif current_phase == Phase.FINAL_REVIEW:
            approach = "Final review of all changes before commit"
        elif current_phase == Phase.COMMIT:
            approach = "Committing remaining changes"
        elif current_phase == Phase.DISCOVER:
            approach = "Researching codebase to understand patterns and structure"
        elif current_phase == Phase.ROADMAP:
            approach = "Documenting future improvements and technical debt"

        # Write the checkpoint
        write_progress_checkpoint(
            log_path=self.decisions_file,
            original_task=original_task,
            current_phase=current_phase,
            cycle=self.state.cycle_iterations + 1,  # Display as 1-indexed
            iteration=self.state.total_iterations,
            tasks_completed=tasks_completed,
            tasks_remaining=tasks_remaining,
            current_state=current_state,
            approach=approach,
            recent_work=recent_work,
            blockers=blockers if blockers else None,
        )

        logger.info(f"Progress checkpoint written at iteration {self.state.total_iterations}")


class WorkflowError(Exception):
    """Exception raised when workflow encounters an error."""

    pass
