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
- **Circuit Breaker Protection**: Detects stagnation and repeated errors
- **Resume Support**: Resume from any previous run
- **Cost & Iteration Limits**: Configurable safety limits
- **Model Selection**: Choose different models per phase (opus/sonnet/haiku)
- **Jail Mode Support**: Docker sandbox via claude-jail
- **Rich Terminal Output**: Colored, formatted logs
- **Comprehensive Testing**: 421 tests with 91% coverage

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
export NELSON_MAX_ITERATIONS=10        # Max complete cycles (default: 10)
export NELSON_COST_LIMIT=10.00         # Max cost in USD (default: 10.00)
export NELSON_MODEL=sonnet             # Model for all phases (default: sonnet)
export NELSON_PLAN_MODEL=opus          # Model for Phase 1 (default: NELSON_MODEL)
export NELSON_REVIEW_MODEL=sonnet      # Model for Phase 3 & 5 (default: NELSON_MODEL)
export NELSON_CLAUDE_COMMAND=claude    # Claude command (default: claude-jail)
export NELSON_AUTO_APPROVE_PUSH=false  # Skip push approval (default: false)
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

When triggered, the workflow stops gracefully for human intervention.

### EXIT_SIGNAL Behavior

The EXIT_SIGNAL in Claude's status block has different meanings by phase:

- **Phase 1**: "No more work found" → Stop workflow ✓
- **Phases 2-6**: "This cycle complete" → Loop to Phase 1 ↻

This enables the autonomous loop while allowing clean termination.

## Project Structure

```
nelson/
├── src/nelson/
│   ├── cli.py              # Click-based CLI
│   ├── workflow.py         # Main orchestration loop
│   ├── state.py            # State management
│   ├── config.py           # Configuration
│   ├── phases.py           # Phase definitions
│   ├── prompts.py          # Prompt generation
│   ├── transitions.py      # Phase transition logic
│   ├── circuit_breaker.py  # Stagnation detection
│   ├── status_parser.py    # Status block parsing
│   ├── plan_parser.py      # Plan file parsing
│   ├── providers/
│   │   ├── base.py         # Provider interface
│   │   └── claude.py       # Claude implementation
│   └── ...
├── tests/                  # Comprehensive test suite (421 tests)
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

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

## Comparison to Bash Implementation

Nelson is a Python reimplementation of the original bash script (`ralph`) with these improvements:

- **Better Testing**: 421 comprehensive tests vs minimal bash testing
- **Type Safety**: Full mypy strict mode compliance
- **Modularity**: Clean separation of concerns
- **Extensibility**: Provider abstraction for multiple AI backends
- **Maintainability**: Object-oriented design, 91% test coverage
- **Developer Experience**: Rich terminal output, better error messages

Core behavior remains identical to the battle-tested bash implementation.

## Future Features

See [FUTURE_FEATURES.md](FUTURE_FEATURES.md) for planned enhancements:

- PRD orchestration (nelson-prd) for multi-task projects
- Support for additional AI providers (OpenAI, etc.)
- Enhanced cost tracking and reporting
- Parallel task execution

## License

MIT License - see LICENSE file for details.

## Credits

Inspired by the "Ralph Wiggum" autonomous development pattern by Geoffrey Huntley.
Python implementation by John Anderson (sontek).
