"""Report compiler agent scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from schemas.report import ResearchReport

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "report_compilation.md"


class ReportCompilerAgentSpec(BaseModel):
    """Static agent metadata for report compilation."""

    name: str = "report_compiler"
    prompt_path: str = str(PROMPT_PATH)
    output_schema: str = ResearchReport.__name__


def load_prompt() -> str:
    """Load report-compilation system prompt from disk."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_user_payload(
    topic: str,
    selected_papers_json: str,
    analyses_json: str,
    synthesis_json: str,
    validated_hypotheses_json: str,
) -> str:
    """Build report-compilation payload."""
    return (
        f"Topic: {topic.strip()}\n\n"
        f"Selected papers:\n{selected_papers_json}\n\n"
        f"Paper analyses:\n{analyses_json}\n\n"
        f"Field synthesis:\n{synthesis_json}\n\n"
        f"Validated hypotheses:\n{validated_hypotheses_json}\n\n"
        "Return a valid ResearchReport object."
    )
