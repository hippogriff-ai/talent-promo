"""Tests for migration service and endpoint.

Test coverage:
- MigrationService.migrate_anonymous_data: preferences, events, ratings migration
- MigrationService._migrate_preferences: conflict resolution (server wins)
- MigrationService._migrate_events: event type filtering, partial failures
- MigrationService._migrate_ratings: duplicate detection, user_id assignment
- MigrationService._cleanup_anonymous_data: anonymous data removal
- POST /api/auth/migrate: authenticated migration endpoint
"""

import pytest
from unittest.mock import MagicMock, patch

from services.migration_service import (
    AnonymousData,
    MigrationResult,
    MigrationService,
    get_migration_service,
)
from services.preferences_service import UserPreferences, PreferenceEvent
from services.ratings_service import DraftRating


# ==================== MigrationService Unit Tests ====================


class TestMigrationServiceInit:
    """Tests for MigrationService initialization."""

    def test_init_with_no_services(self):
        """Service initializes with lazy-loaded services."""
        service = MigrationService()
        assert service._preferences_service is None
        assert service._ratings_service is None

    def test_init_with_provided_services(self):
        """Service accepts pre-configured services."""
        mock_prefs = MagicMock()
        mock_ratings = MagicMock()
        service = MigrationService(
            preferences_service=mock_prefs,
            ratings_service=mock_ratings,
        )
        assert service._preferences_service is mock_prefs
        assert service._ratings_service is mock_ratings

    def test_preferences_service_lazy_load(self):
        """Preferences service is lazy-loaded on first access."""
        service = MigrationService()
        with patch("services.migration_service.get_preferences_service") as mock_get:
            mock_get.return_value = MagicMock()
            _ = service.preferences_service
            mock_get.assert_called_once()

    def test_ratings_service_lazy_load(self):
        """Ratings service is lazy-loaded on first access."""
        service = MigrationService()
        with patch("services.migration_service.get_ratings_service") as mock_get:
            mock_get.return_value = MagicMock()
            _ = service.ratings_service
            mock_get.assert_called_once()


class TestMigratePreferences:
    """Tests for preference migration logic."""

    def test_migrate_preferences_when_user_has_none(self):
        """Preferences migrate when user has no existing preferences."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = None
        mock_prefs.get_or_create_preferences.return_value = UserPreferences(user_id="user-1")
        mock_prefs.update_preferences.return_value = UserPreferences(
            user_id="user-1", tone="professional"
        )

        service = MigrationService(preferences_service=mock_prefs)
        result = service._migrate_preferences("user-1", {"tone": "professional"})

        assert result is True
        mock_prefs.get_or_create_preferences.assert_called_once_with("user-1")
        mock_prefs.update_preferences.assert_called_once()

    def test_migrate_preferences_skipped_when_user_has_existing(self):
        """Preferences NOT migrated when user already has preferences (server wins)."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = UserPreferences(
            user_id="user-1", tone="formal"
        )

        service = MigrationService(preferences_service=mock_prefs)
        result = service._migrate_preferences("user-1", {"tone": "casual"})

        assert result is False
        mock_prefs.update_preferences.assert_not_called()

    def test_migrate_preferences_filters_invalid_fields(self):
        """Only valid preference fields are migrated."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = None
        mock_prefs.get_or_create_preferences.return_value = UserPreferences(user_id="user-1")
        mock_prefs.update_preferences.return_value = UserPreferences(user_id="user-1")

        service = MigrationService(preferences_service=mock_prefs)
        service._migrate_preferences("user-1", {
            "tone": "professional",
            "invalid_field": "should_be_ignored",
            "another_invalid": 123,
        })

        call_args = mock_prefs.update_preferences.call_args
        assert "invalid_field" not in call_args[0][1]
        assert "another_invalid" not in call_args[0][1]
        assert "tone" in call_args[0][1]

    def test_migrate_preferences_empty_returns_false(self):
        """Empty preferences dict returns False without updating."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = None

        service = MigrationService(preferences_service=mock_prefs)
        result = service._migrate_preferences("user-1", {})

        assert result is False
        mock_prefs.update_preferences.assert_not_called()

    def test_migrate_preferences_none_values_filtered(self):
        """None values in preferences are filtered out."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = None
        mock_prefs.get_or_create_preferences.return_value = UserPreferences(user_id="user-1")
        mock_prefs.update_preferences.return_value = UserPreferences(user_id="user-1")

        service = MigrationService(preferences_service=mock_prefs)
        service._migrate_preferences("user-1", {
            "tone": "professional",
            "structure": None,
        })

        call_args = mock_prefs.update_preferences.call_args
        assert "structure" not in call_args[0][1]


class TestMigrateEvents:
    """Tests for event migration logic."""

    def test_migrate_events_valid_types(self):
        """Valid event types (edit, suggestion_accept, suggestion_reject) are migrated."""
        mock_prefs = MagicMock()
        mock_prefs.record_event.return_value = True

        service = MigrationService(preferences_service=mock_prefs)
        events = [
            {"event_type": "edit", "event_data": {"field": "summary"}},
            {"event_type": "suggestion_accept", "event_data": {}},
            {"event_type": "suggestion_reject", "event_data": {}},
        ]
        result = service._migrate_events("user-1", events)

        assert result == 3
        assert mock_prefs.record_event.call_count == 3

    def test_migrate_events_filters_invalid_types(self):
        """Invalid event types are filtered out."""
        mock_prefs = MagicMock()
        mock_prefs.record_event.return_value = True

        service = MigrationService(preferences_service=mock_prefs)
        events = [
            {"event_type": "edit", "event_data": {}},
            {"event_type": "invalid_type", "event_data": {}},
            {"event_type": "page_view", "event_data": {}},
        ]
        result = service._migrate_events("user-1", events)

        assert result == 1
        mock_prefs.record_event.call_count == 1

    def test_migrate_events_partial_failure(self):
        """Partial failures are counted correctly."""
        mock_prefs = MagicMock()
        mock_prefs.record_event.side_effect = [True, False, True]

        service = MigrationService(preferences_service=mock_prefs)
        events = [
            {"event_type": "edit", "event_data": {}},
            {"event_type": "edit", "event_data": {}},
            {"event_type": "edit", "event_data": {}},
        ]
        result = service._migrate_events("user-1", events)

        assert result == 2

    def test_migrate_events_exception_handling(self):
        """Exceptions during event migration are handled gracefully."""
        mock_prefs = MagicMock()
        mock_prefs.record_event.side_effect = [True, Exception("DB error"), True]

        service = MigrationService(preferences_service=mock_prefs)
        events = [
            {"event_type": "edit", "event_data": {}},
            {"event_type": "edit", "event_data": {}},
            {"event_type": "edit", "event_data": {}},
        ]
        result = service._migrate_events("user-1", events)

        assert result == 2

    def test_migrate_events_empty_list(self):
        """Empty events list returns 0."""
        service = MigrationService(preferences_service=MagicMock())
        result = service._migrate_events("user-1", [])
        assert result == 0


class TestMigrateRatings:
    """Tests for rating migration logic."""

    def test_migrate_ratings_success(self):
        """Ratings without existing user ratings are migrated."""
        mock_ratings = MagicMock()
        mock_ratings.get_rating.return_value = None
        mock_ratings.submit_rating.return_value = True

        service = MigrationService(ratings_service=mock_ratings)
        ratings = [
            {"thread_id": "thread-1", "overall_quality": 5},
            {"thread_id": "thread-2", "overall_quality": 4},
        ]
        result = service._migrate_ratings("user-1", ratings)

        assert result == 2
        assert mock_ratings.submit_rating.call_count == 2

    def test_migrate_ratings_skips_existing_user_ratings(self):
        """Ratings with existing user ratings are skipped."""
        mock_ratings = MagicMock()
        existing = MagicMock()
        existing.user_id = "other-user"
        mock_ratings.get_rating.return_value = existing

        service = MigrationService(ratings_service=mock_ratings)
        ratings = [{"thread_id": "thread-1", "overall_quality": 5}]
        result = service._migrate_ratings("user-1", ratings)

        assert result == 0
        mock_ratings.submit_rating.assert_not_called()

    def test_migrate_ratings_skips_missing_thread_id(self):
        """Ratings without thread_id are skipped."""
        mock_ratings = MagicMock()

        service = MigrationService(ratings_service=mock_ratings)
        ratings = [{"overall_quality": 5}]  # No thread_id
        result = service._migrate_ratings("user-1", ratings)

        assert result == 0

    def test_migrate_ratings_exception_handling(self):
        """Exceptions during rating migration are handled gracefully."""
        mock_ratings = MagicMock()
        mock_ratings.get_rating.side_effect = [None, Exception("DB error"), None]
        mock_ratings.submit_rating.return_value = True

        service = MigrationService(ratings_service=mock_ratings)
        ratings = [
            {"thread_id": "thread-1", "overall_quality": 5},
            {"thread_id": "thread-2", "overall_quality": 4},
            {"thread_id": "thread-3", "overall_quality": 3},
        ]
        result = service._migrate_ratings("user-1", ratings)

        assert result == 2


class TestCleanupAnonymousData:
    """Tests for anonymous data cleanup."""

    def test_cleanup_deletes_anonymous_preferences(self):
        """Anonymous preferences are deleted after migration."""
        mock_prefs = MagicMock()

        service = MigrationService(preferences_service=mock_prefs)
        service._cleanup_anonymous_data("anon-123")

        mock_prefs.delete_preferences.assert_called_once_with("anon:anon-123")

    def test_cleanup_handles_delete_failure(self):
        """Cleanup continues even if delete fails."""
        mock_prefs = MagicMock()
        mock_prefs.delete_preferences.side_effect = Exception("Delete failed")

        service = MigrationService(preferences_service=mock_prefs)
        # Should not raise
        service._cleanup_anonymous_data("anon-123")


class TestMigrateAnonymousData:
    """Tests for the main migration orchestration."""

    def test_migrate_all_data_types(self):
        """All data types (preferences, events, ratings) are migrated."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.return_value = None
        mock_prefs.get_or_create_preferences.return_value = UserPreferences(user_id="user-1")
        mock_prefs.update_preferences.return_value = UserPreferences(user_id="user-1")
        mock_prefs.record_event.return_value = True

        mock_ratings = MagicMock()
        mock_ratings.get_rating.return_value = None
        mock_ratings.submit_rating.return_value = True

        service = MigrationService(
            preferences_service=mock_prefs,
            ratings_service=mock_ratings,
        )

        data = AnonymousData(
            anonymous_id="anon-123",
            preferences={"tone": "professional"},
            events=[{"event_type": "edit", "event_data": {}}],
            ratings=[{"thread_id": "thread-1", "overall_quality": 5}],
        )

        result = service.migrate_anonymous_data("user-1", data)

        assert result.preferences_migrated is True
        assert result.events_migrated == 1
        assert result.ratings_migrated == 1
        assert len(result.errors) == 0

    def test_migrate_handles_category_level_failures(self):
        """Category-level failures are recorded in errors list."""
        mock_prefs = MagicMock()
        mock_prefs.get_preferences.side_effect = Exception("Prefs DB connection failed")
        # _migrate_events raises at category level
        mock_prefs.record_event.side_effect = Exception("Events table not found")

        mock_ratings = MagicMock()
        mock_ratings.get_rating.return_value = None
        mock_ratings.submit_rating.return_value = True

        service = MigrationService(
            preferences_service=mock_prefs,
            ratings_service=mock_ratings,
        )

        data = AnonymousData(
            anonymous_id="anon-123",
            preferences={"tone": "professional"},
            events=[{"event_type": "edit", "event_data": {}}],
            ratings=[{"thread_id": "thread-1", "overall_quality": 5}],
        )

        result = service.migrate_anonymous_data("user-1", data)

        assert result.preferences_migrated is False
        # Individual event errors are handled gracefully (0 migrated, but no category error)
        assert result.events_migrated == 0
        assert result.ratings_migrated == 1
        # Only preferences error is recorded (events handle per-item errors internally)
        assert len(result.errors) == 1
        assert "Preferences" in result.errors[0]

    def test_migrate_with_no_data(self):
        """Migration with no data returns empty result."""
        mock_prefs = MagicMock()
        mock_ratings = MagicMock()

        service = MigrationService(
            preferences_service=mock_prefs,
            ratings_service=mock_ratings,
        )

        data = AnonymousData(anonymous_id="anon-123")
        result = service.migrate_anonymous_data("user-1", data)

        assert result.preferences_migrated is False
        assert result.events_migrated == 0
        assert result.ratings_migrated == 0


class TestGetMigrationService:
    """Tests for singleton pattern."""

    def test_get_migration_service_returns_singleton(self):
        """get_migration_service returns the same instance."""
        # Reset singleton for test
        import services.migration_service as module
        module._migration_service = None

        service1 = get_migration_service()
        service2 = get_migration_service()

        assert service1 is service2

        # Clean up
        module._migration_service = None


# ==================== Migration Endpoint Tests ====================


class TestMigrateEndpoint:
    """Tests for POST /api/auth/migrate endpoint."""

    @pytest.fixture
    def mock_auth_service(self):
        """Mock auth service for authenticated requests."""
        with patch("routers.auth.get_auth_service") as mock:
            from datetime import datetime, timedelta
            from services.auth_service import User, SessionInfo
            service = MagicMock()
            service.verify_session_token.return_value = SessionInfo(
                user_id="user-123",
                session_id="session-456",
                expires_at=datetime.now() + timedelta(days=7),
            )
            service.get_user_by_id.return_value = User(
                id="user-123",
                email="test@example.com",
                created_at=datetime.now(),
                is_active=True,
            )
            mock.return_value = service
            yield service

    @pytest.fixture
    def mock_migration_service(self):
        """Mock migration service."""
        with patch("services.migration_service.get_migration_service") as mock:
            service = MagicMock()
            service.migrate_anonymous_data.return_value = MigrationResult(
                preferences_migrated=True,
                events_migrated=2,
                ratings_migrated=1,
                errors=[],
            )
            mock.return_value = service
            yield service

    def test_migrate_requires_authentication(self):
        """Migrate endpoint requires authentication."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/auth/migrate",
            json={"anonymous_id": "anon-123"},
        )

        assert response.status_code == 401

    def test_migrate_success(self, mock_auth_service, mock_migration_service):
        """Migrate endpoint successfully migrates data."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/auth/migrate",
            json={
                "anonymous_id": "anon-123",
                "preferences": {"tone": "professional"},
                "events": [{"event_type": "edit", "event_data": {}}],
                "ratings": [{"thread_id": "t1", "overall_quality": 5}],
            },
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Migration completed"
        assert data["preferences_migrated"] is True
        assert data["events_migrated"] == 2
        assert data["ratings_migrated"] == 1

    def test_migrate_with_errors(self, mock_auth_service):
        """Migrate endpoint returns errors from migration."""
        with patch("services.migration_service.get_migration_service") as mock:
            service = MagicMock()
            service.migrate_anonymous_data.return_value = MigrationResult(
                preferences_migrated=False,
                events_migrated=0,
                ratings_migrated=0,
                errors=["Preferences: DB error", "Events: Connection failed"],
            )
            mock.return_value = service

            from fastapi.testclient import TestClient
            from main import app

            client = TestClient(app)
            response = client.post(
                "/api/auth/migrate",
                json={"anonymous_id": "anon-123"},
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["errors"]) == 2

    def test_migrate_minimal_payload(self, mock_auth_service, mock_migration_service):
        """Migrate endpoint works with minimal payload (just anonymous_id)."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/auth/migrate",
            json={"anonymous_id": "anon-123"},
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 200

    def test_migrate_invalid_payload(self):
        """Migrate endpoint rejects invalid payload."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/auth/migrate",
            json={},  # Missing required anonymous_id
            headers={"Authorization": "Bearer valid-token"},
        )

        assert response.status_code == 422  # Validation error
