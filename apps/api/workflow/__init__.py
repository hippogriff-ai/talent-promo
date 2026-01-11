"""LangGraph workflow for resume optimization."""

# Note: Imports are relative to avoid conflicts with the langgraph package

__all__ = ["configure_langsmith", "ResumeState", "create_resume_workflow"]


def configure_langsmith():
    """Configure LangSmith - import lazily to avoid circular imports."""
    from workflow.config import configure_langsmith as _configure
    return _configure()


def get_resume_state():
    """Get ResumeState - import lazily."""
    from workflow.state import ResumeState
    return ResumeState


def create_resume_workflow(checkpointer=None):
    """Create workflow - import lazily."""
    from workflow.graph import create_resume_workflow as _create
    return _create(checkpointer)
