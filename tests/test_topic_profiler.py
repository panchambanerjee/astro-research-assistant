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
