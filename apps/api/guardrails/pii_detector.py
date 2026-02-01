"""PII (Personally Identifiable Information) detection for resume content.

This module detects sensitive PII that should not appear in resumes,
while allowing resume-appropriate contact information.

Resume-appropriate PII (allowed):
- Name
- Email address
- Phone number
- Location (city/state)
- LinkedIn URL
- Portfolio URL

Sensitive PII (flagged/redacted):
- Social Security Number (SSN)
- Credit card numbers
- Bank account numbers
- Driver's license numbers
- Passport numbers
- Date of birth (age discrimination risk)

Usage:
    from guardrails.pii_detector import detect_pii, redact_sensitive_pii

    pii_items = detect_pii(resume_text)
    if any(p["is_sensitive"] for p in pii_items):
        redacted, redactions = redact_sensitive_pii(resume_text)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""

    # Resume-appropriate (allowed)
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    LOCATION = "location"

    # Sensitive (should be flagged/redacted)
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"


@dataclass
class PIIMatch:
    """Detected PII with location and metadata."""

    pii_type: PIIType
    text: str
    start: int
    end: int
    is_sensitive: bool
    confidence: float  # 0-1, how confident we are this is real PII


# PII types that are allowed in resumes
RESUME_ALLOWED_PII = {
    PIIType.EMAIL,
    PIIType.PHONE,
    PIIType.URL,
    PIIType.LOCATION,
}

# PII types that should be flagged/redacted
SENSITIVE_PII = {
    PIIType.SSN,
    PIIType.CREDIT_CARD,
    PIIType.BANK_ACCOUNT,
    PIIType.DRIVERS_LICENSE,
    PIIType.PASSPORT,
    PIIType.DATE_OF_BIRTH,
    PIIType.IP_ADDRESS,
}

# Regex patterns for detecting PII
# Format: (pattern, pii_type, confidence)
PII_PATTERNS: list[tuple[str, PIIType, float]] = [
    # SSN patterns (high confidence)
    (r"\b\d{3}-\d{2}-\d{4}\b", PIIType.SSN, 0.95),
    (r"\b\d{3}\s\d{2}\s\d{4}\b", PIIType.SSN, 0.9),
    (r"\bSSN[:\s]*\d{9}\b", PIIType.SSN, 0.95),

    # Credit card patterns (high confidence)
    # Visa, Mastercard, Amex, Discover
    (r"\b4[0-9]{12}(?:[0-9]{3})?\b", PIIType.CREDIT_CARD, 0.9),  # Visa
    (r"\b5[1-5][0-9]{14}\b", PIIType.CREDIT_CARD, 0.9),  # Mastercard
    (r"\b3[47][0-9]{13}\b", PIIType.CREDIT_CARD, 0.9),  # Amex
    (r"\b6(?:011|5[0-9]{2})[0-9]{12}\b", PIIType.CREDIT_CARD, 0.9),  # Discover
    # Generic card with dashes/spaces
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", PIIType.CREDIT_CARD, 0.7),

    # Bank account (medium confidence - could be other numbers)
    (r"\b(?:account|acct)[:\s#]*\d{8,17}\b", PIIType.BANK_ACCOUNT, 0.8),
    (r"\b(?:routing)[:\s#]*\d{9}\b", PIIType.BANK_ACCOUNT, 0.85),

    # Driver's license (varies by state, medium confidence)
    (r"\b(?:DL|driver'?s?\s*license)[:\s#]*[A-Z]?\d{7,8}\b", PIIType.DRIVERS_LICENSE, 0.75),

    # Passport (medium confidence)
    (r"\b(?:passport)[:\s#]*[A-Z]?\d{6,9}\b", PIIType.PASSPORT, 0.8),

    # Date of birth (medium confidence - could be other dates)
    (r"\b(?:DOB|date\s*of\s*birth|born|birthday)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", PIIType.DATE_OF_BIRTH, 0.85),
    (r"\b(?:DOB|date\s*of\s*birth)[:\s]*\w+\s+\d{1,2},?\s+\d{4}\b", PIIType.DATE_OF_BIRTH, 0.85),

    # IP address (low confidence in resume context)
    (r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", PIIType.IP_ADDRESS, 0.6),

    # Email (allowed but detected for completeness)
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", PIIType.EMAIL, 0.95),

    # Phone (allowed but detected for completeness)
    (r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", PIIType.PHONE, 0.85),

    # URLs (allowed - LinkedIn, portfolio)
    (r"https?://[^\s<>\"{}|\\^`\[\]]+", PIIType.URL, 0.95),
]


def detect_pii(
    text: str,
    include_allowed: bool = False,
    min_confidence: float = 0.5,
) -> list[dict]:
    """Detect PII in text.

    Scans for both sensitive PII (SSN, credit cards) and resume-appropriate
    PII (email, phone). By default only returns sensitive PII.

    Args:
        text: Text to scan for PII.
        include_allowed: If True, also return resume-allowed PII types.
        min_confidence: Minimum confidence threshold (0-1) to include match.

    Returns:
        List of dicts with type, text, start, end, is_sensitive, confidence.

    Example:
        >>> pii = detect_pii("My SSN is 123-45-6789")
        >>> len(pii)
        1
        >>> pii[0]["type"]
        'ssn'
        >>> pii[0]["is_sensitive"]
        True
    """
    if not text:
        return []

    detected: list[dict] = []
    seen_positions: set[tuple[int, int]] = set()  # Avoid duplicates

    for pattern, pii_type, confidence in PII_PATTERNS:
        if confidence < min_confidence:
            continue

        is_sensitive = pii_type in SENSITIVE_PII

        # Skip allowed types unless explicitly requested
        if not include_allowed and not is_sensitive:
            continue

        for match in re.finditer(pattern, text, re.IGNORECASE):
            pos = (match.start(), match.end())
            if pos in seen_positions:
                continue
            seen_positions.add(pos)

            detected.append({
                "type": pii_type.value,
                "text": match.group(),
                "start": match.start(),
                "end": match.end(),
                "is_sensitive": is_sensitive,
                "confidence": confidence,
            })

    if detected:
        sensitive_count = sum(1 for d in detected if d["is_sensitive"])
        logger.info(
            f"Detected {len(detected)} PII items "
            f"({sensitive_count} sensitive)"
        )

    return detected


def redact_sensitive_pii(text: str) -> tuple[str, list[dict]]:
    """Redact only sensitive PII, keeping resume-appropriate info.

    Replaces sensitive PII (SSN, credit cards, etc.) with redaction
    markers while preserving email, phone, and other contact info.

    Args:
        text: Text to redact.

    Returns:
        Tuple of (redacted_text, list_of_redactions).
        Each redaction dict has type, original_text.

    Example:
        >>> redacted, items = redact_sensitive_pii("SSN: 123-45-6789")
        >>> "123-45-6789" in redacted
        False
        >>> "[REDACTED-SSN]" in redacted
        True
    """
    if not text:
        return text, []

    # Detect only sensitive PII
    pii_items = detect_pii(text, include_allowed=False)

    if not pii_items:
        return text, []

    # Sort by position descending so we can replace without offset issues
    pii_items.sort(key=lambda x: x["start"], reverse=True)

    redactions: list[dict] = []
    result = text

    for item in pii_items:
        pii_type = item["type"].upper()
        redaction_marker = f"[REDACTED-{pii_type}]"

        result = result[:item["start"]] + redaction_marker + result[item["end"]:]

        redactions.append({
            "type": item["type"],
            "original": item["text"],
            "confidence": item["confidence"],
        })

    logger.info(f"Redacted {len(redactions)} sensitive PII items")

    return result, redactions


def has_sensitive_pii(text: str) -> bool:
    """Quick check if text contains any sensitive PII.

    Args:
        text: Text to check.

    Returns:
        True if sensitive PII detected, False otherwise.
    """
    pii_items = detect_pii(text, include_allowed=False)
    return len(pii_items) > 0


def get_pii_summary(pii_items: list[dict]) -> dict[str, int]:
    """Get count of PII by type.

    Args:
        pii_items: List of PII items from detect_pii().

    Returns:
        Dict mapping type name to count.
    """
    counts: dict[str, int] = {}
    for item in pii_items:
        pii_type = item["type"]
        counts[pii_type] = counts.get(pii_type, 0) + 1
    return counts


def format_pii_warnings(pii_items: list[dict]) -> list[dict]:
    """Format PII items for API response.

    Args:
        pii_items: List of PII items from detect_pii().

    Returns:
        List of formatted warning dicts for frontend display.
    """
    warnings = []
    for item in pii_items:
        if item["is_sensitive"]:
            # Partially mask the sensitive data for display
            original = item["text"]
            if len(original) > 4:
                masked = original[:2] + "*" * (len(original) - 4) + original[-2:]
            else:
                masked = "*" * len(original)

            warnings.append({
                "type": item["type"],
                "masked_value": masked,
                "severity": "high" if item["confidence"] > 0.8 else "medium",
                "message": f"Sensitive {item['type'].upper()} detected. "
                          f"This should not appear in a resume.",
            })

    return warnings
