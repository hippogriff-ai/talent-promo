"""Planner module for Deep Agents workflow.

The planner uses a write_todos tool to decompose tasks and
coordinate subagent execution.
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TodoItem(BaseModel):
    """A task item in the planner's todo list."""
    id: str
    task: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    assigned_agent: str | None = None
    result: str | None = None


class PlannerState(BaseModel):
    """State for the planner's task management."""
    todos: list[TodoItem] = Field(default_factory=list)
    current_task_id: str | None = None
    plan_complete: bool = False


def create_initial_plan() -> list[TodoItem]:
    """Create the initial task plan for resume optimization.

    This mirrors the steps in Variant A's explicit workflow.
    """
    return [
        TodoItem(
            id="ingest",
            task="Fetch and parse profile and job posting from URLs/text",
            assigned_agent="ingest_agent",
        ),
        TodoItem(
            id="research",
            task="Research company culture, tech stack, and similar profiles",
            assigned_agent="research_agent",
        ),
        TodoItem(
            id="analysis",
            task="Analyze gaps between user profile and job requirements",
            assigned_agent="research_agent",
        ),
        TodoItem(
            id="discovery",
            task="Conduct discovery conversation to uncover hidden experiences",
            assigned_agent="discovery_agent",
        ),
        TodoItem(
            id="drafting",
            task="Generate ATS-optimized resume draft with suggestions",
            assigned_agent="drafting_agent",
        ),
        TodoItem(
            id="export",
            task="Export resume to PDF/DOCX and generate ATS report + LinkedIn suggestions",
            assigned_agent="export_agent",
        ),
    ]


def get_next_task(todos: list[TodoItem]) -> TodoItem | None:
    """Get the next pending task."""
    for todo in todos:
        if todo.status == "pending":
            return todo
    return None


def mark_task_complete(todos: list[TodoItem], task_id: str, result: str | None = None) -> list[TodoItem]:
    """Mark a task as complete and return updated todos."""
    for todo in todos:
        if todo.id == task_id:
            todo.status = "completed"
            todo.result = result
            break
    return todos


def mark_task_failed(todos: list[TodoItem], task_id: str, error: str) -> list[TodoItem]:
    """Mark a task as failed and return updated todos."""
    for todo in todos:
        if todo.id == task_id:
            todo.status = "failed"
            todo.result = error
            break
    return todos


def is_plan_complete(todos: list[TodoItem]) -> bool:
    """Check if all tasks are completed (or failed)."""
    return all(todo.status in ("completed", "failed") for todo in todos)
