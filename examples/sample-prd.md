# Sample PRD: E-commerce Platform Enhancement

This is an example Product Requirements Document (PRD) that demonstrates the format expected by `nelson-prd`.

## Overview

This PRD contains tasks for enhancing an e-commerce platform with user authentication, product management, and checkout features.

## Task Format

Each task must have:
- A unique ID in format `PRD-NNN` (e.g., PRD-001, PRD-002)
- A checkbox status indicator: `[ ]` (pending), `[~]` (in progress), `[x]` (completed), `[!]` (blocked)
- A clear, descriptive task description

Tasks are organized by priority (High, Medium, Low) and execute in that order.

---

## High Priority

- [ ] PRD-001 Implement user authentication system with JWT tokens
- [ ] PRD-002 Create user profile management with edit capabilities
- [ ] PRD-003 Add password reset functionality via email
- [ ] PRD-004 Implement role-based access control (RBAC) for admin/user roles

## Medium Priority

- [ ] PRD-005 Add product catalog with search and filtering
- [ ] PRD-006 Implement shopping cart with add/remove/update quantity
- [ ] PRD-007 Create checkout flow with order summary
- [ ] PRD-008 Add email notification system for order confirmations
- [ ] PRD-009 Implement product reviews and ratings system

## Low Priority

- [ ] PRD-010 Add dark mode toggle to application settings
- [ ] PRD-011 Implement user wishlist functionality
- [ ] PRD-012 Create admin dashboard for order management
- [ ] PRD-013 Add product recommendation engine based on browsing history

---

## Usage

### Execute all pending tasks
```bash
nelson-prd sample-prd.md
```

### Check current status
```bash
nelson-prd --status sample-prd.md
```

### Preview tasks without execution
```bash
nelson-prd --dry-run sample-prd.md
```

### Block a task when you encounter dependencies
```bash
nelson-prd --block PRD-003 --reason "Waiting for email service API credentials" sample-prd.md
```

### Unblock a task when dependencies are resolved
```bash
nelson-prd --unblock PRD-003 --context "Email API keys added to .env as SENDGRID_API_KEY" sample-prd.md
```

### Resume a specific blocked task
```bash
nelson-prd --resume-task PRD-003 sample-prd.md
```

### Get detailed information about a task
```bash
nelson-prd --task-info PRD-001 sample-prd.md
```

## Notes

- Each task runs through Nelson's full 6-phase workflow (PLAN → IMPLEMENT → REVIEW → TEST → FINAL-REVIEW → COMMIT)
- Git branches are automatically created with format: `feature/PRD-NNN-description`
- Task state and progress are saved in `.nelson/prd/`
- Tasks can be blocked and resumed with context preservation
- Cost tracking is automatic for each task
