"""Main LangGraph workflow definition for resume optimization.

This module implements a multi-step agentic workflow with:
- Human-in-the-loop interrupts using the interrupt() function
- Memory hierarchy for context management
- Production-ready checkpointing (Postgres/Redis)
- Progressive information disclosure
"""

import logging
import os
from datetime import datetime
from typing import Literal, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from workflow.state import ResumeState, WorkingContext, InterruptPayload
from workflow.context import build_working_context, build_qa_interrupt
from workflow.nodes.ingest import parallel_ingest_node
from workflow.nodes.research import research_node
from workflow.nodes.discovery import discovery_node
from workflow.nodes.qa import generate_question, process_qa_answer
from workflow.nodes.drafting import draft_resume_node
from workflow.nodes.editor import editor_assist_node
from workflow.nodes.export import export_node

logger = logging.getLogger(__name__)


# ============================================================================
# Checkpointer Factory
# ============================================================================

def get_checkpointer(checkpointer_type: Optional[str] = None):
    """Get appropriate checkpointer based on environment.

    Args:
        checkpointer_type: Override type ("memory", "sqlite", "postgres", "redis")

    Returns:
        Configured checkpointer instance

    Environment variables:
        LANGGRAPH_CHECKPOINTER: "memory" (default), "sqlite", "postgres", or "redis"
        LANGGRAPH_SQLITE_PATH: Path for SQLite database (default: ./workflow_checkpoints.db)
        DATABASE_URL: Postgres connection string
        REDIS_URL: Redis connection string
    """
    checkpointer_type = checkpointer_type or os.getenv("LANGGRAPH_CHECKPOINTER", "memory")

    if checkpointer_type == "sqlite":
        # SQLite - simple file-based persistence, survives restarts
        # We use SqliteSaver with sync workflow methods wrapped in asyncio.to_thread
        # For async FastAPI, the workflow._run_sync() pattern is used internally
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3

            db_path = os.getenv("LANGGRAPH_SQLITE_PATH", "./workflow_checkpoints.db")

            # Create directory if needed
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # Create connection with check_same_thread=False for multi-threaded use
            conn = sqlite3.connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            # Initialize the checkpoint tables
            checkpointer.setup()
            logger.info(f"Using SqliteSaver for checkpointing: {db_path}")
            return checkpointer
        except ImportError as e:
            logger.warning(f"SQLite checkpointer unavailable ({e}), falling back to memory")
            return MemorySaver()
        except Exception as e:
            logger.warning(f"Failed to create SQLite checkpointer ({e}), falling back to memory")
            return MemorySaver()

    elif checkpointer_type == "postgres":
        # NOTE: PostgresSaver doesn't support async (ainvoke), and AsyncPostgresSaver
        # requires context manager usage which doesn't fit our workflow pattern.
        # For now, fall back to MemorySaver which supports async operations.
        # TODO: Implement proper async Postgres checkpointing with connection pooling
        logger.warning("Postgres checkpointer not yet async-compatible, using MemorySaver")
        return MemorySaver()

    elif checkpointer_type == "redis":
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.warning("REDIS_URL not set, falling back to memory checkpointer")
            return MemorySaver()

        try:
            from langgraph_checkpoint_redis import RedisSaver
            logger.info("Using RedisSaver for checkpointing")
            return RedisSaver(redis_url)
        except ImportError:
            logger.warning("langgraph-checkpoint-redis not installed, falling back to memory")
            return MemorySaver()

    else:
        logger.info("Using MemorySaver for checkpointing (development mode)")
        return MemorySaver()


# ============================================================================
# Routing Functions
# ============================================================================

def _route_or_error(state: ResumeState, next_step: str) -> str:
    """Return next_step unless current step is error."""
    return "error" if state.get("current_step") == "error" else next_step


def should_continue_after_ingest(state: ResumeState) -> Literal["research", "error"]:
    """Route after parallel ingest (profile + job fetch)."""
    return _route_or_error(state, "research")


def should_continue_after_research(state: ResumeState) -> Literal["discovery_node", "error"]:
    """Route after research (now includes analysis) directly to discovery."""
    return _route_or_error(state, "discovery_node")


def should_continue_after_discovery(state: ResumeState) -> Literal["qa_node", "discovery_node", "error"]:
    """Route after discovery - either continue discovery or move to QA."""
    if state.get("current_step") == "error":
        return "error"
    return "qa_node" if state.get("discovery_confirmed", False) else "discovery_node"


def qa_loop_router(state: ResumeState) -> Literal["qa_node", "draft_resume"]:
    """Route based on Q&A completion status."""
    is_complete = (
        state.get("qa_complete", False) or
        state.get("user_done_signal", False) or
        state.get("qa_round", 0) >= 10
    )
    return "draft_resume" if is_complete else "qa_node"


def should_continue_after_draft(state: ResumeState) -> Literal["editor_assist", "error"]:
    """Route after drafting."""
    return _route_or_error(state, "editor_assist")


def should_continue_after_editor(state: ResumeState) -> Literal["export", "error"]:
    """Route after editor."""
    return _route_or_error(state, "export")


# ============================================================================
# Q&A Node with interrupt() Function
# ============================================================================

async def qa_node(state: ResumeState) -> dict:
    """Combined Q&A node using the interrupt() function.

    This node:
    1. Checks if Q&A is complete
    2. Generates a question based on gaps
    3. Uses interrupt() to pause and wait for user answer
    4. Processes the answer and updates state

    The interrupt() function is the recommended pattern as of LangGraph 1.0
    for human-in-the-loop workflows.
    """
    qa_round = state.get("qa_round", 0)
    qa_complete = state.get("qa_complete", False)
    user_done = state.get("user_done_signal", False)

    # Check termination conditions
    if qa_complete or user_done or qa_round >= 10:
        logger.info(f"Q&A complete: round={qa_round}, done={user_done}")
        return {
            "qa_complete": True,
            "current_step": "draft",
            "updated_at": datetime.now().isoformat(),
        }

    # Update working context for efficient LLM calls
    working_context = build_working_context(state)

    # Generate next question
    question_data = await generate_question(state, working_context)

    if question_data.get("no_more_questions"):
        logger.info("No more questions needed")
        return {
            "qa_complete": True,
            "current_step": "draft",
            "updated_at": datetime.now().isoformat(),
        }

    question = question_data["question"]
    question_intent = question_data.get("intent", "")

    # Build interrupt payload for progressive disclosure
    interrupt_payload = build_qa_interrupt(question, state, question_intent)

    logger.info(f"Q&A round {qa_round + 1}: Interrupting for user input")

    # Store the interrupt payload in state BEFORE calling interrupt()
    # This allows the frontend to access the question from the state
    # The interrupt_payload dict is passed to interrupt() and will also
    # be accessible via state.tasks[].interrupts[].value

    # Use interrupt() to pause and wait for user answer
    # This is the new recommended pattern in LangGraph 1.0+
    # The interrupt_payload becomes the interrupt value accessible via graph state
    answer = interrupt(interrupt_payload)

    # Process the answer
    result = process_qa_answer(answer, state, question, question_intent)

    return {
        **result,
        "working_context": working_context,
        "pending_interrupt": None,  # Clear after processing
        "updated_at": datetime.now().isoformat(),
    }


# ============================================================================
# State Factory
# ============================================================================

def create_initial_state(
    linkedin_url: Optional[str] = None,
    job_url: Optional[str] = None,
    uploaded_resume_text: Optional[str] = None,
    uploaded_job_text: Optional[str] = None,
    user_preferences: Optional[dict] = None,
) -> ResumeState:
    """Create initial state for a new workflow.

    Args:
        linkedin_url: LinkedIn profile URL
        job_url: Target job posting URL
        uploaded_resume_text: Raw resume text if uploaded
        uploaded_job_text: Pasted job description if provided
        user_preferences: User's writing style preferences

    Returns:
        Initialized ResumeState
    """
    now = datetime.now().isoformat()

    return ResumeState(
        # Inputs
        linkedin_url=linkedin_url,
        job_url=job_url,
        uploaded_resume_text=uploaded_resume_text,
        uploaded_job_text=uploaded_job_text,

        # Parsed data
        user_profile=None,
        job_posting=None,

        # Workflow outputs
        research=None,
        gap_analysis=None,

        # Working context (memory hierarchy)
        working_context=None,

        # Discovery
        discovery_prompts=[],
        discovery_messages=[],
        discovered_experiences=[],
        discovery_confirmed=False,
        discovery_exchanges=0,
        discovery_phase="setup",
        pending_prompt_id=None,

        # Q&A
        qa_history=[],
        qa_round=0,
        qa_complete=False,
        user_done_signal=False,

        # Interrupt state
        pending_interrupt=None,

        # Resume
        resume_draft=None,
        resume_html=None,
        resume_final=None,

        # Drafting stage
        draft_suggestions=[],
        draft_versions=[],
        draft_change_log=[],
        draft_current_version=None,
        draft_approved=False,

        # Export stage
        export_format=None,
        export_path=None,
        export_output=None,
        export_step=None,
        ats_report=None,
        linkedin_suggestions=None,
        export_completed=False,

        # User preferences
        user_preferences=user_preferences,

        # Metadata
        current_step="ingest",
        sub_step="fetching_data",
        errors=[],
        messages=[],
        progress_messages=[],
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# Graph Builder
# ============================================================================

def create_resume_workflow(checkpointer=None):
    """Create the resume optimization workflow graph.

    The workflow follows these steps:
    1. fetch_profile: Fetch LinkedIn profile or parse uploaded resume
    2. fetch_job: Fetch job posting from URL
    3. research: Research company, culture, similar employees
    4. analyze: Identify gaps and recommended highlights
    5. qa_node: Human-in-the-loop Q&A with interrupt() (up to 10 rounds)
    6. draft_resume: Generate ATS-optimized resume
    7. editor_assist: AI assistance for manual editing
    8. export: Export to DOCX/PDF

    Args:
        checkpointer: Optional checkpointer override.
                     Auto-detects from environment if not provided.

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating resume optimization workflow")

    # Create the graph
    workflow = StateGraph(ResumeState)

    # Add nodes (analyze merged into research for speed)
    workflow.add_node("ingest", parallel_ingest_node)  # Parallel profile + job fetch
    workflow.add_node("research", research_node)  # Now includes gap analysis
    workflow.add_node("discovery_node", discovery_node)  # Discovery conversation with interrupt()
    workflow.add_node("qa_node", qa_node)  # Combined Q&A with interrupt()
    workflow.add_node("draft_resume", draft_resume_node)
    workflow.add_node("editor_assist", editor_assist_node)
    workflow.add_node("export", export_node)

    # Error handling node
    async def error_node(state: ResumeState):
        logger.error(f"Workflow error: {state.get('errors', [])}")
        return {"current_step": "error"}

    workflow.add_node("error", error_node)

    # Set entry point
    workflow.set_entry_point("ingest")

    # Add edges with conditional routing
    workflow.add_conditional_edges(
        "ingest",
        should_continue_after_ingest,
        {"research": "research", "error": "error"},
    )

    workflow.add_conditional_edges(
        "research",
        should_continue_after_research,
        {"discovery_node": "discovery_node", "error": "error"},
    )

    # Discovery loop - discovery_node uses interrupt() internally
    workflow.add_conditional_edges(
        "discovery_node",
        should_continue_after_discovery,
        {"discovery_node": "discovery_node", "qa_node": "qa_node", "error": "error"},
    )

    # Q&A loop - qa_node uses interrupt() internally
    workflow.add_conditional_edges(
        "qa_node",
        qa_loop_router,
        {"qa_node": "qa_node", "draft_resume": "draft_resume"},
    )

    # Drafting to editor
    workflow.add_conditional_edges(
        "draft_resume",
        should_continue_after_draft,
        {"editor_assist": "editor_assist", "error": "error"},
    )

    # Editor to export
    workflow.add_conditional_edges(
        "editor_assist",
        should_continue_after_editor,
        {"export": "export", "error": "error"},
    )

    # Terminal edges
    workflow.add_edge("export", END)
    workflow.add_edge("error", END)

    # Get checkpointer (supports Postgres, Redis, or Memory)
    if checkpointer is None:
        checkpointer = get_checkpointer()

    # Compile the graph
    # Note: We don't use interrupt_before anymore since qa_node uses interrupt() directly
    compiled = workflow.compile(checkpointer=checkpointer)

    logger.info("Resume optimization workflow created successfully")

    return compiled


# ============================================================================
# Global Workflow Instance
# ============================================================================

_workflow = None


def get_workflow():
    """Get the global workflow instance (lazy initialization)."""
    global _workflow
    if _workflow is None:
        _workflow = create_resume_workflow()
    return _workflow


def reset_workflow():
    """Reset the global workflow instance (useful for testing)."""
    global _workflow
    _workflow = None
