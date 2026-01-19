"""Ratings router for draft quality feedback.

Endpoints:
- POST /api/ratings - Submit a rating
- GET /api/ratings/{thread_id} - Get rating for a thread
- GET /api/ratings/history - Get user's rating history
- GET /api/ratings/summary - Get user's rating summary
- DELETE /api/ratings/{rating_id} - Delete a rating
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from middleware.session_auth import get_current_user, get_user_id_optional
from services.auth_service import User
from services.ratings_service import (
    DraftRating,
    RatingSummary,
    get_ratings_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


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


class DeleteResponse(BaseModel):
    """Response for delete operation."""

    message: str
    deleted: bool


# ==================== Endpoints ====================


@router.post("", response_model=RatingResponse)
async def submit_rating(
    body: SubmitRatingInput,
    user: User = Depends(get_current_user),
) -> RatingResponse:
    """Submit or update a draft rating.

    If a rating already exists for this thread, it will be updated.
    Otherwise, a new rating is created.
    """
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

    saved_rating = service.submit_rating(rating, user_id=user.id)
    if not saved_rating:
        raise HTTPException(status_code=500, detail="Failed to submit rating")

    return RatingResponse(rating=saved_rating)


@router.get("/history", response_model=RatingsHistoryResponse)
async def get_rating_history(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
) -> RatingsHistoryResponse:
    """Get rating history for the current user.

    Args:
        limit: Maximum number of ratings to return (1-50).
        offset: Offset for pagination.
    """
    service = get_ratings_service()

    ratings = service.get_user_ratings(user.id, limit=limit + 1, offset=offset)
    total_count = service.get_rating_count(user.id)

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
    user: User = Depends(get_current_user),
) -> RatingSummaryResponse:
    """Get rating summary statistics for the current user.

    Returns aggregate statistics including:
    - Total number of ratings
    - Average quality rating
    - Percentage that would send as-is
    - ATS satisfaction rate
    """
    service = get_ratings_service()
    summary = service.get_rating_summary(user.id)

    return RatingSummaryResponse(summary=summary)


@router.get("/{thread_id}", response_model=RatingResponse)
async def get_rating(
    thread_id: str,
    user_id: Optional[str] = Depends(get_user_id_optional),
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


@router.delete("/{rating_id}", response_model=DeleteResponse)
async def delete_rating(
    rating_id: str,
    user: User = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a rating.

    Users can only delete their own ratings.
    """
    service = get_ratings_service()
    deleted = service.delete_rating(rating_id, user_id=user.id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Rating not found or not owned by user")

    return DeleteResponse(message="Rating deleted", deleted=True)


# ==================== Anonymous User Support ====================


@router.post("/anonymous", response_model=RatingResponse)
async def submit_anonymous_rating(
    body: SubmitRatingInput,
    anonymous_id: Optional[str] = None,
    user_id: Optional[str] = Depends(get_user_id_optional),
) -> RatingResponse:
    """Submit a rating for anonymous users.

    Ratings can be stored without authentication and later
    migrated when the user creates an account.

    Args:
        anonymous_id: Client-generated anonymous identifier.
    """
    service = get_ratings_service()

    # If user is authenticated, use their real user_id
    effective_user_id = user_id or (f"anon:{anonymous_id}" if anonymous_id else None)

    rating = DraftRating(
        thread_id=body.thread_id,
        overall_quality=body.overall_quality,
        ats_satisfaction=body.ats_satisfaction,
        would_send_as_is=body.would_send_as_is,
        feedback_text=body.feedback_text,
        job_title=body.job_title,
        company_name=body.company_name,
    )

    saved_rating = service.submit_rating(rating, user_id=effective_user_id)
    if not saved_rating:
        raise HTTPException(status_code=500, detail="Failed to submit rating")

    return RatingResponse(rating=saved_rating)
