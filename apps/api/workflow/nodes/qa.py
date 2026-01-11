"""Q&A functions for human-in-the-loop interview.

This module provides functions for the interrupt() pattern (LangGraph 1.0+):
1. generate_question() - Generate next question based on gaps and working context
2. process_qa_answer() - Process user's answer and update state

These are called by qa_node in graph.py which uses interrupt() for human-in-the-loop.
"""

import json
import logging
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings
from workflow.state import ResumeState

logger = logging.getLogger(__name__)

settings = get_settings()


def get_llm():
    """Get configured LLM for Q&A."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.5,  # Slightly more creative for questions
    )


QUESTION_GENERATION_PROMPT = """You are an expert career coach conducting an interview to help someone create the best possible resume for a target job.

Your goal is to ask questions that will:
1. Uncover impressive achievements they may have forgotten to mention
2. Get specific metrics and numbers to quantify their impact
3. Discover transferable skills relevant to the target role
4. Address gaps in their profile proactively
5. Find unique stories that differentiate them

Based on the gap analysis and previous Q&A, generate ONE focused question.

IMPORTANT RULES:
- Ask only ONE question at a time
- Be specific and targeted, not generic
- Reference specific gaps or opportunities from the analysis
- Don't repeat questions that have already been asked
- Questions should help fill gaps or strengthen highlights
- Use encouraging, conversational tone

Output JSON:
{
    "question": "Your specific, targeted question here",
    "question_intent": "What you're trying to learn from this question"
}

If you believe you have gathered enough information (or the user has already provided comprehensive answers), output:
{
    "question": null,
    "question_intent": "sufficient_info"
}"""


# ============================================================================
# New Functions for interrupt() Pattern (LangGraph 1.0+)
# ============================================================================

async def generate_question(
    state: ResumeState,
    working_context: dict,
) -> dict:
    """Generate the next question based on gaps and working context.

    This is called by qa_node in graph.py before calling interrupt().
    Uses working context for efficient LLM calls (prevents context bloat).

    Args:
        state: Full workflow state (for gap analysis, qa history)
        working_context: Summarized context for LLM

    Returns:
        dict with 'question', 'intent', or 'no_more_questions' flag
    """
    logger.info("Generating next question")

    gap_analysis = state.get("gap_analysis", {}) or {}
    qa_history = state.get("qa_history", []) or []

    try:
        llm = get_llm()

        # Use working context for compact LLM call
        target_role = working_context.get("target_role", "Unknown")
        target_company = working_context.get("target_company", "Unknown")
        key_gaps = working_context.get("key_gaps", [])
        key_strengths = working_context.get("key_strengths", [])
        priority_keywords = working_context.get("priority_keywords", [])

        # Build compact context
        context = f"""
TARGET: {target_role} at {target_company}

KEY GAPS TO ADDRESS:
{chr(10).join('- ' + g for g in key_gaps)}

AREAS TO STRENGTHEN:
{chr(10).join('- ' + s for s in key_strengths)}

PRIORITY KEYWORDS: {', '.join(priority_keywords)}

PREVIOUS Q&A (avoid repeating topics):
{_format_qa_history(qa_history)}

Q&A Round: {len(qa_history) + 1} of 10
"""

        messages = [
            SystemMessage(content=QUESTION_GENERATION_PROMPT),
            HumanMessage(content=f"Generate the next interview question:\n\n{context}"),
        ]

        response = await llm.ainvoke(messages)

        # Parse JSON from response
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        question_data = json.loads(content.strip())

        # Check if model decided we have sufficient info
        if question_data.get("question") is None:
            logger.info("LLM determined sufficient info gathered")
            return {"no_more_questions": True}

        logger.info(f"Generated question: {question_data['question'][:50]}...")

        return {
            "question": question_data["question"],
            "intent": question_data.get("question_intent", ""),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse question JSON: {e}")
        # Fall back to a generic question
        return {
            "question": "Can you tell me about a specific achievement in your career that you're most proud of?",
            "intent": "Discover impressive achievements",
        }

    except Exception as e:
        logger.error(f"Question generation error: {e}")
        return {
            "question": "What's a challenging project you've worked on that's relevant to this role?",
            "intent": "Discover relevant experience",
        }


def process_qa_answer(
    answer: str,
    state: ResumeState,
    question: str,
    question_intent: str,
) -> dict:
    """Process user's answer and prepare state update.

    This is called by qa_node in graph.py after interrupt() returns.

    Args:
        answer: User's answer text (from interrupt())
        state: Current workflow state
        question: The question that was asked
        question_intent: What we were trying to learn

    Returns:
        State updates dict
    """
    logger.info(f"Processing answer: {answer[:50]}..." if answer else "Processing empty answer")

    qa_history = list(state.get("qa_history", []) or [])
    qa_round = state.get("qa_round", 0)

    # Check if user wants to stop
    done_keywords = ["done", "skip", "finish", "no more", "that's all", "i'm done", "stop"]
    user_done = any(keyword in answer.lower() for keyword in done_keywords) if answer else False

    # Create new Q&A interaction
    new_qa = {
        "question": question,
        "answer": answer,
        "question_intent": question_intent,
        "timestamp": datetime.now().isoformat(),
    }

    qa_history.append(new_qa)

    result = {
        "qa_history": qa_history,
        "qa_round": qa_round + 1,
    }

    if user_done:
        logger.info("User signaled completion")
        result["user_done_signal"] = True
        result["qa_complete"] = True
        result["current_step"] = "draft"

    return result


# ============================================================================
# Helper Functions
# ============================================================================

def _format_qa_history(qa_history: list[dict]) -> str:
    """Format Q&A history for context."""
    if not qa_history:
        return "No previous questions asked."

    formatted = []
    for i, qa in enumerate(qa_history, 1):
        entry = f"Q{i}: {qa.get('question', 'Unknown question')}"
        if qa.get("answer"):
            # Truncate long answers
            answer = qa["answer"]
            if len(answer) > 200:
                answer = answer[:200] + "..."
            entry += f"\nA{i}: {answer}"
        formatted.append(entry)

    return "\n\n".join(formatted)
