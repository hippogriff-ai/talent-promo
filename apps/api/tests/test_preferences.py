"""Tests for preferences service and router.

Test coverage:
- Preferences CRUD operations
- Event recording
- Preference computation from events
- Preferences router endpoints
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set test environment
os.environ["JWT_SECRET"] = "test-jwt-secret-for-testing-only"


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self):
        self.closed = False
        self._cursor = MockCursor()

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class MockCursor:
    """Mock database cursor for testing."""

    def __init__(self):
        self._result = None
        self._results = []
        self._rowcount = 0

    def execute(self, query, params=None):
        pass

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._results

    @property
    def rowcount(self):
        return self._rowcount

    def close(self):
        pass


# ==================== PreferencesService Tests ====================


class TestPreferencesServiceCRUD:
    """Tests for preferences CRUD operations."""

    def test_get_preferences_found(self):
        """Test getting preferences when they exist."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "pref-uuid",
            "user-uuid",
            "formal",
            "bullets",
            "concise",
            True,
            "heavy_metrics",
            True,
            {"custom_key": "custom_value"},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            prefs = service.get_preferences("user-uuid")

            assert prefs is not None
            assert prefs.user_id == "user-uuid"
            assert prefs.tone == "formal"
            assert prefs.structure == "bullets"
            assert prefs.first_person is True

    def test_get_preferences_not_found(self):
        """Test getting preferences when they don't exist."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = None

        with patch.object(service, "_get_connection", return_value=mock_conn):
            prefs = service.get_preferences("user-uuid")
            assert prefs is None

    def test_get_preferences_no_connection(self):
        """Test getting preferences without database connection."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        with patch.object(service, "_get_connection", return_value=None):
            prefs = service.get_preferences("user-uuid")
            assert prefs is None

    def test_create_preferences_success(self):
        """Test creating default preferences."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "pref-uuid",
            "user-uuid",
            None,
            None,
            None,
            None,
            None,
            None,
            {},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            prefs = service.create_preferences("user-uuid")

            assert prefs is not None
            assert prefs.user_id == "user-uuid"
            assert prefs.tone is None  # Default is None

    def test_update_preferences_success(self):
        """Test updating preferences."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        # First call for get_or_create, second for get after update
        mock_conn._cursor._result = (
            "pref-uuid",
            "user-uuid",
            "conversational",
            "paragraphs",
            "detailed",
            False,
            "qualitative",
            False,
            {},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            with patch.object(service, "get_or_create_preferences"):
                prefs = service.update_preferences(
                    "user-uuid",
                    {"tone": "conversational", "structure": "paragraphs"},
                )

                assert prefs is not None

    def test_update_preferences_filters_invalid_fields(self):
        """Test that update filters out invalid fields."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "pref-uuid",
            "user-uuid",
            None,
            None,
            None,
            None,
            None,
            None,
            {},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            with patch.object(service, "get_or_create_preferences"):
                # invalid_field should be filtered out
                prefs = service.update_preferences(
                    "user-uuid",
                    {"invalid_field": "value"},
                )

                # Should still return preferences (just no updates)
                assert prefs is not None

    def test_reset_preferences_success(self):
        """Test resetting preferences to defaults."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "pref-uuid",
            "user-uuid",
            None,
            None,
            None,
            None,
            None,
            None,
            {},
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            prefs = service.reset_preferences("user-uuid")

            assert prefs is not None

    def test_delete_preferences_success(self):
        """Test deleting all preferences data."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()

        with patch.object(service, "_get_connection", return_value=mock_conn):
            result = service.delete_preferences("user-uuid")
            assert result is True


class TestPreferencesServiceEvents:
    """Tests for preference event operations."""

    def test_record_event_success(self):
        """Test recording a preference event."""
        from services.preferences_service import PreferencesService, PreferenceEvent

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()

        with patch.object(service, "_get_connection", return_value=mock_conn):
            event = PreferenceEvent(
                event_type="suggestion_accept",
                event_data={"tone": "formal"},
                thread_id="thread-123",
            )
            result = service.record_event("user-uuid", event)
            assert result is True

    def test_record_event_no_connection(self):
        """Test recording event without database connection."""
        from services.preferences_service import PreferencesService, PreferenceEvent

        service = PreferencesService("postgresql://test")

        with patch.object(service, "_get_connection", return_value=None):
            event = PreferenceEvent(
                event_type="suggestion_accept",
                event_data={"tone": "formal"},
            )
            result = service.record_event("user-uuid", event)
            assert result is False

    def test_get_events_success(self):
        """Test getting preference events."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._results = [
            (
                "event-1",
                "user-uuid",
                "thread-123",
                "suggestion_accept",
                {"tone": "formal"},
                datetime.now(timezone.utc),
            ),
            (
                "event-2",
                "user-uuid",
                "thread-123",
                "edit",
                {"before": "text", "after": "new text"},
                datetime.now(timezone.utc),
            ),
        ]

        with patch.object(service, "_get_connection", return_value=mock_conn):
            events = service.get_events("user-uuid")

            assert len(events) == 2
            assert events[0]["event_type"] == "suggestion_accept"

    def test_get_events_filtered_by_type(self):
        """Test getting events filtered by type."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._results = [
            (
                "event-1",
                "user-uuid",
                "thread-123",
                "suggestion_accept",
                {"tone": "formal"},
                datetime.now(timezone.utc),
            ),
        ]

        with patch.object(service, "_get_connection", return_value=mock_conn):
            events = service.get_events("user-uuid", event_type="suggestion_accept")
            assert len(events) == 1

    def test_get_event_count_success(self):
        """Test getting event count."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (42,)

        with patch.object(service, "_get_connection", return_value=mock_conn):
            count = service.get_event_count("user-uuid")
            assert count == 42


class TestPreferencesServiceComputation:
    """Tests for preference computation from events."""

    def test_compute_preferences_from_events_success(self):
        """Test computing preferences from events."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        events = [
            {"event_type": "suggestion_accept", "event_data": {"tone": "formal"}},
            {"event_type": "suggestion_accept", "event_data": {"tone": "formal"}},
            {"event_type": "suggestion_accept", "event_data": {"tone": "conversational"}},
            {"event_type": "suggestion_accept", "event_data": {"structure": "bullets"}},
        ]

        with patch.object(service, "get_events", return_value=events):
            prefs = service.compute_preferences_from_events("user-uuid")

            assert prefs is not None
            assert prefs.tone == "formal"  # Most common
            assert prefs.structure == "bullets"

    def test_compute_preferences_no_events(self):
        """Test computing preferences with no events."""
        from services.preferences_service import PreferencesService

        service = PreferencesService("postgresql://test")

        with patch.object(service, "get_events", return_value=[]):
            prefs = service.compute_preferences_from_events("user-uuid")
            assert prefs is None


# ==================== Preferences Router Tests ====================


class TestPreferencesRouterGet:
    """Tests for GET /api/preferences endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_get_preferences_authenticated(self, client):
        """Test getting preferences when authenticated."""
        from services.auth_service import User, SessionInfo
        from services.preferences_service import UserPreferences

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_prefs = UserPreferences(
            id="pref-uuid",
            user_id="user-uuid",
            tone="formal",
            structure="bullets",
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.get_or_create_preferences.return_value = mock_prefs
                mock_pref.return_value = mock_pref_instance

                response = client.get(
                    "/api/preferences",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["preferences"]["tone"] == "formal"

    def test_get_preferences_not_authenticated(self, client):
        """Test getting preferences without authentication."""
        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = None
            mock_auth.return_value = mock_instance

            response = client.get("/api/preferences")
            assert response.status_code == 401


class TestPreferencesRouterUpdate:
    """Tests for PATCH /api/preferences endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_update_preferences_success(self, client):
        """Test updating preferences."""
        from services.auth_service import User, SessionInfo
        from services.preferences_service import UserPreferences

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_prefs = UserPreferences(
            id="pref-uuid",
            user_id="user-uuid",
            tone="conversational",
            structure="paragraphs",
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.update_preferences.return_value = mock_prefs
                mock_pref.return_value = mock_pref_instance

                response = client.patch(
                    "/api/preferences",
                    headers={"Authorization": "Bearer valid-token"},
                    json={"tone": "conversational", "structure": "paragraphs"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["preferences"]["tone"] == "conversational"


class TestPreferencesRouterReset:
    """Tests for POST /api/preferences/reset endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_reset_preferences_success(self, client):
        """Test resetting preferences."""
        from services.auth_service import User, SessionInfo
        from services.preferences_service import UserPreferences

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_prefs = UserPreferences(
            id="pref-uuid",
            user_id="user-uuid",
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.reset_preferences.return_value = mock_prefs
                mock_pref.return_value = mock_pref_instance

                response = client.post(
                    "/api/preferences/reset",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                assert "reset" in response.json()["message"].lower()


class TestPreferencesRouterEvents:
    """Tests for preference events endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_record_event_success(self, client):
        """Test recording a preference event."""
        from services.auth_service import User, SessionInfo

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.record_event.return_value = True
                mock_pref_instance.get_event_count.return_value = 5
                mock_pref.return_value = mock_pref_instance

                response = client.post(
                    "/api/preferences/events",
                    headers={"Authorization": "Bearer valid-token"},
                    json={
                        "event_type": "suggestion_accept",
                        "event_data": {"tone": "formal"},
                        "thread_id": "thread-123",
                    },
                )

                assert response.status_code == 200
                assert response.json()["event_count"] == 5

    def test_get_events_success(self, client):
        """Test getting preference events."""
        from services.auth_service import User, SessionInfo

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_events = [
            {
                "id": "event-1",
                "event_type": "suggestion_accept",
                "event_data": {"tone": "formal"},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.get_events.return_value = mock_events
                mock_pref_instance.get_event_count.return_value = 1
                mock_pref.return_value = mock_pref_instance

                response = client.get(
                    "/api/preferences/events",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["events"]) == 1
                assert data["total_count"] == 1


class TestPreferencesRouterCompute:
    """Tests for POST /api/preferences/compute endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_compute_preferences_preview(self, client):
        """Test computing preferences without applying."""
        from services.auth_service import User, SessionInfo
        from services.preferences_service import UserPreferences

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_prefs = UserPreferences(
            id="pref-uuid",
            user_id="user-uuid",
            tone="formal",
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.compute_preferences_from_events.return_value = mock_prefs
                mock_pref.return_value = mock_pref_instance

                response = client.post(
                    "/api/preferences/compute",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["applied"] is False
                assert "not applied" in data["message"].lower()

    def test_compute_preferences_apply(self, client):
        """Test computing and applying preferences."""
        from services.auth_service import User, SessionInfo
        from services.preferences_service import UserPreferences

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        mock_prefs = UserPreferences(
            id="pref-uuid",
            user_id="user-uuid",
            tone="formal",
        )

        with patch("middleware.session_auth.get_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_session_token.return_value = mock_session
            mock_auth_instance.get_user_by_id.return_value = mock_user
            mock_auth.return_value = mock_auth_instance

            with patch("routers.preferences.get_preferences_service") as mock_pref:
                mock_pref_instance = MagicMock()
                mock_pref_instance.apply_computed_preferences.return_value = mock_prefs
                mock_pref.return_value = mock_pref_instance

                response = client.post(
                    "/api/preferences/compute?apply=true",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["applied"] is True


class TestPreferencesRouterAnonymous:
    """Tests for anonymous user event endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from main import app
        return TestClient(app)

    def test_record_anonymous_event_success(self, client):
        """Test recording event for anonymous user."""
        with patch("routers.preferences.get_preferences_service") as mock_pref:
            mock_pref_instance = MagicMock()
            mock_pref_instance.record_event.return_value = True
            mock_pref_instance.get_event_count.return_value = 1
            mock_pref.return_value = mock_pref_instance

            response = client.post(
                "/api/preferences/events/anonymous?anonymous_id=anon-123",
                json={
                    "event_type": "edit",
                    "event_data": {"before": "old", "after": "new"},
                },
            )

            assert response.status_code == 200
            assert response.json()["event_count"] == 1
