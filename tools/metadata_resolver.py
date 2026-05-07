"""Utilities to resolve and deduplicate paper metadata records."""

from __future__ import annotations

import re
from collections import defaultdict

from rapidfuzz import fuzz

from schemas.paper import PaperMetadata

_FUZZY_TITLE_THRESHOLD = 94


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_doi(doi: str | None) -> str | None:
    value = _clean(doi)
    if not value:
        return None
    value = value.lower()
    prefixes = ("https://doi.org/", "http://doi.org/", "doi:")
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.strip() or None


def _normalize_arxiv_id(arxiv_id: str | None) -> str | None:
    value = _clean(arxiv_id)
    if not value:
        return None
    value = value.lower()
    prefixes = ("https://arxiv.org/abs/", "http://arxiv.org/abs/", "arxiv:")
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
    # Normalize optional version suffix, e.g. 2301.12345v2 -> 2301.12345
    value = re.sub(r"v\d+$", "", value)
    return value.strip() or None


def _normalize_generic(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return cleaned.lower()


def _normalize_title(title: str | None) -> str | None:
    value = _clean(title)
    if not value:
        return None
    value = re.sub(r"\s+", " ", value.lower()).strip()
    return value or None


def _has_any_identifier(paper: PaperMetadata) -> bool:
    return any(
        [
            _normalize_doi(paper.doi),
            _normalize_arxiv_id(paper.arxiv_id),
            _normalize_generic(paper.ads_bibcode),
            _normalize_generic(paper.openalex_id),
            _normalize_generic(paper.semantic_scholar_id),
        ]
    )


def _iter_identifiers(paper: PaperMetadata) -> list[tuple[str, str]]:
    identifiers: list[tuple[str, str]] = []
    if (value := _normalize_doi(paper.doi)):
        identifiers.append(("doi", value))
    if (value := _normalize_arxiv_id(paper.arxiv_id)):
        identifiers.append(("arxiv", value))
    if (value := _normalize_generic(paper.ads_bibcode)):
        identifiers.append(("ads", value))
    if (value := _normalize_generic(paper.openalex_id)):
        identifiers.append(("openalex", value))
    if (value := _normalize_generic(paper.semantic_scholar_id)):
        identifiers.append(("s2", value))
    return identifiers


def _union(parent: list[int], rank: list[int], a: int, b: int) -> None:
    ra = _find(parent, a)
    rb = _find(parent, b)
    if ra == rb:
        return
    if rank[ra] < rank[rb]:
        parent[ra] = rb
    elif rank[ra] > rank[rb]:
        parent[rb] = ra
    else:
        parent[rb] = ra
        rank[ra] += 1


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _pick_longest_non_empty(values: list[str | None]) -> str | None:
    non_empty = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    if not non_empty:
        return None
    return max(non_empty, key=len)


def _pick_first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pick_best_pdf_url(group: list[PaperMetadata]) -> str | None:
    arxiv_urls: list[str] = []
    other_urls: list[str] = []

    for paper in group:
        url = _clean(paper.pdf_url)
        if not url:
            continue
        if "arxiv.org" in url.lower() or (paper.arxiv_id and "arxiv" in url.lower()):
            arxiv_urls.append(url)
        else:
            other_urls.append(url)

    if arxiv_urls:
        return arxiv_urls[0]
    if other_urls:
        return other_urls[0]
    return None


def _merge_string_lists(group: list[PaperMetadata], field_name: str) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for paper in group:
        for value in getattr(paper, field_name):
            cleaned = value.strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                merged.append(cleaned)
    return merged


def _merge_group(group: list[PaperMetadata]) -> PaperMetadata:
    merged = PaperMetadata.model_validate(group[0].model_dump())

    merged.doi = _pick_first_non_empty([p.doi for p in group])
    merged.arxiv_id = _pick_first_non_empty([p.arxiv_id for p in group])
    merged.ads_bibcode = _pick_first_non_empty([p.ads_bibcode for p in group])
    merged.openalex_id = _pick_first_non_empty([p.openalex_id for p in group])
    merged.semantic_scholar_id = _pick_first_non_empty([p.semantic_scholar_id for p in group])
    merged.corpus_id = _pick_first_non_empty([p.corpus_id for p in group])

    merged.title = _pick_first_non_empty([p.title for p in group])
    merged.authors = _merge_string_lists(group, "authors")
    merged.year = next((p.year for p in group if p.year is not None), None)
    merged.publication_date = _pick_first_non_empty([p.publication_date for p in group])
    merged.abstract = _pick_longest_non_empty([p.abstract for p in group])
    merged.journal = _pick_first_non_empty([p.journal for p in group])
    merged.venue = _pick_first_non_empty([p.venue for p in group])

    merged.pdf_url = _pick_best_pdf_url(group)
    merged.landing_page_url = _pick_first_non_empty([p.landing_page_url for p in group])
    merged.source_url = _pick_first_non_empty([p.source_url for p in group])

    merged.fields_of_study = _merge_string_lists(group, "fields_of_study")
    merged.arxiv_categories = _merge_string_lists(group, "arxiv_categories")
    merged.datasets = _merge_string_lists(group, "datasets")
    merged.observables = _merge_string_lists(group, "observables")
    merged.instruments = _merge_string_lists(group, "instruments")
    merged.missions = _merge_string_lists(group, "missions")
    merged.parameters = _merge_string_lists(group, "parameters")
    merged.systematics = _merge_string_lists(group, "systematics")
    merged.source_tools = _merge_string_lists(group, "source_tools")

    ads = max((p.citation_counts.ads for p in group if p.citation_counts.ads is not None), default=None)
    s2 = max(
        (p.citation_counts.semantic_scholar for p in group if p.citation_counts.semantic_scholar is not None),
        default=None,
    )
    openalex = max(
        (p.citation_counts.openalex for p in group if p.citation_counts.openalex is not None),
        default=None,
    )
    merged.citation_counts.ads = ads
    merged.citation_counts.semantic_scholar = s2
    merged.citation_counts.openalex = openalex

    if ads is not None:
        merged.citation_counts.selected = ads
        merged.citation_counts.selected_source = "ads"
    elif s2 is not None:
        merged.citation_counts.selected = s2
        merged.citation_counts.selected_source = "semantic_scholar"
    elif openalex is not None:
        merged.citation_counts.selected = openalex
        merged.citation_counts.selected_source = "openalex"
    else:
        merged.citation_counts.selected = None
        merged.citation_counts.selected_source = None

    return merged


def deduplicate_papers(papers: list[PaperMetadata]) -> list[PaperMetadata]:
    """Deduplicate papers by known IDs, then by fuzzy title when IDs are missing."""
    if not papers:
        return []

    parent = list(range(len(papers)))
    rank = [0] * len(papers)

    id_index: dict[tuple[str, str], int] = {}
    for i, paper in enumerate(papers):
        for key in _iter_identifiers(paper):
            if key in id_index:
                _union(parent, rank, i, id_index[key])
            else:
                id_index[key] = i

    no_id_indices = [i for i, paper in enumerate(papers) if not _has_any_identifier(paper)]
    for pos, i in enumerate(no_id_indices):
        title_i = _normalize_title(papers[i].title)
        if not title_i:
            continue
        for j in no_id_indices[pos + 1 :]:
            title_j = _normalize_title(papers[j].title)
            if not title_j:
                continue
            if fuzz.token_set_ratio(title_i, title_j) >= _FUZZY_TITLE_THRESHOLD:
                _union(parent, rank, i, j)

    groups: dict[int, list[PaperMetadata]] = defaultdict(list)
    for i, paper in enumerate(papers):
        groups[_find(parent, i)].append(paper)

    # Preserve stable ordering based on first appearance in input.
    root_order = sorted(groups.keys(), key=lambda root: min(i for i, p in enumerate(papers) if _find(parent, i) == root))
    return [_merge_group(groups[root]) for root in root_order]
