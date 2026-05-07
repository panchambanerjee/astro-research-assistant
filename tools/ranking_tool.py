"""Deterministic ranking utilities for candidate papers."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from schemas.paper import PaperMetadata, RankedPaper

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_TOKEN_RE.findall(text.lower()))


def _selected_citation_count(paper: PaperMetadata) -> int:
    if paper.citation_counts.selected is not None:
        return max(0, paper.citation_counts.selected)
    if paper.citation_counts.ads is not None:
        return max(0, paper.citation_counts.ads)
    if paper.citation_counts.semantic_scholar is not None:
        return max(0, paper.citation_counts.semantic_scholar)
    if paper.citation_counts.openalex is not None:
        return max(0, paper.citation_counts.openalex)
    return 0


def _paper_type_multiplier(paper: PaperMetadata) -> float:
    if paper.paper_type == "review":
        return 0.85
    if paper.paper_type in {"survey_data_release", "methodology", "observational_constraint"}:
        return 1.05
    return 1.0


def _source_confidence_score(paper: PaperMetadata) -> float:
    confidence = 0.0
    if paper.doi:
        confidence += 0.4
    if paper.arxiv_id:
        confidence += 0.2
    if paper.ads_bibcode:
        confidence += 0.2
    if paper.semantic_scholar_id or paper.openalex_id:
        confidence += 0.2
    return min(1.0, confidence)


def _relevance_score(paper: PaperMetadata, topic: str) -> float:
    topic_tokens = _tokenize(topic)
    if not topic_tokens:
        return 0.0

    title_tokens = _tokenize(paper.title)
    abstract_tokens = _tokenize(paper.abstract)
    if not title_tokens and not abstract_tokens:
        return 0.0

    title_overlap = len(topic_tokens & title_tokens) / len(topic_tokens)
    abstract_overlap = len(topic_tokens & abstract_tokens) / len(topic_tokens)
    # Bias toward title signal, but include abstract.
    return min(1.0, (0.7 * title_overlap) + (0.3 * abstract_overlap))


def _recency_score(paper: PaperMetadata, current_year: int) -> float:
    if paper.year is None:
        return 0.0
    age = max(0, current_year - paper.year)
    return 1.0 / (1.0 + (age / 8.0))


def _velocity_raw(paper: PaperMetadata, current_year: int) -> float:
    citations = _selected_citation_count(paper)
    if citations <= 0:
        return 0.0
    if paper.year is None:
        years_active = 10
    else:
        years_active = max(1, current_year - paper.year + 1)
    return citations / years_active


def _log_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    vmax = max(values)
    if vmax <= 0:
        return [0.0 for _ in values]
    denom = math.log1p(vmax)
    return [math.log1p(max(0.0, v)) / denom for v in values]


def rank_papers(
    papers: list[PaperMetadata],
    topic: str,
    current_year: int | None = None,
) -> list[RankedPaper]:
    """Rank papers deterministically using citation, velocity, recency, and lexical relevance."""
    if not papers:
        return []

    if current_year is None:
        current_year = datetime.now(timezone.utc).year

    citation_raw = [float(_selected_citation_count(p)) for p in papers]
    velocity_raw = [_velocity_raw(p, current_year) for p in papers]

    citation_scores = _log_normalize(citation_raw)
    velocity_scores = _log_normalize(velocity_raw)

    ranked: list[RankedPaper] = []
    for i, paper in enumerate(papers):
        relevance_score = _relevance_score(paper, topic)
        recency_score = _recency_score(paper, current_year)
        source_confidence = _source_confidence_score(paper)
        multiplier = _paper_type_multiplier(paper)

        base_score = (
            (0.35 * citation_scores[i])
            + (0.25 * velocity_scores[i])
            + (0.20 * recency_score)
            + (0.20 * relevance_score)
        )
        final_score = base_score * multiplier

        ranked.append(
            RankedPaper(
                metadata=paper,
                relevance_score=relevance_score,
                citation_score=citation_scores[i],
                velocity_score=velocity_scores[i],
                recency_score=recency_score,
                source_confidence_score=source_confidence,
                final_score=final_score,
            )
        )

    ranked.sort(key=lambda r: (-r.final_score, -r.citation_score, r.metadata.title or ""))
    for idx, item in enumerate(ranked, start=1):
        item.rank = idx
        item.ranking_bucket = "candidate"
        item.ranking_reason = (
            f"score={item.final_score:.3f}; "
            f"citation={item.citation_score:.3f}, "
            f"velocity={item.velocity_score:.3f}, "
            f"recency={item.recency_score:.3f}, "
            f"relevance={item.relevance_score:.3f}"
        )
    return ranked


def select_canonical_papers(ranked: list[RankedPaper], n: int = 10) -> list[RankedPaper]:
    """Select top canonical papers from ranked candidates."""
    selected = [r.model_copy(deep=True) for r in sorted(ranked, key=lambda r: r.rank or 10**9)[: max(0, n)]]
    for paper in selected:
        paper.ranking_bucket = "canonical"
    return selected


def select_recent_high_signal_papers(
    ranked: list[RankedPaper],
    n: int = 5,
    year_window: int = 5,
) -> list[RankedPaper]:
    """Select recent high-signal papers within a year window."""
    if not ranked or n <= 0:
        return []

    years = [r.metadata.year for r in ranked if r.metadata.year is not None]
    reference_year = max(years) if years else datetime.now(timezone.utc).year
    min_year = reference_year - max(0, year_window)

    recent = [r for r in ranked if (r.metadata.year or 0) >= min_year]
    recent.sort(key=lambda r: (-r.final_score, r.rank or 10**9))
    selected = [r.model_copy(deep=True) for r in recent[:n]]
    for paper in selected:
        paper.ranking_bucket = "recent_high_signal"
    return selected
