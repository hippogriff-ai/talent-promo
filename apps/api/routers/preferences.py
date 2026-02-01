"""Preferences router for user writing style and content preferences.

Endpoints:
- GET /api/preferences - Get user preferences (anonymous)
- PATCH /api/preferences - Update preferences (anonymous)
- POST /api/preferences/reset - Reset to defaults (anonymous)
- POST /api/preferences/events - Record preference event (anonymous)
- POST /api/preferences/learn - Learn preferences from events (anonymous)
"""

import logging
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from services.preferences_service import (
    PreferenceEvent,
    UserPreferences,
    ToneType,
    StructureType,
    SentenceLengthType,
    QuantificationType,
    get_preferences_service,
)
from workflow.nodes.memory import learn_preferences_from_events, merge_preferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


def get_anonymous_user_id(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID")
) -> str:
    """Get anonymous user ID from header or generate one."""
    return x_anonymous_id or f"anon_{uuid.uuid4().hex[:12]}"


# ==================== Request/Response Models ====================


class PreferencesResponse(BaseModel):
    """Response for preferences endpoints."""

    preferences: UserPreferences


class UpdatePreferencesInput(BaseModel):
    """Request body for updating preferences with validated values."""

    tone: Optional[ToneType] = None
    structure: Optional[StructureType] = None
    sentence_length: Optional[SentenceLengthType] = None
    first_person: Optional[bool] = None
    quantification_preference: Optional[QuantificationType] = None
    achievement_focus: Optional[bool] = None
    custom_preferences: Optional[dict] = None


class RecordEventInput(BaseModel):
    """Request body for recording preference event.

    Supported event types:
    - edit: User manually edited resume content
    - suggestion_accept: User accepted an AI suggestion
    - suggestion_reject: User rejected an AI suggestion
    - suggestion_dismiss: User dismissed suggestion without engaging (weak negative signal)
    - suggestion_implicit_reject: User saw suggestion but edited differently (strong negative signal)
    """

    event_type: Literal[
        "edit",
        "suggestion_accept",
        "suggestion_reject",
        "suggestion_dismiss",
        "suggestion_implicit_reject",
    ]
    event_data: dict
    thread_id: Optional[str] = None


class RecordEventResponse(BaseModel):
    """Response for event recording."""

    message: str
    event_count: int


class ResetResponse(BaseModel):
    """Response for reset operation."""

    message: str
    preferences: UserPreferences


class LearnFromEventsInput(BaseModel):
    """Request body for learning from events."""

    events: list[dict]  # Events from localStorage pending_events
    apply_threshold: float = 0.5  # Minimum confidence to apply learned preferences


class LearnFromEventsResponse(BaseModel):
    """Response for preference learning."""

    learned_preferences: dict  # What was learned
    confidence_scores: dict  # Confidence for each preference
    reasoning: str  # Explanation of what was learned
    applied: bool  # Whether changes were applied to stored preferences
    final_preferences: UserPreferences  # The final preference state


# ==================== Endpoints ====================


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> PreferencesResponse:
    """Get user preferences.

    Returns the user's stored preferences, creating default preferences
    if none exist yet.
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_preferences_service()
    preferences = service.get_or_create_preferences(user_id)

    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to get preferences")

    return PreferencesResponse(preferences=preferences)


@router.patch("", response_model=PreferencesResponse)
async def update_preferences(
    body: UpdatePreferencesInput,
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> PreferencesResponse:
    """Update user preferences.

    Only updates the fields that are provided in the request body.
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_preferences_service()

    # Convert to dict, excluding None values
    updates = body.model_dump(exclude_none=True)

    preferences = service.update_preferences(user_id, updates)
    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    return PreferencesResponse(preferences=preferences)


@router.post("/reset", response_model=ResetResponse)
async def reset_preferences(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> ResetResponse:
    """Reset preferences to defaults.

    Clears all learned and manually set preferences.
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_preferences_service()
    preferences = service.reset_preferences(user_id)

    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to reset preferences")

    return ResetResponse(
        message="Preferences reset to defaults",
        preferences=preferences,
    )


@router.post("/events", response_model=RecordEventResponse)
async def record_event(
    body: RecordEventInput,
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> RecordEventResponse:
    """Record a preference event for learning.

    Events are used to learn user preferences over time. Supported event types:
    - edit: User manually edited resume content
    - suggestion_accept: User accepted an AI suggestion
    - suggestion_reject: User rejected an AI suggestion
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_preferences_service()

    event = PreferenceEvent(
        event_type=body.event_type,
        event_data=body.event_data,
        thread_id=body.thread_id,
    )

    success = service.record_event(user_id, event)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record event")

    event_count = service.get_event_count(user_id)

    return RecordEventResponse(
        message="Event recorded",
        event_count=event_count,
    )


@router.post("/learn", response_model=LearnFromEventsResponse)
async def learn_from_events(
    body: LearnFromEventsInput,
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> LearnFromEventsResponse:
    """Learn preferences from user behavior events.

    Analyzes a batch of events (edits, suggestion accepts/rejects) using an LLM
    to infer the user's writing style preferences. If confidence is high enough,
    the learned preferences are applied to the user's stored preferences.

    This is typically called by the frontend when:
    - User finishes editing a draft
    - User completes a workflow
    - Enough events have accumulated (e.g., 5+ events)

    Args:
        body: Contains events list and apply_threshold

    Returns:
        Learned preferences with confidence scores and whether they were applied
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_preferences_service()

    if not body.events:
        # No events to learn from, return current preferences
        current_prefs = service.get_or_create_preferences(user_id)
        return LearnFromEventsResponse(
            learned_preferences={},
            confidence_scores={},
            reasoning="No events provided to learn from",
            applied=False,
            final_preferences=current_prefs,
        )

    try:
        # Learn preferences from events using LLM
        learned = await learn_preferences_from_events(body.events)

        # Get current preferences
        current_prefs = service.get_or_create_preferences(user_id)
        current_dict = current_prefs.model_dump() if current_prefs else {}

        # Merge learned with existing (only high confidence)
        merged = merge_preferences(
            current_dict,
            learned,
            confidence_threshold=body.apply_threshold,
        )

        # Check if any preferences changed
        changed = False
        for key in ["tone", "structure", "sentence_length", "first_person",
                    "quantification_preference", "achievement_focus"]:
            if merged.get(key) != current_dict.get(key) and merged.get(key) is not None:
                changed = True
                break

        # Apply if changes were made
        if changed:
            updates = {
                k: merged[k] for k in ["tone", "structure", "sentence_length",
                                       "first_person", "quantification_preference",
                                       "achievement_focus"]
                if merged.get(k) is not None
            }
            final_prefs = service.update_preferences(user_id, updates)
        else:
            final_prefs = current_prefs

        return LearnFromEventsResponse(
            learned_preferences={
                k: learned.get(k) for k in ["tone", "structure", "sentence_length",
                                            "first_person", "quantification_preference",
                                            "achievement_focus"]
                if learned.get(k) is not None
            },
            confidence_scores=learned.get("confidence_scores", {}),
            reasoning=learned.get("reasoning", ""),
            applied=changed,
            final_preferences=final_prefs,
        )

    except Exception as e:
        logger.error(f"Failed to learn preferences: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to learn preferences: {str(e)}"
        )
