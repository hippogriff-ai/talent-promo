import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to Python path to import temporal module
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Note: Using absolute import from routers for compatibility with pytest pythonpath config
# When running the API, use: cd apps/api && uvicorn main:app --reload
from routers import agents, research, research_agent, jobs  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Talent Promo API...")
    logger.info("API ready to accept requests")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down Talent Promo API...")
    # Close Temporal client if initialized
    if research_agent._temporal_client:
        try:
            logger.info("Closing Temporal client...")
            # Note: Temporal Python SDK clients don't need explicit close in current version
            # The connection will be closed when the process exits
            research_agent._temporal_client = None
        except Exception as e:
            logger.error(f"Error during Temporal client cleanup: {e}")
    logger.info("API shutdown complete")


app = FastAPI(
    title="Talent Promo API",
    description="API for helping talent present themselves",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents.router)
app.include_router(research.router)
app.include_router(research_agent.router)
app.include_router(jobs.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Talent Promo API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
