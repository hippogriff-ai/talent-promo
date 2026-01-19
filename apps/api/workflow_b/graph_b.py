"""Deep Agents workflow (Variant B).

This workflow uses a coordinator pattern with autonomous subagents,
contrasting with Variant A's explicit state machine.

Key differences from Variant A:
- Planner decomposes tasks using write_todos
- Coordinator delegates to specialized subagents
- Subagents have more autonomy in how they complete tasks
- Same ResumeState output for A/B comparison
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from workflow.state import ResumeState
from workflow.graph import get_checkpointer
from workflow_b.planner import (
    PlannerState,
    create_initial_plan,
    get_next_task,
    mark_task_complete,
    is_plan_complete,
)

# Import nodes from Variant A (reuse for now, agents will replace later)
from workflow.nodes.ingest import parallel_ingest_node
from workflow.nodes.research import research_node
from workflow.nodes.discovery import discovery_node
from workflow.nodes.drafting import draft_resume_node
from workflow.nodes.editor import editor_assist_node
from workflow.nodes.export import export_node

logger = logging.getLogger(__name__)


# Store planner state alongside workflow state
_planner_states: dict[str, PlannerState] = {}


def get_planner_state(thread_id: str) -> PlannerState:
    """Get or create planner state for a thread."""
    if thread_id not in _planner_states:
        _planner_states[thread_id] = PlannerState(todos=create_initial_plan())
    return _planner_states[thread_id]


# ============================================================================
# Coordinator Node
# ============================================================================

async def coordinator_node(state: ResumeState) -> dict:
    """Coordinator that orchestrates subagent execution.

    This replaces Variant A's explicit routing with dynamic
    task selection based on planner state.
    """
    # Get thread_id from state metadata (set during workflow creation)
    thread_id = state.get("_thread_id", "default")
    planner = get_planner_state(thread_id)

    # Check if plan is complete
    if is_plan_complete(planner.todos):
        return {
            "current_step": "completed",
            "updated_at": datetime.now().isoformat(),
        }

    # Get next task
    task = get_next_task(planner.todos)
    if not task:
        return {
            "current_step": "completed",
            "updated_at": datetime.now().isoformat(),
        }

    logger.info(f"[Variant B] Coordinator delegating to: {task.assigned_agent} for task: {task.task}")

    # Update task status
    task.status = "in_progress"
    planner.current_task_id = task.id

    # Route to appropriate handler based on task
    return {
        "_next_agent": task.assigned_agent,
        "_current_task": task.id,
        "current_step": task.id,
        "updated_at": datetime.now().isoformat(),
    }


# ============================================================================
# Agent Nodes (wrap existing nodes for now)
# ============================================================================

def _mark_complete(state: ResumeState, task_id: str, message: str) -> None:
    """Helper to mark a planner task complete."""
    planner = get_planner_state(state.get("_thread_id", "default"))
    mark_task_complete(planner.todos, task_id, message)


async def ingest_agent(state: ResumeState) -> dict:
    """Ingest agent - handles profile and job fetching."""
    logger.info("[Variant B] Ingest agent executing")
    result = await parallel_ingest_node(state)
    _mark_complete(state, "ingest", "Profile and job parsed")
    return result


async def research_agent(state: ResumeState) -> dict:
    """Research agent - handles company research and gap analysis."""
    logger.info("[Variant B] Research agent executing")
    result = await research_node(state)
    _mark_complete(state, "research", "Company research complete")
    _mark_complete(state, "analysis", "Gap analysis complete")
    return result


async def discovery_agent(state: ResumeState) -> dict:
    """Discovery agent - conducts discovery conversation."""
    logger.info("[Variant B] Discovery agent executing")

    if state.get("discovery_confirmed", False):
        _mark_complete(state, "discovery", "Discovery complete")
        return {"current_step": "draft", "updated_at": datetime.now().isoformat()}

    result = await discovery_node(state)
    if result.get("discovery_confirmed"):
        _mark_complete(state, "discovery", "Discovery complete")
    return result


async def drafting_agent(state: ResumeState) -> dict:
    """Drafting agent - generates resume draft."""
    logger.info("[Variant B] Drafting agent executing")
    draft_result = await draft_resume_node(state)
    editor_result = await editor_assist_node({**state, **draft_result})
    _mark_complete(state, "drafting", "Resume draft generated")
    return {**draft_result, **editor_result}


async def export_agent(state: ResumeState) -> dict:
    """Export agent - handles export and ATS analysis."""
    logger.info("[Variant B] Export agent executing")
    result = await export_node(state)
    _mark_complete(state, "export", "Export complete")
    return result


# ============================================================================
# Routing
# ============================================================================

AGENT_NODES = {"ingest_agent", "research_agent", "discovery_agent", "drafting_agent", "export_agent"}


def route_from_coordinator(state: ResumeState) -> str:
    """Route from coordinator to the appropriate agent."""
    next_agent = state.get("_next_agent")
    return next_agent if next_agent in AGENT_NODES else "end"


def route_after_agent(state: ResumeState) -> str:
    """Route back to coordinator or to special handling."""
    current_step = state.get("current_step", "")

    # Discovery needs interrupt handling
    if current_step == "discovery" and not state.get("discovery_confirmed"):
        return "discovery_agent"  # Continue discovery loop

    # Check if all tasks are done
    thread_id = state.get("_thread_id", "default")
    planner = get_planner_state(thread_id)

    if is_plan_complete(planner.todos):
        return "end"

    return "coordinator"


# ============================================================================
# Graph Builder
# ============================================================================

def create_workflow_b(checkpointer=None):
    """Create Deep Agents workflow (Variant B).

    This workflow uses a coordinator pattern instead of explicit routing.
    """
    logger.info("Creating Deep Agents workflow (Variant B)")

    workflow = StateGraph(ResumeState)

    # Add coordinator node
    workflow.add_node("coordinator", coordinator_node)

    # Add agent nodes
    workflow.add_node("ingest_agent", ingest_agent)
    workflow.add_node("research_agent", research_agent)
    workflow.add_node("discovery_agent", discovery_agent)
    workflow.add_node("drafting_agent", drafting_agent)
    workflow.add_node("export_agent", export_agent)

    # Set entry point
    workflow.set_entry_point("coordinator")

    # Add routing from coordinator
    workflow.add_conditional_edges(
        "coordinator",
        route_from_coordinator,
        {
            "ingest_agent": "ingest_agent",
            "research_agent": "research_agent",
            "discovery_agent": "discovery_agent",
            "drafting_agent": "drafting_agent",
            "export_agent": "export_agent",
            "end": END,
        },
    )

    # Add routing after each agent
    for agent in ["ingest_agent", "research_agent", "discovery_agent", "drafting_agent", "export_agent"]:
        workflow.add_conditional_edges(
            agent,
            route_after_agent,
            {"coordinator": "coordinator", "discovery_agent": "discovery_agent", "end": END},
        )

    # Get checkpointer
    if checkpointer is None:
        checkpointer = get_checkpointer()

    compiled = workflow.compile(checkpointer=checkpointer)
    logger.info("Deep Agents workflow (Variant B) created")

    return compiled


# ============================================================================
# Global Instance
# ============================================================================

_workflow_b = None


def get_workflow_b():
    """Get the global Variant B workflow instance."""
    global _workflow_b
    if _workflow_b is None:
        _workflow_b = create_workflow_b()
    return _workflow_b


def reset_workflow_b():
    """Reset the global Variant B workflow instance."""
    global _workflow_b
    _workflow_b = None
    _planner_states.clear()
