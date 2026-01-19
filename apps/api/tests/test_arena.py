"""Tests for arena A/B comparison functionality."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Set test admin token
os.environ["ARENA_ADMIN_TOKEN"] = "test-admin-token"

from main import app
from services.arena_service import ArenaService, ArenaComparison, PreferenceRating, VariantMetrics


client = TestClient(app)

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


class TestAdminAuth:
    """Test admin authentication."""

    def test_verify_token_valid(self):
        """Test valid admin token."""
        response = client.get("/api/arena/verify", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        assert response.json()["valid"] is True

    def test_verify_token_missing(self):
        """Test missing admin token."""
        response = client.get("/api/arena/verify")
        assert response.status_code == 401

    def test_verify_token_invalid(self):
        """Test invalid admin token."""
        response = client.get("/api/arena/verify", headers={"X-Admin-Token": "wrong"})
        assert response.status_code == 401


class TestArenaStart:
    """Test starting arena comparisons."""

    @patch("routers.arena._run_variant_workflow")
    @patch("routers.arena.create_initial_state")
    def test_start_comparison(self, mock_create_state, mock_run):
        """Test starting a comparison creates two workflows."""
        mock_create_state.return_value = {"current_step": "ingest", "created_at": "2025-01-01"}
        mock_run.return_value = None

        response = client.post(
            "/api/arena/start",
            json={
                "resume_text": "Test resume",
                "job_text": "Test job",
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert "arena_id" in data
        assert "variant_a_thread_id" in data
        assert "variant_b_thread_id" in data
        assert data["variant_a_thread_id"] != data["variant_b_thread_id"]

    def test_start_comparison_requires_auth(self):
        """Test starting comparison requires admin auth."""
        response = client.post(
            "/api/arena/start",
            json={"resume_text": "Test", "job_text": "Test"},
        )
        assert response.status_code == 401


class TestArenaStatus:
    """Test arena status endpoint."""

    def test_get_status_both_running(self):
        """Test status when both variants are running."""
        # Skip - requires complex async mock setup
        pytest.skip("Requires complex async mock setup")

    def test_get_status_not_found(self):
        """Test status for non-existent arena."""
        with patch("routers.arena.get_arena_service") as mock:
            mock.return_value.get_comparison.return_value = None
            response = client.get("/api/arena/nonexistent/status", headers=ADMIN_HEADERS)
            assert response.status_code == 404


class TestRating:
    """Test preference rating functionality."""

    @patch("routers.arena.get_arena_service")
    def test_submit_rating_valid(self, mock_service):
        """Test submitting a valid rating."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.save_rating.return_value = PreferenceRating(
            rating_id="rating-1",
            arena_id="test-arena",
            step="research",
            aspect="quality",
            preference="A",
        )

        response = client.post(
            "/api/arena/test-arena/rate",
            json={
                "step": "research",
                "aspect": "quality",
                "preference": "A",
                "reason": "Better analysis",
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("routers.arena.get_arena_service")
    def test_submit_rating_invalid_preference(self, mock_service):
        """Test submitting rating with invalid preference."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )

        response = client.post(
            "/api/arena/test-arena/rate",
            json={
                "step": "research",
                "aspect": "quality",
                "preference": "C",  # Invalid
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 400


class TestArenaService:
    """Test arena service directly."""

    def test_service_creation(self):
        """Test service can be created."""
        service = ArenaService()
        assert service is not None

    def test_create_comparison_without_db(self):
        """Test creating comparison without database."""
        service = ArenaService()
        service.database_url = None  # No database

        comparison = service.create_comparison(
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
            input_data={"test": "data"},
        )

        assert comparison.arena_id is not None
        assert comparison.variant_a_thread_id == "thread-a"
        assert comparison.variant_b_thread_id == "thread-b"
        assert comparison.status == "running"


class TestListComparisons:
    """Test listing comparisons."""

    @patch("routers.arena.get_arena_service")
    def test_list_comparisons(self, mock_service):
        """Test listing comparisons."""
        mock_service.return_value.list_comparisons.return_value = [
            ArenaComparison(
                arena_id="arena-1",
                variant_a_thread_id="a1",
                variant_b_thread_id="b1",
            ),
            ArenaComparison(
                arena_id="arena-2",
                variant_a_thread_id="a2",
                variant_b_thread_id="b2",
            ),
        ]

        response = client.get("/api/arena/comparisons", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "comparisons" in data
        assert len(data["comparisons"]) == 2

    def test_list_comparisons_requires_auth(self):
        """Test listing requires auth."""
        response = client.get("/api/arena/comparisons")
        assert response.status_code == 401


class TestAnalytics:
    """Test analytics functionality."""

    def test_analytics_empty(self):
        """Test analytics with no data."""
        response = client.get("/api/arena/analytics", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "total_comparisons" in data
        assert "total_ratings" in data
        assert "variant_a_wins" in data
        assert "variant_b_wins" in data
        assert "win_rate_a" in data
        assert "win_rate_b" in data

    def test_analytics_requires_auth(self):
        """Test analytics requires auth."""
        response = client.get("/api/arena/analytics")
        assert response.status_code == 401

    def test_analytics_with_ratings(self):
        """Test analytics counts ratings correctly."""
        import services.arena_service as arena_module
        from services.arena_service import ArenaService, PreferenceRating

        # Reset singleton and disable DB to ensure test isolation
        arena_module._arena_service = None
        service = ArenaService()
        service.database_url = None  # Force in-memory storage
        arena_module._arena_service = service

        # Create a comparison
        comparison = service.create_comparison(
            variant_a_thread_id="a1",
            variant_b_thread_id="b1",
            input_data={},
        )

        # Add ratings
        service.save_rating(PreferenceRating(
            arena_id=comparison.arena_id,
            step="research",
            aspect="quality",
            preference="A",
        ))
        service.save_rating(PreferenceRating(
            arena_id=comparison.arena_id,
            step="drafting",
            aspect="quality",
            preference="B",
        ))
        service.save_rating(PreferenceRating(
            arena_id=comparison.arena_id,
            step="export",
            aspect="speed",
            preference="tie",
        ))

        response = client.get("/api/arena/analytics", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        data = response.json()

        assert data["total_comparisons"] == 1
        assert data["total_ratings"] == 3
        assert data["variant_a_wins"] == 1
        assert data["variant_b_wins"] == 1
        assert data["ties"] == 1
        assert "by_step" in data
        assert "by_aspect" in data


class TestMetrics:
    """Test metrics functionality."""

    @patch("routers.arena.get_arena_service")
    def test_submit_metrics(self, mock_service):
        """Test submitting metrics for a variant."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )

        response = client.post(
            "/api/arena/test-arena/metrics",
            json={
                "variant": "A",
                "total_duration_ms": 5000,
                "total_llm_calls": 3,
                "total_input_tokens": 1000,
                "total_output_tokens": 500,
                "ats_score": 85,
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("routers.arena.get_arena_service")
    def test_get_metrics(self, mock_service):
        """Test getting metrics for a comparison."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.get_metrics.return_value = {
            "A": VariantMetrics(
                variant="A",
                thread_id="thread-a",
                total_duration_ms=5000,
                total_llm_calls=3,
            ),
        }

        response = client.get("/api/arena/test-arena/metrics", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "A" in data
        assert data["A"]["total_duration_ms"] == 5000

    def test_metrics_requires_auth(self):
        """Test metrics requires auth."""
        response = client.get("/api/arena/test-arena/metrics")
        assert response.status_code == 401

    def test_service_metrics_storage(self):
        """Test service metrics storage in memory."""
        service = ArenaService()
        service.database_url = None

        # Create comparison first
        comparison = service.create_comparison(
            variant_a_thread_id="a1",
            variant_b_thread_id="b1",
            input_data={},
        )

        # Save metrics
        metrics = VariantMetrics(
            variant="A",
            thread_id="a1",
            total_duration_ms=3000,
            total_llm_calls=2,
            total_input_tokens=500,
            total_output_tokens=250,
            ats_score=90,
        )
        service.save_metrics(comparison.arena_id, "A", metrics)

        # Get metrics
        result = service.get_metrics(comparison.arena_id)
        assert "A" in result
        assert result["A"].total_duration_ms == 3000
        assert result["A"].ats_score == 90


class TestRatingValidation:
    """Test rating validation for step/aspect fields."""

    @patch("routers.arena.get_arena_service")
    def test_invalid_step(self, mock_service):
        """Test submitting rating with invalid step."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )

        response = client.post(
            "/api/arena/test-arena/rate",
            json={
                "step": "invalid_step",
                "aspect": "quality",
                "preference": "A",
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 400
        assert "Step must be one of" in response.json()["detail"]

    @patch("routers.arena.get_arena_service")
    def test_invalid_aspect(self, mock_service):
        """Test submitting rating with invalid aspect."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )

        response = client.post(
            "/api/arena/test-arena/rate",
            json={
                "step": "research",
                "aspect": "invalid_aspect",
                "preference": "A",
            },
            headers=ADMIN_HEADERS,
        )

        assert response.status_code == 400
        assert "Aspect must be one of" in response.json()["detail"]


class TestDeleteComparison:
    """Test comparison deletion."""

    @patch("routers.arena.get_arena_service")
    @patch("routers.arena._workflows", {})
    def test_delete_comparison(self, mock_service):
        """Test deleting a comparison."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.cleanup_comparison.return_value = True

        response = client.delete("/api/arena/test-arena", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_comparison_requires_auth(self):
        """Test deletion requires auth."""
        response = client.delete("/api/arena/test-arena")
        assert response.status_code == 401


class TestExport:
    """Test export functionality."""

    @patch("routers.arena.get_arena_service")
    def test_export_comparison_json(self, mock_service):
        """Test exporting comparison as JSON."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
            created_at="2025-01-01T00:00:00",
        )
        mock_service.return_value.get_ratings.return_value = []
        mock_service.return_value.get_metrics.return_value = {}

        response = client.get("/api/arena/test-arena/export?format=json", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["arena_id"] == "test-arena"
        assert "ratings" in data
        assert "metrics" in data

    @patch("routers.arena.get_arena_service")
    def test_export_comparison_csv(self, mock_service):
        """Test exporting comparison as CSV."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.get_ratings.return_value = [
            PreferenceRating(
                rating_id="r1",
                arena_id="test-arena",
                step="research",
                aspect="quality",
                preference="A",
            )
        ]
        mock_service.return_value.get_metrics.return_value = {}

        response = client.get("/api/arena/test-arena/export?format=csv", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "research" in response.text
        assert "quality" in response.text

    def test_export_analytics_json(self):
        """Test exporting analytics as JSON."""
        response = client.get("/api/arena/export/analytics?format=json", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "total_comparisons" in data
        assert "win_rate_a" in data

    def test_export_analytics_csv(self):
        """Test exporting analytics as CSV."""
        response = client.get("/api/arena/export/analytics?format=csv", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "Total Comparisons" in response.text

    def test_export_requires_auth(self):
        """Test export requires auth."""
        response = client.get("/api/arena/test-arena/export")
        assert response.status_code == 401

    def test_export_invalid_format(self):
        """Test export rejects invalid format."""
        response = client.get("/api/arena/test-arena/export?format=xml", headers=ADMIN_HEADERS)
        assert response.status_code == 400


class TestSSEToken:
    """Test SSE short-lived token functionality."""

    @patch("routers.arena.get_arena_service")
    def test_create_sse_token(self, mock_service):
        """Test creating a short-lived SSE token."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.create_sse_token.return_value = "short-lived-token"
        mock_service.return_value.SSE_TOKEN_TTL_SECONDS = 300

        response = client.post("/api/arena/test-arena/sse-token", headers=ADMIN_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "expires_in_seconds" in data

    def test_create_sse_token_requires_auth(self):
        """Test SSE token creation requires admin auth."""
        response = client.post("/api/arena/test-arena/sse-token")
        assert response.status_code == 401

    def test_service_sse_token_lifecycle(self):
        """Test SSE token creation, validation, and single-use behavior."""
        service = ArenaService()

        # Create token
        token = service.create_sse_token("arena-123")
        assert token is not None
        assert len(token) > 20  # Should be reasonably long

        # Validate token - should succeed
        assert service.validate_sse_token(token, "arena-123") is True

        # Second validation should fail (single-use)
        assert service.validate_sse_token(token, "arena-123") is False

        # Create new token for arena_id mismatch test
        token2 = service.create_sse_token("arena-456")
        # Wrong arena_id should fail
        assert service.validate_sse_token(token2, "other-arena") is False

        # Wrong token should fail
        assert service.validate_sse_token("wrong-token", "arena-123") is False

    def test_service_sse_token_expiration(self):
        """Test SSE token expires after TTL."""
        import time as time_module

        service = ArenaService()
        service.SSE_TOKEN_TTL_SECONDS = 0.1  # 100ms for testing

        token = service.create_sse_token("arena-123")
        assert service.validate_sse_token(token, "arena-123") is True

        # Wait for expiration
        time_module.sleep(0.2)
        assert service.validate_sse_token(token, "arena-123") is False


class TestStream:
    """Test SSE streaming functionality."""

    def test_stream_requires_auth(self):
        """Test stream endpoint requires token query param."""
        response = client.get("/api/arena/test-arena/stream")
        assert response.status_code == 401

    def test_stream_invalid_token(self):
        """Test stream rejects invalid token."""
        response = client.get("/api/arena/test-arena/stream?token=wrong")
        assert response.status_code == 401

    def test_stream_not_found(self):
        """Test stream returns 401 for invalid token (arena check comes after auth)."""
        response = client.get("/api/arena/nonexistent/stream?token=invalid-token")
        assert response.status_code == 401

    @patch("routers.arena.get_arena_service")
    def test_stream_accepts_sse_token(self, mock_service):
        """Test stream accepts short-lived SSE token."""
        mock_service.return_value.get_comparison.return_value = ArenaComparison(
            arena_id="test-arena",
            variant_a_thread_id="thread-a",
            variant_b_thread_id="thread-b",
        )
        mock_service.return_value.validate_sse_token.return_value = True

        # Should not return 401 (may return 200 or start streaming)
        response = client.get("/api/arena/test-arena/stream?token=short-lived-token")
        assert response.status_code != 401
