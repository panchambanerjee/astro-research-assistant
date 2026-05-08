"""Schema for expanded topic decomposition used by retrieval planning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TopicExpansion(BaseModel):
    """Structured topic expansion for astronomy/cosmology retrieval."""

    model_config = ConfigDict(extra="forbid")

    original_topic: str
    canonical_queries: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    observables: list[str] = Field(default_factory=list)
    surveys: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    systematics: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    subfields: list[str] = Field(default_factory=list)
    arxiv_categories: list[str] = Field(default_factory=list)
