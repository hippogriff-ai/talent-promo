"""URL validation utilities for the Research stage."""

import re
from urllib.parse import urlparse
from typing import Tuple, Optional


def validate_linkedin_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate a LinkedIn profile URL.

    Args:
        url: The URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is None
    """
    if not url or not url.strip():
        return False, "LinkedIn URL is required"

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"

    # Check host
    host = parsed.netloc.lower()
    valid_hosts = ("linkedin.com", "www.linkedin.com", "m.linkedin.com")
    if host not in valid_hosts:
        return False, f"URL must be a LinkedIn URL (got: {host})"

    # Check path for profile format
    path = parsed.path.lower()
    if not path.startswith("/in/"):
        return False, "URL must be a LinkedIn profile URL (e.g., linkedin.com/in/username)"

    # Extract username and validate it has content
    username_match = re.match(r"/in/([a-zA-Z0-9\-_%]+)", path)
    if not username_match or not username_match.group(1):
        return False, "Invalid LinkedIn profile username in URL"

    return True, None


def validate_job_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate a job posting URL.

    Args:
        url: The URL to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid, error_message is None
    """
    if not url or not url.strip():
        return False, "Job URL is required"

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"

    # Check host exists
    if not parsed.netloc:
        return False, "URL must include a domain"

    # Accept any valid URL - job postings can be on any domain
    # Just validate basic URL structure
    return True, None


def validate_urls(
    linkedin_url: Optional[str],
    job_url: str,
    resume_text: Optional[str],
    job_text: Optional[str] = None,
) -> Tuple[bool, list[str]]:
    """Validate all input URLs for starting a research workflow.

    Args:
        linkedin_url: LinkedIn profile URL (optional if resume_text provided)
        job_url: Job posting URL (optional if job_text provided)
        resume_text: Raw resume text (optional if linkedin_url provided)
        job_text: Pasted job description (optional if job_url provided)

    Returns:
        Tuple of (all_valid, list of error messages)
    """
    errors = []

    # Normalize empty/whitespace-only strings to None
    linkedin_url = linkedin_url.strip() if linkedin_url and linkedin_url.strip() else None
    resume_text = resume_text.strip() if resume_text and resume_text.strip() else None
    job_text = job_text.strip() if job_text and job_text.strip() else None

    # Must have either LinkedIn URL or resume text
    if not linkedin_url and not resume_text:
        errors.append("Either LinkedIn URL or resume text is required")
    elif linkedin_url:
        is_valid, error = validate_linkedin_url(linkedin_url)
        if not is_valid:
            errors.append(f"LinkedIn URL: {error}")

    # Must have either job URL or job text
    if not job_url and not job_text:
        errors.append("Either job URL or pasted job description is required")
    elif job_url:
        is_valid, error = validate_job_url(job_url)
        if not is_valid:
            errors.append(f"Job URL: {error}")
    # If only job_text is provided, no URL validation needed

    return len(errors) == 0, errors
