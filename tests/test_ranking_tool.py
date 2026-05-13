from schemas.paper import CitationCounts, PaperMetadata
from tools.ranking_tool import (
    profile_relevance_score,
    rank_papers,
    select_primary_papers,
    select_recent_high_signal_papers,
    topic_relevance_score,
)
from tools.topic_profiler import build_topic_profile


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

    primary = select_primary_papers(ranked, n=3)
    recent = select_recent_high_signal_papers(ranked, n=2, year_window=2)

    assert len(primary) == 3
    assert all(p.ranking_bucket == "primary" for p in primary)
    assert len(recent) <= 2
    assert all(p.ranking_bucket == "recent_high_signal" for p in recent)
    assert all((p.metadata.year or 0) >= 2023 for p in recent)


def test_topic_relevance_penalizes_off_topic_terms() -> None:
    off_topic = PaperMetadata(
        title="Axion cosmology constraints from CMB lensing",
        abstract="axion model constraints in cosmology",
        citation_counts=CitationCounts(selected=500),
    )
    on_topic = PaperMetadata(
        title="CEERS massive galaxies at high redshift with JWST NIRCam",
        abstract="jwst high redshift massive galaxies stellar mass density",
        citation_counts=CitationCounts(selected=40),
    )
    topic = "Massive high z galaxies from the JWST"
    assert topic_relevance_score(on_topic, topic) > topic_relevance_score(off_topic, topic)


def test_rank_papers_prefers_topic_relevance_over_generic_high_citation() -> None:
    generic_high_citation = PaperMetadata(
        title="Axion cosmology review",
        abstract="axion cosmology and dark matter only model",
        year=2017,
        citation_counts=CitationCounts(selected=2500),
    )
    jwst_direct = PaperMetadata(
        title="A population of red candidate massive galaxies 600 Myr after the Big Bang",
        abstract="jwst ceers massive galaxies high redshift stellar mass density",
        year=2023,
        citation_counts=CitationCounts(selected=120),
    )
    profile = build_topic_profile("Massive high z galaxies from the JWST")
    ranked = rank_papers(
        [generic_high_citation, jwst_direct],
        topic="Massive high z galaxies from the JWST",
        current_year=2025,
        topic_profile=profile,
    )
    assert ranked[0].metadata.title == jwst_direct.title


def test_rank_papers_dark_energy_filters_gw_discovery_bias() -> None:
    gw = PaperMetadata(
        title="Observation of Gravitational Waves from a Binary Black Hole Merger",
        abstract="gw150914 ligo binary black hole merger",
        year=2016,
        citation_counts=CitationCounts(selected=5000),
    )
    de = PaperMetadata(
        title="Completed SDSS-IV extended Baryon Oscillation Spectroscopic Survey: Cosmological Implications",
        abstract="dark energy equation of state constraints from BAO and supernova combinations with Planck",
        year=2021,
        citation_counts=CitationCounts(selected=600),
    )
    profile = build_topic_profile("Dark Energy evolution over time")
    ranked = rank_papers([gw, de], topic="Dark Energy evolution over time", current_year=2025, topic_profile=profile)
    assert ranked[0].metadata.title == de.title


def test_gw150914_dark_energy_profile_relevance_low() -> None:
    gw = PaperMetadata(
        title="Observation of Gravitational Waves from a Binary Black Hole Merger",
        abstract="gw150914 ligo binary black hole merger",
        year=2016,
        citation_counts=CitationCounts(selected=5000),
    )
    profile = build_topic_profile("Dark Energy evolution over time")
    assert profile_relevance_score(gw, profile) < 0.25


def test_standard_siren_profile_relevance_allowed() -> None:
    siren = PaperMetadata(
        title="Standard sirens and dark energy with gravitational waves",
        abstract="standard siren luminosity distance dark energy hubble constant cosmological constraints",
        year=2022,
        citation_counts=CitationCounts(selected=80),
    )
    profile = build_topic_profile("Dark Energy evolution over time")
    assert profile_relevance_score(siren, profile) > 0.35


def test_expected_paper_types_boost_when_paper_text_aligns() -> None:
    """Papers whose text matches ontology-driven expected_paper_types get a small relevance bonus."""
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    assert profile.expected_paper_types

    ml_paper = PaperMetadata(
        title="Deep learning for cluster detection",
        abstract="we train a convolutional neural network for classification of galaxy clusters in survey data",
        citation_counts=CitationCounts(selected=40),
        doi="10.1000/ml.1",
    )
    plain = PaperMetadata(
        title="Analytical model of cluster profiles",
        abstract="analytic density profile model without data-driven methods",
        citation_counts=CitationCounts(selected=40),
        doi="10.1000/plain.1",
    )

    stripped = profile.model_copy(update={"expected_paper_types": []})
    assert profile_relevance_score(ml_paper, profile) >= profile_relevance_score(ml_paper, stripped)
    assert profile_relevance_score(ml_paper, profile) > profile_relevance_score(plain, profile)
