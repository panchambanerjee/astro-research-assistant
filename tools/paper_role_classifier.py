"""Paper role classification and quota-based selection (TopicProfile-aware)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from schemas.paper import PaperMetadata, RankedPaper
from schemas.topic_profile import PaperRole, TopicProfile
from tools.ml_usage_signals import is_active_ml_usage
from tools.ranking_tool import topic_relevance_score

CLUSTER_TERMS: tuple[str, ...] = (
    "galaxy cluster",
    "galaxy clusters",
    "clusters of galaxies",
    "cluster mass",
    "cluster cosmology",
    "intracluster medium",
    "intracluster",
    "brightest cluster galaxy",
    "intracluster light",
    "x-ray cluster",
    "x-ray clusters",
    "sunyaev",
    "sz effect",
    "cluster gas",
    "cluster survey",
    "cluster catalog",
    "weak-lensing mass",
    "weak lensing mass",
    "mass calibration",
    "hydrostatic",
    "erosita",
    "bcg",
    "icl",
    "sptpol",
    "spt ",
    "south pole telescope",
)

STRONG_ML_TERMS: tuple[str, ...] = (
    "machine learning",
    "deep learning",
    "random forest",
    "neural network",
    "neural networks",
    "cnn",
    "convolutional neural network",
    "convolutional",
    "u-net",
    "unet",
    "gaussian process",
    "emulator",
    "supervised learning",
    "regressor",
    "classifier",
    "gradient boosting",
    "xgboost",
    "simulation-based inference",
    "image-to-image",
    "deep neural",
    "bayesian neural",
)

WEAK_ML_TERMS: tuple[str, ...] = (
    "classification",
    "regression",
    "clustering",
    "inference",
    "estimation",
    "prediction",
)

_SIM_CLUSTER_INFRA_TERMS: tuple[str, ...] = (
    "hydrodynamical simulation",
    "hydrodynamical simulations",
    "halo mass function",
    "matter power spectrum",
    "baryonic effect",
    "baryonic effects",
    "baryonic feedback",
    "cluster gas fraction",
    "cluster gas fractions",
)

_MAJOR_COSMO_SIM_TERMS: tuple[str, ...] = (
    "millenniumtng",
    "millennium-tng",
    "millennium tng",
    "illustris",
    "eagle simulation",
    "simba simulation",
    "tng50",
    " tng ",
    "tng project",
    "flamingo project",
)

_ASTRO_CONTEXT_TERMS: tuple[str, ...] = (
    "galaxy",
    "galaxies",
    "cosmolog",
    "cluster",
    "survey",
    "astronom",
    "astro-ph",
    "stellar",
    "redshift",
    "hubble",
    "dark matter",
    "mnras",
    "apj",
    "arxiv",
)


@dataclass(frozen=True)
class RoleClassificationDetail:
    """Structured role assignment for debugging (use with --debug-report)."""

    role: PaperRole
    reason: str
    matched_cluster_terms: tuple[str, ...] = ()
    matched_strong_ml_terms: tuple[str, ...] = ()
    matched_weak_ml_terms: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _strict_galaxy_cluster_ml_topic(profile: TopicProfile) -> bool:
    overlays = profile.matched_terms.get("method_overlays") or []
    return profile.primary_domain == "galaxy_clusters" and "machine_learning" in overlays


def _role_text(paper: PaperMetadata) -> str:
    return " ".join(
        [
            paper.title or "",
            paper.abstract or "",
            paper.journal or "",
            paper.venue or "",
            " ".join(paper.fields_of_study or []),
        ]
    ).lower()


def _matched_substrings(text_lower: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    hit: list[str] = []
    for t in terms:
        tl = t.lower()
        if tl in text_lower:
            hit.append(t.strip())
    return tuple(hit)


def has_strong_ml_signal(text: str) -> bool:
    """Strong ML terms count; weak terms (classification, regression, …) never count alone."""
    tl = text.lower()
    return any(t.lower() in tl for t in STRONG_ML_TERMS)


def _has_cluster_terms(text_lower: str) -> bool:
    return any(t.lower() in text_lower for t in CLUSTER_TERMS)


def _has_sim_cluster_infra(text_lower: str) -> bool:
    if not _has_cluster_terms(text_lower):
        return False
    return any(t.lower() in text_lower for t in _SIM_CLUSTER_INFRA_TERMS)


def _has_major_cosmo_simulation(text_lower: str) -> bool:
    return any(t.lower() in text_lower for t in _MAJOR_COSMO_SIM_TERMS)


def _has_astro_context(text_lower: str) -> bool:
    return any(t in text_lower for t in _ASTRO_CONTEXT_TERMS)


def _classify_strict_galaxy_cluster_ml_detail(
    paper: PaperMetadata,
    profile: TopicProfile,
    topic: str,
) -> RoleClassificationDetail:
    text = _role_text(paper)
    relevance = topic_relevance_score(paper, topic=topic, topic_profile=profile)
    m_cluster = _matched_substrings(text, CLUSTER_TERMS)
    m_strong = _matched_substrings(text, STRONG_ML_TERMS)
    m_weak = _matched_substrings(text, WEAK_ML_TERMS)
    warnings: list[str] = []
    if m_weak and not m_strong:
        warnings.append("generic method words present but no strong ML phrase")

    has_cluster = bool(m_cluster)
    has_strong = bool(m_strong)
    has_sim_infra = _has_sim_cluster_infra(text)
    has_major_sim = _has_major_cosmo_simulation(text)
    qualifies_direct_ml = is_active_ml_usage(text, has_strong_ml=has_strong)

    if (has_cluster and has_strong) or (has_sim_infra and has_strong):
        if qualifies_direct_ml:
            reason = (
                "cluster context and active ML usage"
                if has_cluster and has_strong
                else "cluster simulation context and active ML usage"
            )
            return RoleClassificationDetail(
                role="direct_evidence",
                reason=reason,
                matched_cluster_terms=m_cluster,
                matched_strong_ml_terms=m_strong,
                matched_weak_ml_terms=m_weak,
                warnings=tuple(warnings),
            )
        warnings.append("ML tokens present but not active method usage (e.g. comparative emulator mention)")

    if (has_major_sim or has_sim_infra) and has_strong and not qualifies_direct_ml:
        reason = (
            "large cosmological simulation suite; ML wording appears comparative or non-operational"
            if has_major_sim
            else "cluster simulation context; ML wording appears comparative or non-operational"
        )
        return RoleClassificationDetail(
            role="theory_interpretation",
            reason=reason,
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    if has_major_sim and not has_strong:
        return RoleClassificationDetail(
            role="theory_interpretation",
            reason="large cosmological simulation suite without explicit ML in abstract",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    if has_sim_infra and not has_strong:
        return RoleClassificationDetail(
            role="theory_interpretation",
            reason="cluster-related simulation or matter statistics without explicit ML",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    if relevance < 0.12:
        return RoleClassificationDetail(
            role="off_topic",
            reason="very low topic relevance for strict cluster+ML profile",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    if has_cluster and not has_strong:
        return RoleClassificationDetail(
            role="background_infrastructure",
            reason="cluster survey or context without explicit ML",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    # Strong ML alone is not enough for method_or_instrument on strict cluster+ML topics:
    # require explicit cluster vocabulary (or cluster+simulation infra handled above as direct/theory).
    cluster_method_context = has_cluster or has_sim_infra

    if has_strong and _has_astro_context(text) and not cluster_method_context:
        warnings.append("strong ML and astro context but no explicit galaxy-cluster vocabulary")
        role: PaperRole = "background_infrastructure" if relevance >= 0.22 else "off_topic"
        return RoleClassificationDetail(
            role=role,
            reason="astro ML without explicit cluster/SZ/ICL/BCG focus for strict cluster+ML topic",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    if relevance < 0.22:
        return RoleClassificationDetail(
            role="off_topic",
            reason="insufficient relevance and no clear cluster+ML signal",
            matched_cluster_terms=m_cluster,
            matched_strong_ml_terms=m_strong,
            matched_weak_ml_terms=m_weak,
            warnings=tuple(warnings),
        )

    return RoleClassificationDetail(
        role="background_infrastructure",
        reason="residual cluster-adjacent or weak signal",
        matched_cluster_terms=m_cluster,
        matched_strong_ml_terms=m_strong,
        matched_weak_ml_terms=m_weak,
        warnings=tuple(warnings),
    )


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
    """When the topic expects method-style papers, add strong ML cues only (no weak-only triggers)."""
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


def classify_paper_role_detailed(
    paper: PaperMetadata,
    profile: TopicProfile,
    topic: str,
) -> RoleClassificationDetail:
    """Assign role plus matched phrases and a short reason (strict cluster+ML is fully explained)."""
    text = _role_text(paper).lower()
    relevance = topic_relevance_score(paper, topic=topic, topic_profile=profile)

    if _strict_galaxy_cluster_ml_topic(profile):
        return _classify_strict_galaxy_cluster_ml_detail(paper, profile, topic)

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
            return RoleClassificationDetail(role="off_topic", reason="GW discovery paper without cosmology allow-list")

    if profile.primary_domain == "galaxy_formation" and "axion" in text:
        return RoleClassificationDetail(role="off_topic", reason="axion topic in galaxy-formation profile")

    if profile.primary_domain == "galaxy_formation":
        if any(t in text for t in background_terms) and not any(t in text for t in direct_terms):
            return RoleClassificationDetail(role="background_review", reason="background cues without direct hits")

    if relevance < 0.15:
        return RoleClassificationDetail(role="off_topic", reason="low topic relevance")

    if any(t in text for t in background_terms) and relevance < 0.55:
        return RoleClassificationDetail(role="background_review", reason="background lexical cues")

    if any(t in text for t in theory_terms) and not any(t in text for t in direct_terms):
        return RoleClassificationDetail(role="theory_interpretation", reason="theory terms without direct hits")

    if any(t in text for t in method_terms) and "jwst" in text and relevance < 0.5:
        return RoleClassificationDetail(role="method_or_instrument", reason="JWST instrument/pipeline focus")

    if any(t in text for t in direct_terms):
        return RoleClassificationDetail(role="direct_evidence", reason="matched direct-evidence vocabulary")

    if relevance >= 0.52:
        return RoleClassificationDetail(role="direct_evidence", reason="high lexical relevance fallback")

    return RoleClassificationDetail(role="background_review", reason="default background bucket")


def classify_paper_role(paper: PaperMetadata, profile: TopicProfile, topic: str) -> PaperRole:
    """Assign PaperRole using profile domain, relevance, and lexical cues."""
    return classify_paper_role_detailed(paper, profile, topic).role


class SelectionPolicy(BaseModel):
    """Caps and floors for role-aware primary selection."""

    model_config = ConfigDict(extra="forbid")

    max_papers: int = 5
    min_direct_evidence: int = 3
    max_background: int = 1
    max_theory_interpretation: int = 1
    max_method_or_instrument: int = 1
    max_background_roles_in_primary: int = 0
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
            max_background_roles_in_primary=0,
        )
    return SelectionPolicy(
        max_papers=cap,
        min_direct_evidence=min(3, max(1, cap - 2)),
        max_background=1,
        max_theory_interpretation=1,
        max_method_or_instrument=1,
        max_background_roles_in_primary=0,
    )


def selection_policy_from_profile(profile: TopicProfile, max_papers: int) -> SelectionPolicy:
    """
    Start from default quotas, then widen method/theory caps when the profile expects
    method-style papers — except strict galaxy_clusters+ML, where the method primary cap
    stays tight and theory primaries are capped at 1 so the set stays ML-heavy.
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
    if methodish and not _strict_galaxy_cluster_ml_topic(profile):
        max_method = min(max(base.max_papers // 2, 2), max(2, max_method))

    if "inference" in types_l:
        max_theory = min(2, max_theory + 1)

    updates: dict[str, object] = {
        "max_method_or_instrument": max_method,
        "max_theory_interpretation": max_theory,
    }
    if _strict_galaxy_cluster_ml_topic(profile):
        updates["min_direct_evidence"] = min(2, base.min_direct_evidence)
        updates["max_method_or_instrument"] = 1
        updates["max_theory_interpretation"] = 1

    return base.model_copy(update=updates)


def _method_allowed_in_primary_strict(
    paper: PaperMetadata,
    profile: TopicProfile,
    topic: str,
    ranked_row: RankedPaper,
) -> bool:
    if not _strict_galaxy_cluster_ml_topic(profile):
        return True
    if ranked_row.relevance_score < 0.45:
        return False
    text = _role_text(paper)
    if not has_strong_ml_signal(text):
        return False
    return _has_cluster_terms(text.lower())


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
        r.metadata
        for r in ranked
        if roles[_paper_key(r.metadata)] in ("background_review", "background_infrastructure")
    ][: max(10, pol.max_papers)]

    primary_roles_eligible: set[str] = {
        "direct_evidence",
        "theory_interpretation",
        "method_or_instrument",
    }
    if pol.max_background_roles_in_primary > 0:
        primary_roles_eligible.update({"background_review", "background_infrastructure"})

    pool = [r for r in ranked if roles[_paper_key(r.metadata)] in primary_roles_eligible]
    if not pool:
        pool = list(ranked)

    pool_thresh = [r for r in pool if r.relevance_score >= primary_cut]
    if not pool_thresh:
        pool_thresh = pool

    def rk(r: RankedPaper) -> int:
        return r.rank or 10**9

    def role_of(r: RankedPaper) -> PaperRole:
        return roles[_paper_key(r.metadata)]

    directs = sorted([r for r in pool_thresh if role_of(r) == "direct_evidence"], key=rk)
    theories = sorted([r for r in pool_thresh if role_of(r) == "theory_interpretation"], key=rk)
    methods_all = sorted([r for r in pool_thresh if role_of(r) == "method_or_instrument"], key=rk)
    methods = [r for r in methods_all if _method_allowed_in_primary_strict(r.metadata, profile, topic, r)]
    backgrounds = sorted(
        [
            r
            for r in pool_thresh
            if role_of(r) in ("background_review", "background_infrastructure")
        ],
        key=rk,
    )

    chosen: list[RankedPaper] = []
    chosen_keys: set[str] = set()
    n_bg_in_primary = 0

    def add_unique(r: RankedPaper, *, allow_background: bool = False) -> bool:
        nonlocal n_bg_in_primary
        k = _paper_key(r.metadata)
        if k in chosen_keys or len(chosen) >= pol.max_papers:
            return False
        ro = role_of(r)
        if ro in ("background_review", "background_infrastructure"):
            if not allow_background:
                return False
            if n_bg_in_primary >= pol.max_background_roles_in_primary:
                return False
            n_bg_in_primary += 1
        chosen.append(r)
        chosen_keys.add(k)
        return True

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

    if pol.max_background_roles_in_primary > 0:
        for r in backgrounds:
            if len(chosen) >= pol.max_papers:
                break
            add_unique(r, allow_background=True)

    primary_ranked = []
    for c in chosen:
        cp = c.model_copy(deep=True)
        cp.ranking_bucket = "primary"
        primary_ranked.append(cp)

    return primary_ranked, background_md, rejected
