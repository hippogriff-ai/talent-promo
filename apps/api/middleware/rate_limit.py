"""IP-based rate limiting for abuse prevention.

Simple in-memory rate limiter that tracks requests per IP address.
Uses a sliding window approach with configurable limits.
Also enforces a global daily limit across all users.
"""

import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Tuple

# Configuration
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "3"))  # Max requests per IP per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "86400"))  # Window in seconds (default: 24h)
GLOBAL_DAILY_LIMIT = int(os.getenv("GLOBAL_DAILY_LIMIT", "30"))  # Max total requests per day

# In-memory storage for rate limits
# Format: {ip: [(timestamp1, timestamp2, ...)]}
_rate_limits: dict[str, list[float]] = defaultdict(list)

# Global request counter (all IPs combined)
_global_requests: list[float] = []


# IPs that bypass rate limiting (localhost/development/testing)
BYPASS_IPS = {"127.0.0.1", "::1", "localhost", "testclient", "unknown"}


def check_rate_limit(client_ip: str) -> Tuple[bool, int, int]:
    """Check if a client IP is within rate limits.

    Checks both per-IP limit and global daily limit.
    Localhost IPs bypass rate limiting entirely.

    Args:
        client_ip: The client's IP address

    Returns:
        Tuple of (allowed: bool, remaining: int, reset_seconds: int)
        - allowed: True if request is allowed
        - remaining: Number of requests remaining in window
        - reset_seconds: Seconds until rate limit resets (0 if not exceeded)
    """
    global _global_requests

    # Bypass rate limiting for localhost/development
    if client_ip in BYPASS_IPS:
        return True, 999, 0

    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Check global daily limit first
    _global_requests = [ts for ts in _global_requests if ts > window_start]

    if len(_global_requests) >= GLOBAL_DAILY_LIMIT:
        oldest_global = min(_global_requests)
        reset_time = int(oldest_global + RATE_LIMIT_WINDOW - now)
        return False, 0, max(1, reset_time)

    # Get request timestamps for this IP, filtering out old ones
    timestamps = _rate_limits[client_ip]
    timestamps = [ts for ts in timestamps if ts > window_start]
    _rate_limits[client_ip] = timestamps

    # Check if under per-IP limit
    if len(timestamps) < RATE_LIMIT_REQUESTS:
        # Add current request to both IP and global trackers
        timestamps.append(now)
        _rate_limits[client_ip] = timestamps
        _global_requests.append(now)

        remaining = RATE_LIMIT_REQUESTS - len(timestamps)
        return True, remaining, 0

    # Per-IP rate limit exceeded
    oldest_request = min(timestamps)
    reset_time = int(oldest_request + RATE_LIMIT_WINDOW - now)

    return False, 0, max(1, reset_time)


def get_rate_limit_status(client_ip: str) -> dict:
    """Get current rate limit status for an IP.

    Args:
        client_ip: The client's IP address

    Returns:
        Dict with rate limit info
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    timestamps = [ts for ts in _rate_limits.get(client_ip, []) if ts > window_start]

    return {
        "ip": client_ip,
        "requests_used": len(timestamps),
        "requests_limit": RATE_LIMIT_REQUESTS,
        "requests_remaining": max(0, RATE_LIMIT_REQUESTS - len(timestamps)),
        "window_seconds": RATE_LIMIT_WINDOW,
    }


def reset_rate_limit(client_ip: str) -> bool:
    """Reset rate limit for a specific IP (for admin use).

    Args:
        client_ip: The client's IP address

    Returns:
        True if reset, False if IP wasn't in rate limit storage
    """
    if client_ip in _rate_limits:
        del _rate_limits[client_ip]
        return True
    return False


def cleanup_old_entries() -> int:
    """Clean up expired rate limit entries (for memory management).

    Returns:
        Number of IPs removed
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    removed = 0
    for ip in list(_rate_limits.keys()):
        timestamps = [ts for ts in _rate_limits[ip] if ts > window_start]
        if not timestamps:
            del _rate_limits[ip]
            removed += 1
        else:
            _rate_limits[ip] = timestamps

    return removed
