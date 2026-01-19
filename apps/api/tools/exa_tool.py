"""EXA search tool for web scraping and research.

EXA provides neural search and content retrieval capabilities
for LinkedIn profiles, job postings, and company research.
"""

import os
import logging
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Fallback: no-op decorator
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args or callable(args[0]) else decorator

logger = logging.getLogger(__name__)


def get_exa_client():
    """Get EXA client with API key from settings."""
    from exa_py import Exa
    from config import get_settings

    settings = get_settings()
    api_key = settings.exa_api_key

    if not api_key:
        raise ValueError("EXA_API_KEY not set in environment or .env file")

    return Exa(api_key=api_key)


# ============================================================================
# Parameter Models
# ============================================================================

class ExaSearchParams(BaseModel):
    """Parameters for EXA search."""
    query: str = Field(..., description="Search query")
    num_results: int = Field(default=5, le=10, description="Number of results")
    search_type: Literal["auto", "keyword", "neural"] = Field(
        default="auto",
        description="Search type: auto, keyword, or neural"
    )
    use_autoprompt: bool = Field(
        default=True,
        description="Let EXA optimize the query"
    )
    include_domains: Optional[list[str]] = Field(
        default=None,
        description="Only search these domains"
    )
    exclude_domains: Optional[list[str]] = Field(
        default=None,
        description="Exclude these domains"
    )
    start_published_date: Optional[str] = Field(
        default=None,
        description="Filter by publish date (YYYY-MM-DD)"
    )


class ExaContentParams(BaseModel):
    """Parameters for fetching URL contents."""
    urls: list[str] = Field(..., description="URLs to fetch content from")
    include_text: bool = Field(default=True, description="Include full text")
    include_highlights: bool = Field(default=True, description="Include key highlights")
    include_summary: bool = Field(default=True, description="Include AI summary")


# ============================================================================
# Tools
# ============================================================================

@tool
@traceable(name="exa_search", run_type="tool")
def exa_search(
    query: str,
    num_results: int = 5,
    search_type: str = "auto",
    use_autoprompt: bool = True,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict:
    """Search the web using EXA's neural search.

    Use for researching companies, finding similar profiles, industry trends.
    Returns both raw text and AI-generated summaries.

    Args:
        query: Search query (e.g., "Stripe engineering culture")
        num_results: Number of results to return (max 10)
        search_type: "auto", "keyword", or "neural"
        use_autoprompt: Let EXA optimize the query
        include_domains: Only search these domains (e.g., ["linkedin.com"])
        exclude_domains: Exclude these domains

    Returns:
        Dict with search results including title, url, summary, highlights, text
    """
    try:
        exa = get_exa_client()

        # Build search parameters
        # Note: use_autoprompt was removed in newer EXA API versions
        search_kwargs = {
            "query": query,
            "num_results": min(num_results, 10),
            "type": search_type,
            "text": True,
            "highlights": True,
            "summary": True,
        }

        if include_domains:
            search_kwargs["include_domains"] = include_domains
        if exclude_domains:
            search_kwargs["exclude_domains"] = exclude_domains

        results = exa.search_and_contents(**search_kwargs)

        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "summary": getattr(r, "summary", None),
                    "highlights": getattr(r, "highlights", []),
                    "text": r.text[:3000] if r.text else None,  # Truncate for context
                    "published_date": getattr(r, "published_date", None),
                }
                for r in results.results
            ]
        }

    except Exception as e:
        logger.error(f"EXA search failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "results": []
        }


@tool
@traceable(name="exa_get_contents", run_type="tool")
def exa_get_contents(
    urls: list[str],
    include_text: bool = True,
    include_highlights: bool = True,
    include_summary: bool = True,
    livecrawl: str = "fallback",
) -> dict:
    """Fetch full content from specific URLs.

    Use for getting LinkedIn profile details, job posting content,
    or full article text from URLs you've discovered.

    Args:
        urls: List of URLs to fetch content from
        include_text: Include full page text
        include_highlights: Include key excerpts
        include_summary: Include AI-generated summary
        livecrawl: "always" for fresh content (use for LinkedIn), "fallback" for cached-first, "never" for cached only

    Returns:
        Dict with content for each URL
    """
    try:
        exa = get_exa_client()

        results = exa.get_contents(
            urls=urls,
            text=include_text,
            highlights=include_highlights,
            summary=include_summary,
            livecrawl=livecrawl,
        )

        return {
            "success": True,
            "contents": [
                {
                    "url": r.url,
                    "title": r.title,
                    "text": r.text,
                    "summary": getattr(r, "summary", None),
                    "highlights": getattr(r, "highlights", []),
                }
                for r in results.results
            ]
        }

    except Exception as e:
        logger.error(f"EXA get_contents failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "contents": []
        }


# LinkedIn Profile Schema for EXA structured extraction
LINKEDIN_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Full name"},
        "headline": {"type": "string", "description": "Professional headline"},
        "summary": {"type": "string", "description": "About/summary section"},
        "location": {"type": "string", "description": "Location"},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "position": {"type": "string"},
                    "location": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "is_current": {"type": "boolean"},
                    "description": {"type": "string"},
                }
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "school": {"type": "string"},
                    "degree": {"type": "string"},
                    "field_of_study": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                }
            }
        },
        "skills": {
            "type": "array",
            "items": {"type": "string"}
        },
        "certifications": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

# Job Posting Schema for EXA structured extraction
JOB_POSTING_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Job title"},
        "company_name": {"type": "string", "description": "Company name"},
        "location": {"type": "string", "description": "Job location"},
        "description": {"type": "string", "description": "Full job description"},
        "requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required qualifications"
        },
        "responsibilities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key responsibilities"
        },
        "tech_stack": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technologies mentioned"
        },
        "benefits": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Benefits and perks"
        },
        "salary_range": {"type": "string", "description": "Salary range if mentioned"},
        "employment_type": {"type": "string", "description": "Full-time, part-time, contract, etc."},
        "experience_level": {"type": "string", "description": "Entry, mid, senior, etc."}
    }
}


@traceable(name="exa_get_structured_content", run_type="tool")
def exa_get_structured_content(
    url: str,
    content_type: Literal["linkedin_profile", "job_posting"],
) -> dict:
    """Fetch and extract structured data from a URL using EXA's schema feature.

    This bypasses the need for LLM parsing by using EXA's built-in
    structured extraction with JSON schema.

    Args:
        url: URL to fetch content from
        content_type: Type of content to extract schema for

    Returns:
        Dict with structured data or error
    """
    try:
        exa = get_exa_client()

        # Select schema based on content type
        schema = LINKEDIN_PROFILE_SCHEMA if content_type == "linkedin_profile" else JOB_POSTING_SCHEMA
        query = "Extract professional profile information" if content_type == "linkedin_profile" else "Extract job posting details"

        # Use EXA's structured summary with schema
        # Use fallback mode: cached data if available, live crawl otherwise
        # Note: "always" mode fails on many sites due to bot protection
        livecrawl_mode = "fallback"
        results = exa.get_contents(
            urls=[url],
            text=True,
            highlights=True,
            summary={
                "query": query,
                "schema": schema,
            },
            livecrawl=livecrawl_mode,
        )

        if not results.results:
            return {
                "success": False,
                "error": "No content returned from URL",
                "structured_data": None,
                "raw_text": None,
            }

        result = results.results[0]

        # Extract structured data from summary if available
        # EXA returns summary as a JSON STRING when schema is provided
        structured_data = None
        if hasattr(result, "summary") and result.summary:
            import json as json_module
            if isinstance(result.summary, str):
                # EXA returns JSON as a string - parse it
                try:
                    structured_data = json_module.loads(result.summary)
                    logger.info(f"Successfully parsed EXA structured summary for {url}")
                except json_module.JSONDecodeError as e:
                    logger.warning(f"Failed to parse EXA summary as JSON: {e}")
                    structured_data = None
            elif isinstance(result.summary, dict):
                # Already a dict (shouldn't happen but handle it)
                structured_data = result.summary.get("parsed", result.summary)

        return {
            "success": True,
            "structured_data": structured_data,
            "raw_text": result.text,
            "title": result.title,
            "url": result.url,
        }

    except Exception as e:
        logger.error(f"EXA structured extraction failed for {url}: {e}")
        return {
            "success": False,
            "error": str(e),
            "structured_data": None,
            "raw_text": None,
        }


@tool
@traceable(name="exa_find_similar", run_type="tool")
def exa_find_similar(
    url: str,
    num_results: int = 5,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict:
    """Find similar pages/profiles to a given URL.

    Use for finding similar LinkedIn profiles for competitive analysis,
    or finding related job postings.

    Args:
        url: Reference URL to find similar content to
        num_results: Number of similar results to return
        include_domains: Only include results from these domains
        exclude_domains: Exclude results from these domains

    Returns:
        Dict with similar pages including title, url, summary
    """
    try:
        exa = get_exa_client()

        search_kwargs = {
            "url": url,
            "num_results": min(num_results, 10),
            "text": True,
            "summary": True,
        }

        if include_domains:
            search_kwargs["include_domains"] = include_domains
        if exclude_domains:
            search_kwargs["exclude_domains"] = exclude_domains

        results = exa.find_similar_and_contents(**search_kwargs)

        return {
            "success": True,
            "reference_url": url,
            "similar_pages": [
                {
                    "url": r.url,
                    "title": r.title,
                    "summary": getattr(r, "summary", None),
                    "text": r.text[:2000] if r.text else None,
                }
                for r in results.results
            ]
        }

    except Exception as e:
        logger.error(f"EXA find_similar failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "reference_url": url,
            "similar_pages": []
        }


# ============================================================================
# Specialized Search Functions (not LangChain tools, for direct use)
# ============================================================================

@traceable(name="fetch_linkedin_profile", run_type="tool")
async def fetch_linkedin_profile(linkedin_url: str) -> dict:
    """Fetch and parse a LinkedIn profile URL.

    Args:
        linkedin_url: LinkedIn profile URL

    Returns:
        Dict with profile information
    """
    result = exa_get_contents.invoke({
        "urls": [linkedin_url],
        "include_text": True,
        "include_highlights": True,
        "include_summary": True,
        "livecrawl": "always",  # Always fetch fresh - profiles change
    })

    if result["success"] and result["contents"]:
        content = result["contents"][0]
        return {
            "success": True,
            "url": linkedin_url,
            "raw_text": content.get("text", ""),
            "summary": content.get("summary", ""),
            "highlights": content.get("highlights", []),
        }

    return {
        "success": False,
        "error": result.get("error", "No content returned"),
        "url": linkedin_url,
    }


@traceable(name="fetch_job_posting", run_type="tool")
async def fetch_job_posting(job_url: str) -> dict:
    """Fetch and parse a job posting URL.

    Args:
        job_url: Job posting URL

    Returns:
        Dict with job posting information
    """
    result = exa_get_contents.invoke({
        "urls": [job_url],
        "include_text": True,
        "include_highlights": True,
        "include_summary": True,
        "livecrawl": "fallback",  # Use cached if available, jobs don't change as often
    })

    if result["success"] and result["contents"]:
        content = result["contents"][0]
        return {
            "success": True,
            "url": job_url,
            "title": content.get("title", ""),
            "raw_text": content.get("text", ""),
            "summary": content.get("summary", ""),
            "highlights": content.get("highlights", []),
        }

    return {
        "success": False,
        "error": result.get("error", "No content returned"),
        "url": job_url,
    }


@traceable(name="research_company", run_type="tool")
async def research_company(company_name: str) -> dict:
    """Research a company's culture, values, and tech stack.

    Args:
        company_name: Name of the company to research

    Returns:
        Dict with company research findings
    """
    # Search for company culture
    culture_result = exa_search.invoke({
        "query": f"{company_name} company culture engineering team values work environment",
        "num_results": 5,
        "include_domains": ["linkedin.com", "glassdoor.com", "builtin.com", "levels.fyi"],
    })

    # Search for tech stack
    tech_result = exa_search.invoke({
        "query": f"{company_name} engineering tech stack technology blog",
        "num_results": 3,
        "include_domains": ["medium.com", "engineering.*.com", "blog.*.com", "github.com"],
    })

    # Search for recent news
    news_result = exa_search.invoke({
        "query": f"{company_name} company news funding growth",
        "num_results": 3,
    })

    return {
        "success": True,
        "company": company_name,
        "culture": culture_result.get("results", []),
        "tech_stack": tech_result.get("results", []),
        "news": news_result.get("results", []),
    }


@traceable(name="find_similar_employees", run_type="tool")
async def find_similar_employees(
    company_name: str,
    job_title: str,
    num_results: int = 5,
) -> dict:
    """Find LinkedIn profiles of similar employees at the company.

    Args:
        company_name: Name of the company
        job_title: Job title to search for
        num_results: Number of profiles to find

    Returns:
        Dict with similar employee profiles
    """
    result = exa_search.invoke({
        "query": f"site:linkedin.com/in {job_title} at {company_name}",
        "num_results": num_results,
        "include_domains": ["linkedin.com"],
    })

    return {
        "success": result.get("success", False),
        "company": company_name,
        "job_title": job_title,
        "profiles": result.get("results", []),
    }
