import logging
import os
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

from routers import documents, optimize, preferences, ratings
from services.thread_metadata import get_metadata_service

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

    # Start the thread cleanup background task (2h TTL)
    metadata_service = get_metadata_service()
    metadata_service.start_cleanup_task()
    logger.info("Thread cleanup task started (2h TTL)")

    logger.info("API ready to accept requests")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down Talent Promo API...")

    # Stop thread cleanup task
    metadata_service.stop_cleanup_task()
    logger.info("Thread cleanup task stopped")

    logger.info("API shutdown complete")


app = FastAPI(
    title="Talent Promo API",
    description="API for helping talent present themselves",
    version="0.1.0",
    lifespan=lifespan,
)

# No CORS middleware needed — Next.js BFF proxies all browser requests.
# FastAPI is never directly exposed to the browser.

# Include routers
app.include_router(documents.router)
app.include_router(optimize.router)  # LangGraph resume optimization workflow
app.include_router(preferences.router)  # User preferences (anonymous)
app.include_router(ratings.router)  # Draft ratings (anonymous)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Talent Promo API"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
