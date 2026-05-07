from pathlib import Path
import sys

# Allow running this file directly: `uv run python scripts/test_wiki_tool.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.paper import CitationCounts, PaperMetadata
from schemas.paper_analysis import PaperAnalysis
from tools.wiki_tool import (
    INDEX_PATH,
    LOG_PATH,
    WIKI_ROOT,
    write_source_page,
)


def main():
    paper = PaperMetadata(
        title="KiDS-450: cosmological parameter constraints from tomographic weak gravitational lensing",
        authors=["Hildebrandt, H.", "Viola, M.", "Heymans, C."],
        year=2017,
        doi="10.1093/mnras/stw2805",
        arxiv_id="1606.05338",
        ads_bibcode="2017MNRAS.465.1454H",
        openalex_id="W2442489531",
        semantic_scholar_id="a027a8715ef1dfa16dc36b63f7997e59e52041fd",
        journal="Monthly Notices of the Royal Astronomical Society",
        pdf_url="https://academic.oup.com/mnras/article-pdf/465/2/1454/24243465/stw2805.pdf",
        landing_page_url="https://ui.adsabs.harvard.edu/abs/2017MNRAS.465.1454H/abstract",
        citation_counts=CitationCounts(
            ads=980,
            openalex=1025,
            semantic_scholar=800,
            selected=980,
            selected_source="ads",
        ),
        source_tools=["ads", "openalex", "arxiv", "semantic_scholar"],
    )

    analysis = PaperAnalysis(
        observables=["cosmic shear", "weak gravitational lensing"],
        datasets=["KiDS-450"],
        instruments=["OmegaCAM"],
        missions=[],
        parameters=["S8", "Omega_m", "sigma8"],
        redshift_range="tomographic source redshift bins",
        wavelength_band="optical",
        cosmological_model="flat Lambda CDM",
        methods=["tomographic weak lensing", "two-point correlation functions", "Bayesian parameter inference"],
        systematics=["intrinsic alignment", "photometric redshift uncertainty", "baryonic feedback", "shear calibration"],
        key_results=[
            "KiDS-450 produced cosmological constraints from tomographic weak gravitational lensing.",
            "The inferred clustering amplitude was lower than the Planck-inferred Lambda CDM value.",
        ],
        limitations=[
            "Sensitivity to intrinsic alignment modeling.",
            "Sensitivity to photometric redshift calibration.",
        ],
        open_questions=[
            "How much of the S8 discrepancy is due to weak-lensing systematics?",
            "How robust are the constraints to baryonic feedback modeling?",
        ],
    )

    page_path = write_source_page(paper, analysis)

    print(f"Wrote source page: {page_path}")
    print(f"Wiki root: {WIKI_ROOT}")
    print(f"Index exists: {INDEX_PATH.exists()} -> {INDEX_PATH}")
    print(f"Log exists: {LOG_PATH.exists()} -> {LOG_PATH}")

    expected_paths = [
        page_path,
        WIKI_ROOT / "concepts" / "cosmic-shear.md",
        WIKI_ROOT / "concepts" / "weak-gravitational-lensing.md",
        WIKI_ROOT / "concepts" / "flat-lambda-cdm.md",
        WIKI_ROOT / "datasets" / "kids-450.md",
        WIKI_ROOT / "parameters" / "s8.md",
        WIKI_ROOT / "parameters" / "omega-m.md",
        WIKI_ROOT / "parameters" / "sigma8.md",
        WIKI_ROOT / "methods" / "tomographic-weak-lensing.md",
    ]

    print("\nExpected pages:")
    for path in expected_paths:
        print(f"- {path.exists()} {path}")

    print("\nSource page preview:")
    print(page_path.read_text(encoding="utf-8")[:1500])

    print("\nIndex preview:")
    print(INDEX_PATH.read_text(encoding="utf-8")[:1500])

    print("\nLog preview:")
    print(LOG_PATH.read_text(encoding="utf-8")[-1500:])


if __name__ == "__main__":
    main()