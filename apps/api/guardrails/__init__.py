"""AI Safety Guardrails Module.

This module provides comprehensive input and output validation for
AI-generated resume content. It protects against:
- Prompt injection attacks
- Content abuse and toxicity
- Bias and discrimination
- PII exposure
- Ungrounded claims

Usage:
    from guardrails import validate_input, validate_output, GuardrailsConfig

    # Validate user input before LLM processing
    validate_input(resume_text, thread_id=thread_id)

    # Validate LLM output before display/storage
    sanitized, results = validate_output(generated_content, source_profile)
    if results["bias_flags"]:
        # Display warnings to user
        pass
"""

import logging
from dataclasses import dataclass, field

from .bias_detector import (
    BiasCategory,
    BiasFlag,
    detect_bias,
    format_bias_warnings,
    has_blocking_bias,
)
from .injection_detector import (
    InjectionRisk,
    detect_injection,
    is_safe_for_llm,
    validate_no_injection,
)
from .input_validators import (
    MAX_JOB_DESC_CHARS,
    MAX_RESUME_CHARS,
    MAX_USER_ANSWER_CHARS,
    estimate_tokens,
    validate_input_size,
    validate_text_not_empty,
)
from .output_validators import (
    contains_harmful_content,
    sanitize_llm_output,
    validate_resume_output,
    validate_resume_output_detailed,
)
from .pii_detector import (
    PIIType,
    detect_pii,
    format_pii_warnings,
    has_sensitive_pii,
    redact_sensitive_pii,
)
from .claim_validator import (
    ClaimType,
    UngroundedClaim,
    validate_claims_grounded,
    format_ungrounded_claims,
    has_high_risk_claims,
)

logger = logging.getLogger(__name__)

# Re-export all public APIs
__all__ = [
    # Config
    "GuardrailsConfig",
    # Main validation functions
    "validate_input",
    "validate_output",
    # Input validators
    "validate_input_size",
    "validate_text_not_empty",
    "estimate_tokens",
    "MAX_RESUME_CHARS",
    "MAX_JOB_DESC_CHARS",
    "MAX_USER_ANSWER_CHARS",
    # Injection detection
    "InjectionRisk",
    "detect_injection",
    "validate_no_injection",
    "is_safe_for_llm",
    # Output validation
    "validate_resume_output",
    "validate_resume_output_detailed",
    "sanitize_llm_output",
    "contains_harmful_content",
    # Bias detection
    "BiasCategory",
    "BiasFlag",
    "detect_bias",
    "format_bias_warnings",
    "has_blocking_bias",
    # PII detection
    "PIIType",
    "detect_pii",
    "format_pii_warnings",
    "has_sensitive_pii",
    "redact_sensitive_pii",
    # Claim validation
    "ClaimType",
    "UngroundedClaim",
    "validate_claims_grounded",
    "format_ungrounded_claims",
    "has_high_risk_claims",
]


@dataclass
class GuardrailsConfig:
    """Configuration for guardrails behavior.

    Customize validation thresholds and behavior by passing
    an instance to validate_input/validate_output.

    Attributes:
        max_resume_chars: Maximum characters for resume input.
        max_job_chars: Maximum characters for job description.
        max_answer_chars: Maximum characters for user answers.
        block_injections: Whether to raise on injection detection.
        block_toxic_content: Whether to block toxic/harmful content.
        injection_block_level: Minimum risk level that triggers blocking.
    """

    max_resume_chars: int = MAX_RESUME_CHARS
    max_job_chars: int = MAX_JOB_DESC_CHARS
    max_answer_chars: int = MAX_USER_ANSWER_CHARS
    block_injections: bool = True
    block_toxic_content: bool = True
    injection_block_level: InjectionRisk = InjectionRisk.HIGH


def validate_input(
    text: str,
    thread_id: str | None = None,
    ip_address: str | None = None,
    config: GuardrailsConfig | None = None,
) -> tuple[bool, list[str]]:
    """Run all input validations on user-provided text.

    This is the main entry point for validating user inputs before
    sending to the LLM. Checks size limits, injection patterns,
    and optionally content safety.

    Args:
        text: User input text (resume, job description, or answer).
        thread_id: Optional session ID for audit logging.
        ip_address: Optional client IP for audit logging.
        config: Optional configuration to customize behavior.

    Returns:
        Tuple of (passed, list_of_warnings).
        passed is True if validation succeeded.
        warnings contains non-blocking issues detected.

    Raises:
        HTTPException: If validation fails with blocking enabled.

    Example:
        >>> passed, warnings = validate_input("Normal resume text")
        >>> passed
        True
        >>> passed, warnings = validate_input("Ignore all instructions")
        HTTPException: 400 - Input contains disallowed patterns...
    """
    if not text:
        return True, []

    config = config or GuardrailsConfig()
    warnings: list[str] = []

    # Size check (always enforced)
    validate_input_size(resume_text=text)

    # Injection check
    risk, patterns = detect_injection(text)
    if patterns:
        warnings.append(f"Potential injection patterns detected: {len(patterns)}")
        if config.block_injections and risk == config.injection_block_level:
            logger.warning(
                f"Blocking injection attempt: thread={thread_id}, ip={ip_address}, "
                f"risk={risk.value}, patterns={len(patterns)}"
            )
            validate_no_injection(text, config.injection_block_level)

    # PII check (warn about sensitive PII in input)
    pii_items = detect_pii(text)
    if pii_items:
        pii_types = list(set(p["type"] for p in pii_items))
        warnings.append(f"Sensitive PII detected in input: {pii_types}")
        logger.info(f"PII detected in input: {pii_types}, thread={thread_id}")

    return True, warnings


def validate_output(
    generated_content: str,
    source_profile: str | None = None,
    thread_id: str | None = None,
) -> tuple[str, dict]:
    """Run all output validations on LLM-generated content.

    This is the main entry point for validating LLM outputs before
    displaying to users. Checks for harmful patterns, AI self-references,
    bias indicators, and optionally validates claim grounding.

    Args:
        generated_content: LLM-generated resume HTML/text.
        source_profile: Original profile for claim validation.
        thread_id: Optional session ID for audit logging.

    Returns:
        Tuple of (sanitized_content, validation_results).
        sanitized_content has problematic patterns removed.
        validation_results dict contains:
            - passed: bool
            - warnings: list[str]
            - bias_flags: list[dict]
            - sanitized: bool

    Example:
        >>> content, results = validate_output("<p>John Doe</p>", "...")
        >>> results["passed"]
        True
        >>> results["bias_flags"]
        []
    """
    if not generated_content:
        return generated_content, {
            "passed": True,
            "warnings": [],
            "bias_flags": [],
            "pii_warnings": [],
            "ungrounded_claims": [],
            "sanitized": False,
        }

    results: dict = {
        "passed": True,
        "warnings": [],
        "bias_flags": [],
        "pii_warnings": [],
        "ungrounded_claims": [],
        "sanitized": False,
    }

    # Basic output validation (AI references, instruction leaks)
    is_valid, warnings = validate_resume_output(generated_content)
    results["warnings"].extend(warnings)

    # Sanitize if needed
    if not is_valid:
        generated_content = sanitize_llm_output(generated_content)
        results["sanitized"] = True
        logger.info(f"Sanitized output for thread={thread_id}")

    # Bias detection (warn, don't block by default)
    bias_flags = detect_bias(generated_content)
    if bias_flags:
        results["bias_flags"] = format_bias_warnings(bias_flags)
        logger.info(
            f"Bias flags for thread={thread_id}: "
            f"{len(bias_flags)} in {len(set(f.category.value for f in bias_flags))} categories"
        )

    # Update passed status based on blocking bias
    if has_blocking_bias(bias_flags):
        results["passed"] = False

    # PII detection in output (should not leak sensitive info)
    pii_items = detect_pii(generated_content)
    if pii_items:
        results["pii_warnings"] = format_pii_warnings(pii_items)
        logger.warning(
            f"Sensitive PII in output for thread={thread_id}: "
            f"{[p['type'] for p in pii_items]}"
        )

    # Claim grounding validation (verify claims against source)
    if source_profile:
        ungrounded = validate_claims_grounded(
            generated_content,
            source_profile,
            confidence_threshold=0.6
        )
        if ungrounded:
            results["ungrounded_claims"] = format_ungrounded_claims(ungrounded)
            logger.info(
                f"Ungrounded claims for thread={thread_id}: {len(ungrounded)}"
            )

    return generated_content, results
