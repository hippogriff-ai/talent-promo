"""Tests for preferences router and service.

Tests the anonymous user preferences functionality including:
- Getting and creating preferences
- Updating preferences
- Resetting preferences
- Recording preference events
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from services.preferences_service import PreferencesService, UserPreferences, PreferenceEvent


client = TestClient(app)

ANON_HEADERS = {"X-Anonymous-ID": "anon_test123456"}


class TestPreferencesRouter:
    """Tests for preferences API endpoints."""

    @patch("routers.preferences.get_preferences_service")
    def test_get_preferences_success(self, mock_get_service):
        """Test getting preferences returns user preferences."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = UserPreferences(
            id="pref-123",
            user_id="anon_test123456",
            tone="formal",
            structure="bullets",
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/preferences", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert data["preferences"]["tone"] == "formal"
        assert data["preferences"]["structure"] == "bullets"

    @patch("routers.preferences.get_preferences_service")
    def test_get_preferences_creates_default(self, mock_get_service):
        """Test getting preferences creates defaults if none exist."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = UserPreferences(
            id="new-pref",
            user_id="anon_newuser123",
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/preferences", headers={"X-Anonymous-ID": "anon_newuser123"})

        assert response.status_code == 200
        mock_service.get_or_create_preferences.assert_called_once()

    @patch("routers.preferences.get_preferences_service")
    def test_get_preferences_generates_id_if_missing(self, mock_get_service):
        """Test getting preferences generates anonymous ID if not provided."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = UserPreferences(
            id="pref-123",
            user_id="anon_generated",
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/preferences")

        assert response.status_code == 200
        # Should have called with a generated ID (starts with "anon_")
        call_args = mock_service.get_or_create_preferences.call_args[0]
        assert call_args[0].startswith("anon_")

    @patch("routers.preferences.get_preferences_service")
    def test_get_preferences_service_failure(self, mock_get_service):
        """Test getting preferences returns 500 if service fails."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = None
        mock_get_service.return_value = mock_service

        response = client.get("/api/preferences", headers=ANON_HEADERS)

        assert response.status_code == 500
        assert "Failed to get preferences" in response.json()["detail"]

    @patch("routers.preferences.get_preferences_service")
    def test_update_preferences_success(self, mock_get_service):
        """Test updating preferences with valid data."""
        mock_service = MagicMock()
        mock_service.update_preferences.return_value = UserPreferences(
            id="pref-123",
            user_id="anon_test123456",
            tone="conversational",
            structure="paragraphs",
            first_person=True,
        )
        mock_get_service.return_value = mock_service

        response = client.patch(
            "/api/preferences",
            json={
                "tone": "conversational",
                "structure": "paragraphs",
                "first_person": True,
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["tone"] == "conversational"
        assert data["preferences"]["first_person"] is True

    @patch("routers.preferences.get_preferences_service")
    def test_update_preferences_partial(self, mock_get_service):
        """Test partial update only modifies provided fields."""
        mock_service = MagicMock()
        mock_service.update_preferences.return_value = UserPreferences(
            id="pref-123",
            user_id="anon_test123456",
            tone="formal",  # Changed
            structure="bullets",  # Unchanged
        )
        mock_get_service.return_value = mock_service

        response = client.patch(
            "/api/preferences",
            json={"tone": "formal"},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        # Verify only tone was passed to update
        call_args = mock_service.update_preferences.call_args
        assert call_args[0][1] == {"tone": "formal"}

    @patch("routers.preferences.get_preferences_service")
    def test_update_preferences_service_failure(self, mock_get_service):
        """Test update returns 500 if service fails."""
        mock_service = MagicMock()
        mock_service.update_preferences.return_value = None
        mock_get_service.return_value = mock_service

        response = client.patch(
            "/api/preferences",
            json={"tone": "formal"},
            headers=ANON_HEADERS,
        )

        assert response.status_code == 500

    @patch("routers.preferences.get_preferences_service")
    def test_reset_preferences_success(self, mock_get_service):
        """Test resetting preferences to defaults."""
        mock_service = MagicMock()
        mock_service.reset_preferences.return_value = UserPreferences(
            id="pref-123",
            user_id="anon_test123456",
            # All fields back to None/default
        )
        mock_get_service.return_value = mock_service

        response = client.post("/api/preferences/reset", headers=ANON_HEADERS)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Preferences reset to defaults"
        mock_service.reset_preferences.assert_called_once()

    @patch("routers.preferences.get_preferences_service")
    def test_reset_preferences_failure(self, mock_get_service):
        """Test reset returns 500 if service fails."""
        mock_service = MagicMock()
        mock_service.reset_preferences.return_value = None
        mock_get_service.return_value = mock_service

        response = client.post("/api/preferences/reset", headers=ANON_HEADERS)

        assert response.status_code == 500

    @patch("routers.preferences.get_preferences_service")
    def test_record_event_success(self, mock_get_service):
        """Test recording a preference event."""
        mock_service = MagicMock()
        mock_service.record_event.return_value = True
        mock_service.get_event_count.return_value = 5
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/preferences/events",
            json={
                "event_type": "suggestion_accept",
                "event_data": {"tone": "formal", "suggestion_id": "s1"},
                "thread_id": "thread-123",
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Event recorded"
        assert data["event_count"] == 5

    @patch("routers.preferences.get_preferences_service")
    def test_record_event_edit(self, mock_get_service):
        """Test recording an edit event."""
        mock_service = MagicMock()
        mock_service.record_event.return_value = True
        mock_service.get_event_count.return_value = 1
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/preferences/events",
            json={
                "event_type": "edit",
                "event_data": {"before": "old text", "after": "new text"},
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200

    @patch("routers.preferences.get_preferences_service")
    def test_record_event_reject(self, mock_get_service):
        """Test recording a suggestion rejection event."""
        mock_service = MagicMock()
        mock_service.record_event.return_value = True
        mock_service.get_event_count.return_value = 2
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/preferences/events",
            json={
                "event_type": "suggestion_reject",
                "event_data": {"suggestion_id": "s2", "reason": "not relevant"},
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 200

    @patch("routers.preferences.get_preferences_service")
    def test_record_event_failure(self, mock_get_service):
        """Test recording event returns 500 if service fails."""
        mock_service = MagicMock()
        mock_service.record_event.return_value = False
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/preferences/events",
            json={
                "event_type": "edit",
                "event_data": {},
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 500

    def test_record_event_invalid_type(self):
        """Test recording event with invalid type returns 422."""
        response = client.post(
            "/api/preferences/events",
            json={
                "event_type": "invalid_type",
                "event_data": {},
            },
            headers=ANON_HEADERS,
        )

        assert response.status_code == 422  # Validation error


class TestPreferencesService:
    """Tests for preferences service directly."""

    def test_service_creation(self):
        """Test service can be created."""
        service = PreferencesService()
        assert service is not None

    def test_service_without_database(self):
        """Test service gracefully handles missing database."""
        service = PreferencesService()
        service.database_url = None

        # Should return None without crashing
        result = service.get_preferences("test-user")
        assert result is None

    def test_service_in_memory_storage(self):
        """Test service uses in-memory storage."""
        service = PreferencesService()

        # Should have empty storage initially
        assert service._preferences == {}
        assert service._events == {}

    def test_user_preferences_model(self):
        """Test UserPreferences model structure."""
        prefs = UserPreferences(
            user_id="test-user",
            tone="formal",
            structure="bullets",
            sentence_length="concise",
            first_person=True,
            quantification_preference="heavy_metrics",
            achievement_focus=True,
            custom_preferences={"key": "value"},
        )

        assert prefs.user_id == "test-user"
        assert prefs.tone == "formal"
        assert prefs.custom_preferences == {"key": "value"}

    def test_preference_event_model(self):
        """Test PreferenceEvent model structure."""
        event = PreferenceEvent(
            event_type="suggestion_accept",
            event_data={"tone": "formal"},
            thread_id="thread-123",
        )

        assert event.event_type == "suggestion_accept"
        assert event.event_data == {"tone": "formal"}
        assert event.thread_id == "thread-123"

    def test_preference_event_without_thread(self):
        """Test PreferenceEvent can be created without thread_id."""
        event = PreferenceEvent(
            event_type="edit",
            event_data={"before": "a", "after": "b"},
        )

        assert event.thread_id is None


class TestAnonymousIdGeneration:
    """Tests for anonymous ID generation in router."""

    @patch("routers.preferences.get_preferences_service")
    def test_uses_provided_anonymous_id(self, mock_get_service):
        """Test router uses X-Anonymous-ID header when provided."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = UserPreferences(
            id="pref-1",
            user_id="anon_provided123",
        )
        mock_get_service.return_value = mock_service

        client.get("/api/preferences", headers={"X-Anonymous-ID": "anon_provided123"})

        mock_service.get_or_create_preferences.assert_called_with("anon_provided123")

    @patch("routers.preferences.get_preferences_service")
    def test_generates_id_when_missing(self, mock_get_service):
        """Test router generates ID when header is missing."""
        mock_service = MagicMock()
        mock_service.get_or_create_preferences.return_value = UserPreferences(
            id="pref-1",
            user_id="anon_generated",
        )
        mock_get_service.return_value = mock_service

        client.get("/api/preferences")

        # Should have been called with generated ID
        call_args = mock_service.get_or_create_preferences.call_args[0][0]
        assert call_args.startswith("anon_")
        assert len(call_args) > 5  # anon_ + uuid portion
