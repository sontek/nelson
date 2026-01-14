# Blocked Task Workflow Example

This guide demonstrates how to use `nelson-prd`'s blocking and resume features when tasks encounter external dependencies or blockers.

## Scenario: API Integration Project

You're building an application that requires integrating with third-party services. Some tasks depend on external factors like API credentials, service availability, or team approvals.

## Initial PRD File: `api-integration.md`

```markdown
# API Integration Project

## High Priority
- [ ] PRD-001 Set up project structure and configuration
- [ ] PRD-002 Implement authentication service with Auth0
- [ ] PRD-003 Add payment processing with Stripe API
- [ ] PRD-004 Implement email notifications with SendGrid

## Medium Priority
- [ ] PRD-005 Add analytics tracking with Google Analytics
- [ ] PRD-006 Implement cloud storage with AWS S3
```

## Step 1: Start Execution

```bash
$ nelson-prd api-integration.md
```

**Result:**
- PRD-001 completes successfully ✓
- PRD-002 starts but you realize you need Auth0 credentials from the platform team

## Step 2: Block the Task

When you hit the blocker, use Ctrl+C to interrupt Nelson, then block the task:

```bash
$ nelson-prd --block PRD-002 --reason "Waiting for Auth0 credentials from platform team" api-integration.md
```

**What happens:**
- Task PRD-002 is marked as blocked in state
- PRD file updates to show: `[!] PRD-002 Implement authentication service with Auth0 (blocked: Waiting for Auth0 credentials from platform team)`
- State saved in `.nelson/prd/PRD-002/state.json`

## Step 3: Continue with Other Tasks

```bash
$ nelson-prd api-integration.md
```

**Result:**
- PRD-002 is skipped (blocked)
- PRD-003 starts execution
- If PRD-003 also hits a blocker (missing Stripe keys), block it too:

```bash
$ nelson-prd --block PRD-003 --reason "Need Stripe test API keys" api-integration.md
```

## Step 4: Check Status

At any time, view the overall status:

```bash
$ nelson-prd --status api-integration.md
```

**Output:**
```
PRD Status: api-integration.md

Tasks by Status:
  ✓ Completed: 1
  ~ In Progress: 0
  ! Blocked: 2
  ○ Pending: 3

Task Details:
  PRD-001 [✓] Set up project structure and configuration
    Status: completed
    Branch: feature/PRD-001-set-up-project-structure-and-configuration
    Cost: $0.45
    Iterations: 8

  PRD-002 [!] Implement authentication service with Auth0
    Status: blocked
    Branch: feature/PRD-002-implement-authentication-service-with-auth0
    Blocking Reason: Waiting for Auth0 credentials from platform team
    Cost: $0.23 (incomplete)
    Iterations: 3

  PRD-003 [!] Add payment processing with Stripe API
    Status: blocked
    Branch: feature/PRD-003-add-payment-processing-with-stripe-api
    Blocking Reason: Need Stripe test API keys
    Cost: $0.12 (incomplete)
    Iterations: 1

  PRD-004 [○] Implement email notifications with SendGrid
    Status: pending

  PRD-005 [○] Add analytics tracking with Google Analytics
    Status: pending

  PRD-006 [○] Implement cloud storage with AWS S3
    Status: pending

Total Cost: $0.80
```

## Step 5: Unblock with Context

Once you receive the Auth0 credentials, unblock the task with helpful context:

```bash
$ nelson-prd --unblock PRD-002 \
  --context "Auth0 credentials added to .env: AUTH0_DOMAIN=myapp.auth0.com, AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET set. Use the test tenant for development." \
  api-integration.md
```

**What happens:**
- Task PRD-002 status changes from `blocked` to `pending`
- Resume context is stored in task state
- PRD file updates to show: `[ ] PRD-002 Implement authentication service with Auth0`

## Step 6: Resume the Blocked Task

Now resume PRD-002 with the stored context:

```bash
$ nelson-prd --resume-task PRD-002 api-integration.md
```

**What happens:**
- Git automatically switches to branch `feature/PRD-002-implement-authentication-service-with-auth0`
- Nelson receives the prepended resume context in its prompt:
  ```
  RESUME CONTEXT: Auth0 credentials added to .env: AUTH0_DOMAIN=myapp.auth0.com,
  AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET set. Use the test tenant for development.

  Implement authentication service with Auth0
  ```
- Task continues from where it left off
- On success, PRD file updates to: `[x] PRD-002`

## Step 7: Continue Remaining Tasks

After unblocking and completing PRD-003 similarly:

```bash
# Unblock with Stripe keys
$ nelson-prd --unblock PRD-003 \
  --context "Stripe test keys added to .env: STRIPE_SECRET_KEY=sk_test_... Use test mode for all transactions." \
  api-integration.md

# Resume PRD-003
$ nelson-prd --resume-task PRD-003 api-integration.md

# Continue with remaining pending tasks
$ nelson-prd api-integration.md
```

## Best Practices

### 1. **Block Immediately When You Hit a Blocker**
Don't let Nelson continue running if you know it will fail due to missing resources. Block immediately with a clear reason.

### 2. **Provide Detailed Blocking Reasons**
```bash
# ✓ Good
--reason "Waiting for database credentials from DevOps team (Ticket #1234)"

# ✗ Bad
--reason "blocked"
```

### 3. **Add Rich Resume Context**
The resume context helps Nelson understand what changed since the task was blocked:

```bash
# ✓ Good - Specific and actionable
--context "API keys added to .env as TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN. Test phone number: +15551234567. Use sandbox mode."

# ✗ Bad - Too vague
--context "keys added"
```

### 4. **Use Task Info to Track Details**
```bash
$ nelson-prd --task-info PRD-002 api-integration.md
```

Shows full task details including blocking reason, resume context, branch, cost, and iteration count.

### 5. **Keep PRD File as Source of Truth**
The PRD markdown file is automatically updated when you block/unblock tasks. You can also manually edit it:

```markdown
- [!] PRD-002 Task description (blocked: reason here)
```

Just ensure you use the CLI for unblocking so resume context is properly stored.

## Common Blocking Scenarios

### Missing API Credentials
```bash
--reason "Waiting for API keys from vendor"
--context "Keys added to .env as API_KEY and API_SECRET"
```

### External Service Unavailable
```bash
--reason "Test environment is down for maintenance"
--context "Test environment restored. Endpoint: https://test.api.example.com"
```

### Pending Code Review or Approval
```bash
--reason "Waiting for security team approval on authentication approach"
--context "Approved. Use OAuth 2.0 with PKCE flow as discussed in review."
```

### Missing Dependencies from Other Tasks
```bash
--reason "Depends on database schema from PRD-001"
--context "Database migrations completed. Use users table with columns: id, email, password_hash, created_at."
```

### Insufficient Requirements
```bash
--reason "Need clarification on error handling requirements"
--context "Requirements updated: Return 4xx for client errors, 5xx for server errors. Log all errors to CloudWatch."
```

## Workflow Summary

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Start: nelson-prd my-prd.md                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Task Executing │
         └───────┬────────┘
                 │
         ┌───────┴────────┐
         │                │
    Hit Blocker?      Completed?
         │                │
         │ YES            │ YES
         ▼                ▼
┌─────────────────┐  ┌──────────────┐
│ Ctrl+C to stop  │  │ Mark [x]     │
│ --block task    │  │ Continue to  │
│ with reason     │  │ next task    │
└────────┬────────┘  └──────────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Blocker Resolved?               │
└──────────┬──────────────────────┘
           │ YES
           ▼
┌──────────────────────────────┐
│ --unblock with context       │
│ --resume-task to continue    │
└──────────┬───────────────────┘
           │
           ▼
     Task Completes [x]
```

## Troubleshooting

**Q: Can I unblock a task without context?**
A: Yes, `--context` is optional. However, providing context significantly helps Nelson understand what changed.

**Q: What if I accidentally block the wrong task?**
A: Simply unblock it: `nelson-prd --unblock PRD-XXX api-integration.md`

**Q: Can I have multiple tasks blocked at once?**
A: Yes, you can block as many tasks as needed. The orchestrator will skip all blocked tasks.

**Q: What happens to work done before blocking?**
A: All state is preserved including the branch, cost, iterations, and phase. When you resume, Nelson continues from where it left off.

**Q: Can I manually edit the blocking reason in the PRD file?**
A: Yes, you can edit the markdown file, but use the CLI for proper state management. The CLI ensures state files and PRD file stay in sync.

---

This workflow enables you to make steady progress on large projects even when external dependencies cause temporary blockers.
