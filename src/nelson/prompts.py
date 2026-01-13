"""Prompt generation for Ralph's AI orchestration system.

This module provides the system prompt (generic Ralph instructions) and phase-specific
prompts that guide the AI through the 6-phase autonomous workflow.
"""

from pathlib import Path

from nelson.phases import Phase


def get_system_prompt(decisions_file: Path) -> str:
    """Generate the system-level prompt with generic Ralph instructions.

    This prompt is sent to Claude for ALL phases and contains:
    - Workflow overview
    - Stateless operation model
    - Core rules
    - Status block format
    - Error handling
    - EXIT_SIGNAL conditions
    - Examples

    Args:
        decisions_file: Path to the decisions.md file for logging

    Returns:
        System prompt string for Claude
    """
    workflow_line = (
        "Ralph: 6-phase autonomous workflow - PLAN, IMPLEMENT, REVIEW(loops), "
        "TEST(loops), FINAL-REVIEW(→4 if fixes), COMMIT"
    )
    return f"""{workflow_line}

STATELESS OPERATION:
Complete ONE task per call. Rebuild context from {decisions_file}, git status, and plan.md.
Mark task [x] in plan, log to {decisions_file}, STOP. Ralph controls phases.

CORE RULES:
- Execute commands, verify results - don't just document
- Minimal scope - only what's in the task
- Commit after each implementation task (Phase 2) - one task = one commit
- Follow project conventions (justfile, package.json, etc.)
- Use Task/Explore for codebase questions; Glob/Grep for specific searches
- NO: unrelated bugs, refactoring, docs (README/SUMMARY), helper scripts, .claude/.ralph commits
- ONLY stage: source code, tests, config files

ERROR HANDLING:
Log error details to {decisions_file} and STOP. Ralph handles recovery.

STATUS BLOCK (REQUIRED):
---RALPH_STATUS---
STATUS: IN_PROGRESS|COMPLETE|BLOCKED
TASKS_COMPLETED_THIS_LOOP: N
FILES_MODIFIED: N
TESTS_STATUS: PASSING|FAILING|NOT_RUN
WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
EXIT_SIGNAL: true|false
RECOMMENDATION: one-line next step
---END_RALPH_STATUS---

EXIT_SIGNAL=true ONLY when ALL conditions met:
1. All plan tasks marked [x] or [~]
2. Tests passing (or NOT_RUN if before Phase 5)
3. No errors in last execution
4. No meaningful work remaining

EXAMPLES:

Example 1 - Making Progress:
---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 3
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Continue with next Phase 2 task from plan
---END_RALPH_STATUS---

Example 2 - All Done (Phase 9 complete):
---RALPH_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: All tasks complete, tests passing, workflow finished
---END_RALPH_STATUS---

Example 3 - Blocked:
---RALPH_STATUS---
STATUS: BLOCKED
TASKS_COMPLETED_THIS_LOOP: 0
FILES_MODIFIED: 2
TESTS_STATUS: FAILING
WORK_TYPE: DEBUGGING
EXIT_SIGNAL: false
RECOMMENDATION: Same import error 3x, needs investigation
---END_RALPH_STATUS---

IMPLEMENTATION REQUIREMENTS:
- Complete all work fully - do not leave TODO, FIXME, or XXX comments
- If you cannot complete something, explain why in {decisions_file}
- Partial implementations are not acceptable - do it right or defer to future task
- Write production-ready code, not placeholder stubs

AVOID:
- Busy work when done
- Test-only loops
- Scope creep
- Missing status block

DECISIONS LOG FORMAT:
## [Iteration N] Phase X: Task Name
**Task:** (exact from plan)
**What I Did:** actions/commands
**Why:** rationale
**Result:** success/failure/findings
"""


def get_phase_prompt(
    phase: Phase, plan_file: Path, decisions_file: Path
) -> str:
    """Generate phase-specific prompt for the given phase.

    Args:
        phase: The phase to generate prompt for
        plan_file: Path to plan.md
        decisions_file: Path to decisions.md

    Returns:
        Phase-specific prompt instructions
    """
    if phase == Phase.PLAN:
        return _get_plan_prompt(plan_file, decisions_file)
    elif phase == Phase.IMPLEMENT:
        return _get_implement_prompt(plan_file, decisions_file)
    elif phase == Phase.REVIEW:
        return _get_review_prompt(plan_file, decisions_file)
    elif phase == Phase.TEST:
        return _get_test_prompt(plan_file, decisions_file)
    elif phase == Phase.FINAL_REVIEW:
        return _get_final_review_prompt(plan_file, decisions_file)
    elif phase == Phase.COMMIT:
        return _get_commit_prompt(plan_file, decisions_file)
    else:
        raise ValueError(f"Unknown phase: {phase}")


def _get_plan_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 1 (PLAN) prompt."""
    return f"""Read {decisions_file}, git status. Analyze the task and create an \
implementation plan.

Create a plan at {plan_file} with 6 phases:
- Phase 1 should have 2-4 analysis tasks to understand the problem
- Phase 2 should break implementation into ATOMIC tasks (each task = one commit)
- Break large features into small, independent tasks
- Each Phase 2 task must be committable on its own
- Format: '- [ ] description' for unchecked, '- [x] description' for checked
- Include Phase 3 (REVIEW), Phase 4 (TEST), Phase 5 (FINAL-REVIEW), Phase 6 (COMMIT)

Mark Phase 1 tasks [x] as you complete them, log to {decisions_file}, then STOP.
"""


def _get_implement_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 2 (IMPLEMENT) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 2 task.

Complete ONE task: code/tests/config only. Then:
1. Stage changes: git add (ONLY files you modified)
2. Create commit: git commit with descriptive message for THIS task
3. Mark [x], log to {decisions_file}, STOP

NO docs (SUMMARY.md, guides). Testing: 20% effort, new features only, Phase 4 is main testing.
Each task = one atomic commit.
"""


def _get_review_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 3 (REVIEW) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 3 task.

Review Phase 2 commits: git log + git status
Check for: bugs, security issues, code quality, unwanted docs, sensitive files

IF issues found:
  - Add '- [ ] Fix: description' tasks to Phase 3
  - Mark current task [x]
  - STOP

IF no issues:
  - Mark task [x]
  - STOP (Ralph advances to Phase 4)

Note: Phase 2 commits already made. Review fixes also get committed.
"""


def _get_test_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 4 (TEST) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 4 task.

IF task is "run tests":
  - EXECUTE tests/linter/type-checker (use justfile or package.json)
  - If failures: Add fix tasks + re-run test task to Phase 4, mark [x]
  - If passing: Mark [x], STOP

IF task is "Fix: X":
  - Fix ONE issue
  - Stage and commit the fix
  - Mark [x], STOP

When all Phase 4 tasks [x]: Ralph advances to Phase 5
"""


def _get_final_review_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 5 (FINAL-REVIEW) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 5 task.

VERIFY Phase 4 tests passed.
Check git status for unwanted files:
  - No docs (README, SUMMARY.md, guides)
  - No .claude/ or .ralph/ files
  - No sensitive data

IF issues found:
  - Add fix tasks to Phase 5 (will be committed)
  - Mark current task [x]
  - STOP (returns to Phase 4 after fixes)

IF no issues:
  - Mark task [x]
  - STOP (Ralph advances to Phase 6)
"""


def _get_commit_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 6 (COMMIT) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 6 task.

Check git status:

NO uncommitted changes:
  - All work committed in Phase 2/3/4/5
  - Mark task [x], STOP

HAS uncommitted changes:
  - Stage ONLY: source code, tests, config files
  - NO docs, .claude/, .ralph/ files
  - Create commit with descriptive message
  - Mark task [x], STOP

Most commits happen in Phase 2. This phase handles any remaining changes.
"""


def build_full_prompt(
    original_task: str,
    phase: Phase,
    plan_file: Path,
    decisions_file: Path,
    loop_context: str | None = None,
) -> str:
    """Build the complete prompt combining task, context, and phase instructions.

    Args:
        original_task: The user's original task description
        phase: Current phase
        plan_file: Path to plan.md
        decisions_file: Path to decisions.md
        loop_context: Optional context from previous iterations

    Returns:
        Complete prompt string for Claude
    """
    parts = [f"Original task: {original_task}"]

    # Add plan document for Phase 2+
    if phase != Phase.PLAN:
        parts.append(f"Plan document: {plan_file}")

    # Add loop context if this is not the first iteration
    if loop_context:
        parts.append("")
        parts.append("━" * 60)
        parts.append(loop_context)
        parts.append("━" * 60)

    # Add phase identification and instructions
    parts.append("")
    if phase == Phase.PLAN:
        parts.append("Phase 1 (PLAN) instructions:")
    else:
        parts.append(f"Current phase: Phase {phase.value}")
        parts.append("Phase instructions:")

    parts.append(get_phase_prompt(phase, plan_file, decisions_file))

    return "\n".join(parts)


def build_loop_context(
    total_iterations: int,
    phase_iterations: int,
    tasks_completed: int,
    current_phase: Phase,
    recent_decisions: str | None = None,
) -> str:
    """Build loop context string for iterations after the first.

    Args:
        total_iterations: Total number of iterations so far
        phase_iterations: Number of iterations in current phase
        tasks_completed: Number of tasks completed so far
        current_phase: Current phase
        recent_decisions: Optional excerpt of recent decision log entries

    Returns:
        Formatted loop context string
    """
    lines = [
        f"LOOP CONTEXT (Iteration {total_iterations}):",
        f"- Total iterations so far: {total_iterations}",
        f"- Phase iterations: {phase_iterations}",
        f"- Tasks completed: {tasks_completed}",
        f"- Current phase: {current_phase.value} ({current_phase.name})",
    ]

    if recent_decisions:
        lines.append("")
        lines.append("Recent activity (last few decisions):")
        lines.append(recent_decisions)

    return "\n".join(lines)
