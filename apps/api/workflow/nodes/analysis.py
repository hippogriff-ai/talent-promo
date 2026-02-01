"""Analysis node for identifying gaps and highlights.

Uses structured output (Pydantic) instead of JSON in prompt for cleaner,
more reliable output parsing. Prompt is organized for optimal Anthropic
caching: static instructions first, dynamic content last.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from config import get_settings
from workflow.state import ResumeState

logger = logging.getLogger(__name__)

settings = get_settings()


# =============================================================================
# Structured Output Schema (Fix #3: JSON via API instead of prompt)
# =============================================================================


class GapAnalysisOutput(BaseModel):
    """Structured output for gap analysis.

    Using Pydantic model with with_structured_output() ensures:
    - Type safety and validation
    - No JSON parsing errors
    - Cleaner prompts without JSON format instructions
    """

    strengths: list[str] = Field(
        description="Skills and experiences the candidate already has that match the job requirements. Be specific and reference actual experience."
    )
    gaps: list[str] = Field(
        description="Areas where the candidate may be lacking or needs to present differently. Be specific about what's missing."
    )
    recommended_emphasis: list[str] = Field(
        description="What the candidate should highlight in their resume with explanation of why."
    )
    transferable_skills: list[str] = Field(
        description="Skills from other areas that can be repositioned for this role."
    )
    keywords_to_include: list[str] = Field(
        description="ATS-friendly keywords that should appear in the resume."
    )
    potential_concerns: list[str] = Field(
        description="Red flags a hiring manager might notice and how to address them."
    )


def get_llm():
    """Get configured LLM for analysis."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
    )


def get_structured_llm():
    """Get LLM configured for structured output.

    Uses with_structured_output() which leverages Anthropic's tool_use
    for reliable JSON output without needing format instructions in prompt.
    """
    base_llm = get_llm()
    return base_llm.with_structured_output(GapAnalysisOutput)


# =============================================================================
# Prompt (Fix #4: Static content first for caching, dynamic content last)
# =============================================================================

# Static system prompt - this part gets cached by Anthropic
GAP_ANALYSIS_SYSTEM_PROMPT = """You are an expert career coach analyzing the fit between a candidate and a target job.

Your task is to identify:
1. STRENGTHS: Skills and experiences the candidate already has that match the job
2. GAPS: Areas where the candidate may be lacking or needs to present differently
3. RECOMMENDED EMPHASIS: What the candidate should highlight in their resume
4. TRANSFERABLE SKILLS: Skills from other areas that can be repositioned for this role
5. KEYWORDS: ATS-friendly keywords that should appear in the resume
6. POTENTIAL CONCERNS: Red flags a hiring manager might notice and how to address them

Be specific and actionable. Reference actual experience from the profile and requirements from the job.
Don't be generic - every item should be specific to this candidate and this role.

When analyzing:
- Look for direct skill matches first
- Identify transferable skills from adjacent domains
- Note experience gaps but suggest how to frame existing experience
- Extract important keywords from the job posting
- Consider seniority alignment and career trajectory"""


async def analyze_node(state: ResumeState) -> dict[str, Any]:
    """Analyze gaps between candidate profile and target job.

    Uses structured output for reliable JSON parsing and organizes
    the prompt for optimal Anthropic caching (static first, dynamic last).

    Compares using raw text (preferred) or structured data:
    - User profile/resume
    - Job posting/requirements
    - Research findings about similar successful candidates
    """
    logger.info("Starting analysis node")

    # Prefer raw text fields for LLM context (Fix #2: ensure markdown is used)
    profile_text = state.get("profile_text") or state.get("profile_markdown") or ""
    job_text = state.get("job_text") or state.get("job_markdown") or ""

    # Log what we're using for debugging
    logger.info(f"Analysis input - profile_text: {len(profile_text)} chars, job_text: {len(job_text)} chars")

    # Fall back to structured data if no raw text
    user_profile = state.get("user_profile") or {}
    job_posting = state.get("job_posting") or {}

    # Get metadata
    profile_name = state.get("profile_name") or user_profile.get("name", "Candidate")
    job_title = state.get("job_title") or job_posting.get("title", "Position")
    job_company = state.get("job_company") or job_posting.get("company_name", "Company")
    research = state.get("research")

    # Check we have either raw text or structured data
    has_profile = bool(profile_text) or bool(user_profile)
    has_job = bool(job_text) or bool(job_posting)

    if not has_profile or not has_job:
        logger.error(f"Missing data - has_profile: {has_profile}, has_job: {has_job}")
        return {
            "errors": [*state.get("errors", []), "Missing profile or job data for analysis"],
            "current_step": "error",
        }

    try:
        # Use structured output LLM
        llm = get_structured_llm()

        # Build profile section - prefer raw text (Fix #2)
        if profile_text:
            profile_section = profile_text[:5000]
        else:
            profile_section = f"""Name: {user_profile.get('name', 'Unknown')}
Headline: {user_profile.get('headline', 'N/A')}
Summary: {user_profile.get('summary', 'N/A')}

Experience:
{_format_experience(user_profile.get('experience', []))}

Education:
{_format_education(user_profile.get('education', []))}

Skills: {', '.join(user_profile.get('skills', []))}
Certifications: {', '.join(user_profile.get('certifications', []))}"""

        # Build job section - prefer raw text (Fix #2)
        if job_text:
            job_section = job_text[:4000]
        else:
            job_section = f"""Title: {job_posting.get('title', 'Unknown')}
Company: {job_posting.get('company_name', 'Unknown')}

Description:
{job_posting.get('description', 'N/A')[:1500]}

Requirements:
{chr(10).join('- ' + r for r in job_posting.get('requirements', []))}

Preferred Qualifications:
{chr(10).join('- ' + q for q in job_posting.get('preferred_qualifications', []))}

Tech Stack: {', '.join(job_posting.get('tech_stack', []))}"""

        # Build research context (optional)
        research_section = ""
        if research:
            research_section = f"""
---

RESEARCH INSIGHTS:
Company Culture: {research.get('company_culture', 'N/A')}
Company Values: {', '.join(research.get('company_values', []))}
Hiring Patterns: {research.get('hiring_patterns', 'N/A')}

Similar Successful Candidates:
{_format_similar_profiles(research.get('similar_profiles', []))}"""

        # =================================================================
        # FIX #4: Organize for optimal caching
        # - System message is static (cached across all calls)
        # - User message has dynamic content LAST
        # =================================================================

        # Dynamic content - organized for cache efficiency
        # Put most variable content (profile) at the very end
        user_content = f"""Analyze the fit and gaps for this candidate applying to the following position.

TARGET JOB:
Title: {job_title}
Company: {job_company}

{job_section}
{research_section}
---

CANDIDATE PROFILE:
{profile_section}"""

        messages = [
            SystemMessage(content=GAP_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        # Call with structured output - no JSON parsing needed
        result: GapAnalysisOutput = await llm.ainvoke(messages)

        # Convert Pydantic model to dict
        analysis_data = result.model_dump()

        logger.info(f"Analysis complete: {len(analysis_data.get('strengths', []))} strengths, {len(analysis_data.get('gaps', []))} gaps identified")

        return {
            "gap_analysis": analysis_data,
            "current_step": "qa",
            "qa_round": 0,
            "qa_complete": False,
            "user_done_signal": False,
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Analysis error: {str(e)}"],
            "current_step": "error",
        }


def _format_experience(experience: list[dict]) -> str:
    """Format experience for context."""
    if not experience:
        return "No experience listed"

    formatted = []
    for exp in experience:
        entry = f"- {exp.get('position', 'Unknown')} at {exp.get('company', 'Unknown')}"
        if exp.get('start_date') or exp.get('end_date'):
            entry += f" ({exp.get('start_date', '?')} - {exp.get('end_date', 'Present')})"
        if exp.get('achievements'):
            entry += "\n  Achievements: " + "; ".join(exp['achievements'][:3])
        if exp.get('technologies'):
            entry += "\n  Technologies: " + ", ".join(exp['technologies'])
        formatted.append(entry)

    return "\n".join(formatted)


def _format_education(education: list[dict]) -> str:
    """Format education for context."""
    if not education:
        return "No education listed"

    formatted = []
    for edu in education:
        entry = f"- {edu.get('degree', 'Degree')} in {edu.get('field_of_study', 'Unknown')} from {edu.get('institution', 'Unknown')}"
        if edu.get('end_date'):
            entry += f" ({edu.get('end_date')})"
        formatted.append(entry)

    return "\n".join(formatted)


def _format_similar_profiles(profiles: list[dict]) -> str:
    """Format similar profiles for context."""
    if not profiles:
        return "No similar profiles found"

    formatted = []
    for profile in profiles[:3]:  # Limit to top 3
        entry = f"- {profile.get('name', 'Unknown')}: {profile.get('headline', 'N/A')}"
        if profile.get('key_skills'):
            entry += f"\n  Skills: {', '.join(profile['key_skills'][:5])}"
        formatted.append(entry)

    return "\n".join(formatted)
