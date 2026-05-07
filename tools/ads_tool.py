"""NASA ADS retrieval tool for astrophysics paper search."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Allow direct script execution: `uv run python tools/ads_tool.py ...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.paper import CitationCounts, PaperMetadata

ADS_SEARCH_URL = "https://api.adsabs.harvard.edu/v1/search/query"
DEFAULT_TIMEOUT_SECONDS = 20


def _get_ads_api_key() -> str:
    """Resolve NASA ADS API key from config/env and raise clear guidance if missing."""
    try:
        from app import config as app_config

        key = getattr(app_config, "NASA_ADS_API_KEY", None)
        if isinstance(key, str) and key.strip():
            return key.strip()
    except Exception:
        pass

    key = os.getenv("NASA_ADS_API_KEY")
    if isinstance(key, str) and key.strip():
        return key.strip()

    # Load from .env as a fallback if caller has not already loaded env vars.
    load_dotenv()
    key = os.getenv("NASA_ADS_API_KEY")
    if isinstance(key, str) and key.strip():
        return key.strip()

    raise RuntimeError(
        "NASA_ADS_API_KEY is required but not set. "
        "Add `NASA_ADS_API_KEY=your_key_here` to your `.env` file or export it in your shell."
    )


def _extract_doi(doi_field: Any) -> str | None:
    if isinstance(doi_field, list) and doi_field:
        first = doi_field[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    if isinstance(doi_field, str) and doi_field.strip():
        return doi_field.strip()
    return None


def _build_landing_page_url(bibcode: str | None) -> str | None:
    if not bibcode:
        return None
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}/abstract"


def _doc_to_metadata(doc: dict[str, Any]) -> PaperMetadata:
    title_field = doc.get("title")
    title = title_field[0].strip() if isinstance(title_field, list) and title_field else None

    author_field = doc.get("author")
    authors = (
        [a.strip() for a in author_field if isinstance(a, str) and a.strip()]
        if isinstance(author_field, list)
        else []
    )

    citation_count = doc.get("citation_count")
    ads_citations = _extract_int(citation_count)

    bibcode = doc.get("bibcode")
    bibcode = bibcode.strip() if isinstance(bibcode, str) and bibcode.strip() else None

    year = _extract_year(doc)

    abstract = doc.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        abstract = None

    return PaperMetadata(
        ads_bibcode=bibcode,
        doi=_extract_doi(doc.get("doi")),
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        landing_page_url=_build_landing_page_url(bibcode),
        source_url=_build_landing_page_url(bibcode),
        citation_counts=CitationCounts(
            ads=ads_citations,
            selected=ads_citations,
            selected_source="ads" if ads_citations is not None else None,
        ),
        source_tools=["ads"],
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
)
def _fetch_ads_docs(query: str, max_results: int) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    params = {
        "q": query,
        "rows": max(1, min(max_results, 200)),
        "sort": "citation_count desc",
        "fl": "title,author,year,pubdate,abstract,bibcode,doi,citation_count",
    }
    url = f"{ADS_SEARCH_URL}?{urlencode(params)}"
    headers = {
        "Authorization": f"Bearer {_get_ads_api_key()}",
        "Accept": "application/json",
    }
    response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
    response.raise_for_status()

    payload = response.json()
    response_section = payload.get("response", {})
    docs = response_section.get("docs", [])
    if not isinstance(docs, list):
        raise ValueError("ADS API response missing list at response.docs.")
    return docs


def search_ads_papers(query: str, max_results: int = 25) -> list[PaperMetadata]:
    """Search NASA ADS and normalize results to PaperMetadata."""
    docs = _fetch_ads_docs(query=query, max_results=max_results)
    return [_doc_to_metadata(doc) for doc in docs]


def _extract_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _extract_year(doc: dict[str, Any]) -> int | None:
    year = doc.get("year")
    parsed = _extract_int(year)
    if parsed is not None:
        return parsed

    pubdate = doc.get("pubdate")
    if isinstance(pubdate, str) and pubdate.strip():
        try:
            return int(pubdate.strip()[:4])
        except ValueError:
            return None

    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NASA ADS search smoke test.")
    parser.add_argument("query", nargs="?", default="Hubble constant tension")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()

    try:
        papers = search_ads_papers(query=args.query, max_results=args.max_results)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1) from exc

    print(f"Fetched {len(papers)} papers from NASA ADS.")
    for idx, paper in enumerate(papers[:5], start=1):
        print(
            f"{idx}. {paper.title} ({paper.year}) | "
            f"bibcode={paper.ads_bibcode} | "
            f"doi={paper.doi} | "
            f"citations={paper.citation_counts.ads}"
        )
