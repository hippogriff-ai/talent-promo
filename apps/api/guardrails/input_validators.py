"""Input validation guardrails for size limits and basic safety checks.

This module provides input size validation to prevent:
- DoS attacks via oversized inputs
- Cost explosions from excessive token usage
- Memory issues from unbounded input processing
"""

import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Configuration - character limits
MAX_RESUME_CHARS = 50000      # ~12,500 tokens
MAX_JOB_DESC_CHARS = 20000    # ~5,000 tokens
MAX_USER_ANSWER_CHARS = 5000  # ~1,250 tokens
MAX_TOTAL_INPUT_TOKENS = 10000


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length.

    Uses rough estimate of 4 characters per token for English text.
    This is a conservative estimate - actual tokenization may vary.

    Args:
        text: Input text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0
    return len(text) // 4


def validate_input_size(
    resume_text: str | None = None,
    job_text: str | None = None,
    user_answer: str | None = None,
) -> None:
    """Validate input sizes before processing.

    Checks individual field sizes and combined token estimate.
    Raises HTTPException with 400 status if validation fails.

    Args:
        resume_text: Resume content to validate.
        job_text: Job description content to validate.
        user_answer: User answer/response to validate.

    Raises:
        HTTPException: If any input exceeds size limits.
    """
    errors = []

    if resume_text and len(resume_text) > MAX_RESUME_CHARS:
        errors.append(
            f"Resume text exceeds {MAX_RESUME_CHARS:,} characters "
            f"(got {len(resume_text):,})"
        )

    if job_text and len(job_text) > MAX_JOB_DESC_CHARS:
        errors.append(
            f"Job description exceeds {MAX_JOB_DESC_CHARS:,} characters "
            f"(got {len(job_text):,})"
        )

    if user_answer and len(user_answer) > MAX_USER_ANSWER_CHARS:
        errors.append(
            f"Answer exceeds {MAX_USER_ANSWER_CHARS:,} characters "
            f"(got {len(user_answer):,})"
        )

    # Check combined token estimate
    total_tokens = sum(
        estimate_tokens(t) for t in [resume_text, job_text, user_answer] if t
    )
    if total_tokens > MAX_TOTAL_INPUT_TOKENS:
        errors.append(
            f"Combined input too large (~{total_tokens:,} tokens, "
            f"max {MAX_TOTAL_INPUT_TOKENS:,})"
        )

    if errors:
        error_message = "; ".join(errors)
        logger.warning(f"Input size validation failed: {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def validate_text_not_empty(text: str | None, field_name: str) -> None:
    """Validate that text is not empty or whitespace-only.

    Args:
        text: Text to validate.
        field_name: Human-readable field name for error message.

    Raises:
        HTTPException: If text is empty or whitespace-only.
    """
    if text is not None and not text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} cannot be empty or whitespace-only"
        )
