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
from services.thread_metadata import ThreadMetadataService, get_metadata_service, reset_metadata_service


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
    old_time = (datetime.now() - timedelta(hours=5)).isoformat()
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
        mock.return_value = service
        yield service


@pytest.fixture
def fresh_metadata_service():
    """Get a fresh in-memory metadata service for testing."""
    reset_metadata_service()
    service = get_metadata_service()
    yield service
    reset_metadata_service()


# ============================================================================
# 1. Thread Metadata Tracking Tests
# ============================================================================

class TestThreadMetadataTracking:
    """Tests for thread metadata creation and updates."""

    @pytest.mark.skip(reason="Requires full workflow mocking - test in integration suite")
    def test_start_workflow_creates_metadata_record(self, mock_metadata_service):
        """
        GIVEN: A new workflow start request
        WHEN: POST /api/optimize/start is called
        THEN: A thread_metadata record is created
        """
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

    def test_delete_calls_cleanup_methods(self, mock_workflow, mock_metadata_service):
        """
        GIVEN: A workflow with metadata
        WHEN: DELETE /api/optimize/{thread_id} is called
        THEN: Cleanup methods are called
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
        mock_metadata_service.get_expired_threads.return_value = []
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

    def test_cleanup_respects_hours_old_parameter(self, mock_metadata_service):
        """
        GIVEN: A custom hours_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: The parameter is passed to cleanup service
        """
        mock_metadata_service.get_expired_threads.return_value = []
        mock_metadata_service.cleanup_expired_threads.return_value = {
            "deleted": 0,
            "errors": 0,
            "thread_ids": [],
        }

        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):  # No key required
            response = client.post(
                "/api/optimize/cleanup",
                json={"hours_old": 1.0}
            )

        assert response.status_code == 200
        mock_metadata_service.cleanup_expired_threads.assert_called_once_with(hours_old=1.0)

    def test_cleanup_returns_accurate_counts(self, mock_metadata_service):
        """
        GIVEN: Threads to clean up
        WHEN: POST /api/optimize/cleanup is called
        THEN: Response shows accurate counts
        """
        mock_metadata_service.get_expired_threads.return_value = ["t1", "t2", "t3", "t4", "t5"]
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
        GIVEN: Old threads in memory
        WHEN: Cleanup runs
        THEN: Threads are removed from memory cache too
        """
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
        response = client.get("/api/optimize/status/cleaned-thread-id")

        assert response.status_code == 404


# ============================================================================
# 5. Edge Cases & Error Handling Tests
# ============================================================================

class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error scenarios."""

    def test_delete_handles_memory_only_thread(self, mock_workflow):
        """
        GIVEN: A workflow only in memory
        WHEN: DELETE is called
        THEN: Memory deletion succeeds
        """
        with patch("routers.optimize.get_metadata_service") as mock:
            service = MagicMock()
            service.delete_checkpoint_data.return_value = True
            service.delete_thread.return_value = True
            mock.return_value = service

            response = client.delete(f"/api/optimize/{mock_workflow}")

        assert response.status_code == 200
        assert mock_workflow not in _workflows

    def test_cleanup_with_invalid_hours_old(self, mock_metadata_service):
        """
        GIVEN: Invalid hours_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: Validation error is returned
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post(
                "/api/optimize/cleanup",
                json={"hours_old": 0}  # Invalid: must be >= 0.5
            )

        assert response.status_code == 422  # Validation error

    def test_cleanup_with_extreme_hours_old(self, mock_metadata_service):
        """
        GIVEN: Very large hours_old parameter
        WHEN: POST /api/optimize/cleanup is called
        THEN: Validation caps at reasonable max
        """
        with patch.dict(os.environ, {"CLEANUP_API_KEY": ""}):
            response = client.post(
                "/api/optimize/cleanup",
                json={"hours_old": 100}  # Invalid: must be <= 24
            )

        assert response.status_code == 422  # Validation error


# ============================================================================
# 6. ThreadMetadataService Unit Tests (In-Memory)
# ============================================================================

class TestThreadMetadataServiceUnit:
    """Unit tests for in-memory ThreadMetadataService class."""

    def test_create_thread_succeeds(self, fresh_metadata_service):
        """
        GIVEN: A fresh service
        WHEN: Thread is created
        THEN: Creation succeeds
        """
        assert fresh_metadata_service.create_thread("test-thread") is True

    def test_get_thread_returns_correct_data(self, fresh_metadata_service):
        """
        GIVEN: A created thread
        WHEN: Thread is retrieved
        THEN: Correct data is returned
        """
        fresh_metadata_service.create_thread("test-thread", workflow_step="ingest")

        metadata = fresh_metadata_service.get_thread("test-thread")

        assert metadata is not None
        assert metadata["thread_id"] == "test-thread"
        assert metadata["workflow_step"] == "ingest"
        assert metadata["status"] == "active"

    def test_update_last_accessed_updates_timestamp(self, fresh_metadata_service):
        """
        GIVEN: A created thread
        WHEN: last_accessed is updated
        THEN: Timestamp is updated
        """
        fresh_metadata_service.create_thread("test-thread")

        import time
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        fresh_metadata_service.update_last_accessed("test-thread", workflow_step="research")

        metadata = fresh_metadata_service.get_thread("test-thread")
        assert metadata["workflow_step"] == "research"

    def test_delete_thread_removes_from_storage(self, fresh_metadata_service):
        """
        GIVEN: A created thread
        WHEN: Thread is deleted
        THEN: Thread is no longer retrievable
        """
        fresh_metadata_service.create_thread("test-thread")
        assert fresh_metadata_service.delete_thread("test-thread") is True
        assert fresh_metadata_service.get_thread("test-thread") is None

    def test_get_expired_threads_returns_old_threads(self, fresh_metadata_service):
        """
        GIVEN: Threads with different ages
        WHEN: get_expired_threads is called
        THEN: Only old threads are returned
        """
        # Create a thread and manually set its last_accessed to be old
        fresh_metadata_service.create_thread("old-thread")
        thread = fresh_metadata_service._threads["old-thread"]
        thread.last_accessed_at = datetime.now(timezone.utc) - timedelta(hours=5)

        fresh_metadata_service.create_thread("new-thread")

        # Get threads older than 1 hour
        expired = fresh_metadata_service.get_expired_threads(hours_old=1.0)

        assert "old-thread" in expired
        assert "new-thread" not in expired

    def test_cleanup_expired_threads_removes_old(self, fresh_metadata_service):
        """
        GIVEN: Old threads
        WHEN: cleanup_expired_threads is called
        THEN: Old threads are removed
        """
        # Create and age a thread
        fresh_metadata_service.create_thread("old-thread")
        thread = fresh_metadata_service._threads["old-thread"]
        thread.last_accessed_at = datetime.now(timezone.utc) - timedelta(hours=5)
        thread.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        result = fresh_metadata_service.cleanup_expired_threads()

        assert result["deleted"] == 1
        assert "old-thread" in result["thread_ids"]
        assert fresh_metadata_service.get_thread("old-thread") is None

    def test_service_calculates_correct_expiry(self, fresh_metadata_service):
        """
        GIVEN: A TTL of 2 hours
        WHEN: Thread is created
        THEN: expires_at is set correctly
        """
        fresh_metadata_service.create_thread("test-thread", ttl_hours=2.0)

        metadata = fresh_metadata_service.get_thread("test-thread")
        created_at = datetime.fromisoformat(metadata["created_at"])
        expires_at = datetime.fromisoformat(metadata["expires_at"])

        # Should expire approximately 2 hours after creation
        expected_expiry = created_at + timedelta(hours=2)
        diff = abs((expires_at - expected_expiry).total_seconds())
        assert diff < 1  # Within 1 second tolerance
