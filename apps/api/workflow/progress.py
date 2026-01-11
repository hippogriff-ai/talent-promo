"""Real-time progress store for workflow nodes.

This module provides a side-channel for progress updates that are immediately
visible to the frontend, unlike LangGraph state which only updates after
a node completes.
"""

import contextvars
from datetime import datetime

# Context variable to track current thread_id during workflow execution
current_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_thread_id', default='')

# In-memory progress store (updates DURING node execution)
_progress_store: dict[str, list[dict]] = {}


def add_realtime_progress(thread_id: str, phase: str, message: str, detail: str = ""):
    """Add a progress message that's immediately visible to the frontend.

    Unlike state.progress_messages which only updates after node completion,
    this store is updated during node execution for real-time feedback.
    """
    if thread_id not in _progress_store:
        _progress_store[thread_id] = []

    _progress_store[thread_id].append({
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "message": message,
        "detail": detail,
    })


def emit_progress(phase: str, message: str, detail: str = ""):
    """Emit a progress message for the current workflow.

    Uses the context variable to get the current thread_id.
    Call this from workflow nodes for real-time progress updates.
    """
    thread_id = current_thread_id.get()
    if thread_id:
        add_realtime_progress(thread_id, phase, message, detail)


def get_realtime_progress(thread_id: str) -> list[dict]:
    """Get current real-time progress messages."""
    return _progress_store.get(thread_id, [])


def clear_realtime_progress(thread_id: str):
    """Clear real-time progress (called when node completes)."""
    if thread_id in _progress_store:
        del _progress_store[thread_id]
