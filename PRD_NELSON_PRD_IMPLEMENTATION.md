# PRD: nelson-prd Implementation

**Product**: nelson-prd - Multi-task orchestration for Nelson
**Version**: 1.0
**Date**: 2026-01-13
**Owner**: Nelson Team

## Overview

Implement `nelson-prd`, a companion CLI tool that orchestrates multiple Nelson workflows from a Product Requirements Document (PRD). This enables autonomous execution of multi-task projects with robust state tracking, blocking support, and resume capabilities.

## Goals

1. Enable users to define multiple tasks in a markdown PRD file with explicit IDs (PRD-NNN)
2. Automatically execute tasks by priority with Nelson
3. Support blocking tasks when dependencies are missing
4. Provide seamless resume capabilities with context
5. Track per-task state, costs, branches, and progress
6. Automatically create and manage git branches per task

## Implementation Tasks

## High Priority

- [x] PRD-001 Create PRD parser to extract tasks from markdown with priority sections
- [x] PRD-002 Add support for parsing explicit task IDs in format: `- [ ] PRD-NNN Task description`
- [x] PRD-003 Add support for parsing status indicators: `[ ]`, `[~]`, `[x]`, `[!]`
- [x] PRD-004 Implement task ID validation (check for missing IDs, duplicate IDs, invalid format)
- [x] PRD-005 Build TaskState dataclass with all required fields (task_id, status, branch, cost, timestamps, etc.)
- [x] PRD-006 Implement TaskState serialization to/from JSON in `.nelson/prd/PRD-NNN/state.json`
- [x] PRD-007 Create PRDState dataclass for overall orchestration state
- [x] PRD-008 Implement task mapping storage in `.nelson/prd/prd-state.json`
- [x] PRD-009 Build PRDStateManager for coordinating task state transitions
- [x] PRD-010 Implement git branch creation logic with format: `feature/PRD-NNN-description`
- [x] PRD-011 Add branch slugification from task description (lowercase, alphanumeric, ~40 chars)
- [x] PRD-012 Create basic PRD orchestrator that invokes Nelson CLI for each task
- [x] PRD-013 Implement priority-based task ordering (High → Medium → Low)
- [x] PRD-014 Add automatic branch creation and switching when starting tasks
- [x] PRD-015 Add basic CLI entry point using Click framework
- [x] PRD-016 Implement `nelson-prd <file>` command to execute all pending tasks
- [x] PRD-017 Add state persistence after each task execution
- [x] PRD-018 Create `.nelson/prd/` directory structure automatically
- [x] PRD-019 Add cost tracking integration with Nelson's cost reporting

## Medium Priority

- [x] PRD-020 Implement `--block <task-id> --reason <text>` command to mark tasks as blocked
- [x] PRD-021 Add blocking state transition logic (in_progress → blocked)
- [x] PRD-022 Update PRD markdown file when task is blocked (status indicator + reason)
- [x] PRD-023 Implement task skipping logic in orchestrator for blocked tasks
- [x] PRD-024 Create `--unblock <task-id>` command to mark tasks as ready
- [x] PRD-025 Add optional `--context <text>` parameter for unblock command to store resume info
- [x] PRD-026 Implement resume context storage in TaskState (free-form text field)
- [x] PRD-027 Build `--resume-task <task-id>` command to resume specific blocked task
- [x] PRD-028 Add resume context injection into Nelson prompt when resuming (prepend to prompt)
- [x] PRD-029 Implement automatic branch switching when resuming blocked tasks
- [x] PRD-030 Implement `--status` command showing all tasks with IDs and current state
- [x] PRD-031 Create rich status output with visual indicators (✓, ~, !, ○)
- [x] PRD-032 Display branch names in status output (e.g., `Branch: feature/PRD-001-add-auth`)
- [x] PRD-033 Implement `--task-info <task-id>` command for detailed task information
- [x] PRD-034 Store Nelson run ID in TaskState for linking to run directories
- [x] PRD-035 Add phase and phase_name tracking from Nelson state
- [x] PRD-036 Implement `--resume` command to continue from last incomplete task
- [x] PRD-037 Add `--dry-run` mode to preview tasks without execution
- [x] PRD-038 Create per-task cost accumulation from Nelson's cost reporting
- [x] PRD-039 Add aggregate cost display in status output
- [x] PRD-040 Implement iteration count tracking per task
- [x] PRD-041 Add blocking reason parsing from markdown (for manual edits)
- [x] PRD-042 Create task text change detection with warnings (when text after PRD-NNN changes)
- [x] PRD-043 Implement line number tracking for tasks in PRD file
- [x] PRD-044 Create comprehensive error handling with helpful messages
- [x] PRD-045 Implement atomic PRD file updates to prevent corruption
- [x] PRD-046 Create backup mechanism for PRD file before modifications
- [ ] PRD-047 Add verbose logging mode for debugging
- [x] PRD-048 Implement environment variable inheritance for Nelson config
- [x] PRD-049 Add support for NELSON_MAX_ITERATIONS per task
- [x] PRD-050 Create rich console output with progress indicators
- [x] PRD-051 Add timestamp formatting in human-readable format
- [ ] PRD-052 Implement completed task archival (optional)
- [ ] PRD-053 Add git branch cleanup command for completed tasks
- [x] PRD-054 Write comprehensive unit tests for task ID validation (PRD-NNN format)
- [x] PRD-055 Add tests for duplicate ID detection
- [x] PRD-056 Add tests for PRD parser with various markdown formats
- [x] PRD-057 Create tests for branch name generation and slugification
- [x] PRD-058 Create tests for TaskState serialization/deserialization
- [x] PRD-059 Write tests for PRDStateManager state transitions
- [x] PRD-060 Add integration tests for end-to-end PRD execution with mock Nelson
- [x] PRD-061 Create tests for blocking/unblocking workflow
- [x] PRD-062 Add tests for resume context storage and retrieval
- [x] PRD-063 Add tests for resume context injection into prompts
- [x] PRD-064 Add tests for automatic branch creation and switching
- [x] PRD-065 Create fixture PRD files for testing (with explicit IDs)
- [x] PRD-066 Add tests for cost aggregation
- [x] PRD-067 Write CLI usage documentation
- [x] PRD-068 Create example PRD files with PRD-NNN format
- [x] PRD-069 Add troubleshooting guide
- [x] PRD-070 Document state file formats
- [x] PRD-071 Document branch naming conventions
- [x] PRD-072 Add architecture documentation
- [ ] PRD-073 Write contributing guidelines for PRD features

## Success Criteria

1. ✓ Users can define tasks with explicit IDs (PRD-001, PRD-002, etc.)
2. ✓ Parser validates that all tasks have unique IDs
3. ✓ Users can execute multi-task PRDs with `nelson-prd requirements.md`
4. ✓ Tasks execute in priority order (High → Medium → Low)
5. ✓ Branches are automatically created with format `feature/PRD-NNN-description`
6. ✓ Users can block tasks with `--block` and resume with `--resume-task`
7. ✓ Resume context successfully prepends to prompt when resuming tasks
8. ✓ Branch automatically switches when resuming blocked tasks
9. ✓ Status command shows clear task breakdown with IDs and branches
10. ✓ State persists across sessions and recovers from interruptions
11. ✓ Per-task costs are tracked and displayed
12. ✓ All tests pass with >90% coverage

## Resolved Design Decisions

1. **Task ID Format**: Explicit IDs required (PRD-001, PRD-002, etc.)
   - Users specify IDs in markdown: `- [ ] PRD-001 Task description`
   - Parser validates uniqueness and format
   - More stable than auto-generated slugs

2. **Task ID Stability**: Strict matching with warnings
   - Store original task text in mapping
   - Warn if text after PRD-NNN changes
   - Require user confirmation for changes

3. **Blocking**: Manual only for v1
   - User explicitly runs `--block` command
   - Can add auto-detection in future versions

4. **Resume Context**: Free-form text prepended to prompt
   - Simple string field: `resume_context: "API keys added to .env"`
   - When resuming, prepend to Nelson prompt
   - Can add structured JSON in future if needed

5. **Branch Management**: Auto-create with descriptive names
   - Format: `feature/PRD-NNN-{slugified-description}`
   - Example: `feature/PRD-001-add-user-authentication`
   - Automatically create and switch branches
   - Slugification: lowercase, alphanumeric + hyphens, ~40 chars

6. **Task Dependencies**: Not in v1
   - Manual blocking serves as dependency mechanism
   - Can add DAG-based execution in v2

7. **Task Reordering**: Not applicable
   - Explicit IDs don't change when tasks are reordered
   - IDs provide stable references

## Non-Goals (Out of Scope for v1)

- Task dependency resolution (DAG execution)
- Parallel task execution
- Automatic blocking detection by Nelson
- Structured resume context (JSON-based)
- Automatic branch merging (creation is in scope)
- Task templating or variables
- Multiple PRD format support (YAML, JSON)
- Rollback support
- Progress webhooks
- Sub-tasks or nested task lists
- Custom priority levels beyond High/Medium/Low

## Technical Architecture

### Directory Structure
```
.nelson/
  prd/
    prd-state.json                                    # Overall PRD state with task mapping
    PRD-001/
      state.json                                       # Per-task state
    PRD-002/
      state.json
    PRD-003/
      state.json
```

### Example PRD Markdown Format
```markdown
# My Feature Implementation PRD

## High Priority
- [ ] PRD-101 Add user authentication system
- [ ] PRD-102 Create user profile management
- [!] PRD-103 Add payment integration (blocked: waiting for Stripe API access)

## Medium Priority
- [~] PRD-104 Add email notification system
- [ ] PRD-105 Implement search functionality

## Low Priority
- [ ] PRD-106 Dark mode toggle
```

### Key Components
- `prd_parser.py` - Markdown parsing, task extraction, ID validation
- `prd_task_state.py` - TaskState dataclass and serialization
- `prd_state.py` - PRDState and PRDStateManager
- `prd_orchestrator.py` - Main execution loop with branch management
- `prd_branch.py` - Git branch creation and switching utilities
- `nelson-prd` - CLI entry point (Click-based)

### Example State Files

**`.nelson/prd/PRD-001/state.json`**:
```json
{
  "task_id": "PRD-001",
  "task_text": "Add user authentication system",
  "status": "in_progress",
  "priority": "high",
  "branch": "feature/PRD-001-add-user-authentication-system",
  "resume_context": null,
  "blocking_reason": null,
  "nelson_run_id": "run-20250115-143022",
  "started_at": "2025-01-15T14:30:22Z",
  "updated_at": "2025-01-15T15:45:10Z",
  "completed_at": null,
  "blocked_at": null,
  "cost_usd": 0.89,
  "iterations": 12,
  "phase": 3,
  "phase_name": "IMPLEMENT"
}
```

**`.nelson/prd/prd-state.json`**:
```json
{
  "prd_file": "requirements.md",
  "started_at": "2025-01-15T14:00:00Z",
  "updated_at": "2025-01-15T16:30:45Z",
  "total_cost_usd": 5.67,
  "task_mapping": {
    "PRD-001": {
      "original_text": "Add user authentication system",
      "priority": "high",
      "line_number": 3
    },
    "PRD-002": {
      "original_text": "Create user profile management",
      "priority": "high",
      "line_number": 4
    }
  },
  "tasks": {
    "PRD-001": {"status": "in_progress", "cost_usd": 0.89},
    "PRD-002": {"status": "pending", "cost_usd": 0.0}
  },
  "current_task_id": "PRD-001",
  "completed_count": 0,
  "in_progress_count": 1,
  "blocked_count": 0,
  "pending_count": 1
}
```

### Integration Points
- Uses Nelson CLI as subprocess for task execution
- Reads Nelson's `state.json` for cost and iteration data
- Inherits environment variables for Nelson configuration
- Links to Nelson run directories via run IDs
- Uses git CLI for branch creation and switching

### CLI Commands and Usage

```bash
# Execute all pending tasks in PRD
nelson-prd requirements.md

# Check status of all tasks
nelson-prd --status requirements.md
# Output shows:
#   PRD-001 [~] Add user authentication (in progress, branch: feature/PRD-001-add-user-auth)
#   PRD-002 [ ] Create user profile (pending)
#   PRD-003 [!] Add payment integration (blocked: waiting for Stripe API)

# Block a task when hitting external dependency
nelson-prd --block PRD-003 --reason "Waiting for Stripe API keys" requirements.md

# Unblock a task with resume context
nelson-prd --unblock PRD-003 --context "API keys added to .env as STRIPE_SECRET_KEY" requirements.md

# Resume a specific blocked task
nelson-prd --resume-task PRD-003 requirements.md

# Get detailed info about a task
nelson-prd --task-info PRD-001 requirements.md
# Shows: status, branch, run ID, cost, iterations, phase, resume context

# Preview tasks without executing
nelson-prd --dry-run requirements.md

# Configure per-task behavior via environment variables
NELSON_MAX_ITERATIONS=100 nelson-prd requirements.md
NELSON_AUTO_APPROVE_PUSH=true nelson-prd requirements.md
```

## Timeline (No specific dates)

**Phase 1**: Core functionality (High priority tasks)
- Basic PRD parsing and execution
- State management and persistence
- Cost tracking integration

**Phase 2**: Blocking and resume (Medium priority tasks)
- Blocking/unblocking workflow
- Resume context storage
- Enhanced status reporting

**Phase 3**: Polish and testing (Low priority + documentation)
- Dry-run mode
- Comprehensive testing
- Documentation and examples

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Duplicate task IDs in PRD | High | Validate on parse, error immediately with clear message |
| Missing task IDs in PRD | High | Validate on parse, error immediately listing all tasks without IDs |
| Task ID format violations | Medium | Regex validation, error with format requirements |
| Branch name conflicts | Medium | Check if branch exists before creation, error if exists |
| Task text changes after ID assignment | Medium | Store original text, warn on changes, require confirmation |
| State file corruption | High | Atomic writes, backup before modifications |
| Nelson CLI changes breaking integration | Medium | Use stable CLI interfaces, version checking |
| Task status divergence between PRD file and state | Medium | Always sync state to PRD file atomically |
| Resume context not providing enough info | Low | Start simple, iterate based on user feedback |
| Branch switching fails mid-task | Medium | Check git status before switching, warn on uncommitted changes |

## Metrics

- Number of PRDs executed per week
- Average tasks per PRD
- Task blocking frequency
- Resume success rate
- Cost savings from resume (vs starting over)
- User satisfaction with blocking/resume UX
- Branch creation success rate
- Average time to resume blocked tasks

## User Workflow Example

**Scenario**: User has a PRD with 5 tasks to implement

1. **Create PRD markdown**:
   ```markdown
   ## High Priority
   - [ ] PRD-001 Add user authentication system
   - [ ] PRD-002 Create user profile management
   - [ ] PRD-003 Add payment integration

   ## Medium Priority
   - [ ] PRD-004 Add email notification system
   - [ ] PRD-005 Dark mode toggle
   ```

2. **Start execution**:
   ```bash
   nelson-prd requirements.md
   ```
   - nelson-prd creates branch `feature/PRD-001-add-user-authentication-system`
   - Runs Nelson for PRD-001
   - Marks task as in-progress: `[~] PRD-001`

3. **Task gets blocked** (missing API keys):
   ```bash
   nelson-prd --block PRD-001 --reason "Waiting for Auth0 API keys"
   ```
   - PRD file updates: `[!] PRD-001 (blocked: Waiting for Auth0 API keys)`
   - Task state saved with blocking reason

4. **Continue with next task**:
   ```bash
   nelson-prd requirements.md
   ```
   - Skips PRD-001 (blocked)
   - Creates branch `feature/PRD-002-create-user-profile-management`
   - Starts PRD-002

5. **Later, unblock PRD-001**:
   ```bash
   nelson-prd --unblock PRD-001 --context "Auth0 keys added to .env as AUTH0_CLIENT_ID and AUTH0_SECRET"
   ```
   - Task state updated with resume context
   - PRD file updates: `[ ] PRD-001`

6. **Resume blocked task**:
   ```bash
   nelson-prd --resume-task PRD-001
   ```
   - Switches to branch `feature/PRD-001-add-user-authentication-system`
   - Runs Nelson with prepended context about Auth0 keys
   - Continues from Phase 3 (where it left off)

7. **Check overall progress**:
   ```bash
   nelson-prd --status requirements.md
   ```
   - Shows all tasks with status, branches, costs
   - Displays aggregate metrics
