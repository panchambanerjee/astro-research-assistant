"""Map TopicProfile to TopicExpansion (retrieval / query layer only)."""

from __future__ import annotations

from pathlib import Path

from schemas.topic_expansion import TopicExpansion
from schemas.topic_profile import TopicProfile
from tools.ontology_loader import load_astro_ontology


def topic_profile_to_expansion(profile: TopicProfile, ontology_path: Path | None = None) -> TopicExpansion:
    """Build TopicExpansion from a TopicProfile plus profile overlay search queries."""
    onto = load_astro_ontology(ontology_path)

    canonical_queries: set[str] = {
        profile.original_topic.strip(),
        f"{profile.original_topic.strip()} cosmology",
        f"{profile.original_topic.strip()} observational constraints",
        f"{profile.original_topic.strip()} review",
    }

    arxiv_categories: set[str] = set(profile.arxiv_categories or [])
    overlay_names = profile.matched_terms.get("profile_overlays") or profile.matched_terms.get("overlays", [])
    for oname in overlay_names:
        ovl = onto.overlays.get(oname)
        if ovl:
            canonical_queries.update(ovl.canonical_queries)

    negative_terms = sorted({n.lower() for n in profile.negative_topics if n})

    subfield_parts = {p for p in profile.subdomains if p}
    if profile.primary_domain:
        subfield_parts.add(profile.primary_domain)

    return TopicExpansion(
        original_topic=profile.original_topic,
        canonical_queries=sorted(canonical_queries),
        aliases=sorted({profile.original_topic, *subfield_parts}),
        observables=list(profile.observables),
        surveys=list(profile.surveys_or_missions),
        instruments=list(profile.instruments),
        parameters=list(profile.parameters),
        systematics=list(profile.systematics),
        negative_terms=negative_terms,
        source_urls=[],
        subfields=sorted(subfield_parts),
        arxiv_categories=sorted(arxiv_categories),
    )
