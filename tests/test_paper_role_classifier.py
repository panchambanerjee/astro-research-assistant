"""Tests for role classification and profile-driven selection quotas."""

from schemas.paper import CitationCounts, PaperMetadata
from tools.paper_role_classifier import (
    classify_paper_role,
    default_selection_policy,
    select_primary_ranked_with_quotas,
    selection_policy_from_profile,
)
from tools.ranking_tool import rank_papers
from tools.topic_profiler import build_topic_profile


def test_selection_policy_widens_method_quota_for_ml_profile() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    assert profile.expected_paper_types
    pol = selection_policy_from_profile(profile, max_papers=10)
    base = default_selection_policy(10)
    assert pol.max_method_or_instrument >= base.max_method_or_instrument
    assert pol.max_method_or_instrument >= 2


def test_selection_policy_default_for_non_method_topic() -> None:
    profile = build_topic_profile("Dark Energy evolution over time")
    pol = selection_policy_from_profile(profile, max_papers=10)
    assert pol.max_method_or_instrument == 1


def test_inference_expected_type_raises_theory_cap() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning").model_copy(
        update={"expected_paper_types": ["inference", "method"]},
    )
    pol = selection_policy_from_profile(profile, max_papers=10)
    assert pol.max_theory_interpretation >= 2


def test_classify_prefers_direct_when_ml_terms_match_expected_profile() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    paper = PaperMetadata(
        title="Machine learning for cluster mass calibration",
        abstract="we use a neural network to estimate galaxy cluster masses from x-ray observables",
    )
    role = classify_paper_role(paper, profile, profile.original_topic)
    assert role in ("direct_evidence", "method_or_instrument")


def test_ranked_primary_respects_max_papers_with_profile_policy() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    pol = selection_policy_from_profile(profile, max_papers=5)
    papers = [
        PaperMetadata(
            title=f"Cluster paper {i}",
            abstract="galaxy cluster machine learning mass calibration eROSITA",
            year=2022,
            citation_counts=CitationCounts(selected=80 - i * 3),
            doi=f"10.1000/test.cluster.{i}",
        )
        for i in range(8)
    ]
    ranked = rank_papers(papers, topic=profile.original_topic, current_year=2025, topic_profile=profile)

    primary, _, _ = select_primary_ranked_with_quotas(
        ranked,
        profile,
        profile.original_topic,
        relevance_threshold=0.1,
        primary_threshold=0.1,
        policy=pol,
    )
    assert len(primary) <= pol.max_papers == 5


def test_strict_cluster_survey_without_ml_is_infrastructure() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    paper = PaperMetadata(
        title="SPTpol extended cluster survey overview",
        abstract="sunyaev-zeldovich selected galaxy cluster catalog over millimeter maps and survey depth",
    )
    assert classify_paper_role(paper, profile, profile.original_topic) == "background_infrastructure"


def test_strict_cluster_ml_requires_both_axes_for_direct() -> None:
    profile = build_topic_profile("Galaxy Clusters and Machine Learning")
    paper = PaperMetadata(
        title="Painting baryons with U-Net",
        abstract="we use deep learning and a u-net on galaxy cluster simulations to paint gas in n-body halos",
    )
    assert classify_paper_role(paper, profile, profile.original_topic) == "direct_evidence"
