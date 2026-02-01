"""Tests for ratings router and service.

Tests the anonymous user draft ratings functionality including:
- Submitting ratings
- Getting rating for a thread
- Rating history
- Rating summary statistics
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from services.ratings_service import RatingsService, DraftRating, RatingSummary


client = TestClient(app)

ANON_HEADERS = {"X-Anonymous-ID": "anon_test123456"}


class TestRatingsRouter:
    """Tests for ratings API endpoints."""

    @patch("routers.ratings.get_ratings_service")
    def test_submit_rating_success(self, mock_get_service):
        """Test submitting a new rating."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = DraftRating(
            id="rating-123",
            user_id="anon_test123456",
            thread_id="thread-abc",
            overall_quality=4,
            ats_satisfaction=True,
            would_send_as_is=True,
            feedback_text="Great resume!",
            job_title="Software Engineer",
            company_name="TechCorp",
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/ratings",
            json={
                "thread_id": "thread-abc",
                "overall_quality": 4,
                "ats_satisfaction": True,
                "would_send_as_is": True,
                "feedback_text": "Great resume!",
                "job_title": "Software Engineer",
                "company_name": "TechCorp",
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert "rating" in data
        assert data["rating"]["overall_quality"] == 4
        assert data["rating"]["ats_satisfaction"] is True

    @patch("routers.ratings.get_ratings_service")
    def test_submit_rating_minimal(self, mock_get_service):
        """Test submitting a rating with minimal fields."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = DraftRating(
            id="rating-456",
            user_id="anon_test123456",
            thread_id="thread-xyz",
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/ratings",
            json={"thread_id": "thread-xyz"},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200

    @patch("routers.ratings.get_ratings_service")
    def test_submit_rating_service_failure(self, mock_get_service):
        """Test submit returns 500 if service fails."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = None
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/ratings",
            json={"thread_id": "thread-xyz"},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 500

    def test_submit_rating_invalid_quality(self):
        """Test submit rejects quality outside 1-5 range."""
        response = client.post(
            "/api/ratings",
            json={"thread_id": "thread-xyz", "overall_quality": 6},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 422  # Validation error

    def test_submit_rating_missing_thread_id(self):
        """Test submit requires thread_id."""
        response = client.post(
            "/api/ratings",
            json={"overall_quality": 4},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 422

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_success(self, mock_get_service):
        """Test getting a rating by thread_id."""
        mock_service = MagicMock()
        mock_service.get_rating.return_value = DraftRating(
            id="rating-123",
            thread_id="thread-abc",
            overall_quality=5,
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/thread-abc")

        assert response.status_code == 200
        data = response.json()
        assert data["rating"]["overall_quality"] == 5

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_not_found(self, mock_get_service):
        """Test getting non-existent rating returns 404."""
        mock_service = MagicMock()
        mock_service.get_rating.return_value = None
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/nonexistent")

        assert response.status_code == 404

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_history_success(self, mock_get_service):
        """Test getting user's rating history."""
        mock_service = MagicMock()
        mock_service.get_user_ratings.return_value = [
            DraftRating(id="r1", thread_id="t1", overall_quality=4),
            DraftRating(id="r2", thread_id="t2", overall_quality=5),
        ]
        mock_service.get_rating_count.return_value = 2
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/history", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert len(data["ratings"]) == 2
        assert data["total_count"] == 2
        assert data["has_more"] is False

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_history_with_pagination(self, mock_get_service):
        """Test rating history with pagination."""
        mock_service = MagicMock()
        # Return 11 items to test has_more logic
        mock_service.get_user_ratings.return_value = [
            DraftRating(id=f"r{i}", thread_id=f"t{i}") for i in range(11)
        ]
        mock_service.get_rating_count.return_value = 20
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/ratings/history?limit=10&offset=0",
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["ratings"]) == 10  # Capped at limit
        assert data["has_more"] is True

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_history_empty(self, mock_get_service):
        """Test empty rating history."""
        mock_service = MagicMock()
        mock_service.get_user_ratings.return_value = []
        mock_service.get_rating_count.return_value = 0
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/history", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["ratings"] == []
        assert data["total_count"] == 0

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_summary_success(self, mock_get_service):
        """Test getting rating summary statistics."""
        mock_service = MagicMock()
        mock_service.get_rating_summary.return_value = RatingSummary(
            total_ratings=10,
            average_quality=4.2,
            would_send_rate=80.0,
            ats_satisfaction_rate=90.0,
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/summary", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_ratings"] == 10
        assert data["summary"]["average_quality"] == 4.2
        assert data["summary"]["would_send_rate"] == 80.0

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_summary_no_ratings(self, mock_get_service):
        """Test summary with no ratings."""
        mock_service = MagicMock()
        mock_service.get_rating_summary.return_value = RatingSummary(
            total_ratings=0,
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/ratings/summary", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_ratings"] == 0
        assert data["summary"]["average_quality"] is None


class TestRatingsService:
    """Tests for ratings service directly."""

    def test_service_creation(self):
        """Test service can be created."""
        service = RatingsService()
        assert service is not None

    def test_service_without_database(self):
        """Test service gracefully handles missing database."""
        service = RatingsService()
        service.database_url = None

        # Should return None without crashing
        result = service.get_rating("test-thread")
        assert result is None

    def test_service_get_user_ratings_no_db(self):
        """Test get_user_ratings returns empty list without DB."""
        service = RatingsService()
        service.database_url = None

        result = service.get_user_ratings("test-user")
        assert result == []

    def test_service_get_rating_summary_no_db(self):
        """Test get_rating_summary returns default without DB."""
        service = RatingsService()
        service.database_url = None

        result = service.get_rating_summary("test-user")
        assert result.total_ratings == 0

    def test_draft_rating_model(self):
        """Test DraftRating model structure."""
        rating = DraftRating(
            id="r-123",
            user_id="u-456",
            thread_id="t-789",
            overall_quality=4,
            ats_satisfaction=True,
            would_send_as_is=False,
            feedback_text="Needs more metrics",
            job_title="Engineer",
            company_name="TechCo",
        )

        assert rating.id == "r-123"
        assert rating.overall_quality == 4
        assert rating.feedback_text == "Needs more metrics"

    def test_draft_rating_minimal(self):
        """Test DraftRating with minimal fields."""
        rating = DraftRating(thread_id="t-123")

        assert rating.thread_id == "t-123"
        assert rating.overall_quality is None
        assert rating.feedback_text is None

    def test_rating_summary_model(self):
        """Test RatingSummary model structure."""
        summary = RatingSummary(
            total_ratings=50,
            average_quality=4.5,
            would_send_rate=85.5,
            ats_satisfaction_rate=92.0,
        )

        assert summary.total_ratings == 50
        assert summary.average_quality == 4.5

    def test_rating_summary_defaults(self):
        """Test RatingSummary with defaults."""
        summary = RatingSummary(total_ratings=0)

        assert summary.total_ratings == 0
        assert summary.average_quality is None
        assert summary.would_send_rate is None


class TestAnonymousIdHandling:
    """Tests for anonymous ID handling in ratings router."""

    @patch("routers.ratings.get_ratings_service")
    def test_uses_provided_anonymous_id(self, mock_get_service):
        """Test router uses X-Anonymous-ID header."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = DraftRating(
            id="r-1",
            thread_id="t-1",
        )
        mock_get_service.return_value = mock_service

        client.post(
            "/api/ratings",
            json={"thread_id": "t-1"},
            headers={"X-Anonymous-ID": "anon_myid123"},
        )

        # Check user_id was passed correctly
        call_args = mock_service.submit_rating.call_args
        assert call_args[1]["user_id"] == "anon_myid123"

    @patch("routers.ratings.get_ratings_service")
    def test_generates_id_when_missing(self, mock_get_service):
        """Test router generates ID when header missing."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = DraftRating(
            id="r-1",
            thread_id="t-1",
        )
        mock_get_service.return_value = mock_service

        client.post(
            "/api/ratings",
            json={"thread_id": "t-1"},
            # No X-Anonymous-ID header
        )

        call_args = mock_service.submit_rating.call_args
        user_id = call_args[1]["user_id"]
        assert user_id.startswith("anon_")

    @patch("routers.ratings.get_ratings_service")
    def test_get_rating_no_auth_required(self, mock_get_service):
        """Test getting rating by thread doesn't require auth."""
        mock_service = MagicMock()
        mock_service.get_rating.return_value = DraftRating(
            id="r-1",
            thread_id="t-1",
        )
        mock_get_service.return_value = mock_service

        # No headers at all
        response = client.get("/api/ratings/t-1")

        assert response.status_code == 200


class TestRatingValidation:
    """Tests for rating data validation."""

    def test_quality_range_valid(self):
        """Test valid quality values 1-5 are accepted."""
        for quality in [1, 2, 3, 4, 5]:
            rating = DraftRating(thread_id="t-1", overall_quality=quality)
            assert rating.overall_quality == quality

    def test_quality_none_allowed(self):
        """Test None quality is allowed."""
        rating = DraftRating(thread_id="t-1", overall_quality=None)
        assert rating.overall_quality is None

    @patch("routers.ratings.get_ratings_service")
    def test_boolean_fields(self, mock_get_service):
        """Test boolean fields are handled correctly."""
        mock_service = MagicMock()
        mock_service.submit_rating.return_value = DraftRating(
            id="r-1",
            thread_id="t-1",
            ats_satisfaction=False,
            would_send_as_is=True,
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/ratings",
            json={
                "thread_id": "t-1",
                "ats_satisfaction": False,
                "would_send_as_is": True,
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"]["ats_satisfaction"] is False
        assert data["rating"]["would_send_as_is"] is True
