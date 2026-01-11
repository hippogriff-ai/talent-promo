"""LangSmith and LangGraph configuration."""

import os
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Configure LangSmith for tracing and deployment.

    Required environment variables:
    - LANGSMITH_TRACING: Set to "true" to enable tracing
    - LANGSMITH_API_KEY: Your LangSmith API key
    - LANGSMITH_PROJECT: Project name in LangSmith (default: talent-promo)

    Note: Also uses config.get_settings() which loads from .env file via Pydantic.
    """
    # Try to get from Pydantic Settings first (loads from .env)
    api_key = None
    project = "talent-promo"

    try:
        from config import get_settings
        settings = get_settings()
        api_key = settings.langsmith_api_key
        project = settings.langsmith_project or project
    except Exception:
        pass

    # Fallback to os.getenv for backwards compatibility
    if not api_key:
        api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")

    if api_key:
        # Set the env vars that LangSmith SDK expects
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", project)
        logger.info(f"LangSmith tracing enabled for project: {project}")
    else:
        logger.warning("LANGSMITH_API_KEY not set - LangSmith tracing disabled")


@lru_cache
def get_langsmith_client():
    """Get a cached LangSmith client instance."""
    try:
        from langsmith import Client
        return Client()
    except Exception as e:
        logger.warning(f"Failed to create LangSmith client: {e}")
        return None
