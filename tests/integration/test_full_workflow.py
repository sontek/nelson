"""Integration tests for complete Nelson workflow execution.

Tests the full workflow components working together with mocked AI provider.
These tests verify the workflow can be initialized and basic integration points work.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nelson.config import NelsonConfig
from nelson.phases import Phase
from nelson.providers.base import AIProvider, AIResponse
from nelson.run_manager import RunManager
from nelson.state import NelsonState
from nelson.workflow import WorkflowError, WorkflowOrchestrator


@pytest.fixture
def mock_config(tmp_path: Path) -> NelsonConfig:
    """Create test configuration with temp directories."""
    nelson_dir = tmp_path / ".nelson"
    return NelsonConfig(
        max_iterations=10,
        max_iterations_explicit=True,
        cost_limit=10.0,
        nelson_dir=nelson_dir,
        audit_dir=nelson_dir / "audit",
        runs_dir=nelson_dir / "runs",
        claude_command="claude",
        claude_command_path=Path("/usr/bin/claude"),
        model="claude-sonnet-4-20250514",
        plan_model="claude-sonnet-4-20250514",
        review_model="claude-sonnet-4-20250514",
        auto_approve_push=False,
        stall_timeout_minutes=15.0,
    )


@pytest.fixture
def mock_run_manager(tmp_path: Path, mock_config: NelsonConfig) -> RunManager:
    """Create test run manager with temp directory."""
    run_mgr = RunManager(mock_config, run_id="test-20260113-120000")
    run_mgr.create_run_directory()
    return run_mgr


@pytest.fixture
def sample_plan_file(mock_run_manager: RunManager) -> Path:
    """Create sample plan file for testing with all tasks completed."""
    plan_path = mock_run_manager.get_plan_path()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """# Test Plan

## Phase 1: PLAN
- [x] Create initial plan

## Phase 2: IMPLEMENT
- [x] Implement feature A
- [x] Implement feature B

## Phase 3: REVIEW
- [x] Review implementation

## Phase 4: TEST
- [x] Run tests

## Phase 5: FINAL-REVIEW
- [x] Final checks

## Phase 6: COMMIT
- [x] Create commit
"""
    )
    return plan_path


class TestWorkflowIntegration:
    """Integration tests for workflow orchestrator."""

    def test_workflow_initialization(
        self, mock_config: NelsonConfig, mock_run_manager: RunManager, sample_plan_file: Path
    ) -> None:
        """Test workflow can be initialized with all components."""
        # Create mock provider
        mock_provider = MagicMock(spec=AIProvider)

        # Create state
        state = NelsonState(current_phase=Phase.PLAN.value)
        state.save(mock_run_manager.get_state_path())

        # Create workflow orchestrator
        workflow = WorkflowOrchestrator(
            config=mock_config,
            state=state,
            provider=mock_provider,
            run_dir=mock_run_manager.run_dir,
        )

        # Verify initialization
        assert workflow.config == mock_config
        assert workflow.state == state
        assert workflow.provider == mock_provider
        assert workflow.run_dir == mock_run_manager.run_dir
        assert workflow.plan_file == mock_run_manager.run_dir / "plan.md"
        assert workflow.decisions_file == mock_run_manager.run_dir / "decisions.md"
        assert workflow.last_output_file == mock_run_manager.run_dir / "last_output.txt"

    def test_workflow_calls_provider(
        self, mock_config: NelsonConfig, mock_run_manager: RunManager, sample_plan_file: Path
    ) -> None:
        """Test workflow calls AI provider with correct parameters."""
        # Create mock provider that exits after first call
        mock_provider = MagicMock(spec=AIProvider)
        mock_provider.execute.return_value = AIResponse(
            content="Response",
            raw_output="raw",
            metadata={},
        )
        # Return EXIT_SIGNAL=true to exit after one iteration
        mock_provider.extract_status_block.return_value = {
            "status": "COMPLETE",
            "tasks_completed": 1,
            "files_modified": 1,
            "tests_status": "NOT_RUN",
            "work_type": "IMPLEMENTATION",
            "exit_signal": True,  # Exit immediately
            "recommendation": "Complete",
        }
        mock_provider.get_cost.return_value = 0.0

        # Create state
        state = NelsonState(current_phase=Phase.IMPLEMENT.value)
        state.save(mock_run_manager.get_state_path())

        # Set low iteration limit to exit quickly if EXIT_SIGNAL doesn't work
        mock_config = NelsonConfig(
            max_iterations=1,
            max_iterations_explicit=True,
            cost_limit=mock_config.cost_limit,
            stall_timeout_minutes=mock_config.stall_timeout_minutes,
            nelson_dir=mock_config.nelson_dir,
            audit_dir=mock_config.audit_dir,
            runs_dir=mock_config.runs_dir,
            claude_command=mock_config.claude_command,
            claude_command_path=mock_config.claude_command_path,
            model=mock_config.model,
            plan_model=mock_config.plan_model,
            review_model=mock_config.review_model,
            auto_approve_push=mock_config.auto_approve_push,
        )

        # Create workflow orchestrator
        workflow = WorkflowOrchestrator(
            config=mock_config,
            state=state,
            provider=mock_provider,
            run_dir=mock_run_manager.run_dir,
        )

        # Run workflow - will hit max cycles after completing cycle 0
        try:
            workflow.run(prompt="Test task")
        except WorkflowError as e:
            # Expected - should hit limits after completing first cycle
            assert "stopping due to limits" in str(e).lower()

        # Verify provider was called
        assert mock_provider.execute.called
        assert mock_provider.extract_status_block.called

    def test_workflow_saves_provider_output(
        self, mock_config: NelsonConfig, mock_run_manager: RunManager, sample_plan_file: Path
    ) -> None:
        """Test workflow saves provider output to last_output.txt."""
        output_content = "This is the provider output that should be saved"

        mock_provider = MagicMock(spec=AIProvider)
        mock_provider.execute.return_value = AIResponse(
            content=output_content,
            raw_output=output_content,
            metadata={},
        )
        # Return EXIT_SIGNAL=true to exit after one call
        mock_provider.extract_status_block.return_value = {
            "status": "COMPLETE",
            "tasks_completed": 1,
            "files_modified": 1,
            "tests_status": "NOT_RUN",
            "work_type": "IMPLEMENTATION",
            "exit_signal": True,  # Exit immediately
            "recommendation": "Complete",
        }
        mock_provider.get_cost.return_value = 0.0

        # Create state with low iteration count to stop quickly
        state = NelsonState(current_phase=Phase.IMPLEMENT.value)
        state.save(mock_run_manager.get_state_path())

        # Set low iteration limit
        mock_config = NelsonConfig(
            max_iterations=1,
            max_iterations_explicit=True,
            cost_limit=mock_config.cost_limit,
            stall_timeout_minutes=mock_config.stall_timeout_minutes,
            nelson_dir=mock_config.nelson_dir,
            audit_dir=mock_config.audit_dir,
            runs_dir=mock_config.runs_dir,
            claude_command=mock_config.claude_command,
            claude_command_path=mock_config.claude_command_path,
            model=mock_config.model,
            plan_model=mock_config.plan_model,
            review_model=mock_config.review_model,
            auto_approve_push=mock_config.auto_approve_push,
        )

        # Create workflow orchestrator
        workflow = WorkflowOrchestrator(
            config=mock_config,
            state=state,
            provider=mock_provider,
            run_dir=mock_run_manager.run_dir,
        )

        # Run workflow - will hit max cycles after completing cycle 0
        try:
            workflow.run(prompt="Test task")
        except WorkflowError as e:
            # Expected - should hit limits after completing first cycle
            assert "stopping due to limits" in str(e).lower()

        # Verify output was saved
        output_path = mock_run_manager.run_dir / "last_output.txt"
        assert output_path.exists()
        saved_content = output_path.read_text()
        assert output_content == saved_content

    def test_workflow_saves_state(
        self, mock_config: NelsonConfig, mock_run_manager: RunManager, sample_plan_file: Path
    ) -> None:
        """Test workflow saves state after execution."""
        mock_provider = MagicMock(spec=AIProvider)
        mock_provider.execute.return_value = AIResponse(
            content="Response",
            raw_output="raw",
            metadata={},
        )
        mock_provider.extract_status_block.return_value = {
            "status": "COMPLETE",
            "tasks_completed": 1,
            "files_modified": 1,
            "tests_status": "NOT_RUN",
            "work_type": "IMPLEMENTATION",
            "exit_signal": True,  # Exit immediately
            "recommendation": "Complete",
        }
        mock_provider.get_cost.return_value = 0.0

        # Create state
        state = NelsonState(current_phase=Phase.IMPLEMENT.value)
        state.save(mock_run_manager.get_state_path())

        # Set low iteration limit
        mock_config = NelsonConfig(
            max_iterations=1,
            max_iterations_explicit=True,
            cost_limit=mock_config.cost_limit,
            stall_timeout_minutes=mock_config.stall_timeout_minutes,
            nelson_dir=mock_config.nelson_dir,
            audit_dir=mock_config.audit_dir,
            runs_dir=mock_config.runs_dir,
            claude_command=mock_config.claude_command,
            claude_command_path=mock_config.claude_command_path,
            model=mock_config.model,
            plan_model=mock_config.plan_model,
            review_model=mock_config.review_model,
            auto_approve_push=mock_config.auto_approve_push,
        )

        # Create workflow orchestrator
        workflow = WorkflowOrchestrator(
            config=mock_config,
            state=state,
            provider=mock_provider,
            run_dir=mock_run_manager.run_dir,
        )

        # Run workflow - will hit max cycles after completing cycle 0
        try:
            workflow.run(prompt="Test task")
        except WorkflowError as e:
            # Expected - should hit limits after completing first cycle
            assert "stopping due to limits" in str(e).lower()

        # Verify state file was created (in run directory, not nelson_dir)
        state_file = mock_run_manager.run_dir / "state.json"
        assert state_file.exists()
        # Verify state was saved with some iterations
        final_state = NelsonState.load(state_file)
        assert final_state.total_iterations >= 1

    def test_workflow_uses_phase_specific_models(
        self, mock_config: NelsonConfig, mock_run_manager: RunManager, sample_plan_file: Path
    ) -> None:
        """Test workflow uses different models for different phases."""
        # Configure phase-specific models
        mock_config = NelsonConfig(
            max_iterations=1,
            max_iterations_explicit=True,
            cost_limit=mock_config.cost_limit,
            stall_timeout_minutes=mock_config.stall_timeout_minutes,
            nelson_dir=mock_config.nelson_dir,
            audit_dir=mock_config.audit_dir,
            runs_dir=mock_config.runs_dir,
            claude_command=mock_config.claude_command,
            claude_command_path=mock_config.claude_command_path,
            model="claude-sonnet-4",
            plan_model="claude-opus-4",
            review_model="claude-sonnet-3.7",
            auto_approve_push=mock_config.auto_approve_push,
        )

        # Create mock provider
        mock_provider = MagicMock(spec=AIProvider)
        mock_provider.execute.return_value = AIResponse(
            content="Response",
            raw_output="raw",
            metadata={},
        )
        mock_provider.extract_status_block.return_value = {
            "status": "COMPLETE",
            "tasks_completed": 0,
            "files_modified": 0,
            "tests_status": "NOT_RUN",
            "work_type": "PLANNING",
            "exit_signal": True,  # Exit immediately
            "recommendation": "Complete",
        }
        mock_provider.get_cost.return_value = 0.0

        # Create state in PLAN phase
        state = NelsonState(current_phase=Phase.PLAN.value)
        state.save(mock_run_manager.get_state_path())

        # Create workflow orchestrator
        workflow = WorkflowOrchestrator(
            config=mock_config,
            state=state,
            provider=mock_provider,
            run_dir=mock_run_manager.run_dir,
        )

        # Run workflow
        try:
            workflow.run(prompt="Test task")
        except WorkflowError:
            pass  # Expected - hit iteration limit

        # Verify PLAN phase used plan_model
        assert mock_provider.execute.called
        # Check the FIRST call (Phase 1/PLAN), not the last call
        first_call_kwargs = mock_provider.execute.call_args_list[0].kwargs
        assert first_call_kwargs["model"] == "claude-opus-4"
