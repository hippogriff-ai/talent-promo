"""API router for arena A/B comparison."""

import asyncio
import csv
import io
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel, Field

from middleware.admin_auth import verify_admin
from services.arena_service import get_arena_service, ArenaComparison, PreferenceRating, VariantMetrics
from routers.optimize import (
    _workflows,
    _get_workflow_data,
    _save_workflow_data,
    _resume_workflow,
    WorkflowStateResponse,
    get_workflow_status,
)
from workflow.graph import create_initial_state, get_workflow
from workflow.progress import current_thread_id, get_realtime_progress
from workflow_b.graph_b import get_workflow_b

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/arena", tags=["arena"])


def _verify_sse_token_or_401(token: Optional[str], arena_id: str) -> None:
    """Verify short-lived SSE token for stream endpoint.

    Only accepts short-lived SSE tokens (single-use, 2 minute TTL).
    Admin tokens are NOT accepted - they must not appear in URLs for security.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    service = get_arena_service()
    if not service.validate_sse_token(token, arena_id):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _get_comparison_or_404(arena_id: str) -> ArenaComparison:
    """Get comparison by ID or raise 404."""
    comparison = get_arena_service().get_comparison(arena_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Arena comparison not found")
    return comparison


# ============================================================================
# Variant-aware workflow runners
# ============================================================================

async def _run_variant_workflow(thread_id: str, variant: str):
    """Run workflow for specified variant (A or B)."""
    token = current_thread_id.set(thread_id)

    try:
        workflow_data = _get_workflow_data(thread_id)
        config = workflow_data["config"]
        initial_state = workflow_data["state"]

        # Add thread_id to state for Variant B planner
        initial_state["_thread_id"] = thread_id

        # Select workflow based on variant
        workflow = get_workflow() if variant == "A" else get_workflow_b()

        result = await workflow.ainvoke(initial_state, config)

        # Check for interrupt
        graph_state = await workflow.aget_state(config)
        has_interrupt = False
        interrupt_value = None

        if graph_state and hasattr(graph_state, 'tasks') and graph_state.tasks:
            has_interrupt = True
            for task in graph_state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    interrupt_value = task.interrupts[0].value if task.interrupts else None
                    break

        workflow_data["state"] = result if isinstance(result, dict) else dict(graph_state.values) if graph_state else {}
        workflow_data["interrupted"] = has_interrupt
        workflow_data["interrupt_value"] = interrupt_value
        _save_workflow_data(thread_id, workflow_data)

        logger.info(f"[Arena] Variant {variant} workflow {thread_id} reached step: {result.get('current_step', 'unknown')}")

    except Exception as e:
        workflow_data = _get_workflow_data(thread_id)
        if isinstance(e, GraphInterrupt):
            logger.info(f"[Arena] Variant {variant} workflow {thread_id} interrupted")
            workflow_data["interrupted"] = True
        else:
            logger.error(f"[Arena] Variant {variant} workflow {thread_id} error: {e}")
            workflow_data["state"]["current_step"] = "error"
            workflow_data["state"]["errors"] = [str(e)]
        _save_workflow_data(thread_id, workflow_data)
    finally:
        current_thread_id.reset(token)


def _compute_arena_status(variant_a, variant_b) -> tuple[str, str | None]:
    """Compute overall arena status and sync point from variant statuses."""
    if not (variant_a and variant_b):
        return "running", None

    a_status, b_status = variant_a.status, variant_b.status

    if "error" in (a_status, b_status):
        return "error", None
    if a_status == "completed" and b_status == "completed":
        return "completed", None
    if a_status == "waiting_input" and b_status == "waiting_input":
        sync = variant_a.current_step if variant_a.current_step == variant_b.current_step else None
        return "waiting_input", sync
    return "running", None


class ArenaStartRequest(BaseModel):
    """Request to start arena comparison."""
    linkedin_url: Optional[str] = None
    job_url: Optional[str] = None
    resume_text: Optional[str] = None
    job_text: Optional[str] = None


class ArenaStartResponse(BaseModel):
    """Response from starting arena comparison."""
    arena_id: str
    variant_a_thread_id: str
    variant_b_thread_id: str


class ArenaStatusResponse(BaseModel):
    """Combined status of both variants."""
    arena_id: str
    status: str
    sync_point: Optional[str] = None
    variant_a: Optional[WorkflowStateResponse] = None
    variant_b: Optional[WorkflowStateResponse] = None
    ratings: list[dict] = Field(default_factory=list)
    metrics: dict[str, dict] = Field(default_factory=dict)


class RatingRequest(BaseModel):
    """Request to submit preference rating."""
    step: str
    aspect: str
    preference: str
    reason: Optional[str] = None


class AnswerRequest(BaseModel):
    """Request to submit answer to both variants."""
    text: str


@router.get("/verify")
async def verify_token(admin: str = Depends(verify_admin)):
    """Verify admin token is valid."""
    return {"valid": True, "admin": admin}


@router.post("/{arena_id}/sse-token")
async def create_sse_token(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Create a short-lived token for SSE stream authentication.

    Returns a token valid for 5 minutes that can be used with the /stream endpoint.
    This is more secure than passing the admin token in the URL.
    """
    _get_comparison_or_404(arena_id)
    service = get_arena_service()
    token = service.create_sse_token(arena_id)
    return {"token": token, "expires_in_seconds": service.SSE_TOKEN_TTL_SECONDS}


@router.post("/start", response_model=ArenaStartResponse)
async def start_arena_comparison(
    request: ArenaStartRequest,
    admin: str = Depends(verify_admin),
):
    """Start parallel comparison of both variants."""
    service = get_arena_service()

    # Create two workflow threads with same input
    variant_a_id = str(uuid.uuid4())
    variant_b_id = str(uuid.uuid4())

    # Create initial states for both variants
    initial_state = create_initial_state(
        linkedin_url=request.linkedin_url,
        job_url=request.job_url,
        uploaded_resume_text=request.resume_text,
        uploaded_job_text=request.job_text,
    )

    # Store both workflows
    config_a = {"configurable": {"thread_id": variant_a_id}}
    config_b = {"configurable": {"thread_id": variant_b_id}}

    _workflows[variant_a_id] = {
        "state": initial_state.copy(),
        "config": config_a,
        "created_at": initial_state.get("created_at", ""),
        "variant": "A",
    }
    _workflows[variant_b_id] = {
        "state": initial_state.copy(),
        "config": config_b,
        "created_at": initial_state.get("created_at", ""),
        "variant": "B",
    }

    # Create comparison record
    comparison = service.create_comparison(
        variant_a_thread_id=variant_a_id,
        variant_b_thread_id=variant_b_id,
        input_data={
            "linkedin_url": request.linkedin_url,
            "job_url": request.job_url,
            "resume_text": request.resume_text,
            "job_text": request.job_text,
        },
        created_by=admin,
    )

    # Start both workflows in parallel - A uses original, B uses Deep Agents
    asyncio.create_task(_run_variant_workflow(variant_a_id, "A"))
    asyncio.create_task(_run_variant_workflow(variant_b_id, "B"))

    logger.info(f"Started arena comparison {comparison.arena_id} with variants A={variant_a_id}, B={variant_b_id}")

    return ArenaStartResponse(
        arena_id=comparison.arena_id,
        variant_a_thread_id=variant_a_id,
        variant_b_thread_id=variant_b_id,
    )


@router.get("/{arena_id}/status", response_model=ArenaStatusResponse)
async def get_arena_status(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Get status of both variants."""
    comparison = _get_comparison_or_404(arena_id)

    # Get status of both variants (silently handle missing workflows)
    variant_a = None
    variant_b = None

    try:
        variant_a = await get_workflow_status(comparison.variant_a_thread_id, include_data=True)
    except HTTPException:
        pass

    try:
        variant_b = await get_workflow_status(comparison.variant_b_thread_id, include_data=True)
    except HTTPException:
        pass

    status, sync_point = _compute_arena_status(variant_a, variant_b)
    service = get_arena_service()
    ratings = service.get_ratings(arena_id)
    metrics = service.get_metrics(arena_id)

    return ArenaStatusResponse(
        arena_id=arena_id,
        status=status,
        sync_point=sync_point,
        variant_a=variant_a,
        variant_b=variant_b,
        ratings=[r.model_dump() for r in ratings],
        metrics={k: v.model_dump() for k, v in metrics.items()},
    )


@router.post("/{arena_id}/answer")
async def submit_answer_to_both(
    arena_id: str,
    answer: AnswerRequest,
    admin: str = Depends(verify_admin),
):
    """Submit same answer to both variants."""
    comparison = _get_comparison_or_404(arena_id)

    asyncio.create_task(_resume_workflow(comparison.variant_a_thread_id, answer.text))
    asyncio.create_task(_resume_workflow(comparison.variant_b_thread_id, answer.text))

    return {"success": True, "message": "Answer submitted to both variants"}


VALID_STEPS = {"research", "discovery", "drafting", "export"}
VALID_ASPECTS = {"quality", "relevance", "completeness", "speed"}


def _sanitize_for_filename(value: str) -> str:
    """Sanitize a value for use in a filename."""
    return re.sub(r'[^a-zA-Z0-9._-]', '', value)[:50]


@router.post("/{arena_id}/rate")
async def submit_rating(
    arena_id: str,
    rating: RatingRequest,
    admin: str = Depends(verify_admin),
):
    """Submit preference rating."""
    _get_comparison_or_404(arena_id)

    if rating.preference not in ("A", "B", "tie"):
        raise HTTPException(status_code=400, detail="Preference must be A, B, or tie")
    if rating.step not in VALID_STEPS:
        raise HTTPException(status_code=400, detail=f"Step must be one of: {', '.join(sorted(VALID_STEPS))}")
    if rating.aspect not in VALID_ASPECTS:
        raise HTTPException(status_code=400, detail=f"Aspect must be one of: {', '.join(sorted(VALID_ASPECTS))}")

    saved = get_arena_service().save_rating(PreferenceRating(
        arena_id=arena_id,
        step=rating.step,
        aspect=rating.aspect,
        preference=rating.preference,
        reason=rating.reason,
        rated_by=admin,
    ))

    return {"success": True, "rating_id": saved.rating_id}


async def _resume_both_variants(arena_id: str, command: str, message: str) -> dict:
    """Resume both variants with the same command."""
    comparison = _get_comparison_or_404(arena_id)
    asyncio.create_task(_resume_workflow(comparison.variant_a_thread_id, command))
    asyncio.create_task(_resume_workflow(comparison.variant_b_thread_id, command))
    return {"success": True, "message": message}


@router.post("/{arena_id}/discovery/confirm")
async def confirm_discovery_both(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Confirm discovery for both variants."""
    return await _resume_both_variants(arena_id, "discovery_complete", "Discovery confirmed for both variants")


@router.post("/{arena_id}/drafting/approve")
async def approve_draft_both(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Approve draft for both variants."""
    return await _resume_both_variants(arena_id, "approve", "Draft approved for both variants")


@router.get("/comparisons")
async def list_comparisons(
    limit: int = 20,
    offset: int = 0,
    admin: str = Depends(verify_admin),
):
    """List all arena comparisons."""
    service = get_arena_service()
    comparisons = service.list_comparisons(limit=limit, offset=offset)
    return {
        "comparisons": [c.model_dump() for c in comparisons],
        "count": len(comparisons),
    }


@router.get("/analytics")
async def get_analytics(admin: str = Depends(verify_admin)):
    """Get cumulative preference analytics across all comparisons."""
    service = get_arena_service()
    analytics = service.get_analytics()
    return analytics.model_dump()


class MetricsRequest(BaseModel):
    """Request to submit variant metrics."""
    variant: str
    total_duration_ms: int = 0
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    ats_score: Optional[int] = None


@router.post("/{arena_id}/metrics")
async def submit_metrics(
    arena_id: str,
    metrics: MetricsRequest,
    admin: str = Depends(verify_admin),
):
    """Submit metrics for a variant."""
    if metrics.variant not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Variant must be A or B")

    comparison = _get_comparison_or_404(arena_id)
    thread_id = comparison.variant_a_thread_id if metrics.variant == "A" else comparison.variant_b_thread_id

    variant_metrics = VariantMetrics(
        variant=metrics.variant,
        thread_id=thread_id,
        total_duration_ms=metrics.total_duration_ms,
        total_llm_calls=metrics.total_llm_calls,
        total_input_tokens=metrics.total_input_tokens,
        total_output_tokens=metrics.total_output_tokens,
        ats_score=metrics.ats_score,
    )

    get_arena_service().save_metrics(arena_id, metrics.variant, variant_metrics)
    return {"success": True}


@router.get("/{arena_id}/metrics")
async def get_metrics(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Get metrics for both variants of a comparison."""
    _get_comparison_or_404(arena_id)
    metrics = get_arena_service().get_metrics(arena_id)
    return {k: v.model_dump() for k, v in metrics.items()}


@router.delete("/{arena_id}")
async def delete_comparison(
    arena_id: str,
    admin: str = Depends(verify_admin),
):
    """Delete a comparison and clean up memory (prevents memory leaks)."""
    comparison = _get_comparison_or_404(arena_id)

    # Clean up workflow entries
    _workflows.pop(comparison.variant_a_thread_id, None)
    _workflows.pop(comparison.variant_b_thread_id, None)

    # Clean up arena service data
    get_arena_service().cleanup_comparison(arena_id)

    return {"success": True, "message": f"Comparison {arena_id} deleted"}


@router.get("/{arena_id}/export")
async def export_comparison(
    arena_id: str,
    format: str = "json",
    admin: str = Depends(verify_admin),
):
    """Export comparison results as JSON or CSV."""
    if format not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")

    comparison = _get_comparison_or_404(arena_id)
    service = get_arena_service()
    ratings = service.get_ratings(arena_id)
    metrics = service.get_metrics(arena_id)

    export_data = {
        "arena_id": comparison.arena_id,
        "created_at": comparison.created_at,
        "status": comparison.status,
        "variant_a_thread_id": comparison.variant_a_thread_id,
        "variant_b_thread_id": comparison.variant_b_thread_id,
        "ratings": [r.model_dump() for r in ratings],
        "metrics": {k: v.model_dump() for k, v in metrics.items()},
    }

    if format == "json":
        return export_data

    # CSV format - flatten ratings into rows
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(["arena_id", "rating_id", "step", "aspect", "preference", "reason", "rated_by"])

    # Rows
    for rating in ratings:
        writer.writerow([
            comparison.arena_id,
            rating.rating_id,
            rating.step,
            rating.aspect,
            rating.preference,
            rating.reason or "",
            rating.rated_by,
        ])

    csv_content = output.getvalue()
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="arena_{_sanitize_for_filename(arena_id)}.csv"'},
    )


@router.get("/export/analytics")
async def export_analytics(
    format: str = "json",
    admin: str = Depends(verify_admin),
):
    """Export cumulative analytics as JSON or CSV."""
    if format not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")

    service = get_arena_service()
    analytics = service.get_analytics()

    if format == "json":
        return analytics.model_dump()

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)

    # Summary section
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Comparisons", analytics.total_comparisons])
    writer.writerow(["Total Ratings", analytics.total_ratings])
    writer.writerow(["Variant A Wins", analytics.variant_a_wins])
    writer.writerow(["Variant B Wins", analytics.variant_b_wins])
    writer.writerow(["Ties", analytics.ties])
    writer.writerow(["Win Rate A", f"{analytics.win_rate_a:.2%}"])
    writer.writerow(["Win Rate B", f"{analytics.win_rate_b:.2%}"])
    writer.writerow([])

    # By step breakdown
    writer.writerow(["Step", "A Wins", "B Wins", "Ties"])
    for step, counts in analytics.by_step.items():
        writer.writerow([step, counts.get("A", 0), counts.get("B", 0), counts.get("tie", 0)])
    writer.writerow([])

    # By aspect breakdown
    writer.writerow(["Aspect", "A Wins", "B Wins", "Ties"])
    for aspect, counts in analytics.by_aspect.items():
        writer.writerow([aspect, counts.get("A", 0), counts.get("B", 0), counts.get("tie", 0)])

    csv_content = output.getvalue()
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="arena_analytics.csv"'},
    )


def _get_variant_state(thread_id: str) -> dict:
    """Get current state for a variant thread."""
    workflow_data = _workflows.get(thread_id)
    if not workflow_data:
        return {"status": "not_found"}

    state = workflow_data.get("state", {})
    return {
        "step": state.get("current_step", "unknown"),
        "interrupted": workflow_data.get("interrupted", False),
        "progress": get_realtime_progress(thread_id)[-5:],  # Last 5 progress messages
    }


@router.get("/{arena_id}/stream")
async def stream_arena_events(
    arena_id: str,
    token: Optional[str] = None,
):
    """Stream real-time progress for both variants via SSE.

    Authentication: Use POST /{arena_id}/sse-token to get a short-lived token,
    then pass it as ?token=xxx. The token is single-use and valid for 2 minutes.

    Sends events for:
    - step_update: When either variant changes step
    - progress: Real-time progress messages from workflow nodes
    - sync: When both variants reach the same sync point
    - complete: When comparison finishes
    """
    _verify_sse_token_or_401(token, arena_id)

    comparison = _get_comparison_or_404(arena_id)

    async def event_generator():
        last_a_step = None
        last_b_step = None
        last_a_progress_len = 0
        last_b_progress_len = 0
        start_time = time.monotonic()
        max_duration_seconds = 3600  # 1 hour max connection

        while True:
            try:
                # Timeout check (1 hour max) - using monotonic time for reliability
                if (time.monotonic() - start_time) > max_duration_seconds:
                    yield f"data: {json.dumps({'type': 'timeout', 'message': 'Connection timeout after 1 hour'})}\n\n"
                    break

                # Get current state for both variants
                state_a = _get_variant_state(comparison.variant_a_thread_id)
                state_b = _get_variant_state(comparison.variant_b_thread_id)

                now = datetime.now().isoformat()

                # Check for step changes
                if state_a["step"] != last_a_step:
                    yield f"data: {json.dumps({'type': 'step_update', 'variant': 'A', 'step': state_a['step'], 'timestamp': now})}\n\n"
                    last_a_step = state_a["step"]

                if state_b["step"] != last_b_step:
                    yield f"data: {json.dumps({'type': 'step_update', 'variant': 'B', 'step': state_b['step'], 'timestamp': now})}\n\n"
                    last_b_step = state_b["step"]

                # Send new progress messages
                a_progress = state_a.get("progress", [])
                b_progress = state_b.get("progress", [])

                if len(a_progress) > last_a_progress_len:
                    for msg in a_progress[last_a_progress_len:]:
                        yield f"data: {json.dumps({'type': 'progress', 'variant': 'A', **msg})}\n\n"
                    last_a_progress_len = len(a_progress)

                if len(b_progress) > last_b_progress_len:
                    for msg in b_progress[last_b_progress_len:]:
                        yield f"data: {json.dumps({'type': 'progress', 'variant': 'B', **msg})}\n\n"
                    last_b_progress_len = len(b_progress)

                # Check for sync point (both interrupted at same step)
                if (state_a["interrupted"] and state_b["interrupted"] and
                    state_a["step"] == state_b["step"]):
                    yield f"data: {json.dumps({'type': 'sync', 'step': state_a['step'], 'timestamp': now})}\n\n"

                # Check for completion
                a_done = state_a["step"] in ["completed", "error", "not_found"]
                b_done = state_b["step"] in ["completed", "error", "not_found"]

                if a_done and b_done:
                    yield f"data: {json.dumps({'type': 'complete', 'variant_a': state_a['step'], 'variant_b': state_b['step'], 'timestamp': now})}\n\n"
                    break

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"SSE error for arena {arena_id}: {e}", exc_info=True)
                # Sanitize error message to avoid leaking internal details
                yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
