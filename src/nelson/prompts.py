"""Prompt generation for Nelson's AI orchestration system.

This module provides the system prompt (generic Nelson instructions) and phase-specific
prompts that guide the AI through the 6-phase autonomous workflow.
"""

from pathlib import Path

from nelson.phases import Phase


def get_system_prompt(decisions_file: Path) -> str:
    """Generate the system-level prompt with generic Nelson instructions.

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
        "Nelson: 6-phase autonomous workflow - PLAN, IMPLEMENT, REVIEW(loops), "
        "TEST(loops), FINAL-REVIEW(→4 if fixes), COMMIT"
    )
    return f"""{workflow_line}

STATELESS OPERATION:
Complete ONE task per call. Rebuild context from {decisions_file}, git status, and plan.md.
Mark task [x] in plan, log to {decisions_file}, STOP. Nelson controls phases.

CORE RULES:
- Execute commands, verify results - don't just document
- Minimal scope - only what's in the task
- Commit after each implementation task (Phase 2) - one task = one commit
- Follow project conventions (justfile, package.json, etc.)
- Use Task/Explore for codebase questions; Glob/Grep for specific searches
- NO: unrelated bugs, refactoring, docs (README/SUMMARY), helper scripts, .claude/.nelson commits
- ONLY stage: source code, tests, config files

ERROR HANDLING:
Log error details to {decisions_file} and STOP. Nelson handles recovery.

STATUS BLOCK (REQUIRED):
---NELSON_STATUS---
STATUS: IN_PROGRESS|COMPLETE|BLOCKED
TASKS_COMPLETED_THIS_LOOP: N
FILES_MODIFIED: N
TESTS_STATUS: PASSING|FAILING|NOT_RUN
WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
EXIT_SIGNAL: true|false
RECOMMENDATION: one-line next step
---END_NELSON_STATUS---

EXIT_SIGNAL=true ONLY when ALL conditions met:
1. All tasks in CURRENT PHASE marked [x] or [~]
2. Tests passing (or NOT_RUN if before Phase 4)
3. No errors in last execution
4. No meaningful work remaining in this phase

NOTE: EXIT_SIGNAL=true means "current phase is complete".
- In Phases 1-6: Nelson advances to next phase
- After Phase 6: Nelson completes cycle, loops to Phase 1 for new work

EXAMPLES:

Example 1 - Making Progress:
---NELSON_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 3
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Continue with next Phase 2 task from plan
---END_NELSON_STATUS---

Example 2 - Phase Complete (will advance to next phase):
---NELSON_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 1
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: All Phase 1 tasks complete, advancing to Phase 2
---END_NELSON_STATUS---

Example 3 - Blocked:
---NELSON_STATUS---
STATUS: BLOCKED
TASKS_COMPLETED_THIS_LOOP: 0
FILES_MODIFIED: 2
TESTS_STATUS: FAILING
WORK_TYPE: DEBUGGING
EXIT_SIGNAL: false
RECOMMENDATION: Same import error 3x, needs investigation
---END_NELSON_STATUS---

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


def get_phase_prompt(phase: Phase, plan_file: Path, decisions_file: Path) -> str:
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
- Phase 3 (REVIEW): Add task '- [ ] Review all changes: bugs, patterns, quality, security'
- Phase 4 (TEST): Add task(s) for running tests/linter/type-checker
- Phase 5 (FINAL-REVIEW): Add task '- [ ] Final review: all changes, patterns, completeness'
- Phase 6 (COMMIT): Add task '- [ ] Commit any remaining changes'

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

CRITICAL: Implement completely - no TODO/FIXME/XXX comments or placeholder stubs.
Write production-ready code. If you cannot complete, explain why in {decisions_file}.
"""


def _get_review_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 3 (REVIEW) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 3 task.

IF task is "Review all changes" or similar review task:
  Review Phase 2 commits: git log + git status

  COMPREHENSIVE CODE REVIEW CHECKLIST:

  1. CORRECTNESS & BUGS:
     - Logic errors, off-by-one errors, incorrect algorithms
     - Edge cases: null/undefined, empty collections, boundary values
     - Race conditions, concurrency issues
     - Proper error handling and validation
     - Return values and side effects are correct

  2. CODEBASE PATTERNS & CONSISTENCY:
     - Follows existing architectural patterns in the codebase
     - Uses same libraries/frameworks as similar features
     - Matches naming conventions (functions, variables, files)
     - Consistent code style with existing code
     - Follows established project structure/organization

  3. CODE QUALITY:
     - Readable and maintainable
     - No unnecessary complexity or over-engineering
     - Proper abstractions and separation of concerns
     - No code duplication that should be refactored
     - Type safety (if applicable: TypeScript, Python type hints, etc.)

  4. SECURITY:
     - No SQL injection, XSS, command injection vulnerabilities
     - Proper input validation and sanitization
     - No hardcoded secrets or sensitive data
     - Secure authentication/authorization checks

  5. COMPLETENESS:
     - No TODO/FIXME/XXX comments or placeholder stubs
     - All implementations are production-ready, not partial
     - Adequate test coverage for new functionality
     - Required edge cases are handled

  6. UNWANTED CHANGES:
     - No unwanted docs (README, SUMMARY.md, guides)
     - No .claude/ or .nelson/ files
     - No unrelated refactoring or scope creep

  REVIEW STANDARD - Flag ANY of these as blocking issues:
  - BUGS: Logic errors, incorrect behavior, missing edge case handling
  - SECURITY: Any security vulnerability from checklist above
  - INCOMPLETE: TODO/FIXME/XXX comments, placeholder code, partial implementations
  - HARDCODED VALUES: Magic numbers/strings that should be constants or configurable
  - MISSING TESTS: New logic with complex edge cases that lacks test coverage
  - BREAKING CHANGES: Changes to public APIs/data structures without migration path
  - INCONSISTENT: Violates established codebase patterns (check similar code)

  IF you find ANY blocking issues:
    - Add '- [ ] Fix: <specific issue with file:line>' to Phase 3 for EACH issue
    - Be specific: "Fix: Hardcoded threshold 10 in workflow.py:445 should be config"
    - Mark current review task [x], log to {decisions_file}, STOP

  IF no blocking issues found (verified ALL categories):
    - Mark task [x], log to {decisions_file}, STOP
    - Nelson advances to Phase 4

IF task starts with "Fix:":
  - Fix the ONE specific issue described in the task
  - Stage changes: git add (ONLY files you modified)
  - Create commit with message describing the fix
  - Mark task [x], log to {decisions_file}, STOP

When all Phase 3 tasks [x]: Nelson advances to Phase 4
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

When all Phase 4 tasks [x]: Nelson advances to Phase 5
"""


def _get_final_review_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 5 (FINAL-REVIEW) prompt."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 5 task.

COMPREHENSIVE FINAL REVIEW - Tests passed, now verify ALL changes:

1. VERIFY TESTS:
   - Confirm Phase 4 tests/linter/type-checker all passed
   - No test failures or warnings ignored

2. FULL CODE REVIEW (entire changeset):
   - Review ALL commits from this implementation cycle
   - Bugs/logic errors: Check edge cases, error handling, return values
   - Patterns: Follows existing codebase conventions and architecture
   - Quality: Readable, maintainable, proper abstractions, no duplication
   - Security: No vulnerabilities (injection, XSS, insecure data handling)
   - Completeness: No TODO/FIXME/XXX, no placeholder stubs, production-ready
   - Type safety: Proper types if applicable (TypeScript, Python hints, etc.)
   - Performance: No obvious performance issues or inefficiencies

3. CODEBASE CONSISTENCY:
   - Naming matches existing conventions (functions, variables, files)
   - Uses same libraries/patterns as similar features
   - File structure follows project organization
   - Code style consistent with existing code

4. UNWANTED FILES/CHANGES:
   - git status: No unwanted staged/unstaged files
   - No docs (README, SUMMARY.md, guides) unless explicitly requested
   - No .claude/ or .nelson/ files
   - No sensitive data or credentials
   - No unrelated refactoring or scope creep

5. TEST COVERAGE:
   - Adequate tests for new functionality
   - Edge cases covered
   - Critical paths tested

REVIEW STANDARD - Flag ANY of these as critical issues:
- BUGS: Logic errors, incorrect behavior, missing edge case handling
- SECURITY: Any security vulnerability
- INCOMPLETE: TODO/FIXME/XXX comments, placeholder code
- BREAKING CHANGES: API/data structure changes without migration path
- TEST FAILURES MISSED: Tests should have caught this but didn't
- CRITICAL QUALITY: Major code quality issues that will cause problems

IF you find ANY critical issues:
  - Add '- [ ] Fix: <specific issue with file:line>' tasks to Phase 2 (IMPLEMENT)
  - Be specific: "Fix: Race condition in auth.py:123 when token expires"
  - Mark current task [x], log to {decisions_file}, STOP
  - Nelson will loop back to Phase 2 → 3 → 4 → 5 for full SDLC cycle

IF no critical issues found (verified ALL categories):
  - Mark task [x], log to {decisions_file}, STOP
  - Nelson advances to Phase 6 (COMMIT)

This is the FINAL checkpoint before commit - be thorough.
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
  - NO docs, .claude/, .nelson/ files
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
    cycle_iterations: int,
    total_iterations: int,
    phase_iterations: int,
    tasks_completed: int,
    current_phase: Phase,
    recent_decisions: str | None = None,
) -> str:
    """Build loop context string for iterations after the first.

    Args:
        cycle_iterations: Number of complete 6-phase cycles
        total_iterations: Total number of phase executions so far
        phase_iterations: Number of iterations in current phase
        tasks_completed: Number of tasks completed so far
        current_phase: Current phase
        recent_decisions: Optional excerpt of recent decision log entries

    Returns:
        Formatted loop context string
    """
    lines = [
        f"LOOP CONTEXT (Cycle {cycle_iterations}, Phase Execution {total_iterations}):",
        f"- Complete cycles so far: {cycle_iterations}",
        f"- Phase executions so far: {total_iterations}",
        f"- Phase iterations in current phase: {phase_iterations}",
        f"- Tasks completed in current plan: {tasks_completed}",
    ]

    if recent_decisions:
        lines.append("")
        lines.append("Recent activity (last few decisions):")
        lines.append(recent_decisions)

    return "\n".join(lines)
