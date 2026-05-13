"""Paper role classification and quota-based selection (TopicProfile-aware)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.paper import PaperMetadata, RankedPaper
from schemas.topic_profile import PaperRole, TopicProfile
from tools.ranking_tool import topic_relevance_score

_DIRECT_EVIDENCE_TERMS = (
    "ceers",
    "jades",
    "glass-jwst",
    "uncover",
    "cosmos-web",
    "primer",
    "excels",
    "nirspec",
    "nircam",
    "desi",
    "eboss",
    "boss",
    "pantheon",
    "bao",
    "baryon acoustic",
    "weak lensing",
    "cosmic shear",
)
_THEORY_TERMS = (
    "stellar mass density",
    "halo abundance",
    "quiescent galaxies",
    "warm dark matter",
    "tension",
    "w0",
    "wa",
    "equation of state",
    "dark energy",
)
_BACKGROUND_TERMS = (
    "overview",
    "instrument",
    "mission",
    "review",
    "the james webb space telescope",
    "candels",
    "tng50",
    "simulation of galaxy formation",
)
_METHOD_INSTRUMENT_TERMS = ("nircam", "nirspec", "miri", "niriss", "instrumental", "pipeline", "calibration")


def _extra_direct_terms_from_profile(profile: TopicProfile) -> tuple[str, ...]:
    """When the topic expects method-style papers, treat ML / pipeline language as direct-evidence cues."""
    types_l = {(t or "").strip().lower() for t in profile.expected_paper_types}
    if not types_l:
        return ()
    want_ml = bool(
        types_l
        & {
            "method",
            "simulation calibration",
            "observational pipeline",
            "catalog construction",
            "inference",
        }
    )
    if not want_ml:
        return ()
    return (
        "machine learning",
        "deep learning",
        "neural network",
        "random forest",
        "gaussian process",
        "classification",
        "regression",
        "emulator",
        "simulation-based inference",
    )


def _paper_key(paper: PaperMetadata) -> str:
    return paper.doi or paper.arxiv_id or paper.ads_bibcode or paper.openalex_id or paper.title or "unknown"


def _merge_role_hints(profile: TopicProfile, role: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for x in (*fallback, *profile.paper_role_hints.get(role, [])):
        lx = x.lower()
        if lx not in seen:
            seen.add(lx)
            out.append(lx)
    return tuple(out)


def classify_paper_role(paper: PaperMetadata, profile: TopicProfile, topic: str) -> PaperRole:
    """Assign PaperRole using profile domain, relevance, and lexical cues."""
    text = " ".join([paper.title or "", paper.abstract or "", paper.journal or "", paper.venue or ""]).lower()
    relevance = topic_relevance_score(paper, topic=topic, topic_profile=profile)

    direct_terms = _merge_role_hints(
        profile,
        "direct_evidence",
        (*_DIRECT_EVIDENCE_TERMS, *_extra_direct_terms_from_profile(profile)),
    )
    theory_terms = _merge_role_hints(profile, "theory_interpretation", _THEORY_TERMS)
    background_terms = _merge_role_hints(profile, "background_review", _BACKGROUND_TERMS)
    method_terms = _merge_role_hints(profile, "method_or_instrument", _METHOD_INSTRUMENT_TERMS)

    if profile.primary_domain == "cosmology":
        if "gravitational wave" in text and not any(a.lower() in text for a in profile.conditional_allow_terms):
            return "off_topic"

    if profile.primary_domain == "galaxy_formation" and "axion" in text:
        return "off_topic"

    if profile.primary_domain == "galaxy_formation":
        if any(t in text for t in background_terms) and not any(t in text for t in direct_terms):
            return "background_review"

    if relevance < 0.15:
        return "off_topic"

    if any(t in text for t in background_terms) and relevance < 0.55:
        return "background_review"

    if any(t in text for t in theory_terms) and not any(t in text for t in direct_terms):
        return "theory_interpretation"

    if any(t in text for t in method_terms) and "jwst" in text and relevance < 0.5:
        return "method_or_instrument"

    if any(t in text for t in direct_terms):
        return "direct_evidence"

    if relevance >= 0.45:
        return "direct_evidence"
    return "background_review"


class SelectionPolicy(BaseModel):
    """Caps and floors for role-aware primary selection."""

    model_config = ConfigDict(extra="forbid")

    max_papers: int = 5
    min_direct_evidence: int = 3
    max_background: int = 1
    max_theory_interpretation: int = 1
    max_method_or_instrument: int = 1
    exclude_off_topic: bool = True


class PaperSelectionResult(BaseModel):
    """Outcome of role-aware selection."""

    model_config = ConfigDict(extra="forbid")

    selected_primary: list[PaperMetadata] = Field(default_factory=list)
    selected_recent: list[PaperMetadata] = Field(default_factory=list)
    background: list[PaperMetadata] = Field(default_factory=list)
    rejected: list[PaperMetadata] = Field(default_factory=list)


def default_selection_policy(max_papers: int) -> SelectionPolicy:
    cap = min(10, max_papers)
    if max_papers <= 2:
        return SelectionPolicy(
            max_papers=cap,
            min_direct_evidence=1,
            max_background=1,
            max_theory_interpretation=1,
            max_method_or_instrument=1,
        )
    return SelectionPolicy(
        max_papers=cap,
        min_direct_evidence=min(3, max(1, cap - 2)),
        max_background=1,
        max_theory_interpretation=1,
        max_method_or_instrument=1,
    )


def selection_policy_from_profile(profile: TopicProfile, max_papers: int) -> SelectionPolicy:
    """
    Start from default quotas, then widen method/theory caps when the profile expects
    method, pipeline, calibration, or inference-style papers (e.g. ML method overlays).
    """
    base = default_selection_policy(max_papers)
    types_l = {(t or "").strip().lower() for t in profile.expected_paper_types if (t or "").strip()}
    max_method = base.max_method_or_instrument
    max_theory = base.max_theory_interpretation

    methodish = types_l & {
        "method",
        "simulation calibration",
        "observational pipeline",
        "catalog construction",
    }
    if methodish:
        max_method = min(max(base.max_papers // 2, 2), max(2, max_method))

    if "inference" in types_l:
        max_theory = min(2, max_theory + 1)

    return base.model_copy(
        update={
            "max_method_or_instrument": max_method,
            "max_theory_interpretation": max_theory,
        }
    )


def select_primary_ranked_with_quotas(
    ranked: list[RankedPaper],
    profile: TopicProfile,
    topic: str,
    *,
    relevance_threshold: float,
    primary_threshold: float | None = None,
    policy: SelectionPolicy | None = None,
) -> tuple[list[RankedPaper], list[PaperMetadata], list[PaperMetadata]]:
    """
    Returns:
        primary_ranked: RankedPaper copies with ``ranking_bucket`` set to ``primary``,
        background_metadata,
        rejected_metadata,
    """
    pol = policy or default_selection_policy(5)
    primary_cut = primary_threshold if primary_threshold is not None else relevance_threshold

    roles: dict[str, PaperRole] = {}
    for r in ranked:
        roles[_paper_key(r.metadata)] = classify_paper_role(r.metadata, profile, topic)

    rejected = [
        r.metadata
        for r in ranked
        if pol.exclude_off_topic and roles[_paper_key(r.metadata)] == "off_topic"
    ]

    background_md = [
        r.metadata for r in ranked if roles[_paper_key(r.metadata)] == "background_review"
    ][: max(10, pol.max_papers)]

    primary_roles_eligible = {"direct_evidence", "theory_interpretation", "method_or_instrument"}
    pool = [r for r in ranked if roles[_paper_key(r.metadata)] in primary_roles_eligible]
    if not pool:
        pool = list(ranked)

    pool_thresh = [r for r in pool if r.relevance_score >= primary_cut]
    if not pool_thresh:
        pool_thresh = pool

    def rk(r: RankedPaper) -> int:
        return r.rank or 10**9

    directs = sorted(
        [r for r in pool_thresh if roles[_paper_key(r.metadata)] == "direct_evidence"],
        key=rk,
    )
    theories = sorted(
        [r for r in pool_thresh if roles[_paper_key(r.metadata)] == "theory_interpretation"],
        key=rk,
    )
    methods = sorted(
        [r for r in pool_thresh if roles[_paper_key(r.metadata)] == "method_or_instrument"],
        key=rk,
    )

    chosen: list[RankedPaper] = []
    chosen_keys: set[str] = set()

    def add_unique(r: RankedPaper) -> None:
        k = _paper_key(r.metadata)
        if k in chosen_keys or len(chosen) >= pol.max_papers:
            return
        chosen.append(r)
        chosen_keys.add(k)

    for r in directs[: pol.min_direct_evidence]:
        add_unique(r)
    for r in theories[: pol.max_theory_interpretation]:
        add_unique(r)
    for r in methods[: pol.max_method_or_instrument]:
        add_unique(r)
    for r in directs[pol.min_direct_evidence :]:
        add_unique(r)
    for r in theories[pol.max_theory_interpretation :]:
        add_unique(r)
    for r in methods[pol.max_method_or_instrument :]:
        add_unique(r)
    for r in sorted(pool_thresh, key=rk):
        add_unique(r)

    primary_ranked = []
    for c in chosen:
        cp = c.model_copy(deep=True)
        cp.ranking_bucket = "primary"
        primary_ranked.append(cp)

    return primary_ranked, background_md, rejected
