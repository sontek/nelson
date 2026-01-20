# Nelson

AI orchestration CLI for autonomous development workflows. Nelson provides a structured 6-phase approach to autonomous AI-driven development, coordinating Claude Code to plan, implement, review, test, and commit changes iteratively.

## Overview

Nelson implements the "Nelson Loop" pattern where an AI agent works autonomously through multiple cycles of development:

1. **PLAN**: Analyze the task and create implementation plan
2. **IMPLEMENT**: Execute tasks one at a time, committing each
3. **REVIEW**: Review changes for quality and correctness
4. **TEST**: Run tests, linters, and type checkers
5. **FINAL-REVIEW**: Final verification before completion
6. **COMMIT**: Commit any remaining changes

After completing all 6 phases (one complete cycle), Nelson loops back to Phase 1 to check if there's more work to do. This continues until the AI determines all work is complete or the maximum cycle limit is reached.

## Features

- **Autonomous Multi-Cycle Execution**: Runs multiple complete cycles until work is done
- **Structured Phase System**: 6 distinct phases with clear responsibilities
- **Circuit Breaker Protection**: Detects stagnation, repeated errors, and stalled processes
- **Progress Monitoring**: Real-time file activity and heartbeat during long-running phases
- **Stall Detection**: Automatic detection and recovery from hung Claude processes
- **Resume Support**: Resume from any previous run
- **Cost & Iteration Limits**: Configurable safety limits
- **Model Selection**: Choose different models per phase (opus/sonnet/haiku)
- **Jail Mode Support**: Docker sandbox via claude-jail
- **Rich Terminal Output**: Colored, formatted logs

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

## Quick Start

### Single Task with Nelson

```bash
# Basic usage
nelson "Add user authentication"

# From a file
nelson docs/implementation.md

# From stdin
echo "implement feature X" | nelson

# Resume from last run
nelson --resume

# Resume from specific run
nelson --resume .nelson/runs/nelson-20260112-120125
```

### Multi-Task with nelson-prd

For projects with multiple tasks, use `nelson-prd` to orchestrate:

```bash
# Create a PRD file (requirements.md)
cat > requirements.md << 'EOF'
## High Priority
- [ ] PRD-001 Implement user authentication
- [ ] PRD-002 Add user profile management
- [ ] PRD-003 Create password reset flow

## Medium Priority
- [ ] PRD-004 Add email notifications
- [ ] PRD-005 Implement search functionality
EOF

# Execute all tasks automatically
nelson-prd requirements.md

# Check progress
nelson-prd --status requirements.md

# Block a task if you hit dependencies
nelson-prd --block PRD-003 --reason "Waiting for email service credentials" requirements.md

# Resume when ready
nelson-prd --unblock PRD-003 --context "Credentials added to .env" requirements.md
nelson-prd --resume-task PRD-003 requirements.md
```

See the [Multi-Task Orchestration](#multi-task-orchestration-with-nelson-prd) section for full details.

## Configuration

Nelson can be configured via CLI flags or environment variables:

### CLI Flags

```bash
nelson --max-iterations 20 "complex task"
nelson --model opus "use opus for everything"
nelson --plan-model opus --model sonnet "opus for planning, sonnet for implementation"
nelson --claude-command claude "use native claude instead of docker"
nelson --auto-approve-push "skip push approval prompts"
```

### Environment Variables

```bash
# Set in your shell profile or .envrc
export NELSON_MAX_ITERATIONS=10            # Max complete cycles (default: 10)
export NELSON_COST_LIMIT=10.00             # Max cost in USD (default: 10.00)
export NELSON_MODEL=sonnet                 # Model for all phases (default: sonnet)
export NELSON_PLAN_MODEL=opus              # Model for Phase 1 (default: NELSON_MODEL)
export NELSON_REVIEW_MODEL=sonnet          # Model for Phase 3 & 5 (default: NELSON_MODEL)
export NELSON_CLAUDE_COMMAND=claude        # Claude command (default: claude-jail)
export NELSON_AUTO_APPROVE_PUSH=false      # Skip push approval (default: false)
export NELSON_STALL_TIMEOUT_MINUTES=15     # Minutes before killing stalled process (default: 15)
```

## How It Works

### The Nelson Loop

1. **Start**: User provides a task/prompt
2. **Phase 1 (PLAN)**: Claude analyzes and creates a plan
3. **Phases 2-6**: Execute plan through implementation, review, testing, and commit
4. **Loop Back**: After Phase 6, archive plan and return to Phase 1
5. **Continue**: Phase 1 checks for more work - if found, create new plan
6. **Stop**: When Phase 1 finds no more work OR max cycles reached

### Iteration vs Cycle

- **Cycle**: One complete pass through all 6 phases
- **Iteration**: A single AI invocation (can be multiple per cycle)
- `max_iterations=10` means up to 10 complete cycles, not 10 AI calls

Example: With `max_iterations=3`:
- Cycle 1: Phase 1 → Phase 6 (may take 15 iterations)
- Cycle 2: Phase 1 → Phase 6 (may take 12 iterations)
- Cycle 3: Phase 1 → Phase 6 (may take 10 iterations)
- Total: 3 complete cycles, 37 total iterations

### Circuit Breakers

Nelson automatically detects problematic patterns:

- **Stagnation**: 3+ iterations with no progress
- **Test-Only Loops**: 3+ iterations of testing without changes
- **Repeated Errors**: Same error pattern 3+ times
- **Stalled Process**: No file activity for 15+ minutes (configurable via `NELSON_STALL_TIMEOUT_MINUTES`)

When triggered, the workflow stops gracefully for human intervention. For stalled processes, Nelson automatically kills the hung Claude process and retries.

### EXIT_SIGNAL Behavior

The EXIT_SIGNAL in Claude's status block has different meanings by phase:

- **Phase 1**: "No more work found" → Stop workflow ✓
- **Phases 2-6**: "This cycle complete" → Loop to Phase 1 ↻

This enables the autonomous loop while allowing clean termination.

## Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/nelson --cov-report=term-missing

# Run specific test file
pytest tests/test_workflow.py -v

# Run specific test
pytest tests/test_workflow.py::TestWorkflowRun::test_run_with_exit_signal -v
```

### Code Quality

```bash
# Format code
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/nelson --strict

# Run all checks
ruff check src/ tests/ && mypy src/nelson --strict && pytest
```

### Development Setup

```bash
# Clone repository
git clone <repo>
cd nelson

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # Unix
# or
.venv\Scripts\activate     # Windows

# Install in development mode
uv pip install -e ".[dev]"

# Run tests
pytest
```

## Architecture

### Key Design Principles

1. **Stateless Phases**: Each phase execution rebuilds context from disk
2. **Atomic Commits**: Each implementation task gets its own commit
3. **Circuit Breakers**: Automatic detection of problematic patterns
4. **Resumability**: Can resume from any previous run
5. **Provider Abstraction**: Easy to add new AI providers beyond Claude

### State Management

Nelson maintains state in `.nelson/` directory:
- `runs/nelson-YYYYMMDD-HHMMSS/`: Per-run directory
  - `plan.md`: Current plan
  - `decisions.md`: Decision log
  - `state.json`: Execution state
  - `last_output.txt`: Latest AI response

### Plan File Format

```markdown
## Phase 1: PLAN
- [x] Analyze requirements
- [x] Review existing code

## Phase 2: IMPLEMENT
- [ ] Add User model
- [ ] Create authentication endpoint
- [ ] Add JWT token handling

## Phase 3: REVIEW
- [ ] Review all Phase 2 changes

## Phase 4: TEST
- [ ] Run tests and linters

## Phase 5: FINAL-REVIEW
- [ ] Final verification

## Phase 6: COMMIT
- [ ] Commit any remaining changes
```

## Multi-Task Orchestration with nelson-prd

`nelson-prd` is a companion CLI tool that orchestrates multiple Nelson workflows from a Product Requirements Document (PRD). This enables autonomous execution of multi-task projects with state tracking, blocking support, and resume capabilities.

### Why nelson-prd?

While Nelson handles single tasks autonomously, real projects often require completing multiple related tasks. `nelson-prd`:

- **Orchestrates Multiple Tasks**: Execute dozens of tasks automatically
- **Priority-Based Execution**: Tasks run in order: High → Medium → Low
- **Branch Management**: Auto-creates git branches per task (e.g., `feature/PRD-001-task-name`)
- **Blocking Support**: Pause tasks waiting on external dependencies
- **Resume Capability**: Continue blocked tasks with context preservation
- **Cost & Progress Tracking**: Per-task and aggregate metrics
- **State Persistence**: Recovers from interruptions seamlessly

### Quick Start

Create a PRD markdown file with explicit task IDs:

```markdown
# My Project PRD

## High Priority
- [ ] PRD-001 Implement user authentication system
- [ ] PRD-002 Create user profile management
- [ ] PRD-003 Add payment integration

## Medium Priority
- [ ] PRD-004 Add email notifications
- [ ] PRD-005 Implement search functionality

## Low Priority
- [ ] PRD-006 Add dark mode toggle
```

Execute all tasks:

```bash
# Run all pending tasks
nelson-prd requirements.md

# Check status
nelson-prd --status requirements.md

# Preview without execution
nelson-prd --dry-run requirements.md
```

### Blocking & Resume Workflow

When a task hits an external dependency:

```bash
# Block the task
nelson-prd --block PRD-003 --reason "Waiting for Stripe API keys" requirements.md

# Continue with other tasks (PRD-003 is skipped)
nelson-prd requirements.md

# Later, when dependency is resolved
nelson-prd --unblock PRD-003 --context "API keys added to .env as STRIPE_SECRET_KEY" requirements.md

# Resume the blocked task with context
nelson-prd --resume-task PRD-003 requirements.md
```

The resume context is prepended to Nelson's prompt, helping it understand what changed since the task was blocked.

### Task Status Indicators

- `[ ]` - Pending (not started)
- `[~]` - In Progress (currently executing)
- `[x]` - Completed (successfully finished)
- `[!]` - Blocked (waiting on external dependency)

### Features

- **Explicit Task IDs**: Required format `PRD-NNN` for stable references
- **Priority Ordering**: High priority tasks execute before medium/low
- **Automatic Branching**: Each task gets `feature/PRD-NNN-description` branch
- **State Management**: Stores state in `.nelson/prd/` directory
- **Cost Tracking**: Accumulates and displays per-task costs
- **Iteration Tracking**: Monitors how many cycles each task requires
- **Resume Context**: Free-form text to help Nelson resume blocked tasks

### Configuration

Pass additional Nelson options:

```bash
# Use opus for all PRD tasks
nelson-prd --nelson-args "--model opus" requirements.md

# Increase iteration limit per task
nelson-prd --nelson-args "--max-iterations 20" requirements.md

# Multiple arguments
nelson-prd --nelson-args "--model opus --max-iterations 20" requirements.md
```

Environment variables are automatically inherited:

```bash
export NELSON_MAX_ITERATIONS=15
export NELSON_AUTO_APPROVE_PUSH=true
nelson-prd requirements.md  # Uses these settings
```

### Examples

See the `examples/` directory for comprehensive guides:

- **[sample-prd.md](examples/sample-prd.md)**: Example PRD with 13 tasks showing format and all CLI commands
- **[blocking-workflow.md](examples/blocking-workflow.md)**: Step-by-step guide for handling blocked tasks

### Advanced Usage

```bash
# Get detailed task information
nelson-prd --task-info PRD-001 requirements.md

# Resume from last incomplete task
nelson-prd --resume requirements.md

# Use custom PRD directory
nelson-prd --prd-dir /path/to/state requirements.md
```

### Directory Structure

```
.nelson/
  prd/
    prd-state.json           # Overall PRD state
    backups/                 # PRD file backups (last 10)
    PRD-001/
      state.json             # Task-specific state
    PRD-002/
      state.json
    ...
```

### Best Practices

1. **Use Descriptive Task IDs**: Start at PRD-001 and increment sequentially
2. **Write Clear Task Descriptions**: The description becomes the branch name and Nelson's prompt
3. **Block Early**: Don't waste cycles if you know a dependency is missing
4. **Provide Rich Context**: When unblocking, explain what changed in detail
5. **Check Status Frequently**: Use `--status` to monitor progress
6. **Organize by Priority**: Put urgent/foundational tasks in High priority

### Troubleshooting

**Q: What if I forget a task ID?**
A: The parser validates all tasks and will error with helpful messages showing which tasks are missing IDs.

**Q: Can I reorder tasks?**
A: Yes! Task IDs are stable, so reordering in the markdown doesn't break anything.

**Q: What if a task fails?**
A: Use `--stop-on-failure=false` to continue with remaining tasks, or fix the issue and resume.

**Q: How do I see what work was done?**
A: Each task links to its Nelson run directory with full logs and decision history.

## Future Features

See [FUTURE_FEATURES.md](FUTURE_FEATURES.md) for planned enhancements:

- Additional AI provider support (OpenAI, Google Gemini, local models)
- Enhanced cost tracking and reporting
- Parallel task execution (currently sequential by priority)
- Task dependency graphs (DAG-based execution)

## License

Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Credits

Inspired by the "Ralph Wiggum" autonomous development pattern by Geoffrey Huntley.
Python implementation by John Anderson (sontek).
