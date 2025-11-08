import asyncio
import json
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/research", tags=["research"])

# In-memory store for research runs (replace with DB in production)
research_runs: dict[str, dict] = {}


class StartResearchRequest(BaseModel):
    query: str


class StartResearchResponse(BaseModel):
    run_id: str


class ResearchEvent(BaseModel):
    type: str
    data: dict


@router.post("/start", response_model=StartResearchResponse)
async def start_research(request: StartResearchRequest) -> StartResearchResponse:
    """Start a new research workflow and return a run ID."""
    run_id = str(uuid4())

    # Initialize research run state
    research_runs[run_id] = {
        "query": request.query,
        "status": "running",
        "events": [],
        "created_at": asyncio.get_event_loop().time(),
    }

    # In a real implementation, this would start a Temporal workflow
    # For now, we'll simulate the workflow progression
    asyncio.create_task(_simulate_research(run_id))

    return StartResearchResponse(run_id=run_id)


@router.get("/stream/{run_id}")
async def stream_research_status(run_id: str) -> StreamingResponse:
    """Stream research status and events via Server-Sent Events."""
    if run_id not in research_runs:
        raise HTTPException(status_code=404, detail="Research run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for the research run."""
        last_event_idx = 0

        while True:
            run = research_runs.get(run_id)
            if not run:
                break

            # Send any new events
            events = run["events"][last_event_idx:]
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
                last_event_idx += 1

            # Send status update
            status_event = {
                "type": "status",
                "data": {"status": run["status"], "run_id": run_id}
            }
            yield f"data: {json.dumps(status_event)}\n\n"

            # Stop streaming if research is complete
            if run["status"] in ["completed", "failed"]:
                break

            # Wait before checking for more events
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{run_id}")
async def get_research_status(run_id: str) -> dict:
    """Get the current status of a research run (for refresh/resume)."""
    if run_id not in research_runs:
        raise HTTPException(status_code=404, detail="Research run not found")

    run = research_runs[run_id]
    return {
        "run_id": run_id,
        "status": run["status"],
        "query": run["query"],
        "event_count": len(run["events"]),
    }


async def _simulate_research(run_id: str) -> None:
    """Simulate a research workflow with events."""
    await asyncio.sleep(1)

    # Add planning event
    research_runs[run_id]["events"].append({
        "type": "phase",
        "data": {"phase": "planning", "message": "Planning research strategy"}
    })
    await asyncio.sleep(2)

    # Add searching event
    research_runs[run_id]["events"].append({
        "type": "phase",
        "data": {"phase": "searching", "message": "Searching for information"}
    })
    await asyncio.sleep(2)

    # Add writing event
    research_runs[run_id]["events"].append({
        "type": "phase",
        "data": {"phase": "writing", "message": "Writing research report"}
    })
    await asyncio.sleep(2)

    # Mark as completed
    research_runs[run_id]["status"] = "completed"
    research_runs[run_id]["events"].append({
        "type": "complete",
        "data": {"message": "Research completed successfully"}
    })
