"""Deterministic ranking utilities for candidate papers."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from schemas.paper import PaperMetadata, RankedPaper
from schemas.topic_profile import TopicProfile

_TOKEN_RE = re.compile(r"[a-z0-9]+")
JWST_HIGHZ_TERMS: dict[str, float] = {
    "jwst": 3.0,
    "james webb": 3.0,
    "high redshift": 3.0,
    "high-z": 3.0,
    "z >": 2.5,
    "z~": 1.5,
    "massive galaxies": 3.0,
    "massive galaxy": 3.0,
    "stellar mass": 2.5,
    "stellar mass density": 3.0,
    "nircam": 2.5,
    "nirspec": 2.5,
    "ceers": 2.5,
    "jades": 2.5,
    "glass-jwst": 2.5,
    "uncover": 2.5,
    "cosmos-web": 2.0,
    "quiescent galaxies": 2.0,
    "luminosity function": 1.5,
    "stellar mass function": 2.5,
    "reionization": 1.0,
}
NEGATIVE_TERMS: dict[str, float] = {
    "axion": -5.0,
    "dark matter only": -1.0,
    "exoplanet": -4.0,
    "planetary": -3.0,
    "cell migration": -8.0,
    "biology": -8.0,
    "medicine": -5.0,
}
DARK_ENERGY_TERMS: dict[str, float] = {
    "dark energy": 4.0,
    "equation of state": 3.0,
    "w0": 2.5,
    "wa": 2.5,
    "wcdm": 2.5,
    "cpl": 2.0,
    "rho_de": 2.0,
    "cosmological constant": 2.0,
    "lambda": 1.0,
    "supernova": 2.0,
    "type ia": 2.0,
    "sne ia": 2.0,
    "bao": 2.0,
    "baryon acoustic": 2.0,
    "desi": 2.0,
    "eboss": 2.0,
    "pantheon": 2.0,
    "union2": 1.5,
    "planck": 1.5,
    "hubble diagram": 2.0,
    "distance modulus": 1.5,
    "expansion history": 3.0,
    "time evolution": 2.0,
    "dynamical dark energy": 3.5,
}
DARK_ENERGY_NEGATIVE_TERMS: dict[str, float] = {
    "binary black hole": -6.0,
    "gravitational waves from a binary black hole merger": -8.0,
    "ligo": -4.0,
    "gw150914": -8.0,
    "stellar-mass black hole": -5.0,
}


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


def _paper_text_for_scoring(paper: PaperMetadata) -> str:
    return " ".join(
        [
            paper.title or "",
            paper.abstract or "",
            paper.journal or "",
            paper.venue or "",
            " ".join(paper.fields_of_study or []),
            " ".join(paper.arxiv_categories or []),
        ]
    ).lower()


def _rw(weights: dict[str, float], key: str, default: float) -> float:
    v = weights.get(key)
    return float(v) if v is not None else default


def profile_relevance_score(paper: PaperMetadata, profile: TopicProfile) -> float:
    """Deterministic relevance from TopicProfile vocabulary and conditional negatives."""
    text = _paper_text_for_scoring(paper)
    raw = _relevance_score(paper, profile.original_topic) * 4.0
    weights = profile.relevance_weights or {}

    weighted_lists: tuple[tuple[str, list[str]], ...] = (
        ("observables", profile.observables),
        ("probes", profile.probes),
        ("surveys", profile.surveys_or_missions),
        ("parameters", profile.parameters),
        ("methods", profile.methods),
        ("systematics", profile.systematics),
        ("phenomena", profile.phenomena),
        ("instruments", profile.instruments),
        ("subdomains", profile.subdomains),
    )
    for key, lst in weighted_lists:
        inc = _rw(weights, key, 1.8)
        for phrase in lst:
            pl = phrase.lower()
            if len(pl) >= 2 and pl in text:
                raw += inc

    neg_w = _rw(weights, "negative_topics", -5.0)
    for neg in profile.negative_topics:
        if neg.lower() in text:
            raw += neg_w

    for block in profile.conditional_negatives:
        allow_hit = any(a.lower() in text for a in block.allow_if)
        if allow_hit:
            continue
        for neg in block.negative_terms:
            if neg.lower() in text:
                raw -= 7.0

    rescued = bool(profile.conditional_allow_terms) and any(
        a.lower() in text for a in profile.conditional_allow_terms
    )
    if rescued:
        raw += 5.5

    if "gravitational wave" in text and profile.primary_domain == "cosmology" and not rescued:
        raw -= 5.5

    return max(0.0, min(1.0, raw / 14.0))


def topic_relevance_score(
    paper: PaperMetadata,
    topic: str,
    *,
    topic_profile: TopicProfile | None = None,
    extra_negative_terms: list[str] | None = None,
) -> float:
    """Weighted topic relevance score with optional negative-term penalties."""
    text = _paper_text_for_scoring(paper)

    if topic_profile is not None:
        score = profile_relevance_score(paper, topic_profile) * 10.0
    else:
        topic_l = topic.lower()
        score = _relevance_score(paper, topic) * 4.0
        if any(term in topic_l for term in ("jwst", "high z", "high-z", "high redshift", "massive")):
            for term, weight in JWST_HIGHZ_TERMS.items():
                if term in text:
                    score += weight
        if any(term in topic_l for term in ("dark energy", "w0", "wa", "equation of state", "expansion")):
            for term, weight in DARK_ENERGY_TERMS.items():
                if term in text:
                    score += weight
            for term, penalty in DARK_ENERGY_NEGATIVE_TERMS.items():
                if term in text:
                    score += penalty
            if "gravitational wave" in text and "dark energy" not in text and "standard siren" not in text:
                score -= 6.0

    penalties = dict(NEGATIVE_TERMS)
    for term in extra_negative_terms or []:
        penalties.setdefault(term.lower(), -3.0)
    for term, penalty in penalties.items():
        if term in text:
            score += penalty

    return max(0.0, min(1.0, score / 10.0))


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
    negative_terms: list[str] | None = None,
    *,
    topic_profile: TopicProfile | None = None,
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
        relevance_score = topic_relevance_score(
            paper,
            topic=topic,
            topic_profile=topic_profile,
            extra_negative_terms=negative_terms,
        )
        recency_score = _recency_score(paper, current_year)
        source_confidence = _source_confidence_score(paper)
        multiplier = _paper_type_multiplier(paper)

        base_score = (
            (0.50 * relevance_score)
            + (0.25 * citation_scores[i])
            + (0.15 * source_confidence)
            + (0.10 * recency_score)
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


def select_primary_papers(ranked: list[RankedPaper], n: int = 10) -> list[RankedPaper]:
    """Select top primary papers from ranked candidates."""
    selected = [r.model_copy(deep=True) for r in sorted(ranked, key=lambda r: r.rank or 10**9)[: max(0, n)]]
    for paper in selected:
        paper.ranking_bucket = "primary"
    return selected


def select_canonical_papers(ranked: list[RankedPaper], n: int = 10) -> list[RankedPaper]:
    """Deprecated alias for :func:`select_primary_papers`."""
    return select_primary_papers(ranked, n=n)


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
    recent.sort(
        key=lambda r: (
            -(0.50 * r.relevance_score + 0.25 * r.recency_score + 0.15 * r.velocity_score + 0.10 * r.citation_score),
            r.rank or 10**9,
        )
    )
    selected = [r.model_copy(deep=True) for r in recent[:n]]
    for paper in selected:
        paper.ranking_bucket = "recent_high_signal"
    return selected
