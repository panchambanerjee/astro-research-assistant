"""Research hypotheses derived from literature and synthesis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .paper import PaperIdentity

HypothesisStatus = Literal["draft", "refined", "challenged", "supported", "retired"]
HypothesisValidationStatus = Literal["validated", "plausible", "rejected"]


class ResearchHypothesis(BaseModel):
    """A testable hypothesis grounded in cited work."""

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(..., description="Clear, falsifiable hypothesis statement.")
    rationale: str = Field(
        default="",
        description="Why this hypothesis is suggested by evidence or synthesis.",
    )
    supporting_evidence_papers: list[PaperIdentity] = Field(
        default_factory=list,
        description="Papers that motivate or support the hypothesis (metadata from APIs only).",
    )
    status: HypothesisStatus = "draft"
    validation_status: HypothesisValidationStatus = "plausible"
    grounding_notes: str = Field(
        default="",
        description=(
            "How this status was assigned. 'validated' requires mechanism evidence in extracted analyses."
        ),
    )
    evidence_basis: list[str] = Field(
        default_factory=list,
        description="Explicit evidence snippets or extracted analysis claims supporting the status.",
    )
    display_rank: int | None = Field(
        default=None,
        ge=1,
        description="Display-only hypothesis ordering in final report output.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional qualitative confidence as 0–1 (assistant-inferred, not a paper metric).",
    )
    falsification_ideas: list[str] = Field(
        default_factory=list,
        description="Observations or analyses that could rule the hypothesis out.",
    )
    proposed_test: str | None = None
    required_data: list[str] = Field(default_factory=list)
    required_method: list[str] = Field(default_factory=list)
    falsification_criteria: list[str] = Field(default_factory=list)
    novelty_score: int | None = Field(default=None, ge=1, le=5)
    testability_score: int | None = Field(default=None, ge=1, le=5)
    data_availability_score: int | None = Field(default=None, ge=1, le=5)
    impact_score: int | None = Field(default=None, ge=1, le=5)
    difficulty_score: int | None = Field(default=None, ge=1, le=5)
    already_done_risk: int | None = Field(default=None, ge=1, le=5)
