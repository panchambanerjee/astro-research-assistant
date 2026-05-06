"""Paper-related Pydantic models: identity, bibliographic metadata, retrieval, ranking."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PaperType = Literal["article", "preprint", "proceedings", "thesis", "book", "other"]


class PaperIdentity(BaseModel):
    """Minimal cross-database identifiers for a physics paper."""

    model_config = ConfigDict(extra="forbid")

    arxiv_id: str | None = None
    doi: str | None = None
    ads_bibcode: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None


class CitationCounts(BaseModel):
    """Citation counts by source; values must come from APIs or stored metadata (never invented)."""

    model_config = ConfigDict(extra="forbid")

    ads: int | None = None
    openalex: int | None = None
    semantic_scholar: int | None = None


class PaperMetadata(PaperIdentity):
    """Full bibliographic and retrieval metadata (identifiers plus bibliographic fields)."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    citation_counts: CitationCounts = Field(default_factory=CitationCounts)
    abstract: str | None = None
    pdf_url: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    paper_type: PaperType | None = None


class PaperCandidate(BaseModel):
    """A paper returned from search/retrieval before full ranking merge."""

    model_config = ConfigDict(extra="forbid")

    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    relevance_score: float | None = Field(
        default=None,
        description="Retrieval / embedding relevance (not citation count).",
    )
    source_tool: str | None = Field(
        default=None,
        description="Which tool produced this candidate (e.g. ads, arxiv).",
    )


class RankedPaper(BaseModel):
    """Candidate after deterministic ranking; includes final combined score."""

    model_config = ConfigDict(extra="forbid")

    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    relevance_score: float | None = Field(
        default=None,
        description="Retrieval relevance component used in ranking.",
    )
    final_score: float | None = Field(
        default=None,
        description="Deterministic combined rank score.",
    )
    rank: int | None = Field(default=None, description="1-based position after sorting.")
