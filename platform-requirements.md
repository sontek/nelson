## High Priority
- [X] PRD-001 Review and implement fixes for PR https://github.com/stacklet/platform/pull/2782

      TASK TYPE: Review + Implement Fixes

      Perform comprehensive code review and DIRECTLY IMPLEMENT all critical and high-priority fixes you find.

      Quality checks:
      - Make sure the quality is good and files are in appropriate locations
      - Check for weird migration files like /platform/migrations/alembic/versions/57fdbd7f74da_merge_queue_tables_and_api_key_.py
        that are just empty migrations saying "merge queue tables and api key migrations" - we don't need empty merge migrations
        since we haven't landed that PR yet, it should have a fresh migration with proper SHAs
      - Review where unit test files were placed and verify they follow repository standards in `main`

      Are there things you would change / improve that we missed based on the architecture diagram ~/code/stacklet/execution/docs/postgres_queue_architecture.md?  This PR
      is 1 of 4 PRs implementing that feature.  The other ones are:

      - https://github.com/stacklet/platform/pull/2834
      - https://github.com/stacklet/platform/pull/2869
      - https://github.com/stacklet/platform/pull/2921

      These branches are stacked and target each other.   It goes:

      1. execution_queue_tables
      2. queue-writer-implementation
      3. dispatcher-implementation
      4. queue-execution-final

      Make sure to review where unit tests files were places in the changes and that the followed the standards of the repository in `main`.


- [x] PRD-002 Review and implement fixes for PR https://github.com/stacklet/platform/pull/2834

      TASK TYPE: Review + Implement Fixes

      Perform comprehensive code review and DIRECTLY IMPLEMENT all critical and high-priority fixes you find.

      Quality checks:
      - Make sure the quality is good and files are in appropriate locations
      - Ensure code follows DRY principles - no unnecessary duplication where code can be shared
      - Look for cleaner implementation opportunities
      - Review where unit test files were placed and verify they follow repository standards in `main`

      Are there things you would change / improve that we missed based on the architecture diagram ~/code/stacklet/execution/docs/postgres_queue_architecture.md?  This PR
      is 1 of 4 PRs implementing that feature.  The other ones are:

      - https://github.com/stacklet/platform/pull/2782 
      - https://github.com/stacklet/platform/pull/2869
      - https://github.com/stacklet/platform/pull/2921

      These branches are stacked and target each other.   It goes:

      1. execution_queue_tables
      2. queue-writer-implementation
      3. dispatcher-implementation
      4. queue-execution-final

      Make sure to review where unit tests files were places in the changes and that the followed the standards of the repository in `main`.

      Pull in the latest changes from the base branch of the PR as well if there
      are any changes that have been pushed to it since this branch was created.

      Review the changes in the stacked branches to make sure you don't implement
      features / code that have been implemented in the subsequent branches.

- [~] PRD-003 Review and implement fixes for PR https://github.com/stacklet/platform/pull/2869

      TASK TYPE: Review + Implement Fixes

      Perform comprehensive code review and DIRECTLY IMPLEMENT all critical and high-priority fixes you find.

      Quality checks:
      - Make sure the quality is good and files are in appropriate locations
      - Ensure code follows DRY principles - no unnecessary duplication where code can be shared
      - Look for cleaner implementation opportunities
      - Review where unit test files were placed and verify they follow repository standards in `main`

      NOTE: Skip documentation tasks (PR descriptions, external docs). Focus ONLY on code quality, tests, and implementation fixes.

      Are there things you would change / improve that we missed based on the architecture diagram ~/code/stacklet/execution/docs/postgres_queue_architecture.md?  This PR
      is 1 of 4 PRs implementing that feature.  The other ones are:

      - https://github.com/stacklet/platform/pull/2782 
      - https://github.com/stacklet/platform/pull/2834
      - https://github.com/stacklet/platform/pull/2921

      These branches are stacked and target each other.   It goes:

      1. execution_queue_tables
      2. queue-writer-implementation
      3. dispatcher-implementation
      4. queue-execution-final

      Make sure to review where unit tests files were places in the changes and that the followed the standards of the repository in `main`.

      Pull in the latest changes from the base branch of the PR as well if there
      are any changes that have been pushed to it since this branch was created.

      Review the changes in the stacked branches to make sure you don't implement
      features / code that have been implemented in the subsequent branches.

- [x] PRD-004 Review and implement fixes for PR https://github.com/stacklet/platform/pull/2921

      TASK TYPE: Review + Implement Fixes

      Perform comprehensive code review and DIRECTLY IMPLEMENT all critical and high-priority fixes you find.

      Quality checks:
      - Make sure the quality is good and files are in appropriate locations
      - Ensure code follows DRY principles - no unnecessary duplication where code can be shared
      - Look for cleaner implementation opportunities
      - Review where unit test files were placed and verify they follow repository standards in `main`

      IMPORTANT: DO NOT just post a review comment - implement the fixes directly in the code and commit them.

      Are there things you would change / improve that we missed based on the architecture diagram ~/code/stacklet/execution/docs/postgres_queue_architecture.md?  This PR
      is 1 of 4 PRs implementing that feature.  The other ones are:

      - https://github.com/stacklet/platform/pull/2782 
      - https://github.com/stacklet/platform/pull/2834
      - https://github.com/stacklet/platform/pull/2869

      These branches are stacked and target each other.   It goes:

      1. execution_queue_tables
      2. queue-writer-implementation
      3. dispatcher-implementation
      4. queue-execution-final

      Make sure to review where unit tests files were places in the changes and that the followed the standards of the repository in `main`.

      Pull in the latest changes from the base branch of the PR as well if there
      are any changes that have been pushed to it since this branch was created.
