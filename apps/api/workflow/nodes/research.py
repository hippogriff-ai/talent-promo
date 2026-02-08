"""Research node for gathering company and role context."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import ResumeState
from tools.exa_tool import exa_search, exa_find_similar
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


def get_llm():
    """Get configured LLM for research synthesis."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.3,
        max_tokens=8192,
    )


RESEARCH_AND_ANALYSIS_PROMPT = """You are an expert career researcher and coach helping someone optimize their resume for a specific role.

Based on the research gathered about the company, similar employees, and the candidate's profile, provide:
1. RESEARCH SYNTHESIS - Company insights, culture, tech stack
2. GAP ANALYSIS - How the candidate fits the role

Output your analysis in JSON format:

{
    "research": {
        "company_overview": "Detailed overview of the company - mission, size, industry position, products (3-5 sentences minimum)",
        "company_culture": "Comprehensive description of company culture - work environment, team dynamics, decision-making style, communication norms, growth opportunities (3-5 sentences minimum)",
        "company_values": ["Value 1", "Value 2"],
        "tech_stack_details": [
            {"technology": "Tech name", "usage": "How it's used", "importance": "critical/important/nice-to-have"}
        ],
        "similar_profiles": [
            {
                "name": "Person name",
                "headline": "Their headline",
                "key_skills": ["Skill 1", "Skill 2"]
            }
        ],
        "company_news": ["Recent news item 1", "Recent news item 2"],
        "hiring_patterns": "Detailed insights about what the company looks for in candidates - interview process, team fit, technical expectations (3-5 sentences minimum)",
        "hiring_criteria": {
            "must_haves": ["Essential skill/qualification 1"],
            "preferred": ["Nice-to-have qualification 1"],
            "keywords": ["ATS keyword 1", "ATS keyword 2"],
            "ats_keywords": ["Technical term 1", "Technical term 2"]
        },
        "ideal_profile": {
            "headline": "Ideal candidate headline for this role",
            "summary_focus": ["Key point to emphasize 1"],
            "experience_emphasis": ["Type of experience to highlight 1"],
            "skills_priority": ["Top skill 1", "Top skill 2"],
            "differentiators": ["What would make a candidate stand out"]
        }
    },
    "gap_analysis": {
        "strengths": ["Specific strength that matches job requirements"],
        "gaps": ["Specific gap or area for improvement"],
        "recommended_emphasis": ["What to highlight with explanation"],
        "transferable_skills": ["Skill that can be repositioned"],
        "keywords_to_include": ["keyword1", "keyword2"],
        "potential_concerns": ["Concern and how to address it"]
    }
}

Be specific and actionable. Reference actual experience from the profile and requirements from the job."""


async def research_node(state: ResumeState) -> dict[str, Any]:
    """Research company and analyze candidate fit - OPTIMIZED.

    All 4 EXA searches run in parallel, then combined research + analysis
    in a single LLM call. Reduces total time from ~140s to ~30s.
    """
    logger.info("Starting optimized research node (parallel EXA + combined analysis)")

    job_posting = state.get("job_posting") or {}
    user_profile = state.get("user_profile") or {}
    progress = list(state.get("progress_messages", []))

    # Get raw text fields (set during ingest) - these contain the actual content
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_text = state.get("job_text") or state.get("job_markdown") or ""

    # Get metadata (extracted via regex during ingest)
    company_name = state.get("job_company") or job_posting.get("company_name") or ""
    job_title = state.get("job_title") or job_posting.get("title") or ""
    tech_stack = job_posting.get("tech_stack") or []

    if not job_text and not job_posting:
        return {
            "errors": [*state.get("errors", []), "No job posting data available for research"],
            "current_step": "error",
            "progress_messages": progress,
        }

    try:
        # Build search queries
        culture_query = f"{company_name} company culture engineering team work environment values"
        if tech_stack:
            tech_query = f"{company_name} engineering tech stack {' '.join(tech_stack[:5])}"
        else:
            tech_query = f"{company_name} engineering technology stack blog"
        similar_query = f"site:linkedin.com/in {job_title} {company_name}"
        news_query = f'"{company_name}" recent news announcements 2024 2025'

        # ============================================================
        # PHASE 1: Run all 4 EXA searches in parallel
        # ============================================================
        logger.info(f"Phase 1: Parallel EXA searches for {company_name}")

        # Add progress message showing all search queries
        progress = _add_progress(progress, "research", f"Researching {company_name}...",
                                "Running 4 parallel searches")
        progress = _add_progress(progress, "research", "🔍 Searching company culture",
                                f'Query: "{culture_query[:60]}..."')
        progress = _add_progress(progress, "research", "🔍 Searching tech stack",
                                f'Query: "{tech_query[:60]}..."')
        progress = _add_progress(progress, "research", "🔍 Finding similar employees",
                                f'Query: "{similar_query[:60]}..."')
        progress = _add_progress(progress, "research", "🔍 Searching company news",
                                f'Query: "{news_query[:60]}..."')

        async def search_culture():
            return exa_search.invoke({
                "query": culture_query,
                "num_results": 5,
                "include_domains": ["linkedin.com", "glassdoor.com", "builtin.com", "levels.fyi", "teamblind.com"],
            })

        async def search_tech():
            return exa_search.invoke({
                "query": tech_query,
                "num_results": 5,
            })

        async def search_similar():
            return exa_search.invoke({
                "query": similar_query,
                "num_results": 5,
                "include_domains": ["linkedin.com"],
            })

        async def search_news():
            return exa_search.invoke({
                "query": news_query,
                "num_results": 3,
            })

        # Execute all searches in parallel
        search_results = await asyncio.gather(
            search_culture(),
            search_tech(),
            search_similar(),
            search_news(),
            return_exceptions=True
        )

        # Process results safely and track failures
        failed_searches = []

        def safe_get_results(result, search_name):
            if isinstance(result, Exception):
                failed_searches.append((search_name, str(result)))
                logger.warning(f"Search '{search_name}' failed: {result}")
                return []
            if not result.get("success"):
                failed_searches.append((search_name, result.get("error", "Unknown error")))
                logger.warning(f"Search '{search_name}' returned error: {result.get('error')}")
                return []
            return result.get("results", [])

        research_results = {
            "culture": safe_get_results(search_results[0], "culture"),
            "tech": safe_get_results(search_results[1], "tech"),
            "similar_profiles": safe_get_results(search_results[2], "similar"),
            "news": safe_get_results(search_results[3], "news"),
        }

        # Check if too many searches failed (3 or more = critical failure)
        if len(failed_searches) >= 3:
            error_msg = f"Research failed: {len(failed_searches)}/4 searches failed - {failed_searches}"
            logger.error(error_msg)
            return {
                "errors": [*errors, error_msg],
                "current_step": "error",
                "progress_messages": progress,
            }

        # Add results summary
        progress = _add_progress(progress, "research", "Search results collected",
                                f"Culture: {len(research_results['culture'])} results, Tech: {len(research_results['tech'])} results, Similar: {len(research_results['similar_profiles'])} profiles, News: {len(research_results['news'])} articles")

        logger.info(f"EXA complete: culture={len(research_results['culture'])}, tech={len(research_results['tech'])}, similar={len(research_results['similar_profiles'])}, news={len(research_results['news'])}")

        # ============================================================
        # PHASE 2: Combined research synthesis + gap analysis (1 LLM call)
        # ============================================================
        logger.info("Phase 2: Combined research synthesis + gap analysis")
        progress = _add_progress(progress, "research", "Analyzing findings with AI...",
                                "Synthesizing research + identifying gaps and opportunities")
        llm = get_llm()

        # Build combined context using raw text (set during ingest)
        # This is much more reliable than structured extraction which may return empty arrays
        synthesis_context = f"""
CANDIDATE PROFILE:
{profile_text[:3000] if profile_text else "No profile text available"}

---

TARGET JOB:
Company: {company_name}
Role: {job_title}

{job_text[:3000] if job_text else "No job description available"}

---

COMPANY RESEARCH:

CULTURE:
{_format_search_results(research_results['culture'])}

TECH STACK:
{_format_search_results(research_results['tech'])}

SIMILAR EMPLOYEES:
{_format_search_results(research_results['similar_profiles'])}

NEWS:
{_format_search_results(research_results['news'])}
"""

        messages = [
            SystemMessage(content=RESEARCH_AND_ANALYSIS_PROMPT),
            HumanMessage(content=f"Analyze and synthesize:\n\n{synthesis_context}"),
        ]

        response = await llm.ainvoke(messages)

        # Parse JSON from response
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result_data = json.loads(content)
            research_data = result_data.get("research", {})
            gap_analysis = result_data.get("gap_analysis", {})

        except json.JSONDecodeError as e:
            logger.warning(
                f"Research JSON truncated or malformed (response length: {len(response.content)} chars). "
                f"Falling back to empty gap analysis. Parse error: {e}"
            )
            # Create fallback data (minimal since we use raw text now)
            research_data = {
                "company_overview": f"Research gathered for {company_name}",
                "company_culture": "See raw research results",
                "company_values": [],
                "tech_stack_details": [{"technology": t, "usage": "", "importance": "unknown"} for t in tech_stack],
                "similar_profiles": [],
                "company_news": [],
                "hiring_patterns": "",
                "hiring_criteria": {
                    "must_haves": [],
                    "preferred": [],
                    "keywords": tech_stack[:5] if tech_stack else [],
                    "ats_keywords": [],
                },
                "ideal_profile": {
                    "headline": job_title,
                    "summary_focus": [],
                    "experience_emphasis": [],
                    "skills_priority": tech_stack[:5] if tech_stack else [],
                    "differentiators": [],
                },
            }
            gap_analysis = {
                "strengths": [],
                "gaps": [],
                "recommended_emphasis": [],
                "transferable_skills": [],
                "keywords_to_include": tech_stack[:10] if tech_stack else [],
                "potential_concerns": [],
            }

        logger.info("Research + analysis complete")

        # Add completion progress
        strengths_count = len(gap_analysis.get("strengths", []))
        gaps_count = len(gap_analysis.get("gaps", []))
        progress = _add_progress(progress, "research", "Research complete!",
                                f"Found {strengths_count} strengths, {gaps_count} gaps to address")

        return {
            "research": research_data,
            "gap_analysis": gap_analysis,
            "current_step": "qa",
            "qa_round": 0,
            "qa_complete": False,
            "user_done_signal": False,
            "progress_messages": progress,
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Research error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Research error: {str(e)}"],
            "current_step": "error",
            "progress_messages": progress,
        }


def _format_experience(experience: list[dict]) -> str:
    """Format experience for context."""
    if not experience:
        return "No experience listed"

    formatted = []
    for exp in experience[:5]:  # Limit to 5 most recent
        entry = f"- {exp.get('position', 'Unknown')} at {exp.get('company', 'Unknown')}"
        if exp.get('start_date') or exp.get('end_date'):
            entry += f" ({exp.get('start_date', '?')} - {exp.get('end_date', 'Present')})"
        if exp.get('achievements'):
            entry += "\n  Achievements: " + "; ".join(exp['achievements'][:3])
        if exp.get('technologies'):
            entry += "\n  Technologies: " + ", ".join(exp['technologies'][:5])
        formatted.append(entry)

    return "\n".join(formatted)


def _format_search_results(results: list[dict]) -> str:
    """Format search results for LLM context."""
    if not results:
        return "No results found."

    formatted = []
    for r in results[:3]:  # Limit to 3 results per category
        title = r.get("title", "Untitled")
        summary = r.get("summary", "")
        text = r.get("text", "")[:1500] if r.get("text") else ""

        entry = f"- {title}"
        if summary:
            entry += f"\n  {summary}"
        elif text:
            entry += f"\n  {text}..."

        formatted.append(entry)

    return "\n".join(formatted)
