# Future Features

This document tracks features planned for future implementation in Nelson.

> **Note**: PRD orchestration (`nelson-prd`) has been fully implemented! See the [README](README.md) for documentation on using `nelson-prd` for multi-task orchestration.

## Planned Enhancements

### Additional AI Provider Support

**Status**: Planned

Support for additional AI providers beyond Anthropic Claude:
- OpenAI GPT-4/GPT-4 Turbo
- Google Gemini
- Local models via LLM APIs
- Provider-specific configuration and cost tracking

### Enhanced Cost Tracking & Reporting

**Status**: Planned

Richer cost analytics and reporting:
- Cost breakdown by phase
- Cost trends over time
- Budget alerts and limits
- Cost estimation before execution
- Export reports (CSV, JSON)

### Parallel Task Execution

**Status**: Planned

Run independent PRD tasks concurrently:
- Analyze task dependencies automatically
- Execute independent tasks in parallel
- Configurable max concurrent tasks
- Resource management for parallel execution

### Task Dependency Graphs (DAG)

**Status**: Planned

Explicit task dependency support:
```markdown
## High Priority
- [ ] PRD-001 Setup database schema
- [ ] PRD-002 Create API endpoints (depends: PRD-001)
- [ ] PRD-003 Build frontend (depends: PRD-002)
```

Features:
- DAG-based execution order
- Automatic dependency validation
- Visualization of task dependencies
- Smart parallelization based on dependencies

### Additional PRD Features

**Blocking/Unblocking**: ✅ Implemented
**Resume with Context**: ✅ Implemented
**State Persistence**: ✅ Implemented
**Priority-Based Execution**: ✅ Implemented
**Branch Management**: ✅ Implemented

**Future additions**:
- Task templates and reusable definitions
- Multiple PRD formats (YAML, JSON, TOML)
- Task validation and pre-flight checks
- Rollback support on task failure
- Progress webhooks for external integrations
- Sub-tasks and hierarchical task structures

### Workflow Enhancements

- Configurable phase order (skip/reorder phases)
- Custom phase definitions
- Phase-level plugins and hooks
- Distributed workflow execution
- Workflow templates for common patterns

### Development Tools

- Nelson CLI plugin system
- Custom status parsers
- Workflow debugging tools
- Performance profiling and metrics
- Integration with CI/CD platforms

## Contributing Ideas

Have an idea for a future feature? Open an issue on GitHub with the "enhancement" label!
