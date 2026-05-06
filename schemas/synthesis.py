"""Cross-paper synthesis for a subfield, observable, or concept."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .paper import PaperIdentity


class FieldSynthesis(BaseModel):
    """Aggregated view over multiple papers for one thematic slice of the literature."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(..., description="Concept, survey, or science question label.")
    summary: str = Field(default="", description="Concise synthesis of consensus and tension.")
    consensus_points: list[str] = Field(default_factory=list)
    tensions_or_disagreements: list[str] = Field(default_factory=list)
    primary_sources: list[PaperIdentity] = Field(
        default_factory=list,
        description="Key papers backing the synthesis (identifiers from metadata APIs).",
    )
    open_questions: list[str] = Field(default_factory=list)
    limitations_of_synthesis: list[str] = Field(
        default_factory=list,
        description="Coverage gaps, selection effects, or caveats in this synthesis pass.",
    )
