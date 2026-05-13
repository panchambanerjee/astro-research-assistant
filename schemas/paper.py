"""Paper-related Pydantic models: identity, bibliographic metadata, retrieval, ranking."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PublicationType = Literal[
    "journal_article",
    "preprint",
    "conference_proceedings",
    "thesis",
    "book",
    "review_article",
    "other",
]

AstroPaperType = Literal[
    "review",
    "theory",
    "simulation",
    "observational_constraint",
    "survey_data_release",
    "instrumentation",
    "catalog",
    "methodology",
    "forecast",
    "tension_discrepancy",
    "parameter_inference",
    "other",
]


class PaperIdentity(BaseModel):
    """Cross-database identifiers for a scientific paper."""

    model_config = ConfigDict(extra="forbid")

    arxiv_id: str | None = None
    doi: str | None = None
    ads_bibcode: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    corpus_id: str | None = None


class CitationCounts(BaseModel):
    """Citation counts by source; values must come from APIs or stored metadata."""

    model_config = ConfigDict(extra="forbid")

    ads: int | None = None
    openalex: int | None = None
    semantic_scholar: int | None = None

    selected: int | None = None
    selected_source: str | None = None


class PaperMetadata(PaperIdentity):
    """Bibliographic, retrieval, and domain metadata for a paper."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    publication_date: str | None = None

    abstract: str | None = None
    journal: str | None = None
    venue: str | None = None

    publication_type: PublicationType | None = None
    paper_type: AstroPaperType = "other"

    citation_counts: CitationCounts = Field(default_factory=CitationCounts)

    pdf_url: str | None = None
    landing_page_url: str | None = None
    source_url: str | None = None

    fields_of_study: list[str] = Field(default_factory=list)
    arxiv_categories: list[str] = Field(default_factory=list)

    datasets: list[str] = Field(default_factory=list)
    observables: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    missions: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    systematics: list[str] = Field(default_factory=list)

    source_tools: list[str] = Field(default_factory=list)


class PaperCandidate(BaseModel):
    """A paper returned from search/retrieval before full ranking and merging."""

    model_config = ConfigDict(extra="forbid")

    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Retrieval, lexical, or embedding relevance score.",
    )
    source_tool: str | None = Field(
        default=None,
        description="Tool that produced this candidate, e.g. ads, arxiv, openalex.",
    )


class RankedPaper(BaseModel):
    """Paper after deterministic ranking."""

    model_config = ConfigDict(extra="forbid")

    metadata: PaperMetadata = Field(default_factory=PaperMetadata)

    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    velocity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    final_score: float = Field(default=0.0, ge=0.0)
    rank: int | None = Field(default=None, ge=1)

    ranking_bucket: Literal["primary", "recent_high_signal", "candidate"] = "candidate"
    ranking_reason: str | None = None
