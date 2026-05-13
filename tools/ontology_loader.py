"""Load `config/astro_ontology.yaml` into typed structures for topic profiling."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from schemas.topic_profile import ConditionalNegativeBlock

_DEFAULT_RELEVANCE_WEIGHTS: dict[str, float] = {
    "phenomena": 4.0,
    "observables": 3.0,
    "probes": 3.0,
    "surveys": 2.5,
    "instruments": 2.5,
    "parameters": 2.0,
    "methods": 2.0,
    "systematics": 1.0,
    "subdomains": 1.5,
    "negative_topics": -5.0,
}


@dataclass
class DomainOntology:
    """Vocabulary and negatives for one domain."""

    name: str
    aliases: list[str] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)
    surveys: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    systematics: list[str] = field(default_factory=list)
    observables: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    negative_topics: list[str] = field(default_factory=list)
    conditional_negatives: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    arxiv_categories: list[str] = field(default_factory=list)
    paper_role_hints: dict[str, list[str]] = field(default_factory=dict)
    relevance_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class MethodOverlay:
    """Cross-cutting method layer (e.g. ML) applied when topic mentions methods, not a science domain."""

    name: str
    description: str = ""
    match_any: list[str] = field(default_factory=list)
    match_boost_if: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    expected_paper_types: list[str] = field(default_factory=list)
    canonical_queries: list[str] = field(default_factory=list)


@dataclass
class ProfileOverlay:
    """Reusable profile refinement when match rules hit (config-driven, not code branches)."""

    name: str
    description: str = ""
    applies_to_domains: list[str] = field(default_factory=list)
    match_any: list[str] = field(default_factory=list)
    match_boost_if: list[str] = field(default_factory=list)
    canonical_queries: list[str] = field(default_factory=list)
    observables: list[str] = field(default_factory=list)
    surveys: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    systematics: list[str] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=list)


@dataclass
class AstroOntology:
    domains: dict[str, DomainOntology]
    overlays: dict[str, ProfileOverlay]
    method_overlays: dict[str, MethodOverlay] = field(default_factory=dict)
    relevance_weights: dict[str, float] = field(default_factory=dict)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()]


def _parse_float_dict(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _parse_paper_role_hints(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): _as_str_list(v) for k, v in raw.items()}


def _parse_conditional_negatives(raw: Any) -> dict[str, dict[str, list[str]]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for key, block in raw.items():
        if not isinstance(block, dict):
            continue
        out[str(key)] = {
            "negative_terms": _as_str_list(block.get("negative_terms")),
            "allow_if": _as_str_list(block.get("allow_if")),
        }
    return out


def _parse_match_any_boost(block: dict[str, Any]) -> tuple[list[str], list[str]]:
    m = block.get("match")
    if isinstance(m, dict):
        any_terms = [t.lower() for t in _as_str_list(m.get("any", []))]
        boost = [t.lower() for t in _as_str_list(m.get("boost_if", []))]
        return any_terms, boost
    if isinstance(m, list):
        return [t.lower() for t in _as_str_list(m)], []
    return [], []


def _parse_domain(name: str, data: dict[str, Any]) -> DomainOntology:
    cn = data.get("conditional_negatives")
    cond: dict[str, dict[str, list[str]]] = {}
    if isinstance(cn, dict):
        for subkey, block in cn.items():
            if isinstance(block, dict):
                cond[str(subkey)] = {
                    "negative_terms": _as_str_list(block.get("negative_terms")),
                    "allow_if": _as_str_list(block.get("allow_if")),
                }
    return DomainOntology(
        name=name,
        aliases=_as_str_list(data.get("aliases")),
        probes=_as_str_list(data.get("probes")),
        surveys=_as_str_list(data.get("surveys")),
        parameters=_as_str_list(data.get("parameters")),
        methods=_as_str_list(data.get("methods")),
        systematics=_as_str_list(data.get("systematics")),
        observables=_as_str_list(data.get("observables")),
        instruments=_as_str_list(data.get("instruments")),
        negative_topics=_as_str_list(data.get("negative_topics")),
        conditional_negatives=cond,
        arxiv_categories=_as_str_list(data.get("arxiv_categories")),
        paper_role_hints=_parse_paper_role_hints(data.get("paper_role_hints")),
        relevance_weights=_parse_float_dict(data.get("relevance_weights")),
    )


def _parse_profile_overlays(raw: Any) -> dict[str, ProfileOverlay]:
    if not isinstance(raw, dict):
        return {}
    overlays: dict[str, ProfileOverlay] = {}
    for name, block in raw.items():
        if not isinstance(block, dict):
            continue
        match_any, boost_if = _parse_match_any_boost(block)
        overlays[str(name)] = ProfileOverlay(
            name=str(name),
            description=str(block.get("description") or "").strip(),
            applies_to_domains=_as_str_list(block.get("applies_to_domains")),
            match_any=match_any,
            match_boost_if=boost_if,
            canonical_queries=_as_str_list(block.get("canonical_queries")),
            observables=_as_str_list(block.get("observables")),
            surveys=_as_str_list(block.get("surveys")),
            parameters=_as_str_list(block.get("parameters")),
            systematics=_as_str_list(block.get("systematics")),
            arxiv_categories=_as_str_list(block.get("arxiv_categories")),
        )
    return overlays


def _parse_method_overlays(raw: Any) -> dict[str, MethodOverlay]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, MethodOverlay] = {}
    for name, block in raw.items():
        if not isinstance(block, dict):
            continue
        match_any, boost_if = _parse_match_any_boost(block)
        out[str(name)] = MethodOverlay(
            name=str(name),
            description=str(block.get("description") or "").strip(),
            match_any=match_any,
            match_boost_if=boost_if,
            methods=_as_str_list(block.get("methods")),
            expected_paper_types=_as_str_list(block.get("expected_paper_types")),
            canonical_queries=_as_str_list(block.get("canonical_queries")),
        )
    return out


def load_astro_ontology(path: Path | None = None) -> AstroOntology:
    """Load unified astro ontology from YAML."""
    root = path or Path(__file__).resolve().parents[1] / "config" / "astro_ontology.yaml"
    data = yaml.safe_load(root.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return AstroOntology(
            domains={},
            overlays={},
            method_overlays={},
            relevance_weights=dict(_DEFAULT_RELEVANCE_WEIGHTS),
        )

    global_rw = {**_DEFAULT_RELEVANCE_WEIGHTS, **_parse_float_dict(data.get("relevance_weights"))}

    domains_raw = data.get("domains", {})
    domains: dict[str, DomainOntology] = {}
    if isinstance(domains_raw, dict):
        for dname, dblock in domains_raw.items():
            if isinstance(dblock, dict):
                domains[str(dname)] = _parse_domain(str(dname), dblock)

    raw_overlays = data.get("profile_overlays")
    if raw_overlays is None:
        raw_overlays = data.get("topic_overlays")
    overlays = _parse_profile_overlays(raw_overlays)
    method_overlays = _parse_method_overlays(data.get("method_overlays"))

    return AstroOntology(
        domains=domains,
        overlays=overlays,
        method_overlays=method_overlays,
        relevance_weights=global_rw,
    )


def merge_relevance_weights(
    global_weights: dict[str, float],
    domains: list[DomainOntology],
) -> dict[str, float]:
    """Later domains in the list override earlier keys (last-wins per field)."""
    merged = dict(global_weights)
    for d in domains:
        merged.update(d.relevance_weights)
    return merged


def merge_paper_role_hints(domains: list[DomainOntology]) -> dict[str, list[str]]:
    """Union hint lists per role across domains."""
    roles: dict[str, set[str]] = {}
    for d in domains:
        for role, hints in d.paper_role_hints.items():
            roles.setdefault(role, set()).update(h.lower() for h in hints)
    return {k: sorted(v) for k, v in roles.items()}


def conditional_blocks_to_pydantic(domain: DomainOntology) -> list[ConditionalNegativeBlock]:
    """Flatten domain.conditional_negatives into schema blocks."""
    blocks: list[ConditionalNegativeBlock] = []
    for _key, spec in domain.conditional_negatives.items():
        neg = spec.get("negative_terms", [])
        allow = spec.get("allow_if", [])
        if neg:
            blocks.append(ConditionalNegativeBlock(negative_terms=neg, allow_if=allow))
    return blocks


def merged_conditional_allow_terms(domains: list[DomainOntology]) -> list[str]:
    """Union of all allow_if phrases from conditional negative blocks (for profile field)."""
    seen: set[str] = set()
    out: list[str] = []
    for d in domains:
        for spec in d.conditional_negatives.values():
            for phrase in spec.get("allow_if", []):
                low = phrase.lower()
                if low not in seen:
                    seen.add(low)
                    out.append(phrase)
    return sorted(out)
