"""Security audit logging for guardrail events.

This module provides structured logging for security-relevant events
to support monitoring, alerting, and forensic analysis.

Events logged:
- Injection attempts (blocked and warned)
- Content flags (toxic, inappropriate)
- PII detection
- Bias flags
- Rate limit hits
- Output sanitization

Usage:
    from guardrails.audit_logger import log_security_event, SecurityEventType

    log_security_event(
        event_type=SecurityEventType.INJECTION_ATTEMPT,
        thread_id=thread_id,
        details={"patterns": patterns},
        blocked=True,
    )
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# Configure dedicated security logger
# This allows security events to be routed to a separate log file/stream
security_logger = logging.getLogger("security.audit")
security_logger.setLevel(logging.INFO)


class SecurityEventType(Enum):
    """Types of security events that are logged."""

    # Input validation events
    INJECTION_ATTEMPT = "injection_attempt"
    INPUT_SIZE_EXCEEDED = "input_size_exceeded"
    CONTENT_FLAGGED = "content_flagged"

    # PII events
    PII_DETECTED = "pii_detected"
    PII_REDACTED = "pii_redacted"

    # Output validation events
    BIAS_FLAGGED = "bias_flagged"
    OUTPUT_SANITIZED = "output_sanitized"
    CLAIM_UNGROUNDED = "claim_ungrounded"

    # Rate limiting
    RATE_LIMIT_HIT = "rate_limit_hit"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # General
    VALIDATION_FAILED = "validation_failed"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class Severity(Enum):
    """Severity levels for security events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Structured security event for logging."""

    event_type: str
    timestamp: str
    thread_id: str | None
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any]
    severity: str
    blocked: bool


def log_security_event(
    event_type: SecurityEventType,
    thread_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
    severity: Severity = Severity.WARNING,
    blocked: bool = False,
) -> None:
    """Log a security event with structured data.

    Events are logged as JSON for easy parsing by log aggregation systems.

    Args:
        event_type: Category of security event.
        thread_id: Optional session/workflow ID.
        ip_address: Optional client IP address.
        user_agent: Optional client user agent.
        details: Optional dict with event-specific details.
        severity: Log level for this event.
        blocked: Whether the action was blocked.

    Example:
        >>> log_security_event(
        ...     SecurityEventType.INJECTION_ATTEMPT,
        ...     thread_id="abc-123",
        ...     details={"patterns": ["ignore previous"]},
        ...     blocked=True,
        ... )
    """
    event = SecurityEvent(
        event_type=event_type.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
        thread_id=thread_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {},
        severity=severity.value,
        blocked=blocked,
    )

    # Convert to JSON for structured logging
    log_entry = asdict(event)

    # Get appropriate log level
    log_level = getattr(logging, severity.value.upper(), logging.WARNING)

    security_logger.log(log_level, json.dumps(log_entry))


# Convenience functions for common events


def log_injection_attempt(
    thread_id: str | None = None,
    patterns: list[str] | None = None,
    risk_level: str = "high",
    ip_address: str | None = None,
    blocked: bool = True,
) -> None:
    """Log a prompt injection attempt.

    Args:
        thread_id: Session ID.
        patterns: List of matched injection patterns.
        risk_level: Injection risk level (low/medium/high).
        ip_address: Client IP.
        blocked: Whether the request was blocked.
    """
    log_security_event(
        SecurityEventType.INJECTION_ATTEMPT,
        thread_id=thread_id,
        ip_address=ip_address,
        details={
            "patterns": patterns or [],
            "pattern_count": len(patterns or []),
            "risk_level": risk_level,
        },
        severity=Severity.WARNING if blocked else Severity.INFO,
        blocked=blocked,
    )


def log_pii_detection(
    thread_id: str | None = None,
    pii_types: list[str] | None = None,
    redacted: bool = False,
    location: str = "input",
) -> None:
    """Log PII detection event.

    Args:
        thread_id: Session ID.
        pii_types: List of PII types detected (e.g., ["ssn", "credit_card"]).
        redacted: Whether the PII was redacted.
        location: Where PII was detected ("input" or "output").
    """
    log_security_event(
        SecurityEventType.PII_REDACTED if redacted else SecurityEventType.PII_DETECTED,
        thread_id=thread_id,
        details={
            "pii_types": pii_types or [],
            "count": len(pii_types or []),
            "location": location,
            "redacted": redacted,
        },
        severity=Severity.WARNING if not redacted else Severity.INFO,
        blocked=False,
    )


def log_bias_flag(
    thread_id: str | None = None,
    categories: list[str] | None = None,
    terms: list[str] | None = None,
    blocking: bool = False,
) -> None:
    """Log bias detection event.

    Args:
        thread_id: Session ID.
        categories: List of bias categories (e.g., ["age", "gender"]).
        terms: List of specific terms flagged.
        blocking: Whether the content was blocked (vs. warned).
    """
    log_security_event(
        SecurityEventType.BIAS_FLAGGED,
        thread_id=thread_id,
        details={
            "categories": categories or [],
            "terms": terms or [],
            "category_count": len(categories or []),
            "term_count": len(terms or []),
        },
        severity=Severity.WARNING if blocking else Severity.INFO,
        blocked=blocking,
    )


def log_output_sanitized(
    thread_id: str | None = None,
    patterns_removed: list[str] | None = None,
) -> None:
    """Log when LLM output was sanitized.

    Args:
        thread_id: Session ID.
        patterns_removed: List of pattern types that were removed.
    """
    log_security_event(
        SecurityEventType.OUTPUT_SANITIZED,
        thread_id=thread_id,
        details={
            "patterns_removed": patterns_removed or [],
            "count": len(patterns_removed or []),
        },
        severity=Severity.WARNING,
        blocked=False,  # Sanitization means we fixed it, not blocked
    )


def log_rate_limit(
    ip_address: str | None = None,
    limit_type: str = "request",
    current_count: int = 0,
    max_allowed: int = 0,
    exceeded: bool = False,
) -> None:
    """Log rate limit event.

    Args:
        ip_address: Client IP address.
        limit_type: Type of limit (e.g., "request", "token").
        current_count: Current request/token count.
        max_allowed: Maximum allowed.
        exceeded: Whether limit was exceeded.
    """
    log_security_event(
        SecurityEventType.RATE_LIMIT_EXCEEDED if exceeded else SecurityEventType.RATE_LIMIT_HIT,
        ip_address=ip_address,
        details={
            "limit_type": limit_type,
            "current_count": current_count,
            "max_allowed": max_allowed,
            "exceeded": exceeded,
        },
        severity=Severity.WARNING if exceeded else Severity.INFO,
        blocked=exceeded,
    )


def log_content_flagged(
    thread_id: str | None = None,
    reason: str = "",
    content_preview: str = "",
    blocked: bool = False,
) -> None:
    """Log when content is flagged for review.

    Args:
        thread_id: Session ID.
        reason: Why the content was flagged.
        content_preview: First N chars of content (for context).
        blocked: Whether the content was blocked.
    """
    # Truncate preview to avoid logging sensitive data
    preview = content_preview[:100] + "..." if len(content_preview) > 100 else content_preview

    log_security_event(
        SecurityEventType.CONTENT_FLAGGED,
        thread_id=thread_id,
        details={
            "reason": reason,
            "preview": preview,
        },
        severity=Severity.WARNING,
        blocked=blocked,
    )
