"""Memory/preference learning node for analyzing user behavior and inferring preferences.

This module analyzes user edit events and suggestion responses to learn their
writing style preferences. The learned preferences are then used by the drafting
agent to generate more personalized resume content.

Learning signals include:
- Text edits: Adding/removing first person, quantification, formatting
- Suggestion accepts: What the user likes (strong positive signal)
- Suggestion rejects: What the user dislikes (strong negative signal)
- Suggestion dismisses: User hid suggestion without engaging (weak negative signal)
- Implicit rejects: User saw suggestion but manually edited differently (strong negative signal)
"""

import json
import logging
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def get_llm(temperature: float = 0.2):
    """Get configured LLM for preference learning."""
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
        max_tokens=2048,
    )


PREFERENCE_LEARNING_PROMPT = """You are an expert at analyzing user behavior to infer writing style preferences.

Your task is to analyze a series of user events (edits, suggestion accepts, suggestion rejects) and infer their preferences for resume writing.

PREFERENCE CATEGORIES:
1. tone: "formal" | "conversational" | "confident" | "humble" | null
   - formal: Uses professional language (implemented, executed, facilitated)
   - conversational: Uses casual language (helped, worked on, got involved)
   - confident: Bold, assertive statements
   - humble: Modest, understated language

2. structure: "bullets" | "paragraphs" | "mixed" | null
   - Based on what format they prefer in their edits

3. sentence_length: "concise" | "detailed" | "mixed" | null
   - concise: Short, punchy sentences
   - detailed: Comprehensive explanations
   - mixed: Varies by context

4. first_person: true | false | null
   - true: Uses "I" statements (e.g., "I led a team")
   - false: Implied first person (e.g., "Led a team")

5. quantification_preference: "heavy_metrics" | "qualitative" | "balanced" | null
   - heavy_metrics: Lots of numbers, percentages, metrics
   - qualitative: Descriptive impact over numbers
   - balanced: Mix of both

6. achievement_focus: true | false | null
   - true: Emphasizes accomplishments and results
   - false: Includes responsibilities alongside achievements

ANALYSIS APPROACH:
1. Look for patterns in what users ADD vs REMOVE in edits
2. Note patterns in accepted suggestions (what they like)
3. Note patterns in rejected suggestions (what they dislike)
4. Weight more recent events higher
5. Only set a preference if there's clear evidence (>= 2-3 consistent signals)

OUTPUT FORMAT (JSON only):
{
  "tone": "formal" | "conversational" | "confident" | "humble" | null,
  "structure": "bullets" | "paragraphs" | "mixed" | null,
  "sentence_length": "concise" | "detailed" | "mixed" | null,
  "first_person": true | false | null,
  "quantification_preference": "heavy_metrics" | "qualitative" | "balanced" | null,
  "achievement_focus": true | false | null,
  "confidence_scores": {
    "tone": 0.0-1.0,
    "structure": 0.0-1.0,
    "sentence_length": 0.0-1.0,
    "first_person": 0.0-1.0,
    "quantification_preference": 0.0-1.0,
    "achievement_focus": 0.0-1.0
  },
  "reasoning": "Brief explanation of key signals observed"
}

Only output valid JSON, no other text."""


async def learn_preferences_from_events(events: list[dict]) -> dict[str, Any]:
    """Analyze user events and learn their preferences.

    Args:
        events: List of events with format:
            {
                "event_type": "edit" | "suggestion_accept" | "suggestion_reject",
                "event_data": {...},
                "created_at": "ISO timestamp"
            }

    Returns:
        Learned preferences with confidence scores
    """
    if not events:
        logger.info("No events to learn from")
        return {
            "tone": None,
            "structure": None,
            "sentence_length": None,
            "first_person": None,
            "quantification_preference": None,
            "achievement_focus": None,
            "confidence_scores": {},
            "reasoning": "No events to analyze",
        }

    # Sort events by timestamp (most recent last)
    sorted_events = sorted(
        events,
        key=lambda e: e.get("created_at", ""),
    )

    # Format events for LLM analysis
    formatted_events = _format_events_for_analysis(sorted_events)

    if not formatted_events:
        logger.info("No meaningful events to analyze")
        return {
            "tone": None,
            "structure": None,
            "sentence_length": None,
            "first_person": None,
            "quantification_preference": None,
            "achievement_focus": None,
            "confidence_scores": {},
            "reasoning": "No meaningful events to analyze",
        }

    try:
        llm = get_llm()

        prompt = f"""Analyze these user events and infer their resume writing preferences:

{formatted_events}

Based on these {len(sorted_events)} events, what are the user's writing preferences?"""

        messages = [
            SystemMessage(content=PREFERENCE_LEARNING_PROMPT),
            HumanMessage(content=prompt),
        ]

        response = await llm.ainvoke(messages)

        # Parse JSON from response
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())

        logger.info(f"Learned preferences from {len(events)} events: {result.get('reasoning', 'N/A')}")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse preferences JSON: {e}")
        return _get_fallback_preferences(events)
    except Exception as e:
        logger.error(f"Preference learning error: {e}")
        return _get_fallback_preferences(events)


def _format_events_for_analysis(events: list[dict]) -> str:
    """Format events for LLM analysis."""
    formatted = []

    for i, event in enumerate(events[-30:], 1):  # Last 30 events max
        event_type = event.get("event_type", "unknown")
        data = event.get("event_data", {})

        if event_type == "edit":
            edit_type = data.get("edit_type", data.get("type", "text_change"))
            before = data.get("before", "")[:200]
            after = data.get("after", "")[:200]
            section = data.get("section", "unknown")

            # Include detected patterns
            patterns = []
            if data.get("uses_first_person"):
                patterns.append("uses_first_person")
            if data.get("uses_quantification"):
                patterns.append("uses_quantification")
            if data.get("change_type"):
                patterns.append(f"change_type: {data['change_type']}")

            formatted.append(
                f"Event {i} - EDIT ({edit_type}, section: {section}):\n"
                f"  Before: \"{before}\"\n"
                f"  After: \"{after}\"\n"
                f"  Patterns: {', '.join(patterns) if patterns else 'none'}"
            )

        elif event_type == "suggestion_accept":
            location = data.get("location", "unknown")
            original = data.get("original_text", "")[:150]
            proposed = data.get("proposed_text", "")[:150]
            was_modified = data.get("was_modified", False)
            final = data.get("final_text", "")[:150] if was_modified else None

            # Include detected patterns
            patterns = []
            if data.get("prefers_formal_tone"):
                patterns.append("prefers_formal")
            if data.get("prefers_conversational_tone"):
                patterns.append("prefers_conversational")
            if data.get("prefers_quantification"):
                patterns.append("prefers_quantification")
            if data.get("prefers_action_verbs"):
                patterns.append("prefers_action_verbs")

            entry = (
                f"Event {i} - SUGGESTION ACCEPTED (location: {location}):\n"
                f"  Original: \"{original}\"\n"
                f"  Proposed: \"{proposed}\""
            )
            if was_modified and final:
                entry += f"\n  Modified to: \"{final}\""
            if patterns:
                entry += f"\n  Patterns: {', '.join(patterns)}"

            formatted.append(entry)

        elif event_type == "suggestion_reject":
            location = data.get("location", "unknown")
            original = data.get("original_text", "")[:150]
            proposed = data.get("proposed_text", "")[:150]
            reason = data.get("rejection_reason", "")

            # Include detected patterns
            patterns = []
            if data.get("dislikes_formal_tone"):
                patterns.append("dislikes_formal")
            if data.get("dislikes_conversational_tone"):
                patterns.append("dislikes_conversational")
            if data.get("dislikes_quantification"):
                patterns.append("dislikes_quantification")
            if data.get("dislikes_action_verbs"):
                patterns.append("dislikes_action_verbs")

            entry = (
                f"Event {i} - SUGGESTION REJECTED (location: {location}):\n"
                f"  Original: \"{original}\"\n"
                f"  Proposed (rejected): \"{proposed}\""
            )
            if reason:
                entry += f"\n  Reason: \"{reason}\""
            if patterns:
                entry += f"\n  Patterns: {', '.join(patterns)}"

            formatted.append(entry)

        elif event_type == "suggestion_dismiss":
            # Weak negative signal - user dismissed without acting
            location = data.get("location", "unknown")
            proposed = data.get("proposed_text", "")[:150]

            formatted.append(
                f"Event {i} - SUGGESTION DISMISSED (location: {location}):\n"
                f"  Proposed (dismissed without review): \"{proposed}\"\n"
                f"  Note: Weak signal - user didn't engage with this suggestion"
            )

        elif event_type == "suggestion_implicit_reject":
            # Strong signal - user saw suggestion but chose to edit differently
            location = data.get("location", "unknown")
            original = data.get("original_text", "")[:150]
            proposed = data.get("proposed_text", "")[:150]
            user_edited = data.get("user_edited_text", "")[:150]

            # Include detected patterns
            patterns = []
            if data.get("dislikes_formal_tone"):
                patterns.append("dislikes_formal")
            if data.get("dislikes_conversational_tone"):
                patterns.append("dislikes_conversational")
            if data.get("dislikes_quantification"):
                patterns.append("dislikes_quantification")
            if data.get("prefers_formal_tone"):
                patterns.append("prefers_formal")
            if data.get("prefers_conversational_tone"):
                patterns.append("prefers_conversational")
            if data.get("prefers_quantification"):
                patterns.append("prefers_quantification")
            if data.get("prefers_concise"):
                patterns.append("prefers_concise")
            if data.get("prefers_detailed"):
                patterns.append("prefers_detailed")
            if data.get("kept_original"):
                patterns.append("kept_original_over_suggestion")

            entry = (
                f"Event {i} - IMPLICIT REJECTION (location: {location}):\n"
                f"  AI suggested: \"{proposed}\"\n"
                f"  User instead wrote: \"{user_edited}\"\n"
                f"  Note: User saw suggestion but manually edited differently"
            )
            if patterns:
                entry += f"\n  Patterns: {', '.join(patterns)}"

            formatted.append(entry)

    return "\n\n".join(formatted)


def _get_fallback_preferences(events: list[dict]) -> dict[str, Any]:
    """Use rule-based heuristics as fallback when LLM fails."""
    # Count patterns from events
    first_person_count = 0
    no_first_person_count = 0
    quantification_count = 0
    formal_count = 0
    conversational_count = 0

    for event in events:
        data = event.get("event_data", {})

        # Count first person usage
        if data.get("uses_first_person"):
            first_person_count += 1
        elif data.get("after") and not any(p in data["after"].lower() for p in ["i ", "i'm", "i've", "my "]):
            no_first_person_count += 1

        # Count quantification
        if data.get("uses_quantification") or data.get("prefers_quantification"):
            quantification_count += 1

        # Count tone preferences from suggestions
        if data.get("prefers_formal_tone"):
            formal_count += 1
        if data.get("prefers_conversational_tone"):
            conversational_count += 1
        if data.get("dislikes_formal_tone"):
            formal_count -= 1
        if data.get("dislikes_conversational_tone"):
            conversational_count -= 1

    result = {
        "tone": None,
        "structure": None,
        "sentence_length": None,
        "first_person": None,
        "quantification_preference": None,
        "achievement_focus": None,
        "confidence_scores": {},
        "reasoning": "Fallback rule-based analysis",
    }

    # Determine preferences from counts (need at least 2 signals)
    if first_person_count >= 2 and first_person_count > no_first_person_count:
        result["first_person"] = True
        result["confidence_scores"]["first_person"] = min(first_person_count / 5, 1.0)
    elif no_first_person_count >= 2 and no_first_person_count > first_person_count:
        result["first_person"] = False
        result["confidence_scores"]["first_person"] = min(no_first_person_count / 5, 1.0)

    if quantification_count >= 2:
        result["quantification_preference"] = "heavy_metrics"
        result["confidence_scores"]["quantification_preference"] = min(quantification_count / 5, 1.0)

    if formal_count >= 2 and formal_count > conversational_count:
        result["tone"] = "formal"
        result["confidence_scores"]["tone"] = min(formal_count / 5, 1.0)
    elif conversational_count >= 2 and conversational_count > formal_count:
        result["tone"] = "conversational"
        result["confidence_scores"]["tone"] = min(conversational_count / 5, 1.0)

    return result


def merge_preferences(
    existing: dict[str, Any],
    learned: dict[str, Any],
    confidence_threshold: float = 0.5,
) -> dict[str, Any]:
    """Merge learned preferences with existing preferences.

    Args:
        existing: Current user preferences
        learned: Newly learned preferences
        confidence_threshold: Minimum confidence to override existing

    Returns:
        Merged preferences
    """
    result = {**existing}
    confidence_scores = learned.get("confidence_scores", {})

    preference_keys = [
        "tone", "structure", "sentence_length",
        "first_person", "quantification_preference", "achievement_focus"
    ]

    for key in preference_keys:
        learned_value = learned.get(key)
        confidence = confidence_scores.get(key, 0)

        if learned_value is not None and confidence >= confidence_threshold:
            # Only override if learned with sufficient confidence
            result[key] = learned_value

    return result
