# Code Review Checklist

Apply ALL categories when reviewing changes.

## 1. CORRECTNESS & BUGS
- Logic errors, off-by-one errors, incorrect algorithms
- Edge cases: null/undefined, empty collections, boundary values
- Race conditions, concurrency issues
- Proper error handling and validation
- Return values and side effects are correct

## 2. CODEBASE PATTERNS & CONSISTENCY
- Follows existing architectural patterns in the codebase
- Uses same libraries/frameworks as similar features
- Matches naming conventions (functions, variables, files)
- Consistent code style with existing code
- Follows established project structure/organization

## 3. CODE QUALITY
- Readable and maintainable
- No unnecessary complexity or over-engineering
- Proper abstractions and separation of concerns
- No code duplication that should be refactored (DRY principle)
- Type safety (if applicable: TypeScript, Python type hints, etc.)

## 4. SECURITY
- No SQL injection, XSS, command injection vulnerabilities
- Proper input validation and sanitization
- No hardcoded secrets or sensitive data
- Secure authentication/authorization checks

## 5. COMPLETENESS
- No TODO/FIXME/XXX comments or placeholder stubs
- All implementations are production-ready, not partial
- Adequate test coverage for new functionality
- Required edge cases are handled

## 6. UNWANTED CHANGES
- No unwanted docs (README, SUMMARY.md, guides)
- No .claude/ or .nelson/ files
- No unrelated refactoring or scope creep

---

## BLOCKING ISSUES

Flag ANY of these as blocking - they MUST be fixed:
- **BUGS**: Logic errors, incorrect behavior, missing edge case handling
- **SECURITY**: Any security vulnerability from checklist above
- **INCOMPLETE**: TODO/FIXME/XXX comments, placeholder code, partial implementations
- **HARDCODED VALUES**: Magic numbers/strings that should be constants or configurable
- **MISSING TESTS**: New logic with complex edge cases that lacks test coverage
- **BREAKING CHANGES**: Changes to public APIs/data structures without migration path
- **INCONSISTENT**: Violates established codebase patterns (check similar code)

When blocking issues are found:
1. Add specific Fix tasks to Phase 2: `- [ ] Fix: <issue with file:line>`
2. Include exact file:line reference (e.g., src/workflow.py:445)
3. Be specific about the issue and fix needed
4. Workflow will loop: IMPLEMENT → TEST → REVIEW
