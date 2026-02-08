"""Shared dependencies for routers."""

import uuid
from typing import Optional

from fastapi import Header


def get_anonymous_user_id(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID")
) -> str:
    """Get anonymous user ID from header or generate one."""
    return x_anonymous_id or f"anon_{uuid.uuid4().hex[:12]}"
