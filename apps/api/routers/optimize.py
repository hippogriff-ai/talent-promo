"""API router for resume optimization workflow.

Updated for LangGraph 1.0+ patterns:
- Uses Command(resume=value) to resume from interrupt()
- Uses astream_events for efficient streaming
- Includes interrupt payload in status responses
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Header, Cookie
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from langgraph.types import Command

from workflow.graph import get_workflow, create_initial_state
from workflow.nodes.editor import get_editor_suggestion, regenerate_section
from workflow.nodes.export import export_resume
from validators import validate_urls, validate_linkedin_url, validate_job_url
from services.thread_metadata import get_metadata_service, ThreadMetadataService
from middleware.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimize", tags=["resume-optimization"])


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO timestamp, handling Z suffix for UTC.

    Args:
        timestamp_str: ISO format timestamp string (e.g., "2025-01-11T12:00:00Z")

    Returns:
        Parsed datetime or None if invalid/empty.
    """
    if not timestamp_str:
        return None
    try:
        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ============================================================================
# Request/Response Models
# ============================================================================

class StartWorkflowRequest(BaseModel):
    """Request to start a new workflow."""
    linkedin_url: Optional[str] = None
    job_url: Optional[str] = None
    resume_text: Optional[str] = None  # If uploaded instead of LinkedIn
    job_text: Optional[str] = None  # If pasted instead of job URL
    user_preferences: Optional[dict] = None  # User's writing style preferences


class WorkflowProgressStep(BaseModel):
    """Progress status for a workflow step."""
    status: str  # "pending", "in_progress", "completed", "error"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ProgressMessage(BaseModel):
    """A single progress message for real-time UI updates."""
    timestamp: str
    phase: str  # "ingest", "research", "analysis", etc.
    message: str  # User-friendly message
    detail: str = ""  # Additional detail (e.g., search query)


class WorkflowStateResponse(BaseModel):
    """Response with current workflow state."""
    thread_id: str
    current_step: str
    sub_step: Optional[str] = None  # Granular progress within a step
    status: str  # "running", "waiting_input", "completed", "error"
    pending_question: Optional[str] = None
    qa_round: int = 0
    progress: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    # Detailed progress messages (for real-time UI updates)
    progress_messages: list[ProgressMessage] = Field(default_factory=list)

    # Interrupt payload (for progressive information disclosure)
    interrupt_payload: Optional[dict] = None

    # Q&A history (always included when in qa step)
    qa_history: list[dict] = Field(default_factory=list)

    # Discovery data
    discovery_prompts: list[dict] = Field(default_factory=list)
    discovery_messages: list[dict] = Field(default_factory=list)
    discovered_experiences: list[dict] = Field(default_factory=list)
    discovery_confirmed: bool = False
    discovery_exchanges: int = 0

    # Data snapshots (optional, only included when requested)
    user_profile: Optional[dict] = None
    job_posting: Optional[dict] = None
    # Raw markdown for display/editing
    profile_markdown: Optional[str] = None
    job_markdown: Optional[str] = None
    research: Optional[dict] = None
    gap_analysis: Optional[dict] = None
    resume_html: Optional[str] = None


class AnswerRequest(BaseModel):
    """Request to submit an answer to Q&A."""
    text: str


class EditorActionRequest(BaseModel):
    """Request for AI editor assistance."""
    action: str  # "improve", "add_keywords", "quantify", "shorten", "rewrite", "fix_tone", "custom"
    selected_text: str
    instructions: Optional[str] = None  # For custom action


class RegenerateSectionRequest(BaseModel):
    """Request to regenerate a resume section."""
    section: str  # "summary", "experience", "skills", "education"
    current_content: str


class UpdateResumeRequest(BaseModel):
    """Request to update the resume content."""
    html_content: str


class ExportRequest(BaseModel):
    """Request to export resume."""
    format: str = "docx"  # "docx" or "pdf"


# ============================================================================
# Workflow Storage with Checkpointer Recovery
# ============================================================================

# ============================================================================
# Real-time Progress Store (imported from workflow.progress)
# ============================================================================

from workflow.progress import (
    current_thread_id,
    get_realtime_progress,
    clear_realtime_progress,
)


_workflows: dict[str, dict] = {}


def _get_workflow_data(thread_id: str) -> dict:
    """Get workflow data from storage, recovering from checkpointer if needed.

    This enables workflow persistence across server restarts:
    1. First checks in-memory cache
    2. If not found, queries LangGraph checkpointer for persisted state
    3. Rebuilds workflow metadata from checkpointed state
    """
    # Check in-memory cache first
    if thread_id in _workflows:
        return _workflows[thread_id]

    # Try to recover from LangGraph checkpointer
    try:
        workflow = get_workflow()
        config = {"configurable": {"thread_id": thread_id}}

        # Query the checkpointer for this thread's state
        graph_state = workflow.get_state(config)

        if graph_state and graph_state.values:
            # Rebuild workflow data from checkpointed state
            state_values = dict(graph_state.values)

            # Check for pending interrupts
            has_interrupt = False
            interrupt_value = None
            if hasattr(graph_state, 'tasks') and graph_state.tasks:
                has_interrupt = True
                for task in graph_state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        interrupt_value = task.interrupts[0].value if task.interrupts else None
                        break

            workflow_data = {
                "state": state_values,
                "config": config,
                "created_at": state_values.get("created_at", datetime.now().isoformat()),
                "interrupted": has_interrupt,
                "interrupt_value": interrupt_value,
                "recovered_from_checkpoint": True,
            }

            # Cache it for future requests
            _workflows[thread_id] = workflow_data
            logger.info(f"Recovered workflow {thread_id} from checkpointer")
            return workflow_data

    except Exception as e:
        logger.debug(f"Could not recover workflow {thread_id} from checkpointer: {e}")

    raise HTTPException(status_code=404, detail="Workflow not found")


def _save_workflow_data(thread_id: str, data: dict):
    """Save workflow data to in-memory cache.

    Note: The actual state persistence is handled by LangGraph's checkpointer.
    This cache is for quick access to workflow metadata.
    """
    _workflows[thread_id] = data


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/start", response_model=WorkflowStateResponse)
async def start_workflow(
    request: StartWorkflowRequest,
    x_forwarded_for: Optional[str] = Header(None),
    x_real_ip: Optional[str] = Header(None),
):
    """Start a new resume optimization workflow.

    Rate limited by IP address to prevent abuse.

    Provide either:
    - linkedin_url: LinkedIn profile URL
    - resume_text: Raw resume text (if uploaded)

    Plus either:
    - job_url: URL to the job posting
    - job_text: Pasted job description (fallback if URL scraping fails)
    """
    # Get client IP from headers (for proxied requests) or fall back to generic
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else (x_real_ip or "unknown")

    # Check rate limit (3 requests per IP per day)
    allowed, remaining, reset_time = check_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again after {reset_time}.",
            headers={"Retry-After": str(reset_time), "X-RateLimit-Remaining": "0"}
        )

    # Validate URLs (job_url is optional if job_text is provided)
    is_valid, errors = validate_urls(
        linkedin_url=request.linkedin_url,
        job_url=request.job_url or "",
        resume_text=request.resume_text,
        job_text=request.job_text,
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="; ".join(errors)
        )

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"Starting new workflow: {thread_id}")

    # Create initial state
    initial_state = create_initial_state(
        linkedin_url=request.linkedin_url,
        job_url=request.job_url,
        uploaded_resume_text=request.resume_text,
        uploaded_job_text=request.job_text,
        user_preferences=request.user_preferences,
    )

    # Store workflow metadata
    _save_workflow_data(thread_id, {
        "state": initial_state,
        "config": config,
        "created_at": datetime.now().isoformat(),
    })

    # Create thread metadata in Postgres for cleanup tracking
    metadata_service = get_metadata_service()
    metadata_service.create_thread(thread_id, workflow_step="ingest")

    # Start workflow in background
    asyncio.create_task(_run_workflow(thread_id))

    return WorkflowStateResponse(
        thread_id=thread_id,
        current_step="ingest",
        status="running",
        progress={"ingest": "in_progress"},
    )


async def _run_workflow(thread_id: str):
    """Run the workflow asynchronously.

    Uses async workflow methods with MemorySaver or async-compatible checkpointers.
    For production persistence, use PostgresSaver which has async support.
    """
    # Set context variable so nodes can emit real-time progress
    token = current_thread_id.set(thread_id)

    try:
        workflow_data = _get_workflow_data(thread_id)
        config = workflow_data["config"]
        initial_state = workflow_data["state"]

        workflow = get_workflow()

        # Use async invoke for async workflow nodes
        result = await workflow.ainvoke(initial_state, config)

        # Check if there's a pending interrupt by examining the graph state
        graph_state = await workflow.aget_state(config)

        # Check for pending tasks (indicates interrupt)
        has_interrupt = False
        interrupt_value = None

        if graph_state and hasattr(graph_state, 'tasks') and graph_state.tasks:
            has_interrupt = True
            for task in graph_state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    interrupt_value = task.interrupts[0].value if task.interrupts else None
                    break

        # Update stored state
        workflow_data["state"] = result if isinstance(result, dict) else dict(graph_state.values) if graph_state else {}
        workflow_data["interrupted"] = has_interrupt
        workflow_data["interrupt_value"] = interrupt_value
        _save_workflow_data(thread_id, workflow_data)

        if has_interrupt:
            logger.info(f"Workflow {thread_id} interrupted for user input")
        else:
            logger.info(f"Workflow {thread_id} reached step: {result.get('current_step') if isinstance(result, dict) else 'unknown'}")

    except Exception as e:
        # Check if this is a GraphInterrupt (from interrupt() function)
        if "GraphInterrupt" in type(e).__name__ or hasattr(e, '__interrupt__'):
            logger.info(f"Workflow {thread_id} interrupted for user input (exception)")

            workflow_data = _get_workflow_data(thread_id)
            config = workflow_data["config"]

            # Get the interrupt value from the graph state
            workflow = get_workflow()
            state = await workflow.aget_state(config)

            workflow_data = _workflows.get(thread_id, {})
            if state and state.values:
                workflow_data["state"] = dict(state.values)

            # Mark as interrupted
            workflow_data["interrupted"] = True
            workflow_data["interrupt_value"] = getattr(e, 'value', None)
            _save_workflow_data(thread_id, workflow_data)
        else:
            import traceback
            logger.error(f"Workflow {thread_id} error: {e}\n{traceback.format_exc()}")
            workflow_data = _workflows.get(thread_id, {})
            if "state" in workflow_data:
                workflow_data["state"]["errors"] = [
                    *workflow_data["state"].get("errors", []),
                    str(e)
                ]
                workflow_data["state"]["current_step"] = "error"
                _save_workflow_data(thread_id, workflow_data)
    finally:
        # Reset context variable and clear real-time progress
        current_thread_id.reset(token)
        clear_realtime_progress(thread_id)


@router.get("/status/{thread_id}", response_model=WorkflowStateResponse)
async def get_workflow_status(thread_id: str, include_data: bool = False):
    """Get current workflow state.

    Args:
        thread_id: Workflow thread ID
        include_data: If true, include full data (profile, job, research, etc.)
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Update last_accessed timestamp in thread metadata
    metadata_service = get_metadata_service()
    current_step = state.get("current_step", "unknown")
    metadata_service.update_last_accessed(thread_id, workflow_step=current_step)
    is_interrupted = workflow_data.get("interrupted", False)

    # Determine status
    current_step = state.get("current_step", "unknown")
    status = "running"

    if current_step == "completed":
        status = "completed"
    elif current_step == "error":
        status = "error"
    elif is_interrupted:
        # Workflow is paused at an interrupt() call
        status = "waiting_input"

    # Get interrupt payload (for progressive information disclosure)
    interrupt_payload = None
    pending_question = None

    if is_interrupted:
        # Get interrupt payload from pending_interrupt or state
        interrupt_payload = state.get("pending_interrupt")

        # Also check for the interrupt value directly
        if not interrupt_payload:
            interrupt_payload = workflow_data.get("interrupt_value")

        # Extract question from payload
        if interrupt_payload and isinstance(interrupt_payload, dict):
            pending_question = interrupt_payload.get("message")

    # Build progress dict
    progress = _compute_progress(state)

    # Get progress messages - merge real-time progress with state progress
    # Real-time progress updates DURING node execution, state progress updates AFTER
    state_progress = state.get("progress_messages", [])
    realtime_progress = get_realtime_progress(thread_id)

    # Use real-time progress if available (more current), else fall back to state
    progress_messages = realtime_progress if realtime_progress else state_progress

    response = WorkflowStateResponse(
        thread_id=thread_id,
        current_step=current_step,
        sub_step=state.get("sub_step"),
        status=status,
        pending_question=pending_question,
        qa_round=state.get("qa_round", 0),
        progress=progress,
        errors=state.get("errors", []),
        progress_messages=progress_messages,
        interrupt_payload=interrupt_payload,
        qa_history=state.get("qa_history", []),  # Always include Q&A history
        # Discovery data - always include
        discovery_prompts=state.get("discovery_prompts", []),
        discovery_messages=state.get("discovery_messages", []),
        discovered_experiences=state.get("discovered_experiences", []),
        discovery_confirmed=state.get("discovery_confirmed", False),
        discovery_exchanges=state.get("discovery_exchanges", 0),
    )

    # Include full data if requested
    if include_data:
        response.user_profile = state.get("user_profile")
        response.job_posting = state.get("job_posting")
        # Raw markdown for display/editing
        response.profile_markdown = state.get("profile_markdown")
        response.job_markdown = state.get("job_markdown")
        response.research = state.get("research")
        response.gap_analysis = state.get("gap_analysis")
        response.resume_html = state.get("resume_html")

    return response


def _compute_progress(state: dict) -> dict[str, str]:
    """Compute step progress from state."""
    current = state.get("current_step", "ingest")
    steps = ["ingest", "research", "analysis", "discovery", "qa", "draft", "editor", "completed"]

    progress = {}
    current_found = False

    for step in steps:
        if step == current:
            progress[step] = "in_progress"
            current_found = True
        elif not current_found:
            progress[step] = "completed"
        else:
            progress[step] = "pending"

    return progress


@router.post("/{thread_id}/answer", response_model=WorkflowStateResponse)
async def submit_answer(thread_id: str, answer: AnswerRequest):
    """Submit answer to Q&A question and resume workflow.

    Uses Command(resume=value) to continue from the interrupt() call.
    The answer is passed directly to where interrupt() was called.
    """
    workflow_data = _get_workflow_data(thread_id)

    if not workflow_data.get("interrupted"):
        raise HTTPException(
            status_code=400,
            detail="Workflow is not waiting for input"
        )

    # Store the answer to resume with and update timestamp
    workflow_data["resume_value"] = answer.text
    workflow_data["interrupted"] = False
    if "state" in workflow_data:
        workflow_data["state"]["updated_at"] = datetime.now().isoformat()
    _save_workflow_data(thread_id, workflow_data)

    logger.info(f"Answer submitted for {thread_id}, resuming workflow")

    # Resume workflow with the answer and wait for it to complete
    # This ensures the response includes updated state after processing
    await _resume_workflow(thread_id, answer.text)

    return await get_workflow_status(thread_id)


async def _resume_workflow(thread_id: str, resume_value: Any = None):
    """Resume the workflow after user input.

    Uses async workflow methods for MemorySaver compatibility.
    For async workflow nodes, we must use ainvoke/aget_state.
    """
    try:
        workflow_data = _get_workflow_data(thread_id)
        config = workflow_data["config"]

        workflow = get_workflow()

        # Resume with Command(resume=value) - async version
        result = await workflow.ainvoke(Command(resume=resume_value), config)

        # Check if there's another pending interrupt
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

        if has_interrupt:
            logger.info(f"Workflow {thread_id} resumed but hit another interrupt")
        else:
            logger.info(f"Workflow {thread_id} resumed, now at: {result.get('current_step') if isinstance(result, dict) else 'unknown'}")

    except Exception as e:
        # Check if this is another interrupt (exception-based)
        if "GraphInterrupt" in type(e).__name__ or hasattr(e, '__interrupt__'):
            logger.info(f"Workflow {thread_id} interrupted again (exception)")

            workflow_data = _get_workflow_data(thread_id)
            config = workflow_data["config"]

            workflow = get_workflow()
            state = await workflow.aget_state(config)

            workflow_data = _workflows.get(thread_id, {})
            if state and state.values:
                workflow_data["state"] = dict(state.values)

            workflow_data["interrupted"] = True
            workflow_data["interrupt_value"] = getattr(e, 'value', None)
            _save_workflow_data(thread_id, workflow_data)
        else:
            logger.error(f"Workflow resume error for {thread_id}: {e}")


class DiscoveryConfirmRequest(BaseModel):
    """Request to confirm discovery completion."""
    confirmed: bool = True


@router.post("/{thread_id}/discovery/confirm", response_model=WorkflowStateResponse)
async def confirm_discovery(thread_id: str, request: DiscoveryConfirmRequest):
    """Confirm discovery is complete and proceed to drafting.

    Requires at least 3 conversation exchanges before allowing confirmation.
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Check minimum exchanges
    exchanges = state.get("discovery_exchanges", 0)
    if exchanges < 3:
        raise HTTPException(
            status_code=400,
            detail=f"At least 3 conversation exchanges required. Current: {exchanges}"
        )

    # Also verify there are actual messages in the conversation
    messages = state.get("discovery_messages", [])
    if len(messages) < 6:  # 3 exchanges = 6 messages (3 questions + 3 answers)
        raise HTTPException(
            status_code=400,
            detail="Discovery conversation incomplete. Please answer more questions."
        )

    # Update state
    state["discovery_confirmed"] = request.confirmed
    state["updated_at"] = datetime.now().isoformat()
    workflow_data["state"] = state

    # Mark as not interrupted so workflow can continue
    workflow_data["interrupted"] = False
    _save_workflow_data(thread_id, workflow_data)

    logger.info(f"Discovery confirmed for {thread_id}, proceeding to drafting")

    # Resume workflow
    asyncio.create_task(_resume_workflow(thread_id, "discovery_complete"))

    return await get_workflow_status(thread_id)


class UpdateResearchDataRequest(BaseModel):
    """Request to update user profile or job posting data."""
    user_profile: Optional[dict] = None
    job_posting: Optional[dict] = None


@router.patch("/{thread_id}/research/data")
async def update_research_data(thread_id: str, request: UpdateResearchDataRequest):
    """Update user profile and/or job posting data.

    Allows users to correct parsing errors in the research phase.
    Only updates fields that are provided (partial update).
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    if request.user_profile is not None:
        existing_profile = state.get("user_profile", {}) or {}
        if isinstance(existing_profile, dict):
            # Merge updates into existing profile
            state["user_profile"] = {**existing_profile, **request.user_profile}
        else:
            state["user_profile"] = request.user_profile

    if request.job_posting is not None:
        existing_job = state.get("job_posting", {}) or {}
        if isinstance(existing_job, dict):
            # Merge updates into existing job
            state["job_posting"] = {**existing_job, **request.job_posting}
        else:
            state["job_posting"] = request.job_posting

    state["updated_at"] = datetime.now().isoformat()
    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    logger.info(f"Research data updated for {thread_id}")

    return {
        "success": True,
        "user_profile": state.get("user_profile"),
        "job_posting": state.get("job_posting"),
    }


@router.get("/{thread_id}/stream")
async def stream_events(thread_id: str):
    """Stream workflow events via Server-Sent Events (SSE).

    Uses astream_events for efficient LangGraph streaming when available,
    falls back to polling for status updates.
    """
    workflow_data = _get_workflow_data(thread_id)

    async def event_generator():
        last_step = None
        last_interrupted = None

        while True:
            try:
                current_data = _workflows.get(thread_id)
                if not current_data:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Workflow not found'})}\n\n"
                    break

                state = current_data.get("state", {})
                current_step = state.get("current_step")
                is_interrupted = current_data.get("interrupted", False)

                # Send update if step changed
                if current_step != last_step:
                    event = {
                        "type": "step_update",
                        "step": current_step,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # Include working context summary
                    working_ctx = state.get("working_context")
                    if working_ctx:
                        event["context"] = {
                            "target_role": working_ctx.get("target_role", ""),
                            "target_company": working_ctx.get("target_company", ""),
                        }

                    yield f"data: {json.dumps(event)}\n\n"
                    last_step = current_step

                # Send interrupt notification
                if is_interrupted and is_interrupted != last_interrupted:
                    interrupt_payload = state.get("pending_interrupt") or current_data.get("interrupt_value")

                    event = {
                        "type": "interrupt",
                        "step": current_step,
                        "timestamp": datetime.now().isoformat(),
                    }

                    if interrupt_payload and isinstance(interrupt_payload, dict):
                        event["payload"] = {
                            "message": interrupt_payload.get("message"),
                            "interrupt_type": interrupt_payload.get("interrupt_type"),
                            "round": interrupt_payload.get("round", 0),
                            "max_rounds": interrupt_payload.get("max_rounds", 10),
                            "suggestions": interrupt_payload.get("suggestions", []),
                            "can_skip": interrupt_payload.get("can_skip", True),
                        }

                    yield f"data: {json.dumps(event)}\n\n"
                    last_interrupted = is_interrupted

                # Check for completion
                if current_step in ["completed", "error"]:
                    final_event = {
                        "type": "complete",
                        "step": current_step,
                        "timestamp": datetime.now().isoformat(),
                    }

                    if current_step == "error":
                        final_event["errors"] = state.get("errors", [])

                    yield f"data: {json.dumps(final_event)}\n\n"
                    break

                await asyncio.sleep(0.5)  # Faster polling for better UX

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
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


@router.get("/{thread_id}/stream/live")
async def stream_live_events(thread_id: str):
    """Stream live workflow events using astream_events.

    This provides more granular events during active workflow execution,
    including LLM token streaming and node transitions.
    """
    workflow_data = _get_workflow_data(thread_id)
    config = workflow_data.get("config", {})

    async def live_event_generator():
        workflow = get_workflow()

        try:
            # Use astream_events for granular streaming
            async for event in workflow.astream_events(
                input=None,  # Use checkpointed state
                config=config,
                version="v2",
            ):
                event_kind = event.get("event", "")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # Filter and transform events for frontend
                if event_kind == "on_chain_start":
                    yield f"data: {json.dumps({'type': 'node_start', 'node': event_name})}\n\n"

                elif event_kind == "on_chain_end":
                    yield f"data: {json.dumps({'type': 'node_end', 'node': event_name})}\n\n"

                elif event_kind == "on_chat_model_stream":
                    # Stream LLM tokens
                    chunk = event_data.get("chunk", {})
                    content = getattr(chunk, "content", "")
                    if content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                elif event_kind == "on_tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': event_name})}\n\n"

                elif event_kind == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': event_name})}\n\n"

        except Exception as e:
            if "GraphInterrupt" in type(e).__name__:
                yield f"data: {json.dumps({'type': 'interrupt', 'message': 'Waiting for input'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        live_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/editor/assist")
async def editor_assist(thread_id: str, action: EditorActionRequest):
    """Get AI assistance for editing a selection in the resume editor."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Handle None values by defaulting to empty dict
    job_posting = state.get("job_posting") or {}
    gap_analysis = state.get("gap_analysis") or {}

    job_context = {
        "title": job_posting.get("title", "") if isinstance(job_posting, dict) else "",
        "company": job_posting.get("company_name", "") if isinstance(job_posting, dict) else "",
        "keywords": gap_analysis.get("keywords_to_include", []) if isinstance(gap_analysis, dict) else [],
    }

    result = await get_editor_suggestion(
        action=action.action,
        selected_text=action.selected_text,
        full_resume=state.get("resume_html", ""),
        job_context=job_context,
        instructions=action.instructions,
    )

    return result


@router.post("/{thread_id}/editor/regenerate")
async def regenerate_resume_section(thread_id: str, request: RegenerateSectionRequest):
    """Regenerate a specific resume section from scratch."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    result = await regenerate_section(
        section=request.section,
        current_content=request.current_content,
        user_profile=state.get("user_profile", {}),
        job_posting=state.get("job_posting", {}),
        gap_analysis=state.get("gap_analysis", {}),
    )

    return result


def _sanitize_html(html_content: str) -> str:
    """Sanitize HTML content to remove potentially dangerous elements.

    Removes script tags, event handlers, and other XSS vectors while
    preserving safe HTML formatting for resume display.
    """
    import re

    # Remove script tags and their content
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<script[^>]*/?>', '', html_content, flags=re.IGNORECASE)

    # Remove style tags and their content (could contain expressions)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

    # Remove event handlers (onclick, onerror, onload, etc.)
    html_content = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'\s+on\w+\s*=\s*[^\s>]+', '', html_content, flags=re.IGNORECASE)

    # Remove javascript: URLs
    html_content = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', 'href=""', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'src\s*=\s*["\']javascript:[^"\']*["\']', 'src=""', html_content, flags=re.IGNORECASE)

    # Remove data: URLs in src (can be used for XSS)
    html_content = re.sub(r'src\s*=\s*["\']data:[^"\']*["\']', 'src=""', html_content, flags=re.IGNORECASE)

    # Remove iframe, object, embed tags
    html_content = re.sub(r'<(iframe|object|embed)[^>]*>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<(iframe|object|embed)[^>]*/>', '', html_content, flags=re.IGNORECASE)

    return html_content


@router.post("/{thread_id}/editor/update")
async def update_resume(thread_id: str, request: UpdateResumeRequest):
    """Update the resume content (save user's edits)."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Sanitize HTML to prevent XSS
    sanitized_html = _sanitize_html(request.html_content)

    state["resume_html"] = sanitized_html
    state["resume_final"] = sanitized_html
    state["updated_at"] = datetime.now().isoformat()

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {"success": True, "message": "Resume updated"}


# ============================================================================
# Drafting Stage Endpoints
# ============================================================================


class SuggestionActionRequest(BaseModel):
    """Request to act on a suggestion."""
    suggestion_id: str
    action: str  # "accept" or "decline"


class DirectEditRequest(BaseModel):
    """Request for a direct edit."""
    location: str
    original_text: str
    new_text: str


class ManualSaveRequest(BaseModel):
    """Request for manual save."""
    html_content: str


class RestoreVersionRequest(BaseModel):
    """Request to restore a version."""
    version: str


class ApproveDraftRequest(BaseModel):
    """Request to approve the draft."""
    approved: bool = True


@router.get("/{thread_id}/drafting/state")
async def get_drafting_state(thread_id: str):
    """Get current drafting state including suggestions and versions."""
    from workflow.nodes.drafting import validate_resume

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Validate current draft
    validation = None
    if state.get("resume_html"):
        validation = validate_resume(state.get("resume_html"))

    return {
        "thread_id": thread_id,
        "resume_html": state.get("resume_html"),
        "suggestions": state.get("draft_suggestions", []),
        "versions": state.get("draft_versions", []),
        "current_version": state.get("draft_current_version"),
        "change_log": state.get("draft_change_log", []),
        "draft_approved": state.get("draft_approved", False),
        "validation": validation.model_dump() if validation else None,
    }


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use in a filename.

    Removes characters that are invalid on Windows or could cause issues.
    Returns 'resume' if the result would be empty.
    """
    name = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove Windows-invalid chars
    name = re.sub(r'[^\w\s-]', '', name)  # Keep only word chars, spaces, hyphens
    return name.replace(" ", "_").strip("_") or "resume"


def _get_export_filename_base(state: dict) -> str:
    """Get sanitized filename base from user profile."""
    user_profile = state.get("user_profile") or {}
    name = user_profile.get("name", "resume") if isinstance(user_profile, dict) else "resume"
    return f"{_sanitize_filename(name)}_optimized"


def _add_version_and_prune(
    state: dict,
    trigger: str,
    description: str,
    html_content: str,
    change_log_entry: Optional[dict] = None,
) -> str:
    """Add a new version to state and prune old versions.

    Creates a new version entry, adds it to the versions list, and
    prunes to keep only the last 5 versions while preserving v1.0.

    Returns the new version number.
    """
    from workflow.nodes.drafting import increment_version

    current_version = state.get("draft_current_version", "1.0")
    new_version = increment_version(current_version)

    version_entry = {
        "version": new_version,
        "html_content": html_content,
        "trigger": trigger,
        "description": description,
        "change_log": [change_log_entry] if change_log_entry else [],
        "created_at": datetime.now().isoformat(),
    }

    versions = state.get("draft_versions", [])
    versions.append(version_entry)

    # Keep only last 5 versions, but always preserve version 1.0 (initial)
    if len(versions) > 5:
        initial_version = next((v for v in versions if v.get("version") == "1.0"), None)
        versions = versions[-5:]
        if initial_version and initial_version not in versions:
            versions = [initial_version] + versions[-4:]

    state["draft_versions"] = versions
    state["draft_current_version"] = new_version
    state["updated_at"] = datetime.now().isoformat()

    return new_version


@router.post("/{thread_id}/drafting/suggestion")
async def handle_suggestion(thread_id: str, request: SuggestionActionRequest):
    """Accept or decline a suggestion."""
    import uuid

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    suggestions = state.get("draft_suggestions", [])
    suggestion = next(
        (s for s in suggestions if s.get("id") == request.suggestion_id),
        None
    )

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Suggestion already resolved")

    # Update suggestion status
    suggestion["status"] = "accepted" if request.action == "accept" else "declined"
    suggestion["resolved_at"] = datetime.now().isoformat()

    # If accepted, apply the change to resume HTML
    resume_html = state.get("resume_html", "")
    if request.action == "accept" and suggestion.get("original_text"):
        resume_html = resume_html.replace(
            suggestion["original_text"],
            suggestion["proposed_text"]
        )
        state["resume_html"] = resume_html

    # Create change log entry
    change_entry = {
        "id": f"chg_{uuid.uuid4().hex[:8]}",
        "location": suggestion.get("location", ""),
        "change_type": request.action,
        "original_text": suggestion.get("original_text"),
        "new_text": suggestion.get("proposed_text") if request.action == "accept" else None,
        "suggestion_id": request.suggestion_id,
        "timestamp": datetime.now().isoformat(),
    }

    state.setdefault("draft_change_log", []).append(change_entry)
    state["draft_suggestions"] = suggestions

    action_label = "Accepted" if request.action == "accept" else "Declined"
    new_version = _add_version_and_prune(
        state,
        trigger=request.action,
        description=f"{action_label} suggestion: {suggestion.get('rationale', '')[:50]}...",
        html_content=resume_html,
        change_log_entry=change_entry,
    )

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "version": new_version,
        "suggestion_status": suggestion["status"],
    }


@router.post("/{thread_id}/drafting/edit")
async def handle_direct_edit(thread_id: str, request: DirectEditRequest):
    """Handle a direct edit from the user."""
    import uuid

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    resume_html = state.get("resume_html", "")

    # Apply the edit - return error if original text not found
    if request.original_text not in resume_html:
        raise HTTPException(
            status_code=400,
            detail="Edit not applied: original text not found in resume"
        )

    resume_html = resume_html.replace(request.original_text, request.new_text)
    state["resume_html"] = resume_html

    # Create change log entry
    change_entry = {
        "id": f"chg_{uuid.uuid4().hex[:8]}",
        "location": request.location,
        "change_type": "edit",
        "original_text": request.original_text,
        "new_text": request.new_text,
        "suggestion_id": None,
        "timestamp": datetime.now().isoformat(),
    }

    state.setdefault("draft_change_log", []).append(change_entry)

    new_version = _add_version_and_prune(
        state,
        trigger="edit",
        description=f"Manual edit at {request.location}",
        html_content=resume_html,
        change_log_entry=change_entry,
    )

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "version": new_version,
    }


@router.post("/{thread_id}/drafting/save")
async def handle_manual_save(thread_id: str, request: ManualSaveRequest):
    """Handle manual save (creates a new version)."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    state["resume_html"] = request.html_content

    new_version = _add_version_and_prune(
        state,
        trigger="manual_save",
        description="Manual save",
        html_content=request.html_content,
    )

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "version": new_version,
        "message": f"Saved as v{new_version}",
    }


@router.post("/{thread_id}/drafting/restore")
async def restore_version(thread_id: str, request: RestoreVersionRequest):
    """Restore a previous version."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    versions = state.get("draft_versions", [])
    target_version = next(
        (v for v in versions if v.get("version") == request.version),
        None
    )

    if not target_version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Restore content
    state["resume_html"] = target_version["html_content"]

    new_version = _add_version_and_prune(
        state,
        trigger="restore",
        description=f"Restored from v{request.version}",
        html_content=target_version["html_content"],
    )

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "version": new_version,
        "restored_from": request.version,
    }


@router.get("/{thread_id}/drafting/versions")
async def get_versions(thread_id: str):
    """Get version history."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    return {
        "versions": state.get("draft_versions", []),
        "current_version": state.get("draft_current_version"),
    }


@router.post("/{thread_id}/drafting/approve")
async def approve_draft(thread_id: str, request: ApproveDraftRequest):
    """Approve the draft and enable export."""
    from workflow.nodes.drafting import validate_resume

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Check all suggestions are resolved
    suggestions = state.get("draft_suggestions", [])
    pending = [s for s in suggestions if s.get("status") == "pending"]

    if pending:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: {len(pending)} suggestions still pending"
        )

    # Validate resume
    resume_html = state.get("resume_html", "")
    validation = validate_resume(resume_html)

    if not validation.valid:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {'; '.join(validation.errors)}"
        )

    # Mark as approved
    state["draft_approved"] = request.approved
    state["resume_final"] = resume_html
    state["updated_at"] = datetime.now().isoformat()

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "draft_approved": request.approved,
        "validation": validation.model_dump(),
    }


# ============================================================================
# Export Stage Endpoints
# ============================================================================


class ExportStartRequest(BaseModel):
    """Request to start export workflow."""
    pass


@router.post("/{thread_id}/export/start")
async def start_export(thread_id: str, request: ExportStartRequest = None):
    """Start the export workflow.

    Requires draft to be approved.
    """
    from workflow.nodes.export import (
        optimize_for_ats,
        analyze_ats_compatibility,
        generate_linkedin_suggestions,
        _extract_job_keywords,
    )
    from workflow.state import ATSReport, LinkedInSuggestion, ExportOutput

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Validate draft is approved
    if not state.get("draft_approved"):
        raise HTTPException(
            status_code=400,
            detail="Draft must be approved before export"
        )

    resume_html = state.get("resume_final") or state.get("resume_html")
    if not resume_html:
        raise HTTPException(
            status_code=400,
            detail="No resume content to export"
        )

    # Handle None values by defaulting to empty dict
    job_posting = state.get("job_posting") or {}
    gap_analysis = state.get("gap_analysis") or {}
    user_profile = state.get("user_profile") or {}

    # Extract keywords
    job_keywords = _extract_job_keywords(job_posting, gap_analysis)

    # Optimize for ATS
    state["export_step"] = "optimizing"
    optimized_html = optimize_for_ats(resume_html)

    # Analyze ATS compatibility
    state["export_step"] = "analyzing_ats"
    ats_report = analyze_ats_compatibility(optimized_html, job_keywords)

    # Generate LinkedIn suggestions
    state["export_step"] = "generating_linkedin"
    linkedin_suggestions = generate_linkedin_suggestions(
        optimized_html,
        user_profile,
        job_posting
    )

    # Create export output
    export_output = ExportOutput(
        pdf_generated=True,
        txt_generated=True,
        json_generated=True,
        ats_report=ats_report,
        linkedin_suggestions=linkedin_suggestions,
        export_completed=True,
        completed_at=datetime.now().isoformat(),
    )

    # Update state
    state["resume_final"] = optimized_html
    state["export_step"] = "completed"
    state["export_output"] = export_output.model_dump()
    state["ats_report"] = ats_report.model_dump()
    state["linkedin_suggestions"] = linkedin_suggestions.model_dump()
    state["export_completed"] = True
    state["current_step"] = "completed"
    state["updated_at"] = datetime.now().isoformat()

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "export_step": "completed",
        "ats_report": ats_report.model_dump(),
        "linkedin_suggestions": linkedin_suggestions.model_dump(),
    }


@router.get("/{thread_id}/export/state")
async def get_export_state(thread_id: str):
    """Get current export state including ATS report and LinkedIn suggestions."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    return {
        "thread_id": thread_id,
        "export_step": state.get("export_step"),
        "export_completed": state.get("export_completed", False),
        "ats_report": state.get("ats_report"),
        "linkedin_suggestions": state.get("linkedin_suggestions"),
        "draft_approved": state.get("draft_approved", False),
    }


@router.get("/{thread_id}/export/ats-report")
async def get_ats_report(thread_id: str):
    """Get the ATS analysis report."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    ats_report = state.get("ats_report")
    if not ats_report:
        raise HTTPException(
            status_code=404,
            detail="ATS report not available. Run export first."
        )

    # Ensure required fields are present with defaults
    required_fields = {
        "keyword_match_score": 0,
        "formatting_issues": [],
        "recommendations": [],
        "keywords_found": [],
        "keywords_missing": [],
    }
    for field, default in required_fields.items():
        if field not in ats_report:
            ats_report[field] = default

    return ats_report


@router.get("/{thread_id}/export/linkedin")
async def get_linkedin_suggestions(thread_id: str):
    """Get LinkedIn profile suggestions."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    linkedin = state.get("linkedin_suggestions")
    if not linkedin:
        raise HTTPException(
            status_code=404,
            detail="LinkedIn suggestions not available. Run export first."
        )

    # Ensure required fields are present with defaults
    required_fields = {
        "headline": "",
        "summary": "",
        "experience_bullets": [],
    }
    for field, default in required_fields.items():
        if field not in linkedin:
            linkedin[field] = default

    return linkedin


@router.get("/{thread_id}/export/download/{format}")
async def download_export(thread_id: str, format: str):
    """Download resume in specified format (pdf, txt, json, docx)."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    html_content = state.get("resume_final") or state.get("resume_html")
    if not html_content:
        raise HTTPException(
            status_code=400,
            detail="No resume content to export"
        )

    # Validate format
    valid_formats = ["pdf", "txt", "json", "docx"]
    if format.lower() not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}"
        )

    user_profile = state.get("user_profile") or {}
    file_bytes, content_type, filename = export_resume(
        html_content=html_content,
        format=format,
        filename_base=_get_export_filename_base(state),
        user_profile=user_profile if isinstance(user_profile, dict) else {},
    )

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/{thread_id}/export/copy-text")
async def get_plain_text(thread_id: str):
    """Get plain text version for clipboard copy."""
    from workflow.nodes.export import html_to_text

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    html_content = state.get("resume_final") or state.get("resume_html")
    if not html_content:
        raise HTTPException(
            status_code=400,
            detail="No resume content available"
        )

    text_content = html_to_text(html_content)

    return {
        "text": text_content,
    }


@router.post("/{thread_id}/export/re-export")
async def re_export(thread_id: str):
    """Re-run the export workflow with updated content."""
    # This just calls start_export again
    return await start_export(thread_id)


@router.post("/{thread_id}/export")
async def export_resume_endpoint(thread_id: str, request: ExportRequest):
    """Export the final resume to DOCX or PDF (legacy endpoint)."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    html_content = state.get("resume_final") or state.get("resume_html")
    if not html_content:
        raise HTTPException(
            status_code=400,
            detail="No resume content to export"
        )

    user_profile = state.get("user_profile") or {}
    file_bytes, content_type, filename = export_resume(
        html_content=html_content,
        format=request.format,
        filename_base=_get_export_filename_base(state),
        user_profile=user_profile if isinstance(user_profile, dict) else {},
    )

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.get("/{thread_id}/data")
async def get_workflow_data_endpoint(thread_id: str):
    """Get all workflow data including profile, job, research, etc."""
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    return {
        "thread_id": thread_id,
        "current_step": state.get("current_step"),
        "user_profile": state.get("user_profile"),
        "job_posting": state.get("job_posting"),
        "research": state.get("research"),
        "gap_analysis": state.get("gap_analysis"),
        "qa_history": state.get("qa_history", []),
        "resume_html": state.get("resume_html"),
        "created_at": workflow_data.get("created_at"),
        "updated_at": state.get("updated_at"),
    }


@router.delete("/{thread_id}")
async def delete_workflow(thread_id: str):
    """Delete a workflow and its data from memory and Postgres.

    This removes:
    - Memory cache entry
    - Thread metadata record
    - LangGraph checkpoint data (checkpoints, checkpoint_writes, checkpoint_blobs)
    """
    # Check if workflow exists in memory or can be recovered from Postgres
    try:
        _get_workflow_data(thread_id)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Delete from memory cache (using pop for atomic check-and-delete)
    _workflows.pop(thread_id, None)

    # Delete from Postgres (thread metadata and checkpoint data)
    metadata_service = get_metadata_service()
    metadata_service.delete_checkpoint_data(thread_id)
    metadata_service.delete_thread(thread_id)

    logger.info(f"Deleted workflow {thread_id} from memory and Postgres")
    return {"success": True, "message": "Workflow deleted"}


@router.get("/")
async def list_workflows(limit: int = 10, offset: int = 0):
    """List all workflows (from memory cache and checkpointer).

    Returns workflows that can be resumed, including those
    recovered from the persistent checkpointer.

    Args:
        limit: Maximum number of workflows to return (default 10, max 100)
        offset: Number of workflows to skip (for pagination)
    """
    # Enforce reasonable limits
    limit = min(max(1, limit), 100)
    offset = max(0, offset)

    workflows_list = []

    # Get workflows from in-memory cache
    for thread_id, data in _workflows.items():
        state = data.get("state", {})
        workflows_list.append({
            "thread_id": thread_id,
            "current_step": state.get("current_step", "unknown"),
            "status": "waiting_input" if data.get("interrupted") else "running",
            "created_at": data.get("created_at"),
            "user_name": state.get("user_profile", {}).get("name") if state.get("user_profile") else None,
            "job_title": state.get("job_posting", {}).get("title") if state.get("job_posting") else None,
            "recovered": data.get("recovered_from_checkpoint", False),
        })

    # Sort by created_at descending (most recent first)
    workflows_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # Apply pagination
    total_count = len(workflows_list)
    workflows_list = workflows_list[offset:offset + limit]

    return {
        "workflows": workflows_list,
        "count": len(workflows_list),
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


# ============================================================================
# Cleanup Endpoint (for scheduled cron jobs)
# ============================================================================

class CleanupRequest(BaseModel):
    """Request for cleanup endpoint."""
    days_old: int = Field(default=30, ge=1, le=365, description="Delete threads not accessed in this many days")


class CleanupResponse(BaseModel):
    """Response from cleanup endpoint."""
    deleted: int
    errors: int
    thread_ids: list[str]
    message: str


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_old_workflows(
    request: CleanupRequest = CleanupRequest(),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Clean up old workflows that haven't been accessed recently.

    This endpoint is designed to be called by a scheduled cron job.
    It requires authentication via X-API-Key header when CLEANUP_API_KEY is set.

    Deletes:
    - Thread metadata records
    - LangGraph checkpoint data
    - Memory cache entries

    Args:
        days_old: Delete threads not accessed in this many days (default: 30)
        x_api_key: API key for authentication (from header)
    """
    # Check API key authentication
    cleanup_api_key = os.getenv("CLEANUP_API_KEY")
    if not cleanup_api_key:
        # Log warning when cleanup endpoint is unprotected
        logger.warning(
            "CLEANUP_API_KEY not set - cleanup endpoint is unprotected. "
            "Set CLEANUP_API_KEY environment variable to secure this endpoint."
        )
    elif x_api_key != cleanup_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Set X-API-Key header."
        )

    metadata_service = get_metadata_service()

    # Check if database is configured
    if not metadata_service.database_url:
        # Memory-only cleanup
        old_threads = []
        cutoff = datetime.now() - timedelta(days=request.days_old)

        for thread_id, data in list(_workflows.items()):
            created_at = _parse_timestamp(data.get("created_at", ""))
            if created_at and created_at < cutoff:
                del _workflows[thread_id]
                old_threads.append(thread_id)

        return CleanupResponse(
            deleted=len(old_threads),
            errors=0,
            thread_ids=old_threads,
            message="Memory-only cleanup (no database configured)"
        )

    # First, get the list of threads to clean up
    expired_threads = metadata_service.get_expired_threads(days_old=request.days_old)

    # Remove from memory cache FIRST to prevent race condition
    # where another request tries to access a thread being deleted
    for thread_id in expired_threads:
        _workflows.pop(thread_id, None)

    # Now perform the database cleanup
    result = metadata_service.cleanup_expired_threads(days_old=request.days_old)

    logger.info(
        f"Cleanup completed: deleted {result['deleted']} threads, "
        f"{result['errors']} errors"
    )

    return CleanupResponse(
        deleted=result["deleted"],
        errors=result["errors"],
        thread_ids=result["thread_ids"],
        message=f"Cleaned up threads not accessed in {request.days_old} days"
    )
