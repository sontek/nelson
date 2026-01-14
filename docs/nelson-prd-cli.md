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

## Troubleshooting

### Task ID Format Errors

**Problem:** Error message like `"Invalid task ID format: found 'PRD-1', expected 'PRD-NNN'"`

**Cause:** Task IDs must have exactly 3 digits (PRD-001 to PRD-999)

**Solution:**
```bash
# ❌ Wrong
- [ ] PRD-1 Add authentication
- [ ] PRD-12 Create profile
- [ ] PRD-1234 Add payment

# ✅ Correct
- [ ] PRD-001 Add authentication
- [ ] PRD-012 Create profile
- [ ] PRD-123 Add payment
```

---

### Duplicate Task ID Error

**Problem:** Error message like `"Duplicate task IDs found: PRD-001 appears 2 times"`

**Cause:** Multiple tasks have the same ID in the PRD file

**Solution:**
1. Search for the duplicate ID: `grep "PRD-001" requirements.md`
2. Assign unique IDs to each task
3. Check line numbers in error message for locations

---

### Task Outside Priority Section

**Problem:** Error message like `"Task 'PRD-001 ...' has no priority context"`

**Cause:** Task appears before any priority header or in unrecognized section

**Solution:**
```bash
# ❌ Wrong - task before priority section
- [ ] PRD-001 Add authentication

## High Priority
- [ ] PRD-002 Create profile

# ✅ Correct - all tasks under priority sections
## High Priority
- [ ] PRD-001 Add authentication
- [ ] PRD-002 Create profile
```

---

### Branch Already Exists Error

**Problem:** Git error when trying to create branch `feature/PRD-001-...`

**Cause:** Branch already exists from previous run

**Solutions:**
1. **Delete the branch:**
   ```bash
   git branch -D feature/PRD-001-add-authentication
   nelson-prd requirements.md
   ```

2. **Switch to existing branch:**
   ```bash
   git checkout feature/PRD-001-add-authentication
   nelson-prd --resume-task PRD-001 requirements.md
   ```

3. **Clean up all PRD branches:**
   ```bash
   git branch | grep "feature/PRD-" | xargs git branch -D
   nelson-prd requirements.md
   ```

---

### Uncommitted Changes Error

**Problem:** Git refuses to switch branches due to uncommitted changes

**Cause:** Current branch has uncommitted changes that would be overwritten

**Solutions:**
1. **Commit changes:**
   ```bash
   git add .
   git commit -m "WIP: Current progress"
   nelson-prd requirements.md
   ```

2. **Stash changes:**
   ```bash
   git stash
   nelson-prd requirements.md
   git stash pop  # Later when you return
   ```

3. **Use --nelson-args to stay on current branch (not recommended):**
   ```bash
   # This bypasses branch switching - use cautiously
   nelson-prd --resume-task PRD-001 requirements.md
   ```

---

### State File Corruption

**Problem:** Error message like `"Failed to load PRD state: JSONDecodeError"`

**Cause:** State file corrupted (crash during write, disk full, manual edit)

**Solution:**
```bash
# 1. Backup corrupted state
cp .nelson/prd/prd-state.json .nelson/prd/prd-state.json.corrupted

# 2. Remove corrupted file
rm .nelson/prd/prd-state.json

# 3. Re-run (will recreate state from PRD file)
nelson-prd requirements.md
```

**For task-specific state corruption:**
```bash
# Remove corrupted task state
rm .nelson/prd/PRD-001/state.json

# Task will restart from beginning
nelson-prd --resume-task PRD-001 requirements.md
```

---

### Task Stuck in "In Progress"

**Problem:** Task shows `[~]` but isn't running, or status shows "in_progress" forever

**Cause:** Previous execution was interrupted (Ctrl+C, crash, kill signal)

**Solutions:**
1. **Block and resume:**
   ```bash
   # Block with reason
   nelson-prd --block PRD-003 --reason "Interrupted, resuming" requirements.md

   # Unblock and resume
   nelson-prd --unblock PRD-003 requirements.md
   nelson-prd --resume-task PRD-003 requirements.md
   ```

2. **Manual state fix:**
   ```bash
   # Edit task state to mark as pending
   # Change status from "in_progress" to "pending" in:
   vim .nelson/prd/PRD-003/state.json

   # Then resume
   nelson-prd requirements.md
   ```

---

### Cost Tracking Shows $0.00

**Problem:** Task completes but `--status` shows $0.00 cost

**Cause:** Nelson's state.json file not found or cost field missing

**Solutions:**
1. **Check Nelson state file exists:**
   ```bash
   ls -la .nelson/runs/*/state.json
   cat .nelson/runs/nelson-*/state.json | grep cost_usd
   ```

2. **Verify Nelson version:**
   ```bash
   nelson --version  # Should be >= 1.0.0
   ```

3. **Check --nelson-args syntax:**
   ```bash
   # ❌ Wrong - might break state tracking
   nelson-prd --nelson-args "--some-invalid-flag" requirements.md

   # ✅ Correct - valid Nelson arguments
   nelson-prd --nelson-args "--model opus" requirements.md
   ```

---

### Tasks Execute Out of Order

**Problem:** Medium priority tasks run before High priority tasks

**Cause:** Tasks don't have valid priority section headers

**Solution:**
```bash
# ❌ Wrong - typo in priority header
## High Prority
- [ ] PRD-001 Important task

## Medium Pririty
- [ ] PRD-002 Less important

# ✅ Correct - exact headers required
## High Priority
- [ ] PRD-001 Important task

## Medium Priority
- [ ] PRD-002 Less important
```

Valid headers (case-sensitive):
- `## High Priority`
- `## Medium Priority`
- `## Low Priority`

---

### Resume Context Not Working

**Problem:** Unblock with `--context` but Nelson doesn't see the context

**Cause:** Context not stored correctly or task not resumed properly

**Solution:**
```bash
# 1. Verify context was stored
nelson-prd --task-info PRD-003 requirements.md
# Look for "Resume Context:" section

# 2. Must use --resume-task to use context
nelson-prd --resume-task PRD-003 requirements.md  # ✅ Includes context

# ❌ Don't do this - won't use stored context
nelson-prd requirements.md  # Starts fresh without context
```

---

### PRD File Changes Not Detected

**Problem:** Modified task descriptions but status doesn't show warnings

**Cause:** Changes happened before task was started (no original_text stored)

**Expected Behavior:**
- Only tasks that have been started have original_text in task_mapping
- New tasks or pending tasks won't show change warnings
- Warnings only appear for tasks that have state (started, completed, blocked)

**Check Status:**
```bash
nelson-prd --status requirements.md
# Look for "⚠️ Task text changes detected" section
```

---

### Too Many Backup Files

**Problem:** `.nelson/backups/` directory has hundreds of backup files

**Cause:** Many PRD file updates (normal behavior)

**Solution:**
Backups are automatically cleaned up (max 10 per PRD file). Manual cleanup:
```bash
# Remove all backups older than 7 days
find .nelson/backups -name "*.backup-*" -mtime +7 -delete

# Remove all backups (will lose recovery ability)
rm -rf .nelson/backups/
```

---

### Nelson Command Not Found

**Problem:** Error message like `"nelson: command not found"` during task execution

**Cause:** Nelson not installed or not in PATH

**Solution:**
```bash
# 1. Verify Nelson installation
which nelson
nelson --version

# 2. If not installed, install Nelson
pip install nelson-cli  # Or appropriate installation method

# 3. If installed but not in PATH
export PATH="$HOME/.local/bin:$PATH"  # Add to ~/.bashrc or ~/.zshrc
```

---

### Permission Denied on State Files

**Problem:** Error message like `"Permission denied: '.nelson/prd/prd-state.json'"`

**Cause:** File ownership or permissions issue (possibly from sudo execution)

**Solution:**
```bash
# 1. Check current ownership
ls -la .nelson/prd/

# 2. Fix ownership (replace USERNAME with your username)
sudo chown -R USERNAME:USERNAME .nelson/

# 3. Fix permissions
chmod -R u+rw .nelson/prd/

# 4. Re-run
nelson-prd requirements.md
```

---

### Task Fails Immediately

**Problem:** Task shows as failed without making progress

**Possible Causes & Solutions:**

1. **Nelson configuration issue:**
   ```bash
   # Test Nelson directly
   echo "Add a simple function" | nelson
   ```

2. **Invalid --nelson-args:**
   ```bash
   # Check Nelson help for valid arguments
   nelson --help
   ```

3. **Git repository issues:**
   ```bash
   # Verify git repo is initialized
   git status

   # Initialize if needed
   git init
   git add .
   git commit -m "Initial commit"
   ```

4. **Check detailed error:**
   ```bash
   nelson-prd --task-info PRD-001 requirements.md
   # Look for error messages in output
   ```

---

## See Also

- [nelson(1)](nelson-cli.md) - Single-task autonomous development tool
- [examples/sample-prd.md](../examples/sample-prd.md) - Example PRD file
- [examples/blocking-workflow.md](../examples/blocking-workflow.md) - Blocking workflow guide
- [README.md](../README.md#multi-task-orchestration-with-nelson-prd) - Overview and quick start
