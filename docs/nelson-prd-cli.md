# nelson-prd CLI Reference

Complete command-line reference for `nelson-prd`, the multi-task orchestration tool for Nelson.

## Synopsis

```bash
nelson-prd [OPTIONS] PRD_FILE
```

## Description

`nelson-prd` orchestrates multiple Nelson workflows from a Product Requirements Document (PRD). It executes tasks in priority order, manages git branches, tracks state, and supports blocking/resuming tasks that encounter external dependencies.

## Arguments

### `PRD_FILE`
**Type:** Path (required)
**Description:** Path to the PRD markdown file containing tasks with explicit IDs (PRD-NNN format)

**Example:**
```bash
nelson-prd requirements.md
nelson-prd ./docs/sprint-1.md
```

## Options

### Execution Control

#### `--dry-run`
**Type:** Flag
**Default:** False
**Description:** Preview tasks that would be executed without actually running them. Shows task order and status.

**Example:**
```bash
nelson-prd --dry-run requirements.md
```

**Output:**
```
Dry run - would execute these tasks:
  PRD-001 (high): Implement user authentication
  PRD-002 (high): Create user profile management
  PRD-004 (medium): Add email notifications

Skipping:
  PRD-003 (high): blocked - Waiting for Stripe API keys
```

---

#### `--stop-on-failure`
**Type:** Flag
**Default:** True
**Description:** Stop execution when a task fails. Set to false to continue with remaining tasks even if one fails.

**Example:**
```bash
# Continue with remaining tasks even if one fails
nelson-prd --stop-on-failure=false requirements.md
```

---

#### `--nelson-args ARGS`
**Type:** String
**Default:** None
**Description:** Additional arguments to pass to Nelson subprocess. Space-separated string of Nelson CLI options.

**Example:**
```bash
# Use opus model for all tasks
nelson-prd --nelson-args "--model opus" requirements.md

# Multiple arguments
nelson-prd --nelson-args "--model opus --max-iterations 20" requirements.md

# Auto-approve pushes
nelson-prd --nelson-args "--auto-approve-push" requirements.md
```

**Common Nelson Arguments:**
- `--model opus|sonnet|haiku` - AI model to use
- `--max-iterations N` - Maximum cycles per task
- `--plan-model MODEL` - Model for planning phase
- `--auto-approve-push` - Skip push approval prompts
- `--claude-command CMD` - Claude command to use

---

### Status & Information

#### `--status`
**Type:** Flag
**Default:** False
**Description:** Display current status of all tasks in the PRD including completion counts, cost, and detailed task breakdown.

**Example:**
```bash
nelson-prd --status requirements.md
```

**Output:**
```
PRD Status: requirements.md

Tasks by Status:
  ✓ Completed: 2
  ~ In Progress: 1
  ! Blocked: 1
  ○ Pending: 3

Task Details:
  PRD-001 [✓] Implement user authentication
    Status: completed
    Branch: feature/PRD-001-implement-user-authentication
    Cost: $0.45
    Iterations: 8

  PRD-002 [~] Create user profile management
    Status: in_progress
    Branch: feature/PRD-002-create-user-profile-management
    Cost: $0.23 (incomplete)
    Iterations: 3

Total Cost: $0.68
```

---

#### `--task-info TASK_ID`
**Type:** String (task ID)
**Default:** None
**Description:** Display detailed information about a specific task.

**Example:**
```bash
nelson-prd --task-info PRD-003 requirements.md
```

**Output:**
```
Task: PRD-003
Description: Add payment integration
Status: blocked
Priority: high
Branch: feature/PRD-003-add-payment-integration

Blocking Reason: Waiting for Stripe API keys
Blocked At: 2026-01-13T15:30:22Z

Resume Context: (none)

Started At: 2026-01-13T14:00:00Z
Updated At: 2026-01-13T15:30:22Z
Completed At: (not completed)

Cost: $0.12
Iterations: 2
Phase: 2 (IMPLEMENT)

Nelson Run ID: nelson-20260113-140000
```

---

### Blocking & Resume

#### `--block TASK_ID --reason REASON`
**Type:** String (task ID) + String (reason)
**Required:** Both arguments required together
**Description:** Mark a task as blocked with a descriptive reason. Used when a task encounters external dependencies.

**Example:**
```bash
# Block task waiting for credentials
nelson-prd --block PRD-003 --reason "Waiting for Stripe API keys" requirements.md

# Block task pending approval
nelson-prd --block PRD-005 --reason "Pending security team approval" requirements.md

# Block task with service issue
nelson-prd --block PRD-007 --reason "Test environment down for maintenance" requirements.md
```

**Effect:**
- Task status changes to "blocked"
- PRD file updated: `[!] PRD-003 ... (blocked: reason)`
- Task state saved with blocking reason and timestamp
- Subsequent executions skip this task

---

#### `--unblock TASK_ID [--context CONTEXT]`
**Type:** String (task ID) + Optional String (context)
**Description:** Unblock a previously blocked task. Optionally provide resume context describing what changed.

**Example:**
```bash
# Unblock without context
nelson-prd --unblock PRD-003 requirements.md

# Unblock with helpful context
nelson-prd --unblock PRD-003 \
  --context "Stripe keys added to .env as STRIPE_SECRET_KEY. Use test mode for development." \
  requirements.md
```

**Effect:**
- Task status changes from "blocked" to "pending"
- Resume context stored in task state
- PRD file updated: `[ ] PRD-003 ...`
- Task ready for execution

---

#### `--resume-task TASK_ID`
**Type:** String (task ID)
**Description:** Resume a specific task (typically after unblocking). Switches to task branch and executes Nelson with stored resume context prepended to prompt.

**Example:**
```bash
nelson-prd --resume-task PRD-003 requirements.md
```

**Effect:**
- Git switches to task branch (e.g., `feature/PRD-003-...`)
- Nelson invoked with resume context prepended to prompt
- Task continues from where it left off
- Cost and iteration tracking continues

**When to Use:**
- After unblocking a task with `--unblock`
- To retry a specific task after fixing issues
- To continue a task that was interrupted

---

#### `--resume`
**Type:** Flag
**Default:** False
**Description:** Resume execution from the last incomplete task. Useful for continuing after interruption or failure.

**Example:**
```bash
nelson-prd --resume requirements.md
```

**Behavior:**
- Finds first pending or in-progress task
- Continues execution from that point
- Skips completed and blocked tasks
- Respects priority ordering

---

### Advanced Options

#### `--prd-dir DIRECTORY`
**Type:** Path
**Default:** `.nelson/prd`
**Description:** Custom directory for PRD state storage. Useful for isolating state or testing.

**Example:**
```bash
# Use custom state directory
nelson-prd --prd-dir /tmp/prd-test requirements.md

# Multiple isolated PRD executions
nelson-prd --prd-dir .nelson/prd-feature-a feature-a.md
nelson-prd --prd-dir .nelson/prd-feature-b feature-b.md
```

---

### Help & Version

#### `--help`
**Type:** Flag
**Description:** Display help message with all available options.

**Example:**
```bash
nelson-prd --help
```

---

## Environment Variables

`nelson-prd` respects all Nelson environment variables, which are passed to each task execution:

| Variable | Description | Default |
|----------|-------------|---------|
| `NELSON_MAX_ITERATIONS` | Max cycles per task | 10 |
| `NELSON_COST_LIMIT` | Max cost in USD per task | 10.00 |
| `NELSON_MODEL` | AI model for all phases | sonnet |
| `NELSON_PLAN_MODEL` | Model for Phase 1 | NELSON_MODEL |
| `NELSON_REVIEW_MODEL` | Model for Phase 3 & 5 | NELSON_MODEL |
| `NELSON_CLAUDE_COMMAND` | Claude command | claude-jail |
| `NELSON_AUTO_APPROVE_PUSH` | Skip push approval | false |

**Example:**
```bash
# Set environment for all PRD tasks
export NELSON_MAX_ITERATIONS=15
export NELSON_AUTO_APPROVE_PUSH=true
export NELSON_MODEL=opus

nelson-prd requirements.md  # Uses these settings
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - all tasks completed or properly blocked |
| 1 | Error - invalid arguments, file not found, validation error, or execution failure |
| 130 | Interrupted - user cancelled with Ctrl+C |

## PRD File Format

Tasks must follow this format:

```markdown
## High Priority
- [ ] PRD-001 Task description here
- [ ] PRD-002 Another task description

## Medium Priority
- [ ] PRD-003 Medium priority task

## Low Priority
- [ ] PRD-004 Low priority task
```

**Requirements:**
- Each task must have unique ID: `PRD-NNN` (3 digits)
- Status indicator: `[ ]` (pending), `[~]` (in progress), `[x]` (completed), `[!]` (blocked)
- Tasks organized under priority headers: "High Priority", "Medium Priority", "Low Priority"
- Task description follows the ID

**Status Transitions:**
```
[ ] pending → [~] in_progress → [x] completed
                    ↓
                   [!] blocked → [ ] pending (after unblock)
```

## Common Workflows

### Basic Execution
```bash
# Execute all pending tasks
nelson-prd requirements.md

# Check what would run
nelson-prd --dry-run requirements.md

# Check current status
nelson-prd --status requirements.md
```

### Blocking Workflow
```bash
# 1. Start execution
nelson-prd requirements.md

# 2. Task hits blocker, interrupt with Ctrl+C
# 3. Block the task
nelson-prd --block PRD-003 --reason "Waiting for API keys" requirements.md

# 4. Continue with other tasks
nelson-prd requirements.md

# 5. When blocker resolved
nelson-prd --unblock PRD-003 --context "Keys added to .env" requirements.md

# 6. Resume blocked task
nelson-prd --resume-task PRD-003 requirements.md
```

### Using Custom Models
```bash
# Use opus for important tasks
nelson-prd --nelson-args "--model opus" critical-features.md

# Use haiku for simple tasks (faster/cheaper)
nelson-prd --nelson-args "--model haiku" simple-fixes.md

# Mixed: opus for planning, sonnet for implementation
nelson-prd --nelson-args "--plan-model opus --model sonnet" requirements.md
```

### Monitoring Progress
```bash
# Quick status check
nelson-prd --status requirements.md

# Detailed task info
nelson-prd --task-info PRD-001 requirements.md

# Watch progress (run periodically)
watch -n 30 "nelson-prd --status requirements.md"
```

## Tips & Best Practices

1. **Use `--dry-run` first** to preview execution order
2. **Check `--status` frequently** to monitor progress
3. **Block early** when you know dependencies are missing
4. **Provide detailed context** when unblocking tasks
5. **Use `--nelson-args`** to customize behavior per PRD
6. **Set environment variables** for consistent defaults
7. **Review task info** after failures to understand what happened
8. **Keep PRD file in version control** to track project progress

## See Also

- [nelson(1)](nelson-cli.md) - Single-task autonomous development tool
- [examples/sample-prd.md](../examples/sample-prd.md) - Example PRD file
- [examples/blocking-workflow.md](../examples/blocking-workflow.md) - Blocking workflow guide
- [README.md](../README.md#multi-task-orchestration-with-nelson-prd) - Overview and quick start
