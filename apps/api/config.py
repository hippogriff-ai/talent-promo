"""Configuration for the Talent Promo API."""

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Find project root by looking for .env file
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent  # apps/api -> apps -> project root

# Look for .env in multiple locations
ENV_LOCATIONS = [
    PROJECT_ROOT / ".env",  # Project root
    CURRENT_DIR / ".env",  # apps/api/
    Path.cwd() / ".env",  # Current working directory
]

# Find the first .env that exists
ENV_FILE = None
for env_path in ENV_LOCATIONS:
    if env_path.exists():
        ENV_FILE = env_path
        break


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"  # Default model with structured outputs support
    openai_timeout: int = 60

    # Anthropic Configuration (for LangGraph)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # EXA Configuration
    exa_api_key: str = ""

    # LangSmith Configuration (for tracing/monitoring)
    langsmith_api_key: str = ""
    langsmith_project: str = "talent-promo"
    langsmith_tracing: bool = True

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()  # type: ignore[call-arg]

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if ENV_FILE:
        logger.info(f"Loaded config from: {ENV_FILE}")
    else:
        logger.warning("No .env file found, using environment variables only")

    logger.info(f"Settings loaded: model={settings.anthropic_model}")

    return settings
