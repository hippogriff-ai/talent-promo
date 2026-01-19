import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

# ============================================================================
# CRITICAL: Load .env and configure LangSmith BEFORE any LangChain imports
# LangSmith tracing checks env vars at import time, not runtime
# ============================================================================
from dotenv import load_dotenv

# Find and load .env file
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent
for env_path in [_project_root / ".env", _current_dir / ".env", Path.cwd() / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        break

# Set LangSmith env vars that the SDK expects (must be before LangChain imports)
if os.getenv("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "talent-promo"))

# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to Python path to import temporal module
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Note: Using absolute import from routers for compatibility with pytest pythonpath config
# When running the API, use: cd apps/api && uvicorn main:app --reload
from routers import agents, documents, jobs, research, research_agent, optimize, arena, filesystem  # noqa: E402

logger = logging.getLogger(__name__)

# Log LangSmith status (tracing already configured above)
if os.getenv("LANGSMITH_API_KEY"):
    logger.info(f"LangSmith tracing enabled for project: {os.getenv('LANGSMITH_PROJECT')}")
else:
    logger.warning("LANGSMITH_API_KEY not set - LangSmith tracing disabled")


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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3004",
        "http://localhost:3005",
        "http://localhost:3006",
        "http://localhost:3007",
        "http://localhost:3008",
        "http://localhost:3009",
        "http://localhost:3010",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents.router)
app.include_router(research.router)
app.include_router(research_agent.router)
app.include_router(jobs.router)
app.include_router(documents.router)
app.include_router(optimize.router)  # LangGraph resume optimization workflow
app.include_router(arena.router)  # Arena A/B comparison
app.include_router(filesystem.router)  # Virtual filesystem with Linux-like commands


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Talent Promo API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
