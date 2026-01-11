"""Ingest nodes for fetching LinkedIn profiles and job postings."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import ResumeState, UserProfile, JobPostingData
from tools.exa_tool import exa_get_contents
from workflow.progress import emit_progress

logger = logging.getLogger(__name__)

settings = get_settings()


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


def get_llm():
    """Get configured LLM for parsing."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0,
    )


PROFILE_EXTRACTION_PROMPT = """You are an expert at extracting structured information from LinkedIn profiles.

Given the raw text content from a LinkedIn profile page, extract the following information in JSON format:

{
    "name": "Full name",
    "headline": "Professional headline",
    "summary": "About/summary section",
    "location": "Location",
    "experience": [
        {
            "company": "Company name",
            "position": "Job title",
            "location": "Location if available",
            "start_date": "Start date",
            "end_date": "End date or null if current",
            "is_current": true/false,
            "achievements": ["Achievement 1", "Achievement 2"],
            "technologies": ["Tech 1", "Tech 2"],
            "description": "Role description"
        }
    ],
    "education": [
        {
            "institution": "School name",
            "degree": "Degree type",
            "field_of_study": "Field",
            "start_date": "Start date",
            "end_date": "End date"
        }
    ],
    "skills": ["Skill 1", "Skill 2"],
    "certifications": ["Cert 1", "Cert 2"],
    "languages": ["Language 1"]
}

Extract as much information as available. If something is not present, omit the field or use null.
Be precise and don't make up information that isn't clearly stated in the profile."""


JOB_EXTRACTION_PROMPT = """You are an expert at extracting structured information from job postings.

Given the raw text content from a job posting page, extract the following information in JSON format:

{
    "title": "Job title",
    "company_name": "Company name",
    "description": "Full job description",
    "location": "Job location",
    "work_type": "remote/hybrid/onsite",
    "job_type": "full-time/part-time/contract",
    "experience_level": "Entry/Mid/Senior/Lead/Executive",
    "requirements": ["Required qualification 1", "Required qualification 2"],
    "preferred_qualifications": ["Nice to have 1", "Nice to have 2"],
    "responsibilities": ["Responsibility 1", "Responsibility 2"],
    "tech_stack": ["Technology 1", "Framework 2"],
    "benefits": ["Benefit 1", "Benefit 2"],
    "salary_range": "Salary range if mentioned",
    "posted_date": "Posted date if available"
}

Extract as much information as available. If something is not present, omit the field or use null.
Be precise and don't make up information that isn't clearly stated in the posting.
For tech_stack, extract all mentioned programming languages, frameworks, tools, and platforms."""


async def fetch_profile_node(state: ResumeState) -> dict[str, Any]:
    """Fetch and parse user profile from LinkedIn URL or use uploaded resume.

    This node handles two cases:
    1. LinkedIn URL provided -> Fetch via EXA and parse
    2. Resume text uploaded -> Parse directly
    """
    logger.info("Starting profile fetch node")

    linkedin_url = state.get("linkedin_url")
    uploaded_resume = state.get("uploaded_resume_text")

    try:
        if linkedin_url:
            # Fetch LinkedIn profile via EXA with retry logic
            logger.info(f"Fetching LinkedIn profile: {linkedin_url}")

            result = await fetch_with_retry(
                exa_get_contents.invoke,
                {
                    "urls": [linkedin_url],
                    "include_text": True,
                    "include_highlights": True,
                    "include_summary": True,
                },
                max_retries=MAX_RETRIES,
            )

            if not result.get("success") or not result.get("contents"):
                error_msg = result.get("error", "Unknown error")
                # Provide manual input fallback option
                fallback_msg = f"Failed to fetch LinkedIn profile after {MAX_RETRIES} retries: {error_msg}. You can try again or paste your resume text instead."
                return {
                    "errors": [*state.get("errors", []), fallback_msg],
                    "current_step": "error",
                }

            raw_text = result["contents"][0].get("text", "")

            # Parse with LLM
            llm = get_llm()
            messages = [
                SystemMessage(content=PROFILE_EXTRACTION_PROMPT),
                HumanMessage(content=f"Extract profile information from:\n\n{raw_text}"),
            ]

            response = await llm.ainvoke(messages)

            # Parse JSON from response
            import json
            try:
                # Try to extract JSON from the response
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                profile_data = json.loads(content)
                profile_data["linkedin_url"] = linkedin_url
                profile_data["raw_text"] = raw_text

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse profile JSON: {e}")
                return {
                    "errors": [*state.get("errors", []), f"Failed to parse profile data: {str(e)}"],
                    "current_step": "error",
                }

        elif uploaded_resume:
            # Parse uploaded resume text
            logger.info("Parsing uploaded resume text")

            llm = get_llm()
            messages = [
                SystemMessage(content=PROFILE_EXTRACTION_PROMPT),
                HumanMessage(content=f"Extract profile information from this resume:\n\n{uploaded_resume}"),
            ]

            response = await llm.ainvoke(messages)

            import json
            try:
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                profile_data = json.loads(content)
                profile_data["raw_text"] = uploaded_resume

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse resume JSON: {e}")
                return {
                    "errors": [*state.get("errors", []), f"Failed to parse resume data: {str(e)}"],
                    "current_step": "error",
                }

        else:
            return {
                "errors": [*state.get("errors", []), "No LinkedIn URL or resume provided"],
                "current_step": "error",
            }

        logger.info(f"Successfully parsed profile for: {profile_data.get('name', 'Unknown')}")

        return {
            "user_profile": profile_data,
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Profile fetch error: {str(e)}"],
            "current_step": "error",
        }


async def fetch_job_node(state: ResumeState) -> dict[str, Any]:
    """Fetch and parse job posting from URL."""
    logger.info("Starting job fetch node")

    job_url = state.get("job_url")

    if not job_url:
        return {
            "errors": [*state.get("errors", []), "No job URL provided"],
            "current_step": "error",
        }

    try:
        # Fetch job posting via EXA with retry logic
        logger.info(f"Fetching job posting: {job_url}")

        result = await fetch_with_retry(
            exa_get_contents.invoke,
            {
                "urls": [job_url],
                "include_text": True,
                "include_highlights": True,
                "include_summary": True,
            },
            max_retries=MAX_RETRIES,
        )

        if not result.get("success") or not result.get("contents"):
            error_msg = result.get("error", "Unknown error")
            return {
                "errors": [*state.get("errors", []), f"Failed to fetch job posting after {MAX_RETRIES} retries: {error_msg}"],
                "current_step": "error",
            }

        raw_text = result["contents"][0].get("text", "")

        # Parse with LLM
        llm = get_llm()
        messages = [
            SystemMessage(content=JOB_EXTRACTION_PROMPT),
            HumanMessage(content=f"Extract job posting information from:\n\n{raw_text}"),
        ]

        response = await llm.ainvoke(messages)

        # Parse JSON from response
        import json
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            job_data = json.loads(content)
            job_data["source_url"] = job_url

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse job JSON: {e}")
            return {
                "errors": [*state.get("errors", []), f"Failed to parse job data: {str(e)}"],
                "current_step": "error",
            }

        logger.info(f"Successfully parsed job: {job_data.get('title', 'Unknown')} at {job_data.get('company_name', 'Unknown')}")

        return {
            "job_posting": job_data,
            "current_step": "research",
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Job fetch error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Job fetch error: {str(e)}"],
            "current_step": "error",
        }


async def parallel_ingest_node(state: ResumeState) -> dict[str, Any]:
    """Fetch and parse profile + job posting with maximum parallelism.

    Optimized flow:
    1. Fetch both URLs in parallel via EXA
    2. Parse both with LLM in parallel

    This reduces ingest time from ~50s to ~25s.
    """
    logger.info("Starting optimized parallel ingest")

    linkedin_url = state.get("linkedin_url")
    uploaded_resume = state.get("uploaded_resume_text")
    job_url = state.get("job_url")
    uploaded_job_text = state.get("uploaded_job_text")

    errors = list(state.get("errors", []))
    progress = list(state.get("progress_messages", []))

    try:
        # Phase 1: Fetch both URLs in parallel (or use uploaded text)
        logger.info("Phase 1: Parallel URL fetching")
        profile_source = "Using uploaded resume" if uploaded_resume else f"LinkedIn: {linkedin_url[:50]}..." if linkedin_url else "No profile source"
        job_source = "Using pasted job description" if uploaded_job_text else f"Job URL: {job_url[:50]}..." if job_url else "No job source"
        progress = _add_progress(progress, "ingest", "Fetching your profile and job posting...",
                                f"{profile_source} | {job_source}")

        async def fetch_profile_content():
            if uploaded_resume:
                return {"success": True, "text": uploaded_resume, "source": "upload"}
            if not linkedin_url:
                return {"success": False, "error": "No LinkedIn URL or resume provided"}

            result = await fetch_with_retry(
                exa_get_contents.invoke,
                {"urls": [linkedin_url], "include_text": True, "include_highlights": True, "include_summary": True},
                max_retries=MAX_RETRIES,
            )
            if result.get("success") and result.get("contents"):
                text = result["contents"][0].get("text", "")
                if text:
                    return {"success": True, "text": text, "source": "linkedin"}
                return {"success": False, "error": f"LinkedIn page returned empty content. The profile may be private or the page requires login. URL: {linkedin_url}"}
            if result.get("error"):
                return {"success": False, "error": f"EXA error: {result.get('error')}"}
            return {"success": False, "error": f"Could not extract content from LinkedIn profile. The profile may be private or blocked. URL: {linkedin_url}"}

        async def fetch_job_content():
            # Check for pasted job description first
            if uploaded_job_text:
                return {"success": True, "text": uploaded_job_text, "source": "paste"}
            if not job_url:
                return {"success": False, "error": "No job URL or job description provided"}

            result = await fetch_with_retry(
                exa_get_contents.invoke,
                {"urls": [job_url], "include_text": True, "include_highlights": True, "include_summary": True},
                max_retries=MAX_RETRIES,
            )
            if result.get("success") and result.get("contents"):
                text = result["contents"][0].get("text", "")
                if text:
                    return {"success": True, "text": text, "source": "url"}
                return {"success": False, "error": f"Job page returned empty content. The page may require JavaScript or be protected. Try pasting the job description instead. URL: {job_url}"}
            if result.get("error"):
                return {"success": False, "error": f"EXA error: {result.get('error')}. Try pasting the job description instead."}
            return {"success": False, "error": f"Could not extract content from job page. The site may block scrapers or require login. Try pasting the job description instead. URL: {job_url}"}

        fetch_results = await asyncio.gather(
            fetch_profile_content(),
            fetch_job_content(),
            return_exceptions=True
        )

        profile_content = fetch_results[0] if not isinstance(fetch_results[0], Exception) else {"success": False, "error": str(fetch_results[0])}
        job_content = fetch_results[1] if not isinstance(fetch_results[1], Exception) else {"success": False, "error": str(fetch_results[1])}

        if not profile_content.get("success"):
            errors.append(f"Profile fetch failed: {profile_content.get('error')}")
        if not job_content.get("success"):
            errors.append(f"Job fetch failed: {job_content.get('error')}")

        if not profile_content.get("success") or not job_content.get("success"):
            return {"errors": errors, "current_step": "error", "progress_messages": progress}

        progress = _add_progress(progress, "ingest", "URLs fetched successfully", "Extracting structured data...")

        # Phase 2: Parse both with LLM in parallel
        logger.info("Phase 2: Parallel LLM parsing")
        progress = _add_progress(progress, "ingest", "Parsing profile with AI...", "Extracting skills, experience, education")

        llm = get_llm()

        async def parse_profile():
            messages = [
                SystemMessage(content=PROFILE_EXTRACTION_PROMPT),
                HumanMessage(content=f"Extract profile information from:\n\n{profile_content['text']}"),
            ]
            response = await llm.ainvoke(messages)
            return _parse_json_response(response.content)

        async def parse_job():
            messages = [
                SystemMessage(content=JOB_EXTRACTION_PROMPT),
                HumanMessage(content=f"Extract job posting information from:\n\n{job_content['text']}"),
            ]
            response = await llm.ainvoke(messages)
            return _parse_json_response(response.content)

        parse_results = await asyncio.gather(
            parse_profile(),
            parse_job(),
            return_exceptions=True
        )

        profile_data = parse_results[0] if not isinstance(parse_results[0], Exception) else None
        job_data = parse_results[1] if not isinstance(parse_results[1], Exception) else None

        if isinstance(parse_results[0], Exception):
            errors.append(f"Profile parse error: {str(parse_results[0])}")
        if isinstance(parse_results[1], Exception):
            errors.append(f"Job parse error: {str(parse_results[1])}")

        if not profile_data or not job_data:
            return {"errors": errors, "current_step": "error", "progress_messages": progress}

        # Add source URLs and raw text
        if linkedin_url:
            profile_data["linkedin_url"] = linkedin_url
        profile_data["raw_text"] = profile_content["text"]
        job_data["source_url"] = job_url if job_url else "pasted_job_description"
        job_data["raw_text"] = job_content["text"]

        # Add completion progress
        progress = _add_progress(progress, "ingest", "Profile and job parsed successfully",
                                f"Found: {profile_data.get('name', 'Unknown')} → {job_data.get('title', 'Unknown')} at {job_data.get('company_name', 'Unknown')}")

        logger.info(f"Ingest complete: {profile_data.get('name', 'Unknown')} -> {job_data.get('title', 'Unknown')}")

        return {
            "user_profile": profile_data,
            "job_posting": job_data,
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


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling code blocks."""
    import json
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content)
