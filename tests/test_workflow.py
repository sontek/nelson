"""Tests for workflow orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nelson.config import RalphConfig
from nelson.phases import Phase
from nelson.providers.base import AIResponse, ProviderError
from nelson.state import NelsonState
from nelson.workflow import (
    CircuitBreakerResult,
    WorkflowError,
    WorkflowOrchestrator,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> RalphConfig:
    """Create mock configuration."""
    return RalphConfig(
        max_iterations=50,
        max_iterations_explicit=True,
        cost_limit=10.0,
        ralph_dir=tmp_path / ".ralph",
        audit_dir=tmp_path / ".ralph" / "audit",
        runs_dir=tmp_path / ".ralph" / "runs",
        claude_command="claude",
        claude_command_path=Path("claude"),
        model="sonnet",
        plan_model="sonnet",
        review_model="sonnet",
        auto_approve_push=False,
    )


@pytest.fixture
def mock_state() -> NelsonState:
    """Create mock state."""
    return NelsonState(
        prompt="Test prompt",
        current_phase=1,
        total_iterations=0,
        phase_iterations=0,
    )


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create mock AI provider."""
    provider = MagicMock()
    provider.execute.return_value = AIResponse(
        content="Response with status block\n"
        "---RALPH_STATUS---\n"
        "STATUS: COMPLETE\n"
        "TASKS_COMPLETED_THIS_LOOP: 1\n"
        "FILES_MODIFIED: 2\n"
        "TESTS_STATUS: PASSING\n"
        "WORK_TYPE: IMPLEMENTATION\n"
        "EXIT_SIGNAL: true\n"
        "RECOMMENDATION: All done\n"
        "---END_RALPH_STATUS---",
        raw_output="raw",
        metadata={},
        is_error=False,
    )
    provider.extract_status_block.return_value = {
        "status": "COMPLETE",
        "tasks_completed": 1,
        "files_modified": 2,
        "tests_status": "PASSING",
        "work_type": "IMPLEMENTATION",
        "exit_signal": True,
        "recommendation": "All done",
    }
    provider.get_cost.return_value = 0.0
    return provider


@pytest.fixture
def mock_run_dir(tmp_path: Path) -> Path:
    """Create mock run directory."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    return run_dir


@pytest.fixture
def orchestrator(
    mock_config: RalphConfig,
    mock_state: NelsonState,
    mock_provider: MagicMock,
    mock_run_dir: Path,
) -> WorkflowOrchestrator:
    """Create workflow orchestrator with mocks."""
    return WorkflowOrchestrator(
        config=mock_config,
        state=mock_state,
        provider=mock_provider,
        run_dir=mock_run_dir,
    )


class TestWorkflowOrchestratorInitialization:
    """Tests for workflow orchestrator initialization."""

    def test_initialization(
        self,
        mock_config: RalphConfig,
        mock_state: NelsonState,
        mock_provider: MagicMock,
        mock_run_dir: Path,
    ) -> None:
        """Test orchestrator initialization."""
        orchestrator = WorkflowOrchestrator(
            config=mock_config,
            state=mock_state,
            provider=mock_provider,
            run_dir=mock_run_dir,
        )

        assert orchestrator.config == mock_config
        assert orchestrator.state == mock_state
        assert orchestrator.provider == mock_provider
        assert orchestrator.run_dir == mock_run_dir
        assert orchestrator.plan_file == mock_run_dir / "plan.md"
        assert orchestrator.decisions_file == mock_run_dir / "decisions.md"
        assert orchestrator.last_output_file == mock_run_dir / "last_output.txt"


class TestLimitChecking:
    """Tests for limit checking."""

    def test_check_limits_within_limits(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test limit checking when within limits."""
        orchestrator.state.cycle_iterations = 5
        orchestrator.state.cost_usd = 5.0

        assert orchestrator._check_limits() is True

    def test_check_limits_iteration_limit_reached(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test limit checking when cycle limit reached."""
        orchestrator.state.cycle_iterations = 50

        assert orchestrator._check_limits() is False

    def test_check_limits_cost_limit_reached(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test limit checking when cost limit reached."""
        orchestrator.state.cost_usd = 10.0

        assert orchestrator._check_limits() is False


class TestPromptBuilding:
    """Tests for prompt building."""

    def test_read_plan_file_exists(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test reading plan file when it exists."""
        orchestrator.plan_file.write_text("# Plan\n- [x] Task 1\n- [ ] Task 2")

        content = orchestrator._read_plan_file()

        assert "# Plan" in content
        assert "- [x] Task 1" in content
        assert "- [ ] Task 2" in content

    def test_read_plan_file_does_not_exist(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test reading plan file when it doesn't exist."""
        content = orchestrator._read_plan_file()

        assert content == ""

    def test_build_loop_context(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test building loop context."""
        orchestrator.state.total_iterations = 5
        orchestrator.state.phase_iterations = 2
        orchestrator.plan_file.write_text("- [x] Task 1\n- [x] Task 2\n- [ ] Task 3")
        orchestrator.decisions_file.write_text("Decision 1\nDecision 2")

        context = orchestrator._build_loop_context()

        assert "5" in context  # total_iterations
        assert "2" in context  # phase_iterations


class TestProviderExecution:
    """Tests for provider execution."""

    def test_execute_provider_plan_phase(
        self,
        mock_state: NelsonState,
        mock_provider: MagicMock,
        mock_run_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test provider execution in PLAN phase uses plan_model."""
        # Create config with opus for plan_model
        config = RalphConfig(
            max_iterations=50,
            max_iterations_explicit=True,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("claude"),
            model="sonnet",
            plan_model="opus",
            review_model="sonnet",
            auto_approve_push=False,
        )
        orchestrator = WorkflowOrchestrator(config, mock_state, mock_provider, mock_run_dir)
        orchestrator.state.current_phase = Phase.PLAN.value

        orchestrator._execute_provider("prompt", Phase.PLAN)

        # Verify plan_model was used
        call_args = orchestrator.provider.execute.call_args
        assert call_args[1]["model"] == "opus"

    def test_execute_provider_review_phase(
        self,
        mock_state: NelsonState,
        mock_provider: MagicMock,
        mock_run_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test provider execution in REVIEW phase uses review_model."""
        # Create config with opus for review_model
        config = RalphConfig(
            max_iterations=50,
            max_iterations_explicit=True,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="opus",
            auto_approve_push=False,
        )
        orchestrator = WorkflowOrchestrator(config, mock_state, mock_provider, mock_run_dir)

        orchestrator._execute_provider("prompt", Phase.REVIEW)

        # Verify review_model was used
        call_args = orchestrator.provider.execute.call_args
        assert call_args[1]["model"] == "opus"

    def test_execute_provider_other_phase(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test provider execution in other phases uses default model."""
        orchestrator._execute_provider("prompt", Phase.IMPLEMENT)

        # Verify default model was used
        call_args = orchestrator.provider.execute.call_args
        assert call_args[1]["model"] == "sonnet"


class TestCircuitBreaker:
    """Tests for circuit breaker logic."""

    def test_circuit_breaker_exit_signal(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test circuit breaker detects EXIT_SIGNAL."""
        status_block = {
            "exit_signal": True,
            "tasks_completed": 1,
            "files_modified": 1,
        }

        result = orchestrator._check_circuit_breaker(status_block)

        assert result == CircuitBreakerResult.EXIT_SIGNAL

    def test_circuit_breaker_no_progress(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test circuit breaker detects no progress."""
        status_block = {
            "exit_signal": False,
            "tasks_completed": 0,
            "files_modified": 0,
        }

        # Trigger 3 times to activate circuit breaker
        orchestrator._check_circuit_breaker(status_block)
        orchestrator._check_circuit_breaker(status_block)
        result = orchestrator._check_circuit_breaker(status_block)

        assert result == CircuitBreakerResult.TRIGGERED

    def test_circuit_breaker_test_only_loop(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test circuit breaker detects test-only loops."""
        status_block = {
            "exit_signal": False,
            "tasks_completed": 0,
            "files_modified": 0,
            "work_type": "TESTING",
        }

        # Trigger 3 times
        orchestrator._check_circuit_breaker(status_block)
        orchestrator._check_circuit_breaker(status_block)
        result = orchestrator._check_circuit_breaker(status_block)

        assert result == CircuitBreakerResult.TRIGGERED

    def test_circuit_breaker_repeated_error(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test circuit breaker detects repeated errors."""
        status_block = {
            "exit_signal": False,
            "tasks_completed": 1,
            "files_modified": 1,
            "status": "BLOCKED",
            "recommendation": "Same error message",
        }

        # Trigger 3 times with same error
        orchestrator._check_circuit_breaker(status_block)
        orchestrator._check_circuit_breaker(status_block)
        result = orchestrator._check_circuit_breaker(status_block)

        assert result == CircuitBreakerResult.TRIGGERED

    def test_circuit_breaker_ok(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test circuit breaker returns OK when no issues."""
        status_block = {
            "exit_signal": False,
            "tasks_completed": 1,
            "files_modified": 2,
            "work_type": "IMPLEMENTATION",
            "status": "IN_PROGRESS",
            "recommendation": "Continue working",
        }

        result = orchestrator._check_circuit_breaker(status_block)

        assert result == CircuitBreakerResult.OK


class TestPhaseTransition:
    """Tests for phase transition logic."""

    def test_log_phase_transition(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test logging phase transition."""
        orchestrator.state.total_iterations = 5

        orchestrator._log_phase_transition(Phase.PLAN, Phase.IMPLEMENT)

        # Verify decisions file was updated
        content = orchestrator.decisions_file.read_text()
        assert "Phase Transition" in content
        assert "From**: Phase 1 (PLAN)" in content
        assert "To**: Phase 2" in content


class TestWorkflowRun:
    """Tests for main workflow run."""

    def test_run_with_exit_signal(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test workflow run that completes via EXIT_SIGNAL."""
        # Provider already set up to return EXIT_SIGNAL in fixture
        orchestrator.plan_file.write_text("# Plan\n- [x] Task 1")

        # Run should complete without error
        orchestrator.run("Test prompt")

        # Verify provider was called
        assert orchestrator.provider.execute.called

    def test_run_with_iteration_limit(
        self,
        mock_state: NelsonState,
        mock_provider: MagicMock,
        mock_run_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test workflow run that hits iteration limit."""
        # Create config with low limit
        config = RalphConfig(
            max_iterations=2,
            max_iterations_explicit=True,
            cost_limit=10.0,
            ralph_dir=tmp_path / ".ralph",
            audit_dir=tmp_path / ".ralph" / "audit",
            runs_dir=tmp_path / ".ralph" / "runs",
            claude_command="claude",
            claude_command_path=Path("claude"),
            model="sonnet",
            plan_model="sonnet",
            review_model="sonnet",
            auto_approve_push=False,
        )

        # Set state to be exactly at cycle limit (will fail on next _check_limits call)
        mock_state.cycle_iterations = 2

        # Provider returns no EXIT_SIGNAL
        mock_provider.extract_status_block.return_value = {
            "status": "IN_PROGRESS",
            "tasks_completed": 1,
            "files_modified": 1,
            "tests_status": "NOT_RUN",
            "work_type": "IMPLEMENTATION",
            "exit_signal": False,
            "recommendation": "Continue",
        }

        orchestrator = WorkflowOrchestrator(config, mock_state, mock_provider, mock_run_dir)
        orchestrator.plan_file.write_text("# Plan\n- [ ] Task 1")

        # Should raise WorkflowError when cycle limit is reached
        with pytest.raises(WorkflowError, match="Stopping due to limits"):
            orchestrator.run("Test prompt")

    def test_run_with_provider_error(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test workflow run with provider error."""
        orchestrator.provider.execute.side_effect = ProviderError(
            "Provider failed", is_retryable=False
        )

        with pytest.raises(WorkflowError, match="Claude execution failed"):
            orchestrator.run("Test prompt")

    def test_run_saves_output(self, orchestrator: WorkflowOrchestrator) -> None:
        """Test workflow run saves output to file."""
        orchestrator.plan_file.write_text("# Plan\n- [x] Task 1")

        orchestrator.run("Test prompt")

        # Verify last_output.txt was created
        assert orchestrator.last_output_file.exists()
        content = orchestrator.last_output_file.read_text()
        assert "RALPH_STATUS" in content


class TestWorkflowError:
    """Tests for WorkflowError exception."""

    def test_workflow_error_creation(self) -> None:
        """Test creating WorkflowError."""
        error = WorkflowError("Test error")

        assert str(error) == "Test error"
        assert isinstance(error, Exception)
