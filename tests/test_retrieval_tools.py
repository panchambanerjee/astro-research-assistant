import os

import pytest
import requests
from dotenv import load_dotenv

from schemas.paper import PaperMetadata
from tools.openalex_tool import search_openalex_works
from tools.arxiv_tool import search_arxiv_papers
from tools.semantic_scholar_tool import enrich_paper_with_semantic_scholar
from tools.ads_tool import search_ads_papers


load_dotenv()


def assert_valid_papers(papers):
    assert isinstance(papers, list)
    assert len(papers) > 0

    for paper in papers:
        metadata = getattr(paper, "metadata", paper)
        assert isinstance(metadata, PaperMetadata)
        assert metadata.title
        assert metadata.title.strip()


@pytest.mark.integration
def test_openalex_search():
    try:
        papers = search_openalex_works("Hubble tension", max_results=3)
    except requests.RequestException as exc:
        pytest.skip(f"OpenAlex unavailable in this environment: {exc}")
    assert_valid_papers(papers)


@pytest.mark.integration
def test_arxiv_search():
    try:
        papers = search_arxiv_papers("Hubble tension", max_results=3)
    except requests.RequestException as exc:
        pytest.skip(f"arXiv unavailable in this environment: {exc}")
    assert_valid_papers(papers)


@pytest.mark.integration
def test_semantic_scholar_search():
    try:
        seed_papers = search_openalex_works("Hubble tension", max_results=1)
    except requests.RequestException as exc:
        pytest.skip(f"OpenAlex unavailable for S2 seed paper: {exc}")
    if not seed_papers:
        pytest.skip("No seed paper available for Semantic Scholar enrichment test")

    enriched = enrich_paper_with_semantic_scholar(seed_papers[0])
    assert isinstance(enriched, PaperMetadata)


@pytest.mark.integration
def test_ads_search():
    if not os.getenv("NASA_ADS_API_KEY"):
        pytest.skip("NASA_ADS_API_KEY not set")

    try:
        papers = search_ads_papers("Hubble tension", max_results=3)
    except requests.RequestException as exc:
        pytest.skip(f"NASA ADS unavailable in this environment: {exc}")
    assert_valid_papers(papers)