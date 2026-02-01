"""Output validation guardrails for LLM-generated content.

This module validates LLM outputs before displaying to users or storing.
It checks for:
- Injection pattern leaks (LLM repeating injection attempts)
- AI self-references ("As an AI...")
- Unprofessional language and tone issues
- Instruction/refusal leaks

Usage:
    from guardrails.output_validators import validate_resume_output, sanitize_llm_output

    is_valid, warnings = validate_resume_output(generated_resume)
    if not is_valid:
        sanitized = sanitize_llm_output(generated_resume)
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OutputValidationResult:
    """Result of output validation with details."""

    is_valid: bool
    blocked_patterns: list[str]
    warnings: list[str]


# Patterns that should NEVER appear in resume output (block if found)
BLOCKED_OUTPUT_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+previous", "injection_leak"),
    (r"as\s+an?\s+(ai|language\s+model|assistant|llm)", "ai_self_reference"),
    (r"i\s+(cannot|can\'t|don\'t|won\'t)\s+(help|assist|do|provide)", "refusal_leak"),
    (r"\[?(system|user|assistant)\]?\s*:", "instruction_leak"),
    (r"i\'?m\s+(just\s+)?an?\s+(ai|bot|assistant)", "ai_self_reference"),
    (r"as\s+a\s+large\s+language\s+model", "ai_self_reference"),
    (r"my\s+programming\s+doesn\'?t\s+allow", "refusal_leak"),
    (r"i\s+was\s+(trained|programmed)\s+to", "ai_self_reference"),
    (r"(openai|anthropic|google)\s+(created|built|made)\s+me", "ai_self_reference"),
]

# Patterns that indicate unprofessional tone (warn but allow)
# Tuple: (pattern, reason, case_sensitive)
UNPROFESSIONAL_PATTERNS: list[tuple[str, str, bool]] = [
    (r"\b(obviously|clearly|simply|basically|just)\b", "condescending_language", False),
    (r"\b(stupid|dumb|idiotic|moronic)\b", "unprofessional_language", False),
    (r"!!+", "excessive_punctuation", False),
    (r"[A-Z]{8,}", "excessive_capitalization", True),  # Case-sensitive!
    (r"\b(lol|lmao|omg|wtf)\b", "informal_language", False),
    (r"!!!\s*$", "excessive_exclamation", False),
]


def validate_resume_output(content: str) -> tuple[bool, list[str]]:
    """Validate LLM-generated resume content.

    Checks for blocked patterns that should never appear in resumes
    (injection leaks, AI self-references) and warns about unprofessional
    language without blocking.

    Args:
        content: LLM-generated resume HTML or text.

    Returns:
        Tuple of (is_valid, list_of_warnings).
        is_valid is False if any blocked patterns found.
        warnings list contains descriptions of tone/style issues.

    Example:
        >>> is_valid, warnings = validate_resume_output("As an AI, I wrote...")
        >>> is_valid
        False
        >>> "ai_self_reference" in warnings[0].lower()
        True
    """
    if not content:
        return True, []

    warnings: list[str] = []
    is_valid = True

    # Check for blocked patterns (these invalidate output)
    for pattern, reason in BLOCKED_OUTPUT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            logger.error(f"Blocked pattern in output: {reason}")
            warnings.append(f"Blocked: {reason}")
            is_valid = False

    # Check for unprofessional patterns (warn but allow)
    for pattern, reason, case_sensitive in UNPROFESSIONAL_PATTERNS:
        flags = 0 if case_sensitive else re.IGNORECASE
        if re.search(pattern, content, flags):
            warnings.append(f"Style issue: {reason}")

    if not is_valid:
        logger.warning(
            f"Output validation failed: {len(warnings)} issues, "
            f"blocked patterns detected"
        )

    return is_valid, warnings


def validate_resume_output_detailed(content: str) -> OutputValidationResult:
    """Detailed validation with categorized results.

    Same as validate_resume_output but returns structured result object
    separating blocked patterns from warnings.

    Args:
        content: LLM-generated resume content.

    Returns:
        OutputValidationResult with is_valid, blocked_patterns, and warnings.
    """
    if not content:
        return OutputValidationResult(is_valid=True, blocked_patterns=[], warnings=[])

    blocked_patterns: list[str] = []
    warnings: list[str] = []

    # Check for blocked patterns
    for pattern, reason in BLOCKED_OUTPUT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            blocked_patterns.append(reason)

    # Check for unprofessional patterns
    for pattern, reason, case_sensitive in UNPROFESSIONAL_PATTERNS:
        flags = 0 if case_sensitive else re.IGNORECASE
        if re.search(pattern, content, flags):
            warnings.append(reason)

    is_valid = len(blocked_patterns) == 0

    if blocked_patterns:
        logger.warning(f"Output blocked: {blocked_patterns}")

    return OutputValidationResult(
        is_valid=is_valid,
        blocked_patterns=blocked_patterns,
        warnings=warnings,
    )


def sanitize_llm_output(content: str) -> str:
    """Remove problematic patterns from LLM output.

    Used as fallback when regeneration is not practical. Removes:
    - AI self-references
    - Instruction leaks
    - Refusal phrases

    The goal is to make output safe for display while preserving
    as much useful content as possible.

    Args:
        content: LLM-generated content to sanitize.

    Returns:
        Sanitized content with problematic patterns removed.

    Example:
        >>> sanitize_llm_output("As an AI assistant, here is the resume...")
        "here is the resume..."
    """
    if not content:
        return content

    # Remove AI self-references (entire sentences)
    patterns_to_remove = [
        r"(As an AI|I am an AI|As a language model)[^.!?]*[.!?]\s*",
        r"(I cannot|I can't|I don't|I won't)\s+(help|assist|do|provide)[^.!?]*[.!?]\s*",
        r"My programming (doesn't|does not) allow[^.!?]*[.!?]\s*",
        r"I was (trained|programmed) to[^.!?]*[.!?]\s*",
    ]

    result = content
    for pattern in patterns_to_remove:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    # Remove instruction leak markers
    result = re.sub(
        r"\[?(System|User|Assistant)\]?:\s*",
        "",
        result,
        flags=re.IGNORECASE,
    )

    # Clean up extra whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"  +", " ", result)

    return result.strip()


def contains_harmful_content(content: str) -> bool:
    """Quick check if content contains any blocked patterns.

    Convenience function for conditional logic without full validation.

    Args:
        content: Content to check.

    Returns:
        True if any blocked patterns detected, False otherwise.
    """
    if not content:
        return False

    for pattern, _ in BLOCKED_OUTPUT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return False
