"""In-memory draft ratings service for user feedback on generated resumes.

This service handles:
- Draft rating submission and retrieval (in-memory)
- Rating history for users
- Rating summary/analytics

Privacy by design: All data is ephemeral. Use browser localStorage for persistence.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DraftRating(BaseModel):
    """Draft rating model."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    thread_id: str
    overall_quality: Optional[int] = Field(None, ge=1, le=5, description="1-5 star rating")
    ats_satisfaction: Optional[bool] = None
    would_send_as_is: Optional[bool] = None
    feedback_text: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RatingSummary(BaseModel):
    """Summary of user's rating history."""

    total_ratings: int
    average_quality: Optional[float] = None
    would_send_rate: Optional[float] = None  # % that said yes
    ats_satisfaction_rate: Optional[float] = None


class RatingsService:
    """In-memory service for managing draft ratings."""

    def __init__(self):
        """Initialize the service with in-memory storage."""
        self._ratings: dict[str, DraftRating] = {}  # thread_id -> rating
        self._user_ratings: dict[str, list[str]] = {}  # user_id -> list of thread_ids
        logger.info("RatingsService initialized (in-memory)")

    # ==================== Rating CRUD ====================

    def submit_rating(
        self,
        rating: DraftRating,
        user_id: Optional[str] = None,
    ) -> Optional[DraftRating]:
        """Submit or update a draft rating.

        Args:
            rating: The rating to submit.
            user_id: Optional user ID (overrides rating.user_id).

        Returns:
            Saved DraftRating if successful.
        """
        import uuid

        effective_user_id = user_id or rating.user_id
        now = datetime.now(timezone.utc)

        # Check if rating already exists for this thread
        existing = self._ratings.get(rating.thread_id)

        if existing:
            # Update existing rating
            existing.overall_quality = rating.overall_quality
            existing.ats_satisfaction = rating.ats_satisfaction
            existing.would_send_as_is = rating.would_send_as_is
            existing.feedback_text = rating.feedback_text
            existing.job_title = rating.job_title
            existing.company_name = rating.company_name
            existing.updated_at = now
            return existing
        else:
            # Create new rating
            new_rating = DraftRating(
                id=str(uuid.uuid4()),
                user_id=effective_user_id,
                thread_id=rating.thread_id,
                overall_quality=rating.overall_quality,
                ats_satisfaction=rating.ats_satisfaction,
                would_send_as_is=rating.would_send_as_is,
                feedback_text=rating.feedback_text,
                job_title=rating.job_title,
                company_name=rating.company_name,
                created_at=now,
                updated_at=now,
            )
            self._ratings[rating.thread_id] = new_rating

            # Track by user if user_id provided
            if effective_user_id:
                if effective_user_id not in self._user_ratings:
                    self._user_ratings[effective_user_id] = []
                if rating.thread_id not in self._user_ratings[effective_user_id]:
                    self._user_ratings[effective_user_id].append(rating.thread_id)

            return new_rating

    def get_rating(self, thread_id: str) -> Optional[DraftRating]:
        """Get rating for a specific thread.

        Args:
            thread_id: The workflow thread ID.

        Returns:
            DraftRating if found, None otherwise.
        """
        return self._ratings.get(thread_id)

    def get_user_ratings(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[DraftRating]:
        """Get rating history for a user.

        Args:
            user_id: User's ID.
            limit: Maximum number of ratings to return.
            offset: Offset for pagination.

        Returns:
            List of DraftRating objects.
        """
        thread_ids = self._user_ratings.get(user_id, [])
        ratings = [self._ratings[tid] for tid in thread_ids if tid in self._ratings]

        # Sort by created_at descending
        ratings = sorted(
            ratings,
            key=lambda r: r.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        return ratings[offset : offset + limit]

    def get_rating_summary(self, user_id: str) -> RatingSummary:
        """Get rating summary statistics for a user.

        Args:
            user_id: User's ID.

        Returns:
            RatingSummary with aggregate statistics.
        """
        ratings = self.get_user_ratings(user_id, limit=1000)

        if not ratings:
            return RatingSummary(total_ratings=0)

        total = len(ratings)
        quality_values = [r.overall_quality for r in ratings if r.overall_quality]
        would_send_values = [r.would_send_as_is for r in ratings if r.would_send_as_is is not None]
        ats_values = [r.ats_satisfaction for r in ratings if r.ats_satisfaction is not None]

        return RatingSummary(
            total_ratings=total,
            average_quality=sum(quality_values) / len(quality_values) if quality_values else None,
            would_send_rate=(sum(would_send_values) / len(would_send_values) * 100)
            if would_send_values
            else None,
            ats_satisfaction_rate=(sum(ats_values) / len(ats_values) * 100) if ats_values else None,
        )

    def delete_rating(self, rating_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a rating.

        Args:
            rating_id: The rating UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            True if deleted successfully.
        """
        # Find rating by id
        for thread_id, rating in self._ratings.items():
            if rating.id == rating_id:
                if user_id and rating.user_id != user_id:
                    return False

                # Remove from ratings
                del self._ratings[thread_id]

                # Remove from user_ratings
                if rating.user_id and rating.user_id in self._user_ratings:
                    self._user_ratings[rating.user_id] = [
                        tid
                        for tid in self._user_ratings[rating.user_id]
                        if tid != thread_id
                    ]

                return True

        return False

    def get_rating_count(self, user_id: str) -> int:
        """Get total rating count for a user.

        Args:
            user_id: User's ID.

        Returns:
            Number of ratings.
        """
        return len(self._user_ratings.get(user_id, []))

    def close(self):
        """Clear all data."""
        self._ratings.clear()
        self._user_ratings.clear()


# Singleton instance for use across the application
_ratings_service: Optional[RatingsService] = None


def get_ratings_service() -> RatingsService:
    """Get the singleton RatingsService instance."""
    global _ratings_service
    if _ratings_service is None:
        _ratings_service = RatingsService()
    return _ratings_service


def reset_ratings_service():
    """Reset singleton (for testing)."""
    global _ratings_service
    if _ratings_service:
        _ratings_service.close()
    _ratings_service = None
