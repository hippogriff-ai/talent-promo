"""Cloudflare Turnstile bot protection.

Verifies Turnstile tokens on the /start endpoint to prevent automated abuse.
When TURNSTILE_SECRET_KEY is not set, verification is bypassed (dev mode).
"""

import logging
import os

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT = 5.0  # seconds


async def verify_turnstile_token(token: str | None, client_ip: str) -> None:
    """Verify a Cloudflare Turnstile token.

    Args:
        token: The turnstile response token from the frontend widget.
        client_ip: Client IP address for Turnstile's remote IP check.

    Raises:
        HTTPException(403): If token is missing or invalid.
        HTTPException(503): If Cloudflare API is unreachable (fail-closed).

    Returns:
        None on success (token valid or Turnstile not configured).
    """
    secret_key = os.getenv("TURNSTILE_SECRET_KEY")
    if not secret_key:
        # Dev mode: Turnstile not configured, skip verification
        return

    if not token:
        raise HTTPException(
            status_code=403,
            detail="Bot protection check required. Please complete the challenge and try again.",
        )

    try:
        async with httpx.AsyncClient(timeout=TURNSTILE_TIMEOUT) as client:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": secret_key,
                    "response": token,
                    "remoteip": client_ip,
                },
            )

        result = response.json()

        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            logger.warning(
                "Turnstile verification failed: %s (IP: %s)",
                error_codes,
                client_ip,
            )
            raise HTTPException(
                status_code=403,
                detail="Bot protection check failed. Please refresh the page and try again.",
            )

    except httpx.TimeoutException:
        logger.error("Turnstile API timeout (IP: %s)", client_ip)
        raise HTTPException(
            status_code=503,
            detail="Bot protection service is temporarily unavailable. Please try again in a moment.",
        )
    except httpx.HTTPError as e:
        logger.error("Turnstile API error: %s (IP: %s)", e, client_ip)
        raise HTTPException(
            status_code=503,
            detail="Bot protection service is temporarily unavailable. Please try again in a moment.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected Turnstile error: %s (IP: %s)", e, client_ip)
        raise HTTPException(
            status_code=503,
            detail="Bot protection service is temporarily unavailable. Please try again in a moment.",
        )
