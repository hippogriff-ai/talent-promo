"""Drafting node for generating ATS-friendly resume with suggestions."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import (
    ResumeState,
    DraftingSuggestion,
    DraftVersion,
    DraftValidationResult,
)

logger = logging.getLogger(__name__)

settings = get_settings()


def _extract_content_from_code_block(content: str, language: str = "json") -> str:
    """Extract content from LLM response wrapped in markdown code blocks.

    Args:
        content: Raw LLM response that may be wrapped in code fences
        language: Expected language (e.g., 'json', 'html')

    Returns:
        Extracted content without code fences
    """
    lang_marker = f"```{language}"
    if lang_marker in content:
        content = content.split(lang_marker)[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return content.strip()


def get_llm(temperature: float = 0.4):
    """Get configured LLM for resume drafting."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        max_tokens=4096,
    )


RESUME_DRAFTING_PROMPT = """You are an expert resume writer who creates ATS-friendly, compelling resumes.

Your task is to create a tailored resume that:
1. Is optimized for Applicant Tracking Systems (ATS) with relevant keywords
2. Sounds natural and human - NOT robotic or obviously AI-generated
3. Quantifies achievements with metrics wherever possible
4. Highlights transferable skills and addresses gaps strategically
5. Uses strong action verbs and concise bullet points
6. Is tailored specifically to the target job

WRITING GUIDELINES:
- Use first-person implied (no "I" but write as if candidate is speaking)
- Each bullet should start with a strong action verb
- Quantify with numbers: "increased by 40%", "managed team of 5", "reduced time by 2 hours"
- Keep bullets to 1-2 lines each
- Summary should be 2-4 sentences, impactful and specific
- Include ALL relevant keywords from the job posting naturally
- Don't use buzzwords like "synergy", "leverage", "utilize" excessively
- Vary sentence structure to sound natural

OUTPUT FORMAT (HTML for Tiptap editor):

<h1>[Candidate Name]</h1>
<p>[Contact info: email | phone | location | LinkedIn]</p>

<h2>Professional Summary</h2>
<p>[2-4 sentence summary tailored to this specific role]</p>

<h2>Experience</h2>
<h3>[Job Title] | [Company] | [Dates]</h3>
<ul>
<li>[Achievement bullet with metrics]</li>
<li>[Achievement bullet with metrics]</li>
</ul>

<h2>Education</h2>
<p><strong>[Degree]</strong> - [Institution], [Year]</p>

<h2>Skills</h2>
<p>[Comma-separated skills, prioritized for ATS]</p>

<h2>Certifications</h2>
<ul>
<li>[Certification name]</li>
</ul>

Make sure the HTML is clean and well-formatted for a rich text editor."""


SUGGESTION_GENERATION_PROMPT = """You are an expert resume consultant reviewing a resume draft for a specific job application.

Analyze this resume and generate 3-5 specific improvement suggestions. Focus on:
1. Making achievements more quantifiable
2. Better keyword alignment with the job posting
3. Strengthening weak bullet points
4. Improving the professional summary
5. Better highlighting relevant experience

For each suggestion, identify:
- The exact text to change (original_text)
- Your proposed improvement (proposed_text)
- Why this change improves the resume (rationale)
- Where in the resume (location): "summary", "experience.0", "skills", etc.

OUTPUT FORMAT (JSON array):
[
  {
    "location": "summary",
    "original_text": "the exact text from the resume",
    "proposed_text": "your improved version",
    "rationale": "why this is better"
  }
]

Only output the JSON array, no other text."""


# Action verb list for validation
ACTION_VERBS = {
    "achieved", "accomplished", "accelerated", "administered", "analyzed",
    "built", "collaborated", "created", "delivered", "designed", "developed",
    "directed", "enhanced", "established", "executed", "expanded", "facilitated",
    "generated", "grew", "guided", "handled", "implemented", "improved",
    "increased", "initiated", "introduced", "launched", "led", "maintained",
    "managed", "maximized", "minimized", "negotiated", "optimized", "orchestrated",
    "organized", "oversaw", "pioneered", "planned", "produced", "promoted",
    "provided", "reduced", "redesigned", "resolved", "restructured", "revamped",
    "saved", "secured", "simplified", "spearheaded", "streamlined", "strengthened",
    "supervised", "transformed", "upgraded"
}


async def draft_resume_node(state: ResumeState) -> dict[str, Any]:
    """Draft an ATS-friendly resume based on all gathered information.

    Uses:
    - Original user profile
    - Job posting requirements
    - Gap analysis recommendations
    - Q&A interview responses
    - Discovered experiences from discovery stage
    """
    logger.info("Starting resume drafting node")

    user_profile = state.get("user_profile", {})
    job_posting = state.get("job_posting", {})
    gap_analysis = state.get("gap_analysis", {})
    qa_history = state.get("qa_history", [])
    research = state.get("research", {})
    discovered_experiences = state.get("discovered_experiences", [])

    if not user_profile or not job_posting:
        return {
            "errors": [*state.get("errors", []), "Missing profile or job data for drafting"],
            "current_step": "error",
        }

    try:
        llm = get_llm()

        # Build comprehensive drafting context
        context = _build_drafting_context(
            user_profile, job_posting, gap_analysis, qa_history, research, discovered_experiences
        )

        messages = [
            SystemMessage(content=RESUME_DRAFTING_PROMPT),
            HumanMessage(content=f"Create an ATS-optimized resume based on:\n\n{context}"),
        ]

        response = await llm.ainvoke(messages)

        resume_html = _extract_content_from_code_block(response.content, "html")

        logger.info(f"Resume draft generated: {len(resume_html)} characters")

        # Create initial version
        initial_version = DraftVersion(
            version="1.0",
            html_content=resume_html,
            trigger="initial",
            description="Initial draft generated from profile and job analysis",
            change_log=[],
            created_at=datetime.now().isoformat(),
        )

        # Generate improvement suggestions
        suggestions = await _generate_suggestions(resume_html, job_posting, gap_analysis)

        # Also create structured data for potential JSON editing
        resume_structured = {
            "name": user_profile.get("name", ""),
            "contact": {
                "email": user_profile.get("email", ""),
                "phone": user_profile.get("phone", ""),
                "location": user_profile.get("location", ""),
                "linkedin": user_profile.get("linkedin_url", ""),
            },
            "target_job": {
                "title": job_posting.get("title", ""),
                "company": job_posting.get("company_name", ""),
            },
            "keywords_used": gap_analysis.get("keywords_to_include", []),
        }

        return {
            "resume_html": resume_html,
            "resume_draft": resume_structured,
            "draft_suggestions": [s.model_dump() for s in suggestions],
            "draft_versions": [initial_version.model_dump()],
            "draft_change_log": [],
            "draft_current_version": "1.0",
            "draft_approved": False,
            "current_step": "draft",
            "sub_step": "suggestions_ready",
            "updated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Resume drafting error: {e}")
        return {
            "errors": [*state.get("errors", []), f"Resume drafting error: {str(e)}"],
            "current_step": "error",
        }


def _build_drafting_context(
    user_profile: dict,
    job_posting: dict,
    gap_analysis: dict,
    qa_history: list,
    research: dict,
    discovered_experiences: list,
) -> str:
    """Build comprehensive context for resume drafting."""
    context = f"""
CANDIDATE INFORMATION:
Name: {user_profile.get('name', 'Candidate')}
Email: {user_profile.get('email', '')}
Phone: {user_profile.get('phone', '')}
Location: {user_profile.get('location', '')}
LinkedIn: {user_profile.get('linkedin_url', '')}

Current Headline: {user_profile.get('headline', '')}
Current Summary: {user_profile.get('summary', '')}

WORK EXPERIENCE:
{_format_experience_for_draft(user_profile.get('experience', []))}

EDUCATION:
{_format_education_for_draft(user_profile.get('education', []))}

SKILLS: {', '.join(user_profile.get('skills', []))}

CERTIFICATIONS: {', '.join(user_profile.get('certifications', []))}

---

TARGET JOB:
Title: {job_posting.get('title', '')}
Company: {job_posting.get('company_name', '')}

Job Description:
{job_posting.get('description', '')[:2000]}

Requirements:
{chr(10).join('- ' + r for r in job_posting.get('requirements', []))}

Tech Stack to highlight: {', '.join(job_posting.get('tech_stack', []))}

---

GAP ANALYSIS RECOMMENDATIONS:

Strengths to Emphasize:
{chr(10).join('- ' + s for s in gap_analysis.get('strengths', []))}

Areas to Address:
{chr(10).join('- ' + g for g in gap_analysis.get('gaps', []))}

What to Highlight:
{chr(10).join('- ' + e for e in gap_analysis.get('recommended_emphasis', []))}

Keywords to Include: {', '.join(gap_analysis.get('keywords_to_include', []))}

---

ADDITIONAL INFORMATION FROM INTERVIEW:
{_format_qa_for_draft(qa_history)}

---

DISCOVERED EXPERIENCES (from discovery conversation):
{_format_discovered_experiences(discovered_experiences)}

---

COMPANY INSIGHTS:
Culture: {research.get('company_culture', 'N/A')[:500] if research else 'N/A'}
Values: {', '.join(research.get('company_values', [])) if research else 'N/A'}
"""
    return context


async def _generate_suggestions(
    resume_html: str,
    job_posting: dict,
    gap_analysis: dict,
) -> list[DraftingSuggestion]:
    """Generate improvement suggestions for the resume draft."""
    try:
        llm = get_llm(temperature=0.3)

        prompt = f"""
RESUME DRAFT:
{resume_html}

---

TARGET JOB:
Title: {job_posting.get('title', '')}
Company: {job_posting.get('company_name', '')}

Key Requirements:
{chr(10).join('- ' + r for r in job_posting.get('requirements', [])[:10])}

Keywords that should be included:
{', '.join(gap_analysis.get('keywords_to_include', [])[:15])}

Generate 3-5 specific, actionable suggestions to improve this resume for the target job.
"""

        messages = [
            SystemMessage(content=SUGGESTION_GENERATION_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)
        content = _extract_content_from_code_block(response.content.strip(), "json")
        suggestions_data = json.loads(content)

        suggestions = []
        for idx, s in enumerate(suggestions_data[:5]):  # Max 5 suggestions
            suggestion = DraftingSuggestion(
                id=f"sug_{uuid.uuid4().hex[:8]}",
                location=s.get("location", "general"),
                original_text=s.get("original_text", ""),
                proposed_text=s.get("proposed_text", ""),
                rationale=s.get("rationale", ""),
                status="pending",
                created_at=datetime.now().isoformat(),
            )
            suggestions.append(suggestion)

        logger.info(f"Generated {len(suggestions)} suggestions")
        return suggestions

    except Exception as e:
        logger.error(f"Failed to generate suggestions: {e}")
        return []


def validate_resume(html_content: str) -> DraftValidationResult:
    """Validate resume draft against quality criteria.

    Checks:
    - Summary exists and <= 100 words
    - At least 1 experience entry
    - Bullets start with action verbs
    - Skills section exists with categories
    - Education section exists
    """
    errors = []
    warnings = []
    checks = {}

    # Check summary exists
    summary_match = re.search(
        r'<h2[^>]*>.*?(?:Professional\s+)?Summary.*?</h2>\s*<p[^>]*>(.*?)</p>',
        html_content,
        re.IGNORECASE | re.DOTALL
    )
    checks["summary_exists"] = bool(summary_match)

    if summary_match:
        summary_text = re.sub(r'<[^>]+>', '', summary_match.group(1)).strip()
        word_count = len(summary_text.split())
        checks["summary_length"] = word_count <= 100
        if word_count > 100:
            errors.append(f"Summary is {word_count} words, should be <= 100")
    else:
        errors.append("Professional summary is missing")
        checks["summary_length"] = False

    # Check experience entries
    experience_matches = re.findall(
        r'<h3[^>]*>(.*?)</h3>',
        html_content,
        re.IGNORECASE | re.DOTALL
    )
    checks["experience_count"] = len(experience_matches) >= 1
    if len(experience_matches) < 1:
        errors.append("At least 1 experience entry is required")

    # Check bullets start with action verbs
    bullet_matches = re.findall(r'<li[^>]*>(.*?)</li>', html_content, re.DOTALL)
    action_verb_bullets = 0
    for bullet in bullet_matches:
        clean_bullet = re.sub(r'<[^>]+>', '', bullet).strip().lower()
        first_word = clean_bullet.split()[0] if clean_bullet.split() else ""
        if first_word in ACTION_VERBS:
            action_verb_bullets += 1

    total_bullets = len(bullet_matches)
    if total_bullets > 0:
        action_verb_ratio = action_verb_bullets / total_bullets
        checks["action_verbs"] = action_verb_ratio >= 0.5
        if action_verb_ratio < 0.5:
            warnings.append(f"Only {action_verb_bullets}/{total_bullets} bullets start with action verbs")
    else:
        checks["action_verbs"] = False
        warnings.append("No bullet points found in resume")

    # Check skills section
    skills_match = re.search(
        r'<h2[^>]*>.*?Skills.*?</h2>',
        html_content,
        re.IGNORECASE
    )
    checks["skills_section"] = bool(skills_match)
    if not skills_match:
        errors.append("Skills section is missing")

    # Check education section
    education_match = re.search(
        r'<h2[^>]*>.*?Education.*?</h2>',
        html_content,
        re.IGNORECASE
    )
    checks["education_section"] = bool(education_match)
    if not education_match:
        errors.append("Education section is missing")

    valid = len(errors) == 0

    return DraftValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )


def _format_experience_for_draft(experience: list[dict]) -> str:
    """Format experience with full detail for drafting."""
    if not experience:
        return "No experience provided"

    formatted = []
    for exp in experience:
        entry = f"""
Position: {exp.get('position', 'Unknown')}
Company: {exp.get('company', 'Unknown')}
Location: {exp.get('location', 'N/A')}
Duration: {exp.get('start_date', '?')} - {exp.get('end_date', 'Present')}
Current Role: {exp.get('is_current', False)}

Description: {exp.get('description', 'N/A')}

Achievements:
{chr(10).join('  - ' + a for a in exp.get('achievements', []))}

Technologies Used: {', '.join(exp.get('technologies', []))}
"""
        formatted.append(entry)

    return "\n---\n".join(formatted)


def _format_education_for_draft(education: list[dict]) -> str:
    """Format education for drafting."""
    if not education:
        return "No education provided"

    formatted = []
    for edu in education:
        entry = f"{edu.get('degree', 'Degree')} in {edu.get('field_of_study', 'Unknown')}"
        entry += f" from {edu.get('institution', 'Unknown')}"
        if edu.get("end_date"):
            entry += f" ({edu.get('end_date')})"
        if edu.get("gpa"):
            entry += f", GPA: {edu.get('gpa')}"
        formatted.append(entry)

    return "\n".join(formatted)


def _format_qa_for_draft(qa_history: list[dict]) -> str:
    """Format Q&A responses for drafting context."""
    if not qa_history:
        return "No additional information gathered from interview."

    relevant_info = []
    for qa in qa_history:
        if qa.get("answer"):
            # Include Q&A pairs that have answers
            relevant_info.append(f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}")

    if not relevant_info:
        return "No additional information gathered from interview."

    return "\n\n".join(relevant_info)


def _format_discovered_experiences(experiences: list[dict]) -> str:
    """Format discovered experiences for drafting context."""
    if not experiences:
        return "No additional experiences discovered."

    formatted = []
    for exp in experiences:
        entry = f"""
Experience: {exp.get('description', '')}
Quote from user: "{exp.get('source_quote', '')}"
Relevant to: {', '.join(exp.get('mapped_requirements', []))}
"""
        formatted.append(entry)

    return "\n---\n".join(formatted)


def increment_version(current_version: str) -> str:
    """Increment version number (e.g., 1.0 -> 1.1, 1.9 -> 2.0)."""
    try:
        major, minor = current_version.split(".")
        minor = int(minor) + 1
        if minor >= 10:
            major = int(major) + 1
            minor = 0
        return f"{major}.{minor}"
    except (ValueError, AttributeError):
        return "1.1"


def create_version(
    html_content: str,
    trigger: str,
    description: str,
    current_version: str,
    change_log: list[dict] = None,
) -> DraftVersion:
    """Create a new version snapshot."""
    new_version = increment_version(current_version)

    return DraftVersion(
        version=new_version,
        html_content=html_content,
        trigger=trigger,
        description=description,
        change_log=change_log or [],
        created_at=datetime.now().isoformat(),
    )
