"""Arena service for A/B comparison management."""

import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime
from typing import Optional

import psycopg2
from contextlib import contextmanager
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ArenaComparison(BaseModel):
    """Arena comparison record."""
    arena_id: str
    variant_a_thread_id: str
    variant_b_thread_id: str
    status: str = "running"
    sync_point: Optional[str] = None
    winner: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    input_data: dict = Field(default_factory=dict)


class PreferenceRating(BaseModel):
    """Preference rating for a step."""
    rating_id: str = ""
    arena_id: str
    step: str
    aspect: str
    preference: str
    reason: Optional[str] = None
    rated_by: str = "admin"


class VariantMetrics(BaseModel):
    """Metrics for one variant."""
    variant: str
    thread_id: str
    total_duration_ms: int = 0
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    ats_score: Optional[int] = None
    step_metrics: list[dict] = Field(default_factory=list)


class PreferenceAnalytics(BaseModel):
    """Cumulative preference analytics across all comparisons."""
    total_comparisons: int = 0
    total_ratings: int = 0
    variant_a_wins: int = 0
    variant_b_wins: int = 0
    ties: int = 0
    win_rate_a: float = 0.0
    win_rate_b: float = 0.0
    by_step: dict[str, dict] = Field(default_factory=dict)
    by_aspect: dict[str, dict] = Field(default_factory=dict)


class SSEToken(BaseModel):
    """Short-lived token for SSE authentication."""
    token: str
    arena_id: str
    expires_at: float  # Unix timestamp


class ArenaService:
    """Service for managing arena comparisons."""

    SSE_TOKEN_TTL_SECONDS = 120  # 2 minutes (short-lived for security)

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self._comparisons: dict[str, ArenaComparison] = {}
        self._ratings: dict[str, list[PreferenceRating]] = {}
        self._metrics: dict[str, dict[str, VariantMetrics]] = {}  # arena_id -> {variant -> metrics}
        self._sse_tokens: dict[str, SSEToken] = {}  # token -> SSEToken

    @contextmanager
    def _db_connection(self):
        """Context manager for database connections. Yields None if no database configured."""
        if not self.database_url:
            yield None
            return
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_comparison(
        self,
        variant_a_thread_id: str,
        variant_b_thread_id: str,
        input_data: dict,
        created_by: str = "admin",
    ) -> ArenaComparison:
        """Create a new arena comparison."""
        arena_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        comparison = ArenaComparison(
            arena_id=arena_id,
            variant_a_thread_id=variant_a_thread_id,
            variant_b_thread_id=variant_b_thread_id,
            status="running",
            created_at=now,
            input_data=input_data,
        )

        # Store in memory for non-database mode
        self._comparisons[arena_id] = comparison

        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO arena_comparisons
                           (arena_id, variant_a_thread_id, variant_b_thread_id, status, created_at, created_by, input_data)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (arena_id, variant_a_thread_id, variant_b_thread_id, "running", now, created_by, json.dumps(input_data)),
                    )
                conn.commit()

        return comparison

    def get_comparison(self, arena_id: str) -> Optional[ArenaComparison]:
        """Get an arena comparison by ID."""
        with self._db_connection() as conn:
            if not conn:
                return self._comparisons.get(arena_id)

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT arena_id, variant_a_thread_id, variant_b_thread_id, status, sync_point, winner, created_at, completed_at
                       FROM arena_comparisons WHERE arena_id = %s""",
                    (arena_id,),
                )
                row = cur.fetchone()
                if row:
                    return ArenaComparison(
                        arena_id=row[0],
                        variant_a_thread_id=row[1],
                        variant_b_thread_id=row[2],
                        status=row[3],
                        sync_point=row[4],
                        winner=row[5],
                        created_at=row[6].isoformat() if row[6] else "",
                        completed_at=row[7].isoformat() if row[7] else None,
                    )
            return self._comparisons.get(arena_id)

    def update_status(self, arena_id: str, status: str, sync_point: Optional[str] = None):
        """Update comparison status."""
        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE arena_comparisons SET status = %s, sync_point = %s WHERE arena_id = %s",
                        (status, sync_point, arena_id),
                    )
                conn.commit()

    def save_rating(self, rating: PreferenceRating) -> PreferenceRating:
        """Save a preference rating."""
        rating.rating_id = str(uuid.uuid4())

        # Store in memory
        if rating.arena_id not in self._ratings:
            self._ratings[rating.arena_id] = []
        self._ratings[rating.arena_id].append(rating)

        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO arena_ratings (rating_id, arena_id, step, aspect, preference, reason, rated_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (rating.rating_id, rating.arena_id, rating.step, rating.aspect, rating.preference, rating.reason, rating.rated_by),
                    )
                conn.commit()

        return rating

    def get_ratings(self, arena_id: str) -> list[PreferenceRating]:
        """Get all ratings for a comparison."""
        with self._db_connection() as conn:
            if not conn:
                return self._ratings.get(arena_id, [])

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rating_id, arena_id, step, aspect, preference, reason, rated_by FROM arena_ratings WHERE arena_id = %s",
                    (arena_id,),
                )
                return [
                    PreferenceRating(
                        rating_id=row[0],
                        arena_id=row[1],
                        step=row[2],
                        aspect=row[3],
                        preference=row[4],
                        reason=row[5],
                        rated_by=row[6],
                    )
                    for row in cur.fetchall()
                ]

    def list_comparisons(self, limit: int = 20, offset: int = 0) -> list[ArenaComparison]:
        """List all comparisons."""
        with self._db_connection() as conn:
            if not conn:
                # Return from memory, sorted by created_at desc
                all_comparisons = list(self._comparisons.values())
                all_comparisons.sort(key=lambda c: c.created_at, reverse=True)
                return all_comparisons[offset : offset + limit]

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT arena_id, variant_a_thread_id, variant_b_thread_id, status, sync_point, winner, created_at
                       FROM arena_comparisons ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
                return [
                    ArenaComparison(
                        arena_id=row[0],
                        variant_a_thread_id=row[1],
                        variant_b_thread_id=row[2],
                        status=row[3],
                        sync_point=row[4],
                        winner=row[5],
                        created_at=row[6].isoformat() if row[6] else "",
                    )
                    for row in cur.fetchall()
                ]


    def save_metrics(self, arena_id: str, variant: str, metrics: VariantMetrics) -> None:
        """Save metrics for a variant to memory and database."""
        if arena_id not in self._metrics:
            self._metrics[arena_id] = {}
        self._metrics[arena_id][variant] = metrics

        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    metric_id = str(uuid.uuid4())
                    step_metrics_json = json.dumps(metrics.step_metrics) if metrics.step_metrics else "[]"
                    # Use UPSERT pattern with ON CONFLICT for atomicity
                    cur.execute(
                        """INSERT INTO arena_variant_metrics
                           (metric_id, arena_id, variant, thread_id, total_duration_ms,
                            total_llm_calls, total_input_tokens, total_output_tokens, ats_score, step_metrics)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (arena_id, variant) DO UPDATE SET
                               thread_id = EXCLUDED.thread_id,
                               total_duration_ms = EXCLUDED.total_duration_ms,
                               total_llm_calls = EXCLUDED.total_llm_calls,
                               total_input_tokens = EXCLUDED.total_input_tokens,
                               total_output_tokens = EXCLUDED.total_output_tokens,
                               ats_score = EXCLUDED.ats_score,
                               step_metrics = EXCLUDED.step_metrics""",
                        (metric_id, arena_id, variant, metrics.thread_id,
                         metrics.total_duration_ms, metrics.total_llm_calls,
                         metrics.total_input_tokens, metrics.total_output_tokens,
                         metrics.ats_score, step_metrics_json)
                    )
                conn.commit()

    def get_metrics(self, arena_id: str) -> dict[str, VariantMetrics]:
        """Get metrics for both variants of a comparison from database or memory."""
        with self._db_connection() as conn:
            if not conn:
                return self._metrics.get(arena_id, {})

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT variant, thread_id, total_duration_ms, total_llm_calls,
                              total_input_tokens, total_output_tokens, ats_score, step_metrics
                       FROM arena_variant_metrics WHERE arena_id = %s""",
                    (arena_id,)
                )
                result = {}
                for row in cur.fetchall():
                    # Deserialize JSON step_metrics
                    step_metrics = json.loads(row[7]) if isinstance(row[7], str) else (row[7] or [])
                    result[row[0]] = VariantMetrics(
                        variant=row[0],
                        thread_id=row[1],
                        total_duration_ms=row[2] or 0,
                        total_llm_calls=row[3] or 0,
                        total_input_tokens=row[4] or 0,
                        total_output_tokens=row[5] or 0,
                        ats_score=row[6],
                        step_metrics=step_metrics
                    )
                return result if result else self._metrics.get(arena_id, {})

    def _aggregate_ratings(self, ratings: list[PreferenceRating], analytics: PreferenceAnalytics) -> None:
        """Aggregate ratings into analytics counts."""
        for rating in ratings:
            if rating.preference == "A":
                analytics.variant_a_wins += 1
            elif rating.preference == "B":
                analytics.variant_b_wins += 1
            else:
                analytics.ties += 1

            # Aggregate by step
            if rating.step not in analytics.by_step:
                analytics.by_step[rating.step] = {"A": 0, "B": 0, "tie": 0}
            analytics.by_step[rating.step][rating.preference] += 1

            # Aggregate by aspect
            if rating.aspect not in analytics.by_aspect:
                analytics.by_aspect[rating.aspect] = {"A": 0, "B": 0, "tie": 0}
            analytics.by_aspect[rating.aspect][rating.preference] += 1

    def cleanup_comparison(self, arena_id: str) -> bool:
        """Remove a completed comparison from memory and database."""
        removed = arena_id in self._comparisons
        self._comparisons.pop(arena_id, None)
        self._ratings.pop(arena_id, None)
        self._metrics.pop(arena_id, None)

        # Clean up associated SSE tokens
        tokens_to_remove = [
            t for t, data in self._sse_tokens.items()
            if data.arena_id == arena_id
        ]
        for t in tokens_to_remove:
            self._sse_tokens.pop(t, None)

        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    # CASCADE will delete related ratings and metrics
                    cur.execute("DELETE FROM arena_comparisons WHERE arena_id = %s", (arena_id,))
                conn.commit()

        return removed

    def create_sse_token(self, arena_id: str) -> str:
        """Create a short-lived token for SSE authentication."""
        # Clean up expired tokens first
        self._cleanup_expired_sse_tokens()

        token = secrets.token_urlsafe(32)
        expires_at = time.time() + self.SSE_TOKEN_TTL_SECONDS

        self._sse_tokens[token] = SSEToken(
            token=token,
            arena_id=arena_id,
            expires_at=expires_at,
        )
        return token

    def validate_sse_token(self, token: str, arena_id: str) -> bool:
        """Validate an SSE token for a specific arena (single-use).

        Uses constant-time comparison to prevent timing attacks.
        Token is consumed on successful validation to prevent reuse.
        """
        sse_token = self._sse_tokens.pop(token, None)  # Atomic: remove immediately
        if not sse_token:
            return False
        # Check expiration first
        if time.time() > sse_token.expires_at:
            return False
        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(sse_token.arena_id, arena_id):
            return False
        return True

    def _cleanup_expired_sse_tokens(self) -> None:
        """Remove expired SSE tokens."""
        now = time.time()
        expired = [t for t, data in self._sse_tokens.items() if now > data.expires_at]
        for token in expired:
            self._sse_tokens.pop(token, None)

    def get_analytics(self) -> PreferenceAnalytics:
        """Get cumulative preference analytics across all comparisons."""
        analytics = PreferenceAnalytics()

        with self._db_connection() as conn:
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM arena_comparisons")
                    analytics.total_comparisons = cur.fetchone()[0]

                    cur.execute(
                        "SELECT rating_id, arena_id, step, aspect, preference, reason, rated_by FROM arena_ratings"
                    )
                    ratings = [
                        PreferenceRating(
                            rating_id=row[0], arena_id=row[1], step=row[2],
                            aspect=row[3], preference=row[4], reason=row[5], rated_by=row[6]
                        )
                        for row in cur.fetchall()
                    ]
                    self._aggregate_ratings(ratings, analytics)
            else:
                analytics.total_comparisons = len(self._comparisons)
                all_ratings = [r for ratings in self._ratings.values() for r in ratings]
                self._aggregate_ratings(all_ratings, analytics)

        analytics.total_ratings = analytics.variant_a_wins + analytics.variant_b_wins + analytics.ties
        if analytics.total_ratings > 0:
            analytics.win_rate_a = analytics.variant_a_wins / analytics.total_ratings
            analytics.win_rate_b = analytics.variant_b_wins / analytics.total_ratings

        return analytics


_arena_service: Optional[ArenaService] = None


def get_arena_service() -> ArenaService:
    """Get or create the arena service singleton."""
    global _arena_service
    if _arena_service is None:
        _arena_service = ArenaService()
    return _arena_service
