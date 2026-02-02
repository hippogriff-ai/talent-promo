"""Content safety moderation for user inputs.

This module detects inappropriate, violent, or abusive content that
should not appear in a professional resume optimization context.

It uses lightweight regex patterns (no external dependencies) to flag:
- Violence and threats
- Hate speech and slurs
- Illegal activity references
- Explicit sexual content
- Self-harm content

The patterns are tuned for resume/professional contexts to minimize
false positives (e.g., "kill process" in tech is fine, but "kill you"
is not).

Usage:
    from guardrails.content_moderator import check_content_safety

    is_safe, reason = check_content_safety(user_input)
    if not is_safe:
        raise HTTPException(400, detail=reason)
"""

import logging
import re

logger = logging.getLogger(__name__)


# Professional/technical terms that look like blocked words but are safe
# These are checked BEFORE blocked patterns to avoid false positives
SAFE_PROFESSIONAL_CONTEXTS = [
    r"kill\s+(?:process|switch|signal|command|chain|shot|fee|time)",
    r"attack\s+(?:surface|vector|model|pattern|scenario|tree)",
    r"bomb\s+(?:threat\s+detection|disposal|squad|defusal|sniffing)",
    r"threat\s+(?:model|assessment|detection|intelligence|landscape|analysis|mitigation|management|hunting|vector)",
    r"exploit\s+(?:kit|chain|mitigation|prevention|detection|analysis|database)",
    r"target\s+(?:audience|market|group|demographic|customer|user|segment|date)",
    r"execute\s+(?:command|query|script|code|function|task|order|plan|strategy)",
    r"terminate\s+(?:process|connection|session|thread|instance|contract|employment)",
    r"abuse\s+(?:detection|prevention|reporting|case|policy|team)",
    r"suicide\s+(?:prevention|hotline|awareness|intervention)",
    r"drug\s+(?:test|testing|screening|development|discovery|trial|administration|interaction)",
    r"crack\s+(?:down|the\s+code|under\s+pressure)",
    r"offensive\s+(?:security|testing|operations)",
    r"penetration\s+(?:test|testing|tester)",
    r"race\s+(?:condition|car|track)",
    r"master\s+(?:slave|degree|plan|class|node|branch)",
    r"slave\s+(?:node|server|database|process)",
    r"injection\s+(?:attack|prevention|detection|vulnerability|molding|site)",
    r"fire\s+(?:wall|base|fox|drill|department|safety|fighting|proof|side|store|station)",
    r"shoot\s+(?:for|out|off|up\s+(?:an?\s+)?email)",
    r"hit\s+(?:rate|count|ratio|target|milestone|deadline|goal)",
    r"dead\s+(?:lock|line|letter|code|end|zone)",
    r"hostile\s+(?:takeover|environment\s+(?:testing|detection))",
]

# Blocked content patterns - these indicate genuinely inappropriate content
# Each tuple: (compiled_regex_pattern_string, category, description)
BLOCKED_PATTERNS: list[tuple[str, str, str]] = [
    # Violence/threats toward people
    (
        r"\b(?:i(?:'ll|will)\s+)?kill\s+(?:you|him|her|them|that\s+(?:person|guy|man|woman))",
        "violence",
        "Threats of violence",
    ),
    (
        r"\b(?:i(?:'ll|will)\s+)?(?:murder|assassinate|stab|strangle|shoot)\s+(?:you|him|her|them|someone|people)",
        "violence",
        "Threats of violence",
    ),
    (
        r"\b(?:death|bomb)\s+threat",
        "violence",
        "Threats of violence",
    ),
    (
        r"\bmake\s+(?:a\s+)?(?:bomb|explosive|weapon)",
        "violence",
        "Weapon creation instructions",
    ),
    (
        r"\bhow\s+to\s+(?:kill|murder|harm|poison|attack)\s+(?:a\s+)?(?:person|someone|people)",
        "violence",
        "Violence instructions",
    ),

    # Hate speech patterns
    (
        r"\b(?:hate|racist|sexist|homophobic|transphobic)\s+(?:speech|content|rhetoric|propaganda)",
        "hate_speech",
        "Hate speech",
    ),
    (
        r"\b(?:white|black|jewish|muslim|asian)\s+(?:supremac|inferior|should\s+(?:die|be\s+killed))",
        "hate_speech",
        "Hate speech / supremacist content",
    ),
    (
        r"\b(?:ethnic|racial)\s+cleansing",
        "hate_speech",
        "Hate speech",
    ),
    (
        r"\bgenocide\s+(?:is\s+)?(?:good|necessary|justified)",
        "hate_speech",
        "Hate speech",
    ),

    # Illegal activity
    (
        r"\b(?:how\s+to\s+)?(?:cook|make|manufacture|produce|synthesize)\s+(?:meth|cocaine|heroin|fentanyl|crystal)",
        "illegal",
        "Drug manufacturing",
    ),
    (
        r"\b(?:buy|sell|traffic)\s+(?:illegal\s+)?(?:drugs?|narcotics|cocaine|heroin|meth)",
        "illegal",
        "Drug trafficking",
    ),
    (
        r"\b(?:how\s+to\s+)?(?:launder|laundering)\s+money",
        "illegal",
        "Money laundering",
    ),
    (
        r"\b(?:how\s+to\s+)?(?:hack|breach|break\s+into)\s+(?:a\s+)?(?:bank|account|system|server|database|network)\b",
        "illegal",
        "Unauthorized access instructions",
    ),
    (
        r"\b(?:steal|forge|counterfeit)\s+(?:identity|identities|passport|credentials|credit\s+card)",
        "illegal",
        "Identity theft / fraud",
    ),

    # Explicit sexual content
    (
        r"\b(?:graphic|explicit)\s+(?:sexual|pornographic)\s+(?:content|material|description)",
        "sexual",
        "Explicit sexual content",
    ),

    # Self-harm (not blocking awareness/prevention - just instructions/encouragement)
    (
        r"\bhow\s+to\s+(?:commit\s+)?suicide\b",
        "self_harm",
        "Self-harm instructions",
    ),
    (
        r"\b(?:you\s+should|go\s+)(?:kill|harm)\s+yourself",
        "self_harm",
        "Self-harm encouragement",
    ),
    (
        r"\b(?:cutting|hurting)\s+yourself\s+(?:is|feels)\s+(?:good|great|nice)",
        "self_harm",
        "Self-harm encouragement",
    ),
]

# Compile patterns once at import time
_SAFE_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in SAFE_PROFESSIONAL_CONTEXTS]
_BLOCKED_PATTERNS_COMPILED = [
    (re.compile(p, re.IGNORECASE), cat, desc)
    for p, cat, desc in BLOCKED_PATTERNS
]


def check_content_safety(text: str) -> tuple[bool, str | None]:
    """Check if text content is safe for the platform.

    Scans for violent, hateful, illegal, or otherwise inappropriate
    content that has no place in a professional resume context.

    Professional/technical terms that look like blocked words are
    excluded to prevent false positives (e.g., "kill process",
    "attack surface", "penetration testing").

    Args:
        text: User input text to check.

    Returns:
        Tuple of (is_safe, reason_if_unsafe).
        is_safe is True if content passes all checks.
        reason_if_unsafe is None when safe, otherwise a description.

    Example:
        >>> check_content_safety("Experienced software engineer")
        (True, None)
        >>> is_safe, reason = check_content_safety("I will kill you")
        >>> is_safe
        False
    """
    if not text:
        return True, None

    text_lower = text.lower()

    # First, find all safe professional contexts and mask them
    # so they don't trigger blocked patterns
    masked_text = text_lower
    for safe_pattern in _SAFE_PATTERNS_COMPILED:
        masked_text = safe_pattern.sub("__SAFE__", masked_text)

    # Check blocked patterns against the masked text
    for pattern, category, description in _BLOCKED_PATTERNS_COMPILED:
        if pattern.search(masked_text):
            logger.warning(
                f"Content safety violation: category={category}, "
                f"description={description}"
            )
            return False, f"Content flagged: {description}"

    return True, None


def validate_content_safety(text: str) -> None:
    """Validate content safety, raising HTTPException if unsafe.

    Convenience function that raises instead of returning a tuple.
    Used in API endpoint handlers for cleaner code.

    Args:
        text: User input text to validate.

    Raises:
        HTTPException: 400 if content is flagged as unsafe.
    """
    is_safe, reason = check_content_safety(text)
    if not is_safe:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="Content flagged for review. Please ensure your input "
            "is professional and appropriate.",
        )
