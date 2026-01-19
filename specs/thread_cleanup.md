# Thread Cleanup & Persistence Spec

**Version**: 1.0
**Date**: 2025-01-11
**Status**: Draft

## Overview

Implement production-ready thread cleanup for LangGraph workflows when deployed to Vercel with Supabase Postgres persistence. This ensures:
1. Workflows persist across serverless cold starts
2. Old workflows are automatically cleaned up
3. Manual deletion removes data from both memory and Postgres
4. Storage costs remain bounded

## Current State

| Component | Status | Issue |
|-----------|--------|-------|
| Memory cache (`_workflows`) | ✅ Working | Lost on cold start |
| Postgres checkpointer | ✅ Configured | Tables auto-created |
| Recovery from Postgres | ✅ Working | `_get_workflow_data()` |
| Delete from memory | ✅ Working | Only deletes from `_workflows` |
| Delete from Postgres | ❌ Missing | Orphaned data remains |
| Scheduled cleanup | ❌ Missing | Unbounded growth |
| Thread TTL tracking | ❌ Missing | No expiration metadata |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     THREAD LIFECYCLE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CREATE                                                          │
│  ├─ POST /api/optimize/start                                    │
│  ├─ Generate thread_id (UUID)                                   │
│  ├─ Store in _workflows (memory)                                │
│  ├─ LangGraph creates checkpoint in Postgres                    │
│  └─ Record created_at timestamp                                 │
│                                                                  │
│  USE                                                             │
│  ├─ Each state change → LangGraph checkpoints to Postgres       │
│  ├─ Update last_accessed_at on each API call                    │
│  └─ Frontend stores thread_id in localStorage                   │
│                                                                  │
│  RECOVER (after cold start)                                      │
│  ├─ Frontend sends thread_id                                    │
│  ├─ _get_workflow_data() checks memory → miss                   │
│  ├─ Query Postgres checkpointer → hit                           │
│  └─ Rebuild _workflows entry from checkpoint                    │
│                                                                  │
│  DELETE (manual)                                                 │
│  ├─ DELETE /api/optimize/{thread_id}                            │
│  ├─ Remove from _workflows                                      │
│  ├─ Delete from Postgres checkpoints table                      │
│  ├─ Delete from Postgres checkpoint_writes table                │
│  └─ Delete from Postgres checkpoint_blobs table                 │
│                                                                  │
│  CLEANUP (scheduled)                                             │
│  ├─ POST /api/optimize/cleanup (cron-triggered)                 │
│  ├─ Find threads with last_accessed_at > TTL                    │
│  ├─ Delete from all Postgres tables                             │
│  └─ Return count of deleted threads                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Database Schema

LangGraph's PostgresSaver creates these tables automatically:

```sql
-- Existing tables (auto-created by LangGraph)
checkpoints (
    thread_id TEXT,
    checkpoint_id TEXT,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_id)
)

checkpoint_writes (
    thread_id TEXT,
    checkpoint_id TEXT,
    task_id TEXT,
    idx INTEGER,
    channel TEXT,
    type TEXT,
    blob BYTEA
)

checkpoint_blobs (
    thread_id TEXT,
    checkpoint_ns TEXT,
    channel TEXT,
    version TEXT,
    type TEXT,
    blob BYTEA
)
```

We'll add a metadata table for tracking:

```sql
-- New table for thread metadata
CREATE TABLE IF NOT EXISTS thread_metadata (
    thread_id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    user_id TEXT,  -- Future: for multi-tenant
    status TEXT DEFAULT 'active',  -- active, completed, expired
    workflow_step TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Index for cleanup queries
CREATE INDEX idx_thread_metadata_expires ON thread_metadata(expires_at);
CREATE INDEX idx_thread_metadata_last_accessed ON thread_metadata(last_accessed_at);
```

---

## TDD Test Specification

### Test File: `apps/api/tests/test_thread_cleanup.py`

```python
"""
TDD Test Specification for Thread Cleanup Feature.

Run these tests with:
    pytest apps/api/tests/test_thread_cleanup.py -v

Tests are organized by feature area:
1. Thread Metadata Tracking
2. Manual Thread Deletion
3. Scheduled Cleanup
4. Recovery After Cleanup
5. Edge Cases & Error Handling
"""
```

---

### 1. Thread Metadata Tracking Tests

```python
class TestThreadMetadataTracking:
    """Tests for thread metadata creation and updates."""

    def test_start_workflow_creates_metadata_record(self):
        """
        GIVEN: A new workflow start request
        WHEN: POST /api/optimize/start is called
        THEN: A thread_metadata record is created with:
            - thread_id matching response
            - created_at set to current time
            - last_accessed_at set to current time
            - expires_at set to created_at + DEFAULT_TTL (30 days)
            - status = 'active'
        """
        pass

    def test_status_check_updates_last_accessed_at(self):
        """
        GIVEN: An existing workflow
        WHEN: GET /api/optimize/status/{thread_id} is called
        THEN: last_accessed_at is updated to current time
        """
        pass

    def test_answer_submission_updates_last_accessed_at(self):
        """
        GIVEN: A workflow in discovery/qa step
        WHEN: POST /api/optimize/{thread_id}/answer is called
        THEN: last_accessed_at is updated to current time
        """
        pass

    def test_workflow_completion_updates_status(self):
        """
        GIVEN: A workflow that reaches 'completed' step
        WHEN: The workflow transitions to completed
        THEN: thread_metadata.status is set to 'completed'
        """
        pass

    def test_metadata_includes_current_workflow_step(self):
        """
        GIVEN: A workflow at various stages
        WHEN: Thread metadata is queried
        THEN: workflow_step reflects current_step from workflow state
        """
        pass
```

---

### 2. Manual Thread Deletion Tests

```python
class TestManualThreadDeletion:
    """Tests for DELETE /api/optimize/{thread_id} endpoint."""

    def test_delete_removes_from_memory_cache(self):
        """
        GIVEN: A workflow exists in _workflows dict
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: The thread_id is removed from _workflows
        """
        pass

    def test_delete_removes_from_postgres_checkpoints(self):
        """
        GIVEN: A workflow with checkpoints in Postgres
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: All rows in 'checkpoints' table with this thread_id are deleted
        """
        pass

    def test_delete_removes_from_postgres_checkpoint_writes(self):
        """
        GIVEN: A workflow with checkpoint_writes in Postgres
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: All rows in 'checkpoint_writes' table with this thread_id are deleted
        """
        pass

    def test_delete_removes_from_postgres_checkpoint_blobs(self):
        """
        GIVEN: A workflow with checkpoint_blobs in Postgres
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: All rows in 'checkpoint_blobs' table with this thread_id are deleted
        """
        pass

    def test_delete_removes_thread_metadata(self):
        """
        GIVEN: A workflow with thread_metadata record
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: The thread_metadata record is deleted
        """
        pass

    def test_delete_nonexistent_thread_returns_404(self):
        """
        GIVEN: A thread_id that doesn't exist anywhere
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: 404 error is returned
        """
        pass

    def test_delete_only_in_postgres_succeeds(self):
        """
        GIVEN: A workflow that exists in Postgres but not in _workflows (cold start scenario)
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: Deletion succeeds and removes from Postgres
        """
        pass

    def test_deleted_thread_cannot_be_recovered(self):
        """
        GIVEN: A workflow that was deleted
        WHEN: GET /api/optimize/status/{thread_id} is called
        THEN: 404 error is returned (not recovered from Postgres)
        """
        pass

    def test_delete_is_idempotent(self):
        """
        GIVEN: A workflow that was already deleted
        WHEN: DELETE /api/optimize/{thread_id} is called again
        THEN: 404 is returned (not 500 error)
        """
        pass
```

---

### 3. Scheduled Cleanup Tests

```python
class TestScheduledCleanup:
    """Tests for POST /api/optimize/cleanup endpoint."""

    def test_cleanup_requires_api_key(self):
        """
        GIVEN: A cleanup request without X-API-Key header
        WHEN: POST /api/optimize/cleanup is called
        THEN: 401 Unauthorized is returned
        """
        pass

    def test_cleanup_rejects_invalid_api_key(self):
        """
        GIVEN: A cleanup request with wrong X-API-Key
        WHEN: POST /api/optimize/cleanup is called
        THEN: 401 Unauthorized is returned
        """
        pass

    def test_cleanup_with_valid_api_key_succeeds(self):
        """
        GIVEN: A cleanup request with valid X-API-Key
        WHEN: POST /api/optimize/cleanup is called
        THEN: 200 OK is returned with deleted count
        """
        pass

    def test_cleanup_deletes_threads_older_than_ttl(self):
        """
        GIVEN: Threads with last_accessed_at older than 30 days
        WHEN: POST /api/optimize/cleanup?days_old=30 is called
        THEN: Those threads are deleted from all tables
        """
        pass

    def test_cleanup_preserves_recent_threads(self):
        """
        GIVEN: Threads with last_accessed_at within last 30 days
        WHEN: POST /api/optimize/cleanup?days_old=30 is called
        THEN: Those threads are NOT deleted
        """
        pass

    def test_cleanup_respects_custom_days_old_parameter(self):
        """
        GIVEN: Threads of various ages
        WHEN: POST /api/optimize/cleanup?days_old=7 is called
        THEN: Only threads older than 7 days are deleted
        """
        pass

    def test_cleanup_returns_accurate_deleted_count(self):
        """
        GIVEN: 5 threads older than TTL, 3 threads newer
        WHEN: POST /api/optimize/cleanup is called
        THEN: Response shows {"deleted": 5, "preserved": 3}
        """
        pass

    def test_cleanup_handles_empty_database(self):
        """
        GIVEN: No threads exist in database
        WHEN: POST /api/optimize/cleanup is called
        THEN: Response shows {"deleted": 0} without error
        """
        pass

    def test_cleanup_removes_from_memory_cache_too(self):
        """
        GIVEN: Old threads exist in both _workflows and Postgres
        WHEN: POST /api/optimize/cleanup is called
        THEN: Threads are removed from _workflows dict as well
        """
        pass

    def test_cleanup_handles_partial_data(self):
        """
        GIVEN: Thread exists in checkpoints but not checkpoint_writes
        WHEN: POST /api/optimize/cleanup is called
        THEN: Cleanup succeeds without error
        """
        pass

    def test_cleanup_logs_deleted_thread_ids(self):
        """
        GIVEN: Threads to be cleaned up
        WHEN: POST /api/optimize/cleanup is called
        THEN: Deleted thread_ids are logged for audit trail
        """
        pass
```

---

### 4. Recovery After Cleanup Tests

```python
class TestRecoveryAfterCleanup:
    """Tests for workflow recovery behavior after cleanup runs."""

    def test_cleaned_thread_not_recoverable(self):
        """
        GIVEN: A thread that was deleted by cleanup
        WHEN: _get_workflow_data(thread_id) is called
        THEN: HTTPException 404 is raised
        """
        pass

    def test_preserved_thread_still_recoverable(self):
        """
        GIVEN: A thread that was preserved by cleanup (recent activity)
        WHEN: Server restarts and _get_workflow_data(thread_id) is called
        THEN: Thread is recovered from Postgres successfully
        """
        pass

    def test_frontend_handles_cleaned_thread_gracefully(self):
        """
        GIVEN: Frontend has thread_id in localStorage
        AND: That thread was cleaned up
        WHEN: Frontend calls status endpoint
        THEN: Frontend should receive 404 and can start fresh

        Note: This is a frontend integration test - document expected behavior
        """
        pass
```

---

### 5. Edge Cases & Error Handling Tests

```python
class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error scenarios."""

    def test_cleanup_continues_on_single_thread_failure(self):
        """
        GIVEN: 10 threads to clean up, 1 has corrupted data
        WHEN: POST /api/optimize/cleanup is called
        THEN: Other 9 threads are still cleaned up, error is logged
        """
        pass

    def test_delete_handles_postgres_connection_failure(self):
        """
        GIVEN: Postgres is temporarily unavailable
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: Memory cache is still cleared
        AND: Error is logged with thread_id for retry
        AND: 500 error is returned with helpful message
        """
        pass

    def test_cleanup_handles_postgres_connection_failure(self):
        """
        GIVEN: Postgres is temporarily unavailable
        WHEN: POST /api/optimize/cleanup is called
        THEN: 503 Service Unavailable is returned
        AND: Error is logged
        """
        pass

    def test_concurrent_delete_requests_are_safe(self):
        """
        GIVEN: A thread_id
        WHEN: Two DELETE requests are made simultaneously
        THEN: Both return successfully (one 200, one 404)
        AND: No data corruption occurs
        """
        pass

    def test_cleanup_during_active_workflow(self):
        """
        GIVEN: A workflow that's currently being used (recent last_accessed_at)
        WHEN: Cleanup runs
        THEN: Active workflow is NOT deleted
        """
        pass

    def test_large_batch_cleanup_performance(self):
        """
        GIVEN: 1000 threads older than TTL
        WHEN: POST /api/optimize/cleanup is called
        THEN: Cleanup completes within 30 seconds
        AND: Uses batch deletion for efficiency
        """
        pass

    def test_cleanup_with_no_database_configured(self):
        """
        GIVEN: DATABASE_URL is not set (memory-only mode)
        WHEN: POST /api/optimize/cleanup is called
        THEN: 200 OK with message "No database configured, memory-only cleanup"
        AND: _workflows older than TTL are cleared from memory
        """
        pass
```

---

### 6. Integration Tests with Vercel Cron

```python
class TestVercelCronIntegration:
    """Tests simulating Vercel cron behavior."""

    def test_cron_endpoint_accepts_vercel_cron_header(self):
        """
        GIVEN: Request with 'x-vercel-cron-signature' header
        WHEN: POST /api/optimize/cleanup is called
        THEN: Request is authenticated (alternative to API key for Vercel cron)
        """
        pass

    def test_cron_endpoint_returns_quickly(self):
        """
        GIVEN: Cleanup endpoint
        WHEN: Called by Vercel cron (10s timeout)
        THEN: Returns within 10 seconds
        AND: If more work needed, schedules continuation
        """
        pass
```

---

## Implementation Plan

### Phase 1: Database Schema (Day 1)

1. Create migration for `thread_metadata` table
2. Add indexes for query performance
3. Test migration on Supabase

**Files to modify:**
- `apps/api/migrations/001_thread_metadata.sql` (new)
- `apps/api/config.py` (add migration runner)

### Phase 2: Metadata Tracking (Day 1-2)

1. Create `ThreadMetadataService` class
2. Hook into workflow start to create metadata
3. Hook into status/answer endpoints to update last_accessed_at
4. Add tests for metadata tracking

**Files to modify:**
- `apps/api/services/thread_metadata.py` (new)
- `apps/api/routers/optimize.py`
- `apps/api/tests/test_thread_cleanup.py` (new)

### Phase 3: Enhanced Delete (Day 2)

1. Update `delete_workflow` to delete from Postgres
2. Add Postgres table deletion logic
3. Add tests for deletion

**Files to modify:**
- `apps/api/routers/optimize.py`
- `apps/api/tests/test_thread_cleanup.py`

### Phase 4: Scheduled Cleanup (Day 2-3)

1. Create cleanup endpoint with API key auth
2. Implement batch deletion logic
3. Add Vercel cron configuration
4. Add tests for cleanup

**Files to modify:**
- `apps/api/routers/optimize.py`
- `vercel.json`
- `apps/api/tests/test_thread_cleanup.py`

### Phase 5: Integration Testing (Day 3)

1. End-to-end test with real Supabase
2. Load test cleanup with many threads
3. Verify Vercel cron works

---

## Configuration

### Environment Variables

```bash
# Required for Postgres persistence
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.co:6543/postgres
LANGGRAPH_CHECKPOINTER=postgres

# Required for cleanup endpoint
CLEANUP_API_KEY=your-secret-key-here

# Optional: Custom TTL (default 30 days)
THREAD_TTL_DAYS=30
```

### Vercel Configuration

```json
// vercel.json
{
  "crons": [
    {
      "path": "/api/optimize/cleanup",
      "schedule": "0 0 * * *"
    }
  ]
}
```

---

## Success Criteria

| Criteria | Measurement |
|----------|-------------|
| All TDD tests pass | `pytest test_thread_cleanup.py` green |
| Delete removes from Postgres | Manual verification in Supabase |
| Cleanup runs daily | Vercel cron logs show execution |
| No orphaned data after 30 days | Query shows 0 threads > 30 days old |
| Recovery still works | Cold start → status call → workflow recovered |
| Performance acceptable | Cleanup of 1000 threads < 30s |

---

## Rollback Plan

If issues arise:

1. **Disable cron**: Remove cron from `vercel.json`, redeploy
2. **Revert delete**: The old delete (memory-only) still works
3. **Data recovery**: Postgres data is not deleted immediately; can restore from backup

---

## Future Enhancements

1. **User-scoped cleanup**: Delete only threads for a specific user
2. **Soft delete**: Mark as deleted, purge after 7 days
3. **Export before delete**: Offer users export of their data
4. **Cleanup dashboard**: Admin UI to see storage usage and trigger cleanup
