"""Ingest nodes for fetching LinkedIn profiles and job postings.

Simplified approach: Store raw markdown/text directly instead of extracting
structured JSON. Downstream LLMs work better with raw text anyway.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Optional

from config import get_settings
from workflow.state import ResumeState
from tools.exa_tool import exa_get_contents, exa_linkedin_people_search
from workflow.progress import emit_progress

logger = logging.getLogger(__name__)

settings = get_settings()


# =============================================================================
# Text normalization (reduce token waste before passing to LLMs)
# =============================================================================


def _normalize_text(text: str) -> str:
    """Strip redundant whitespace/page-breaks to save LLM tokens.

    - Removes form-feed / page-break chars
    - Strips trailing whitespace per line
    - Collapses 3+ consecutive newlines into 2 (preserves paragraph breaks)
    """
    if not text:
        return text
    # Remove form-feed / vertical-tab / page-break characters
    text = re.sub(r'[\f\v]', '\n', text)
    # Strip trailing whitespace on every line
    text = re.sub(r'[^\S\n]+$', '', text, flags=re.MULTILINE)
    # Collapse 3+ consecutive newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# =============================================================================
# Simple Regex Extractors (no LLM needed)
# =============================================================================


def extract_name_from_text(text: str) -> str:
    """Extract name from the beginning of resume/profile text.

    Looks for a name-like line in the first few lines (not email, URL, etc).
    """
    if not text:
        return "Candidate"

    lines = text.strip().split('\n')
    for line in lines[:5]:
        line = line.strip()
        # Skip empty lines, emails, URLs, phone numbers
        if not line or len(line) > 60:
            continue
        if any(c in line.lower() for c in ['@', 'http', 'www.', '|', '•']):
            continue
        if re.match(r'^[\d\s\-\(\)\+]+$', line):  # Phone number
            continue
        # Likely a name if it's 2-4 words, starts with capital
        words = line.split()
        if 1 <= len(words) <= 4 and words[0] and words[0][0].isupper():
            # Remove common titles
            cleaned = re.sub(r'^(Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+', '', line, flags=re.I)
            if cleaned:
                return cleaned

    return "Candidate"


def extract_job_title_from_text(text: str) -> str:
    """Extract job title from job posting text."""
    if not text:
        return "Position"

    lines = text.strip().split('\n')

    # Look for common patterns
    for line in lines[:10]:
        line = line.strip()
        # Skip empty or very long lines
        if not line or len(line) > 100:
            continue

        # Pattern: "Job Title:" or "Position:" prefix
        match = re.match(r'^(?:job\s*title|position|role)\s*[:\-]\s*(.+)$', line, re.I)
        if match:
            return match.group(1).strip()

        # Pattern: Title is often in h1/first meaningful line
        # Skip company names (usually have Inc, LLC, etc)
        if not any(w in line.lower() for w in ['inc', 'llc', 'ltd', 'corp', 'company', 'about us']):
            # Likely a job title if it contains common title words
            title_words = ['engineer', 'developer', 'manager', 'director', 'analyst',
                          'designer', 'lead', 'senior', 'junior', 'staff', 'principal',
                          'architect', 'scientist', 'specialist', 'coordinator', 'consultant']
            if any(w in line.lower() for w in title_words):
                return line[:80]

    return "Position"


def extract_company_from_url(url: str) -> str | None:
    """Extract company name from job posting URL domain."""
    if not url:
        return None

    # Extract domain from URL
    match = re.search(r'https?://(?:www\.)?([^/]+)', url, re.I)
    if not match:
        return None

    domain = match.group(1).lower()

    # Skip generic job boards - these don't indicate company name
    generic_domains = [
        'linkedin.com', 'indeed.com', 'glassdoor.com', 'monster.com',
        'ziprecruiter.com', 'lever.co', 'greenhouse.io', 'workday.com',
        'smartrecruiters.com', 'jobs.', 'careers.', 'apply.', 'hire.'
    ]
    if any(g in domain for g in generic_domains):
        return None

    # Extract company name from domain (e.g., openai.com -> OpenAI)
    company_part = domain.split('.')[0]

    # Clean up and capitalize
    # Handle camelCase or all-lowercase
    if company_part.islower():
        # Try to capitalize intelligently (e.g., openai -> OpenAI)
        # Common patterns
        known_capitalizations = {
            'openai': 'OpenAI',
            'microsoft': 'Microsoft',
            'google': 'Google',
            'apple': 'Apple',
            'amazon': 'Amazon',
            'meta': 'Meta',
            'netflix': 'Netflix',
            'stripe': 'Stripe',
            'airbnb': 'Airbnb',
            'uber': 'Uber',
            'lyft': 'Lyft',
            'slack': 'Slack',
            'spotify': 'Spotify',
            'salesforce': 'Salesforce',
            'dropbox': 'Dropbox',
            'atlassian': 'Atlassian',
            'github': 'GitHub',
            'gitlab': 'GitLab',
            'databricks': 'Databricks',
            'snowflake': 'Snowflake',
            'palantir': 'Palantir',
            'nvidia': 'NVIDIA',
            'amd': 'AMD',
            'intel': 'Intel',
            'ibm': 'IBM',
            'oracle': 'Oracle',
            'sap': 'SAP',
            'adobe': 'Adobe',
            'autodesk': 'Autodesk',
            'figma': 'Figma',
            'notion': 'Notion',
            'linear': 'Linear',
            'vercel': 'Vercel',
            'netlify': 'Netlify',
            'cloudflare': 'Cloudflare',
            'twilio': 'Twilio',
            'plaid': 'Plaid',
            'coinbase': 'Coinbase',
            'robinhood': 'Robinhood',
            'doordash': 'DoorDash',
            'instacart': 'Instacart',
            'anthropic': 'Anthropic',
        }
        if company_part in known_capitalizations:
            return known_capitalizations[company_part]
        # Default: capitalize first letter
        return company_part.capitalize()

    return company_part


def extract_company_from_text(text: str, url: str | None = None) -> str:
    """Extract company name from job posting text and/or URL.

    Tries multiple strategies:
    1. Explicit labels (Company:, Employer:, Organization:)
    2. "About [Company]" pattern
    3. "Join [Company]" pattern
    4. "[Company] is hiring/looking for" pattern
    5. "at [Company]" pattern (without requiring Inc/LLC)
    6. URL domain fallback
    """
    # Strategy 1: Try URL domain first (most reliable for company careers pages)
    if url:
        url_company = extract_company_from_url(url)
        if url_company:
            logger.debug(f"Extracted company from URL: {url_company}")
            return url_company

    if not text:
        return "Company"

    lines = text.strip().split('\n')

    # Strategy 2: Look for explicit patterns in first 20 lines
    for line in lines[:20]:
        line = line.strip()
        if not line or len(line) > 150:
            continue

        # Pattern: "Company:" or "Employer:" or "Organization:"
        match = re.match(r'^(?:company|employer|organization)\s*[:\-]\s*(.+)$', line, re.I)
        if match:
            company = match.group(1).strip()
            if len(company) < 50:
                return company

        # Pattern: "About [Company]" (common in company descriptions)
        match = re.match(r'^about\s+(.+)$', line, re.I)
        if match:
            company = match.group(1).strip()
            # Avoid "About the role", "About this job", etc.
            if len(company) < 50 and not any(w in company.lower() for w in ['role', 'job', 'position', 'team', 'opportunity']):
                return company

        # Pattern: "Join [Company]" (very common in job postings)
        match = re.match(r'^join\s+(?:the\s+)?(.+?)(?:\s+team)?(?:\s+as)?(?:\s+and)?[!\.]?$', line, re.I)
        if match:
            company = match.group(1).strip()
            if len(company) < 50 and company.lower() not in ['us', 'our team', 'our']:
                return company

        # Pattern: "[Company] is hiring/looking for/seeking"
        match = re.match(r'^([A-Z][A-Za-z0-9\s&\-\.]+?)\s+(?:is\s+)?(?:hiring|looking\s+for|seeking|wants)', line, re.I)
        if match:
            company = match.group(1).strip()
            if len(company) < 50:
                return company

        # Pattern: "at [Company]" - more flexible, doesn't require Inc/LLC
        match = re.search(r'\bat\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s*[,\.\!]|\s+(?:as|for|in|we|is|are|you)|\s*$)', line)
        if match:
            company = match.group(1).strip()
            # Avoid common false positives
            if len(company) < 50 and company.lower() not in ['a', 'the', 'our', 'this', 'an']:
                return company

    # Strategy 3: Look for company name with common suffixes anywhere in text
    suffix_pattern = r'\b([A-Z][A-Za-z0-9\s]+?)\s*(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|Company|Co\.)\b'
    for line in lines[:30]:
        match = re.search(suffix_pattern, line)
        if match:
            company = match.group(1).strip()
            if len(company) < 50:
                return company + " " + match.group(0).split()[-1]  # Include the suffix

    return "Company"


def extract_contact_info(text: str) -> dict:
    """Extract contact info using regex patterns."""
    if not text:
        return {}

    contact = {}

    # Email
    email_match = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w+', text)
    if email_match:
        contact['email'] = email_match.group(0)

    # Phone (various formats)
    phone_match = re.search(r'[\+]?[\d\s\-\(\)\.]{10,20}', text[:1000])  # Only check first part
    if phone_match:
        phone = re.sub(r'[^\d\+]', '', phone_match.group(0))
        if len(phone) >= 10:
            contact['phone'] = phone_match.group(0).strip()

    # LinkedIn URL
    linkedin_match = re.search(r'(?:linkedin\.com/in/|linkedin\.com/pub/)[\w\-]+', text, re.I)
    if linkedin_match:
        contact['linkedin'] = 'https://www.' + linkedin_match.group(0)

    # Location (city, state pattern)
    location_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s*([A-Z]{2})\b', text[:500])
    if location_match:
        contact['location'] = f"{location_match.group(1)}, {location_match.group(2)}"

    return contact


def estimate_seniority(text: str) -> str:
    """Estimate seniority from resume text."""
    if not text:
        return "mid_level"

    text_lower = text.lower()

    # Senior indicators
    senior_keywords = ['director', 'vp', 'vice president', 'head of', 'principal',
                      'staff engineer', 'distinguished', 'chief', 'cto', 'ceo', 'cfo',
                      'founding', '10+ years', '15+ years', '20+ years']
    if any(w in text_lower for w in senior_keywords):
        return "senior"

    # Mid-level indicators
    mid_keywords = ['senior', 'lead', 'manager', 'team lead', 'tech lead',
                   '5+ years', '6+ years', '7+ years', '8+ years']
    if any(w in text_lower for w in mid_keywords):
        return "mid_level"

    # Early career indicators
    early_keywords = ['junior', 'associate', 'entry', 'intern', 'graduate',
                     'bootcamp', 'recent graduate', '1+ years', '2+ years', '0-2 years']
    if any(w in text_lower for w in early_keywords):
        return "early_career"

    # Default to mid-level if unclear
    return "mid_level"


def _add_progress(messages: list, phase: str, message: str, detail: str = "") -> list:
    """Add a progress message to the list."""
    # Also emit real-time progress for immediate visibility
    emit_progress(phase, message, detail)
    return [*messages, {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "message": message,
        "detail": detail,
    }]

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


async def fetch_with_retry(
    fetch_fn: callable,
    params: dict,
    max_retries: int = MAX_RETRIES,
    delay: float = RETRY_DELAY_SECONDS,
) -> dict:
    """Fetch with retry logic.

    Args:
        fetch_fn: The fetch function to call (e.g., exa_get_contents.invoke)
        params: Parameters to pass to the fetch function
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        Result dict from fetch function

    Raises:
        Exception: If all retries fail
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            result = fetch_fn(params)

            if result.get("success"):
                return result

            # Handle non-success response
            error_msg = result.get("error", "Unknown error")
            logger.warning(f"Fetch attempt {attempt + 1}/{max_retries} failed: {error_msg}")
            last_error = error_msg

            # Don't retry on 404 - the resource doesn't exist
            if "404" in error_msg or "not found" in error_msg.lower():
                return result

        except Exception as e:
            logger.warning(f"Fetch attempt {attempt + 1}/{max_retries} raised exception: {e}")
            last_error = str(e)

        # Wait before retrying (except on last attempt)
        if attempt < max_retries - 1:
            await asyncio.sleep(delay * (attempt + 1))  # Exponential backoff

    # All retries exhausted
    return {
        "success": False,
        "error": f"Failed after {max_retries} retries: {last_error}",
        "contents": [],
    }


# NOTE: LLM extraction prompts removed - we now store raw text directly
# and let downstream LLMs (discovery, drafting) work with raw text


# NOTE: fetch_profile_node and fetch_job_node removed
# Use parallel_ingest_node instead which is faster and simpler


async def _fetch_profile_async(
    linkedin_url: str | None,
    uploaded_resume: str | None,
) -> tuple[str | None, str | None]:
    """Fetch profile content asynchronously.

    Returns:
        Tuple of (profile_text, error_message)
    """
    from tools.exa_tool import exa_get_structured_content

    if uploaded_resume:
        logger.info("Using uploaded resume text")
        return uploaded_resume, None

    if not linkedin_url:
        return None, "No LinkedIn URL or resume provided"

    # Try EXA structured content
    structured_result = exa_get_structured_content(
        url=linkedin_url,
        content_type="linkedin_profile",
    )
    profile_text = structured_result.get("raw_text", "")

    # If no raw text, try direct fetch
    if not profile_text:
        result = await fetch_with_retry(
            exa_get_contents.invoke,
            {"urls": [linkedin_url], "include_text": True, "include_highlights": True, "include_summary": True, "livecrawl": "always"},
            max_retries=MAX_RETRIES,
        )
        if result.get("success") and result.get("contents"):
            profile_text = result["contents"][0].get("text", "")

    # Fallback: Try Exa people search
    if not profile_text:
        logger.info("Direct LinkedIn fetch failed, trying Exa people search fallback...")
        emit_progress("ingest", "Searching profile database...",
                     "LinkedIn blocked direct access, using alternative method")
        people_result = exa_linkedin_people_search(linkedin_url)
        if people_result.get("success") and people_result.get("raw_text"):
            profile_text = people_result["raw_text"]
            logger.info(f"Exa people search found profile: {people_result.get('title')}")

    if not profile_text:
        return None, f"LINKEDIN_FETCH_FAILED: Unable to access LinkedIn profile. LinkedIn blocks automated access. Please paste your resume text instead. URL: {linkedin_url}"

    return profile_text, None


async def _fetch_job_async(
    job_url: str | None,
    uploaded_job_text: str | None,
) -> tuple[str | None, str | None]:
    """Fetch job content asynchronously.

    Returns:
        Tuple of (job_text, error_message)
    """
    from tools.exa_tool import exa_get_structured_content

    if uploaded_job_text:
        logger.info("Using pasted job description")
        return uploaded_job_text, None

    if not job_url:
        return None, "No job URL or job description provided"

    # Try EXA structured content
    structured_result = exa_get_structured_content(
        url=job_url,
        content_type="job_posting",
    )
    job_text = structured_result.get("raw_text", "")

    # If no raw text, try direct fetch
    if not job_text:
        result = await fetch_with_retry(
            exa_get_contents.invoke,
            {"urls": [job_url], "include_text": True, "include_highlights": True, "include_summary": True, "livecrawl": "fallback"},
            max_retries=MAX_RETRIES,
        )
        if result.get("success") and result.get("contents"):
            job_text = result["contents"][0].get("text", "")

    if not job_text:
        return None, f"Failed to fetch job posting content. Try pasting the job description instead. URL: {job_url}"

    return job_text, None


async def parallel_ingest_node(state: ResumeState) -> dict[str, Any]:
    """Fetch profile + job posting IN PARALLEL and store raw text directly.

    SIMPLIFIED: No LLM extraction. We store raw text and extract minimal
    metadata (name, job title, company) using simple regex. Downstream
    LLMs work better with raw text anyway.

    Uses asyncio.gather for TRUE parallel fetching - both requests run
    simultaneously, and partial data is emitted via progress as soon as ready.
    """
    logger.info("Starting TRUE parallel ingest (profile + job simultaneously)")

    linkedin_url = state.get("linkedin_url")
    uploaded_resume = state.get("uploaded_resume_text")
    job_url = state.get("job_url")
    uploaded_job_text = state.get("uploaded_job_text")

    errors = list(state.get("errors", []))
    progress = list(state.get("progress_messages", []))

    try:
        profile_source = "Using uploaded resume" if uploaded_resume else f"LinkedIn: {linkedin_url[:50]}..." if linkedin_url else "No profile source"
        job_source = "Using pasted job description" if uploaded_job_text else f"Job URL: {job_url[:50]}..." if job_url else "No job source"
        progress = _add_progress(progress, "ingest", "Fetching your profile and job posting in parallel...",
                                f"{profile_source} | {job_source}")

        # === FETCH BOTH IN PARALLEL ===
        profile_task = _fetch_profile_async(linkedin_url, uploaded_resume)
        job_task = _fetch_job_async(job_url, uploaded_job_text)

        # Run both fetches simultaneously
        (profile_text, profile_error), (job_text, job_error) = await asyncio.gather(
            profile_task,
            job_task,
        )

        # Check for errors
        if profile_error:
            errors.append(profile_error)
            return {"errors": errors, "current_step": "error", "progress_messages": progress}

        if job_error:
            errors.append(job_error)
            return {"errors": errors, "current_step": "error", "progress_messages": progress}

        # === EXTRACT MINIMAL METADATA (regex only, no LLM) ===
        profile_name = extract_name_from_text(profile_text)
        job_title = extract_job_title_from_text(job_text)
        job_company = extract_company_from_text(job_text, url=job_url)
        contact_info = extract_contact_info(profile_text)
        seniority = estimate_seniority(profile_text)

        logger.info(f"Extracted metadata: name={profile_name}, job={job_title}@{job_company}, seniority={seniority}")

        # Create minimal structured data for backward compatibility
        # These are used by some UI components that expect structured data
        profile_data = {
            "name": profile_name,
            "email": contact_info.get("email", ""),
            "phone": contact_info.get("phone", ""),
            "location": contact_info.get("location", ""),
            "linkedin_url": linkedin_url or contact_info.get("linkedin", ""),
            "headline": "",
            "summary": "",
            "experience": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "raw_text": profile_text,
            "extraction_method": "raw_text",
            "seniority": seniority,
        }

        job_data = {
            "title": job_title,
            "company_name": job_company,
            "description": job_text[:2000] if job_text else "",  # Truncate for display
            "location": "",
            "work_type": "",
            "job_type": "",
            "experience_level": "",
            "requirements": [],
            "preferred_qualifications": [],
            "responsibilities": [],
            "tech_stack": [],
            "benefits": [],
            "salary_range": "",
            "source_url": job_url or "pasted_job_description",
            "raw_text": job_text,
            "extraction_method": "raw_text",
        }

        progress = _add_progress(progress, "ingest", "Content fetched successfully",
                                f"Found: {profile_name} → {job_title} at {job_company}")

        logger.info(f"Simplified ingest complete: {profile_name} -> {job_title}@{job_company}")

        # Normalize text to strip redundant newlines/page-breaks (saves LLM tokens)
        profile_text = _normalize_text(profile_text)
        job_text = _normalize_text(job_text)

        return {
            # Raw text fields (primary - used by downstream LLMs)
            "profile_text": profile_text,
            "job_text": job_text,
            "profile_name": profile_name,
            "job_title": job_title,
            "job_company": job_company,
            # Backward-compatible structured data (for UI components)
            "user_profile": profile_data,
            "job_posting": job_data,
            # Markdown fields (for display/editing in UI)
            "profile_markdown": profile_text,
            "job_markdown": job_text,
            # Workflow state
            "current_step": "research",
            "sub_step": "ingest_complete",
            "progress_messages": progress,
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Parallel ingest error: {e}")
        return {
            "errors": [*errors, f"Parallel ingest error: {str(e)}"],
            "current_step": "error",
            "progress_messages": progress,
        }
