import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def agent_event_stream(agent_id: str) -> AsyncGenerator[str, None]:
    """
    Stream agent events from Agents SDK.
    Simulates agent phases: planning → tools → writing with citations.
    """
    # Simulate agent workflow phases
    phases = [
        {
            "type": "phase",
            "phase": "planning",
            "message": "Planning research strategy",
            "timestamp": asyncio.get_event_loop().time(),
        },
        {
            "type": "tool_use",
            "tool": "web_search",
            "query": "latest developments",
            "timestamp": asyncio.get_event_loop().time(),
        },
        {
            "type": "citation",
            "url": "https://example.com/article1",
            "title": "Relevant Article 1",
            "timestamp": asyncio.get_event_loop().time(),
        },
        {
            "type": "phase",
            "phase": "writing",
            "message": "Synthesizing findings",
            "timestamp": asyncio.get_event_loop().time(),
        },
        {
            "type": "complete",
            "message": "Agent completed successfully",
            "timestamp": asyncio.get_event_loop().time(),
        },
    ]

    for phase in phases:
        # Add agent_id to event
        event_data = {"agent_id": agent_id, **phase}
        yield f"data: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(2)  # Simulate processing time


@router.get("/stream/{agent_id}")
async def stream_agent_events(agent_id: str) -> StreamingResponse:
    """
    SSE endpoint that proxies Agents SDK event stream.
    Phases visible in UI: planning → tools → writing with citations.
    """
    return StreamingResponse(
        agent_event_stream(agent_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
