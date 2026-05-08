"""Application configuration loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for CLI and tool integrations."""

    openalex_mailto: str | None
    nasa_ads_api_key: str | None
    semantic_scholar_api_key: str | None
    openai_api_key: str | None
    llm_model: str


def load_config() -> AppConfig:
    """Load app configuration from environment variables."""
    return AppConfig(
        openalex_mailto=os.getenv("OPENALEX_MAILTO"),
        nasa_ads_api_key=os.getenv("NASA_ADS_API_KEY"),
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
    )
