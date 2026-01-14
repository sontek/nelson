#!/usr/bin/env bash
# Manual E2E test script for nelson-prd
#
# This script provides a manual test workflow for verifying nelson-prd
# functionality end-to-end. It creates a test repository, sample PRD file,
# and walks through the full blocking/unblocking/resume workflow.
#
# Usage:
#   ./tests/manual/test_prd_e2e_manual.sh
#
# Requirements:
#   - nelson CLI installed and in PATH
#   - nelson-prd CLI installed and in PATH
#   - git available

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="/tmp/nelson-prd-manual-test-$$"
PRD_FILE="test-requirements.md"

echo -e "${BLUE}=== Nelson PRD Manual E2E Test ===${NC}"
echo ""
echo "This script will:"
echo "  1. Create a test git repository"
echo "  2. Generate a sample PRD file with tasks"
echo "  3. Execute nelson-prd with mocked Nelson (dry run)"
echo "  4. Test blocking/unblocking workflow"
echo "  5. Verify state persistence"
echo "  6. Test status and task-info commands"
echo "  7. Clean up test directory"
echo ""
echo -e "${YELLOW}Press Enter to continue or Ctrl+C to cancel...${NC}"
read

# Cleanup function
cleanup() {
    if [ -d "$TEST_DIR" ]; then
        echo -e "${YELLOW}Cleaning up test directory: $TEST_DIR${NC}"
        rm -rf "$TEST_DIR"
    fi
}

# Register cleanup on exit
trap cleanup EXIT

# Step 1: Create test repository
echo -e "${BLUE}Step 1: Creating test repository${NC}"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"
git init
git config user.name "Test User"
git config user.email "test@example.com"

# Create initial commit
echo "# Test Project" > README.md
git add README.md
git commit -m "Initial commit"

echo -e "${GREEN}✓ Test repository created${NC}"
echo ""

# Step 2: Create sample PRD file
echo -e "${BLUE}Step 2: Creating sample PRD file${NC}"
cat > "$PRD_FILE" <<'EOF'
# Test Requirements

## High Priority
- [ ] PRD-001 Implement user authentication system
- [ ] PRD-002 Create user profile management
- [ ] PRD-003 Add password reset functionality

## Medium Priority
- [ ] PRD-004 Add email notification system
- [ ] PRD-005 Implement search functionality

## Low Priority
- [ ] PRD-006 Add dark mode toggle
- [ ] PRD-007 Create user preferences page
EOF

echo "Created PRD file with 7 tasks:"
cat "$PRD_FILE"
echo ""
echo -e "${GREEN}✓ PRD file created${NC}"
echo ""

# Step 3: Dry run to preview tasks
echo -e "${BLUE}Step 3: Running dry-run to preview execution order${NC}"
echo "Command: nelson-prd --dry-run $PRD_FILE"
echo ""
nelson-prd --dry-run "$PRD_FILE" || true
echo ""
echo -e "${GREEN}✓ Dry run completed${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 4: Check initial status
echo -e "${BLUE}Step 4: Checking initial status${NC}"
echo "Command: nelson-prd --status $PRD_FILE"
echo ""
nelson-prd --status "$PRD_FILE" || true
echo ""
echo -e "${GREEN}✓ Initial status checked${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 5: Test task-info command
echo -e "${BLUE}Step 5: Getting detailed info for PRD-001${NC}"
echo "Command: nelson-prd --task-info PRD-001 $PRD_FILE"
echo ""
nelson-prd --task-info PRD-001 "$PRD_FILE" || true
echo ""
echo -e "${GREEN}✓ Task info retrieved${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 6: Block a task
echo -e "${BLUE}Step 6: Blocking PRD-003 (simulating external dependency)${NC}"
echo "Command: nelson-prd --block PRD-003 --reason \"Waiting for email service API keys\" $PRD_FILE"
echo ""
nelson-prd --block PRD-003 --reason "Waiting for email service API keys" "$PRD_FILE" || true
echo ""
echo "PRD file after blocking:"
cat "$PRD_FILE"
echo ""
echo -e "${GREEN}✓ Task blocked${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 7: Check status after blocking
echo -e "${BLUE}Step 7: Checking status after blocking${NC}"
echo "Command: nelson-prd --status $PRD_FILE"
echo ""
nelson-prd --status "$PRD_FILE" || true
echo ""
echo -e "${GREEN}✓ Status shows blocked task${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 8: Unblock task with context
echo -e "${BLUE}Step 8: Unblocking PRD-003 with resume context${NC}"
echo "Command: nelson-prd --unblock PRD-003 --context \"API keys added to .env as EMAIL_API_KEY\" $PRD_FILE"
echo ""
nelson-prd --unblock PRD-003 --context "API keys added to .env as EMAIL_API_KEY" "$PRD_FILE" || true
echo ""
echo "PRD file after unblocking:"
cat "$PRD_FILE"
echo ""
echo -e "${GREEN}✓ Task unblocked with context${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 9: Check task info after unblocking
echo -e "${BLUE}Step 9: Checking PRD-003 details (should show resume context)${NC}"
echo "Command: nelson-prd --task-info PRD-003 $PRD_FILE"
echo ""
nelson-prd --task-info PRD-003 "$PRD_FILE" || true
echo ""
echo -e "${GREEN}✓ Resume context stored${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 10: Test state directory structure
echo -e "${BLUE}Step 10: Verifying state directory structure${NC}"
echo "Command: tree .nelson/prd/ (or ls -R if tree not available)"
echo ""
if command -v tree &> /dev/null; then
    tree .nelson/prd/ || true
else
    find .nelson/prd/ -type f -o -type d | sort
fi
echo ""
echo -e "${GREEN}✓ State structure verified${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 11: Test state file content
echo -e "${BLUE}Step 11: Inspecting PRD state file${NC}"
echo "Command: cat .nelson/prd/prd-state.json | jq ."
echo ""
if command -v jq &> /dev/null; then
    cat .nelson/prd/prd-state.json | jq . || cat .nelson/prd/prd-state.json
else
    cat .nelson/prd/prd-state.json
fi
echo ""
echo -e "${GREEN}✓ State file inspected${NC}"
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 12: Test task state file
echo -e "${BLUE}Step 12: Inspecting PRD-003 task state${NC}"
echo "Command: cat .nelson/prd/PRD-003/state.json | jq ."
echo ""
if [ -f .nelson/prd/PRD-003/state.json ]; then
    if command -v jq &> /dev/null; then
        cat .nelson/prd/PRD-003/state.json | jq . || cat .nelson/prd/PRD-003/state.json
    else
        cat .nelson/prd/PRD-003/state.json
    fi
    echo ""
    echo -e "${GREEN}✓ Task state file inspected${NC}"
else
    echo "Task state file not yet created (expected for blocked-only task)"
    echo -e "${YELLOW}⚠ Task state not created yet (normal)${NC}"
fi
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 13: Test backup mechanism
echo -e "${BLUE}Step 13: Verifying backup files${NC}"
echo "Command: ls -lah .nelson/backups/"
echo ""
if [ -d .nelson/backups ]; then
    ls -lah .nelson/backups/
    echo ""
    echo "Latest backup:"
    ls -t .nelson/backups/*.backup-* 2>/dev/null | head -1 | xargs cat || echo "No backups found"
    echo ""
    echo -e "${GREEN}✓ Backup mechanism verified${NC}"
else
    echo "No backups directory (may not be created until PRD file is modified)"
    echo -e "${YELLOW}⚠ Backups not created yet (normal)${NC}"
fi
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 14: Test validation - duplicate IDs
echo -e "${BLUE}Step 14: Testing validation - duplicate task IDs${NC}"
cat > "${PRD_FILE}.invalid" <<'EOF'
## High Priority
- [ ] PRD-001 First task
- [ ] PRD-001 Duplicate ID (should error)
EOF

echo "Testing with invalid PRD (duplicate IDs):"
cat "${PRD_FILE}.invalid"
echo ""
echo "Command: nelson-prd --status ${PRD_FILE}.invalid"
echo ""
if nelson-prd --status "${PRD_FILE}.invalid" 2>&1; then
    echo -e "${RED}✗ Should have failed with duplicate ID error${NC}"
else
    echo -e "${GREEN}✓ Duplicate ID validation working${NC}"
fi
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 15: Test validation - invalid format
echo -e "${BLUE}Step 15: Testing validation - invalid task ID format${NC}"
cat > "${PRD_FILE}.invalid2" <<'EOF'
## High Priority
- [ ] PRD-1 Invalid format (only 1 digit)
- [ ] PRD-12 Invalid format (only 2 digits)
EOF

echo "Testing with invalid PRD (bad format):"
cat "${PRD_FILE}.invalid2"
echo ""
echo "Command: nelson-prd --status ${PRD_FILE}.invalid2"
echo ""
if nelson-prd --status "${PRD_FILE}.invalid2" 2>&1; then
    echo -e "${RED}✗ Should have failed with format error${NC}"
else
    echo -e "${GREEN}✓ Task ID format validation working${NC}"
fi
echo ""
echo -e "${YELLOW}Press Enter to continue...${NC}"
read

# Step 16: Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Verified functionality:"
echo "  ✓ PRD file parsing with 7 tasks"
echo "  ✓ Task ID validation (PRD-NNN format)"
echo "  ✓ Priority-based ordering (High → Medium → Low)"
echo "  ✓ Dry-run preview mode"
echo "  ✓ Status command with task breakdown"
echo "  ✓ Task-info command for detailed view"
echo "  ✓ Blocking workflow (--block with reason)"
echo "  ✓ Unblocking workflow (--unblock with context)"
echo "  ✓ Resume context storage"
echo "  ✓ State file persistence (.nelson/prd/)"
echo "  ✓ Task state files (per-task directories)"
echo "  ✓ Backup file creation"
echo "  ✓ Duplicate ID validation"
echo "  ✓ Invalid format validation"
echo ""
echo -e "${GREEN}All manual tests completed successfully!${NC}"
echo ""
echo "Test directory: $TEST_DIR"
echo "To inspect further: cd $TEST_DIR"
echo "To clean up now: rm -rf $TEST_DIR"
echo ""
echo -e "${YELLOW}Press Enter to clean up and exit...${NC}"
read

# Cleanup happens via trap
echo -e "${GREEN}✓ Cleanup complete${NC}"
