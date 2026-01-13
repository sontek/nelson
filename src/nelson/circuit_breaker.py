"""Circuit breaker detection for Ralph workflow.

This module provides circuit breaker logic to prevent runaway loops in the Ralph
workflow. It detects various stagnation conditions and signals when to halt execution.

Circuit breaker conditions:
1. No progress: 3+ iterations with 0 tasks completed and 0 files modified
2. Test-only loops: 3+ consecutive TESTING iterations with no file changes
3. Repeated errors: Same error pattern occurring 3+ times consecutively
"""

from __future__ import annotations

from enum import Enum

from nelson.state import NelsonState


class CircuitBreakerResult(Enum):
    """Result of circuit breaker check."""

    OK = "ok"  # No issues, continue
    EXIT_SIGNAL = "exit"  # EXIT_SIGNAL=true from status block
    TRIGGERED = "triggered"  # Circuit breaker activated


class CircuitBreaker:
    """Circuit breaker for detecting workflow stagnation.

    The circuit breaker monitors progress and error patterns to detect when
    Ralph is stuck in an unproductive loop. It tracks:
    - Progress (tasks completed, files modified)
    - Test-only loops (TESTING work with no file changes)
    - Repeated errors (same error pattern multiple times)
    """

    def __init__(self, state: NelsonState) -> None:
        """Initialize circuit breaker.

        Args:
            state: Ralph state for tracking metrics
        """
        self.state = state

    def check(
        self,
        exit_signal: bool,
        tasks_completed: int,
        files_modified: int,
        work_type: str,
        status: str,
        recommendation: str,
    ) -> CircuitBreakerResult:
        """Check for circuit breaker conditions.

        Args:
            exit_signal: EXIT_SIGNAL from status block
            tasks_completed: Number of tasks completed this iteration
            files_modified: Number of files modified this iteration
            work_type: Work type from status block (IMPLEMENTATION, TESTING, etc.)
            status: Status from status block (IN_PROGRESS, COMPLETE, BLOCKED)
            recommendation: Recommendation text from status block

        Returns:
            CircuitBreakerResult indicating what action to take
        """
        # Check for EXIT_SIGNAL first (normal completion)
        if exit_signal:
            return CircuitBreakerResult.EXIT_SIGNAL

        # Update state tracking for all circuit breaker conditions
        # This must happen before checks so counters are accurate

        # Track test-only loops (3+ consecutive TESTING with no file changes)
        if work_type == "TESTING" and files_modified == 0:
            self.state.test_only_loop_count += 1
        else:
            self.state.test_only_loop_count = 0

        # Track repeated errors (same pattern 3+ times)
        if "error" in recommendation.lower() or "blocked" in status.lower():
            self.state.record_error(recommendation)
        else:
            # Clear error tracking if no error this iteration
            self.state.last_error_message = ""
            self.state.repeated_error_count = 0

        # Track no progress (3+ iterations with 0 tasks, 0 files)
        # Note: record_progress expects cumulative task count, not delta
        # For now we track by bool since we don't have cumulative count
        if tasks_completed == 0 and files_modified == 0:
            self.state.no_progress_iterations += 1
        else:
            self.state.no_progress_iterations = 0

        # Now check circuit breaker conditions in priority order
        # Check test-only loops first (most specific)
        if self.state.test_only_loop_count >= 3:
            return CircuitBreakerResult.TRIGGERED

        # Check repeated errors second
        if self.state.repeated_error_count >= 3:
            return CircuitBreakerResult.TRIGGERED

        # Check no progress last (least specific)
        if self.state.no_progress_iterations >= 3:
            return CircuitBreakerResult.TRIGGERED

        # No circuit breaker conditions met
        return CircuitBreakerResult.OK

    def get_trigger_reason(self) -> str:
        """Get human-readable reason for circuit breaker trigger.

        Returns:
            Description of why circuit breaker was triggered
        """
        # Check in same priority order as check() method
        if self.state.test_only_loop_count >= 3:
            return (
                f"Test-only loop detected ({self.state.test_only_loop_count} iterations "
                "of TESTING with no file changes)"
            )
        elif self.state.repeated_error_count >= 3:
            return (
                f"Repeated error detected "
                f"(same error pattern {self.state.repeated_error_count} times)"
            )
        elif self.state.no_progress_iterations >= 3:
            return (
                f"No progress detected for {self.state.no_progress_iterations} iterations "
                "(0 tasks completed, 0 files modified)"
            )
        else:
            return "Circuit breaker triggered (unknown reason)"
