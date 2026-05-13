from schemas.paper import CitationCounts, PaperMetadata
from schemas.paper_analysis import PaperAnalysis

from app.cli import (
    _apply_topic_relevance_filter,
    _build_structured_hypotheses,
    _clean_paper_analysis_against_text,
    bootstrap_paper_analysis,
)
from tools.paper_role_classifier import classify_paper_role
from tools.ranking_tool import topic_relevance_score
from tools.topic_profiler import build_topic_profile


def test_apply_topic_relevance_filter_drops_off_topic() -> None:
    jwst = PaperMetadata(
        title="CEERS massive galaxies at high redshift",
        abstract="jwst ceers stellar mass density high redshift",
        citation_counts=CitationCounts(selected=50),
    )
    off_topic = PaperMetadata(
        title="Control of directed cell migration in vivo",
        abstract="cell migration biology medicine",
        citation_counts=CitationCounts(selected=500),
    )
    profile = build_topic_profile("Massive high z galaxies from the JWST")
    kept, dropped = _apply_topic_relevance_filter(
        [jwst, off_topic],
        topic="Massive high z galaxies from the JWST",
        negative_terms=["cell migration", "biology", "medicine"],
        threshold=0.25,
        topic_profile=profile,
    )
    assert jwst in kept
    assert off_topic in dropped


def test_classify_paper_role_marks_background() -> None:
    background = PaperMetadata(
        title="The James Webb Space Telescope mission overview",
        abstract="mission instrument overview",
    )
    profile = build_topic_profile("Massive high z galaxies from the JWST")
    assert (
        classify_paper_role(background, profile, "Massive high z galaxies from the JWST") == "background_review"
    )


def test_clean_paper_analysis_against_text_removes_unmentioned_terms() -> None:
    paper = PaperMetadata(title="TNG50 simulation overview", abstract="simulation of galaxy formation")
    analysis = PaperAnalysis(
        paper=paper,
        datasets=["ACT", "DES", "TNG50"],
        instruments=["NIRSpec"],
        missions=["JWST"],
        observables=["cosmic shear"],
        parameters=["S8"],
        systematics=["intrinsic alignment"],
    )
    cleaned = _clean_paper_analysis_against_text(
        analysis,
        metadata_text="tng50 simulation of galaxy formation",
        evidence_text="tng50 simulation of galaxy formation",
    )
    assert cleaned.datasets == ["TNG50"]
    assert cleaned.instruments == []
    assert cleaned.missions == []


def test_jwst_structured_hypothesis_fallback_not_empty() -> None:
    paper = PaperMetadata(
        title="CEERS high-redshift massive galaxies",
        abstract="photometric redshift uncertainty and stellar mass estimation with dust attenuation",
    )
    analysis = PaperAnalysis(
        paper=paper,
        systematics=["photometric redshift uncertainty", "dust attenuation modeling", "cosmic variance"],
        methods=["NIRCam photometry"],
        key_results=["stellar mass density at high redshift is sensitive to SPS assumptions"],
    )
    hypotheses = _build_structured_hypotheses("Massive high z galaxies from the JWST", [analysis])
    assert hypotheses


def test_dark_energy_relevance_penalizes_non_cosmology_gw_discovery() -> None:
    gw = PaperMetadata(
        title="Observation of Gravitational Waves from a Binary Black Hole Merger",
        abstract="gw150914 ligo binary black hole merger",
        citation_counts=CitationCounts(selected=5000),
    )
    de = PaperMetadata(
        title="Dark energy equation of state constraints from BAO and Type Ia supernovae",
        abstract="w0 wa cpl dark energy expansion history pantheon eboss",
        citation_counts=CitationCounts(selected=400),
    )
    topic = "Dark Energy evolution over time"
    profile = build_topic_profile(topic)
    assert topic_relevance_score(de, topic, topic_profile=profile) > topic_relevance_score(
        gw, topic, topic_profile=profile
    )


def test_dark_energy_structured_hypothesis_fallback_not_empty() -> None:
    paper = PaperMetadata(
        title="Dark energy equation-of-state constraints from Planck + BAO + SNe",
        abstract="w0 wa cpl dark energy model comparison with supernova calibration systematics",
    )
    analysis = PaperAnalysis(
        paper=paper,
        systematics=["SN calibration", "selection effects"],
        methods=["Joint likelihood inference"],
        key_results=["w0 wa constraints from CMB BAO SNe combinations"],
    )
    hypotheses = _build_structured_hypotheses("Dark Energy evolution over time", [analysis])
    assert hypotheses


def test_no_profile_leakage_to_paper_analysis() -> None:
    """TopicExpansion surveys must not populate datasets unless present on the paper."""
    paper = PaperMetadata(
        title="TNG50 simulation overview",
        abstract="simulation of galaxy formation and stellar feedback",
    )
    profile = build_topic_profile("S8 tension between weak lensing and Planck")
    from tools.query_generator import topic_profile_to_expansion

    expansion = topic_profile_to_expansion(profile)
    analysis = bootstrap_paper_analysis(
        paper=paper,
        topic="S8 tension between weak lensing and Planck",
        extracted_text="",
        expansion=expansion,
        topic_profile=profile,
    )
    assert "DES" not in analysis.datasets
    assert "KiDS" not in analysis.datasets


def test_profile_enrichment_adds_methods_when_in_abstract() -> None:
    paper = PaperMetadata(
        title="Cluster mass with ML",
        abstract="we train a random forest regressor on x-ray luminosity and sz signal for galaxy clusters",
    )
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    from tools.query_generator import topic_profile_to_expansion

    expansion = topic_profile_to_expansion(profile)
    analysis = bootstrap_paper_analysis(
        paper=paper,
        topic=profile.original_topic,
        extracted_text="",
        expansion=expansion,
        topic_profile=profile,
    )
    assert "random forest" in " ".join(m.lower() for m in analysis.methods)


def test_dataset_hints_do_not_match_substrings() -> None:
    """Short survey tokens must not match inside unrelated words (e.g. DES in 'addresses')."""
    paper = PaperMetadata(
        title="Galaxy cluster miscentering and projection effects",
        abstract="This work addresses systematic biases in cluster mass estimation.",
    )
    profile = build_topic_profile("S8 tension between weak lensing and Planck")
    from tools.query_generator import topic_profile_to_expansion

    expansion = topic_profile_to_expansion(profile)
    analysis = bootstrap_paper_analysis(
        paper=paper,
        topic="S8 tension between weak lensing and Planck",
        extracted_text="",
        expansion=expansion,
    )
    assert "DES" not in analysis.datasets
