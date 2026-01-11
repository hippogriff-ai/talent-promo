"""Analysis node for identifying gaps and highlights."""

import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import ResumeState

logger = logging.getLogger(__name__)

settings = get_settings()


def get_llm():
    """Get configured LLM for analysis."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
    )


GAP_ANALYSIS_PROMPT = """You are an expert career coach analyzing the fit between a candidate and a target job.

Your task is to identify:
1. STRENGTHS: Skills and experiences the candidate already has that match the job
2. GAPS: Areas where the candidate may be lacking or needs to present differently
3. RECOMMENDED EMPHASIS: What the candidate should highlight in their resume
4. TRANSFERABLE SKILLS: Skills from other areas that can be repositioned for this role
5. KEYWORDS: ATS-friendly keywords that should appear in the resume
6. POTENTIAL CONCERNS: Red flags a hiring manager might notice and how to address them

Output your analysis in JSON format:

{
    "strengths": [
        "Specific strength that matches job requirements"
    ],
    "gaps": [
        "Specific gap or area for improvement"
    ],
    "recommended_emphasis": [
        "What to highlight with explanation"
    ],
    "transferable_skills": [
        "Skill that can be repositioned"
    ],
    "keywords_to_include": [
        "keyword1", "keyword2"
    ],
    "potential_concerns": [
        "Concern and how to address it"
    ]
}

Be specific and actionable. Reference actual experience from the profile and requirements from the job.
Don't be generic - every item should be specific to this candidate and this role."""


async def analyze_node(state: ResumeState) -> dict[str, Any]:
    """Analyze gaps between candidate profile and target job.

    Compares:
    - User profile (skills, experience, education)
    - Job requirements
    - Research findings about similar successful candidates
    """
    logger.info("Starting analysis node")

    user_profile = state.get("user_profile")
    job_posting = state.get("job_posting")
    research = state.get("research")

    if not user_profile or not job_posting:
        return {
            "errors": [*state.get("errors", []), "Missing profile or job data for analysis"],
            "current_step": "error",
        }

    try:
        llm = get_llm()

        # Build analysis context
        analysis_context = f"""
CANDIDATE PROFILE:
Name: {user_profile.get('name', 'Unknown')}
Headline: {user_profile.get('headline', 'N/A')}
Summary: {user_profile.get('summary', 'N/A')}

Experience:
{_format_experience(user_profile.get('experience', []))}

Education:
{_format_education(user_profile.get('education', []))}

Skills: {', '.join(user_profile.get('skills', []))}
Certifications: {', '.join(user_profile.get('certifications', []))}

---

TARGET JOB:
Title: {job_posting.get('title', 'Unknown')}
Company: {job_posting.get('company_name', 'Unknown')}

Description:
{job_posting.get('description', 'N/A')[:1500]}

Requirements:
{chr(10).join('- ' + r for r in job_posting.get('requirements', []))}

Preferred Qualifications:
{chr(10).join('- ' + q for q in job_posting.get('preferred_qualifications', []))}

Tech Stack: {', '.join(job_posting.get('tech_stack', []))}

---

RESEARCH INSIGHTS:
Company Culture: {research.get('company_culture', 'N/A') if research else 'N/A'}
Company Values: {', '.join(research.get('company_values', [])) if research else 'N/A'}
Hiring Patterns: {research.get('hiring_patterns', 'N/A') if research else 'N/A'}

Similar Successful Candidates:
{_format_similar_profiles(research.get('similar_profiles', []) if research else [])}
"""

        messages = [
            SystemMessage(content=GAP_ANALYSIS_PROMPT),
            HumanMessage(content=f"Analyze the fit and gaps for this candidate:\n\n{analysis_context}"),
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

            analysis_data = json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis JSON: {e}")
            return {
                "errors": [*state.get("errors", []), f"Failed to parse analysis: {str(e)}"],
                "current_step": "error",
            }

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
