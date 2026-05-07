from pathlib import Path
import sys

# Allow running this file directly: `uv run python scripts/test_retrieval_tools.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.openalex_tool import search_openalex_works
from tools.arxiv_tool import search_arxiv_papers
from tools.semantic_scholar_tool import enrich_paper_with_semantic_scholar
from tools.ads_tool import search_ads_papers


def print_papers(name, papers, n=3):
    print(f"\n=== {name} ===")
    print(f"Returned: {len(papers)} papers")

    for i, paper in enumerate(papers[:n], start=1):
        metadata = getattr(paper, "metadata", paper)

        print(f"\n{i}. {metadata.title}")
        print(f"   Year: {metadata.year}")
        print(f"   DOI: {metadata.doi}")
        print(f"   arXiv: {metadata.arxiv_id}")
        print(f"   ADS: {metadata.ads_bibcode}")
        print(f"   S2: {metadata.semantic_scholar_id}")
        print(f"   OpenAlex: {metadata.openalex_id}")
        print(f"   Citations: {metadata.citation_counts}")
        print(f"   PDF: {metadata.pdf_url}")


def main():
    query = "S8 tension weak lensing Planck"

    openalex = search_openalex_works(query, max_results=5)
    print_papers("OpenAlex", openalex)

    arxiv = search_arxiv_papers(query, max_results=5)
    print_papers("arXiv", arxiv)

    semantic_inputs = openalex[:3] if openalex else arxiv[:3]
    semantic = [enrich_paper_with_semantic_scholar(paper) for paper in semantic_inputs]
    print_papers("Semantic Scholar (enrichment)", semantic)

    try:
        ads = search_ads_papers(query, max_results=5)
        print_papers("NASA ADS", ads)
    except Exception as e:
        print("\n=== NASA ADS ===")
        print(f"Skipped or failed: {e}")


if __name__ == "__main__":
    main()