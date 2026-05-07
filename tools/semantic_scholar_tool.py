"""Semantic Scholar enrichment tool for PaperMetadata."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv
from rapidfuzz import fuzz
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Allow direct script execution: `uv run python tools/semantic_scholar_tool.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.paper import PaperMetadata

load_dotenv()

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
DEFAULT_TIMEOUT_SECONDS = 20

S2_PAPER_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "year",
        "publicationDate",
        "url",
        "venue",
        "authors",
        "externalIds",
        "openAccessPdf",
        "citationCount",
        "influentialCitationCount",
        "referenceCount",
        "fieldsOfStudy",
        "s2FieldsOfStudy",
        "publicationTypes",
    ]
)


class SemanticScholarRateLimitError(RuntimeError):
    """Raised when Semantic Scholar responds with HTTP 429."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("Semantic Scholar rate limit hit.")
        self.retry_after_seconds = retry_after_seconds


def _debug_enabled() -> bool:
    return os.getenv("S2_DEBUG", "").lower() in {"1", "true", "yes"}


def _debug(message: str) -> None:
    if _debug_enabled():
        print(f"[S2] {message}")


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


def _get_semantic_scholar_api_key() -> str | None:
    """Resolve API key from app config first, then environment."""
    try:
        from app import config as app_config

        api_key = getattr(app_config, "SEMANTIC_SCHOLAR_API_KEY", None)
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    except Exception:
        pass

    env_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if isinstance(env_api_key, str) and env_api_key.strip():
        return env_api_key.strip()

    return None


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}

    api_key = _get_semantic_scholar_api_key()
    if api_key:
        headers["x-api-key"] = api_key
        _debug("Using Semantic Scholar API key.")
    else:
        _debug("No Semantic Scholar API key found; using unauthenticated request.")

    return headers


def _normalize_arxiv_id(arxiv_id: str) -> str:
    normalized = arxiv_id.strip()

    if normalized.lower().startswith("arxiv:"):
        normalized = normalized.split(":", 1)[1]

    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    for prefix in ("https://arxiv.org/pdf/", "http://arxiv.org/pdf/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    normalized = normalized.removesuffix(".pdf")

    if "v" in normalized:
        base, possible_version = normalized.rsplit("v", 1)
        if possible_version.isdigit():
            normalized = base

    return normalized


def _normalize_doi(doi: str) -> str:
    normalized = doi.strip()

    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.lower().startswith(prefix):
            normalized = normalized[len(prefix):]

    return normalized.lower()


def _extract_external_id(record: dict[str, Any], key: str) -> str | None:
    external_ids = record.get("externalIds") or {}
    if not isinstance(external_ids, dict):
        return None

    value = external_ids.get(key)
    return _clean_str(value)


def _extract_authors(record: dict[str, Any]) -> list[str]:
    authors: list[str] = []

    for author in record.get("authors", []) or []:
        if not isinstance(author, dict):
            continue

        name = _clean_str(author.get("name"))
        if name:
            authors.append(name)

    return authors


def _extract_open_access_pdf_url(record: dict[str, Any]) -> str | None:
    open_access_pdf = record.get("openAccessPdf") or {}
    if not isinstance(open_access_pdf, dict):
        return None

    return _clean_str(open_access_pdf.get("url"))


def _extract_fields_of_study(record: dict[str, Any]) -> list[str]:
    fields: list[str] = []

    raw_fields = record.get("fieldsOfStudy") or []
    if isinstance(raw_fields, list):
        for field in raw_fields:
            if isinstance(field, str) and field.strip():
                fields.append(field.strip())

    s2_fields = record.get("s2FieldsOfStudy") or []
    if isinstance(s2_fields, list):
        for field in s2_fields:
            if not isinstance(field, dict):
                continue

            category = _clean_str(field.get("category"))
            if category:
                fields.append(category)

    return list(dict.fromkeys(fields))


def _request_json(url: str) -> dict[str, Any] | None:
    _debug(f"GET {url}")

    response = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT_SECONDS)

    _debug(f"status={response.status_code}")

    if response.status_code >= 400:
        _debug(f"response={response.text[:1500]}")

    if response.status_code == 404:
        return None

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        wait_seconds: float | None = None

        if retry_after is not None:
            try:
                wait_seconds = float(retry_after)
            except ValueError:
                wait_seconds = None

        raise SemanticScholarRateLimitError(wait_seconds)

    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict):
        raise ValueError("Semantic Scholar response was not a JSON object.")

    return payload


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((requests.RequestException, SemanticScholarRateLimitError)),
)
def _fetch_by_identifier(identifier: str) -> dict[str, Any] | None:
    encoded_identifier = quote(identifier, safe=":")
    url = f"{S2_API_BASE}/paper/{encoded_identifier}?fields={S2_PAPER_FIELDS}"

    try:
        return _request_json(url)
    except SemanticScholarRateLimitError as exc:
        if exc.retry_after_seconds and exc.retry_after_seconds > 0:
            wait_time = min(exc.retry_after_seconds, 30)
            _debug(f"Rate limited; sleeping {wait_time} seconds before retry.")
            time.sleep(wait_time)
        raise


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((requests.RequestException, SemanticScholarRateLimitError)),
)
def _search_by_title(title: str) -> dict[str, Any] | None:
    url = (
        f"{S2_API_BASE}/paper/search?"
        f"query={quote_plus(title)}&limit=5&fields={S2_PAPER_FIELDS}"
    )

    try:
        payload = _request_json(url)
    except SemanticScholarRateLimitError as exc:
        if exc.retry_after_seconds and exc.retry_after_seconds > 0:
            wait_time = min(exc.retry_after_seconds, 30)
            _debug(f"Rate limited; sleeping {wait_time} seconds before retry.")
            time.sleep(wait_time)
        raise

    if not payload:
        return None

    data = payload.get("data", [])
    if not isinstance(data, list):
        return None

    best_record: dict[str, Any] | None = None
    best_score = 0

    for item in data:
        if not isinstance(item, dict):
            continue

        result_title = _clean_str(item.get("title"))
        score = fuzz.token_set_ratio(title.lower(), result_title.lower()) if result_title else 0

        _debug(f"title candidate score={score}: {result_title}")

        if score > best_score:
            best_score = score
            best_record = item

    if best_record and best_score >= 90:
        _debug(f"accepted title match with score={best_score}")
        return best_record

    _debug(f"no title match accepted; best_score={best_score}")
    return None


def _pick_semantic_scholar_record(paper: PaperMetadata) -> dict[str, Any] | None:
    if paper.doi:
        doi = _normalize_doi(paper.doi)
        _debug(f"trying DOI:{doi}")
        record = _fetch_by_identifier(f"DOI:{doi}")
        if record:
            _debug("matched by DOI")
            return record

    if paper.arxiv_id:
        arxiv_id = _normalize_arxiv_id(paper.arxiv_id)
        _debug(f"trying ARXIV:{arxiv_id}")
        record = _fetch_by_identifier(f"ARXIV:{arxiv_id}")
        if record:
            _debug("matched by arXiv ID")
            return record

    if paper.title:
        _debug(f"trying title search: {paper.title}")
        return _search_by_title(paper.title)

    return None


def _merge_semantic_scholar_record(
    paper: PaperMetadata,
    record: dict[str, Any],
) -> PaperMetadata:
    enriched = paper.model_copy(deep=True)

    paper_id = _clean_str(record.get("paperId"))
    if not enriched.semantic_scholar_id and paper_id:
        enriched.semantic_scholar_id = paper_id

    if not enriched.title:
        enriched.title = _clean_str(record.get("title"))

    if not enriched.abstract:
        enriched.abstract = _clean_str(record.get("abstract"))

    if enriched.year is None:
        enriched.year = _extract_int(record.get("year"))

    if hasattr(enriched, "publication_date") and not enriched.publication_date:
        enriched.publication_date = _clean_str(record.get("publicationDate"))

    if not enriched.landing_page_url:
        enriched.landing_page_url = _clean_str(record.get("url"))

    if not enriched.source_url:
        enriched.source_url = _clean_str(record.get("url"))

    if not enriched.pdf_url:
        enriched.pdf_url = _extract_open_access_pdf_url(record)

    venue = _clean_str(record.get("venue"))
    if not enriched.journal:
        enriched.journal = venue

    if hasattr(enriched, "venue") and not enriched.venue:
        enriched.venue = venue

    if not enriched.authors:
        enriched.authors = _extract_authors(record)

    doi = _extract_external_id(record, "DOI")
    if not enriched.doi and doi:
        enriched.doi = _normalize_doi(doi)

    arxiv_id = _extract_external_id(record, "ArXiv")
    if not enriched.arxiv_id and arxiv_id:
        enriched.arxiv_id = _normalize_arxiv_id(arxiv_id)

    fields = _extract_fields_of_study(record)
    if hasattr(enriched, "fields_of_study"):
        for field in fields:
            if field not in enriched.fields_of_study:
                enriched.fields_of_study.append(field)

    citation_count = _extract_int(record.get("citationCount"))
    if (
        enriched.citation_counts.semantic_scholar is None
        and citation_count is not None
        and citation_count >= 0
    ):
        enriched.citation_counts.semantic_scholar = citation_count

    influential_count = _extract_int(record.get("influentialCitationCount"))
    if hasattr(enriched.citation_counts, "influential_semantic_scholar"):
        current_value = getattr(enriched.citation_counts, "influential_semantic_scholar")
        if current_value is None and influential_count is not None and influential_count >= 0:
            enriched.citation_counts.influential_semantic_scholar = influential_count

    if (
        enriched.citation_counts.selected is None
        and enriched.citation_counts.semantic_scholar is not None
    ):
        enriched.citation_counts.selected = enriched.citation_counts.semantic_scholar
        enriched.citation_counts.selected_source = "semantic_scholar"

    if "semantic_scholar" not in enriched.source_tools:
        enriched.source_tools.append("semantic_scholar")

    return enriched


def enrich_paper_with_semantic_scholar(paper: PaperMetadata) -> PaperMetadata:
    """
    Enrich a paper with Semantic Scholar data.

    Strategy: DOI first, then arXiv ID, then title search.
    Existing metadata is preserved; only empty target fields are filled.
    """
    try:
        record = _pick_semantic_scholar_record(paper)
    except (requests.RequestException, SemanticScholarRateLimitError, ValueError) as exc:
        _debug(f"enrichment failed: {type(exc).__name__}: {exc}")
        return paper.model_copy(deep=True)

    if not record:
        _debug("no matching record found")
        return paper.model_copy(deep=True)

    return _merge_semantic_scholar_record(paper, record)


def enrich_papers_with_semantic_scholar(papers: list[PaperMetadata]) -> list[PaperMetadata]:
    """
    Enrich multiple papers with Semantic Scholar data.

    This uses single-paper enrichment for now. Later, replace with the
    Semantic Scholar batch endpoint for efficiency.
    """
    enriched: list[PaperMetadata] = []

    for paper in papers:
        enriched.append(enrich_paper_with_semantic_scholar(paper))
        time.sleep(1.0)

    return enriched


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Semantic Scholar enrichment smoke test.")
    parser.add_argument(
        "--title",
        default="KiDS-450: cosmological parameter constraints from tomographic weak gravitational lensing",
    )
    parser.add_argument("--doi", default="10.1093/mnras/stw2805")
    parser.add_argument("--arxiv-id", default="1606.05338")
    args = parser.parse_args()

    seed = PaperMetadata(
        title=args.title,
        doi=args.doi,
        arxiv_id=args.arxiv_id,
    )

    enriched_paper = enrich_paper_with_semantic_scholar(seed)

    print("Semantic Scholar enrichment result:")
    print(f"Title: {enriched_paper.title}")
    print(f"Year: {enriched_paper.year}")
    print(f"DOI: {enriched_paper.doi}")
    print(f"arXiv: {enriched_paper.arxiv_id}")
    print(f"S2 ID: {enriched_paper.semantic_scholar_id}")
    print(f"Citations S2: {enriched_paper.citation_counts.semantic_scholar}")
    print(f"Selected citations: {enriched_paper.citation_counts.selected}")
    print(f"Selected source: {enriched_paper.citation_counts.selected_source}")
    print(f"PDF: {enriched_paper.pdf_url}")
    print(f"Fields: {getattr(enriched_paper, 'fields_of_study', [])}")