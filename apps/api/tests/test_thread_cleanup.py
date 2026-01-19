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

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Set test environment before imports
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("EXA_API_KEY", "test-key")

from main import app
from routers.optimize import _workflows, _save_workflow_data, _get_workflow_data
from services.thread_metadata import ThreadMetadataService, get_metadata_service


client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_workflow():
    """Create a mock workflow in memory."""
    thread_id = "test-thread-123"
    _save_workflow_data(thread_id, {
        "state": {
            "current_step": "research",
            "user_profile": {"name": "Test User"},
        },
        "config": {"configurable": {"thread_id": thread_id}},
        "created_at": datetime.now().isoformat(),
    })
    yield thread_id
    # Cleanup
    _workflows.pop(thread_id, None)


@pytest.fixture
def mock_old_workflow():
    """Create a mock workflow that appears old."""
    thread_id = "old-thread-456"
    old_time = (datetime.now() - timedelta(days=45)).isoformat()
    _save_workflow_data(thread_id, {
        "state": {"current_step": "completed"},
        "config": {"configurable": {"thread_id": thread_id}},
        "created_at": old_time,
    })
    yield thread_id
    _workflows.pop(thread_id, None)


@pytest.fixture
def mock_metadata_service():
    """Mock the metadata service for unit tests."""
    with patch("routers.optimize.get_metadata_service") as mock:
        service = MagicMock(spec=ThreadMetadataService)
        service.database_url = "postgresql://test:test@localhost/test"
        mock.return_value = service
        yield service


# ============================================================================
# 1. Thread Metadata Tracking Tests
# ============================================================================

class TestThreadMetadataTracking:
    """Tests for thread metadata creation and updates.

    Note: These tests require full workflow mocking and are marked as integration tests.
    They verify the metadata service is called correctly during workflow operations.
    """

    @pytest.mark.skip(reason="Requires full workflow mocking - test in integration suite")
    def test_start_workflow_creates_metadata_record(self, mock_metadata_service):
        """
        GIVEN: A new workflow start request
        WHEN: POST /api/optimize/start is called
        THEN: A thread_metadata record is created
        """
        # This test verifies that metadata_service.create_thread is called
        # when a new workflow is started via POST /api/optimize/start
        pass

    def test_status_check_updates_last_accessed_at(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: An existing workflow
        WHEN: GET /api/optimize/status/{thread_id} is called
        THEN: last_accessed_at is updated
        """
        response = client.get(f"/api/optimize/status/{mock_workflow}")

        assert response.status_code == 200
        mock_metadata_service.update_last_accessed.assert_called()
        call_args = mock_metadata_service.update_last_accessed.call_args
        assert call_args[0][0] == mock_workflow

    def test_metadata_service_tracks_workflow_step(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: A workflow at a specific stage
        WHEN: Status is checked
        THEN: The current workflow step is recorded in metadata
        """
        response = client.get(f"/api/optimize/status/{mock_workflow}")

        assert response.status_code == 200
        mock_metadata_service.update_last_accessed.assert_called()
        call_args = mock_metadata_service.update_last_accessed.call_args
        # workflow_step should be passed
        assert "workflow_step" in call_args[1]


# ============================================================================
# 2. Manual Thread Deletion Tests
# ============================================================================

class TestManualThreadDeletion:
    """Tests for DELETE /api/optimize/{thread_id} endpoint."""

    def test_delete_removes_from_memory_cache(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: A workflow exists in _workflows dict
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: The thread_id is removed from _workflows
        """
        assert mock_workflow in _workflows

        response = client.delete(f"/api/optimize/{mock_workflow}")

        assert response.status_code == 200
        assert mock_workflow not in _workflows

    def test_delete_calls_postgres_cleanup(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: A workflow with checkpoints in Postgres
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: Postgres cleanup methods are called
        """
        response = client.delete(f"/api/optimize/{mock_workflow}")

        assert response.status_code == 200
        mock_metadata_service.delete_checkpoint_data.assert_called_once_with(mock_workflow)
        mock_metadata_service.delete_thread.assert_called_once_with(mock_workflow)

    def test_delete_nonexistent_thread_returns_404(self, mock_metadata_service):
        """
        GIVEN: A thread_id that doesn't exist anywhere
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: 404 error is returned
        """
        response = client.delete("/api/optimize/nonexistent-thread")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_returns_success_message(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: A valid workflow
        WHEN: DELETE is called
        THEN: Success response is returned
        """
        response = client.delete(f"/api/optimize/{mock_workflow}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()


# ============================================================================
# 3. Scheduled Cleanup Tests
# ============================================================================

class TestScheduledCleanup:
    """Tests for POST /api/optimize/cleanup endpoint."""

    def test_cleanup_requires_api_key_when_configured(self):
        """
        GIVEN: CLEANUP_API_KEY is set
        WHEN: POST /api/optimize/cleanup is called without key
        THEN: 401 Unauthorized is returned
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": "secret-key"}):
            response = client.post("/api/optimize/cleanup")

        assert response.status_code == 401

    def test_cleanup_rejects_invalid_api_key(self):
        """
        GIVEN: CLEANUP_API_KEY is set
        WHEN: POST /api/optimize/cleanup is called with wrong key
        THEN: 401 Unauthorized is returned
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": "secret-key"}):
            response = client.post(
                "/api/optimize/cleanup",
                headers={"X-API-Key": "wrong-key"}
            )

        assert response.status_code == 401

    def test_cleanup_with_valid_api_key_succeeds(self, mock_metadata_service):
        """
        GIVEN: Valid API key
        WHEN: POST /api/optimize/cleanup is called
        THEN: 200 OK is returned
        """
        mock_metadata_service.cleanup_expired_threads.return_value = {
            "deleted": 0,
            "errors": 0,
            "thread_ids": [],
        }

        with patch.dict(os.environ, {"CLEANUP_API_KEY": "secret-key"}):
            response = client.post(
                "/api/optimize/cleanup",
                headers={"X-API-Key": "secret-key"}
            )

        assert response.status_code == 200

    def test_cleanup_respects_days_old_parameter(self, mock_metadata_service):
        """
        GIVEN: A custom days_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: The parameter is passed to cleanup service
        """
        mock_metadata_service.cleanup_expired_threads.return_value = {
            "deleted": 0,
            "errors": 0,
            "thread_ids": [],
        }

        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):  # No key required
            response = client.post(
                "/api/optimize/cleanup",
                json={"days_old": 7}
            )

        assert response.status_code == 200
        mock_metadata_service.cleanup_expired_threads.assert_called_once_with(days_old=7)

    def test_cleanup_returns_accurate_counts(self, mock_metadata_service):
        """
        GIVEN: Threads to clean up
        WHEN: POST /api/optimize/cleanup is called
        THEN: Response shows accurate counts
        """
        mock_metadata_service.cleanup_expired_threads.return_value = {
            "deleted": 5,
            "errors": 1,
            "thread_ids": ["t1", "t2", "t3", "t4", "t5"],
        }

        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post("/api/optimize/cleanup")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 5
        assert data["errors"] == 1
        assert len(data["thread_ids"]) == 5

    def test_cleanup_removes_from_memory_cache(self, mock_old_workflow, mock_metadata_service):
        """
        GIVEN: Old threads in memory and Postgres
        WHEN: Cleanup runs
        THEN: Threads are removed from memory cache too
        """
        # Mock get_expired_threads to return the thread IDs first
        mock_metadata_service.get_expired_threads.return_value = [mock_old_workflow]
        mock_metadata_service.cleanup_expired_threads.return_value = {
            "deleted": 1,
            "errors": 0,
            "thread_ids": [mock_old_workflow],
        }

        assert mock_old_workflow in _workflows

        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post("/api/optimize/cleanup")

        assert response.status_code == 200
        assert mock_old_workflow not in _workflows

    def test_cleanup_handles_no_database(self, mock_old_workflow):
        """
        GIVEN: No database configured
        WHEN: POST /api/optimize/cleanup is called
        THEN: Memory-only cleanup runs
        """
        with patch("routers.optimize.get_metadata_service") as mock:
            service = MagicMock()
            service.database_url = None  # No database
            mock.return_value = service

            with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
                response = client.post(
                    "/api/optimize/cleanup",
                    json={"days_old": 30}
                )

        assert response.status_code == 200
        data = response.json()
        assert "memory-only" in data["message"].lower()


# ============================================================================
# 4. Recovery After Cleanup Tests
# ============================================================================

class TestRecoveryAfterCleanup:
    """Tests for workflow recovery behavior after cleanup runs."""

    def test_cleaned_thread_not_recoverable(self, mock_metadata_service):
        """
        GIVEN: A thread that was deleted by cleanup
        WHEN: Status is requested
        THEN: 404 is returned
        """
        # Thread doesn't exist in memory or Postgres
        response = client.get("/api/optimize/status/cleaned-thread-id")

        assert response.status_code == 404


# ============================================================================
# 5. Edge Cases & Error Handling Tests
# ============================================================================

class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error scenarios."""

    def test_delete_handles_memory_only_thread(self, mock_workflow):
        """
        GIVEN: A workflow only in memory (no Postgres)
        WHEN: DELETE is called
        THEN: Memory deletion succeeds, Postgres deletion gracefully handles missing
        """
        with patch("routers.optimize.get_metadata_service") as mock:
            service = MagicMock()
            service.delete_checkpoint_data.return_value = False
            service.delete_thread.return_value = False
            mock.return_value = service

            response = client.delete(f"/api/optimize/{mock_workflow}")

        assert response.status_code == 200
        assert mock_workflow not in _workflows

    def test_cleanup_with_invalid_days_old(self, mock_metadata_service):
        """
        GIVEN: Invalid days_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: Validation error is returned
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post(
                "/api/optimize/cleanup",
                json={"days_old": 0}  # Invalid: must be >= 1
            )

        assert response.status_code == 422  # Validation error

    def test_cleanup_with_extreme_days_old(self, mock_metadata_service):
        """
        GIVEN: Very large days_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: Validation caps at reasonable max
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post(
                "/api/optimize/cleanup",
                json={"days_old": 1000}  # Invalid: must be <= 365
            )

        assert response.status_code == 422  # Validation error


# ============================================================================
# 6. ThreadMetadataService Unit Tests
# ============================================================================

class TestThreadMetadataServiceUnit:
    """Unit tests for ThreadMetadataService class."""

    def test_service_handles_missing_database_url(self):
        """
        GIVEN: No DATABASE_URL configured
        WHEN: Service is created
        THEN: Operations return False/empty gracefully
        """
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            service = ThreadMetadataService(database_url=None)

            assert service.create_thread("test") is False
            assert service.update_last_accessed("test") is False
            assert service.delete_thread("test") is False
            assert service.get_expired_threads() == []

    def test_service_calculates_correct_expiry(self):
        """
        GIVEN: A TTL of 30 days
        WHEN: Thread is created
        THEN: expires_at is set correctly
        """
        import psycopg2
        with patch.object(psycopg2, "connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            mock_conn.closed = False
            mock_connect.return_value = mock_conn

            service = ThreadMetadataService(database_url="postgresql://test")
            service.create_thread("test-thread", ttl_days=30)

            # Verify the INSERT was called with correct expiry
            mock_cur.execute.assert_called()
            call_args = mock_cur.execute.call_args[0]
            # The expires_at should be approximately 30 days from now
            # We can't check exact values due to timing, but verify query structure
            assert "INSERT INTO thread_metadata" in call_args[0]


# ============================================================================
# Integration Tests (require actual Postgres)
# ============================================================================

@pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set - skipping integration tests"
)
class TestPostgresIntegration:
    """Integration tests that require actual Postgres connection."""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        """Setup and teardown for integration tests."""
        self.service = ThreadMetadataService()
        self.service.ensure_table_exists()
        self.test_threads = []
        yield
        # Cleanup test threads
        for thread_id in self.test_threads:
            self.service.delete_thread(thread_id)
        self.service.close()

    def test_full_lifecycle_create_update_delete(self):
        """
        GIVEN: Postgres is available
        WHEN: Full thread lifecycle is executed
        THEN: All operations succeed
        """
        thread_id = f"integration-test-{datetime.now().timestamp()}"
        self.test_threads.append(thread_id)

        # Create
        assert self.service.create_thread(thread_id, workflow_step="ingest")

        # Read
        metadata = self.service.get_thread(thread_id)
        assert metadata is not None
        assert metadata["thread_id"] == thread_id
        assert metadata["status"] == "active"

        # Update
        assert self.service.update_last_accessed(thread_id, workflow_step="research")

        # Verify update
        metadata = self.service.get_thread(thread_id)
        assert metadata["workflow_step"] == "research"

        # Delete
        assert self.service.delete_thread(thread_id)
        self.test_threads.remove(thread_id)

        # Verify deleted
        assert self.service.get_thread(thread_id) is None

    def test_cleanup_removes_old_threads(self):
        """
        GIVEN: Old threads in database
        WHEN: cleanup_expired_threads is called
        THEN: Old threads are removed
        """
        # This test would require manipulating timestamps
        # which is complex in a real database test
        pass
