"""Admin authentication middleware for arena endpoints."""

import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException


def _get_admin_token() -> Optional[str]:
    """Get admin token lazily at runtime (not import time)."""
    return os.getenv("ARENA_ADMIN_TOKEN")


async def verify_admin(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    authorization: Optional[str] = Header(None),
) -> str:
    """Verify admin authentication via token header. Returns admin identifier or raises 401."""
    admin_token = _get_admin_token()
    if not admin_token:
        raise HTTPException(status_code=500, detail="ARENA_ADMIN_TOKEN not configured")

    token = x_admin_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Missing admin authentication")

    if not secrets.compare_digest(token, admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    return "admin"
