"""Session authentication middleware for protected routes.

This module provides FastAPI dependencies for authentication:
- get_current_user: Requires authentication, returns User or raises 401
- get_current_user_optional: Returns User if authenticated, None otherwise
- require_auth: Simple dependency that just verifies authentication
"""

import logging
from typing import Optional

from fastapi import Cookie, Header, HTTPException

from services.auth_service import User, get_auth_service

logger = logging.getLogger(__name__)


def _get_token_from_request(
    authorization: Optional[str] = None,
    session_token: Optional[str] = None,
) -> Optional[str]:
    """Extract session token from Authorization header or cookie.

    Priority:
    1. Authorization: Bearer <token>
    2. session_token cookie

    Args:
        authorization: Authorization header value.
        session_token: Cookie value.

    Returns:
        Token string if found, None otherwise.
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return session_token


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    This dependency doesn't raise an error if not authenticated.
    Use this for endpoints that work with or without authentication.

    Args:
        authorization: Authorization header.
        session_token: Session cookie.

    Returns:
        User object if authenticated, None otherwise.
    """
    token = _get_token_from_request(authorization, session_token)
    if not token:
        return None

    auth_service = get_auth_service()
    session_info = auth_service.verify_session_token(token)
    if not session_info:
        return None

    user = auth_service.get_user_by_id(session_info.user_id)
    if user and not user.is_active:
        return None

    return user


async def get_current_user(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> User:
    """Get current authenticated user or raise 401.

    This dependency requires authentication. Use it for protected endpoints.

    Args:
        authorization: Authorization header.
        session_token: Session cookie.

    Returns:
        User object.

    Raises:
        HTTPException: 401 if not authenticated or user not found.
    """
    user = await get_current_user_optional(authorization, session_token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_auth(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> str:
    """Simple dependency that verifies authentication and returns user ID.

    Use this when you only need to verify the user is authenticated
    but don't need the full User object.

    Args:
        authorization: Authorization header.
        session_token: Session cookie.

    Returns:
        User ID string.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user = await get_current_user(authorization, session_token)
    return user.id


async def get_user_id_optional(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> Optional[str]:
    """Get user ID if authenticated, None otherwise.

    Lightweight version of get_current_user_optional that only returns the ID.

    Args:
        authorization: Authorization header.
        session_token: Session cookie.

    Returns:
        User ID string if authenticated, None otherwise.
    """
    token = _get_token_from_request(authorization, session_token)
    if not token:
        return None

    auth_service = get_auth_service()
    session_info = auth_service.verify_session_token(token)
    if not session_info:
        return None

    return session_info.user_id
