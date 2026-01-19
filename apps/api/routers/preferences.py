"""Preferences router for user writing style and content preferences.

Endpoints:
- GET /api/preferences - Get user preferences
- PATCH /api/preferences - Update preferences
- POST /api/preferences/reset - Reset to defaults
- POST /api/preferences/events - Record preference event
- GET /api/preferences/events - Get preference events
- POST /api/preferences/compute - Compute preferences from events
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from middleware.session_auth import get_current_user, get_user_id_optional
from services.auth_service import User
from services.preferences_service import (
    PreferenceEvent,
    UserPreferences,
    get_preferences_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


# ==================== Request/Response Models ====================


class PreferencesResponse(BaseModel):
    """Response for preferences endpoints."""

    preferences: UserPreferences


class UpdatePreferencesInput(BaseModel):
    """Request body for updating preferences."""

    tone: Optional[str] = None
    structure: Optional[str] = None
    sentence_length: Optional[str] = None
    first_person: Optional[bool] = None
    quantification_preference: Optional[str] = None
    achievement_focus: Optional[bool] = None
    custom_preferences: Optional[dict] = None


class RecordEventInput(BaseModel):
    """Request body for recording preference event."""

    event_type: Literal["edit", "suggestion_accept", "suggestion_reject"]
    event_data: dict
    thread_id: Optional[str] = None


class RecordEventResponse(BaseModel):
    """Response for event recording."""

    message: str
    event_count: int


class EventsResponse(BaseModel):
    """Response for events list."""

    events: list[dict]
    total_count: int


class ResetResponse(BaseModel):
    """Response for reset operation."""

    message: str
    preferences: UserPreferences


class ComputeResponse(BaseModel):
    """Response for preference computation."""

    message: str
    preferences: UserPreferences
    applied: bool


# ==================== Endpoints ====================


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    user: User = Depends(get_current_user),
) -> PreferencesResponse:
    """Get user preferences.

    Returns the user's stored preferences, creating default preferences
    if none exist yet.
    """
    service = get_preferences_service()
    preferences = service.get_or_create_preferences(user.id)

    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to get preferences")

    return PreferencesResponse(preferences=preferences)


@router.patch("", response_model=PreferencesResponse)
async def update_preferences(
    body: UpdatePreferencesInput,
    user: User = Depends(get_current_user),
) -> PreferencesResponse:
    """Update user preferences.

    Only updates the fields that are provided in the request body.
    """
    service = get_preferences_service()

    # Convert to dict, excluding None values
    updates = body.model_dump(exclude_none=True)

    preferences = service.update_preferences(user.id, updates)
    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    return PreferencesResponse(preferences=preferences)


@router.post("/reset", response_model=ResetResponse)
async def reset_preferences(
    user: User = Depends(get_current_user),
) -> ResetResponse:
    """Reset preferences to defaults.

    Clears all learned and manually set preferences.
    """
    service = get_preferences_service()
    preferences = service.reset_preferences(user.id)

    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to reset preferences")

    return ResetResponse(
        message="Preferences reset to defaults",
        preferences=preferences,
    )


@router.delete("", response_model=dict)
async def delete_preferences(
    user: User = Depends(get_current_user),
) -> dict:
    """Delete all preference data including events.

    This is a destructive operation that removes all stored preferences
    and learning data.
    """
    service = get_preferences_service()
    success = service.delete_preferences(user.id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete preferences")

    return {"message": "All preference data deleted"}


@router.post("/events", response_model=RecordEventResponse)
async def record_event(
    body: RecordEventInput,
    user: User = Depends(get_current_user),
) -> RecordEventResponse:
    """Record a preference event for learning.

    Events are used to learn user preferences over time. Supported event types:
    - edit: User manually edited resume content
    - suggestion_accept: User accepted an AI suggestion
    - suggestion_reject: User rejected an AI suggestion
    """
    service = get_preferences_service()

    event = PreferenceEvent(
        event_type=body.event_type,
        event_data=body.event_data,
        thread_id=body.thread_id,
    )

    success = service.record_event(user.id, event)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record event")

    event_count = service.get_event_count(user.id)

    return RecordEventResponse(
        message="Event recorded",
        event_count=event_count,
    )


@router.get("/events", response_model=EventsResponse)
async def get_events(
    event_type: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
) -> EventsResponse:
    """Get preference events for the current user.

    Args:
        event_type: Optional filter by event type.
        limit: Maximum number of events to return (default: 50, max: 100).
    """
    service = get_preferences_service()

    # Enforce max limit
    limit = min(limit, 100)

    events = service.get_events(user.id, event_type=event_type, limit=limit)
    total_count = service.get_event_count(user.id)

    return EventsResponse(events=events, total_count=total_count)


@router.post("/compute", response_model=ComputeResponse)
async def compute_preferences(
    apply: bool = False,
    user: User = Depends(get_current_user),
) -> ComputeResponse:
    """Compute preferences from recorded events.

    This analyzes the user's edit and suggestion patterns to infer
    their preferences.

    Args:
        apply: If True, apply the computed preferences to the user's profile.
    """
    service = get_preferences_service()

    if apply:
        preferences = service.apply_computed_preferences(user.id)
        message = "Preferences computed and applied"
    else:
        computed = service.compute_preferences_from_events(user.id)
        if computed:
            preferences = computed
            message = "Preferences computed (not applied)"
        else:
            preferences = service.get_or_create_preferences(user.id)
            message = "No events to compute from"

    if not preferences:
        raise HTTPException(status_code=500, detail="Failed to compute preferences")

    return ComputeResponse(
        message=message,
        preferences=preferences,
        applied=apply,
    )


# ==================== Anonymous User Support ====================
# These endpoints allow anonymous users to submit events
# Events are stored with a temporary ID until they create an account


@router.post("/events/anonymous", response_model=RecordEventResponse)
async def record_anonymous_event(
    body: RecordEventInput,
    anonymous_id: str,
    user_id: Optional[str] = Depends(get_user_id_optional),
) -> RecordEventResponse:
    """Record a preference event for anonymous users.

    Events are stored with the anonymous_id and can be migrated
    when the user creates an account.

    Args:
        anonymous_id: Client-generated anonymous identifier.
    """
    # If user is authenticated, use their real user_id
    effective_user_id = user_id or f"anon:{anonymous_id}"

    service = get_preferences_service()

    event = PreferenceEvent(
        event_type=body.event_type,
        event_data=body.event_data,
        thread_id=body.thread_id,
    )

    success = service.record_event(effective_user_id, event)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record event")

    event_count = service.get_event_count(effective_user_id)

    return RecordEventResponse(
        message="Event recorded",
        event_count=event_count,
    )
