"""Field synthesis agent scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from schemas.paper_analysis import PaperAnalysis
from schemas.synthesis import FieldSynthesis

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "synthesis.md"


class SynthesisAgentSpec(BaseModel):
    """Static agent metadata for synthesis."""

    name: str = "synthesis_agent"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = FieldSynthesis.__name__


def load_prompt() -> str:
    """Load synthesis system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(topic: str, analyses: list[PaperAnalysis]) -> str:
    """Build synthesis payload from structured paper analyses."""
    analyses_json = [analysis.model_dump(mode="json") for analysis in analyses]
    return (
        f"Topic: {topic.strip()}\n\n"
        f"Structured analyses (JSON):\n{analyses_json}\n\n"
        "Return a valid FieldSynthesis object with clear Evidence from papers vs Assistant inference."
    )
