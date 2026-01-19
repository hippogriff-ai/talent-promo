"""Draft ratings service for user feedback on generated resumes.

This service handles:
- Draft rating submission and retrieval
- Rating history for users
- Rating summary/analytics
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DraftRating(BaseModel):
    """Draft rating model."""

    id: Optional[str] = None
    user_id: Optional[str] = None
    thread_id: str
    overall_quality: Optional[int] = None  # 1-5 stars
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
    """Service for managing draft ratings."""

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
            logger.warning("No DATABASE_URL configured, ratings service disabled")
            return None

        if self._connection is None or self._connection.closed:
            try:
                import psycopg2

                self._connection = psycopg2.connect(self.database_url)
            except ImportError:
                logger.error("psycopg2 not installed, ratings service disabled")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                return None

        return self._connection

    def ensure_tables_exist(self) -> bool:
        """Create ratings tables if they don't exist.

        Returns:
            True if tables exist or were created, False on error.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS draft_ratings (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID,
                    thread_id VARCHAR(255) NOT NULL,
                    overall_quality INTEGER CHECK (overall_quality BETWEEN 1 AND 5),
                    ats_satisfaction BOOLEAN,
                    would_send_as_is BOOLEAN,
                    feedback_text TEXT,
                    job_title VARCHAR(255),
                    company_name VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # Create indexes
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_draft_ratings_user_id ON draft_ratings(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_draft_ratings_thread_id ON draft_ratings(thread_id)"
            )

            conn.commit()
            cur.close()
            logger.info("Ratings tables created/verified successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create ratings tables: {e}")
            conn.rollback()
            return False

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
        conn = self._get_connection()
        if not conn:
            return None

        effective_user_id = user_id or rating.user_id

        try:
            cur = conn.cursor()

            # Check if rating already exists for this thread
            cur.execute(
                """
                SELECT id FROM draft_ratings
                WHERE thread_id = %s AND (user_id = %s OR (user_id IS NULL AND %s IS NULL))
                """,
                (rating.thread_id, effective_user_id, effective_user_id),
            )
            existing = cur.fetchone()

            if existing:
                # Update existing rating
                cur.execute(
                    """
                    UPDATE draft_ratings
                    SET overall_quality = %s,
                        ats_satisfaction = %s,
                        would_send_as_is = %s,
                        feedback_text = %s,
                        job_title = %s,
                        company_name = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, user_id, thread_id, overall_quality, ats_satisfaction,
                              would_send_as_is, feedback_text, job_title, company_name,
                              created_at, updated_at
                    """,
                    (
                        rating.overall_quality,
                        rating.ats_satisfaction,
                        rating.would_send_as_is,
                        rating.feedback_text,
                        rating.job_title,
                        rating.company_name,
                        existing[0],
                    ),
                )
            else:
                # Create new rating
                cur.execute(
                    """
                    INSERT INTO draft_ratings
                        (user_id, thread_id, overall_quality, ats_satisfaction,
                         would_send_as_is, feedback_text, job_title, company_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, user_id, thread_id, overall_quality, ats_satisfaction,
                              would_send_as_is, feedback_text, job_title, company_name,
                              created_at, updated_at
                    """,
                    (
                        effective_user_id,
                        rating.thread_id,
                        rating.overall_quality,
                        rating.ats_satisfaction,
                        rating.would_send_as_is,
                        rating.feedback_text,
                        rating.job_title,
                        rating.company_name,
                    ),
                )

            row = cur.fetchone()
            conn.commit()
            cur.close()

            if row:
                return DraftRating(
                    id=str(row[0]),
                    user_id=str(row[1]) if row[1] else None,
                    thread_id=row[2],
                    overall_quality=row[3],
                    ats_satisfaction=row[4],
                    would_send_as_is=row[5],
                    feedback_text=row[6],
                    job_title=row[7],
                    company_name=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to submit rating: {e}")
            conn.rollback()
            return None

    def get_rating(self, thread_id: str) -> Optional[DraftRating]:
        """Get rating for a specific thread.

        Args:
            thread_id: The workflow thread ID.

        Returns:
            DraftRating if found, None otherwise.
        """
        conn = self._get_connection()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, user_id, thread_id, overall_quality, ats_satisfaction,
                       would_send_as_is, feedback_text, job_title, company_name,
                       created_at, updated_at
                FROM draft_ratings
                WHERE thread_id = %s
                """,
                (thread_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                return DraftRating(
                    id=str(row[0]),
                    user_id=str(row[1]) if row[1] else None,
                    thread_id=row[2],
                    overall_quality=row[3],
                    ats_satisfaction=row[4],
                    would_send_as_is=row[5],
                    feedback_text=row[6],
                    job_title=row[7],
                    company_name=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get rating: {e}")
            return None

    def get_user_ratings(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[DraftRating]:
        """Get rating history for a user.

        Args:
            user_id: User's UUID.
            limit: Maximum number of ratings to return.
            offset: Offset for pagination.

        Returns:
            List of DraftRating objects.
        """
        conn = self._get_connection()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, user_id, thread_id, overall_quality, ats_satisfaction,
                       would_send_as_is, feedback_text, job_title, company_name,
                       created_at, updated_at
                FROM draft_ratings
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = cur.fetchall()
            cur.close()

            return [
                DraftRating(
                    id=str(row[0]),
                    user_id=str(row[1]) if row[1] else None,
                    thread_id=row[2],
                    overall_quality=row[3],
                    ats_satisfaction=row[4],
                    would_send_as_is=row[5],
                    feedback_text=row[6],
                    job_title=row[7],
                    company_name=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get user ratings: {e}")
            return []

    def get_rating_summary(self, user_id: str) -> RatingSummary:
        """Get rating summary statistics for a user.

        Args:
            user_id: User's UUID.

        Returns:
            RatingSummary with aggregate statistics.
        """
        conn = self._get_connection()
        if not conn:
            return RatingSummary(total_ratings=0)

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    COUNT(*) as total,
                    AVG(overall_quality) as avg_quality,
                    AVG(CASE WHEN would_send_as_is THEN 1.0 ELSE 0.0 END) as would_send_rate,
                    AVG(CASE WHEN ats_satisfaction THEN 1.0 ELSE 0.0 END) as ats_rate
                FROM draft_ratings
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row and row[0] > 0:
                return RatingSummary(
                    total_ratings=row[0],
                    average_quality=float(row[1]) if row[1] else None,
                    would_send_rate=float(row[2]) * 100 if row[2] else None,
                    ats_satisfaction_rate=float(row[3]) * 100 if row[3] else None,
                )
            return RatingSummary(total_ratings=0)
        except Exception as e:
            logger.error(f"Failed to get rating summary: {e}")
            return RatingSummary(total_ratings=0)

    def delete_rating(self, rating_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a rating.

        Args:
            rating_id: The rating UUID.
            user_id: Optional user ID to verify ownership.

        Returns:
            True if deleted successfully.
        """
        conn = self._get_connection()
        if not conn:
            return False

        try:
            cur = conn.cursor()

            if user_id:
                # Only delete if user owns it
                cur.execute(
                    "DELETE FROM draft_ratings WHERE id = %s AND user_id = %s",
                    (rating_id, user_id),
                )
            else:
                cur.execute(
                    "DELETE FROM draft_ratings WHERE id = %s",
                    (rating_id,),
                )

            deleted = cur.rowcount > 0
            conn.commit()
            cur.close()
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete rating: {e}")
            conn.rollback()
            return False

    def get_rating_count(self, user_id: str) -> int:
        """Get total rating count for a user.

        Args:
            user_id: User's UUID.

        Returns:
            Number of ratings.
        """
        conn = self._get_connection()
        if not conn:
            return 0

        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM draft_ratings WHERE user_id = %s",
                (user_id,),
            )
            result = cur.fetchone()
            cur.close()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get rating count: {e}")
            return 0

    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None


# Singleton instance for use across the application
_ratings_service: Optional[RatingsService] = None


def get_ratings_service() -> RatingsService:
    """Get the singleton RatingsService instance."""
    global _ratings_service
    if _ratings_service is None:
        _ratings_service = RatingsService()
        _ratings_service.ensure_tables_exist()
    return _ratings_service
