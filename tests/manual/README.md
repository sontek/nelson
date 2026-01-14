# Manual Tests

This directory contains manual test scripts for human-driven verification of Nelson and nelson-prd functionality.

## Purpose

While automated tests (pytest) verify functionality programmatically, manual tests serve different purposes:

1. **Human Verification**: Interactive walkthrough of features for manual inspection
2. **Documentation**: Demonstrate real-world usage patterns
3. **Smoke Testing**: Quick verification after installation or deployment
4. **Debugging**: Step-by-step execution to identify issues
5. **Demo**: Show features to users or during development

## Available Tests

### test_prd_e2e_manual.sh

**Purpose**: End-to-end manual verification of nelson-prd workflow

**What it tests**:
- PRD file parsing with multiple tasks
- Task ID validation (format, duplicates)
- Priority-based ordering (High → Medium → Low)
- Dry-run preview mode
- Status and task-info commands
- Blocking/unblocking workflow
- Resume context storage and retrieval
- State file persistence
- Backup file creation
- Error handling and validation

**Usage**:
```bash
./tests/manual/test_prd_e2e_manual.sh
```

**Interactive**: The script pauses at each step, allowing you to inspect output and state files. Press Enter to continue through the workflow.

**Requirements**:
- `nelson` CLI installed and in PATH
- `nelson-prd` CLI installed and in PATH
- `git` available
- Optional: `jq` for pretty JSON formatting
- Optional: `tree` for directory visualization

**Output**: Creates temporary test directory at `/tmp/nelson-prd-manual-test-<PID>` and cleans up automatically on exit.

## Running Manual Tests

### Quick Run

```bash
# Run the PRD e2e test
./tests/manual/test_prd_e2e_manual.sh
```

### Inspection Mode

To keep the test directory for inspection:

```bash
# Comment out the trap cleanup line in the script
# Then run normally
./tests/manual/test_prd_e2e_manual.sh

# Test directory will remain at /tmp/nelson-prd-manual-test-<PID>
cd /tmp/nelson-prd-manual-test-*/
ls -la .nelson/prd/
```

### Debug Mode

```bash
# Run with bash debug output
bash -x ./tests/manual/test_prd_e2e_manual.sh
```

## When to Use Manual Tests

**Use manual tests when**:
- Verifying installation on a new system
- Demonstrating features to users or team members
- Debugging issues that require step-by-step inspection
- Testing integration with external tools (git, nelson)
- Validating error messages and user experience

**Use automated tests (pytest) when**:
- Running CI/CD pipelines
- Verifying code changes during development
- Ensuring regression coverage
- Testing edge cases programmatically
- Measuring test coverage

## Adding New Manual Tests

To add a new manual test script:

1. Create executable bash script: `test_<feature>_manual.sh`
2. Include clear purpose and usage in header comments
3. Use colored output for readability (RED, GREEN, YELLOW, BLUE)
4. Make it interactive with pauses between steps
5. Clean up temporary files/directories
6. Add entry to this README

### Template

```bash
#!/usr/bin/env bash
# Manual test for <feature>
#
# Purpose: <what this tests>
#
# Usage:
#   ./tests/manual/test_<feature>_manual.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test configuration
TEST_DIR="/tmp/nelson-test-$$"

# Cleanup function
cleanup() {
    [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# Test steps...
echo -e "${BLUE}Step 1: ...${NC}"
# ... test code ...
echo -e "${GREEN}✓ Step complete${NC}"
echo ""
```

## Best Practices

1. **Clear Output**: Use colored output and clear step descriptions
2. **Interactive**: Pause between steps for inspection
3. **Self-Contained**: Create temporary directories, don't modify user's workspace
4. **Cleanup**: Always cleanup temporary files/directories
5. **Error Handling**: Use `set -e` and trap for cleanup on error
6. **Documentation**: Include usage and requirements in script header
7. **Realistic**: Use realistic examples that mirror actual usage
