"""arXiv retrieval tool for searching astrophysics literature."""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Iterable

import arxiv

# Allow direct script execution: `uv run python tools/arxiv_tool.py ...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.paper import PaperMetadata


def _tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_+\-]+", query)
    stopwords = {
        "the", "and", "or", "of", "in", "to", "with", "between", "a", "an",
        "for", "from", "on", "using", "by", "around", "into",
    }
    return [t for t in tokens if t.lower() not in stopwords]


def _guess_arxiv_category(query: str) -> str:
    q = query.lower()

    cosmology_terms = {
        "cosmology", "hubble", "s8", "sigma8", "planck", "cmb", "bao",
        "dark energy", "lambda", "lcdm", "weak lensing", "cosmic shear",
        "large scale structure", "desi", "kids", "hsc", "des",
    }
    if any(term in q for term in cosmology_terms):
        return "astro-ph.CO"

    exoplanet_terms = {"exoplanet", "planet", "atmosphere", "transit", "tess", "kepler"}
    if any(term in q for term in exoplanet_terms):
        return "astro-ph.EP"

    galaxy_terms = {"galaxy", "galaxies", "jwst", "redshift", "stellar mass", "reionization"}
    if any(term in q for term in galaxy_terms):
        return "astro-ph.GA"

    high_energy_terms = {"black hole", "x-ray", "gamma", "agn", "quasar", "chandra", "xmm"}
    if any(term in q for term in high_energy_terms):
        return "astro-ph.HE"

    instrumentation_terms = {"instrument", "detector", "telescope", "pipeline", "survey design"}
    if any(term in q for term in instrumentation_terms):
        return "astro-ph.IM"

    return "astro-ph*"


def _build_arxiv_queries(query: str) -> list[str]:
    """Build preferred and fallback arXiv API queries."""
    clean_query = query.strip()
    if not clean_query:
        return []

    if "cat:" in clean_query or "all:" in clean_query or "ti:" in clean_query or "abs:" in clean_query:
        return [clean_query]

    tokens = _tokenize_query(clean_query)
    if not tokens:
        return [clean_query]

    category = _guess_arxiv_category(clean_query)
    all_terms = " AND ".join(f'all:"{token}"' for token in tokens)

    return [
        f"({all_terms}) AND cat:{category}",
        f'all:"{clean_query}" AND cat:{category}',
        f'(({all_terms}) OR all:"{clean_query}") AND cat:{category}',
        all_terms,
        clean_query,
    ]


def _result_to_paper_metadata(result: arxiv.Result) -> PaperMetadata:
    arxiv_id = result.get_short_id()
    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=result.title.strip() if result.title else None,
        authors=[author.name for author in result.authors if getattr(author, "name", None)],
        year=result.published.year if result.published else None,
        publication_date=result.published.date().isoformat() if result.published else None,
        abstract=result.summary.strip() if result.summary else None,
        pdf_url=result.pdf_url,
        landing_page_url=result.entry_id,
        source_url=result.entry_id,
        publication_type="preprint",
        arxiv_categories=list(result.categories or []),
        source_tools=["arxiv"],
    )


def _search_raw(query: str, max_results: int) -> Iterable[arxiv.Result]:
    client = arxiv.Client(page_size=min(max_results, 100), delay_seconds=3.0, num_retries=5)
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
        sort_order=arxiv.SortOrder.Descending,
    )
    return client.results(search)


def search_arxiv_papers(query: str, max_results: int = 25) -> list[PaperMetadata]:
    """Search arXiv and return normalized `PaperMetadata` records."""
    if not query.strip():
        return []

    max_results = max(1, min(max_results, 200))

    for idx, candidate_query in enumerate(_build_arxiv_queries(query)):
        papers = [_result_to_paper_metadata(result) for result in _search_raw(candidate_query, max_results)]
        if papers or idx == len(_build_arxiv_queries(query)) - 1:
            return papers

    return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="arXiv search smoke test")
    parser.add_argument("query", nargs="?", default="cosmological parameter inference")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args()

    found = search_arxiv_papers(query=args.query, max_results=args.max_results)
    print(f"Fetched {len(found)} papers from arXiv.")
    for i, paper in enumerate(found[:5], start=1):
        print(
            f"{i}. {paper.title} ({paper.year}) | "
            f"arxiv_id={paper.arxiv_id} | "
            f"landing={paper.landing_page_url}"
        )