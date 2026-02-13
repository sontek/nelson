"""Prompt generation for Nelson's AI orchestration system.

This module provides the system prompt (generic Nelson instructions) and phase-specific
prompts that guide the AI through the 6-phase autonomous workflow.

Supports depth modes:
- QUICK: Lean prompts, 4 phases (PLAN, IMPLEMENT, TEST, COMMIT)
- STANDARD: Full prompts, 6 phases (adds REVIEW, FINAL_REVIEW)
- COMPREHENSIVE: Full prompts, 8 phases (adds DISCOVER, ROADMAP)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nelson.phases import Phase

if TYPE_CHECKING:
    from nelson.depth import DepthConfig


def get_system_prompt(decisions_file: Path) -> str:
    """Generate condensed system prompt - essential instructions only.

    Args:
        decisions_file: Path to the decisions.md file for logging

    Returns:
        System prompt string for Claude
    """
    return f"""Nelson: 5-phase workflow - PLAN, IMPLEMENT, TEST(loops), REVIEW(→2 if issues), COMMIT

OPERATION: Complete ONE task per call. Read {decisions_file} and plan.md. Mark [x], log, STOP.

RULES:
• Execute and verify (not just document)
• Minimal scope (task only)
• Commit after Phase 2 tasks
• Follow project conventions
• Use Task/Explore for codebase research
• NO: unrelated changes, docs, .claude/.nelson commits
• Stage ONLY: source, tests, config

STATUS BLOCK (required):
---NELSON_STATUS---
STATUS: IN_PROGRESS|COMPLETE|BLOCKED
TASKS_COMPLETED_THIS_LOOP: N
FILES_MODIFIED: N
TESTS_STATUS: PASSING|FAILING|NOT_RUN
WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
EXIT_SIGNAL: true|false
RECOMMENDATION: one-line next step
BLOCKED_REASON: (if BLOCKED) detailed reason
BLOCKED_RESOURCES: (if BLOCKED) resources needed
BLOCKED_RESOLUTION: (if BLOCKED) suggested fix
---END_NELSON_STATUS---

EXIT_SIGNAL=true when: (1) all current phase tasks [x], (2) tests passing, (3) no errors.

ERROR HANDLING: Log to {decisions_file}, STOP. Nelson handles recovery.

IMPLEMENTATION: No TODO/FIXME/XXX. Production-ready code only.
Explain in {decisions_file} if incomplete.

LOG FORMAT:
## [Iteration N] Phase X: Task
**Task:** from plan | **Did:** actions | **Why:** rationale | **Result:** outcome
"""


def _get_lean_system_prompt(decisions_file: Path) -> str:
    """Generate lean system prompt for quick mode.

    Args:
        decisions_file: Path to the decisions.md file for logging

    Returns:
        Lean system prompt string for Claude
    """
    return f"""Nelson: 4-phase workflow - PLAN, IMPLEMENT, TEST, COMMIT

ONE task per call. Read {decisions_file}, plan.md. Mark [x], log, STOP.

RULES: Execute/verify, minimal scope, commit after Phase 2, NO unrelated changes/docs

STATUS (required):
---NELSON_STATUS---
STATUS: IN_PROGRESS|COMPLETE|BLOCKED
TASKS_COMPLETED_THIS_LOOP: N
FILES_MODIFIED: N
TESTS_STATUS: PASSING|FAILING|NOT_RUN
WORK_TYPE: IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING
EXIT_SIGNAL: true|false
RECOMMENDATION: next step
BLOCKED_REASON: (if BLOCKED) reason
---END_NELSON_STATUS---

EXIT_SIGNAL=true when: all phase tasks [x], tests pass, no errors.

LOG: ## [Iteration N] Phase X: Task | **Task:** X | **Did:** Y | **Result:** Z
"""


def get_system_prompt_for_depth(decisions_file: Path, depth: DepthConfig | None = None) -> str:
    """Generate system prompt appropriate for depth mode.

    Args:
        decisions_file: Path to the decisions.md file for logging
        depth: Optional depth configuration (None defaults to standard)

    Returns:
        System prompt string for Claude
    """
    if depth is not None and depth.lean_prompts:
        return _get_lean_system_prompt(decisions_file)
    return get_system_prompt(decisions_file)


def get_phase_prompt(phase: Phase, plan_file: Path, decisions_file: Path) -> str:
    """Generate phase-specific prompt for the given phase.

    Args:
        phase: The phase to generate prompt for
        plan_file: Path to plan.md
        decisions_file: Path to decisions.md

    Returns:
        Phase-specific prompt instructions
    """
    if phase == Phase.DISCOVER:
        return _get_discover_prompt(plan_file, decisions_file)
    elif phase == Phase.PLAN:
        return _get_plan_prompt(plan_file, decisions_file)
    elif phase == Phase.IMPLEMENT:
        return _get_implement_prompt(plan_file, decisions_file)
    elif phase == Phase.TEST:
        return _get_test_prompt(plan_file, decisions_file)
    elif phase == Phase.REVIEW:
        return _get_review_prompt(plan_file, decisions_file)
    elif phase == Phase.COMMIT:
        return _get_commit_prompt(plan_file, decisions_file)
    elif phase == Phase.ROADMAP:
        return _get_roadmap_prompt(plan_file, decisions_file)
    else:
        raise ValueError(f"Unknown phase: {phase}")


def _get_discover_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 0 (DISCOVER) prompt for comprehensive mode."""
    return f"""DISCOVER PHASE - Research and document the codebase BEFORE planning.

CRITICAL: This phase is DOCUMENTATION ONLY. Document what EXISTS, never what SHOULD BE.
Do NOT suggest improvements, recommend changes, or propose solutions.
You are a documentarian, not a critic. Describe the current implementation factually.

Document your findings in {decisions_file}.

RESEARCH TASKS:

1. CODEBASE STRUCTURE:
   - Map the directory structure and identify key modules
   - Find the entry points (main files, CLI, API endpoints) with file:line references
   - Document the build/test/deployment setup (package.json, pyproject.toml, etc.)
   - List the tech stack and major dependencies

2. ARCHITECTURE PATTERNS:
   - Identify architectural patterns used (MVC, hexagonal, monolith, microservices, etc.)
   - Document existing abstractions and interfaces with file:line references
   - Note code organization conventions (naming, file structure)
   - Describe data flow and state management

3. SIMILAR IMPLEMENTATIONS:
   - Search for features similar to what we're building
   - Document code patterns used in similar features with file:line references
   - List reusable components or utilities that exist
   - Note testing patterns and conventions used

4. DEPENDENCIES AND INTEGRATION POINTS:
   - Map external API integrations with file:line references
   - Document database schema and ORM patterns
   - Find configuration management approach
   - Note authentication/authorization patterns

5. COMPLEXITY OBSERVATIONS:
   - Note areas with high cyclomatic complexity (factual observation)
   - Document any deprecated markers or TODO comments found
   - List dependencies between modules
   - Note edge cases handled in existing code

DOCUMENTATION RULES:
- Use file:line references (e.g., src/auth/login.py:45) for all observations
- State facts, not opinions ("X uses pattern Y" not "X should use pattern Y")
- Do NOT include words like "should", "could be improved", "needs", "recommend"
- Do NOT suggest fixes, refactoring, or improvements - that's for PLAN phase

OUTPUT FORMAT:

Document findings in {decisions_file} as:

## [Iteration N] Phase 0: DISCOVER - Codebase Research

### Codebase Structure
- Entry point: src/main.py:1 (CLI entry)
- Key modules: src/auth/ (authentication), src/api/ (endpoints)
- Build system: pyproject.toml uses poetry

### Architecture Patterns
- Pattern: Repository pattern in src/repos/ (src/repos/user.py:10)
- Conventions: snake_case for functions, PascalCase for classes

### Similar Features Found
- Feature X in src/features/x.py:25 uses pattern Y
- Similar validation in src/validators/base.py:100

### Integration Points
- External API: Stripe integration in src/payments/stripe.py:50
- Database: PostgreSQL via SQLAlchemy in src/db/models.py
- Auth: JWT tokens validated in src/auth/middleware.py:30

### Complexity Observations
- Module src/legacy/processor.py has 500+ line functions
- TODO comment at src/api/v1.py:200 notes incomplete feature
- Circular import between src/a.py and src/b.py

---

After documenting findings, output STATUS block with EXIT_SIGNAL=true to advance to PLAN phase.

The PLAN phase will use these findings to make informed implementation decisions.
"""


def _get_plan_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 1 (PLAN) prompt."""
    return f"""Analyze task and create plan.

TASK TYPE: Detect REVIEW (audit/analyze/check), IMPLEMENT (build/add/fix), or BOTH.

REVIEW TASKS:
- Phase 1: Fetch/read diff, apply review checklist, document findings
- Phase 2: Add Fix task for EACH issue (with file:line)

IMPLEMENT TASKS:
- Phase 1: 2-4 analysis tasks
- Phase 2: Atomic implementation tasks (one commit each)

FILE:LINE REFERENCES:
Use specific file:line references throughout the plan (e.g., src/auth/login.py:45).
This helps:
- Locate exact code locations for implementation
- Verify changes were made to the correct locations
- Create precise Fix: tasks with context

CLARIFYING QUESTIONS (Optional but encouraged for ambiguous tasks):
Before creating the plan, identify 1-3 clarifying questions about ambiguous requirements.
Only ask questions when the answer would significantly change your approach.

Output questions in a ```questions JSON block:
```questions
[
  {{
    "id": "q1",
    "question": "Your question here?",
    "options": ["Option A", "Option B"],
    "default": "Option A",
    "context": "Why this matters for the plan",
    "category": "requirements|architecture|scope|preferences"
  }}
]
```

Categories:
- requirements: Core functionality unclear (highest priority)
- architecture: Multiple valid approaches exist
- scope: Boundaries undefined
- preferences: Style/convention choices (lowest priority)

If no questions needed, output empty array: ```questions\n[]\n```
After questions are answered (or if none needed), create the implementation plan.

Create a plan at {plan_file} with 5 phases:
- Format: '- [ ] description' for unchecked, '- [x] description' for checked
- Phase 3 (TEST): Add task(s) for running tests/linter/type-checker
- Phase 4 (REVIEW): Add task '- [ ] Review all changes: bugs, patterns, quality, security'
- Phase 5 (COMMIT): Add task '- [ ] Commit any remaining changes'

IMPORTANT - NO MANUAL SUB-TASKS IN PLAN:
- Do NOT create indented sub-tasks that require human action (manual testing, UI review, etc.)
- Do NOT add checklists under tasks like "- [ ] Test X manually" or "- [ ] Verify Y in browser"
- These block phase transitions since they can never be auto-completed
- Instead: Create a "POST-IMPLEMENTATION.md" document at the end with manual verification steps
- The plan should ONLY contain tasks that can be completed autonomously

VERIFICATION SUBTASKS (labeled "FINAL VERIFICATION STEPS" in task):
- These are verification/completion steps - NOT the main task
- The MAIN TASK is described BEFORE the verification steps section
- First create Phase 2 tasks for the MAIN TASK (review findings, implementation, etc.)
- Add verification subtasks at the END of Phase 2 (after all main work tasks)
- Do NOT skip the main task just because subtasks exist - subtasks are final checks

EXIT_SIGNAL in Phase 1:
- If this is a NEW cycle and there's work to plan: EXIT_SIGNAL=true (advance to Phase 2)
- If reviewing previous cycle's work and ALL complete: EXIT_SIGNAL=true with note in plan
- If rebuilding context: Check if original task is 100% complete before creating empty phases

"""


def _get_implement_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 2 (IMPLEMENT) prompt."""
    return f"""Find FIRST unchecked Phase 2 task.

TASK TYPE DETECTION:
- If task starts with "Fix:" → This is a REVIEW FINDING - implement the specific fix
- If task is "No fixes needed" → Mark [x] and verify the review was thorough
- Otherwise → This is an IMPLEMENTATION task

FOR "Fix:" TASKS (from code review):
- Read the specific file:line mentioned
- Understand the issue from Phase 1 findings in {decisions_file}
- Implement the fix properly (not a band-aid)
- Stage: git add (ONLY files you modified)
- Commit: git commit with message like "fix: <what was fixed>"

FOR IMPLEMENTATION TASKS:
- Complete ONE task: code/tests/config only
- Stage: git add (ONLY files you modified)
- Commit: git commit with descriptive message for THIS task

AUTO-FIX DEVIATIONS:
You may apply these automatic fixes inline without stopping:
- **AUTO_FIX_BUGS**: Fix type errors, logic bugs, undefined variables
- **AUTO_ADD_CRITICAL**: Add missing input validation, error handling, null checks
- **AUTO_INSTALL_DEPS**: Install missing packages (npm install / pip install)

When you apply any auto-fix, include a DEVIATIONS block in your response:
```deviations
[
  {{
    "rule": "auto_fix_bugs",
    "issue": "TypeError: 'NoneType' has no attribute 'name'",
    "fix_applied": "Added null check before accessing .name",
    "files_affected": ["handler.py"]
  }}
]
```

COMMON:
- NO docs (SUMMARY.md, guides)
- Testing: 20% effort, new features only, Phase 3 is main testing
- Each task = one atomic commit

CRITICAL: No TODO/FIXME/XXX. Production-ready code only.
"""


def _get_review_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 4 (REVIEW) prompt - consolidated review after tests pass."""
    # Get path to Nelson's review checklist template
    template_path = Path(__file__).parent / "templates" / "review-checklist.md"

    # Use template if it exists, otherwise fall back to embedded checklist
    if template_path.exists():
        checklist_instruction = f"Apply comprehensive checklist from {template_path}"
    else:
        # Fallback: embedded checklist
        checklist_instruction = """Apply comprehensive review checklist:
1. CORRECTNESS & BUGS: Logic errors, edge cases, error handling
2. SECURITY: No SQL injection, XSS, hardcoded secrets
3. COMPLETENESS: No TODO/FIXME/XXX, production-ready
4. PATTERNS: Follows codebase conventions
5. CODE QUALITY: Readable, no duplication
6. UNWANTED: No docs/refactoring outside scope"""

    return f"""Find FIRST unchecked Phase 4 task.

IF task is "Review all changes" or similar review task:
  Determine what to review:
  1. git status - Check for uncommitted changes → Review with git diff HEAD
  2. git diff main...HEAD - Check committed branch changes
  3. Choose higher priority (uncommitted > committed)

  {checklist_instruction}
  Flag ANY blocking issues (bugs, security, incomplete code, breaking changes,
  hardcoded values, missing tests, pattern violations)

  IF blocking issues found:
    - Add '- [ ] Fix: <specific issue with file:line>' to Phase 2 (IMPLEMENT)
    - ALWAYS include file:line reference (e.g., src/auth.py:123)
    - Be specific: "Fix: Race condition in auth.py:123 when token expires"
    - Mark current review task [x], log to {decisions_file}, STOP
    - Nelson will loop back to Phase 2 → TEST → REVIEW (full SDLC cycle)

  IF no blocking issues found (verified ALL categories):
    - Mark task [x], log to {decisions_file}, STOP
    - Nelson advances to Phase 5 (COMMIT)

IF task starts with "Fix:":
  - Fix the ONE specific issue described in the task
  - Stage changes: git add (ONLY files you modified)
  - Create commit with message describing the fix
  - Mark task [x], log to {decisions_file}, STOP

IF task is "Verify goal" or similar verification task:
  Run GOAL-BACKWARD VERIFICATION:
  1. EXISTS: Verify expected files/directories exist
  2. SUBSTANTIVE: No placeholder code (TODO, FIXME, XXX, pass, ...)
  3. WIRED: Components connected (imports/calls exist)
  4. FUNCTIONAL: Run functional checks, verify output

  Output verification results in ```verification block:
  ```verification
  {{
    "goal": "Feature description",
    "checks": [
      {{"level": "exists", "target": "file.py", "passed": true, "result": "Exists"}},
      {{"level": "substantive", "target": "file.py", "passed": true, "result": "OK"}},
      {{"level": "wired", "target": "main->utils", "passed": true, "result": "Found"}},
      {{"level": "functional", "target": "curl", "passed": true, "result": "200 OK"}}
    ],
    "passed": true
  }}
  ```

  IF verification fails ANY check:
    - Add '- [ ] Fix: <verification failure>' tasks to Phase 2 (IMPLEMENT)
    - Mark current task [x], log to {decisions_file}, STOP
    - Nelson loops back for full cycle

  IF all verification passes:
    - Mark task [x], log to {decisions_file}, STOP
    - Nelson advances to Phase 5 (COMMIT)

CRITICAL: This is the final quality gate before commit.
Tests passed (Phase 3), now verify code quality, patterns, and completeness.
"""


def _get_test_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 3 (TEST) prompt."""
    return f"""Find FIRST unchecked Phase 3 task.

IF task is "run tests":
  1. EXECUTE tests/linter/type-checker (use justfile, package.json, or direct commands)

  2. ANALYZE TEST FAILURES:
     If tests fail, investigate the root cause:

     **Infrastructure/Environment Issues** (Docker, services, databases, etc.):
     - Check if services are running: docker ps, docker-compose ps
     - Check service logs: docker-compose logs <service>
     - Check port availability: lsof -i :<port> or netstat
     - Check database connections: Can services reach the database?
     - Check network: Are containers on same network? docker network inspect
     - Check environment variables: Are required vars set? Check .env files
     - Check service health: docker-compose exec <service> <health-check-command>
     - Check startup order: Do services have proper depends_on and health checks?

     **Code/Logic Issues** (bugs, broken imports, etc.):
     - Check error messages and stack traces
     - Identify which test failed and why
     - Review recent code changes that might have broken tests

  3. CREATE FIX TASKS:
     Based on the root cause analysis, add specific fix tasks to Phase 4:

     For infrastructure issues:
     - '- [ ] Fix: Start missing service X'
     - '- [ ] Fix: Configure database connection in docker-compose.yml'
     - '- [ ] Fix: Add health check for service X'
     - '- [ ] Fix: Set missing environment variable Y'
     - '- [ ] Fix: Update service startup order to wait for database'

     For code issues:
     - '- [ ] Fix: <specific bug description with file:line>'

     Always add a re-run task:
     - '- [ ] Re-run tests after fixes'

  4. Mark the original "run tests" task [x], log findings to {decisions_file}, STOP

  IMPORTANT:
  - ALL test failures must be investigated and fixed (infrastructure OR code)
  - Do NOT dismiss failures as "infrastructure issues" - fix them
  - Tests must pass before workflow can advance to Phase 5

IF task is "Fix: X":
  - Investigate and fix the ONE specific issue described
  - For infrastructure fixes: modify docker-compose.yml, .env, scripts, etc.
  - For code fixes: modify source/test files
  - Verify the fix worked (run relevant command/test)
  - Stage and commit the fix: git add <files>; git commit -m "fix: <description>"
  - Mark [x], log to {decisions_file}, STOP

IF task is "Re-run tests after fixes":
  - Execute the same test command(s) from the original "run tests" task
  - If passing: Mark [x], STOP
  - If still failing: Investigate further, add more fix tasks, mark [x], STOP

When all Phase 4 tasks [x]: Nelson advances to Phase 5
"""


def _get_commit_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 5 (COMMIT) prompt."""
    return """Find FIRST unchecked Phase 5 task.

Check git status:

NO uncommitted changes:
  - All work committed in Phase 2/3/4/5
  - Mark task [x], STOP

HAS uncommitted changes:
  - Stage ONLY: source code, tests, config files
  - NO docs, .claude/, .nelson/ files
  - Create commit with descriptive message
  - Mark task [x], STOP

MANUAL VERIFICATION STEPS (if applicable):
If the implementation requires manual steps (UI testing, browser checks, deployment, etc.):
  - Create POST-IMPLEMENTATION.md with sections:
    * Manual Testing Steps - How to verify the changes work
    * Deployment Notes - Any deployment considerations
    * User Actions Required - Steps users need to take
    * Known Limitations - Edge cases or limitations
  - This document helps humans complete tasks that can't be automated
  - Do NOT add these as blocking sub-tasks in the plan

Most commits happen in Phase 2. This phase handles any remaining changes.
"""


def _get_roadmap_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate Phase 7 (ROADMAP) prompt for comprehensive mode."""
    return f"""ROADMAP PHASE - Document future improvements and technical debt.

This is the final phase. Implementation is complete and committed.
Now document insights for future development.

Read {decisions_file} for context on what was implemented.

DOCUMENTATION TASKS:

1. FUTURE IMPROVEMENTS:
   - Features that could enhance this implementation
   - Performance optimizations identified but not implemented
   - Edge cases that could be handled better
   - User experience improvements

2. TECHNICAL DEBT:
   - Shortcuts taken that should be revisited
   - Areas where code could be refactored
   - Patterns that don't match codebase conventions
   - Dependencies that should be updated

3. TESTING GAPS:
   - Edge cases not covered by tests
   - Integration tests that would be valuable
   - Performance testing opportunities
   - Scenarios that need manual verification

4. DOCUMENTATION NEEDS:
   - Features that need user documentation
   - API changes that need developer docs
   - Architecture decisions that should be recorded
   - Onboarding improvements for new contributors

5. RELATED WORK:
   - Follow-up tasks that naturally extend this work
   - Related features that could be implemented
   - Refactoring opportunities in adjacent code
   - Integration points for other systems

OUTPUT FORMAT:

Create a ROADMAP.md file (or append to existing) with:

## Roadmap for [Feature Name]

### Future Improvements
- [ ] Improvement 1: Description
- [ ] Improvement 2: Description

### Technical Debt
- [ ] Debt item 1: Why and how to address
- [ ] Debt item 2: Why and how to address

### Testing Gaps
- [ ] Test scenario 1
- [ ] Test scenario 2

### Documentation Needs
- [ ] Doc item 1
- [ ] Doc item 2

### Related Work
- [ ] Related task 1
- [ ] Related task 2

---

Also log summary to {decisions_file}:

## [Iteration N] Phase 7: ROADMAP - Future Work Documented

**Items Documented:** N improvements, N debt items, N test gaps
**Roadmap File:** ROADMAP.md
**Key Priorities:**
1. Priority item 1
2. Priority item 2

---

After documenting, output STATUS block with EXIT_SIGNAL=true.

The workflow is now complete. Roadmap provides visibility for future development.
"""


# =============================================================================
# LEAN PROMPTS (for QUICK mode - minimal instructions)
# =============================================================================


def _get_lean_plan_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate lean Phase 1 (PLAN) prompt for quick mode."""
    return f"""Read {decisions_file}, git status. Analyze task briefly.

Create plan at {plan_file} with 4 phases:
- Phase 1 (PLAN): 1-2 analysis tasks
- Phase 2 (IMPLEMENT): Break into atomic tasks (one commit each)
- Phase 3 (TEST): Run tests/linter
- Phase 4 (COMMIT): Final commit if needed

Format: '- [ ] task' unchecked, '- [x] task' checked

IMPORTANT: Do NOT add manual sub-tasks (UI checks, manual tests)
Create POST-IMPLEMENTATION.md instead

Mark tasks [x], log to {decisions_file}, STOP.
"""


def _get_lean_implement_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate lean Phase 2 (IMPLEMENT) prompt for quick mode."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 2 task.

Do ONE task:
- Write code/tests/config
- git add (only modified files)
- git commit with descriptive message
- Mark [x], log to {decisions_file}, STOP
"""


def _get_lean_test_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate lean Phase 3 (TEST) prompt for quick mode."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 3 task.

Run tests/linter/type-checker:
- Investigate failures (infrastructure OR code):
  * Check services: docker ps, docker-compose logs
  * Check database connections, environment variables
  * Check error messages and stack traces
- Add specific fix tasks (infrastructure or code) to Phase 3
- Add '- [ ] Re-run tests' task
- Mark current [x], STOP

Fix tasks:
- For infrastructure: Fix docker-compose, services, env vars, etc.
- For code: Fix bugs, imports, logic errors
- Verify fix works, stage, commit, mark [x], STOP

IMPORTANT: Do NOT dismiss test failures as "infrastructure issues" - investigate and fix them.
"""


def _get_lean_commit_prompt(plan_file: Path, decisions_file: Path) -> str:
    """Generate lean Phase 4 (COMMIT) prompt for quick mode."""
    return f"""Read {decisions_file}, {plan_file}. Find FIRST unchecked Phase 4 task.

git status:
- No changes: Mark [x], STOP
- Has changes: Stage source/tests/config, commit, mark [x], STOP

If manual steps needed: Create POST-IMPLEMENTATION.md with verification steps
"""


def get_phase_prompt_for_depth(
    phase: Phase,
    plan_file: Path,
    decisions_file: Path,
    depth: DepthConfig | None = None,
) -> str:
    """Generate phase-specific prompt appropriate for depth mode.

    Args:
        phase: The phase to generate prompt for
        plan_file: Path to plan.md
        decisions_file: Path to decisions.md
        depth: Optional depth configuration (None defaults to standard)

    Returns:
        Phase-specific prompt instructions
    """
    if depth is not None and depth.lean_prompts:
        # Quick mode uses lean prompts and maps to 4-phase workflow
        if phase == Phase.PLAN:
            return _get_lean_plan_prompt(plan_file, decisions_file)
        elif phase == Phase.IMPLEMENT:
            return _get_lean_implement_prompt(plan_file, decisions_file)
        elif phase == Phase.TEST:
            return _get_lean_test_prompt(plan_file, decisions_file)
        elif phase == Phase.COMMIT:
            return _get_lean_commit_prompt(plan_file, decisions_file)
        # REVIEW and FINAL_REVIEW are skipped in quick mode
        # but return standard prompt as fallback
        return get_phase_prompt(phase, plan_file, decisions_file)

    # Standard/Comprehensive mode uses full prompts
    return get_phase_prompt(phase, plan_file, decisions_file)


def build_full_prompt(
    original_task: str,
    phase: Phase,
    plan_file: Path,
    decisions_file: Path,
    loop_context: str | None = None,
    depth: DepthConfig | None = None,
) -> str:
    """Build the complete prompt combining task, context, and phase instructions.

    Args:
        original_task: The user's original task description
        phase: Current phase
        plan_file: Path to plan.md
        decisions_file: Path to decisions.md
        loop_context: Optional context from previous iterations
        depth: Optional depth configuration for lean/full prompts

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

    parts.append(get_phase_prompt_for_depth(phase, plan_file, decisions_file, depth))

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
        cycle_iterations: Current cycle number (1-indexed, e.g., 1 for first cycle)
        total_iterations: Total number of API calls/iterations so far (across all phases)
        phase_iterations: Number of API calls within the current phase
        tasks_completed: Number of tasks completed so far
        current_phase: Current phase
        recent_decisions: Optional excerpt of recent decision log entries

    Returns:
        Formatted loop context string
    """
    lines = [
        f"LOOP CONTEXT (Cycle {cycle_iterations}, API Call #{total_iterations}):",
        # cycle_iterations is 1-indexed current cycle
        f"- Completed cycles: {cycle_iterations - 1}",
        f"- Total API calls so far: {total_iterations}",
        f"- API calls in current phase: {phase_iterations}",
        f"- Tasks completed in current plan: {tasks_completed}",
    ]

    if recent_decisions:
        lines.append("")
        lines.append("Recent activity (last few decisions):")
        lines.append(recent_decisions)

    return "\n".join(lines)
