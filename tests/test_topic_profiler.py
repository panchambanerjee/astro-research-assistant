"""Tests for TopicProfile construction from ontology."""

from tools.topic_profiler import build_topic_profile


def test_topic_profiler_dark_energy() -> None:
    profile = build_topic_profile("Dark Energy evolution over time")
    assert profile.primary_domain == "cosmology"
    assert "BAO" in profile.probes or "BAO" in profile.observables
    assert "Type Ia supernovae" in profile.probes
    assert "w0" in profile.parameters
    assert "wa" in profile.parameters


def test_topic_profiler_jwst() -> None:
    profile = build_topic_profile("Massive high z galaxies from the JWST")
    assert profile.primary_domain == "galaxy_formation"
    assert "JWST" in profile.surveys_or_missions
    assert "NIRCam" in profile.instruments
    assert "NIRSpec" in profile.instruments
    assert "stellar mass" in profile.parameters


def test_topic_profiler_galaxy_clusters_and_ml() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    assert profile.primary_domain == "galaxy_clusters"
    assert "eROSITA" in profile.surveys_or_missions or "DES" in profile.surveys_or_missions
    assert "machine learning" in profile.methods
    assert "machine_learning" in (profile.matched_terms.get("method_overlays") or [])
    assert profile.expected_paper_types
    assert profile.profile_confidence is not None and profile.profile_confidence >= 0.35
