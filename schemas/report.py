"""End-user research report bundling synthesis, analyses, and hypotheses."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from .hypothesis import ResearchHypothesis
from .paper import PaperMetadata
from .paper_analysis import PaperAnalysis
from .synthesis import FieldSynthesis


class ResearchReport(BaseModel):
    """Deliverable report with explicit links to source papers and structured sections."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="Research report")
    query_or_brief: str = Field(
        default="",
        description="Original user question or research brief.",
    )
    executive_summary: str = Field(default="")
    field_syntheses: list[FieldSynthesis] = Field(default_factory=list)
    paper_analyses: list[PaperAnalysis] = Field(default_factory=list)
    hypotheses: list[ResearchHypothesis] = Field(default_factory=list)
    cited_papers: list[PaperMetadata] = Field(
        default_factory=list,
        description="Bibliography-style entries; metadata from APIs or stored files only.",
    )
    evidence_gaps: list[str] = Field(
        default_factory=list,
        description="Claims that could not be tied to retrieved papers.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of report generation.",
    )
    wiki_paths_updated: list[str] = Field(
        default_factory=list,
        description="Optional relative paths under storage/wiki/ that were written.",
    )
