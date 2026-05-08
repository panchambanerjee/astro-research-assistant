"""Paper analyzer agent scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from schemas.paper import PaperMetadata
from schemas.paper_analysis import PaperAnalysis

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "paper_analysis.md"


class PaperAnalyzerAgentSpec(BaseModel):
    """Static agent metadata for paper analysis."""

    name: str = "paper_analyzer"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = PaperAnalysis.__name__


def load_prompt() -> str:
    """Load paper-analysis system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(
    paper: PaperMetadata,
    paper_text_excerpt: str,
    user_topic: str | None = None,
) -> str:
    """Build analysis payload for LLM execution."""
    topic_line = f"User topic: {user_topic}\n\n" if user_topic else ""
    return (
        f"{topic_line}"
        f"Paper metadata:\n{paper.model_dump_json(indent=2)}\n\n"
        f"Paper text excerpt:\n{paper_text_excerpt.strip()}\n\n"
        'Return a valid PaperAnalysis object. Use "not extracted" when needed.'
    )
