"""Authentication router for magic link authentication.

Endpoints:
- POST /api/auth/request-link - Request a magic link email
- POST /api/auth/verify - Verify magic link and get session token
- GET /api/auth/me - Get current authenticated user
- POST /api/auth/logout - Revoke current session
- POST /api/auth/logout-all - Revoke all sessions for user
- POST /api/auth/refresh - Refresh session token
- POST /api/auth/migrate - Migrate anonymous data to user account
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Header, Request, Response
from pydantic import BaseModel, EmailStr

from services.auth_service import User, get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Frontend URL for magic link
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


# ==================== Request/Response Models ====================


class RequestLinkInput(BaseModel):
    """Request body for magic link request."""

    email: EmailStr


class RequestLinkResponse(BaseModel):
    """Response for magic link request."""

    message: str


class VerifyInput(BaseModel):
    """Request body for magic link verification."""

    token: str


class VerifyResponse(BaseModel):
    """Response for successful verification."""

    user: User
    message: str


class UserResponse(BaseModel):
    """Response for current user endpoint."""

    user: User


class LogoutResponse(BaseModel):
    """Response for logout endpoint."""

    message: str


# ==================== Helper Functions ====================


def get_token_from_request(
    authorization: Optional[str] = None,
    session_token: Optional[str] = None,
) -> Optional[str]:
    """Extract session token from Authorization header or cookie."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return session_token


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    token = get_token_from_request(authorization, session_token)
    if not token:
        return None

    auth_service = get_auth_service()
    session_info = auth_service.verify_session_token(token)
    if not session_info:
        return None

    return auth_service.get_user_by_id(session_info.user_id)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> User:
    """Get current authenticated user or raise 401."""
    user = await get_current_user_optional(authorization, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ==================== Endpoints ====================


@router.post("/request-link", response_model=RequestLinkResponse)
async def request_magic_link(body: RequestLinkInput, request: Request) -> RequestLinkResponse:
    """Request a magic link to be sent to the user's email.

    This endpoint:
    1. Creates a user if they don't exist
    2. Generates a magic link token
    3. Sends an email with the magic link (or logs it in dev mode)
    """
    auth_service = get_auth_service()

    # Get or create user
    user = auth_service.get_or_create_user(body.email)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Invalidate any existing unused magic links
    auth_service.invalidate_magic_links_for_user(user.id)

    # Create new magic link
    magic_link = auth_service.create_magic_link(user.id)
    if not magic_link:
        raise HTTPException(status_code=500, detail="Failed to create magic link")

    # Build the verification URL
    verify_url = f"{FRONTEND_URL}/auth/verify?token={magic_link.token}"

    # Send email (import here to avoid circular imports and allow mocking)
    try:
        from services.email_service import send_magic_link_email

        email_sent = await send_magic_link_email(body.email, verify_url)
        if not email_sent:
            logger.warning(f"Failed to send magic link email to {body.email}")
    except ImportError:
        # Email service not available, log the link for development
        logger.info(f"Magic link for {body.email}: {verify_url}")

    return RequestLinkResponse(message="Check your email for the login link")


@router.post("/verify", response_model=VerifyResponse)
async def verify_magic_link(
    body: VerifyInput,
    request: Request,
    response: Response,
) -> VerifyResponse:
    """Verify a magic link token and create a session.

    This endpoint:
    1. Validates the magic link token
    2. Creates a new session
    3. Sets the session cookie
    4. Returns the user info
    """
    auth_service = get_auth_service()

    # Validate the magic link
    user = auth_service.validate_magic_link(body.token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Update last login timestamp
    auth_service.update_last_login(user.id)

    # Get client info for session tracking
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    # Create session token
    token = auth_service.create_session_token(user.id, user_agent, client_ip)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Set session cookie (httpOnly for security)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return VerifyResponse(user=user, message="Successfully authenticated")


@router.get("/me", response_model=UserResponse)
async def get_me(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> UserResponse:
    """Get the current authenticated user's information."""
    user = await get_current_user(authorization, session_token)
    return UserResponse(user=user)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> LogoutResponse:
    """Logout and revoke the current session."""
    token = get_token_from_request(authorization, session_token)

    if token:
        auth_service = get_auth_service()
        auth_service.revoke_session(token)

    # Clear the session cookie
    response.delete_cookie(key="session_token")

    return LogoutResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(
    response: Response,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> LogoutResponse:
    """Logout and revoke all sessions for the current user."""
    user = await get_current_user(authorization, session_token)

    auth_service = get_auth_service()
    auth_service.revoke_all_sessions(user.id)

    # Clear the session cookie
    response.delete_cookie(key="session_token")

    return LogoutResponse(message="All sessions have been revoked")


@router.post("/refresh", response_model=VerifyResponse)
async def refresh_token(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> VerifyResponse:
    """Refresh the session token.

    This revokes the current token and issues a new one.
    """
    token = get_token_from_request(authorization, session_token)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = get_auth_service()

    # Verify current session
    session_info = auth_service.verify_session_token(token)
    if not session_info:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Get user
    user = auth_service.get_user_by_id(session_info.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Revoke old session
    auth_service.revoke_session(token)

    # Get client info for new session
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    # Create new session token
    new_token = auth_service.create_session_token(user.id, user_agent, client_ip)
    if not new_token:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Set new session cookie
    response.set_cookie(
        key="session_token",
        value=new_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return VerifyResponse(user=user, message="Session refreshed")


# ==================== Migration Endpoint ====================


class MigrateInput(BaseModel):
    """Request body for migrating anonymous data."""

    anonymous_id: str
    preferences: Optional[dict] = None
    events: list[dict] = []
    ratings: list[dict] = []


class MigrateResponse(BaseModel):
    """Response for migration endpoint."""

    message: str
    preferences_migrated: bool
    events_migrated: int
    ratings_migrated: int
    errors: list[str] = []


@router.post("/migrate", response_model=MigrateResponse)
async def migrate_anonymous_data(
    body: MigrateInput,
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> MigrateResponse:
    """Migrate anonymous user data to authenticated account.

    This endpoint should be called after successful authentication
    when the client has localStorage data to migrate.

    Conflict resolution: If user already has preferences set,
    they take precedence (anonymous data is not overwritten).
    """
    user = await get_current_user(authorization, session_token)

    from services.migration_service import AnonymousData, get_migration_service

    migration_service = get_migration_service()

    data = AnonymousData(
        anonymous_id=body.anonymous_id,
        preferences=body.preferences,
        events=body.events,
        ratings=body.ratings,
    )

    result = migration_service.migrate_anonymous_data(user.id, data)

    return MigrateResponse(
        message="Migration completed",
        preferences_migrated=result.preferences_migrated,
        events_migrated=result.events_migrated,
        ratings_migrated=result.ratings_migrated,
        errors=result.errors,
    )


# ==================== Admin Endpoints ====================

# Admin token for managing users (set in environment)
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change-me-in-production")


class SetUnlimitedInput(BaseModel):
    """Request body for setting unlimited status."""

    email: EmailStr
    unlimited: bool = True


class SetUnlimitedResponse(BaseModel):
    """Response for set unlimited endpoint."""

    success: bool
    message: str


@router.post("/admin/set-unlimited", response_model=SetUnlimitedResponse)
async def set_user_unlimited(
    body: SetUnlimitedInput,
    x_admin_secret: Optional[str] = Header(None),
) -> SetUnlimitedResponse:
    """Grant or revoke unlimited resume access for a user.

    Requires X-Admin-Secret header matching ADMIN_SECRET env var.

    Example:
        curl -X POST http://localhost:8000/api/auth/admin/set-unlimited \\
             -H "Content-Type: application/json" \\
             -H "X-Admin-Secret: your-secret" \\
             -d '{"email": "friend@example.com", "unlimited": true}'
    """
    import secrets

    if not x_admin_secret or not secrets.compare_digest(x_admin_secret, ADMIN_SECRET):
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    auth_service = get_auth_service()
    success = auth_service.set_unlimited(body.email, body.unlimited)

    if success:
        status = "unlimited" if body.unlimited else "limited"
        return SetUnlimitedResponse(
            success=True,
            message=f"User {body.email} is now {status}",
        )
    else:
        return SetUnlimitedResponse(
            success=False,
            message=f"User {body.email} not found or update failed",
        )
