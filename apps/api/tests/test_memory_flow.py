"""Integration tests for the Memory Feature flow.

Test coverage:
- Full authentication flow: request-link → verify → session management
- Migration flow from anonymous to authenticated user
- Error handling for protected routes
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app


class TestAuthenticationFlow:
    """Integration tests for complete authentication flow."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    def test_full_auth_flow_request_to_logout(self, client):
        """Test complete auth flow from request-link to logout."""
        with patch("routers.auth.get_auth_service") as mock_auth:
            from services.auth_service import User, MagicLink, SessionInfo

            service = MagicMock()
            mock_user = User(
                id="user-123",
                email="test@example.com",
                created_at=datetime.now(),
                is_active=True,
            )
            mock_magic = MagicLink(
                id="ml-1",
                user_id="user-123",
                token="test-token",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
            )
            mock_session = SessionInfo(
                user_id="user-123",
                session_id="sess-1",
                expires_at=datetime.now() + timedelta(days=7),
            )

            service.get_or_create_user.return_value = mock_user
            service.invalidate_magic_links_for_user.return_value = None
            service.create_magic_link.return_value = mock_magic
            service.validate_magic_link.return_value = mock_user
            service.update_last_login.return_value = None
            service.create_session_token.return_value = "session-token-abc"
            service.verify_session_token.return_value = mock_session
            service.get_user_by_id.return_value = mock_user
            service.revoke_session.return_value = None
            mock_auth.return_value = service

            # Step 1: Request magic link
            response = client.post(
                "/api/auth/request-link",
                json={"email": "test@example.com"},
            )
            assert response.status_code == 200
            assert "email" in response.json()["message"].lower()

            # Step 2: Verify magic link
            response = client.post(
                "/api/auth/verify",
                json={"token": "test-token"},
            )
            assert response.status_code == 200
            assert response.json()["user"]["email"] == "test@example.com"

            # Step 3: Get current user
            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer session-token-abc"},
            )
            assert response.status_code == 200
            assert response.json()["user"]["id"] == "user-123"

            # Step 4: Logout
            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer session-token-abc"},
            )
            assert response.status_code == 200

    def test_deactivated_user_blocked(self, client):
        """Deactivated users cannot request magic links."""
        with patch("routers.auth.get_auth_service") as mock_auth:
            from services.auth_service import User

            service = MagicMock()
            service.get_or_create_user.return_value = User(
                id="user-1",
                email="inactive@example.com",
                created_at=datetime.now(),
                is_active=False,
            )
            mock_auth.return_value = service

            response = client.post(
                "/api/auth/request-link",
                json={"email": "inactive@example.com"},
            )

            assert response.status_code == 403
            assert "deactivated" in response.json()["detail"].lower()


class TestMigrationFlow:
    """Integration tests for anonymous to authenticated migration."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    def test_full_migration_flow(self, client):
        """Test complete migration from anonymous to authenticated."""
        with patch("routers.auth.get_auth_service") as mock_auth:
            from services.auth_service import User, SessionInfo

            auth_service = MagicMock()
            auth_service.verify_session_token.return_value = SessionInfo(
                user_id="user-123",
                session_id="sess-1",
                expires_at=datetime.now() + timedelta(days=7),
            )
            auth_service.get_user_by_id.return_value = User(
                id="user-123",
                email="test@example.com",
                created_at=datetime.now(),
                is_active=True,
            )
            mock_auth.return_value = auth_service

            with patch("services.migration_service.get_migration_service") as mock_mig:
                from services.migration_service import MigrationResult

                mig_service = MagicMock()
                mig_service.migrate_anonymous_data.return_value = MigrationResult(
                    preferences_migrated=True,
                    events_migrated=5,
                    ratings_migrated=2,
                    errors=[],
                )
                mock_mig.return_value = mig_service

                response = client.post(
                    "/api/auth/migrate",
                    headers={"Authorization": "Bearer valid-token"},
                    json={
                        "anonymous_id": "anon-abc123",
                        "preferences": {
                            "tone": "professional",
                            "structure": "bullet_points",
                        },
                        "events": [
                            {"event_type": "edit", "event_data": {"field": "summary"}},
                        ],
                        "ratings": [
                            {"thread_id": "t1", "overall_quality": 5},
                        ],
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Migration completed"
                assert data["preferences_migrated"] is True
                assert data["events_migrated"] == 5
                assert data["ratings_migrated"] == 2


class TestErrorHandling:
    """Integration tests for error scenarios."""

    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)

    def test_me_requires_auth(self, client):
        """GET /api/auth/me requires authentication."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_migrate_requires_auth(self, client):
        """POST /api/auth/migrate requires authentication."""
        response = client.post(
            "/api/auth/migrate",
            json={"anonymous_id": "test"},
        )
        assert response.status_code == 401

    def test_logout_all_requires_auth(self, client):
        """POST /api/auth/logout-all requires authentication."""
        response = client.post("/api/auth/logout-all")
        assert response.status_code == 401

    def test_refresh_requires_auth(self, client):
        """POST /api/auth/refresh requires authentication."""
        response = client.post("/api/auth/refresh")
        assert response.status_code == 401

    def test_invalid_email_format_rejected(self, client):
        """Invalid email format is rejected."""
        response = client.post(
            "/api/auth/request-link",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_invalid_magic_link_rejected(self, client):
        """Invalid magic link returns 401."""
        with patch("routers.auth.get_auth_service") as mock_auth:
            service = MagicMock()
            service.validate_magic_link.return_value = None
            mock_auth.return_value = service

            response = client.post(
                "/api/auth/verify",
                json={"token": "invalid-token"},
            )
            assert response.status_code == 401
