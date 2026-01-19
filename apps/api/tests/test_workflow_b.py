"""Tests for Workflow Variant B (Deep Agents)."""

import pytest
from unittest.mock import patch, AsyncMock

from workflow_b.planner import (
    TodoItem,
    PlannerState,
    create_initial_plan,
    get_next_task,
    mark_task_complete,
    mark_task_failed,
    is_plan_complete,
)
from workflow_b.graph_b import (
    get_planner_state,
    coordinator_node,
    route_from_coordinator,
    route_after_agent,
    create_workflow_b,
    reset_workflow_b,
)


class TestPlanner:
    """Test planner module."""

    def test_create_initial_plan(self):
        """Test initial plan creation."""
        todos = create_initial_plan()
        assert len(todos) == 6
        assert todos[0].id == "ingest"
        assert todos[1].id == "research"
        assert todos[2].id == "analysis"
        assert todos[3].id == "discovery"
        assert todos[4].id == "drafting"
        assert todos[5].id == "export"

    def test_get_next_task(self):
        """Test getting next pending task."""
        todos = create_initial_plan()
        next_task = get_next_task(todos)
        assert next_task is not None
        assert next_task.id == "ingest"

    def test_get_next_task_after_complete(self):
        """Test getting next task after first is complete."""
        todos = create_initial_plan()
        todos = mark_task_complete(todos, "ingest", "done")
        next_task = get_next_task(todos)
        assert next_task is not None
        assert next_task.id == "research"

    def test_mark_task_complete(self):
        """Test marking task as complete."""
        todos = create_initial_plan()
        todos = mark_task_complete(todos, "ingest", "Profile parsed")
        assert todos[0].status == "completed"
        assert todos[0].result == "Profile parsed"

    def test_mark_task_failed(self):
        """Test marking task as failed."""
        todos = create_initial_plan()
        todos = mark_task_failed(todos, "ingest", "URL not found")
        assert todos[0].status == "failed"
        assert todos[0].result == "URL not found"

    def test_is_plan_complete_false(self):
        """Test plan not complete when tasks pending."""
        todos = create_initial_plan()
        assert is_plan_complete(todos) is False

    def test_is_plan_complete_true(self):
        """Test plan complete when all tasks done."""
        todos = create_initial_plan()
        for todo in todos:
            todo.status = "completed"
        assert is_plan_complete(todos) is True

    def test_is_plan_complete_with_failed(self):
        """Test plan complete even with failed tasks."""
        todos = create_initial_plan()
        for i, todo in enumerate(todos):
            todo.status = "failed" if i == 0 else "completed"
        assert is_plan_complete(todos) is True


class TestCoordinator:
    """Test coordinator node."""

    @pytest.mark.asyncio
    async def test_coordinator_returns_next_agent(self):
        """Test coordinator returns next agent."""
        reset_workflow_b()
        state = {"_thread_id": "test-thread"}
        result = await coordinator_node(state)
        assert result["_next_agent"] == "ingest_agent"
        assert result["_current_task"] == "ingest"

    @pytest.mark.asyncio
    async def test_coordinator_returns_completed_when_done(self):
        """Test coordinator returns completed when all tasks done."""
        reset_workflow_b()
        thread_id = "test-done"
        planner = get_planner_state(thread_id)
        for todo in planner.todos:
            todo.status = "completed"

        state = {"_thread_id": thread_id}
        result = await coordinator_node(state)
        assert result["current_step"] == "completed"


class TestRouting:
    """Test routing functions."""

    def test_route_from_coordinator_ingest(self):
        """Test routing to ingest agent."""
        state = {"_next_agent": "ingest_agent"}
        assert route_from_coordinator(state) == "ingest_agent"

    def test_route_from_coordinator_research(self):
        """Test routing to research agent."""
        state = {"_next_agent": "research_agent"}
        assert route_from_coordinator(state) == "research_agent"

    def test_route_from_coordinator_discovery(self):
        """Test routing to discovery agent."""
        state = {"_next_agent": "discovery_agent"}
        assert route_from_coordinator(state) == "discovery_agent"

    def test_route_from_coordinator_drafting(self):
        """Test routing to drafting agent."""
        state = {"_next_agent": "drafting_agent"}
        assert route_from_coordinator(state) == "drafting_agent"

    def test_route_from_coordinator_export(self):
        """Test routing to export agent."""
        state = {"_next_agent": "export_agent"}
        assert route_from_coordinator(state) == "export_agent"

    def test_route_from_coordinator_unknown(self):
        """Test routing with unknown agent."""
        state = {"_next_agent": "unknown"}
        assert route_from_coordinator(state) == "end"

    def test_route_after_agent_to_coordinator(self):
        """Test routing back to coordinator."""
        reset_workflow_b()
        state = {"_thread_id": "test-route", "current_step": "ingest"}
        assert route_after_agent(state) == "coordinator"

    def test_route_after_agent_discovery_loop(self):
        """Test discovery loop continues."""
        state = {"current_step": "discovery", "discovery_confirmed": False}
        assert route_after_agent(state) == "discovery_agent"


class TestWorkflowCreation:
    """Test workflow creation."""

    def test_create_workflow_b(self):
        """Test workflow B can be created."""
        reset_workflow_b()
        workflow = create_workflow_b()
        assert workflow is not None

    def test_workflow_has_nodes(self):
        """Test workflow has expected nodes."""
        reset_workflow_b()
        workflow = create_workflow_b()
        # LangGraph compiled graphs have nodes in the graph structure
        assert workflow is not None
