"""Bias detection for AI-generated resume content.

This module detects potentially biased language that could indicate
discrimination based on protected characteristics. Critical for legal
compliance with AI hiring regulations (e.g., California AB-5, NYC LL 144).

Categories of bias detected:
- Age discrimination (young/old, digital native, seasoned)
- Gender bias (gendered job titles, pronouns)
- Race/ethnicity (cultural fit, native speaker)
- Disability discrimination (physically fit, able-bodied)
- Nationality/citizenship requirements

Usage:
    from guardrails.bias_detector import detect_bias, format_bias_warnings

    flags = detect_bias(resume_content)
    if flags:
        warnings = format_bias_warnings(flags)
        # Return warnings in API response
"""

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BiasCategory(Enum):
    """Categories of potential bias."""

    AGE = "age"
    GENDER = "gender"
    RACE_ETHNICITY = "race_ethnicity"
    DISABILITY = "disability"
    RELIGION = "religion"
    NATIONALITY = "nationality"


@dataclass
class BiasFlag:
    """Detected bias indicator with context."""

    category: BiasCategory
    term: str
    context: str
    severity: str  # "warning" or "block"
    suggestion: str | None = None


# Bias indicator terms organized by category and severity
# Format: (term, reason, suggested_alternative_or_None)
BIAS_INDICATORS: dict[BiasCategory, dict[str, list[tuple[str, str, str | None]]]] = {
    BiasCategory.AGE: {
        "warning": [
            ("digital native", "May exclude older candidates", "tech-savvy"),
            ("young and energetic", "Age-discriminatory", "motivated and energetic"),
            ("recent graduate energy", "Age-discriminatory", "enthusiastic"),
            (
                "seasoned veteran",
                "May imply age preference",
                "experienced professional",
            ),
            ("young professional", "Age-discriminatory", "emerging professional"),
            ("old school", "Age-related stereotype", None),
            ("fresh perspective", "May imply youth preference", "innovative perspective"),
            ("dynamic young", "Age-discriminatory", "dynamic"),
            ("energetic youth", "Age-discriminatory", "energetic individual"),
            ("mature professional", "Age-specific", "experienced professional"),
        ],
        "block": [
            ("must be under", "Illegal age discrimination", None),
            ("must be over", "Illegal age discrimination", None),
            ("years old", "Age specification may be discriminatory", None),
            ("age requirement", "Illegal age discrimination", None),
        ],
    },
    BiasCategory.GENDER: {
        "warning": [
            ("manpower", "Gendered language", "workforce"),
            ("chairman", "Gendered language", "chairperson"),
            ("mankind", "Gendered language", "humanity"),
            ("he/she", "Binary assumption", "they"),
            ("salesman", "Gendered language", "sales representative"),
            ("manmade", "Gendered language", "artificial"),
            ("fireman", "Gendered language", "firefighter"),
            ("policeman", "Gendered language", "police officer"),
            ("stewardess", "Gendered language", "flight attendant"),
            ("waitress", "Gendered language", "server"),
            ("businessman", "Gendered language", "business professional"),
            ("foreman", "Gendered language", "supervisor"),
        ],
        "block": [],
    },
    BiasCategory.RACE_ETHNICITY: {
        "warning": [
            (
                "native speaker",
                "May exclude qualified non-native speakers",
                "fluent in",
            ),
            (
                "cultural fit",
                "Often used as proxy for discrimination",
                "alignment with company values",
            ),
            (
                "professional appearance",
                "Subjective and potentially discriminatory",
                None,
            ),
            (
                "good english",
                "May be discriminatory",
                "strong English communication skills",
            ),
        ],
        "block": [],
    },
    BiasCategory.DISABILITY: {
        "warning": [
            ("physically fit", "May exclude disabled candidates", None),
            ("able-bodied", "Discriminatory language", None),
            ("standing required", "May exclude without reasonable accommodation", None),
            ("must be able to lift", "Consider essential functions test", None),
            ("clean driving record", "May exclude those unable to drive", None),
        ],
        "block": [],
    },
    BiasCategory.NATIONALITY: {
        "warning": [
            (
                "us citizen only",
                "May be discriminatory unless for security clearance",
                "authorized to work in the US",
            ),
            ("american only", "Discriminatory", None),
            (
                "must be citizen",
                "May be discriminatory unless legally required",
                "work authorization required",
            ),
        ],
        "block": [],
    },
    BiasCategory.RELIGION: {
        "warning": [
            (
                "christian values",
                "Religious preference in hiring",
                "ethical values",
            ),
            ("faith-based", "May exclude non-religious candidates", None),
        ],
        "block": [],
    },
}


def detect_bias(text: str) -> list[BiasFlag]:
    """Detect potentially biased language in text.

    Scans text for terms that may indicate discrimination based on
    protected characteristics. Returns list of flags with context
    and suggested alternatives where available.

    Args:
        text: Text to analyze for bias indicators.

    Returns:
        List of BiasFlag objects, empty if no bias detected.

    Example:
        >>> flags = detect_bias("Looking for young and energetic candidate")
        >>> len(flags) > 0
        True
        >>> flags[0].category
        BiasCategory.AGE
    """
    if not text:
        return []

    flags: list[BiasFlag] = []
    text_lower = text.lower()

    for category, severity_dict in BIAS_INDICATORS.items():
        for severity, patterns in severity_dict.items():
            for pattern_tuple in patterns:
                term = pattern_tuple[0]
                reason = pattern_tuple[1]
                suggestion = pattern_tuple[2] if len(pattern_tuple) > 2 else None

                if term.lower() in text_lower:
                    # Extract context (surrounding text for display)
                    idx = text_lower.find(term.lower())
                    start = max(0, idx - 30)
                    end = min(len(text), idx + len(term) + 30)
                    context = text[start:end]

                    flags.append(
                        BiasFlag(
                            category=category,
                            term=term,
                            context=f"...{context}...",
                            severity=severity,
                            suggestion=suggestion,
                        )
                    )

    if flags:
        logger.info(
            f"Bias indicators detected: {len(flags)} flags in "
            f"{len(set(f.category for f in flags))} categories"
        )

    return flags


def format_bias_warnings(flags: list[BiasFlag]) -> list[dict]:
    """Format bias flags for API response.

    Converts internal BiasFlag objects to JSON-serializable dicts
    with human-readable messages for frontend display.

    Args:
        flags: List of BiasFlag objects from detect_bias().

    Returns:
        List of dicts with category, term, message, suggestion, severity.
    """
    return [
        {
            "category": f.category.value,
            "term": f.term,
            "context": f.context,
            "severity": f.severity,
            "suggestion": f.suggestion,
            "message": (
                f"'{f.term}' may indicate {f.category.value.replace('_', ' ')} bias. "
                f"Consider: {f.suggestion}"
                if f.suggestion
                else f"'{f.term}' may indicate {f.category.value.replace('_', ' ')} bias."
            ),
        }
        for f in flags
    ]


def has_blocking_bias(flags: list[BiasFlag]) -> bool:
    """Check if any bias flags are severe enough to block output.

    Args:
        flags: List of bias flags from detect_bias().

    Returns:
        True if any flags have severity="block", False otherwise.
    """
    return any(f.severity == "block" for f in flags)


