"""PRD orchestration engine for nelson-prd.

This module implements the main execution loop that orchestrates
multiple Nelson runs based on PRD tasks, handling priority-based
execution, branch management, cost tracking, and state transitions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from nelson.cli import main as nelson_main
from nelson.config import NelsonConfig
from nelson.git_utils import GitError, get_current_branch
from nelson.logging_config import get_logger
from nelson.prd_parser import PRDParser, PRDTaskStatus
from nelson.prd_state import PRDStateManager
from nelson.prd_task_state import TaskStatus
from nelson.providers.claude import ClaudeProvider
from nelson.state import NelsonState

logger = get_logger()


def _prd_status_to_task_status(prd_status: PRDTaskStatus) -> str:
    """Convert PRDTaskStatus to TaskStatus enum value.

    Args:
        prd_status: Status from PRD file

    Returns:
        TaskStatus enum value string
    """
    if prd_status == PRDTaskStatus.COMPLETED:
        return TaskStatus.COMPLETED.value
    elif prd_status == PRDTaskStatus.IN_PROGRESS:
        return TaskStatus.IN_PROGRESS.value
    elif prd_status == PRDTaskStatus.BLOCKED:
        return TaskStatus.BLOCKED.value
    else:  # PENDING
        return TaskStatus.PENDING.value


class PRDOrchestrator:
    """Orchestrates Nelson execution across multiple PRD tasks."""

    def __init__(
        self, prd_file: Path, prd_dir: Path | None = None, target_path: Path | None = None
    ):
        """Initialize orchestrator.

        Args:
            prd_file: Path to PRD markdown file
            prd_dir: Path to .nelson/prd directory (default: .nelson/prd)
            target_path: Optional target repository path (default: current directory)
        """
        self.prd_file = prd_file
        self.target_path = target_path

        # PRD directory should be relative to target path, not CWD
        target = Path(target_path) if target_path else Path(".")
        self.prd_dir = prd_dir or (target / ".nelson/prd")

        # Initialize state manager
        self.state_manager = PRDStateManager(self.prd_dir, str(prd_file))

        # Parse PRD file (backups go to prd_dir/backups)
        backup_dir = self.prd_dir / "backups"
        self.parser = PRDParser(prd_file, backup_dir=backup_dir)
        self.tasks = self.parser.parse()

        # Initialize task mapping in state if needed
        self._initialize_task_mapping()

    def _initialize_task_mapping(self) -> None:
        """Initialize task mapping in PRD state from parsed tasks."""
        for task in self.tasks:
            # Only add if not already in mapping
            if task.task_id not in self.state_manager.prd_state.task_mapping:
                self.state_manager.prd_state.add_task(
                    task.task_id, task.task_text, task.priority, task.line_number
                )
        self.state_manager.save_prd_state()

    def check_task_text_changes(self) -> list[dict[str, str]]:
        """Check if any task texts have changed compared to stored original text.

        Returns:
            List of dictionaries with change information:
            [
                {
                    "task_id": "PRD-001",
                    "original_text": "Old task description",
                    "current_text": "New task description"
                },
                ...
            ]
        """
        changes = []
        task_mapping = self.state_manager.prd_state.task_mapping

        for task in self.tasks:
            if task.task_id in task_mapping:
                original_text = task_mapping[task.task_id]["original_text"]
                if task.task_text != original_text:
                    changes.append({
                        "task_id": task.task_id,
                        "original_text": original_text,
                        "current_text": task.task_text,
                    })

        return changes

    def _parse_branch_info(self, output: str) -> dict[str, str] | None:
        """Parse BRANCH_INFO from Nelson's output.

        Args:
            output: Combined stdout/stderr from Nelson

        Returns:
            Dictionary with branch, base, and reason keys, or None if not found
        """
        import re

        # Look for the marker block
        pattern = r"=== BRANCH_INFO ===\s*\nBRANCH:\s*(.+?)\s*\nBASE:\s*(.+?)\s*\nREASON:\s*(.+?)\s*\n==================="
        match = re.search(pattern, output, re.DOTALL)

        if match:
            return {
                "branch": match.group(1).strip(),
                "base": match.group(2).strip(),
                "reason": match.group(3).strip(),
            }

        return None

    def _setup_branch_for_task(
        self, task_id: str, task_text: str
    ) -> dict[str, str | None]:
        """Analyze task and create appropriate branch using Claude.

        This makes a single, focused Claude API call to:
        1. Analyze the task requirements
        2. Determine appropriate branching strategy
        3. Create/checkout the branch
        4. Return branch information

        Args:
            task_id: Task ID (e.g., "PRD-001")
            task_text: Full task description

        Returns:
            Dictionary with keys: branch, base_branch, reason
        """
        logger.info(f"Analyzing task for branch setup: {task_id}")

        # Load config to get claude command
        config = NelsonConfig.from_environment(target_path=self.target_path)

        # Create Claude provider
        provider = ClaudeProvider(
            claude_command=config.claude_command, target_path=self.target_path
        )

        # Build focused system prompt for branching
        system_prompt = """You are a git branching expert helping set up the correct branch for a task.

Your job is to:
1. Analyze the task description
2. Determine the appropriate branching strategy
3. Execute git commands to create/checkout the branch
4. Return structured information about what you did

Guidelines:
- If the task involves reviewing/fixing a PR, use gh CLI to checkout that PR branch, then create a fix branch from it
- If the task is new work, branch from main/master
- Choose descriptive, concise branch names (e.g., "execution_queue_tables-fixes" not "feature/PRD-001-code-review-pr-https...")
- Use lowercase with hyphens, keep it under 40 characters

After setting up the branch, you MUST output EXACTLY this format:
```json
{
  "branch": "actual-branch-name",
  "base_branch": "branch-you-based-it-on",
  "reason": "brief explanation of your choice"
}
```

Output ONLY the JSON, nothing else."""

        # Build user prompt with task details
        user_prompt = f"""Task ID: {task_id}

Task Description:
{task_text}

Please analyze this task, create the appropriate git branch, and return the JSON with branch information."""

        try:
            # Call Claude with haiku (fast and cheap for simple task)
            response = provider.execute(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="haiku",
                max_retries=2,
            )

            # Parse JSON from response
            content = response.content.strip()

            # Extract JSON if wrapped in code block
            if "```json" in content:
                json_start = content.index("```json") + 7
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.index("```") + 3
                json_end = content.index("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content

            branch_info = json.loads(json_str)

            # Validate we got the required fields
            if not all(k in branch_info for k in ["branch", "base_branch", "reason"]):
                raise ValueError("Missing required fields in branch info")

            logger.info(
                f"Branch setup complete: {branch_info['branch']} (from {branch_info['base_branch']})"
            )

            # Verify with git that we're actually on this branch
            actual_branch = get_current_branch(self.target_path)
            if actual_branch != branch_info["branch"]:
                logger.warning(
                    f"Git shows branch '{actual_branch}' but Claude reported '{branch_info['branch']}'"
                )
                branch_info["branch"] = actual_branch

            return branch_info

        except Exception as e:
            logger.error(f"Branch setup failed: {e}")
            # Fallback: use current branch
            current_branch = get_current_branch(self.target_path)
            if current_branch:
                logger.info(f"Falling back to current branch: {current_branch}")
                return {
                    "branch": current_branch,
                    "base_branch": None,
                    "reason": f"Fallback due to error: {e}",
                }
            else:
                # No branch at all - this is a problem
                raise GitError(
                    f"Failed to setup branch and no current branch exists: {e}"
                )

    def _find_actual_nelson_run(self, expected_time: str) -> str | None:
        """Find the actual Nelson run directory created around the expected time.

        Nelson generates its own run_id when it starts, which may differ from
        the run_id PRD generates. This function finds the actual run directory
        by looking for the most recent run created around the expected time.

        Args:
            expected_time: Expected run_id timestamp (format: nelson-YYYYMMDD-HHMMSS)

        Returns:
            Actual run_id (without nelson- prefix) or None if not found
        """
        base_path = self.target_path if self.target_path else Path(".")
        runs_dir = base_path / ".nelson" / "runs"

        if not runs_dir.exists():
            return None

        # Parse expected timestamp
        try:
            expected_dt = datetime.strptime(
                expected_time.replace("nelson-", ""), "%Y%m%d-%H%M%S"
            )
        except ValueError:
            return None

        # Find runs within 5 minutes of expected time
        matching_runs = []
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("nelson-"):
                continue

            try:
                run_dt = datetime.strptime(
                    run_dir.name.replace("nelson-", ""), "%Y%m%d-%H%M%S"
                )
                time_diff = abs((run_dt - expected_dt).total_seconds())

                # Within 5 minutes (300 seconds)
                if time_diff <= 300:
                    matching_runs.append((run_dir.name, time_diff))
            except ValueError:
                continue

        # Return closest match
        if matching_runs:
            closest = min(matching_runs, key=lambda x: x[1])
            return closest[0]

        return None

    def get_next_pending_task(self) -> tuple[str, str, str] | None:
        """Get next pending task by priority.

        Returns:
            Tuple of (task_id, task_text, priority) or None if no pending tasks
        """
        # Re-parse to get current task statuses
        self.tasks = self.parser.parse()

        # Check priorities in order: high, medium, low
        for priority in ["high", "medium", "low"]:
            for task in self.tasks:
                if (
                    task.priority == priority
                    and task.status == PRDTaskStatus.PENDING
                ):
                    return (task.task_id, task.task_text, task.priority)

        return None

    def execute_task(
        self,
        task_id: str,
        task_text: str,
        priority: str,
        prompt: str | None = None,
        nelson_args: list[str] | None = None,
    ) -> bool:
        """Execute a single task with Nelson.

        Args:
            task_id: Task ID (e.g., "PRD-001")
            task_text: Task description
            priority: Task priority
            prompt: Optional custom prompt (defaults to task_text)
            nelson_args: Additional Nelson CLI arguments

        Returns:
            True if task succeeded, False if failed
        """
        # Load or create task state
        task_state = self.state_manager.load_task_state(task_id, task_text, priority)

        # Setup branch BEFORE starting Nelson
        print("\n🌿 Setting up git branch for task...")
        try:
            branch_info = self._setup_branch_for_task(task_id, task_text)
            branch_name = branch_info["branch"]
            base_branch = branch_info.get("base_branch")
            branch_reason = branch_info.get("reason")

            print(f"   Branch: {branch_name}")
            if base_branch:
                print(f"   Based on: {base_branch}")
            if branch_reason:
                print(f"   Reason: {branch_reason}")
        except Exception as e:
            print(f"   ❌ Branch setup failed: {e}")
            # Mark task as blocked
            self.parser.update_task_status(
                task_id, PRDTaskStatus.BLOCKED, f"Branch setup failed: {e}"
            )
            task_state.block(f"Branch setup failed: {e}")
            self.state_manager.save_task_state(task_state)
            return False

        # Generate Nelson run ID
        from datetime import UTC, datetime
        run_id = datetime.now(UTC).strftime("nelson-%Y%m%d-%H%M%S")

        # Start task (updates state) with branch info
        task_state.start(
            run_id,
            branch=branch_name,
            base_branch=base_branch,
            branch_reason=branch_reason,
        )
        self.state_manager.save_task_state(task_state)

        # Update PRD file to in-progress
        self.parser.update_task_status(task_id, PRDTaskStatus.IN_PROGRESS)

        # Build Nelson arguments (NO branching instructions - branch is already set up)
        # Use full_description if available (contains all indented content from PRD)
        if prompt:
            task_prompt = prompt
        else:
            # Get the task to access full_description
            task = self.parser.get_task_by_id(task_id)
            if task and task.full_description:
                # Combine first line with full description for complete context
                task_prompt = f"{task_text}\n\n{task.full_description}"
            else:
                task_prompt = task_text

        # Prepend resume context if present
        if task_state.resume_context:
            task_prompt = f"RESUME CONTEXT: {task_state.resume_context}\n\n{task_prompt}"

        # Build args list (no "nelson" command needed - calling directly)
        args = [task_prompt]

        # Add target path if provided (must come after prompt, before flags)
        if self.target_path:
            args.append(str(self.target_path))

        if nelson_args:
            args.extend(nelson_args)

        # Execute Nelson
        print(f"\n{'='*60}")
        print(f"🚀 Starting task: {task_id}")
        print(f"   Description: {task_text}")
        print(f"   Branch: {branch_name}")
        if task_state.resume_context:
            print("   🔄 Resuming with context")
        print(f"{'='*60}\n")

        try:
            # Run Nelson directly (in-process, no subprocess)
            # standalone_mode=False prevents Click from calling sys.exit()
            # and instead returns the exit code
            exit_code = nelson_main(args, standalone_mode=False)
            success = exit_code == 0

            # Provide specific feedback for non-zero exit codes
            if not success:
                print(f"\nNelson exited with code {exit_code}")
                if exit_code == 1:
                    print("This usually indicates Nelson encountered an error during execution.")
                else:
                    print(f"Unexpected exit code: {exit_code}")
        except KeyboardInterrupt:
            print("\n\nTask interrupted by user (KeyboardInterrupt)")
            success = False
            raise  # Re-raise to stop PRD execution
        except Exception as e:
            print(f"\nUnexpected error executing Nelson: {type(e).__name__}: {e}")
            print("This is an unexpected error. Please report this issue.")
            success = False

        # Update task state based on result
        if success:
            # Try to read Nelson state for cost/iteration info
            # Nelson generates its own run_id, so find the actual run directory
            actual_run_id = self._find_actual_nelson_run(run_id)

            if actual_run_id:
                # Update task state with actual run_id
                task_state.nelson_run_id = actual_run_id
                logger.info(f"Found actual Nelson run: {actual_run_id}")

                # Nelson state is relative to target repository
                base_path = self.target_path if self.target_path else Path(".")
                nelson_state_path = base_path / ".nelson" / "runs" / actual_run_id / "state.json"

                if nelson_state_path.exists():
                    try:
                        nelson_state = NelsonState.load(nelson_state_path)
                        task_state.update_cost(nelson_state.cost_usd)
                        task_state.increment_iterations(nelson_state.total_iterations)
                        if nelson_state.current_phase:
                            task_state.update_phase(
                                nelson_state.current_phase, nelson_state.phase_name
                            )
                    except Exception as e:
                        print(f"Warning: Could not read Nelson state: {e}")
                else:
                    print(f"Warning: Nelson state file not found at {nelson_state_path}")
            else:
                print(f"Warning: Could not find actual Nelson run directory near {run_id}")

            # Check if task has incomplete subtasks before marking complete
            task = self.parser.get_task_by_id(task_id)
            if task and task.has_incomplete_subtasks():
                completed, total = task.get_subtask_completion_count()
                print(f"\n{'='*60}")
                print(f"⚠️  Task {task_id} has incomplete subtasks ({completed}/{total} done)")
                print(f"   Cannot mark task as complete until all subtasks are finished.")
                print(f"   Please check off remaining subtasks in the PRD file.")
                print(f"{'='*60}\n")

                # Mark as blocked instead with reason
                task_state.fail()
                self.state_manager.save_task_state(task_state)
                self.parser.update_task_status(
                    task_id,
                    PRDTaskStatus.BLOCKED,
                    f"Incomplete subtasks: {completed}/{total} done"
                )
                return False

            # Mark as completed
            task_state.complete()
            self.state_manager.save_task_state(task_state)

            # Update PRD file
            self.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)

            print(f"\n{'='*60}")
            print(f"✅ Task completed: {task_id}")
            if task_state.branch:
                print(f"   Branch: {task_state.branch}")
                if task_state.base_branch:
                    print(f"   Based on: {task_state.base_branch}")
                if task_state.branch_reason:
                    print(f"   Reason: {task_state.branch_reason}")
            print(f"   Cost: ${task_state.cost_usd:.2f}")
            print(f"   Iterations: {task_state.iterations}")
            if task_state.phase_name:
                print(f"   Final phase: {task_state.phase_name}")
            print(f"{'='*60}\n")
        else:
            # Try to find actual run directory even on failure to extract partial state
            actual_run_id = self._find_actual_nelson_run(run_id)

            if actual_run_id:
                task_state.nelson_run_id = actual_run_id
                logger.info(f"Found actual Nelson run (failed): {actual_run_id}")

                base_path = self.target_path if self.target_path else Path(".")
                nelson_state_path = base_path / ".nelson" / "runs" / actual_run_id / "state.json"

                if nelson_state_path.exists():
                    try:
                        nelson_state = NelsonState.load(nelson_state_path)
                        task_state.update_cost(nelson_state.cost_usd)
                        task_state.increment_iterations(nelson_state.total_iterations)
                        if nelson_state.current_phase:
                            task_state.update_phase(
                                nelson_state.current_phase, nelson_state.phase_name
                            )
                    except Exception as e:
                        print(f"Warning: Could not read Nelson state from failed run: {e}")

            # Mark as failed
            task_state.fail()
            self.state_manager.save_task_state(task_state)

            # Keep in-progress in PRD file for manual review
            print(f"\n{'='*60}")
            print(f"❌ Task failed: {task_id}")
            print("   Review the task and fix any issues before resuming")
            print(f"{'='*60}\n")

        return success

    def execute_all_pending(
        self, nelson_args: list[str] | None = None, stop_on_failure: bool = False
    ) -> dict[str, bool]:
        """Execute all pending tasks in priority order.

        Args:
            nelson_args: Additional Nelson CLI arguments
            stop_on_failure: If True, stop execution on first failure

        Returns:
            Dictionary mapping task_id to success status
        """
        results = {}

        # Get count of pending tasks for progress tracking
        pending_tasks = [
            t for t in self.tasks if t.status.value == " "  # PRDTaskStatus.PENDING
        ]
        total_pending = len(pending_tasks)

        # Get current completion status
        summary = self.get_status_summary()
        total_tasks = summary["total_tasks"]
        completed_before = summary["completed"]

        # Show initial progress
        if total_pending > 0:
            print(f"\n{'='*60}")
            print("PRD Execution Progress")
            print(f"{'='*60}")
            print(f"Total tasks in PRD: {total_tasks}")
            print(f"Already completed: {completed_before}")
            print(f"Pending to execute: {total_pending}")
            print(f"{'='*60}\n")

        current_task_num = 0
        try:
            while True:
                # Get next pending task
                next_task = self.get_next_pending_task()
                if next_task is None:
                    # No more pending tasks
                    break

                task_id, task_text, priority = next_task
                current_task_num += 1

                # Show progress indicator
                print(f"\n{'─'*60}")
                print(f"📋 Task {current_task_num} of {total_pending} | Priority: {priority.upper()}")
                print(f"{'─'*60}")

                # Execute task
                success = self.execute_task(
                    task_id, task_text, priority, nelson_args=nelson_args
                )
                results[task_id] = success

                # Show interim progress
                completed_so_far = completed_before + sum(1 for s in results.values() if s)
                remaining = total_tasks - completed_so_far
                completion_pct = (completed_so_far / total_tasks * 100) if total_tasks > 0 else 0

                print(f"\n{'─'*60}")
                print(
                    f"📊 Progress: {completed_so_far}/{total_tasks} tasks "
                    f"({completion_pct:.1f}% complete)"
                )
                print(f"   Remaining: {remaining} tasks")
                print(f"{'─'*60}")

                if not success and stop_on_failure:
                    print(f"\n⚠️  Stopping execution due to task failure: {task_id}")
                    break
        except KeyboardInterrupt:
            print("\n\n⚠️  Execution interrupted by user (Ctrl-C)")
            print("Stopping task execution...")

        return results

    def resume_task(
        self, task_id: str, nelson_args: list[str] | None = None
    ) -> bool:
        """Resume a specific task (typically after unblocking).

        Args:
            task_id: Task ID to resume
            nelson_args: Additional Nelson CLI arguments

        Returns:
            True if task succeeded, False if failed
        """
        # Find task
        task = self.parser.get_task_by_id(task_id)
        if task is None:
            print(f"Error: Task not found: {task_id}")
            return False

        # Check if task is resumable (blocked, in-progress, or pending with resume context)
        if task.status not in [
            PRDTaskStatus.BLOCKED,
            PRDTaskStatus.IN_PROGRESS,
            PRDTaskStatus.PENDING,
        ]:
            print(
                f"Error: Task {task_id} is not in a resumable state (status: {task.status})"
            )
            return False

        # If task is pending, it must have resume context to be resumable
        if task.status == PRDTaskStatus.PENDING:
            task_state = self.state_manager.load_task_state(
                task_id, task.task_text, task.priority
            )
            if not task_state.resume_context:
                print(
                    f"Error: Task {task_id} is PENDING but has no resume context. "
                    "Use execute_task instead of resume_task for fresh pending tasks."
                )
                return False

        # Update status to pending in PRD file so it can be picked up (if not already)
        if task.status != PRDTaskStatus.PENDING:
            self.parser.update_task_status(task_id, PRDTaskStatus.PENDING)
            # Re-parse to refresh cache
            self.tasks = self.parser.parse()

        # Execute task
        return self.execute_task(
            task_id, task.task_text, task.priority, nelson_args=nelson_args
        )

    def block_task(self, task_id: str, reason: str) -> bool:
        """Block a task with a reason.

        Args:
            task_id: Task ID to block
            reason: Blocking reason

        Returns:
            True if successful, False otherwise
        """
        # Find task
        task = self.parser.get_task_by_id(task_id)
        if task is None:
            print(f"Error: Task not found: {task_id}")
            return False

        # Update task state
        self.state_manager.block_task(task_id, task.task_text, task.priority, reason)

        # Update PRD file
        self.parser.update_task_status(task_id, PRDTaskStatus.BLOCKED, reason)

        # Re-parse to refresh cache
        self.tasks = self.parser.parse()

        print(f"Task {task_id} blocked: {reason}")
        return True

    def unblock_task(self, task_id: str, context: str | None = None) -> bool:
        """Unblock a task with optional resume context.

        Args:
            task_id: Task ID to unblock
            context: Optional resume context

        Returns:
            True if successful, False otherwise
        """
        # Find task
        task = self.parser.get_task_by_id(task_id)
        if task is None:
            print(f"Error: Task not found: {task_id}")
            return False

        if task.status != PRDTaskStatus.BLOCKED:
            print(f"Error: Task {task_id} is not blocked (status: {task.status})")
            return False

        # Update task state
        self.state_manager.unblock_task(task_id, task.task_text, task.priority, context)

        # Update PRD file
        self.parser.update_task_status(task_id, PRDTaskStatus.PENDING)

        # Re-parse to refresh cache
        self.tasks = self.parser.parse()

        print(f"Task {task_id} unblocked")
        if context:
            print(f"Resume context: {context}")
        return True

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of all tasks and their status.

        Returns:
            Dictionary with status information
        """
        # Re-parse to get current status from PRD file
        self.tasks = self.parser.parse()

        # Count statuses from parsed PRD file (source of truth)
        completed_count = 0
        in_progress_count = 0
        blocked_count = 0
        pending_count = 0
        failed_count = 0

        # Build tasks list with merged data from PRD file and state files
        tasks_list = []
        total_cost = 0.0

        for task in self.tasks:
            # Load state file if it exists for this task
            task_state_path = self.state_manager.get_task_state_path(task.task_id)
            if task_state_path.exists():
                task_state = self.state_manager.load_task_state(
                    task.task_id, task.task_text, task.priority
                )
                # Use state from PRD file (source of truth), not from state file
                # But keep metadata from state file
                task_dict = {
                    "task_id": task.task_id,
                    "task_text": task.task_text,
                    "status": _prd_status_to_task_status(task.status),  # From PRD file
                    "priority": task.priority,
                    "branch": task_state.branch,
                    "base_branch": task_state.base_branch,
                    "branch_reason": task_state.branch_reason,
                    "blocking_reason": task_state.blocking_reason,
                    "resume_context": task_state.resume_context,
                    "nelson_run_id": task_state.nelson_run_id,
                    "started_at": task_state.started_at,
                    "completed_at": task_state.completed_at,
                    "blocked_at": task_state.blocked_at,
                    "cost_usd": task_state.cost_usd,
                    "iterations": task_state.iterations,
                    "phase": task_state.phase,
                    "phase_name": task_state.phase_name,
                }
                total_cost += task_state.cost_usd
            else:
                # No state file exists yet
                task_dict = {
                    "task_id": task.task_id,
                    "task_text": task.task_text,
                    "status": _prd_status_to_task_status(task.status),  # From PRD file
                    "priority": task.priority,
                    "branch": None,
                    "base_branch": None,
                    "branch_reason": None,
                    "blocking_reason": None,
                    "resume_context": None,
                    "nelson_run_id": None,
                    "started_at": None,
                    "completed_at": None,
                    "blocked_at": None,
                    "cost_usd": 0.0,
                    "iterations": 0,
                    "phase": None,
                    "phase_name": None,
                }

            tasks_list.append(task_dict)

            # Count by status from PRD file
            if task.status == PRDTaskStatus.COMPLETED:
                completed_count += 1
            elif task.status == PRDTaskStatus.IN_PROGRESS:
                in_progress_count += 1
            elif task.status == PRDTaskStatus.BLOCKED:
                blocked_count += 1
            elif task.status == PRDTaskStatus.PENDING:
                pending_count += 1
            # Note: FAILED status doesn't have a marker in PRD file

        return {
            "prd_file": str(self.prd_file),
            "total_tasks": len(self.tasks),
            "completed": completed_count,
            "in_progress": in_progress_count,
            "blocked": blocked_count,
            "pending": pending_count,
            "failed": failed_count,
            "total_cost": total_cost,
            "tasks": tasks_list,
        }

    def get_task_info(self, task_id: str) -> dict[str, Any] | None:
        """Get detailed information about a specific task.

        Args:
            task_id: Task ID

        Returns:
            Dictionary with task details or None if not found
        """
        task = self.parser.get_task_by_id(task_id)
        if task is None:
            return None

        task_state_path = self.state_manager.get_task_state_path(task_id)
        if task_state_path.exists():
            task_state = self.state_manager.load_task_state(
                task_id, task.task_text, task.priority
            )
        else:
            # Task hasn't been started yet
            from nelson.prd_task_state import TaskState

            task_state = TaskState(
                task_id=task_id, task_text=task.task_text, priority=task.priority
            )

        return {
            "task_id": task_id,
            "task_text": task.task_text,
            "status": task_state.status.value,
            "priority": task.priority,
            "branch": task_state.branch,
            "base_branch": task_state.base_branch,
            "branch_reason": task_state.branch_reason,
            "nelson_run_id": task_state.nelson_run_id,
            "blocking_reason": task_state.blocking_reason,
            "resume_context": task_state.resume_context,
            "started_at": task_state.started_at,
            "completed_at": task_state.completed_at,
            "blocked_at": task_state.blocked_at,
            "cost_usd": task_state.cost_usd,
            "iterations": task_state.iterations,
            "phase": task_state.phase,
            "phase_name": task_state.phase_name,
        }
