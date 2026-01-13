# Future Features

This document tracks features planned for future implementation in Nelson.

## PRD Orchestration (nelson-prd)

**Status**: Planned for future implementation
**Related Bash Script**: `~/code/sontek/homies/bin/ralph-prd`

### Overview

PRD orchestration is a companion feature that executes multiple Nelson workflows, one per task in a Product Requirements Document (PRD). This allows orchestrating complex, multi-task projects where each task goes through Nelson's full 6-phase workflow autonomously.

### How It Works

1. **PRD Format**: Tasks organized by priority in markdown format:
   ```markdown
   ## High Priority
   - [ ] Add user authentication system
   - [ ] Create user profile management

   ## Medium Priority
   - [ ] Add email notification system

   ## Low Priority
   - [ ] Dark mode toggle
   ```

2. **Execution Flow**:
   - Reads PRD file and extracts unchecked tasks
   - Executes tasks by priority: High → Medium → Low
   - Each task runs through full Nelson workflow (Phases 1-6)
   - Marks tasks complete `[x]` as they finish
   - Tracks progress in `.nelson/prd-status.json`

3. **Resume Support**:
   - Can resume from last incomplete task
   - Maintains state between sessions
   - Handles failures gracefully

4. **Progress Tracking**:
   - Shows overall completion status
   - Tracks tasks by priority level
   - Displays time elapsed
   - Maintains backup of PRD file

### Key Features

- **Priority-Based Execution**: High priority tasks execute first
- **Task Isolation**: Each task gets its own Nelson run with independent state
- **Failure Recovery**: Stops on failure, can resume with `--resume`
- **Dry Run Mode**: Preview tasks without execution
- **Status Reporting**: Check current progress with `--status`
- **Environment Inheritance**: Passes Nelson configuration to each task

### CLI Design (Proposed)

```bash
# Execute PRD
nelson-prd PRD.md

# Resume from last failure
nelson-prd --resume PRD.md

# Preview tasks
nelson-prd --dry-run PRD.md

# Check status
nelson-prd --status PRD.md

# Configure per-task behavior
NELSON_MAX_ITERATIONS=75 nelson-prd PRD.md
NELSON_AUTO_APPROVE_PUSH=true nelson-prd PRD.md
```

### Implementation Considerations

#### Architecture Decision: Separate CLI vs Subcommand

**Option 1: Separate CLI Tool (`nelson-prd`)**
- Pros:
  - Clear separation of concerns
  - Independent evolution of PRD features
  - Can be optional dependency
  - Follows bash script pattern
- Cons:
  - Additional entry point to maintain
  - Slight increase in installation complexity

**Option 2: Subcommand (`nelson prd`)**
- Pros:
  - Unified CLI experience
  - Single installation point
  - Easier discovery
- Cons:
  - Couples PRD logic to main CLI
  - May bloat main CLI if PRD grows complex

**Recommendation**: Start with separate CLI tool (`nelson-prd`) following the bash pattern. This provides:
- Clear boundaries between core workflow and PRD orchestration
- Ability to evolve PRD features independently
- Option to merge into main CLI later if desired

#### Core Components Needed

1. **PRD Parser** (`prd_parser.py`):
   - Parse markdown PRD files
   - Extract tasks by section
   - Handle priority levels
   - Update task status ([ ] → [x])

2. **PRD State Manager** (`prd_state.py`):
   - Track current task execution
   - Maintain `.nelson/prd-status.json`
   - Handle resume logic
   - Record task history

3. **PRD Orchestrator** (`prd_orchestrator.py`):
   - Main execution loop
   - Invoke Nelson CLI for each task
   - Handle task completion/failure
   - Coordinate progress tracking

4. **PRD CLI** (`nelson-prd`):
   - Click-based interface
   - Options: --resume, --dry-run, --status
   - Environment variable support
   - Rich output formatting

#### Testing Strategy

- **Unit Tests**:
  - PRD parser: section extraction, task parsing, status updates
  - State manager: status persistence, resume logic
  - Task prioritization logic

- **Integration Tests**:
  - End-to-end PRD execution with mock Nelson
  - Resume from failure scenarios
  - Multi-task workflow completion

- **Fixtures**:
  - Sample PRD files with various structures
  - Mock Nelson CLI responses

#### Key Differences from Bash Implementation

1. **Better Format Support**: Could support multiple PRD formats (markdown, YAML, JSON)
2. **Enhanced State**: Richer state tracking with timing, logs per task
3. **Improved Error Handling**: Structured error reporting and recovery suggestions
4. **Task Dependencies**: Potential for future task dependency support
5. **Parallel Execution**: Option to run independent tasks in parallel

#### Migration Path

When implementing, we can:
1. Start with markdown format matching bash script exactly
2. Add JSON state file for better resume support
3. Consider richer formats (task dependencies, metadata) later
4. Maintain compatibility with bash-created PRD files

### Usage Examples

```bash
# Basic execution
nelson-prd requirements.md

# High iteration limit per task
NELSON_MAX_ITERATIONS=100 nelson-prd requirements.md

# Use specific Claude model for planning
NELSON_PLAN_MODEL=claude-opus-4-20250514 nelson-prd requirements.md

# Auto-approve all pushes
NELSON_AUTO_APPROVE_PUSH=true nelson-prd requirements.md

# Resume after fixing an issue
nelson-prd --resume requirements.md

# Check current progress
nelson-prd --status requirements.md
```

### Open Questions

1. Should PRD tasks support templating/variables?
2. Should we support task dependencies (e.g., "Task B depends on Task A")?
3. Should we allow custom priorities beyond High/Medium/Low?
4. Should PRD support sub-tasks or just flat lists?
5. Should we support rollback if a task fails?

### Future Enhancements

- **Task Dependencies**: DAG-based execution order
- **Parallel Execution**: Run independent tasks concurrently
- **Task Templates**: Reusable task definitions
- **Cost Estimation**: Predict costs before execution
- **Progress Webhooks**: Notify external systems of progress
- **Multiple PRD Formats**: YAML, JSON, TOML support
- **Task Validation**: Pre-flight checks before execution
- **Rollback Support**: Undo task changes on failure

### References

- Bash implementation: `~/code/sontek/homies/bin/ralph-prd`
- PRD format based on GitHub-style task lists
- State management follows Nelson core patterns
