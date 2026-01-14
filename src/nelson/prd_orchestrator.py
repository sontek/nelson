"""PRD orchestration engine for nelson-prd.

This module implements the main execution loop that orchestrates
multiple Nelson runs based on PRD tasks, handling priority-based
execution, branch management, cost tracking, and state transitions.
"""

import subprocess
from pathlib import Path
from typing import Any

from nelson.git_utils import GitError
from nelson.prd_branch import ensure_branch_for_task
from nelson.prd_parser import PRDParser, PRDTaskStatus
from nelson.prd_state import PRDStateManager
from nelson.state import NelsonState


class PRDOrchestrator:
    """Orchestrates Nelson execution across multiple PRD tasks."""

    def __init__(self, prd_file: Path, prd_dir: Path | None = None):
        """Initialize orchestrator.

        Args:
            prd_file: Path to PRD markdown file
            prd_dir: Path to .nelson/prd directory (default: .nelson/prd)
        """
        self.prd_file = prd_file
        self.prd_dir = prd_dir or Path(".nelson/prd")

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
        # Generate branch name and ensure it exists
        try:
            branch_name = ensure_branch_for_task(task_id, task_text)
        except GitError as e:
            print(f"Error creating/switching branch: {e}")
            return False

        # Load or create task state
        task_state = self.state_manager.load_task_state(task_id, task_text, priority)

        # Generate Nelson run ID
        from datetime import UTC, datetime
        run_id = datetime.now(UTC).strftime("nelson-%Y%m%d-%H%M%S")

        # Start task (updates state)
        task_state.start(run_id, branch_name)
        self.state_manager.save_task_state(task_state)

        # Update PRD file to in-progress
        self.parser.update_task_status(task_id, PRDTaskStatus.IN_PROGRESS)

        # Build Nelson command
        task_prompt = prompt or task_text

        # Prepend resume context if present
        if task_state.resume_context:
            task_prompt = f"RESUME CONTEXT: {task_state.resume_context}\n\n{task_prompt}"

        cmd = ["nelson", task_prompt]
        if nelson_args:
            cmd.extend(nelson_args)

        # Execute Nelson
        print(f"\n{'='*60}")
        print(f"🚀 Starting task: {task_id}")
        print(f"   Description: {task_text}")
        print(f"   Branch: {branch_name}")
        if task_state.resume_context:
            print("   🔄 Resuming with context")
        print(f"{'='*60}\n")

        try:
            result = subprocess.run(cmd, check=False)
            success = result.returncode == 0

            # Provide specific feedback for non-zero exit codes
            if not success:
                print(f"\nNelson exited with code {result.returncode}")
                if result.returncode == 1:
                    print("This usually indicates Nelson encountered an error during execution.")
                elif result.returncode == 130:
                    print("Task was interrupted (SIGINT/Ctrl+C).")
                else:
                    print(f"Unexpected exit code: {result.returncode}")
        except KeyboardInterrupt:
            print("\n\nTask interrupted by user (KeyboardInterrupt)")
            success = False
        except FileNotFoundError:
            print("\nError: 'nelson' command not found in PATH")
            print("Please ensure Nelson is installed and available in your PATH.")
            print("Install with: pip install nelson-cli")
            success = False
        except PermissionError as e:
            print(f"\nError: Permission denied when executing Nelson: {e}")
            print("Please check that the nelson command has execute permissions.")
            success = False
        except OSError as e:
            print(f"\nError: OS error when executing Nelson: {e}")
            print("This may indicate system-level issues (e.g., resource exhaustion).")
            success = False
        except Exception as e:
            print(f"\nUnexpected error executing Nelson: {type(e).__name__}: {e}")
            print("This is an unexpected error. Please report this issue.")
            success = False

        # Update task state based on result
        if success:
            # Try to read Nelson state for cost/iteration info
            nelson_state_path = Path(".nelson/runs") / run_id / "state.json"
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

            # Mark as completed
            task_state.complete()
            self.state_manager.save_task_state(task_state)

            # Update PRD file
            self.parser.update_task_status(task_id, PRDTaskStatus.COMPLETED)

            print(f"\n{'='*60}")
            print(f"✅ Task completed: {task_id}")
            print(f"   Cost: ${task_state.cost_usd:.2f}")
            print(f"   Iterations: {task_state.iterations}")
            if task_state.phase_name:
                print(f"   Final phase: {task_state.phase_name}")
            print(f"{'='*60}\n")
        else:
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
        prd_state = self.state_manager.prd_state
        task_states = self.state_manager.get_all_task_states()

        # Convert TaskState objects to dictionaries for iteration
        tasks_list = [state.to_dict() for state in task_states.values()]

        return {
            "prd_file": str(self.prd_file),
            "total_tasks": len(self.tasks),
            "completed": prd_state.completed_count,
            "in_progress": prd_state.in_progress_count,
            "blocked": prd_state.blocked_count,
            "pending": prd_state.pending_count,
            "failed": prd_state.failed_count,
            "total_cost": prd_state.total_cost_usd,
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
