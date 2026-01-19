"""Tests for authentication service and router.

Test coverage:
- User creation and lookup
- Magic link generation and validation
- JWT session token management
- Auth router endpoints
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Set test JWT secret before imports
os.environ["JWT_SECRET"] = "test-jwt-secret-for-testing-only"
os.environ["JWT_EXPIRY_DAYS"] = "7"
os.environ["MAGIC_LINK_EXPIRY_MINUTES"] = "15"


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


# ==================== AuthService Tests ====================


class TestAuthServiceUserManagement:
    """Tests for user creation and lookup."""

    def test_create_user_success(self):
        """Test successful user creation."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "test-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            None,
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.create_user("test@example.com")

            assert user is not None
            assert user.email == "test@example.com"
            assert user.is_active is True

    def test_create_user_normalizes_email(self):
        """Test that email is normalized to lowercase."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "test-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            None,
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.create_user("TEST@EXAMPLE.COM")

            assert user is not None
            assert user.email == "test@example.com"

    def test_create_user_no_connection(self):
        """Test user creation fails gracefully without database."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        with patch.object(service, "_get_connection", return_value=None):
            user = service.create_user("test@example.com")
            assert user is None

    def test_get_user_by_email_found(self):
        """Test getting user by email when exists."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "test-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.get_user_by_email("test@example.com")

            assert user is not None
            assert user.id == "test-uuid"
            assert user.email == "test@example.com"

    def test_get_user_by_email_not_found(self):
        """Test getting user by email when not exists."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = None

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.get_user_by_email("notfound@example.com")
            assert user is None

    def test_get_user_by_id_found(self):
        """Test getting user by ID when exists."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "test-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            None,
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.get_user_by_id("test-uuid")

            assert user is not None
            assert user.id == "test-uuid"

    def test_get_or_create_user_existing(self):
        """Test get_or_create returns existing user."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        existing_user = MagicMock()
        existing_user.id = "existing-uuid"
        existing_user.email = "test@example.com"

        with patch.object(service, "get_user_by_email", return_value=existing_user):
            with patch.object(service, "create_user") as create_mock:
                user = service.get_or_create_user("test@example.com")

                assert user.id == "existing-uuid"
                create_mock.assert_not_called()

    def test_get_or_create_user_new(self):
        """Test get_or_create creates new user when not exists."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        new_user = MagicMock()
        new_user.id = "new-uuid"
        new_user.email = "new@example.com"

        with patch.object(service, "get_user_by_email", return_value=None):
            with patch.object(service, "create_user", return_value=new_user):
                user = service.get_or_create_user("new@example.com")

                assert user.id == "new-uuid"


class TestAuthServiceMagicLinks:
    """Tests for magic link generation and validation."""

    def test_create_magic_link_success(self):
        """Test successful magic link creation."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (
            "link-uuid",
            "user-uuid",
            "test-token",
            datetime.now(timezone.utc) + timedelta(minutes=15),
            datetime.now(timezone.utc),
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            magic_link = service.create_magic_link("user-uuid")

            assert magic_link is not None
            assert magic_link.user_id == "user-uuid"
            assert len(magic_link.token) > 0

    def test_validate_magic_link_success(self):
        """Test successful magic link validation."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        # Return magic link + user data
        mock_conn._cursor._result = (
            "link-uuid",  # magic link id
            "user-uuid",  # user_id
            datetime.now(timezone.utc) + timedelta(minutes=10),  # expires_at (not expired)
            None,  # used_at (not used)
            "user-uuid",  # user id
            "test@example.com",  # user email
            datetime.now(timezone.utc),  # user created_at
            None,  # user last_login_at
            True,  # user is_active
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.validate_magic_link("valid-token")

            assert user is not None
            assert user.email == "test@example.com"

    def test_validate_magic_link_expired(self):
        """Test magic link validation fails when expired."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        # Return expired magic link
        mock_conn._cursor._result = (
            "link-uuid",
            "user-uuid",
            datetime.now(timezone.utc) - timedelta(minutes=10),  # expired
            None,
            "user-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            None,
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.validate_magic_link("expired-token")
            assert user is None

    def test_validate_magic_link_already_used(self):
        """Test magic link validation fails when already used."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        # Return already used magic link
        mock_conn._cursor._result = (
            "link-uuid",
            "user-uuid",
            datetime.now(timezone.utc) + timedelta(minutes=10),
            datetime.now(timezone.utc) - timedelta(minutes=5),  # used_at is set
            "user-uuid",
            "test@example.com",
            datetime.now(timezone.utc),
            None,
            True,
        )

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.validate_magic_link("used-token")
            assert user is None

    def test_validate_magic_link_not_found(self):
        """Test magic link validation fails when token not found."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = None

        with patch.object(service, "_get_connection", return_value=mock_conn):
            user = service.validate_magic_link("invalid-token")
            assert user is None


class TestAuthServiceSessions:
    """Tests for JWT session token management."""

    def test_create_session_token_success(self):
        """Test successful session token creation."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()

        with patch.object(service, "_get_connection", return_value=mock_conn):
            token = service.create_session_token("user-uuid")

            assert token is not None
            assert len(token) > 0

    def test_verify_session_token_success(self):
        """Test successful session token verification."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()
        mock_conn._cursor._result = (None,)  # revoked_at is None

        with patch.object(service, "_get_connection", return_value=mock_conn):
            # First create a token
            token = service.create_session_token("user-uuid")

            # Then verify it
            session_info = service.verify_session_token(token)

            assert session_info is not None
            assert session_info.user_id == "user-uuid"

    def test_verify_session_token_expired(self):
        """Test session token verification fails when expired."""
        import jwt
        from services.auth_service import AuthService, JWT_SECRET, JWT_ALGORITHM

        service = AuthService("postgresql://test")

        # Create an expired token
        payload = {
            "sub": "user-uuid",
            "sid": "session-id",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        session_info = service.verify_session_token(expired_token)
        assert session_info is None

    def test_verify_session_token_invalid(self):
        """Test session token verification fails for invalid token."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        session_info = service.verify_session_token("invalid-token")
        assert session_info is None

    def test_revoke_session_success(self):
        """Test successful session revocation."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()

        with patch.object(service, "_get_connection", return_value=mock_conn):
            token = service.create_session_token("user-uuid")
            result = service.revoke_session(token)

            assert result is True

    def test_revoke_all_sessions_success(self):
        """Test successful revocation of all sessions."""
        from services.auth_service import AuthService

        service = AuthService("postgresql://test")

        mock_conn = MockConnection()

        with patch.object(service, "_get_connection", return_value=mock_conn):
            result = service.revoke_all_sessions("user-uuid")
            assert result is True


# ==================== Auth Router Tests ====================


class TestAuthRouterRequestLink:
    """Tests for POST /api/auth/request-link endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked services."""
        from main import app
        return TestClient(app)

    def test_request_link_success(self, client):
        """Test successful magic link request."""
        from services.auth_service import User, MagicLink

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        mock_link = MagicLink(
            id="link-uuid",
            user_id="user-uuid",
            token="test-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            created_at=datetime.now(timezone.utc),
        )

        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_or_create_user.return_value = mock_user
            mock_instance.invalidate_magic_links_for_user.return_value = True
            mock_instance.create_magic_link.return_value = mock_link
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/request-link",
                json={"email": "test@example.com"},
            )

            assert response.status_code == 200
            assert response.json()["message"] == "Check your email for the login link"

    def test_request_link_invalid_email(self, client):
        """Test magic link request with invalid email."""
        response = client.post(
            "/api/auth/request-link",
            json={"email": "invalid-email"},
        )

        assert response.status_code == 422  # Validation error

    def test_request_link_deactivated_user(self, client):
        """Test magic link request for deactivated user."""
        from services.auth_service import User

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=False,  # Deactivated
        )

        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_or_create_user.return_value = mock_user
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/request-link",
                json={"email": "test@example.com"},
            )

            assert response.status_code == 403
            assert "deactivated" in response.json()["detail"].lower()


class TestAuthRouterVerify:
    """Tests for POST /api/auth/verify endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked services."""
        from main import app
        return TestClient(app)

    def test_verify_success(self, client):
        """Test successful magic link verification."""
        from services.auth_service import User

        mock_user = User(
            id="user-uuid",
            email="test@example.com",
            created_at=datetime.now(timezone.utc),
            is_active=True,
        )

        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_magic_link.return_value = mock_user
            mock_instance.update_last_login.return_value = True
            mock_instance.create_session_token.return_value = "jwt-token"
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/verify",
                json={"token": "valid-token"},
            )

            assert response.status_code == 200
            assert response.json()["user"]["email"] == "test@example.com"
            assert "session_token" in response.cookies

    def test_verify_invalid_token(self, client):
        """Test verification with invalid token."""
        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.validate_magic_link.return_value = None
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/verify",
                json={"token": "invalid-token"},
            )

            assert response.status_code == 401


class TestAuthRouterMe:
    """Tests for GET /api/auth/me endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked services."""
        from main import app
        return TestClient(app)

    def test_get_me_authenticated(self, client):
        """Test getting current user when authenticated."""
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

        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = mock_session
            mock_instance.get_user_by_id.return_value = mock_user
            mock_service.return_value = mock_instance

            response = client.get(
                "/api/auth/me",
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            assert response.json()["user"]["email"] == "test@example.com"

    def test_get_me_not_authenticated(self, client):
        """Test getting current user when not authenticated."""
        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = None
            mock_service.return_value = mock_instance

            response = client.get("/api/auth/me")

            assert response.status_code == 401


class TestAuthRouterLogout:
    """Tests for POST /api/auth/logout endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked services."""
        from main import app
        return TestClient(app)

    def test_logout_success(self, client):
        """Test successful logout."""
        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.revoke_session.return_value = True
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            assert "logged out" in response.json()["message"].lower()

    def test_logout_without_token(self, client):
        """Test logout without token still succeeds."""
        response = client.post("/api/auth/logout")

        assert response.status_code == 200


class TestAuthRouterLogoutAll:
    """Tests for POST /api/auth/logout-all endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked services."""
        from main import app
        return TestClient(app)

    def test_logout_all_success(self, client):
        """Test successful logout of all sessions."""
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

        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = mock_session
            mock_instance.get_user_by_id.return_value = mock_user
            mock_instance.revoke_all_sessions.return_value = True
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/auth/logout-all",
                headers={"Authorization": "Bearer valid-token"},
            )

            assert response.status_code == 200
            assert "revoked" in response.json()["message"].lower()

    def test_logout_all_not_authenticated(self, client):
        """Test logout all fails when not authenticated."""
        with patch("routers.auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = None
            mock_service.return_value = mock_instance

            response = client.post("/api/auth/logout-all")

            assert response.status_code == 401


# ==================== Session Middleware Tests ====================


class TestSessionMiddleware:
    """Tests for session authentication middleware."""

    @pytest.mark.asyncio
    async def test_get_current_user_optional_authenticated(self):
        """Test optional auth returns user when authenticated."""
        from middleware.session_auth import get_current_user_optional
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

        with patch("middleware.session_auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = mock_session
            mock_instance.get_user_by_id.return_value = mock_user
            mock_service.return_value = mock_instance

            user = await get_current_user_optional(
                authorization="Bearer valid-token",
                session_token=None,
            )

            assert user is not None
            assert user.id == "user-uuid"

    @pytest.mark.asyncio
    async def test_get_current_user_optional_not_authenticated(self):
        """Test optional auth returns None when not authenticated."""
        from middleware.session_auth import get_current_user_optional

        user = await get_current_user_optional(
            authorization=None,
            session_token=None,
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_raises_401(self):
        """Test required auth raises 401 when not authenticated."""
        from middleware.session_auth import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                authorization=None,
                session_token=None,
            )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_user_id_optional_returns_id(self):
        """Test get_user_id_optional returns user ID."""
        from middleware.session_auth import get_user_id_optional
        from services.auth_service import SessionInfo

        mock_session = SessionInfo(
            user_id="user-uuid",
            session_id="session-id",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        with patch("middleware.session_auth.get_auth_service") as mock_service:
            mock_instance = MagicMock()
            mock_instance.verify_session_token.return_value = mock_session
            mock_service.return_value = mock_instance

            user_id = await get_user_id_optional(
                authorization="Bearer valid-token",
                session_token=None,
            )

            assert user_id == "user-uuid"
