"""Editor assistance node for AI-powered resume editing."""

import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from config import get_settings
from workflow.state import ResumeState

logger = logging.getLogger(__name__)

settings = get_settings()


def get_llm():
    """Get configured LLM for editing assistance."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.3,
    )


EDITOR_PROMPTS = {
    "improve": """You are an expert resume writer. Improve the following text to be more impactful and professional while maintaining the same core meaning.

Guidelines:
- Use strong action verbs
- Add quantifiable metrics where possible
- Keep it concise but impactful
- Sound natural, not robotic
- Maintain ATS-friendly keywords

Return ONLY the improved text, no explanations.""",

    "add_keywords": """You are an ATS optimization expert. Add relevant keywords to the following text to improve its ATS score for the target role.

Guidelines:
- Incorporate keywords naturally
- Don't keyword stuff
- Maintain readability
- Keep the same general length

Return ONLY the optimized text with keywords, no explanations.""",

    "quantify": """You are an expert at quantifying achievements. Rewrite the following to include specific numbers, percentages, or metrics.

Guidelines:
- Add realistic estimates if exact numbers aren't provided
- Use formats like "increased by X%", "managed team of X", "reduced time by X hours"
- Keep it credible and natural

Return ONLY the quantified text, no explanations.""",

    "shorten": """You are an expert at concise professional writing. Shorten the following text while preserving the key achievements and impact.

Guidelines:
- Cut filler words and redundancy
- Keep quantifiable achievements
- Maintain professional tone
- Aim for 50-70% of original length

Return ONLY the shortened text, no explanations.""",

    "rewrite": """You are an expert resume writer. Completely rewrite the following section with fresh language and structure.

Guidelines:
- Use different action verbs
- Restructure sentences
- Keep the same factual content
- Make it more impactful

Return ONLY the rewritten text, no explanations.""",

    "fix_tone": """You are an expert at professional writing. Adjust the following to sound more professional and confident without being arrogant.

Guidelines:
- Remove uncertainty words ("helped", "assisted with")
- Use confident language
- Maintain accuracy
- Sound natural, not pompous

Return ONLY the adjusted text, no explanations.""",
}


async def editor_assist_node(state: ResumeState) -> dict[str, Any]:
    """Provide AI assistance for resume editing in Tiptap.

    This node uses interrupt() to pause the workflow and wait for user approval.
    The user edits the resume in the frontend, then clicks "Approve" which
    resumes the workflow with the approval signal.
    """
    logger.info("Editor assist node - waiting for user approval")

    # Check if draft is already approved (resume from interrupt)
    if state.get("draft_approved"):
        logger.info("Draft approved, proceeding to export")
        return {
            "current_step": "editor",
            "updated_at": datetime.now().isoformat(),
        }

    # Interrupt and wait for user to approve the draft
    # The frontend shows the editor, user makes edits, then clicks "Approve"
    # which calls POST /api/optimize/{thread_id}/answer with "approve"
    approval = interrupt({
        "interrupt_type": "draft_approval",
        "message": "Review and approve your resume draft",
        "resume_html": state.get("resume_html", ""),
        "suggestions": state.get("draft_suggestions", []),
    })

    # User approved - set the flag
    if approval and str(approval).lower().strip() in ["approve", "approved", "yes", "confirm"]:
        logger.info("User approved the draft")
        return {
            "draft_approved": True,
            "current_step": "editor",
            "updated_at": datetime.now().isoformat(),
        }
    else:
        # User made edits but didn't approve yet - stay in editor
        logger.info(f"User response: {approval} - staying in editor")
        return {
            "current_step": "editor",
            "updated_at": datetime.now().isoformat(),
        }


async def get_editor_suggestion(
    action: str,
    selected_text: str,
    full_resume: str,
    job_context: dict,
    instructions: str | None = None,
) -> dict[str, Any]:
    """Generate AI suggestion for editor action.

    This is called directly from the API endpoint, not as a graph node.

    Args:
        action: Type of edit (improve, add_keywords, quantify, shorten, rewrite, fix_tone)
        selected_text: The text the user selected
        full_resume: The full resume HTML for context
        job_context: Job posting and gap analysis context
        instructions: Optional custom instructions from user

    Returns:
        Dict with suggestion and metadata
    """
    logger.info(f"Generating editor suggestion for action: {action}")

    if action not in EDITOR_PROMPTS and action != "custom":
        return {
            "success": False,
            "error": f"Unknown action: {action}",
        }

    try:
        llm = get_llm()

        if action == "custom" and instructions:
            prompt = f"""You are an expert resume writer. Follow these instructions to modify the text:

Instructions: {instructions}

Guidelines:
- Make the requested changes
- Keep it professional and ATS-friendly
- Maintain the core meaning unless asked to change it

Return ONLY the modified text, no explanations."""
        else:
            prompt = EDITOR_PROMPTS[action]

        # Build context
        context = f"""
TARGET ROLE: {job_context.get('title', 'Unknown')} at {job_context.get('company', 'Unknown')}

KEY KEYWORDS TO INCLUDE: {', '.join(job_context.get('keywords', [])[:10])}

SELECTED TEXT TO MODIFY:
{selected_text}
"""

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=context),
        ]

        response = await llm.ainvoke(messages)
        suggestion = response.content.strip()

        # Clean up any code blocks or extra formatting
        if "```" in suggestion:
            suggestion = suggestion.replace("```html", "").replace("```", "").strip()

        return {
            "success": True,
            "original": selected_text,
            "suggestion": suggestion,
            "action": action,
        }

    except Exception as e:
        logger.error(f"Editor suggestion error: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def regenerate_section(
    section: str,
    current_content: str,
    user_profile: dict,
    job_posting: dict,
    gap_analysis: dict,
) -> dict[str, Any]:
    """Regenerate a specific resume section from scratch.

    Args:
        section: Section name (summary, experience, skills, etc.)
        current_content: Current section content
        user_profile: User profile data
        job_posting: Job posting data
        gap_analysis: Gap analysis data

    Returns:
        Dict with regenerated section
    """
    logger.info(f"Regenerating section: {section}")

    section_prompts = {
        "summary": "Write a compelling 2-3 sentence professional summary that positions this candidate perfectly for the target role.",
        "experience": "Rewrite this experience section with stronger action verbs, quantified achievements, and ATS keywords.",
        "skills": "Reorganize and optimize this skills section for ATS, prioritizing skills mentioned in the job posting.",
        "education": "Format this education section professionally and highlight any relevant coursework or achievements.",
    }

    prompt = section_prompts.get(section, f"Rewrite this {section} section to be more impactful and ATS-friendly.")

    try:
        llm = get_llm()

        context = f"""
{prompt}

TARGET ROLE: {job_posting.get('title', '')} at {job_posting.get('company_name', '')}

KEYWORDS TO INCLUDE: {', '.join(gap_analysis.get('keywords_to_include', []))}

CURRENT CONTENT:
{current_content}

ADDITIONAL CONTEXT:
- Strengths: {', '.join(gap_analysis.get('strengths', [])[:3])}
- Emphasis areas: {', '.join(gap_analysis.get('recommended_emphasis', [])[:3])}

Return ONLY the HTML for this section, formatted for a rich text editor."""

        messages = [
            SystemMessage(content="You are an expert resume writer creating ATS-optimized, professional resume sections."),
            HumanMessage(content=context),
        ]

        response = await llm.ainvoke(messages)
        regenerated = response.content.strip()

        if "```" in regenerated:
            regenerated = regenerated.replace("```html", "").replace("```", "").strip()

        return {
            "success": True,
            "section": section,
            "content": regenerated,
        }

    except Exception as e:
        logger.error(f"Section regeneration error: {e}")
        return {
            "success": False,
            "error": str(e),
        }
