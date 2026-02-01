"""LLM-as-a-judge grader for preference learning evaluation.

Evaluates how well the preference learning system infers user preferences
from their behavior events.

Dimensions:
1. Accuracy: Did it infer the correct preferences?
2. Confidence Calibration: Are confidence scores appropriate?
3. Reasoning Quality: Does the reasoning explain the inference well?
"""

import json
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_grader_llm():
    """Get LLM for grading."""
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        temperature=0.1,
        max_tokens=1024,
    )


GRADER_PROMPT = """You are an expert evaluator assessing a preference learning system.

The system analyzes user events (edits, suggestion accepts/rejects) and infers their writing preferences.

Evaluate the system's output on these dimensions (0-10 scale):

1. ACCURACY (0-10): Did it correctly infer the expected preferences?
   - 10: All expected preferences correctly identified
   - 7: Most preferences correct, minor misses
   - 5: Some correct, some wrong
   - 3: Mostly wrong
   - 0: Completely wrong

2. CONFIDENCE_CALIBRATION (0-10): Are confidence scores appropriate?
   - 10: High confidence only when clear evidence, low when ambiguous
   - 7: Generally appropriate confidence levels
   - 5: Sometimes over or under confident
   - 3: Confidence doesn't match evidence
   - 0: Confidence is random/meaningless

3. REASONING_QUALITY (0-10): Does the reasoning explain the inference well?
   - 10: Clear, specific reasoning citing actual events
   - 7: Good reasoning with some specifics
   - 5: Generic reasoning, could apply to any case
   - 3: Poor reasoning, doesn't match output
   - 0: No useful reasoning

OUTPUT FORMAT (JSON only):
{
  "accuracy": 0-10,
  "confidence_calibration": 0-10,
  "reasoning_quality": 0-10,
  "feedback": "Specific feedback on what was good/bad",
  "overall_score": 0-10
}

Only output valid JSON, no other text."""


async def grade_preference_learning(
    events: list[dict],
    expected_preferences: dict,
    learned_result: dict,
) -> dict[str, Any]:
    """Grade preference learning output against expected preferences.

    Args:
        events: Input events that were analyzed
        expected_preferences: What preferences should have been learned
        learned_result: The actual output from the learning system

    Returns:
        Grading scores and feedback
    """
    llm = get_grader_llm()

    # Format the grading context
    events_summary = []
    for i, event in enumerate(events[:10], 1):  # Limit to 10 for context
        event_type = event.get("event_type", "unknown")
        data = event.get("event_data", {})
        events_summary.append(f"{i}. {event_type}: {json.dumps(data)[:200]}")

    # Extract learned preferences from top level (not nested under 'learned_preferences' key)
    preference_keys = ["tone", "structure", "sentence_length", "first_person",
                       "quantification_preference", "achievement_focus"]
    learned_preferences = {k: learned_result.get(k) for k in preference_keys}

    context = f"""
INPUT EVENTS:
{chr(10).join(events_summary)}

EXPECTED PREFERENCES:
{json.dumps(expected_preferences, indent=2)}

SYSTEM OUTPUT:
Learned preferences: {json.dumps(learned_preferences, indent=2)}
Confidence scores: {json.dumps(learned_result.get('confidence_scores', {}), indent=2)}
Reasoning: {learned_result.get('reasoning', 'No reasoning provided')}
"""

    messages = [
        SystemMessage(content=GRADER_PROMPT),
        HumanMessage(content=f"Grade this preference learning output:\n\n{context}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        # Ensure all required fields
        return {
            "accuracy": result.get("accuracy", 0),
            "confidence_calibration": result.get("confidence_calibration", 0),
            "reasoning_quality": result.get("reasoning_quality", 0),
            "feedback": result.get("feedback", ""),
            "overall_score": result.get("overall_score", 0),
        }

    except Exception as e:
        logger.error(f"Grading failed: {e}")
        return {
            "accuracy": 0,
            "confidence_calibration": 0,
            "reasoning_quality": 0,
            "feedback": f"Grading error: {str(e)}",
            "overall_score": 0,
        }


def compute_aggregate_score(grades: list[dict]) -> dict[str, float]:
    """Compute aggregate scores across multiple samples.

    Args:
        grades: List of individual grade dicts

    Returns:
        Average scores for each dimension
    """
    if not grades:
        return {
            "accuracy": 0.0,
            "confidence_calibration": 0.0,
            "reasoning_quality": 0.0,
            "overall_score": 0.0,
        }

    totals = {
        "accuracy": 0.0,
        "confidence_calibration": 0.0,
        "reasoning_quality": 0.0,
        "overall_score": 0.0,
    }

    for grade in grades:
        for key in totals:
            totals[key] += grade.get(key, 0)

    count = len(grades)
    return {key: value / count for key, value in totals.items()}
