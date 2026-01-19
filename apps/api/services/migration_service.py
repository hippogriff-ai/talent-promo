"""Migration service for anonymous to authenticated user data transfer.

This service handles:
- Migrating anonymous preferences to user account
- Migrating anonymous events to user account
- Migrating anonymous ratings to user account
- Conflict resolution (server data takes precedence)
"""

import logging
import os
from typing import Optional

from pydantic import BaseModel

from services.preferences_service import (
    PreferenceEvent,
    PreferencesService,
    UserPreferences,
    get_preferences_service,
)
from services.ratings_service import DraftRating, RatingsService, get_ratings_service

logger = logging.getLogger(__name__)


class AnonymousData(BaseModel):
    """Data collected from anonymous user's localStorage."""

    anonymous_id: str
    preferences: Optional[dict] = None
    events: list[dict] = []
    ratings: list[dict] = []


class MigrationResult(BaseModel):
    """Result of migration operation."""

    preferences_migrated: bool = False
    events_migrated: int = 0
    ratings_migrated: int = 0
    errors: list[str] = []


class MigrationService:
    """Service for migrating anonymous user data to authenticated accounts."""

    def __init__(
        self,
        preferences_service: Optional[PreferencesService] = None,
        ratings_service: Optional[RatingsService] = None,
    ):
        """Initialize the service.

        Args:
            preferences_service: Optional preferences service instance.
            ratings_service: Optional ratings service instance.
        """
        self._preferences_service = preferences_service
        self._ratings_service = ratings_service

    @property
    def preferences_service(self) -> PreferencesService:
        """Get preferences service (lazy load)."""
        if self._preferences_service is None:
            self._preferences_service = get_preferences_service()
        return self._preferences_service

    @property
    def ratings_service(self) -> RatingsService:
        """Get ratings service (lazy load)."""
        if self._ratings_service is None:
            self._ratings_service = get_ratings_service()
        return self._ratings_service

    def migrate_anonymous_data(
        self,
        user_id: str,
        data: AnonymousData,
    ) -> MigrationResult:
        """Migrate anonymous user data to authenticated account.

        Conflict resolution: If user already has preferences, they take
        precedence (don't overwrite with anonymous data).

        Args:
            user_id: The authenticated user's UUID.
            data: Anonymous data from localStorage.

        Returns:
            MigrationResult with counts of migrated items.
        """
        result = MigrationResult()

        # Migrate preferences (only if user doesn't have any)
        if data.preferences:
            try:
                prefs_migrated = self._migrate_preferences(user_id, data.preferences)
                result.preferences_migrated = prefs_migrated
            except Exception as e:
                logger.error(f"Failed to migrate preferences: {e}")
                result.errors.append(f"Preferences: {str(e)}")

        # Migrate events
        if data.events:
            try:
                events_count = self._migrate_events(user_id, data.events)
                result.events_migrated = events_count
            except Exception as e:
                logger.error(f"Failed to migrate events: {e}")
                result.errors.append(f"Events: {str(e)}")

        # Migrate ratings
        if data.ratings:
            try:
                ratings_count = self._migrate_ratings(user_id, data.ratings)
                result.ratings_migrated = ratings_count
            except Exception as e:
                logger.error(f"Failed to migrate ratings: {e}")
                result.errors.append(f"Ratings: {str(e)}")

        # Clean up anonymous data from database
        self._cleanup_anonymous_data(data.anonymous_id)

        logger.info(
            f"Migration for user {user_id}: "
            f"prefs={result.preferences_migrated}, "
            f"events={result.events_migrated}, "
            f"ratings={result.ratings_migrated}"
        )

        return result

    def _migrate_preferences(self, user_id: str, preferences: dict) -> bool:
        """Migrate preferences from anonymous to user account.

        Only migrates if user doesn't already have preferences set.

        Args:
            user_id: The authenticated user's UUID.
            preferences: Anonymous preferences dict.

        Returns:
            True if preferences were migrated.
        """
        existing = self.preferences_service.get_preferences(user_id)

        # If user already has preferences with any set values, don't overwrite
        if existing:
            has_values = any([
                existing.tone,
                existing.structure,
                existing.sentence_length,
                existing.first_person is not None,
                existing.quantification_preference,
                existing.achievement_focus is not None,
                existing.custom_preferences,
            ])
            if has_values:
                logger.info(f"User {user_id} already has preferences, skipping migration")
                return False

        # Filter to only valid preference fields
        valid_fields = {
            "tone",
            "structure",
            "sentence_length",
            "first_person",
            "quantification_preference",
            "achievement_focus",
            "custom_preferences",
        }
        filtered_prefs = {k: v for k, v in preferences.items() if k in valid_fields and v is not None}

        if not filtered_prefs:
            return False

        # Create or update preferences
        self.preferences_service.get_or_create_preferences(user_id)
        result = self.preferences_service.update_preferences(user_id, filtered_prefs)

        return result is not None

    def _migrate_events(self, user_id: str, events: list[dict]) -> int:
        """Migrate preference events from anonymous to user account.

        Args:
            user_id: The authenticated user's UUID.
            events: List of anonymous event dicts.

        Returns:
            Number of events migrated.
        """
        migrated = 0

        for event_data in events:
            try:
                event_type = event_data.get("event_type")
                if event_type not in ("edit", "suggestion_accept", "suggestion_reject"):
                    continue

                event = PreferenceEvent(
                    event_type=event_type,
                    event_data=event_data.get("event_data", {}),
                    thread_id=event_data.get("thread_id"),
                )

                if self.preferences_service.record_event(user_id, event):
                    migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate event: {e}")
                continue

        return migrated

    def _migrate_ratings(self, user_id: str, ratings: list[dict]) -> int:
        """Migrate ratings from anonymous to user account.

        Args:
            user_id: The authenticated user's UUID.
            ratings: List of anonymous rating dicts.

        Returns:
            Number of ratings migrated.
        """
        migrated = 0

        for rating_data in ratings:
            try:
                thread_id = rating_data.get("thread_id")
                if not thread_id:
                    continue

                # Check if rating already exists for this thread
                existing = self.ratings_service.get_rating(thread_id)
                if existing and existing.user_id:
                    # Already has a user rating, skip
                    continue

                rating = DraftRating(
                    thread_id=thread_id,
                    overall_quality=rating_data.get("overall_quality"),
                    ats_satisfaction=rating_data.get("ats_satisfaction"),
                    would_send_as_is=rating_data.get("would_send_as_is"),
                    feedback_text=rating_data.get("feedback_text"),
                    job_title=rating_data.get("job_title"),
                    company_name=rating_data.get("company_name"),
                )

                if self.ratings_service.submit_rating(rating, user_id=user_id):
                    migrated += 1
            except Exception as e:
                logger.warning(f"Failed to migrate rating: {e}")
                continue

        return migrated

    def _cleanup_anonymous_data(self, anonymous_id: str) -> None:
        """Clean up anonymous data from database after migration.

        This removes data stored with the anonymous ID prefix.

        Args:
            anonymous_id: The anonymous user's ID.
        """
        anon_user_id = f"anon:{anonymous_id}"

        try:
            # Delete anonymous events
            self.preferences_service.delete_preferences(anon_user_id)
        except Exception as e:
            logger.warning(f"Failed to cleanup anonymous preferences: {e}")

        # Note: Ratings are updated in place (user_id changed), not deleted


# Singleton instance
_migration_service: Optional[MigrationService] = None


def get_migration_service() -> MigrationService:
    """Get the singleton MigrationService instance."""
    global _migration_service
    if _migration_service is None:
        _migration_service = MigrationService()
    return _migration_service
