"""Build TopicProfile from user topic + astro ontology (deterministic)."""

from __future__ import annotations

from pathlib import Path

from schemas.topic_profile import ConditionalNegativeBlock, ProfileSource, TopicProfile
from tools.ontology_loader import (
    DomainOntology,
    ProfileOverlay,
    conditional_blocks_to_pydantic,
    load_astro_ontology,
    merge_paper_role_hints,
    merge_relevance_weights,
    merged_conditional_allow_terms,
)


def _domain_match_score(topic_l: str, domain: DomainOntology) -> tuple[float, list[str]]:
    score = 0.0
    matched: list[str] = []
    for alias in domain.aliases:
        if alias.lower() in topic_l:
            score += 2.0
            matched.append(alias)
    for probe in domain.probes:
        if probe.lower() in topic_l:
            score += 0.5
            matched.append(probe)
    for param in domain.parameters:
        if param.lower() in topic_l:
            score += 0.5
            matched.append(param)
    return score, matched


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        key = x.lower()
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def _merge_domain_vocab(domains: list[DomainOntology]) -> dict[str, list[str]]:
    probes: list[str] = []
    surveys: list[str] = []
    parameters: list[str] = []
    methods: list[str] = []
    systematics: list[str] = []
    observables: list[str] = []
    instruments: list[str] = []
    negatives: list[str] = []
    cond_blocks: list[ConditionalNegativeBlock] = []
    arxiv: list[str] = []
    for d in domains:
        probes.extend(d.probes)
        surveys.extend(d.surveys)
        parameters.extend(d.parameters)
        methods.extend(d.methods)
        systematics.extend(d.systematics)
        observables.extend(d.observables)
        instruments.extend(d.instruments)
        negatives.extend(d.negative_topics)
        cond_blocks.extend(conditional_blocks_to_pydantic(d))
        arxiv.extend(d.arxiv_categories)
    return {
        "probes": _dedupe_preserve(probes),
        "surveys_or_missions": _dedupe_preserve(surveys),
        "parameters": _dedupe_preserve(parameters),
        "methods": _dedupe_preserve(methods),
        "systematics": _dedupe_preserve(systematics),
        "observables": _dedupe_preserve(observables),
        "instruments": _dedupe_preserve(instruments),
        "negative_topics": _dedupe_preserve(negatives),
        "conditional_negatives": cond_blocks,
        "arxiv_categories": _dedupe_preserve(arxiv),
    }


def _active_domain_names(primary_name: str | None, domains: list[DomainOntology]) -> set[str]:
    names = {d.name for d in domains}
    if primary_name:
        names.add(primary_name)
    return names


def _overlay_applies(
    topic_l: str,
    ovl: ProfileOverlay,
    active_domain_names: set[str],
) -> tuple[bool, float]:
    """
    Returns (applies, confidence_boost).
    applies_to_domains empty => overlay eligible for any active domain once match_any hits.
    """
    applies = {d.lower() for d in ovl.applies_to_domains}
    active_lower = {n.lower() for n in active_domain_names}
    if applies and not (applies & active_lower):
        return False, 0.0
    if not ovl.match_any:
        return False, 0.0
    if not any(tok in topic_l for tok in ovl.match_any):
        return False, 0.0
    boost = sum(0.04 for b in ovl.match_boost_if if b in topic_l)
    return True, boost


def build_topic_profile(
    topic: str,
    *,
    source: ProfileSource = "ontology",
    ontology_path: Path | None = None,
) -> TopicProfile:
    """Match topic string to ontology domains and profile_overlays; fill TopicProfile."""
    topic_l = topic.lower().strip()
    onto = load_astro_ontology(ontology_path)

    scored: list[tuple[float, str, DomainOntology, list[str]]] = []
    for name, dom in onto.domains.items():
        s, hits = _domain_match_score(topic_l, dom)
        if s > 0:
            scored.append((s, name, dom, hits))
    scored.sort(key=lambda t: -t[0])

    matched_terms: dict[str, list[str]] = {}

    active_domains: list[DomainOntology] = []
    primary_name: str | None = None

    if scored:
        primary_name = scored[0][1]
        active_domains.append(scored[0][2])
        matched_terms[primary_name] = _dedupe_preserve(scored[0][3])
        for s, name, dom, hits in scored[1:]:
            if s >= 1.0:
                active_domains.append(dom)
                if hits:
                    matched_terms[name] = _dedupe_preserve(hits)

    if not active_domains:
        if any(t in topic_l for t in ("jwst", "galaxy", "redshift", "stellar mass", "massive", "early galaxies")):
            gd = onto.domains.get("galaxy_formation")
            if gd:
                active_domains = [gd]
                primary_name = "galaxy_formation"
                _, hits = _domain_match_score(topic_l, gd)
                matched_terms["galaxy_formation"] = _dedupe_preserve(hits)
        else:
            cd = onto.domains.get("cosmology")
            if cd:
                active_domains = [cd]
                primary_name = "cosmology"
                _, hits = _domain_match_score(topic_l, cd)
                matched_terms["cosmology"] = _dedupe_preserve(hits)

    is_de_topic = any(
        t in topic_l
        for t in ("dark energy", "w0", "wa", "equation of state", "expansion history", "time evolution", "cpl")
    )
    is_jwst_topic = any(
        t in topic_l
        for t in ("jwst", "james webb", "high z", "high-z", "high redshift", "massive galaxies", "early galaxies")
    )

    if is_de_topic:
        cd = onto.domains.get("cosmology")
        if cd:
            if cd not in active_domains:
                active_domains.insert(0, cd)
            primary_name = "cosmology"
            _, hits = _domain_match_score(topic_l, cd)
            if hits:
                matched_terms["cosmology"] = _dedupe_preserve(matched_terms.get("cosmology", []) + hits)
    elif is_jwst_topic:
        gd = onto.domains.get("galaxy_formation")
        if gd:
            if gd not in active_domains:
                active_domains.append(gd)
            primary_name = "galaxy_formation"
            _, ghits = _domain_match_score(topic_l, gd)
            if ghits:
                matched_terms["galaxy_formation"] = _dedupe_preserve(
                    matched_terms.get("galaxy_formation", []) + ghits
                )

    vocab = _merge_domain_vocab(active_domains)
    allow_terms = merged_conditional_allow_terms(active_domains)
    rw = merge_relevance_weights(onto.relevance_weights, active_domains)
    role_hints = merge_paper_role_hints(active_domains)

    active_names = _active_domain_names(primary_name, active_domains)

    overlays_hit: list[str] = []
    overlay_boost = 0.0
    for oname, ovl in onto.overlays.items():
        applies, boost = _overlay_applies(topic_l, ovl, active_names)
        if applies:
            overlays_hit.append(oname)
            overlay_boost += boost
            vocab["observables"] = _dedupe_preserve(vocab["observables"] + ovl.observables)
            vocab["surveys_or_missions"] = _dedupe_preserve(vocab["surveys_or_missions"] + ovl.surveys)
            vocab["parameters"] = _dedupe_preserve(vocab["parameters"] + ovl.parameters)
            vocab["systematics"] = _dedupe_preserve(vocab["systematics"] + ovl.systematics)
            vocab["arxiv_categories"] = _dedupe_preserve(vocab["arxiv_categories"] + ovl.arxiv_categories)
    if overlays_hit:
        matched_terms["profile_overlays"] = overlays_hit

    subdomains = [t[1] for t in scored[1:] if t[0] >= 1.0 and t[1] != primary_name]

    n_matched = sum(len(v) for v in matched_terms.values())
    confidence = min(
        1.0,
        0.18 + 0.07 * len(overlays_hit) + overlay_boost + 0.035 * max(1, n_matched),
    )

    return TopicProfile(
        original_topic=topic,
        source=source,
        primary_domain=primary_name,
        subdomains=_dedupe_preserve(subdomains),
        probes=vocab["probes"],
        surveys_or_missions=vocab["surveys_or_missions"],
        parameters=vocab["parameters"],
        methods=vocab["methods"],
        systematics=vocab["systematics"],
        observables=vocab["observables"],
        instruments=vocab["instruments"],
        arxiv_categories=vocab["arxiv_categories"],
        paper_role_hints=role_hints,
        relevance_weights=rw,
        negative_topics=vocab["negative_topics"],
        conditional_negatives=vocab["conditional_negatives"],
        conditional_allow_terms=_dedupe_preserve(allow_terms),
        matched_terms={k: _dedupe_preserve(v) for k, v in matched_terms.items() if v},
        profile_confidence=confidence,
    )
