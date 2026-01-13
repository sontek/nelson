"""Tests for circuit breaker detection."""

from nelson.circuit_breaker import CircuitBreaker, CircuitBreakerResult
from nelson.state import RalphState


class TestCircuitBreakerResult:
    """Tests for CircuitBreakerResult enum."""

    def test_enum_values(self) -> None:
        """Test that all expected enum values exist."""
        assert CircuitBreakerResult.OK.value == "ok"
        assert CircuitBreakerResult.EXIT_SIGNAL.value == "exit"
        assert CircuitBreakerResult.TRIGGERED.value == "triggered"


class TestCircuitBreakerExitSignal:
    """Tests for EXIT_SIGNAL detection."""

    def test_exit_signal_true(self) -> None:
        """Test that EXIT_SIGNAL=true returns EXIT_SIGNAL result."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=True,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="COMPLETE",
            recommendation="All done",
        )

        assert result == CircuitBreakerResult.EXIT_SIGNAL

    def test_exit_signal_false(self) -> None:
        """Test that EXIT_SIGNAL=false doesn't trigger EXIT_SIGNAL result."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=1,
            files_modified=1,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Continue",
        )

        assert result == CircuitBreakerResult.OK


class TestCircuitBreakerNoProgress:
    """Tests for no progress detection."""

    def test_single_iteration_no_progress(self) -> None:
        """Test that single iteration with no progress doesn't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Continue",
        )

        assert result == CircuitBreakerResult.OK
        assert state.no_progress_iterations == 1

    def test_two_iterations_no_progress(self) -> None:
        """Test that two iterations with no progress doesn't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        for _ in range(2):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="IN_PROGRESS",
                recommendation="Continue",
            )

        assert result == CircuitBreakerResult.OK
        assert state.no_progress_iterations == 2

    def test_three_iterations_no_progress(self) -> None:
        """Test that three iterations with no progress triggers circuit breaker."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        for _ in range(3):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="IN_PROGRESS",
                recommendation="Continue",
            )

        assert result == CircuitBreakerResult.TRIGGERED
        assert state.no_progress_iterations == 3

    def test_progress_resets_counter(self) -> None:
        """Test that making progress resets no_progress counter."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Two iterations with no progress
        for _ in range(2):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="IN_PROGRESS",
                recommendation="Continue",
            )

        assert state.no_progress_iterations == 2

        # One iteration with progress (tasks completed)
        result = breaker.check(
            exit_signal=False,
            tasks_completed=1,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Continue",
        )

        assert result == CircuitBreakerResult.OK
        assert state.no_progress_iterations == 0

    def test_files_modified_counts_as_progress(self) -> None:
        """Test that files_modified > 0 counts as progress."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=2,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Continue",
        )

        assert result == CircuitBreakerResult.OK
        assert state.no_progress_iterations == 0


class TestCircuitBreakerTestOnlyLoops:
    """Tests for test-only loop detection."""

    def test_single_test_iteration_no_files(self) -> None:
        """Test that single TESTING iteration with no files doesn't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="TESTING",
            status="IN_PROGRESS",
            recommendation="Running tests",
        )

        assert result == CircuitBreakerResult.OK
        assert state.test_only_loop_count == 1

    def test_two_test_iterations_no_files(self) -> None:
        """Test that two TESTING iterations with no files doesn't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        for _ in range(2):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="TESTING",
                status="IN_PROGRESS",
                recommendation="Running tests",
            )

        assert result == CircuitBreakerResult.OK
        assert state.test_only_loop_count == 2

    def test_three_test_iterations_no_files(self) -> None:
        """Test that three TESTING iterations with no files triggers."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        for _ in range(3):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="TESTING",
                status="IN_PROGRESS",
                recommendation="Running tests",
            )

        assert result == CircuitBreakerResult.TRIGGERED
        assert state.test_only_loop_count == 3

    def test_test_with_files_resets_counter(self) -> None:
        """Test that TESTING with files_modified resets counter."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Two TESTING iterations with no files
        for _ in range(2):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="TESTING",
                status="IN_PROGRESS",
                recommendation="Running tests",
            )

        assert state.test_only_loop_count == 2

        # One TESTING iteration WITH files
        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=1,
            work_type="TESTING",
            status="IN_PROGRESS",
            recommendation="Fixed test",
        )

        assert result == CircuitBreakerResult.OK
        assert state.test_only_loop_count == 0

    def test_non_testing_work_resets_counter(self) -> None:
        """Test that non-TESTING work type resets counter."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Two TESTING iterations with no files
        for _ in range(2):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="TESTING",
                status="IN_PROGRESS",
                recommendation="Running tests",
            )

        assert state.test_only_loop_count == 2

        # One IMPLEMENTATION iteration with progress to avoid no_progress trigger
        result = breaker.check(
            exit_signal=False,
            tasks_completed=1,
            files_modified=1,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Writing code",
        )

        assert result == CircuitBreakerResult.OK
        assert state.test_only_loop_count == 0


class TestCircuitBreakerRepeatedErrors:
    """Tests for repeated error detection."""

    def test_single_error(self) -> None:
        """Test that single error doesn't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="BLOCKED",
            recommendation="Import error encountered",
        )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 1

    def test_two_same_errors(self) -> None:
        """Test that two identical errors don't trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        error_msg = "Import error encountered"
        for _ in range(2):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="BLOCKED",
                recommendation=error_msg,
            )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 2

    def test_three_same_errors(self) -> None:
        """Test that three identical errors trigger circuit breaker."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        error_msg = "Import error encountered"
        for _ in range(3):
            result = breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="BLOCKED",
                recommendation=error_msg,
            )

        assert result == CircuitBreakerResult.TRIGGERED
        assert state.repeated_error_count == 3

    def test_different_errors_reset_counter(self) -> None:
        """Test that different error messages reset counter."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # First error
        breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="BLOCKED",
            recommendation="Import error",
        )

        assert state.repeated_error_count == 1

        # Different error
        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="BLOCKED",
            recommendation="Syntax error",
        )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 1

    def test_success_clears_errors(self) -> None:
        """Test that successful iteration clears error tracking."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Two errors
        for _ in range(2):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="BLOCKED",
                recommendation="Import error",
            )

        assert state.repeated_error_count == 2

        # Success
        result = breaker.check(
            exit_signal=False,
            tasks_completed=1,
            files_modified=1,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="Continue working",
        )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 0

    def test_error_in_recommendation_text(self) -> None:
        """Test that 'error' in recommendation triggers error tracking."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="IN_PROGRESS",
            recommendation="There was an error in the code",
        )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 1

    def test_blocked_status_triggers_error_tracking(self) -> None:
        """Test that BLOCKED status triggers error tracking."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        result = breaker.check(
            exit_signal=False,
            tasks_completed=0,
            files_modified=0,
            work_type="IMPLEMENTATION",
            status="BLOCKED",
            recommendation="Waiting for input",
        )

        assert result == CircuitBreakerResult.OK
        assert state.repeated_error_count == 1


class TestCircuitBreakerGetTriggerReason:
    """Tests for get_trigger_reason method."""

    def test_no_progress_reason(self) -> None:
        """Test reason string for no progress trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Trigger no progress
        for _ in range(3):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="IN_PROGRESS",
                recommendation="Continue",
            )

        reason = breaker.get_trigger_reason()
        assert "No progress detected" in reason
        assert "3 iterations" in reason

    def test_test_only_reason(self) -> None:
        """Test reason string for test-only loop trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Trigger test-only loop
        for _ in range(3):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="TESTING",
                status="IN_PROGRESS",
                recommendation="Running tests",
            )

        reason = breaker.get_trigger_reason()
        assert "Test-only loop detected" in reason
        assert "3 iterations" in reason

    def test_repeated_error_reason(self) -> None:
        """Test reason string for repeated error trigger."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        # Trigger repeated errors
        error_msg = "Import error"
        for _ in range(3):
            breaker.check(
                exit_signal=False,
                tasks_completed=0,
                files_modified=0,
                work_type="IMPLEMENTATION",
                status="BLOCKED",
                recommendation=error_msg,
            )

        reason = breaker.get_trigger_reason()
        assert "Repeated error detected" in reason
        assert "3 times" in reason

    def test_no_trigger_reason(self) -> None:
        """Test reason string when no trigger has occurred."""
        state = RalphState()
        breaker = CircuitBreaker(state)

        reason = breaker.get_trigger_reason()
        assert "unknown reason" in reason
