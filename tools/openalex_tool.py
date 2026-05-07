"""OpenAlex retrieval tool for work search and metadata normalization."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Allow direct script execution: `uv run python tools/openalex_tool.py ...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.paper import CitationCounts, PaperMetadata

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_TIMEOUT_SECONDS = 20

OPENALEX_SELECT_FIELDS = [
    "id",
    "doi",
    "display_name",
    "publication_year",
    "publication_date",
    "type",
    "authorships",
    "primary_location",
    "best_oa_location",
    "locations",
    "abstract_inverted_index",
    "cited_by_count",
    "concepts",
    "primary_topic",
    "ids",
]


def _clean_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _get_openalex_mailto() -> str | None:
    """Resolve OpenAlex mailto from config module first, then environment."""
    try:
        from app import config as app_config

        mailto = getattr(app_config, "OPENALEX_MAILTO", None)
        if isinstance(mailto, str) and mailto.strip():
            return mailto.strip()
    except Exception:
        pass

    env_mailto = os.getenv("OPENALEX_MAILTO")
    if isinstance(env_mailto, str) and env_mailto.strip():
        return env_mailto.strip()
    return None


def _decode_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct OpenAlex abstract text from abstract_inverted_index."""
    if not inverted_index:
        return None

    position_to_token: dict[int, str] = {}
    for token, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                position_to_token[pos] = token

    if not position_to_token:
        return None

    max_pos = max(position_to_token)
    words = [position_to_token.get(i, "") for i in range(max_pos + 1)]
    abstract = " ".join(word for word in words if word).strip()
    return abstract or None


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None

    normalized = doi.strip()
    prefix = "https://doi.org/"

    if normalized.lower().startswith(prefix):
        normalized = normalized[len(prefix):]

    return normalized.lower() or None


def _normalize_openalex_id(openalex_id: str | None) -> str | None:
    if not openalex_id:
        return None

    prefix = "https://openalex.org/"
    if openalex_id.startswith(prefix):
        return openalex_id[len(prefix):]

    return openalex_id


def _extract_arxiv_id(work: dict[str, Any]) -> str | None:
    ids = work.get("ids") or {}

    if isinstance(ids, dict):
        for key in ("arxiv", "arxiv_id"):
            value = ids.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().removeprefix("https://arxiv.org/abs/")

    for location in work.get("locations", []) or []:
        if not isinstance(location, dict):
            continue

        landing = location.get("landing_page_url")
        if isinstance(landing, str) and "arxiv.org/abs/" in landing:
            return landing.rsplit("/abs/", 1)[-1].strip()

        pdf_url = location.get("pdf_url")
        if isinstance(pdf_url, str) and "arxiv.org/pdf/" in pdf_url:
            arxiv_id = pdf_url.rsplit("/pdf/", 1)[-1].strip()
            return arxiv_id.removesuffix(".pdf")

    return None


def _extract_authors(work: dict[str, Any]) -> list[str]:
    authors: list[str] = []

    for authorship in work.get("authorships", []) or []:
        if not isinstance(authorship, dict):
            continue

        author = authorship.get("author") or {}
        if not isinstance(author, dict):
            continue

        name = _clean_str(author.get("display_name"))
        if name:
            authors.append(name)

    return authors


def _extract_journal(work: dict[str, Any]) -> str | None:
    primary_location = work.get("primary_location") or {}
    if not isinstance(primary_location, dict):
        return None

    source = primary_location.get("source") or {}
    if not isinstance(source, dict):
        return None

    return _clean_str(source.get("display_name"))


def _extract_landing_page(work: dict[str, Any]) -> str | None:
    primary_location = work.get("primary_location") or {}
    if isinstance(primary_location, dict):
        landing = _clean_str(primary_location.get("landing_page_url"))
        if landing:
            return landing

    best_oa = work.get("best_oa_location") or {}
    if isinstance(best_oa, dict):
        landing = _clean_str(best_oa.get("landing_page_url"))
        if landing:
            return landing

    return None


def _extract_pdf_url(work: dict[str, Any]) -> str | None:
    primary_location = work.get("primary_location") or {}
    if isinstance(primary_location, dict):
        pdf_url = _clean_str(primary_location.get("pdf_url"))
        if pdf_url:
            return pdf_url

    best_oa = work.get("best_oa_location") or {}
    if isinstance(best_oa, dict):
        pdf_url = _clean_str(best_oa.get("pdf_url"))
        if pdf_url:
            return pdf_url

    for location in work.get("locations", []) or []:
        if not isinstance(location, dict):
            continue

        pdf_url = _clean_str(location.get("pdf_url"))
        if pdf_url:
            return pdf_url

    return None


def _extract_fields_of_study(work: dict[str, Any]) -> list[str]:
    fields: list[str] = []

    for concept in work.get("concepts", []) or []:
        if not isinstance(concept, dict):
            continue

        name = _clean_str(concept.get("display_name"))
        if name:
            fields.append(name)

    primary_topic = work.get("primary_topic") or {}
    if isinstance(primary_topic, dict):
        name = _clean_str(primary_topic.get("display_name"))
        if name:
            fields.append(name)

    return list(dict.fromkeys(fields))


def _map_openalex_publication_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.lower().strip()

    mapping = {
        "article": "journal_article",
        "preprint": "preprint",
        "book-chapter": "book",
        "book": "book",
        "dissertation": "thesis",
        "proceedings-article": "conference_proceedings",
    }

    return mapping.get(value, "other")


def _work_to_metadata(work: dict[str, Any], source_tool: str = "openalex") -> PaperMetadata:
    openalex_citations = _extract_int(work.get("cited_by_count"))
    journal = _extract_journal(work)

    return PaperMetadata(
        openalex_id=_normalize_openalex_id(_clean_str(work.get("id"))),
        arxiv_id=_extract_arxiv_id(work),
        doi=_normalize_doi(_clean_str(work.get("doi"))),
        title=_clean_str(work.get("display_name")),
        year=_extract_int(work.get("publication_year")),
        publication_date=_clean_str(work.get("publication_date")),
        authors=_extract_authors(work),
        journal=journal,
        venue=journal,
        abstract=_decode_abstract(work.get("abstract_inverted_index")),
        publication_type=_map_openalex_publication_type(work.get("type")),
        fields_of_study=_extract_fields_of_study(work),
        citation_counts=CitationCounts(
            openalex=openalex_citations,
            selected=openalex_citations,
            selected_source="openalex" if openalex_citations is not None else None,
        ),
        landing_page_url=_extract_landing_page(work),
        pdf_url=_extract_pdf_url(work),
        source_url=_clean_str(work.get("id")),
        source_tools=[source_tool],
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
)
def _fetch_openalex_works(
    query: str,
    max_results: int,
    sort: str,
) -> list[dict[str, Any]]:
    """Fetch raw works from OpenAlex API with retries."""
    if not query.strip():
        return []

    params: dict[str, Any] = {
        "search": query,
        "per-page": max(1, min(max_results, 200)),
        "sort": sort,
        "select": ",".join(OPENALEX_SELECT_FIELDS),
    }

    mailto = _get_openalex_mailto()
    if mailto:
        params["mailto"] = mailto

    response = requests.get(
        f"{OPENALEX_WORKS_URL}?{urlencode(params)}",
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = response.json()
    results = payload.get("results", [])

    if not isinstance(results, list):
        raise ValueError("OpenAlex response did not include a list in 'results'.")

    return results


def search_openalex_works(
    query: str,
    max_results: int = 25,
    sort: str = "cited_by_count:desc",
) -> list[PaperMetadata]:
    """Search OpenAlex works and normalize into PaperMetadata objects."""
    raw_works = _fetch_openalex_works(query=query, max_results=max_results, sort=sort)
    return [_work_to_metadata(work) for work in raw_works]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenAlex search smoke test.")
    parser.add_argument("query", nargs="?", default="Planck cosmology")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--sort", type=str, default="cited_by_count:desc")
    args = parser.parse_args()

    papers = search_openalex_works(
        query=args.query,
        max_results=args.max_results,
        sort=args.sort,
    )

    print(f"Fetched {len(papers)} papers from OpenAlex.")
    for idx, paper in enumerate(papers[:5], start=1):
        print(
            f"{idx}. {paper.title} ({paper.year}) | "
            f"openalex_id={paper.openalex_id} | "
            f"arxiv_id={paper.arxiv_id} | "
            f"doi={paper.doi} | "
            f"citations={paper.citation_counts.openalex}"
        )