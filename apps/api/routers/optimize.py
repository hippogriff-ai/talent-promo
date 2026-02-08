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
from datetime import datetime
from typing import Literal, Optional, Any

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from langgraph.types import Command

from workflow.graph import get_workflow, create_initial_state
from workflow.nodes.analysis import analyze_node
from workflow.nodes.editor import get_editor_suggestion, regenerate_section
from workflow.nodes.export import export_resume
from validators import validate_urls
from services.thread_metadata import get_metadata_service
from middleware.rate_limit import check_rate_limit
from middleware.turnstile import verify_turnstile_token
from guardrails import validate_input

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimize", tags=["resume-optimization"])


# ============================================================================
# Helper Functions
# ============================================================================


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
    turnstile_token: Optional[str] = None  # Cloudflare Turnstile bot protection token


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
    discovery_agenda: Optional[dict] = None  # Structured agenda with topics

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
    action: Literal["improve", "add_keywords", "quantify", "shorten", "rewrite", "fix_tone", "custom"]
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
_workflow_locks: dict[str, asyncio.Lock] = {}

# File-based persistence for dev mode (survives server restarts)
_WORKFLOWS_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".workflow_cache.json"
)


def _persist_workflows():
    """Save all workflows to disk (dev mode only)."""
    try:
        with open(_WORKFLOWS_CACHE_FILE, "w") as f:
            json.dump(_workflows, f, default=str)
        logger.debug(f"Persisted {len(_workflows)} workflows to disk cache")
    except Exception as e:
        logger.warning(f"Could not persist workflows to disk: {e}")


def _load_workflows_from_disk():
    """Load workflows from disk cache on startup.

    Note: Loaded workflows can serve status requests but cannot resume
    LangGraph execution since MemorySaver state is lost on restart.
    The frontend validates sessions against /status before offering resume.
    """
    if os.path.exists(_WORKFLOWS_CACHE_FILE):
        try:
            with open(_WORKFLOWS_CACHE_FILE, "r") as f:
                data = json.load(f)
            # Mark all loaded workflows as recovered from disk
            for thread_id, wd in data.items():
                wd["recovered_from_disk"] = True
            _workflows.update(data)
            logger.info(f"Loaded {len(data)} workflows from disk cache")
        except Exception as e:
            logger.warning(f"Could not load workflow cache: {e}")


# Auto-load on import
_load_workflows_from_disk()


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
    """Save workflow data to in-memory cache and persist to disk.

    Note: The actual state persistence is handled by LangGraph's checkpointer.
    This cache is for quick access to workflow metadata.
    Disk persistence allows recovery after server restarts.
    """
    _workflows[thread_id] = data
    _persist_workflows()


def _enrich_job_posting(state: dict) -> dict | None:
    """Enrich job_posting with new fields from state.

    After ingest simplification, company/title may be in separate state fields
    (job_company, job_title) rather than inside job_posting. This merges them.

    Returns None if no meaningful job data exists (to avoid frontend showing
    empty "Job Details" checkmark with no content).
    """
    job_posting = state.get("job_posting") or {}
    if not isinstance(job_posting, dict):
        job_posting = {}

    # Make a copy to avoid mutating state
    enriched = dict(job_posting)

    # Merge new fields if job_posting doesn't have them
    if not enriched.get("company_name") and state.get("job_company"):
        enriched["company_name"] = state.get("job_company")
    if not enriched.get("title") and state.get("job_title"):
        enriched["title"] = state.get("job_title")

    # Return None if no meaningful data (prevents truthy empty object bug)
    if not enriched.get("title") and not enriched.get("company_name") and not enriched.get("description"):
        return None

    return enriched


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

    # Verify Turnstile token BEFORE rate limit (so bot requests don't consume rate limit slots)
    await verify_turnstile_token(request.turnstile_token, client_ip)

    # Check rate limit (3 requests per IP per day)
    allowed, remaining, reset_time = check_rate_limit(client_ip)
    if not allowed:
        # Format reset time nicely
        hours = reset_time // 3600
        minutes = (reset_time % 3600) // 60
        if hours > 0:
            time_str = f"{hours}h {minutes}m" if minutes else f"{hours} hours"
        else:
            time_str = f"{minutes} minutes"

        raise HTTPException(
            status_code=429,
            detail=f"Whoa there, speedster! You've used up your daily resume juice. Your creativity tank refills in {time_str}. Maybe grab a coffee? ☕",
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

    # Validate inputs for injection attacks and content safety
    if request.resume_text:
        validate_input(request.resume_text, ip_address=client_ip)
    if request.job_text:
        validate_input(request.job_text, ip_address=client_ip)

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

    Uses async workflow methods with MemorySaver.
    All data is ephemeral and cleaned up after 2 hours (privacy by design).
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
            if state and state.values:
                workflow_data["state"] = dict(state.values)

            # Mark as interrupted
            workflow_data["interrupted"] = True
            workflow_data["interrupt_value"] = getattr(e, 'value', None)
            _save_workflow_data(thread_id, workflow_data)
        else:
            import traceback
            logger.error(f"Workflow {thread_id} error: {e}\n{traceback.format_exc()}")
            if thread_id in _workflows and "state" in _workflows[thread_id]:
                wd = _workflows[thread_id]
                wd["state"]["errors"] = [
                    *wd["state"].get("errors", []),
                    str(e)
                ]
                wd["state"]["current_step"] = "error"
                _save_workflow_data(thread_id, wd)
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
        discovery_agenda=state.get("discovery_agenda"),  # Structured agenda with topics
    )

    # Include full data if requested
    if include_data:
        response.user_profile = state.get("user_profile")
        response.job_posting = _enrich_job_posting(state)  # Merge job_company/job_title
        # Raw markdown for display/editing
        response.profile_markdown = state.get("profile_markdown")
        response.job_markdown = state.get("job_markdown")
        response.research = state.get("research")
        response.gap_analysis = state.get("gap_analysis")
        response.resume_html = state.get("resume_final") or state.get("resume_html")

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
    # Validate user answer for injection attacks
    validate_input(answer.text, thread_id=thread_id)

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

    Note: If the workflow was recovered from disk cache (after server restart),
    the MemorySaver won't have its state and this will fail. The frontend
    validates session availability before attempting resume.
    """
    # Check if this workflow was recovered from disk — LangGraph can't resume it
    # (MemorySaver state is lost on server restart)
    workflow_data_check = _workflows.get(thread_id, {})
    if workflow_data_check.get("recovered_from_disk"):
        raise HTTPException(
            status_code=409,
            detail="Session was recovered after server restart but cannot be resumed. Please start a new optimization."
        )

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
            if state and state.values:
                workflow_data["state"] = dict(state.values)

            workflow_data["interrupted"] = True
            workflow_data["interrupt_value"] = getattr(e, 'value', None)
            _save_workflow_data(thread_id, workflow_data)
        else:
            import traceback
            logger.error(f"Workflow resume error for {thread_id}: {e}\n{traceback.format_exc()}")
            if thread_id in _workflows and "state" in _workflows[thread_id]:
                wd = _workflows[thread_id]
                wd["state"]["errors"] = [
                    *wd["state"].get("errors", []),
                    str(e)
                ]
                wd["state"]["current_step"] = "error"
                _save_workflow_data(thread_id, wd)


class DiscoveryConfirmRequest(BaseModel):
    """Request to confirm discovery completion."""
    confirmed: bool = True


@router.post("/{thread_id}/discovery/confirm", response_model=WorkflowStateResponse)
async def confirm_discovery(thread_id: str, request: DiscoveryConfirmRequest):
    """Confirm discovery is complete and proceed to drafting.

    Requires at least 3 conversation exchanges before allowing confirmation.
    """
    workflow_data = _get_workflow_data(thread_id)
    if workflow_data.get("recovered_from_disk"):
        raise HTTPException(status_code=409, detail="Session cannot be resumed after server restart. Please start a new optimization.")
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


@router.post("/{thread_id}/discovery/skip", response_model=WorkflowStateResponse)
async def skip_discovery(thread_id: str):
    """Skip the discovery phase entirely and proceed directly to drafting.

    Use this when users don't want to participate in the discovery conversation.
    The resume will be generated based solely on their LinkedIn profile data.
    """
    workflow_data = _get_workflow_data(thread_id)
    if workflow_data.get("recovered_from_disk"):
        raise HTTPException(status_code=409, detail="Session cannot be resumed after server restart. Please start a new optimization.")
    state = workflow_data.get("state", {})

    # Update state to mark discovery as skipped/confirmed
    state["discovery_confirmed"] = True
    state["discovery_skipped"] = True  # Flag to indicate it was skipped
    # Also mark QA as complete so qa_node short-circuits to drafting
    # Without this, qa_node calls interrupt() and the workflow hangs
    state["qa_complete"] = True
    state["user_done_signal"] = True
    state["updated_at"] = datetime.now().isoformat()
    workflow_data["state"] = state

    # Mark as not interrupted so workflow can continue
    workflow_data["interrupted"] = False
    _save_workflow_data(thread_id, workflow_data)

    logger.info(f"Discovery skipped for {thread_id}, proceeding to drafting")

    # Resume workflow
    asyncio.create_task(_resume_workflow(thread_id, "discovery_complete"))

    return await get_workflow_status(thread_id)


class RerunGapAnalysisRequest(BaseModel):
    """Request to re-run gap analysis with updated profile/job data."""
    profile_markdown: Optional[str] = None
    job_markdown: Optional[str] = None


@router.post("/{thread_id}/gap-analysis/rerun", response_model=WorkflowStateResponse)
async def rerun_gap_analysis(thread_id: str, request: RerunGapAnalysisRequest = None):
    """Re-run the gap analysis with the current user profile and job posting data.

    Use this when users have updated their profile information (e.g., pasted in
    additional resume content) and want to get a fresh gap analysis.

    If profile_markdown or job_markdown are provided in the request body,
    they will be used instead of the cached state values. This allows the
    frontend to send edited content that was modified in the UI.
    """
    # Validate user input for injection attacks
    if request:
        if request.profile_markdown:
            validate_input(request.profile_markdown, thread_id=thread_id)
        if request.job_markdown:
            validate_input(request.job_markdown, thread_id=thread_id)

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Update state with provided markdown if given (from frontend edits)
    if request:
        if request.profile_markdown:
            state["profile_markdown"] = request.profile_markdown
            state["profile_text"] = request.profile_markdown
            logger.info(f"Using provided profile_markdown ({len(request.profile_markdown)} chars)")
        if request.job_markdown:
            state["job_markdown"] = request.job_markdown
            state["job_text"] = request.job_markdown
            logger.info(f"Using provided job_markdown ({len(request.job_markdown)} chars)")

    # Verify we have profile/job data from either raw text or structured data
    has_profile = state.get("profile_text") or state.get("profile_markdown") or state.get("user_profile")
    has_job = state.get("job_text") or state.get("job_markdown") or state.get("job_posting")

    if not has_profile or not has_job:
        raise HTTPException(
            status_code=400,
            detail="Missing user profile or job posting data. Cannot re-run gap analysis."
        )

    try:
        # Run the analysis node directly with current state
        analysis_result = await analyze_node(state)

        if "errors" in analysis_result and analysis_result.get("current_step") == "error":
            raise HTTPException(
                status_code=500,
                detail=analysis_result.get("errors", ["Analysis failed"])[-1]
            )

        # Update state with new gap analysis
        if "gap_analysis" in analysis_result:
            state["gap_analysis"] = analysis_result["gap_analysis"]
            state["updated_at"] = datetime.now().isoformat()
            workflow_data["state"] = state
            _save_workflow_data(thread_id, workflow_data)
            logger.info(f"Gap analysis re-run for {thread_id}")

        return await get_workflow_status(thread_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to re-run gap analysis for {thread_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to re-run gap analysis: {str(e)}"
        )


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
        "job_posting": _enrich_job_posting(state),  # Merge job_company/job_title
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
    # Validate user input for injection attacks
    if action.instructions:
        validate_input(action.instructions, thread_id=thread_id)
    validate_input(action.selected_text, thread_id=thread_id)

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
    # Validate user input for injection attacks
    validate_input(request.current_content, thread_id=thread_id)

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

    Uses the bleach library for proper HTML sanitization instead of regex,
    which is more secure and handles edge cases correctly.

    Allows safe HTML formatting tags commonly used in resumes while
    blocking scripts, event handlers, and other XSS vectors.
    """
    import bleach

    # Tags allowed in resume HTML (safe formatting elements)
    ALLOWED_TAGS = [
        # Headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # Text formatting
        "p", "br", "hr",
        "strong", "b", "em", "i", "u", "s", "mark",
        "small", "sub", "sup",
        # Lists
        "ul", "ol", "li",
        # Structure
        "div", "span", "section", "article", "header", "footer",
        # Tables (for structured resume layouts)
        "table", "thead", "tbody", "tr", "th", "td",
        # Links (href will be sanitized)
        "a",
        # Other safe elements
        "blockquote", "pre", "code",
    ]

    # Attributes allowed on specific tags
    ALLOWED_ATTRIBUTES = {
        "*": ["class", "id", "style"],  # Allow class/id/style on all tags
        "a": ["href", "title", "target"],
        "td": ["colspan", "rowspan"],
        "th": ["colspan", "rowspan", "scope"],
        "table": ["border", "cellpadding", "cellspacing"],
    }

    # Protocols allowed in href/src attributes
    ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,  # Strip disallowed tags instead of escaping
    )


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
# Editor Sync and Chat Endpoints (with prompt caching)
# ============================================================================


class DraftingChatRequest(BaseModel):
    """Request for chat with drafting agent."""
    selected_text: str
    user_message: str
    chat_history: list[dict] = []
    # No current_html - backend uses synced state


class EditorSyncRequest(BaseModel):
    """Request to sync editor state to backend."""
    html: str  # Current editor content
    original: str = ""  # For tracking (optional)
    suggestion: str = ""  # For tracking (optional)
    user_message: str = ""  # What user asked for (optional)


@router.post("/{thread_id}/editor/sync")
async def editor_sync(thread_id: str, request: EditorSyncRequest):
    """Sync editor state to backend (called after apply or undo).

    Also tracks accepted suggestions for preference learning.
    """
    workflow_data = _get_workflow_data(thread_id)
    if not workflow_data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    state = workflow_data.get("state", {})

    # Sanitize and update resume state
    sanitized_html = _sanitize_html(request.html)
    state["resume_html"] = sanitized_html
    state["updated_at"] = datetime.now().isoformat()

    # Track for learning if this was an apply (not just a sync)
    if request.original and request.suggestion:
        suggestion_history = state.get("suggestion_history", [])
        suggestion_history.append({
            "original": request.original,
            "suggestion": request.suggestion,
            "user_message": request.user_message,
            "timestamp": datetime.now().isoformat(),
        })
        state["suggestion_history"] = suggestion_history

    workflow_data["state"] = state
    _save_workflow_data(thread_id, workflow_data)

    return {"success": True}


@router.post("/{thread_id}/editor/chat")
async def drafting_chat_endpoint(thread_id: str, request: DraftingChatRequest):
    """Chat with drafting agent (full context, cached).

    Uses synced state["resume_html"] - no HTML in request needed.
    Reuses the same system prompt and context as initial draft generation.
    Uses Anthropic prompt caching for efficiency on subsequent messages.
    """
    from workflow.nodes.drafting import drafting_chat

    # Validate user input for injection attacks
    validate_input(request.user_message, thread_id=thread_id)
    validate_input(request.selected_text, thread_id=thread_id)

    workflow_data = _get_workflow_data(thread_id)
    if not workflow_data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    state = workflow_data.get("state", {})

    result = await drafting_chat(
        state=state,
        selected_text=request.selected_text,
        user_message=request.user_message,
        chat_history=request.chat_history,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Chat failed"))

    return result


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
        validation = validate_resume(state.get("resume_html"), source_text=state.get("profile_text", ""), job_text=state.get("job_text", ""))

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
    if request.action == "accept" and suggestion.get("original_text") and suggestion.get("proposed_text"):
        resume_html = resume_html.replace(
            suggestion["original_text"],
            suggestion["proposed_text"],
            1,  # Only replace first occurrence to avoid unintended duplicate replacements
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
    # Validate user input for injection attacks
    validate_input(request.new_text, thread_id=thread_id)

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    resume_html = state.get("resume_html", "")

    # Apply the edit - return error if original text not found
    if request.original_text not in resume_html:
        raise HTTPException(
            status_code=400,
            detail="Edit not applied: original text not found in resume"
        )

    resume_html = resume_html.replace(request.original_text, request.new_text, 1)
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
    validate_input(request.html_content, thread_id=thread_id)

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Update both resume_html and resume_final for consistency
    state["resume_html"] = request.html_content
    state["resume_final"] = request.html_content

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


@router.post("/{thread_id}/discovery/revert")
async def revert_to_discovery(thread_id: str):
    """Revert from drafting back to discovery for more conversation.

    This allows users to go back and provide more information before
    the resume is regenerated.
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Revert discovery confirmation - keep discovered experiences
    state["discovery_confirmed"] = False
    state["discovery_skipped"] = False
    state["current_step"] = "discovery"
    state["sub_step"] = None
    state["updated_at"] = datetime.now().isoformat()

    # Clear draft data since it will be regenerated
    state.pop("resume_html", None)
    state.pop("resume_draft", None)
    state.pop("draft_suggestions", None)
    state.pop("draft_versions", None)
    state.pop("draft_approved", None)
    state.pop("draft_validation", None)
    state.pop("user_done_signal", None)
    state.pop("qa_complete", None)

    # Re-enable interrupt so discovery node can ask questions again
    workflow_data["state"] = state
    workflow_data["interrupted"] = True
    # Restore the last discovery interrupt if available
    if state.get("discovery_prompts"):
        # Find first unasked prompt to resume from
        for prompt in state["discovery_prompts"]:
            if not prompt.get("asked"):
                workflow_data["interrupt_value"] = {
                    "question": prompt["question"],
                    "context": {
                        "current_topic": prompt.get("topic_id"),
                    },
                }
                break

    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "message": "Reverted to discovery. You can continue the conversation.",
        "discovery_confirmed": False,
        "current_step": "discovery",
    }


@router.post("/{thread_id}/drafting/revert")
async def revert_to_drafting(thread_id: str):
    """Revert from export back to drafting for edits.

    This allows users to go back and make corrections (e.g., fix email/contact info)
    after they've already approved the draft.
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Revert the approval - keep resume_html so user can continue editing
    state["draft_approved"] = False
    state["current_step"] = "editor"  # Go back to editor step so frontend shows editable view
    state["updated_at"] = datetime.now().isoformat()

    # Clear export-related data since it's now stale
    state.pop("export_output", None)
    state.pop("ats_report", None)
    state.pop("linkedin_suggestions", None)
    state.pop("export_completed", None)
    state.pop("export_step", None)

    workflow_data["state"] = state
    # Set interrupted so submitAnswer works if needed
    workflow_data["interrupted"] = True
    _save_workflow_data(thread_id, workflow_data)

    return {
        "success": True,
        "message": "Reverted to drafting. You can now make edits.",
        "draft_approved": False,
        "current_step": "editor",
    }


@router.post("/{thread_id}/drafting/approve")
async def approve_draft(thread_id: str, request: ApproveDraftRequest):
    """Approve the draft and enable export."""
    from workflow.nodes.drafting import validate_resume

    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    # Auto-resolve any pending suggestions (the editor UI doesn't surface them,
    # so requiring manual resolution would block the user indefinitely).
    suggestions = state.get("draft_suggestions", [])
    for s in suggestions:
        if s.get("status") == "pending":
            s["status"] = "declined"
            s["resolved_at"] = datetime.now().isoformat()
    state["draft_suggestions"] = suggestions

    # Validate resume (advisory only — user explicitly approved, so don't block)
    resume_html = state.get("resume_html", "")
    validation = validate_resume(resume_html, source_text=state.get("profile_text", ""), job_text=state.get("job_text", ""))

    # Strip editor artifacts (highlight marks) before storing final version
    clean_html = re.sub(r'<mark[^>]*>', '', resume_html)
    clean_html = clean_html.replace('</mark>', '')

    # Mark as approved
    state["draft_approved"] = request.approved
    state["resume_final"] = clean_html
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


@router.get("/{thread_id}/drafting/preview-pdf")
async def preview_pdf(thread_id: str):
    """Generate a PDF preview of the current resume draft.

    Returns PDF for inline viewing (Content-Disposition: inline).
    Use this to show users how their resume will look when exported.
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})

    html_content = state.get("resume_html")
    if not html_content:
        raise HTTPException(
            status_code=400,
            detail="No resume content to preview"
        )

    user_profile = state.get("user_profile") or {}
    file_bytes, content_type, filename = export_resume(
        html_content=html_content,
        format="pdf",
        filename_base="preview",
        user_profile=user_profile if isinstance(user_profile, dict) else {},
    )

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            # inline instead of attachment so browser displays it
            "Content-Disposition": 'inline; filename="preview.pdf"'
        },
    )


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
        "job_posting": _enrich_job_posting(state),  # Merge job_company/job_title
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
    # Clean up the associated lock
    _workflow_locks.pop(thread_id, None)

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
    hours_old: float = Field(default=2.0, ge=0.5, le=24.0, description="Delete threads not accessed in this many hours")


class CleanupResponse(BaseModel):
    """Response from cleanup endpoint."""
    deleted: int
    errors: int
    thread_ids: list[str]
    message: str


# ============================================================================
# Dev: State Snapshots (save/restore for replay testing)
# ============================================================================

SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "snapshots")


@router.post("/{thread_id}/snapshot")
async def save_snapshot(thread_id: str, label: Optional[str] = None):
    """Save workflow state to a JSON file for replay testing.

    Snapshots are saved to apps/api/snapshots/<thread_id>_<step>_<timestamp>.json.
    Use POST /api/optimize/restore?file=<filename> to restore.
    """
    workflow_data = _get_workflow_data(thread_id)
    state = workflow_data.get("state", {})
    step = state.get("current_step", "unknown")

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    tag = label or step
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{thread_id[:8]}_{tag}_{timestamp}.json"
    filepath = os.path.join(SNAPSHOT_DIR, filename)

    snapshot = {
        "thread_id": thread_id,
        "snapshot_label": tag,
        "created_at": datetime.now().isoformat(),
        "state": state,
    }

    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    logger.info(f"Saved snapshot: {filename}")
    return {"filename": filename, "step": step, "path": filepath}


@router.post("/restore")
async def restore_snapshot(file: str):
    """Restore workflow state from a snapshot file.

    Creates a new thread_id with the saved state, ready for testing.
    The workflow resumes from whatever step was captured.
    """
    filepath = os.path.join(SNAPSHOT_DIR, file)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {file}")

    with open(filepath, "r") as f:
        snapshot = json.load(f)

    # Create a fresh thread_id for the restored workflow
    new_thread_id = str(uuid.uuid4())
    state = snapshot["state"]

    config = {"configurable": {"thread_id": new_thread_id}}

    _save_workflow_data(new_thread_id, {
        "state": state,
        "config": config,
        "created_at": datetime.now().isoformat(),
        "interrupted": True,  # Mark as interrupted so editor endpoints work
        "interrupt_value": {
            "interrupt_type": "draft_approval",
            "message": "Restored from snapshot",
        },
        "restored_from_snapshot": file,
    })

    step = state.get("current_step", "unknown")
    logger.info(f"Restored snapshot {file} as thread {new_thread_id} at step={step}")

    return {
        "thread_id": new_thread_id,
        "restored_from": file,
        "step": step,
        "original_thread_id": snapshot.get("thread_id"),
    }


@router.get("/snapshots/list")
async def list_snapshots():
    """List all saved snapshots."""
    if not os.path.exists(SNAPSHOT_DIR):
        return {"snapshots": []}

    files = sorted(os.listdir(SNAPSHOT_DIR), reverse=True)
    snapshots = []
    for f in files:
        if f.endswith(".json"):
            filepath = os.path.join(SNAPSHOT_DIR, f)
            try:
                with open(filepath, "r") as fh:
                    data = json.load(fh)
                snapshots.append({
                    "filename": f,
                    "thread_id": data.get("thread_id", ""),
                    "label": data.get("snapshot_label", ""),
                    "created_at": data.get("created_at", ""),
                    "step": data.get("state", {}).get("current_step", ""),
                })
            except Exception:
                snapshots.append({"filename": f, "error": "Could not read"})

    return {"snapshots": snapshots}


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

    # Get list of threads to clean up (in-memory)
    expired_threads = metadata_service.get_expired_threads(hours_old=request.hours_old)

    # Remove from memory cache and locks FIRST to prevent race condition
    for thread_id in expired_threads:
        _workflows.pop(thread_id, None)
        _workflow_locks.pop(thread_id, None)

    # Perform the in-memory cleanup
    result = metadata_service.cleanup_expired_threads(hours_old=request.hours_old)

    logger.info(
        f"Cleanup completed: deleted {result['deleted']} threads, "
        f"{result['errors']} errors"
    )

    return CleanupResponse(
        deleted=result["deleted"],
        errors=result["errors"],
        thread_ids=result["thread_ids"],
        message=f"Cleaned up threads not accessed in {request.hours_old} hours"
    )
