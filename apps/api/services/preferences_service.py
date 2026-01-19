"""User preferences service for managing writing style and content preferences.

This service handles:
- User preferences CRUD operations
- Preference event recording (for learning from user behavior)
- Preference computation from events
"""

import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UserPreferences(BaseModel):
    """User preferences model."""

    id: Optional[str] = None
    user_id: str
    # Writing style
    tone: Optional[str] = None  # formal, conversational, confident, humble
    structure: Optional[str] = None  # bullets, paragraphs, mixed
    sentence_length: Optional[str] = None  # concise, detailed, mixed
    first_person: Optional[bool] = None
    # Content choices
    quantification_preference: Optional[str] = None  # heavy_metrics, qualitative, balanced
    achievement_focus: Optional[bool] = None
    # Extensibility
    custom_preferences: dict = {}
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PreferenceEvent(BaseModel):
    """Preference event model for tracking user behavior."""

    event_type: Literal["edit", "suggestion_accept", "suggestion_reject"]
    event_data: dict
    thread_id: Optional[str] = None


class PreferencesService:
    """Service for managing user preferences."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize the service.

        Args:
            database_url: Postgres connection string. If None, uses DATABASE_URL env var.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self._connection = None

    def _get_connection(self):
        """Get or create database connection."""
        if not self.database_url:
            logger.warning("No DATABASE_URL configured, preferences service disabled")
            return None

        if self._connection is None or self._connection.closed:
            try:
                import psycopg2

                self._connection = psycopg2.connect(self.database_url)
            except ImportError:
                logger.error("psycopg2 not installed, preferences service disabled")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                return None

        return self._connection

    def ensure_tables_exist(self) -> bool:
        """Create preferences tables if they don't exist.

        Returns:
            True if tables exist or were created, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            # Create user_preferences table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    tone VARCHAR(50),
                    structure VARCHAR(50),
                    sentence_length VARCHAR(50),
                    first_person BOOLEAN,
                    quantification_preference VARCHAR(50),
                    achievement_focus BOOLEAN,
                    custom_preferences JSONB DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id)
                )
            """)

            # Create preference_events table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS preference_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    thread_id VARCHAR(255),
                    event_type VARCHAR(50) NOT NULL,
                    event_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create indexes
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_preference_events_user_id ON preference_events(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_preference_events_type ON preference_events(event_type)"
            )

            conn.commit()
            cur.close()
            logger.info("Preferences tables created/verified successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create preferences tables: {e}")
            conn.rollback()
            return False

    # ==================== Preferences CRUD ====================

    def get_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get user preferences.

        Args:
            user_id: User's UUID.

        Returns:
            UserPreferences if found, None otherwise.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, user_id, tone, structure, sentence_length, first_person,
                       quantification_preference, achievement_focus, custom_preferences,
                       created_at, updated_at
                FROM user_preferences
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                return UserPreferences(
                    id=str(row[0]),
                    user_id=str(row[1]),
                    tone=row[2],
                    structure=row[3],
                    sentence_length=row[4],
                    first_person=row[5],
                    quantification_preference=row[6],
                    achievement_focus=row[7],
                    custom_preferences=row[8] or {},
                    created_at=row[9],
                    updated_at=row[10],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return None

    def get_or_create_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get existing preferences or create default ones.

        Args:
            user_id: User's UUID.

        Returns:
            UserPreferences (existing or newly created).
        """
        prefs = self.get_preferences(user_id)
        if prefs:
            return prefs

        # Create default preferences
        return self.create_preferences(user_id)

    def create_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Create default preferences for a user.

        Args:
            user_id: User's UUID.

        Returns:
            UserPreferences if created successfully.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            import json

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, custom_preferences)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
                RETURNING id, user_id, tone, structure, sentence_length, first_person,
                          quantification_preference, achievement_focus, custom_preferences,
                          created_at, updated_at
                """,
                (user_id, json.dumps({})),
            )
            row = cur.fetchone()
            conn.commit()
            cur.close()

            if row:
                return UserPreferences(
                    id=str(row[0]),
                    user_id=str(row[1]),
                    tone=row[2],
                    structure=row[3],
                    sentence_length=row[4],
                    first_person=row[5],
                    quantification_preference=row[6],
                    achievement_focus=row[7],
                    custom_preferences=row[8] or {},
                    created_at=row[9],
                    updated_at=row[10],
                )

            # If insert returned nothing (conflict), fetch existing
            return self.get_preferences(user_id)
        except Exception as e:
            logger.error(f"Failed to create preferences: {e}")
            conn.rollback()
            return None

    def update_preferences(
        self, user_id: str, updates: dict
    ) -> Optional[UserPreferences]:
        """Update user preferences.

        Args:
            user_id: User's UUID.
            updates: Dict of field names to new values.

        Returns:
            Updated UserPreferences if successful.
        """
        conn = self._get_connection()
        if not conn:
            return None

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

        # Filter to only allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered_updates:
            return self.get_preferences(user_id)

        try:
            import json

            # Ensure preferences record exists
            self.get_or_create_preferences(user_id)

            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            for field, value in filtered_updates.items():
                set_clauses.append(f"{field} = %s")
                if field == "custom_preferences":
                    values.append(json.dumps(value))
                else:
                    values.append(value)

            values.append(user_id)

            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE user_preferences
                SET {", ".join(set_clauses)}, updated_at = NOW()
                WHERE user_id = %s
                """,
                tuple(values),
            )
            conn.commit()
            cur.close()

            return self.get_preferences(user_id)
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            conn.rollback()
            return None

    def reset_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Reset user preferences to defaults.

        Args:
            user_id: User's UUID.

        Returns:
            Reset UserPreferences if successful.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            import json

            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_preferences
                SET tone = NULL,
                    structure = NULL,
                    sentence_length = NULL,
                    first_person = NULL,
                    quantification_preference = NULL,
                    achievement_focus = NULL,
                    custom_preferences = %s,
                    updated_at = NOW()
                WHERE user_id = %s
                """,
                (json.dumps({}), user_id),
            )
            conn.commit()
            cur.close()

            return self.get_preferences(user_id)
        except Exception as e:
            logger.error(f"Failed to reset preferences: {e}")
            conn.rollback()
            return None

    def delete_preferences(self, user_id: str) -> bool:
        """Delete all preferences and events for a user.

        Args:
            user_id: User's UUID.

        Returns:
            True if successful.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM preference_events WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM user_preferences WHERE user_id = %s", (user_id,))
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to delete preferences: {e}")
            conn.rollback()
            return False

    # ==================== Event Recording ====================

    def record_event(
        self,
        user_id: str,
        event: PreferenceEvent,
    ) -> bool:
        """Record a preference event for learning.

        Args:
            user_id: User's UUID.
            event: The preference event to record.

        Returns:
            True if recorded successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            import json

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO preference_events (user_id, thread_id, event_type, event_data)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    event.thread_id,
                    event.event_type,
                    json.dumps(event.event_data),
                ),
            )
            conn.commit()
            cur.close()
            return True
        except Exception as e:
            logger.error(f"Failed to record event: {e}")
            conn.rollback()
            return False

    def get_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get preference events for a user.

        Args:
            user_id: User's UUID.
            event_type: Optional filter by event type.
            limit: Maximum number of events to return.

        Returns:
            List of event dicts.
        """
        conn = self._get_connection()
        if not conn:
            return []

        try:
            cur = conn.cursor()

            if event_type:
                cur.execute(
                    """
                    SELECT id, user_id, thread_id, event_type, event_data, created_at
                    FROM preference_events
                    WHERE user_id = %s AND event_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, event_type, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, user_id, thread_id, event_type, event_data, created_at
                    FROM preference_events
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )

            rows = cur.fetchall()
            cur.close()

            return [
                {
                    "id": str(row[0]),
                    "user_id": str(row[1]),
                    "thread_id": row[2],
                    "event_type": row[3],
                    "event_data": row[4] or {},
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []

    def get_event_count(self, user_id: str) -> int:
        """Get the total number of events for a user.

        Args:
            user_id: User's UUID.

        Returns:
            Number of events.
        """
        conn = self._get_connection()
        if not conn:
            return 0

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM preference_events WHERE user_id = %s",
                (user_id,),
            )
            result = cur.fetchone()
            cur.close()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get event count: {e}")
            return 0

    # ==================== Preference Learning ====================

    def compute_preferences_from_events(self, user_id: str) -> Optional[UserPreferences]:
        """Compute preferences from recorded events.

        This analyzes patterns in suggestion acceptances and edits to
        infer user preferences.

        Args:
            user_id: User's UUID.

        Returns:
            Computed UserPreferences (not saved).
        """
        events = self.get_events(user_id, limit=500)
        if not events:
            return None

        # Analyze events to infer preferences
        tone_votes = Counter()
        structure_votes = Counter()
        first_person_votes = Counter()
        achievement_votes = Counter()

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
            user_id: User's UUID.

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
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None


# Singleton instance for use across the application
_preferences_service: Optional[PreferencesService] = None


def get_preferences_service() -> PreferencesService:
    """Get the singleton PreferencesService instance."""
    global _preferences_service
    if _preferences_service is None:
        _preferences_service = PreferencesService()
        _preferences_service.ensure_tables_exist()
    return _preferences_service
