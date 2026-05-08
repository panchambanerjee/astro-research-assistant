"""Topic expansion agent scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from schemas.topic_expansion import TopicExpansion

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "topic_expansion.md"


class TopicExpanderAgentSpec(BaseModel):
    """Static agent metadata for topic expansion."""

    name: str = "topic_expander"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = TopicExpansion.__name__


def load_prompt() -> str:
    """Load topic-expansion system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(topic: str) -> str:
    """Build user payload for the topic expansion prompt."""
    return f"User topic:\n{topic.strip()}\n\nReturn a valid TopicExpansion object."
