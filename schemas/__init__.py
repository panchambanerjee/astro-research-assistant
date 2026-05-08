"""Pydantic schemas for structured research assistant I/O."""

from .hypothesis import ResearchHypothesis
from .paper import (
    CitationCounts,
    PaperCandidate,
    PaperIdentity,
    PaperMetadata,
    RankedPaper,
)
from .paper_analysis import PaperAnalysis
from .report import ResearchReport
from .synthesis import FieldSynthesis
from .topic_expansion import TopicExpansion

__all__ = [
    "CitationCounts",
    "FieldSynthesis",
    "PaperAnalysis",
    "PaperCandidate",
    "PaperIdentity",
    "PaperMetadata",
    "RankedPaper",
    "ResearchHypothesis",
    "ResearchReport",
    "TopicExpansion",
]
