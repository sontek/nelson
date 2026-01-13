# Nelson Python Implementation - Complete Analysis & Improvement Plan

## Phase 1: PLAN (Analysis & Design)

### Context
The Python implementation (nelson) is a reimplementation of the bash ralph script. The Python version has made excellent progress with:
- ✅ Core workflow orchestration
- ✅ State management with JSON persistence
- ✅ Phase transitions (6 phases)
- ✅ Circuit breaker detection
- ✅ Click-based CLI with rich formatting
- ✅ Provider abstraction (Claude)
- ✅ Comprehensive test coverage
- ✅ Type hints and modern Python practices
- ✅ Renamed from ralph to nelson (mostly complete)

### Critical Issues to Address

**Issue 1: Iteration Loop Logic**
The current implementation stops when EXIT_SIGNAL is detected, but should continue looping back to Phase 1 to check for more work. The "ralph wiggum" pattern means repeatedly asking Claude if there's more work, allowing it to discover additional tasks across multiple cycles.

**Issue 2: .ralph Directory References**
Code still references `.ralph/` in some places - should be `.nelson/` throughout. The `.ralph` folder exists in repo but should not be used by new code.

**Issue 3: Default max_iterations Value**
Bash script uses default of 10 complete cycles, Python uses 50. Should align on a sensible default (bash's 10 is better for most tasks).

### Analysis Tasks

- [x] Read and thoroughly analyze bash ralph script (~/code/sontek/homies/bin/ralph)
- [x] Read and analyze bash ralph-prd script for future reference
- [x] Review all Python nelson source files (cli.py, workflow.py, config.py, state.py, etc.)
- [x] Identify discrepancies between bash and Python implementations
- [x] Review existing tests to understand coverage
- [x] Check git history to understand recent changes
- [x] Create comprehensive plan with all 6 phases defined

## Phase 2: IMPLEMENT (Atomic Implementation Tasks)

### Fix Iteration Loop Logic
- [x] Update workflow.py EXIT_SIGNAL handling to continue to next cycle instead of breaking
- [x] Ensure cycle completion always loops back to Phase 1 for re-planning
- [x] Verify cycle_iterations counter increments correctly after Phase 6

### Fix Configuration Defaults
- [x] Change default max_iterations from 50 to 10 in config.py
- [x] Update CLI help text to reflect correct default
- [x] Update tests that assume 50 as default

### Update System Prompt
- [x] Add guidance to system prompt: "Do not leave FIXME, TODO, or placeholder comments - implement fully"
- [x] Ensure prompt clarity about completing work vs leaving markers

### Cleanup Directory References
- [x] Audit all files for .ralph/ string references and update to .nelson/
- [x] Verify .gitignore excludes .nelson/ not .ralph/
- [ ] Update any test fixtures using .ralph paths

### Verify Test Coverage for Iteration Logic
- [ ] Add/update tests for multi-cycle iteration behavior
- [ ] Test EXIT_SIGNAL triggers cycle completion and continues
- [ ] Test that max_iterations limits complete cycles not total iterations
- [ ] Verify circuit breaker works across multiple cycles

## Phase 3: REVIEW (Code Quality Check)

- [ ] Review all implementation changes for correctness
- [ ] Check for any remaining ralph→nelson naming issues
- [ ] Verify no unintended behavior changes
- [ ] Ensure code follows project style (ruff, mypy)

## Phase 4: TEST (Validation)

- [ ] Run full test suite: pytest
- [ ] Run type checker: mypy src/
- [ ] Run linter/formatter: ruff check src/ && ruff format src/
- [ ] Fix any test failures or type errors

## Phase 5: FINAL-REVIEW (Pre-Commit Verification)

- [ ] Verify all changes align with original task requirements
- [ ] Confirm iteration loop matches "ralph wiggum" pattern
- [ ] Ensure no .ralph/ references in active code
- [ ] Check that all tests pass

## Phase 6: COMMIT (Finalize Changes)

- [ ] Commit all implementation changes with descriptive message
- [ ] Ensure clean git status (no untracked nelson files)
