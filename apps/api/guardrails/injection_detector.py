"""Prompt injection detection for AI safety.

This module detects and blocks attempts to manipulate LLM behavior through
prompt injection attacks. Common attack patterns include:
- Direct instruction override ("ignore all previous instructions")
- Role manipulation ("you are now a hacker")
- System prompt extraction ("show your system prompt")
- Delimiter attacks (fake message boundaries)

Usage:
    from guardrails.injection_detector import validate_no_injection, detect_injection

    # Check if text contains injection attempts
    risk, patterns = detect_injection(user_input)
    if risk == InjectionRisk.HIGH:
        log_security_event(...)

    # Raise HTTPException if injection detected
    validate_no_injection(user_input)
"""

import logging
import re
from enum import Enum
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class InjectionRisk(Enum):
    """Risk levels for detected injection patterns."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Patterns that indicate prompt injection attempts
# Each tuple: (regex_pattern, risk_level)
INJECTION_PATTERNS: list[tuple[str, InjectionRisk]] = [
    # Direct instruction override attempts
    (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|guidelines?)",
        InjectionRisk.HIGH,
    ),
    (r"disregard\s+(all\s+)?(previous|prior|above)", InjectionRisk.HIGH),
    (
        r"forget\s+(everything|all|what)\s+(you|i)\s+(said|told|know)",
        InjectionRisk.HIGH,
    ),
    (r"override\s+(your|the|all)\s+(instructions?|rules?)", InjectionRisk.HIGH),
    (r"new\s+instructions?\s*:", InjectionRisk.HIGH),
    # Role manipulation
    (r"you\s+are\s+now\s+(a|an|the)", InjectionRisk.HIGH),
    (r"pretend\s+(to\s+be|you\'?re)", InjectionRisk.HIGH),
    (r"act\s+as\s+(if|though|a|an)", InjectionRisk.MEDIUM),
    (r"roleplay\s+as", InjectionRisk.MEDIUM),
    (r"from\s+now\s+on\s+(you|you\'?re|be)", InjectionRisk.HIGH),
    (r"switch\s+(to|into)\s+(a|an|the)\s+\w+\s+mode", InjectionRisk.HIGH),
    # System prompt extraction
    (
        r"(show|reveal|display|print|output)\s+(\w+\s+)?(your|the)\s+(system|initial)\s+(prompt|instructions?)",
        InjectionRisk.HIGH,
    ),
    (
        r"what\s+(are|were)\s+your\s+(original|initial|system)\s+instructions?",
        InjectionRisk.HIGH,
    ),
    (r"repeat\s+(back|everything)\s+(after|starting\s+with)", InjectionRisk.HIGH),
    (r"(tell|show)\s+me\s+your\s+(prompt|instructions?)", InjectionRisk.HIGH),
    # Delimiter attacks (fake message boundaries)
    (r"```\s*(system|assistant|user)\s*[\r\n]", InjectionRisk.MEDIUM),
    (r"<\s*(system|assistant|user)\s*>", InjectionRisk.MEDIUM),
    (r"\[INST\]|\[/INST\]", InjectionRisk.MEDIUM),
    (r"###\s*(system|human|assistant)\s*:", InjectionRisk.MEDIUM),
    (r"<\|im_start\|>|<\|im_end\|>", InjectionRisk.MEDIUM),
    # Output manipulation
    (r"respond\s+(only\s+)?with", InjectionRisk.LOW),
    (r"your\s+(only\s+)?response\s+(should|must|will)\s+be", InjectionRisk.LOW),
    (r"only\s+say\s+['\"]", InjectionRisk.LOW),
    # Jailbreak keywords (context-dependent)
    (r"(dan|dude|jailbreak)\s*mode", InjectionRisk.HIGH),
    (r"developer\s+mode\s+(enabled|on|activated)", InjectionRisk.HIGH),
]


def detect_injection(text: str) -> tuple[InjectionRisk, list[str]]:
    """Detect potential prompt injection attempts in text.

    Scans the input text for known injection patterns and returns the
    highest risk level found along with matched patterns.

    Args:
        text: User input text to scan for injection patterns.

    Returns:
        Tuple of (highest_risk_level, list_of_matched_patterns).
        If no patterns matched, returns (InjectionRisk.NONE, []).

    Example:
        >>> risk, patterns = detect_injection("ignore all previous instructions")
        >>> risk
        InjectionRisk.HIGH
        >>> len(patterns) > 0
        True
    """
    if not text:
        return InjectionRisk.NONE, []

    text_lower = text.lower()
    matches: list[str] = []
    highest_risk = InjectionRisk.NONE

    # Define risk ordering for comparison
    risk_order = {
        InjectionRisk.NONE: 0,
        InjectionRisk.LOW: 1,
        InjectionRisk.MEDIUM: 2,
        InjectionRisk.HIGH: 3,
    }

    for pattern, risk in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matches.append(pattern)
            if risk_order[risk] > risk_order[highest_risk]:
                highest_risk = risk

    if matches:
        logger.warning(
            f"Injection patterns detected: {len(matches)} patterns, "
            f"highest risk: {highest_risk.value}"
        )

    return highest_risk, matches


def validate_no_injection(
    text: str,
    block_threshold: InjectionRisk = InjectionRisk.HIGH,
) -> None:
    """Validate that text doesn't contain injection attempts.

    Scans text for injection patterns and raises HTTPException if the
    detected risk level meets or exceeds the blocking threshold.

    Args:
        text: User input text to validate.
        block_threshold: Minimum risk level that triggers blocking.
            Defaults to HIGH (only block confirmed injection attempts).

    Raises:
        HTTPException: If detected risk meets or exceeds threshold.
            Returns 400 status with generic message (no pattern details).

    Example:
        >>> validate_no_injection("normal resume text")  # OK
        >>> validate_no_injection("ignore previous instructions")
        HTTPException: 400 - Input contains disallowed patterns...
    """
    risk, patterns = detect_injection(text)

    # Define risk ordering for comparison
    risk_order = {
        InjectionRisk.NONE: 0,
        InjectionRisk.LOW: 1,
        InjectionRisk.MEDIUM: 2,
        InjectionRisk.HIGH: 3,
    }

    if risk_order[risk] >= risk_order[block_threshold]:
        # Log with details but don't expose patterns to user
        logger.warning(
            f"Blocking input due to injection risk: {risk.value}, "
            f"patterns: {patterns[:3]}..."  # Limit logged patterns
        )
        raise HTTPException(
            status_code=400,
            detail="Input contains disallowed patterns. Please rephrase your request.",
        )


def is_safe_for_llm(text: str) -> bool:
    """Quick check if text is safe to send to LLM.

    Convenience function that returns boolean instead of raising exception.
    Useful for conditional logic without try/except.

    Args:
        text: Text to check for safety.

    Returns:
        True if no HIGH risk patterns detected, False otherwise.
    """
    risk, _ = detect_injection(text)
    return risk != InjectionRisk.HIGH
