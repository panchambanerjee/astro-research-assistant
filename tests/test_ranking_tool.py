from schemas.paper import CitationCounts, PaperMetadata
from tools.ranking_tool import (
    rank_papers,
    select_canonical_papers,
    select_recent_high_signal_papers,
)


def test_rank_papers_returns_ranked_and_sorted() -> None:
    papers = [
        PaperMetadata(
            title="Planck cosmology constraints",
            abstract="cmb planck cosmology constraints",
            year=2018,
            paper_type="observational_constraint",
            citation_counts=CitationCounts(selected=600),
            doi="10.1/a",
            ads_bibcode="2018A&A...641A...6P",
        ),
        PaperMetadata(
            title="A review of weak lensing in cosmology",
            abstract="review weak lensing cosmology",
            year=2020,
            paper_type="review",
            citation_counts=CitationCounts(selected=600),
            doi="10.1/b",
        ),
    ]

    ranked = rank_papers(papers, topic="planck weak lensing cosmology", current_year=2025)

    assert len(ranked) == 2
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
    assert ranked[0].final_score >= ranked[1].final_score
    # Same citations, but review gets downweighted by multiplier.
    assert ranked[0].metadata.paper_type == "observational_constraint"
    assert ranked[1].metadata.paper_type == "review"


def test_citation_priority_and_velocity_affect_ranking() -> None:
    high_velocity = PaperMetadata(
        title="Recent high-impact measurement",
        abstract="measurement results",
        year=2024,
        citation_counts=CitationCounts(selected=120),
    )
    old_high_citation = PaperMetadata(
        title="Older foundational paper",
        abstract="foundational results",
        year=2010,
        citation_counts=CitationCounts(selected=300),
    )
    low_signal = PaperMetadata(
        title="Low signal",
        abstract="",
        year=2023,
        citation_counts=CitationCounts(selected=2),
    )

    ranked = rank_papers(
        [high_velocity, old_high_citation, low_signal],
        topic="measurement results",
        current_year=2025,
    )
    assert ranked[0].final_score >= ranked[1].final_score >= ranked[2].final_score
    assert ranked[0].citation_score >= 0.0
    assert ranked[0].velocity_score >= 0.0
    assert ranked[0].recency_score >= 0.0
    assert ranked[0].relevance_score >= 0.0


def test_selection_helpers_assign_buckets() -> None:
    papers = [
        PaperMetadata(title=f"Paper {i}", year=2025 - i, citation_counts=CitationCounts(selected=100 - i * 5))
        for i in range(8)
    ]
    ranked = rank_papers(papers, topic="paper", current_year=2025)

    canonical = select_canonical_papers(ranked, n=3)
    recent = select_recent_high_signal_papers(ranked, n=2, year_window=2)

    assert len(canonical) == 3
    assert all(p.ranking_bucket == "canonical" for p in canonical)
    assert len(recent) <= 2
    assert all(p.ranking_bucket == "recent_high_signal" for p in recent)
    assert all((p.metadata.year or 0) >= 2023 for p in recent)
