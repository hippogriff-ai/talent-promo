"""Ratings router for draft quality feedback.

Endpoints:
- POST /api/ratings - Submit a rating (anonymous)
- GET /api/ratings/{thread_id} - Get rating for a thread
- GET /api/ratings/history - Get user's rating history
- GET /api/ratings/summary - Get user's rating summary
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from services.ratings_service import (
    DraftRating,
    RatingSummary,
    get_ratings_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


def get_anonymous_user_id(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID")
) -> str:
    """Get anonymous user ID from header or generate one."""
    return x_anonymous_id or f"anon_{uuid.uuid4().hex[:12]}"


# ==================== Request/Response Models ====================


class SubmitRatingInput(BaseModel):
    """Request body for submitting a rating."""

    thread_id: str
    overall_quality: Optional[int] = Field(None, ge=1, le=5)
    ats_satisfaction: Optional[bool] = None
    would_send_as_is: Optional[bool] = None
    feedback_text: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None


class RatingResponse(BaseModel):
    """Response for single rating."""

    rating: DraftRating


class RatingsHistoryResponse(BaseModel):
    """Response for rating history."""

    ratings: list[DraftRating]
    total_count: int
    has_more: bool


class RatingSummaryResponse(BaseModel):
    """Response for rating summary."""

    summary: RatingSummary


# ==================== Endpoints ====================


@router.post("", response_model=RatingResponse)
async def submit_rating(
    body: SubmitRatingInput,
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> RatingResponse:
    """Submit or update a draft rating.

    If a rating already exists for this thread, it will be updated.
    Otherwise, a new rating is created.
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_ratings_service()

    rating = DraftRating(
        thread_id=body.thread_id,
        overall_quality=body.overall_quality,
        ats_satisfaction=body.ats_satisfaction,
        would_send_as_is=body.would_send_as_is,
        feedback_text=body.feedback_text,
        job_title=body.job_title,
        company_name=body.company_name,
    )

    saved_rating = service.submit_rating(rating, user_id=user_id)
    if not saved_rating:
        raise HTTPException(status_code=500, detail="Failed to submit rating")

    return RatingResponse(rating=saved_rating)


@router.get("/history", response_model=RatingsHistoryResponse)
async def get_rating_history(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> RatingsHistoryResponse:
    """Get rating history for the current user.

    Args:
        limit: Maximum number of ratings to return (1-50).
        offset: Offset for pagination.
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_ratings_service()

    ratings = service.get_user_ratings(user_id, limit=limit + 1, offset=offset)
    total_count = service.get_rating_count(user_id)

    # Check if there are more results
    has_more = len(ratings) > limit
    if has_more:
        ratings = ratings[:limit]

    return RatingsHistoryResponse(
        ratings=ratings,
        total_count=total_count,
        has_more=has_more,
    )


@router.get("/summary", response_model=RatingSummaryResponse)
async def get_rating_summary(
    x_anonymous_id: Optional[str] = Header(None, alias="X-Anonymous-ID"),
) -> RatingSummaryResponse:
    """Get rating summary statistics for the current user.

    Returns aggregate statistics including:
    - Total number of ratings
    - Average quality rating
    - Percentage that would send as-is
    - ATS satisfaction rate
    """
    user_id = get_anonymous_user_id(x_anonymous_id)
    service = get_ratings_service()
    summary = service.get_rating_summary(user_id)

    return RatingSummaryResponse(summary=summary)


@router.get("/{thread_id}", response_model=RatingResponse)
async def get_rating(
    thread_id: str,
) -> RatingResponse:
    """Get rating for a specific thread.

    This endpoint is accessible without authentication to allow
    viewing ratings for shared resumes.
    """
    service = get_ratings_service()
    rating = service.get_rating(thread_id)

    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    return RatingResponse(rating=rating)
