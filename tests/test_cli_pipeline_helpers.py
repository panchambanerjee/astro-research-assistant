from schemas.paper import CitationCounts, PaperMetadata
from schemas.paper_analysis import PaperAnalysis

from app.cli import (
    _apply_topic_relevance_filter,
    _build_structured_hypotheses,
    _classify_paper_role,
    _clean_paper_analysis_against_text,
)
from tools.ranking_tool import topic_relevance_score


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
    kept, dropped = _apply_topic_relevance_filter(
        [jwst, off_topic],
        topic="Massive high z galaxies from the JWST",
        negative_terms=["cell migration", "biology", "medicine"],
        threshold=0.25,
    )
    assert jwst in kept
    assert off_topic in dropped


def test_classify_paper_role_marks_background() -> None:
    background = PaperMetadata(
        title="The James Webb Space Telescope mission overview",
        abstract="mission instrument overview",
    )
    assert _classify_paper_role(background, "Massive high z galaxies from the JWST") == "background"


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
    assert topic_relevance_score(de, topic) > topic_relevance_score(gw, topic)


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
