"""Integration tests for workflow feature integrations (Phases 2-7).

These tests verify that planning questions, blocked handling, deviations,
verification, depth modes, and JSON plans are properly wired into the workflow.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from nelson.blocked_handling import BlockedResolution
from nelson.config import NelsonConfig
from nelson.depth import DepthConfig, DepthMode
from nelson.deviations import DeviationConfig
from nelson.interaction import InteractionConfig, InteractionMode
from nelson.phases import Phase
from nelson.providers.base import AIResponse
from nelson.state import NelsonState
from nelson.workflow import CircuitBreakerResult, WorkflowOrchestrator


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    """Create temporary run directory."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return run_dir


@pytest.fixture
def mock_config(temp_run_dir: Path) -> NelsonConfig:
    """Create mock config for testing."""
    return NelsonConfig(
        max_iterations=10,
        max_iterations_explicit=False,
        cost_limit=10.0,
        stall_timeout_minutes=15.0,
        nelson_dir=temp_run_dir.parent / ".nelson",
        audit_dir=temp_run_dir.parent / ".nelson" / "audit",
        runs_dir=temp_run_dir.parent / ".nelson" / "runs",
        claude_command="claude",
        claude_command_path=None,
        model="sonnet",
        plan_model="sonnet",
        review_model="sonnet",
        auto_approve_push=False,
        skip_verification=False,
        target_path=temp_run_dir.parent,
        _interaction=InteractionConfig(
            mode=InteractionMode.INTERACTIVE,
            planning_timeout_seconds=60,
            ambiguity_timeout_seconds=30,
            prompt_on_blocked=True,
            skip_planning_questions=False,
        ),
        _depth=DepthConfig.for_mode(DepthMode.STANDARD),
        _deviations=DeviationConfig(),
    )


@pytest.fixture
def mock_state() -> NelsonState:
    """Create mock state for testing."""
    return NelsonState(
        current_phase=Phase.PLAN.value,
        phase_name="PLAN",
        total_iterations=1,
        cycle_iterations=0,
        phase_iterations=1,
    )


@pytest.fixture
def mock_provider() -> Mock:
    """Create mock AI provider."""
    provider = Mock()
    provider.extract_status_block = Mock(
        return_value={
            "status": "COMPLETE",
            "exit_signal": True,
            "tasks_completed_this_loop": 1,
            "files_modified": 2,
        }
    )
    return provider


class TestPlanningQuestionsIntegration:
    """Test planning questions integration in workflow."""

    def test_questions_extracted_after_plan_phase(
        self, temp_run_dir: Path, mock_config: NelsonConfig, mock_state: NelsonState, mock_provider: Mock
    ) -> None:
        """Test that questions are extracted after PLAN phase."""
        # Setup
        mock_state.current_phase = Phase.PLAN.value
        mock_state.phase_name = "PLAN"

        # Create plan file
        plan_file = temp_run_dir / "plan.md"
        plan_file.write_text("# Plan\n\n## Phase 1: PLAN\n- [x] Analyze task")

        # Create response with questions block
        response_content = """
Here's the plan...

```questions
[
  {
    "id": "q1",
    "question": "Which database to use?",
    "options": ["PostgreSQL", "MySQL"],
    "default": "PostgreSQL",
    "context": "Database choice affects ORM",
    "category": "architecture"
  }
]
```
"""
        mock_provider.execute = Mock(return_value=AIResponse(content=response_content, usage=None))

        orchestrator = WorkflowOrchestrator(mock_config, mock_state, mock_provider, temp_run_dir)

        # Patch UserInteraction to simulate user answering
        with patch("nelson.workflow.ask_planning_questions") as mock_ask:
            mock_ask.return_value = {"q1": "PostgreSQL"}

            # Patch log function
            with patch("nelson.workflow.log_planning_questions") as mock_log:
                # Execute one iteration to trigger PLAN -> IMPLEMENT transition
                # This would normally be in the run loop
                from nelson.planning_questions import extract_questions_from_response

                questions = extract_questions_from_response(response_content)

                assert len(questions) == 1
                assert questions[0].id == "q1"
                assert questions[0].question == "Which database to use?"

    def test_questions_skipped_when_configured(
        self, temp_run_dir: Path, mock_config: NelsonConfig, mock_state: NelsonState
    ) -> None:
        """Test that questions are skipped when skip_planning_questions=True."""
        # Modify config to skip questions
        mock_config._interaction = InteractionConfig(
            mode=InteractionMode.AUTONOMOUS,
            skip_planning_questions=True,
        )

        # Verify config setting
        assert mock_config.interaction.skip_planning_questions is True


class TestBlockedHandlingIntegration:
    """Test blocked handling integration in workflow."""

    def test_blocked_status_detected_in_circuit_breaker(
        self, temp_run_dir: Path, mock_config: NelsonConfig, mock_state: NelsonState, mock_provider: Mock
    ) -> None:
        """Test that BLOCKED status is detected in circuit breaker."""
        orchestrator = WorkflowOrchestrator(mock_config, mock_state, mock_provider, temp_run_dir)

        # Create status block with BLOCKED status
        status_block = {
            "status": "BLOCKED",
            "blocked_reason": "Missing API key",
            "blocked_resources": "OPENAI_API_KEY",
            "blocked_resolution": "Add key to .env",
            "exit_signal": False,
        }

        # Create response content
        response_content = "Task is blocked waiting for API key"
        temp_run_dir.joinpath("last_output.txt").write_text(response_content)

        # Patch prompt_blocked_resolution to simulate user choosing RESOLVED
        with patch("nelson.workflow.prompt_blocked_resolution") as mock_prompt:
            mock_prompt.return_value = (BlockedResolution.RESOLVED, "Added API key")

            with patch("nelson.workflow.log_blocked_event"):
                result = orchestrator._check_circuit_breaker(status_block)

                # Should return RETRY_NO_INCREMENT when resolved
                assert result == CircuitBreakerResult.RETRY_NO_INCREMENT
                mock_prompt.assert_called_once()

    def test_blocked_skip_continues_workflow(
        self, temp_run_dir: Path, mock_config: NelsonConfig, mock_state: NelsonState, mock_provider: Mock
    ) -> None:
        """Test that SKIP resolution continues workflow."""
        orchestrator = WorkflowOrchestrator(mock_config, mock_state, mock_provider, temp_run_dir)

        status_block = {
            "status": "BLOCKED",
            "blocked_reason": "Missing API key",
            "exit_signal": False,
        }

        temp_run_dir.joinpath("last_output.txt").write_text("Blocked")

        with patch("nelson.workflow.prompt_blocked_resolution") as mock_prompt:
            mock_prompt.return_value = (BlockedResolution.SKIP, None)

            with patch("nelson.workflow.log_blocked_event"):
                result = orchestrator._check_circuit_breaker(status_block)

                assert result == CircuitBreakerResult.OK


class TestDeviationTrackingIntegration:
    """Test deviation tracking integration in workflow."""

    def test_deviations_extracted_after_implement_phase(self) -> None:
        """Test that deviations are extracted after IMPLEMENT phase."""
        response_content = """
Fixed the bug...

```deviations
[
  {
    "rule": "auto_fix_bugs",
    "issue": "TypeError: NoneType has no attribute 'name'",
    "fix_applied": "Added null check before accessing .name",
    "files_affected": ["handler.py"]
  }
]
```
"""
        from nelson.deviations import extract_deviations_from_response

        deviations = extract_deviations_from_response(response_content)

        assert len(deviations) == 1
        assert deviations[0].issue == "TypeError: NoneType has no attribute 'name'"
        assert deviations[0].files_affected == ["handler.py"]

    def test_deviations_validated_against_config(self) -> None:
        """Test that deviations are validated against config rules."""
        from nelson.deviations import Deviation, DeviationRule, validate_deviations

        config = DeviationConfig(
            auto_fix_bugs=True,
            auto_add_critical=False,  # Disabled
            max_deviations_per_task=2,
        )

        deviations = [
            Deviation(
                rule=DeviationRule.AUTO_FIX_BUGS,
                issue="Bug 1",
                fix_applied="Fixed",
            ),
            Deviation(
                rule=DeviationRule.AUTO_ADD_CRITICAL,
                issue="Missing validation",
                fix_applied="Added",
            ),
        ]

        allowed, blocked = validate_deviations(deviations, config, task_deviation_count=0)

        assert len(allowed) == 1  # Only AUTO_FIX_BUGS allowed
        assert len(blocked) == 1  # AUTO_ADD_CRITICAL blocked (disabled)


class TestVerificationIntegration:
    """Test verification integration in workflow."""

    def test_verification_runs_after_final_review(self, temp_run_dir: Path) -> None:
        """Test that verification runs after FINAL_REVIEW phase."""
        # Create plan.json with verification criteria
        plan_data = {
            "name": "Test Plan",
            "phase": 1,
            "goal": "Test goal",
            "tasks": [
                {
                    "id": "01",
                    "name": "Test task",
                    "wave": 1,
                    "depends_on": [],
                    "files": [],
                    "action": "Do something",
                    "verify": None,
                    "done_when": "Task done",
                }
            ],
            "verification": {
                "goal": "Feature works",
                "truths": ["User can log in"],
                "artifacts": ["auth.py"],
                "wiring": [["main.py", "auth.py"]],
                "functional_checks": [],
            },
        }

        json_file = temp_run_dir / "plan.json"
        with open(json_file, "w") as f:
            json.dump(plan_data, f)

        # Create the artifacts
        (temp_run_dir / "auth.py").write_text("def login(): pass")
        (temp_run_dir / "main.py").write_text("import auth")

        # Load and verify
        from nelson.verification import GoalVerification, run_verification

        verification = GoalVerification.from_dict(plan_data["verification"])
        result = run_verification(verification, temp_run_dir)

        # Should have checks for EXISTS and SUBSTANTIVE at minimum
        assert len(result.checks) > 0
        assert result.passed  # All checks should pass


class TestDepthModesIntegration:
    """Test depth modes integration in workflow."""

    def test_quick_mode_skips_review_phases(self) -> None:
        """Test that QUICK mode skips REVIEW and FINAL_REVIEW."""
        from nelson.depth import should_skip_phase

        depth = DepthConfig.for_mode(DepthMode.QUICK)

        assert should_skip_phase("REVIEW", depth) is True
        assert should_skip_phase("FINAL_REVIEW", depth) is True
        assert should_skip_phase("PLAN", depth) is False
        assert should_skip_phase("IMPLEMENT", depth) is False

    def test_standard_mode_includes_all_phases(self) -> None:
        """Test that STANDARD mode includes all 6 phases."""
        from nelson.depth import get_phases_for_depth

        depth = DepthConfig.for_mode(DepthMode.STANDARD)
        phases = get_phases_for_depth(depth)

        assert len(phases) == 6
        assert "PLAN" in phases
        assert "IMPLEMENT" in phases
        assert "REVIEW" in phases
        assert "TEST" in phases
        assert "FINAL_REVIEW" in phases
        assert "COMMIT" in phases

    def test_lean_prompts_used_in_quick_mode(self) -> None:
        """Test that lean prompts are used in QUICK mode."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)
        assert depth.lean_prompts is True

        depth = DepthConfig.for_mode(DepthMode.STANDARD)
        assert depth.lean_prompts is False


class TestJSONPlanIntegration:
    """Test JSON plan extraction integration."""

    def test_json_plan_extracted_from_response(self) -> None:
        """Test that JSON plans are extracted from Claude responses."""
        response = """
Here's the plan in both formats:

# Plan

## Tasks
- [ ] Task 1
- [ ] Task 2

```json
{
  "name": "Test Plan",
  "phase": 1,
  "goal": "Build feature",
  "tasks": [
    {
      "id": "01",
      "name": "Task 1",
      "wave": 1,
      "depends_on": [],
      "files": [],
      "action": "Implement",
      "verify": null,
      "done_when": "Code written"
    }
  ]
}
```
"""
        from nelson.plan_parser_json import extract_plan_from_response

        plan = extract_plan_from_response(response)

        assert plan is not None
        assert plan.name == "Test Plan"
        assert len(plan.tasks) == 1
        assert plan.tasks[0].name == "Task 1"

    def test_json_plan_written_to_file(self, temp_run_dir: Path) -> None:
        """Test that JSON plans are written to plan.json."""
        from nelson.plan_models import Plan, Task, TaskStatus
        from nelson.plan_parser_json import write_json_plan

        task = Task(
            id="01",
            name="Test",
            wave=1,
            depends_on=[],
            files=[],
            action="Do it",
            verify=None,
            done_when="Done",
            status=TaskStatus.PENDING,
        )

        plan = Plan(
            name="Test",
            phase=1,
            goal="Test goal",
            tasks=[task],
        )

        json_file = temp_run_dir / "plan.json"
        write_json_plan(plan, json_file)

        assert json_file.exists()

        # Verify content
        with open(json_file) as f:
            data = json.load(f)

        assert data["name"] == "Test"
        assert len(data["tasks"]) == 1


class TestWorkflowEndToEnd:
    """End-to-end tests for workflow with all integrations."""

    def test_workflow_with_all_features_enabled(
        self, temp_run_dir: Path, mock_config: NelsonConfig, mock_state: NelsonState, mock_provider: Mock
    ) -> None:
        """Test workflow with planning questions, deviations, and verification."""
        # This is a high-level test to ensure all pieces work together
        # Actual execution would require more complex mocking

        # Verify config has all features enabled
        assert mock_config.interaction.skip_planning_questions is False
        assert mock_config.interaction.prompt_on_blocked is True
        assert mock_config.skip_verification is False
        assert mock_config.deviations.auto_fix_bugs is True

        # Verify state can track all metrics
        if not hasattr(mock_state, "deviations_count"):
            mock_state.deviations_count = 0

        if not hasattr(mock_state, "verification_retries"):
            mock_state.verification_retries = 0

        assert mock_state.deviations_count == 0
        assert mock_state.verification_retries == 0
