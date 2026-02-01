"""In-memory user preferences service for managing writing style and content preferences.

This service handles:
- User preferences CRUD operations (in-memory)
- Preference event recording (for learning from user behavior)
- Preference computation from events

Privacy by design: All data is ephemeral. Use browser localStorage for persistence.
"""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Type aliases for validated preference values
ToneType = Literal["formal", "conversational", "confident", "humble"]
StructureType = Literal["bullets", "paragraphs", "mixed"]
SentenceLengthType = Literal["concise", "detailed", "mixed"]
QuantificationType = Literal["heavy_metrics", "qualitative", "balanced"]


class UserPreferences(BaseModel):
    """User preferences model with validated preference values."""

    id: Optional[str] = None
    user_id: str
    # Writing style (validated Literal types)
    tone: Optional[ToneType] = None
    structure: Optional[StructureType] = None
    sentence_length: Optional[SentenceLengthType] = None
    first_person: Optional[bool] = None
    # Content choices (validated Literal types)
    quantification_preference: Optional[QuantificationType] = None
    achievement_focus: Optional[bool] = None
    # Extensibility
    custom_preferences: dict = {}
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PreferenceEvent(BaseModel):
    """Preference event model for tracking user behavior."""

    event_type: Literal[
        "edit",
        "suggestion_accept",
        "suggestion_reject",
        "suggestion_dismiss",  # User dismissed suggestion without engaging (weak negative signal)
        "suggestion_implicit_reject",  # User saw suggestion but edited differently (strong negative signal)
    ]
    event_data: dict
    thread_id: Optional[str] = None


class PreferencesService:
    """In-memory service for managing user preferences."""

    def __init__(self):
        """Initialize the service with in-memory storage."""
        self._preferences: dict[str, UserPreferences] = {}
        self._events: dict[str, list[dict]] = {}  # user_id -> list of events
        logger.info("PreferencesService initialized (in-memory)")

    # ==================== Preferences CRUD ====================

    def get_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences.

        Args:
            user_id: User's ID.

        Returns:
            UserPreferences if found, None otherwise.
        """
        return self._preferences.get(user_id)

    def get_or_create_preferences(self, user_id: str) -> UserPreferences:
        """Get existing preferences or create default ones.

        Args:
            user_id: User's ID.

        Returns:
            UserPreferences (existing or newly created).
        """
        prefs = self.get_preferences(user_id)
        if prefs:
            return prefs

        return self.create_preferences(user_id)

    def create_preferences(self, user_id: str) -> UserPreferences:
        """Create default preferences for a user.

        Args:
            user_id: User's ID.

        Returns:
            UserPreferences.
        """
        import uuid

        now = datetime.now(timezone.utc)
        prefs = UserPreferences(
            id=str(uuid.uuid4()),
            user_id=user_id,
            custom_preferences={},
            created_at=now,
            updated_at=now,
        )
        self._preferences[user_id] = prefs
        return prefs

    def update_preferences(
        self, user_id: str, updates: dict
    ) -> Optional[UserPreferences]:
        """Update user preferences.

        Args:
            user_id: User's ID.
            updates: Dict of field names to new values.

        Returns:
            Updated UserPreferences if successful.
        """
        # Ensure preferences exist
        prefs = self.get_or_create_preferences(user_id)

        # Allowed fields to update
        allowed_fields = {
            "tone",
            "structure",
            "sentence_length",
            "first_person",
            "quantification_preference",
            "achievement_focus",
            "custom_preferences",
        }

        # Update allowed fields
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(prefs, field, value)

        prefs.updated_at = datetime.now(timezone.utc)
        self._preferences[user_id] = prefs
        return prefs

    def reset_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Reset user preferences to defaults.

        Args:
            user_id: User's ID.

        Returns:
            Reset UserPreferences if successful.
        """
        prefs = self._preferences.get(user_id)
        if not prefs:
            return self.create_preferences(user_id)

        prefs.tone = None
        prefs.structure = None
        prefs.sentence_length = None
        prefs.first_person = None
        prefs.quantification_preference = None
        prefs.achievement_focus = None
        prefs.custom_preferences = {}
        prefs.updated_at = datetime.now(timezone.utc)

        return prefs

    def delete_preferences(self, user_id: str) -> bool:
        """Delete all preferences and events for a user.

        Args:
            user_id: User's ID.

        Returns:
            True if successful.
        """
        self._preferences.pop(user_id, None)
        self._events.pop(user_id, None)
        return True

    # ==================== Event Recording ====================

    def record_event(
        self,
        user_id: str,
        event: PreferenceEvent,
    ) -> bool:
        """Record a preference event for learning.

        Args:
            user_id: User's ID.
            event: The preference event to record.

        Returns:
            True if recorded successfully.
        """
        import uuid

        if user_id not in self._events:
            self._events[user_id] = []

        event_dict = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "thread_id": event.thread_id,
            "event_type": event.event_type,
            "event_data": event.event_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._events[user_id].append(event_dict)
        return True

    def get_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get preference events for a user.

        Args:
            user_id: User's ID.
            event_type: Optional filter by event type.
            limit: Maximum number of events to return.

        Returns:
            List of event dicts.
        """
        events = self._events.get(user_id, [])

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]

        # Sort by created_at descending
        events = sorted(events, key=lambda e: e.get("created_at", ""), reverse=True)

        return events[:limit]

    def get_event_count(self, user_id: str) -> int:
        """Get the total number of events for a user.

        Args:
            user_id: User's ID.

        Returns:
            Number of events.
        """
        return len(self._events.get(user_id, []))

    # ==================== Preference Learning ====================

    def compute_preferences_from_events(self, user_id: str) -> Optional[UserPreferences]:
        """Compute preferences from recorded events.

        This analyzes patterns in suggestion acceptances and edits to
        infer user preferences.

        Args:
            user_id: User's ID.

        Returns:
            Computed UserPreferences (not saved).
        """
        events = self.get_events(user_id, limit=500)
        if not events:
            return None

        # Analyze events to infer preferences
        tone_votes: Counter = Counter()
        structure_votes: Counter = Counter()
        first_person_votes: Counter = Counter()
        achievement_votes: Counter = Counter()

        for event in events:
            event_data = event.get("event_data", {})
            event_type = event.get("event_type")

            # For suggestion accepts, we assume user prefers that style
            if event_type == "suggestion_accept":
                if "tone" in event_data:
                    tone_votes[event_data["tone"]] += 1
                if "structure" in event_data:
                    structure_votes[event_data["structure"]] += 1
                if "first_person" in event_data:
                    first_person_votes[event_data["first_person"]] += 1
                if "achievement_focus" in event_data:
                    achievement_votes[event_data["achievement_focus"]] += 1

            # For edits, analyze the change
            elif event_type == "edit":
                edit_analysis = event_data.get("analysis", {})
                if "tone" in edit_analysis:
                    tone_votes[edit_analysis["tone"]] += 1
                if "structure" in edit_analysis:
                    structure_votes[edit_analysis["structure"]] += 1

        # Build preferences from most common patterns
        computed = UserPreferences(user_id=user_id)

        if tone_votes:
            computed.tone = tone_votes.most_common(1)[0][0]
        if structure_votes:
            computed.structure = structure_votes.most_common(1)[0][0]
        if first_person_votes:
            most_common = first_person_votes.most_common(1)[0][0]
            computed.first_person = most_common if isinstance(most_common, bool) else None
        if achievement_votes:
            most_common = achievement_votes.most_common(1)[0][0]
            computed.achievement_focus = most_common if isinstance(most_common, bool) else None

        return computed

    def apply_computed_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Compute preferences from events and save them.

        Args:
            user_id: User's ID.

        Returns:
            Updated UserPreferences.
        """
        computed = self.compute_preferences_from_events(user_id)
        if not computed:
            return self.get_preferences(user_id)

        # Only update fields that were computed
        updates = {}
        if computed.tone:
            updates["tone"] = computed.tone
        if computed.structure:
            updates["structure"] = computed.structure
        if computed.first_person is not None:
            updates["first_person"] = computed.first_person
        if computed.achievement_focus is not None:
            updates["achievement_focus"] = computed.achievement_focus

        if updates:
            return self.update_preferences(user_id, updates)

        return self.get_preferences(user_id)

    def close(self):
        """Clear all data."""
        self._preferences.clear()
        self._events.clear()


# Singleton instance for use across the application
_preferences_service: Optional[PreferencesService] = None


def get_preferences_service() -> PreferencesService:
    """Get the singleton PreferencesService instance."""
    global _preferences_service
    if _preferences_service is None:
        _preferences_service = PreferencesService()
    return _preferences_service


def reset_preferences_service():
    """Reset singleton (for testing)."""
    global _preferences_service
    if _preferences_service:
        _preferences_service.close()
    _preferences_service = None
