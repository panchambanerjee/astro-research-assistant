"""Skeptical referee agent scaffold for filtering hypotheses."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from schemas.hypothesis import ResearchHypothesis

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "skeptical_review.md"


class ValidatedHypotheses(BaseModel):
    """Structured output of referee-approved hypotheses."""

    model_config = ConfigDict(extra="forbid")
    validated: list[ResearchHypothesis] = Field(default_factory=list)


class SkepticalRefereeAgentSpec(BaseModel):
    """Static agent metadata for skeptical review."""

    name: str = "skeptical_referee"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = ValidatedHypotheses.__name__


def load_prompt() -> str:
    """Load skeptical-review system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(hypotheses: list[ResearchHypothesis]) -> str:
    """Build skeptical-review payload."""
    payload = [hyp.model_dump(mode="json") for hyp in hypotheses]
    return (
        f"Hypotheses to review:\n{payload}\n\n"
        "Return only validated hypotheses as a valid ValidatedHypotheses object."
    )
