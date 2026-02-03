"""Tests for prompt generation."""

from pathlib import Path

import pytest

from nelson.depth import DepthConfig, DepthMode
from nelson.phases import Phase
from nelson.prompts import (
    build_full_prompt,
    build_loop_context,
    get_phase_prompt,
    get_phase_prompt_for_depth,
    get_system_prompt,
    get_system_prompt_for_depth,
)


class TestSystemPrompt:
    """Tests for system prompt generation."""

    def test_system_prompt_contains_workflow_overview(self) -> None:
        """System prompt should include the 6-phase workflow overview."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "6-phase autonomous workflow" in prompt
        assert "PLAN, IMPLEMENT, REVIEW(loops), TEST(loops), FINAL-REVIEW" in prompt

    def test_system_prompt_contains_stateless_operation(self) -> None:
        """System prompt should explain stateless operation model."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "STATELESS OPERATION:" in prompt
        assert "Complete ONE task per call" in prompt
        assert "Rebuild context" in prompt

    def test_system_prompt_contains_core_rules(self) -> None:
        """System prompt should include core rules."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "CORE RULES:" in prompt
        assert "Execute commands, verify results" in prompt
        assert "Commit after each implementation task (Phase 2)" in prompt
        assert "Use Task/Explore for codebase questions" in prompt

    def test_system_prompt_contains_status_block_format(self) -> None:
        """System prompt should define status block format."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "STATUS BLOCK (REQUIRED):" in prompt
        assert "---NELSON_STATUS---" in prompt
        assert "STATUS:" in prompt
        assert "EXIT_SIGNAL:" in prompt
        assert "---END_NELSON_STATUS---" in prompt

    def test_system_prompt_contains_exit_signal_conditions(self) -> None:
        """System prompt should define EXIT_SIGNAL conditions."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "EXIT_SIGNAL=true ONLY when ALL conditions met:" in prompt
        assert "All tasks in CURRENT PHASE marked [x] or [~]" in prompt
        assert "Tests passing" in prompt
        assert "No errors in last execution" in prompt

    def test_system_prompt_contains_examples(self) -> None:
        """System prompt should include example status blocks."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "Example 1 - Making Progress:" in prompt
        assert "Example 2 - Phase Complete" in prompt
        assert "Example 3 - Blocked:" in prompt

    def test_system_prompt_includes_decisions_file_path(self) -> None:
        """System prompt should reference the decisions file path."""
        decisions_file = Path(".nelson/runs/test-123/decisions.md")
        prompt = get_system_prompt(decisions_file)
        assert str(decisions_file) in prompt

    def test_system_prompt_contains_decisions_log_format(self) -> None:
        """System prompt should define decisions log format."""
        prompt = get_system_prompt(Path(".nelson/decisions.md"))
        assert "DECISIONS LOG FORMAT:" in prompt
        assert "## [Iteration N] Phase X: Task Name" in prompt
        assert "**Task:**" in prompt
        assert "**What I Did:**" in prompt


class TestPhasePrompts:
    """Tests for phase-specific prompt generation."""

    def test_discover_phase_prompt(self) -> None:
        """Phase 0 prompt should include research instructions."""
        prompt = get_phase_prompt(
            Phase.DISCOVER,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "DISCOVER PHASE" in prompt
        assert "Research and document" in prompt
        assert "CODEBASE STRUCTURE" in prompt
        assert "ARCHITECTURE PATTERNS" in prompt
        assert "SIMILAR IMPLEMENTATIONS" in prompt
        assert "DEPENDENCIES AND INTEGRATION POINTS" in prompt
        assert "COMPLEXITY OBSERVATIONS" in prompt
        assert "EXIT_SIGNAL=true" in prompt
        # Verify documentation-only approach
        assert "Document what EXISTS, never what SHOULD BE" in prompt
        assert "file:line references" in prompt

    def test_plan_phase_prompt(self) -> None:
        """Phase 1 prompt should include planning instructions."""
        prompt = get_phase_prompt(
            Phase.PLAN,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "Create a plan" in prompt
        assert "6 phases" in prompt
        assert "2-4 analysis tasks" in prompt
        assert "ATOMIC tasks" in prompt
        assert "'- [ ] description'" in prompt

    def test_implement_phase_prompt(self) -> None:
        """Phase 2 prompt should include implementation instructions."""
        prompt = get_phase_prompt(
            Phase.IMPLEMENT,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "Find FIRST unchecked Phase 2 task" in prompt
        assert "git add" in prompt
        assert "git commit" in prompt
        assert "Each task = one atomic commit" in prompt
        assert "NO docs" in prompt

    def test_review_phase_prompt(self) -> None:
        """Phase 3 prompt should include review instructions."""
        prompt = get_phase_prompt(
            Phase.REVIEW,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "git status" in prompt  # Check uncommitted changes first
        assert "git diff HEAD" in prompt  # Shows all uncommitted
        assert "git diff main...HEAD" in prompt  # Branch diff vs base
        assert "git log" in prompt
        assert "COMPREHENSIVE CODE REVIEW CHECKLIST" in prompt
        assert "CORRECTNESS & BUGS" in prompt
        assert "CODEBASE PATTERNS & CONSISTENCY" in prompt
        assert "CODE QUALITY" in prompt
        assert "SECURITY" in prompt
        assert "- [ ] Fix:" in prompt  # Check for the actual format without quotes

    def test_test_phase_prompt(self) -> None:
        """Phase 4 prompt should include testing instructions."""
        prompt = get_phase_prompt(
            Phase.TEST,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "Find FIRST unchecked Phase 4 task" in prompt
        assert 'IF task is "run tests"' in prompt
        assert "EXECUTE tests" in prompt
        assert "justfile or package.json" in prompt

    def test_final_review_phase_prompt(self) -> None:
        """Phase 5 prompt should include final review instructions."""
        prompt = get_phase_prompt(
            Phase.FINAL_REVIEW,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "COMPREHENSIVE FINAL REVIEW" in prompt
        assert "VERIFY TESTS" in prompt
        assert "Confirm Phase 4 tests/linter/type-checker all passed" in prompt
        assert "FULL CODE REVIEW" in prompt
        assert "CODEBASE CONSISTENCY" in prompt
        assert "UNWANTED FILES/CHANGES" in prompt
        assert ".claude/ or .nelson/" in prompt
        # Phase 5 now adds Fix tasks to Phase 2, not Phase 4
        assert "loop back to Phase 2" in prompt

    def test_commit_phase_prompt(self) -> None:
        """Phase 6 prompt should include commit instructions."""
        prompt = get_phase_prompt(
            Phase.COMMIT,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "Check git status" in prompt
        assert "NO uncommitted changes" in prompt
        assert "HAS uncommitted changes" in prompt
        assert "Most commits happen in Phase 2" in prompt

    def test_roadmap_phase_prompt(self) -> None:
        """Phase 7 prompt should include roadmap documentation instructions."""
        prompt = get_phase_prompt(
            Phase.ROADMAP,
            Path(".nelson/plan.md"),
            Path(".nelson/decisions.md"),
        )
        assert "ROADMAP PHASE" in prompt
        assert "Document future improvements" in prompt
        assert "FUTURE IMPROVEMENTS" in prompt
        assert "TECHNICAL DEBT" in prompt
        assert "TESTING GAPS" in prompt
        assert "DOCUMENTATION NEEDS" in prompt
        assert "RELATED WORK" in prompt
        assert "ROADMAP.md" in prompt
        assert "EXIT_SIGNAL=true" in prompt

    def test_phase_prompts_include_file_paths(self) -> None:
        """All phase prompts should reference plan and decisions files."""
        plan_file = Path(".nelson/runs/test-123/plan.md")
        decisions_file = Path(".nelson/runs/test-123/decisions.md")

        for phase in Phase:
            prompt = get_phase_prompt(phase, plan_file, decisions_file)
            # At least one of the files should be mentioned
            assert str(plan_file) in prompt or str(decisions_file) in prompt

    def test_invalid_phase_raises_error(self) -> None:
        """Getting prompt for invalid phase should raise ValueError."""
        # Phase enum doesn't allow invalid values, but test the type guard
        with pytest.raises((ValueError, AttributeError)):
            # This would fail type checking, but test runtime behavior
            get_phase_prompt(
                999,  # type: ignore[arg-type]
                Path(".nelson/plan.md"),
                Path(".nelson/decisions.md"),
            )


class TestFullPromptBuilding:
    """Tests for building complete prompts."""

    def test_full_prompt_phase_1_no_loop_context(self) -> None:
        """Phase 1 prompt should include task and phase instructions."""
        prompt = build_full_prompt(
            original_task="Implement feature X",
            phase=Phase.PLAN,
            plan_file=Path(".nelson/plan.md"),
            decisions_file=Path(".nelson/decisions.md"),
            loop_context=None,
        )

        assert "Original task: Implement feature X" in prompt
        assert "Phase 1 (PLAN) instructions:" in prompt
        assert "Create a plan" in prompt
        # Phase 1 should not reference plan document
        assert "Plan document:" not in prompt

    def test_full_prompt_phase_2_includes_plan_document(self) -> None:
        """Phase 2+ prompts should reference plan document."""
        prompt = build_full_prompt(
            original_task="Implement feature X",
            phase=Phase.IMPLEMENT,
            plan_file=Path(".nelson/plan.md"),
            decisions_file=Path(".nelson/decisions.md"),
            loop_context=None,
        )

        assert "Plan document: .nelson/plan.md" in prompt
        assert "Current phase: Phase 2" in prompt

    def test_full_prompt_with_loop_context(self) -> None:
        """Prompts should include loop context when provided."""
        loop_ctx = "LOOP CONTEXT (Iteration 5):\n- Tasks completed: 3"
        prompt = build_full_prompt(
            original_task="Implement feature X",
            phase=Phase.IMPLEMENT,
            plan_file=Path(".nelson/plan.md"),
            decisions_file=Path(".nelson/decisions.md"),
            loop_context=loop_ctx,
        )

        assert loop_ctx in prompt
        assert "━" * 60 in prompt  # Context separator

    def test_full_prompt_structure_order(self) -> None:
        """Full prompt should have correct section ordering."""
        loop_ctx = "LOOP CONTEXT (Iteration 2):\n- Info here"
        prompt = build_full_prompt(
            original_task="Task X",
            phase=Phase.REVIEW,
            plan_file=Path(".nelson/plan.md"),
            decisions_file=Path(".nelson/decisions.md"),
            loop_context=loop_ctx,
        )

        # Find positions of key sections
        task_pos = prompt.index("Original task:")
        plan_pos = prompt.index("Plan document:")
        context_pos = prompt.index("LOOP CONTEXT")
        phase_pos = prompt.index("Current phase:")

        # Verify order
        assert task_pos < plan_pos < context_pos < phase_pos


class TestLoopContextBuilding:
    """Tests for loop context generation."""

    def test_loop_context_basic_info(self) -> None:
        """Loop context should include basic iteration information."""
        context = build_loop_context(
            cycle_iterations=1,
            total_iterations=5,
            phase_iterations=3,
            tasks_completed=7,
            current_phase=Phase.IMPLEMENT,
            recent_decisions=None,
        )

        assert "LOOP CONTEXT (Cycle 1, Phase Execution 5):" in context
        assert "Complete cycles so far: 1" in context
        assert "Phase executions so far: 5" in context
        assert "Phase iterations in current phase: 3" in context
        assert "Tasks completed in current plan: 7" in context

    def test_loop_context_with_recent_decisions(self) -> None:
        """Loop context should include recent decisions when provided."""
        recent = "## [Iteration 4] Phase 2: Task completed\n**Result:** Success"
        context = build_loop_context(
            cycle_iterations=0,
            total_iterations=5,
            phase_iterations=2,
            tasks_completed=3,
            current_phase=Phase.REVIEW,
            recent_decisions=recent,
        )

        assert "Recent activity" in context
        assert recent in context

    def test_loop_context_without_recent_decisions(self) -> None:
        """Loop context should work without recent decisions."""
        context = build_loop_context(
            cycle_iterations=0,
            total_iterations=1,
            phase_iterations=1,
            tasks_completed=0,
            current_phase=Phase.PLAN,
            recent_decisions=None,
        )

        assert "LOOP CONTEXT (Cycle 0, Phase Execution 1):" in context
        assert "Recent activity" not in context

    def test_loop_context_all_phases(self) -> None:
        """Loop context should work for all phases."""
        for phase in Phase:
            context = build_loop_context(
                cycle_iterations=2,
                total_iterations=10,
                phase_iterations=2,
                tasks_completed=5,
                current_phase=phase,
                recent_decisions=None,
            )

            assert "LOOP CONTEXT (Cycle 2, Phase Execution 10):" in context


class TestPromptIntegration:
    """Integration tests for prompt generation."""

    def test_complete_workflow_prompts(self) -> None:
        """Test generating prompts for a complete workflow."""
        plan_file = Path(".nelson/runs/test/plan.md")
        decisions_file = Path(".nelson/runs/test/decisions.md")
        task = "Implement authentication system"

        # Phase 1: Planning
        system_prompt = get_system_prompt(decisions_file)
        full_prompt_p1 = build_full_prompt(task, Phase.PLAN, plan_file, decisions_file)

        assert "6-phase autonomous workflow" in system_prompt
        assert "Original task: Implement authentication system" in full_prompt_p1
        assert "Phase 1 (PLAN) instructions:" in full_prompt_p1

        # Phase 2: Implementation
        loop_ctx = build_loop_context(0, 2, 1, 1, Phase.IMPLEMENT)
        full_prompt_p2 = build_full_prompt(
            task, Phase.IMPLEMENT, plan_file, decisions_file, loop_ctx
        )

        assert "Plan document:" in full_prompt_p2
        assert "LOOP CONTEXT" in full_prompt_p2
        assert "Find FIRST unchecked Phase 2 task" in full_prompt_p2

        # All prompts should be non-empty strings
        assert len(system_prompt) > 100
        assert len(full_prompt_p1) > 100
        assert len(full_prompt_p2) > 100

    def test_prompt_file_paths_are_preserved(self) -> None:
        """Test that file paths are correctly embedded in prompts."""
        custom_plan = Path("/custom/path/to/plan.md")
        custom_decisions = Path("/custom/path/to/decisions.md")

        system_prompt = get_system_prompt(custom_decisions)
        phase_prompt = get_phase_prompt(Phase.IMPLEMENT, custom_plan, custom_decisions)

        assert str(custom_decisions) in system_prompt
        assert str(custom_plan) in phase_prompt or str(custom_decisions) in phase_prompt


class TestDepthAwareSystemPrompt:
    """Tests for depth-aware system prompt generation."""

    def test_standard_mode_uses_full_prompt(self) -> None:
        """Standard mode should use full system prompt."""
        depth = DepthConfig.for_mode(DepthMode.STANDARD)
        prompt = get_system_prompt_for_depth(Path(".nelson/decisions.md"), depth)

        assert "6-phase autonomous workflow" in prompt
        assert "STATELESS OPERATION:" in prompt
        assert "CORE RULES:" in prompt

    def test_comprehensive_mode_uses_full_prompt(self) -> None:
        """Comprehensive mode should use full system prompt."""
        depth = DepthConfig.for_mode(DepthMode.COMPREHENSIVE)
        prompt = get_system_prompt_for_depth(Path(".nelson/decisions.md"), depth)

        assert "6-phase autonomous workflow" in prompt
        assert "STATELESS OPERATION:" in prompt

    def test_quick_mode_uses_lean_prompt(self) -> None:
        """Quick mode should use lean system prompt."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)
        prompt = get_system_prompt_for_depth(Path(".nelson/decisions.md"), depth)

        assert "4-phase workflow" in prompt
        assert "PLAN, IMPLEMENT, TEST, COMMIT" in prompt
        # Lean prompt should not have verbose sections
        assert "STATELESS OPERATION:" not in prompt
        assert "CORE RULES:" not in prompt

    def test_quick_mode_lean_prompt_contains_essentials(self) -> None:
        """Lean prompt should still have essential elements."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)
        prompt = get_system_prompt_for_depth(Path(".nelson/decisions.md"), depth)

        # Must have status block
        assert "---NELSON_STATUS---" in prompt
        assert "STATUS:" in prompt
        assert "EXIT_SIGNAL:" in prompt
        assert "---END_NELSON_STATUS---" in prompt

        # Must have blocked fields
        assert "BLOCKED_REASON:" in prompt
        assert "BLOCKED_RESOURCES:" in prompt

    def test_none_depth_defaults_to_standard(self) -> None:
        """None depth should use standard (full) prompt."""
        prompt = get_system_prompt_for_depth(Path(".nelson/decisions.md"), None)

        assert "6-phase autonomous workflow" in prompt
        assert "STATELESS OPERATION:" in prompt

    def test_lean_prompt_is_shorter(self) -> None:
        """Lean prompt should be significantly shorter than full prompt."""
        full_prompt = get_system_prompt_for_depth(
            Path(".nelson/decisions.md"),
            DepthConfig.for_mode(DepthMode.STANDARD),
        )
        lean_prompt = get_system_prompt_for_depth(
            Path(".nelson/decisions.md"),
            DepthConfig.for_mode(DepthMode.QUICK),
        )

        # Lean should be at least 50% shorter
        assert len(lean_prompt) < len(full_prompt) * 0.5


class TestDepthAwarePhasePrompts:
    """Tests for depth-aware phase prompt generation."""

    def test_standard_mode_uses_full_phase_prompts(self) -> None:
        """Standard mode should use full phase prompts."""
        depth = DepthConfig.for_mode(DepthMode.STANDARD)

        plan_prompt = get_phase_prompt_for_depth(
            Phase.PLAN, Path("plan.md"), Path("decisions.md"), depth
        )

        assert "6 phases" in plan_prompt
        assert "CLARIFYING QUESTIONS" in plan_prompt

    def test_quick_mode_plan_prompt_is_lean(self) -> None:
        """Quick mode PLAN prompt should be lean."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = get_phase_prompt_for_depth(
            Phase.PLAN, Path("plan.md"), Path("decisions.md"), depth
        )

        assert "4 phases" in prompt
        # Lean prompt should not have clarifying questions
        assert "CLARIFYING QUESTIONS" not in prompt
        assert len(prompt) < 500  # Should be very short

    def test_quick_mode_implement_prompt_is_lean(self) -> None:
        """Quick mode IMPLEMENT prompt should be lean."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = get_phase_prompt_for_depth(
            Phase.IMPLEMENT, Path("plan.md"), Path("decisions.md"), depth
        )

        assert "git add" in prompt
        assert "git commit" in prompt
        assert "Mark [x]" in prompt
        assert len(prompt) < 300

    def test_quick_mode_test_prompt_is_lean(self) -> None:
        """Quick mode TEST prompt should be lean."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = get_phase_prompt_for_depth(
            Phase.TEST, Path("plan.md"), Path("decisions.md"), depth
        )

        assert "tests" in prompt.lower()
        assert len(prompt) < 300

    def test_quick_mode_commit_prompt_is_lean(self) -> None:
        """Quick mode COMMIT prompt should be lean."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = get_phase_prompt_for_depth(
            Phase.COMMIT, Path("plan.md"), Path("decisions.md"), depth
        )

        assert "git status" in prompt
        assert len(prompt) < 200

    def test_quick_mode_review_returns_standard(self) -> None:
        """Quick mode should return standard prompt for REVIEW (skipped phase)."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = get_phase_prompt_for_depth(
            Phase.REVIEW, Path("plan.md"), Path("decisions.md"), depth
        )

        # Falls back to standard prompt since REVIEW is skipped in quick mode
        assert "COMPREHENSIVE CODE REVIEW CHECKLIST" in prompt

    def test_none_depth_defaults_to_standard_prompts(self) -> None:
        """None depth should use standard phase prompts."""
        prompt = get_phase_prompt_for_depth(
            Phase.PLAN, Path("plan.md"), Path("decisions.md"), None
        )

        assert "6 phases" in prompt
        assert "CLARIFYING QUESTIONS" in prompt

    def test_lean_prompts_are_shorter(self) -> None:
        """Lean phase prompts should be shorter than full prompts."""
        quick = DepthConfig.for_mode(DepthMode.QUICK)
        standard = DepthConfig.for_mode(DepthMode.STANDARD)

        for phase in [Phase.PLAN, Phase.IMPLEMENT, Phase.TEST, Phase.COMMIT]:
            lean = get_phase_prompt_for_depth(
                phase, Path("plan.md"), Path("decisions.md"), quick
            )
            full = get_phase_prompt_for_depth(
                phase, Path("plan.md"), Path("decisions.md"), standard
            )

            assert len(lean) < len(full), f"{phase.name} lean prompt should be shorter"


class TestBuildFullPromptWithDepth:
    """Tests for build_full_prompt with depth configuration."""

    def test_build_full_prompt_with_quick_mode(self) -> None:
        """build_full_prompt should use lean prompts in quick mode."""
        depth = DepthConfig.for_mode(DepthMode.QUICK)

        prompt = build_full_prompt(
            original_task="Fix typo",
            phase=Phase.PLAN,
            plan_file=Path("plan.md"),
            decisions_file=Path("decisions.md"),
            loop_context=None,
            depth=depth,
        )

        assert "Original task: Fix typo" in prompt
        assert "4 phases" in prompt
        assert "CLARIFYING QUESTIONS" not in prompt

    def test_build_full_prompt_with_standard_mode(self) -> None:
        """build_full_prompt should use full prompts in standard mode."""
        depth = DepthConfig.for_mode(DepthMode.STANDARD)

        prompt = build_full_prompt(
            original_task="Add feature",
            phase=Phase.PLAN,
            plan_file=Path("plan.md"),
            decisions_file=Path("decisions.md"),
            loop_context=None,
            depth=depth,
        )

        assert "Original task: Add feature" in prompt
        assert "6 phases" in prompt
        assert "CLARIFYING QUESTIONS" in prompt

    def test_build_full_prompt_none_depth_uses_standard(self) -> None:
        """build_full_prompt with None depth should use standard prompts."""
        prompt = build_full_prompt(
            original_task="Add feature",
            phase=Phase.PLAN,
            plan_file=Path("plan.md"),
            decisions_file=Path("decisions.md"),
            loop_context=None,
            depth=None,
        )

        assert "6 phases" in prompt

    def test_build_full_prompt_backwards_compatible(self) -> None:
        """build_full_prompt should work without depth parameter."""
        # This tests backwards compatibility - existing code should still work
        prompt = build_full_prompt(
            original_task="Add feature",
            phase=Phase.PLAN,
            plan_file=Path("plan.md"),
            decisions_file=Path("decisions.md"),
        )

        assert "Original task: Add feature" in prompt
        assert "6 phases" in prompt
