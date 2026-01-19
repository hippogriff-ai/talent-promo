"""Context management utilities for LangGraph workflow.

This module handles:
1. Context summarization - Reduce full state to working context for LLM calls
2. Progressive disclosure - Create appropriate interrupt payloads for users
3. Memory management - Prevent context window bloat
"""

import logging
from typing import Any

from workflow.state import (
    ResumeState,
    WorkingContext,
    InterruptPayload,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Context Summarization (Full State -> Working Context)
# ============================================================================

def build_working_context(state: ResumeState) -> dict:
    """Build a summarized working context from full state.

    This is called at each step to create a compact context
    for LLM calls, preventing context window bloat.

    Args:
        state: Full workflow state

    Returns:
        Serialized WorkingContext dict
    """
    job_posting = state.get("job_posting", {}) or {}
    gap_analysis = state.get("gap_analysis", {}) or {}
    qa_history = state.get("qa_history", []) or []

    context = WorkingContext(
        target_role=job_posting.get("title") or "",
        target_company=job_posting.get("company_name") or "",
        key_strengths=(gap_analysis.get("strengths") or [])[:5],
        key_gaps=(gap_analysis.get("gaps") or [])[:5],
        priority_keywords=(gap_analysis.get("keywords_to_include") or [])[:10],
        recent_qa=qa_history[-3:] if qa_history else [],  # Only last 3
        current_objective=_get_current_objective(state),
    )

    return context.model_dump()


def _get_current_objective(state: ResumeState) -> str:
    """Determine current objective based on workflow step."""
    step = state.get("current_step", "ingest")

    objectives = {
        "ingest": "Parse and understand user profile and job requirements",
        "research": "Research company culture, tech stack, and similar employees",
        "analysis": "Identify gaps and recommend what to highlight",
        "qa": "Gather additional context from user to strengthen resume",
        "draft": "Generate ATS-optimized resume tailored to the role",
        "editor": "Assist user with resume refinements",
        "export": "Export final resume",
    }

    return objectives.get(step, "Process workflow step")


def summarize_for_llm(state: ResumeState, max_tokens: int = 2000) -> str:
    """Create a compact string summary for LLM prompts.

    Args:
        state: Full workflow state
        max_tokens: Approximate max tokens (rough estimate)

    Returns:
        Formatted string for LLM context
    """
    working_ctx = state.get("working_context") or build_working_context(state)

    if isinstance(working_ctx, dict):
        ctx = WorkingContext(**working_ctx)
    else:
        ctx = working_ctx

    return ctx.to_prompt_context()


def summarize_profile_for_llm(profile: dict, max_experience: int = 3) -> str:
    """Summarize user profile for LLM context.

    Args:
        profile: Full user profile dict
        max_experience: Max experience entries to include

    Returns:
        Compact profile summary
    """
    if not profile:
        return "No profile available"

    parts = [
        f"Name: {profile.get('name', 'Unknown')}",
        f"Headline: {profile.get('headline', 'N/A')}",
    ]

    # Summary (truncated)
    summary = profile.get("summary", "")
    if summary:
        parts.append(f"Summary: {summary[:300]}...")

    # Experience (limited)
    experience = profile.get("experience", [])[:max_experience]
    if experience:
        exp_summary = []
        for exp in experience:
            exp_line = f"- {exp.get('position', '?')} at {exp.get('company', '?')}"
            if exp.get("achievements"):
                exp_line += f" ({len(exp['achievements'])} achievements)"
            exp_summary.append(exp_line)
        parts.append("Experience:\n" + "\n".join(exp_summary))

    # Skills (limited)
    skills = profile.get("skills", [])[:15]
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    return "\n".join(parts)


def summarize_job_for_llm(job: dict) -> str:
    """Summarize job posting for LLM context.

    Args:
        job: Full job posting dict

    Returns:
        Compact job summary
    """
    if not job:
        return "No job posting available"

    parts = [
        f"Role: {job.get('title', 'Unknown')} at {job.get('company_name', 'Unknown')}",
    ]

    # Requirements (limited)
    requirements = job.get("requirements", [])[:5]
    if requirements:
        parts.append("Key Requirements:\n" + "\n".join(f"- {r}" for r in requirements))

    # Tech stack
    tech_stack = job.get("tech_stack", [])[:10]
    if tech_stack:
        parts.append(f"Tech Stack: {', '.join(tech_stack)}")

    return "\n".join(parts)


def summarize_research_for_llm(research: dict) -> str:
    """Summarize research findings for LLM context.

    Args:
        research: Full research findings dict

    Returns:
        Compact research summary
    """
    if not research:
        return "No research available"

    parts = []

    # Company culture (truncated)
    culture = research.get("company_culture", "")
    if culture:
        parts.append(f"Culture: {culture[:200]}...")

    # Values
    values = research.get("company_values", [])[:5]
    if values:
        parts.append(f"Values: {', '.join(values)}")

    # Hiring patterns
    hiring = research.get("hiring_patterns", "")
    if hiring:
        parts.append(f"Hiring: {hiring[:150]}...")

    return "\n".join(parts) if parts else "Research available but no key insights extracted"


# ============================================================================
# Progressive Disclosure (Build Interrupt Payloads)
# ============================================================================

def build_qa_interrupt(
    question: str,
    state: ResumeState,
    question_intent: str = "",
) -> dict:
    """Build interrupt payload for Q&A question.

    This creates a focused payload with only what the user needs
    to answer the question effectively.

    Args:
        question: The question to ask
        state: Full workflow state
        question_intent: What we're trying to learn

    Returns:
        Serialized InterruptPayload dict
    """
    gap_analysis = state.get("gap_analysis", {}) or {}
    qa_round = state.get("qa_round", 0)

    # Build context for the user
    context = {
        "question_intent": question_intent,
        "gaps_being_addressed": gap_analysis.get("gaps", [])[:3],
        "keywords_to_mention": gap_analysis.get("keywords_to_include", [])[:5],
    }

    # Generate suggestions based on what we're looking for
    suggestions = _generate_answer_suggestions(question, gap_analysis)

    payload = InterruptPayload(
        interrupt_type="qa_question",
        message=question,
        context=context,
        suggestions=suggestions,
        round=qa_round + 1,
        max_rounds=10,
        can_skip=True,
    )

    return payload.model_dump()


def _generate_answer_suggestions(question: str, gap_analysis: dict) -> list[str]:
    """Generate helpful suggestions for answering a question.

    Args:
        question: The question being asked
        gap_analysis: Gap analysis data

    Returns:
        List of suggestion strings
    """
    suggestions = []

    # Check question type and provide relevant suggestions
    question_lower = question.lower()

    if any(word in question_lower for word in ["metric", "number", "quantif", "measure"]):
        suggestions.append("Include specific numbers (%, $, time saved, team size)")

    if any(word in question_lower for word in ["challenge", "difficult", "problem"]):
        suggestions.append("Use STAR format: Situation, Task, Action, Result")

    if any(word in question_lower for word in ["team", "collaborat", "lead"]):
        suggestions.append("Mention team size and your specific role")

    if any(word in question_lower for word in ["technolog", "tool", "stack"]):
        keywords = gap_analysis.get("keywords_to_include", [])[:5]
        if keywords:
            suggestions.append(f"Relevant keywords: {', '.join(keywords)}")

    # Default suggestions
    if not suggestions:
        suggestions = [
            "Be specific with examples",
            "Include measurable outcomes if possible",
        ]

    return suggestions[:3]  # Max 3 suggestions


def build_draft_review_interrupt(state: ResumeState) -> dict:
    """Build interrupt payload for draft review.

    Args:
        state: Full workflow state

    Returns:
        Serialized InterruptPayload dict
    """
    resume_html = state.get("resume_html", "")
    gap_analysis = state.get("gap_analysis", {}) or {}

    context = {
        "resume_preview": resume_html[:1000] if resume_html else "",
        "keywords_included": gap_analysis.get("keywords_to_include", [])[:10],
        "strengths_highlighted": gap_analysis.get("recommended_emphasis", [])[:5],
    }

    payload = InterruptPayload(
        interrupt_type="review_draft",
        message="Please review your optimized resume draft",
        context=context,
        suggestions=[
            "Check that your key achievements are highlighted",
            "Verify all information is accurate",
            "Look for any missing relevant experience",
        ],
        can_skip=False,
    )

    return payload.model_dump()


# ============================================================================
# Context Window Management
# ============================================================================

def estimate_token_count(text: str) -> int:
    """Rough estimate of token count.

    Args:
        text: Text to estimate

    Returns:
        Approximate token count
    """
    # Rough estimate: ~4 characters per token for English
    return len(text) // 4


def trim_context_to_fit(
    context_parts: list[tuple[str, str]],
    max_tokens: int = 3000,
) -> str:
    """Trim context parts to fit within token budget.

    Args:
        context_parts: List of (label, content) tuples in priority order
        max_tokens: Maximum tokens allowed

    Returns:
        Combined context string within budget
    """
    result_parts = []
    current_tokens = 0

    for label, content in context_parts:
        content_tokens = estimate_token_count(content)

        if current_tokens + content_tokens <= max_tokens:
            result_parts.append(f"## {label}\n{content}")
            current_tokens += content_tokens
        else:
            # Try to fit a truncated version
            available_tokens = max_tokens - current_tokens - 50  # Buffer
            if available_tokens > 100:
                truncated = content[:available_tokens * 4]  # Rough char estimate
                result_parts.append(f"## {label} (truncated)\n{truncated}...")
            break

    return "\n\n".join(result_parts)


def build_llm_context(
    state: ResumeState,
    include_profile: bool = True,
    include_job: bool = True,
    include_research: bool = False,
    include_qa: bool = True,
    max_tokens: int = 3000,
) -> str:
    """Build optimized context for LLM calls.

    Args:
        state: Full workflow state
        include_profile: Include profile summary
        include_job: Include job summary
        include_research: Include research summary
        include_qa: Include recent Q&A
        max_tokens: Maximum context tokens

    Returns:
        Optimized context string
    """
    context_parts = []

    # Priority order: job > profile > Q&A > research
    if include_job:
        job_summary = summarize_job_for_llm(state.get("job_posting", {}))
        context_parts.append(("Target Job", job_summary))

    if include_profile:
        profile_summary = summarize_profile_for_llm(state.get("user_profile", {}))
        context_parts.append(("Candidate Profile", profile_summary))

    if include_qa:
        qa_history = state.get("qa_history", [])
        if qa_history:
            qa_text = "\n".join([
                f"Q: {qa.get('question', '')}\nA: {qa.get('answer', 'Not answered')}"
                for qa in qa_history[-3:]
            ])
            context_parts.append(("Recent Q&A", qa_text))

    if include_research:
        research_summary = summarize_research_for_llm(state.get("research", {}))
        context_parts.append(("Company Research", research_summary))

    return trim_context_to_fit(context_parts, max_tokens)
