# Comprehensive Mode

Comprehensive mode is Nelson's most thorough workflow, designed for large features, architectural changes, and projects where documentation and long-term planning are priorities.

## Overview

Comprehensive mode adds two phases to the standard 6-phase workflow:

**Phase 0: DISCOVER** (before PLAN)
- Research and document the codebase before planning
- Map architecture, patterns, and integration points
- Find similar features and reusable components
- Document findings factually (no suggestions or critiques)

**Phase 7: ROADMAP** (after COMMIT)
- Document future improvements and technical debt
- List testing gaps and documentation needs
- Identify related work and follow-up tasks
- Create ROADMAP.md with structured action items

### Full Workflow

```
DISCOVER → PLAN → IMPLEMENT → REVIEW → TEST → FINAL_REVIEW → COMMIT → ROADMAP
   (0)      (1)       (2)        (3)     (4)        (5)        (6)      (7)
```

## When to Use Comprehensive Mode

Use `--comprehensive` for:

- **Large features**: Multi-file features that touch several systems
- **Architectural changes**: Refactoring, new patterns, infrastructure work
- **Team collaboration**: When others will build on your work
- **Complex integrations**: Third-party APIs, databases, external services
- **Long-term projects**: Work that will evolve over time

Don't use for:
- Simple bug fixes (use `--quick` instead)
- Typos or small tweaks (use `--quick`)
- One-off scripts or utilities (use standard mode)

## Usage

### Basic Usage

```bash
nelson --comprehensive "Implement user authentication with OAuth"
```

Or set via environment:

```bash
export NELSON_DEPTH=comprehensive
nelson "Implement user authentication with OAuth"
```

### What to Expect

#### Phase 0: DISCOVER

Claude will:
1. Explore your codebase structure
2. Identify architectural patterns
3. Search for similar implementations
4. Map integration points and dependencies
5. Note complexity observations

**Duration**: 1-2 iterations (2-5 minutes)

**Output**: Detailed research findings in `decisions.md`

Example findings:
```markdown
## [Iteration 1] Phase 0: DISCOVER - Codebase Research

### Codebase Structure
- Entry point: src/main.py:1 (CLI entry)
- Key modules: src/auth/ (authentication), src/api/ (endpoints)
- Build system: pyproject.toml uses poetry

### Architecture Patterns
- Pattern: Repository pattern in src/repos/ (src/repos/user.py:10)
- Conventions: snake_case for functions, PascalCase for classes

### Similar Features Found
- JWT validation in src/auth/jwt.py:25
- User sessions in src/auth/session.py:40

### Integration Points
- Database: PostgreSQL via SQLAlchemy in src/db/models.py
- Auth: JWT tokens validated in src/auth/middleware.py:30
```

#### Phase 7: ROADMAP

After all implementation and commits are complete, Claude will:
1. Document future improvements
2. List technical debt incurred
3. Identify testing gaps
4. Note documentation needs
5. Suggest related work

**Duration**: 1 iteration (1-2 minutes)

**Output**: `ROADMAP.md` file + summary in `decisions.md`

Example roadmap:
```markdown
## Roadmap for User Authentication

### Future Improvements
- [ ] Add OAuth provider support (Google, GitHub)
- [ ] Implement refresh token rotation
- [ ] Add session management UI
- [ ] Support multi-factor authentication

### Technical Debt
- [ ] Extract JWT logic to dedicated service
- [ ] Add rate limiting to login endpoint
- [ ] Centralize error messages

### Testing Gaps
- [ ] Test concurrent login attempts
- [ ] Test expired token handling
- [ ] Integration tests with real OAuth providers

### Documentation Needs
- [ ] Document OAuth configuration
- [ ] Add API authentication guide
- [ ] Create security best practices doc

### Related Work
- [ ] Implement password reset flow
- [ ] Add email verification
- [ ] Create user profile management
```

## Benefits

### Better Planning
DISCOVER phase ensures Claude understands your codebase before making decisions:
- Follows existing patterns instead of inventing new ones
- Reuses existing components instead of duplicating
- Matches your code style and conventions
- Avoids conflicts with existing implementations

### Long-term Value
ROADMAP phase captures insights while they're fresh:
- Documents shortcuts taken under time pressure
- Identifies follow-up work before context is lost
- Creates actionable backlog items
- Helps future contributors understand the code

### Team Communication
Both phases improve collaboration:
- DISCOVER findings serve as codebase documentation
- ROADMAP provides clear handoff for other team members
- Decisions are documented for future reference
- Technical debt is acknowledged and tracked

## Cost Considerations

Comprehensive mode uses approximately:
- **2-4 additional API calls** (1-2 for DISCOVER, 1-2 for ROADMAP)
- **~5-10 minutes extra time**
- **$0.01-0.05 additional cost** (depending on codebase size)

For most projects, the improved quality and documentation are worth the small additional cost.

## Configuration

Comprehensive mode respects all other flags:

```bash
# Comprehensive + interactive mode
nelson --comprehensive --interactive "Add new feature"

# Comprehensive + specific model
nelson --comprehensive --plan-model opus "Add new feature"

# Comprehensive with iteration limit
nelson --comprehensive --max-iterations 15 "Add new feature"
```

## Disabling DISCOVER or ROADMAP

If you want comprehensive research but not roadmap (or vice versa), you can:

```bash
# Set in environment
export NELSON_DEPTH=comprehensive

# Then manually adjust in workflow if needed
# (This is advanced usage - most users won't need this)
```

## Examples

### Example 1: Adding OAuth

```bash
nelson --comprehensive "Add GitHub OAuth authentication"
```

**DISCOVER phase** finds:
- Existing auth patterns in `src/auth/`
- JWT implementation to reuse
- Database models for users
- Middleware structure for route protection

**ROADMAP phase** documents:
- Adding Google/GitLab OAuth support
- Implementing account linking
- Adding OAuth token refresh
- Testing edge cases (revoked tokens, etc.)

### Example 2: Database Migration

```bash
nelson --comprehensive "Migrate from SQLite to PostgreSQL"
```

**DISCOVER phase** finds:
- All database queries and ORM usage
- Schema definitions and migrations
- Connection pooling setup
- Transaction handling patterns

**ROADMAP phase** documents:
- Performance tuning for Postgres
- Adding connection retry logic
- Implementing read replicas
- Monitoring query performance

### Example 3: API Redesign

```bash
nelson --comprehensive "Redesign REST API to use JSON:API spec"
```

**DISCOVER phase** finds:
- Current endpoint structure
- Response formatting patterns
- Error handling approach
- Versioning strategy

**ROADMAP phase** documents:
- Deprecating old API version
- Client migration guide
- Performance testing
- OpenAPI documentation

## Tips

1. **Use for unfamiliar codebases**: DISCOVER is most valuable when you're working with code you don't know well

2. **Save ROADMAP for later**: The roadmap items make great backlog entries for future sprints

3. **Review DISCOVER findings**: Check the research findings before PLAN phase starts to catch any misconceptions

4. **Share roadmap with team**: ROADMAP.md is great for sprint planning and backlog grooming

5. **Not for every task**: Reserve comprehensive mode for meaningful features - simple tasks don't need it

## Troubleshooting

**Q: DISCOVER phase is taking too long**
A: Large codebases may need 2-3 iterations. This is normal. Nelson is thoroughly exploring to make better decisions.

**Q: ROADMAP has too many items**
A: That's okay! Not everything needs to be done. Use it as a menu of possibilities.

**Q: Can I skip DISCOVER if I already know the codebase?**
A: Yes - use standard mode instead: `nelson "Add feature"` (no `--comprehensive` flag)

**Q: DISCOVER is finding deprecated code**
A: Good! This helps avoid building on top of code that's scheduled for removal.

## See Also

- [Quick Mode](./quick-mode.md) - For simple tasks
- [Depth Modes](./depth-modes.md) - Overview of all depth modes
- [Configuration](./configuration.md) - All configuration options
