"""Structured extraction of astrophysics-oriented content from a paper."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .paper import PaperIdentity


class PaperAnalysis(BaseModel):
    """Astrophysics-specific structured analysis of a single paper."""

    model_config = ConfigDict(extra="forbid")

    paper: PaperIdentity = Field(default_factory=PaperIdentity)
    observables: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    missions: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(
        default_factory=list,
        description="Cosmological or astrophysical parameters discussed or constrained.",
    )
    redshift_range: str | None = Field(
        default=None,
        description="Human-readable redshift range, e.g. '0 < z < 2' or 'z ~ 1100'.",
    )
    wavelength_band: str | None = Field(
        default=None,
        description="Rest or observed band, e.g. '21 cm', '0.5–2 keV', '450 μm'.",
    )
    cosmological_model: str | None = Field(
        default=None,
        description="ΛCDM variant, wCDM, etc., as stated or assumed in the paper.",
    )
    systematics: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    key_results: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
