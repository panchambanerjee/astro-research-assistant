"""Topic profile: structured interpretation of the user's research topic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileSource = Literal["ontology", "ontology+web", "fixture", "manual"]

PaperRole = Literal[
    "direct_evidence",
    "theory_interpretation",
    "method_or_instrument",
    "background_review",
    "off_topic",
]


class ConditionalNegativeBlock(BaseModel):
    """Penalize negative_terms in paper text unless at least one allow_if phrase is present."""

    model_config = ConfigDict(extra="forbid")

    negative_terms: list[str] = Field(default_factory=list)
    allow_if: list[str] = Field(default_factory=list)


class TopicProfile(BaseModel):
    """What the user is asking about (distinct from TopicExpansion and PaperAnalysis)."""

    model_config = ConfigDict(extra="forbid")

    original_topic: str
    profile_version: str = "0.1"
    source: ProfileSource = "ontology"

    primary_domain: str | None = None
    subdomains: list[str] = Field(default_factory=list)
    phenomena: list[str] = Field(default_factory=list)
    observables: list[str] = Field(default_factory=list)
    probes: list[str] = Field(default_factory=list)
    surveys_or_missions: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    systematics: list[str] = Field(default_factory=list)
    expected_paper_types: list[str] = Field(default_factory=list)

    arxiv_categories: list[str] = Field(default_factory=list)
    paper_role_hints: dict[str, list[str]] = Field(default_factory=dict)
    relevance_weights: dict[str, float] = Field(default_factory=dict)

    negative_topics: list[str] = Field(default_factory=list)
    conditional_allow_terms: list[str] = Field(default_factory=list)
    conditional_negatives: list[ConditionalNegativeBlock] = Field(default_factory=list)

    matched_terms: dict[str, list[str]] = Field(default_factory=dict)
    profile_confidence: float | None = None
