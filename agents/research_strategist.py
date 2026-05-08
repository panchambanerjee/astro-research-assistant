"""Research strategist (hypothesis generation) agent scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from schemas.hypothesis import ResearchHypothesis
from schemas.synthesis import FieldSynthesis

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "hypothesis_generation.md"


class HypothesisBatch(BaseModel):
    """Structured output wrapper for generated hypotheses."""

    model_config = ConfigDict(extra="forbid")
    hypotheses: list[ResearchHypothesis] = Field(default_factory=list)


class ResearchStrategistAgentSpec(BaseModel):
    """Static agent metadata for hypothesis generation."""

    name: str = "research_strategist"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = HypothesisBatch.__name__


def load_prompt() -> str:
    """Load hypothesis-generation system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(topic: str, synthesis: FieldSynthesis) -> str:
    """Build hypothesis-generation payload."""
    return (
        f"User topic: {topic.strip()}\n\n"
        f"Field synthesis:\n{synthesis.model_dump_json(indent=2)}\n\n"
        "Return hypotheses as a valid HypothesisBatch object."
    )
