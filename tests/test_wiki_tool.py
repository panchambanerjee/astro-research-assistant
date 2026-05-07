from schemas.paper import CitationCounts, PaperMetadata
from schemas.paper_analysis import PaperAnalysis
from tools.wiki_tool import WIKI_ROOT, slugify_title, write_source_page


def test_slugify_title():
    assert slugify_title("KiDS-450: Cosmic Shear!") == "kids-450-cosmic-shear"
    assert slugify_title("") == "untitled"


def test_write_source_page_creates_expected_files():
    paper = PaperMetadata(
        title="Test S8 Paper",
        authors=["A. Author"],
        year=2024,
        doi="10.1234/test",
        arxiv_id="2401.00001",
        citation_counts=CitationCounts(selected=10, selected_source="test"),
    )

    analysis = PaperAnalysis(
        observables=["cosmic shear"],
        datasets=["DES Y3"],
        instruments=[],
        missions=[],
        parameters=["S8"],
        redshift_range=None,
        wavelength_band=None,
        cosmological_model="flat Lambda CDM",
        methods=["Bayesian inference"],
        systematics=["intrinsic alignment"],
        key_results=["Test key result."],
        limitations=["Test limitation."],
        open_questions=["Test open question."],
    )

    page_path = write_source_page(paper, analysis)

    assert page_path.exists()
    assert "test-s8-paper.md" in str(page_path)

    content = page_path.read_text(encoding="utf-8")
    assert "# Test S8 Paper" in content
    assert "doi: \"10.1234/test\"" in content
    assert "- Observables: cosmic shear" in content
    assert "- Test key result." in content

    assert (WIKI_ROOT / "concepts" / "cosmic-shear.md").exists()
    assert (WIKI_ROOT / "datasets" / "des-y3.md").exists()
    assert (WIKI_ROOT / "parameters" / "s8.md").exists()
    assert (WIKI_ROOT / "methods" / "bayesian-inference.md").exists()


def test_write_source_page_is_idempotent_for_evidence_bullets():
    paper = PaperMetadata(
        title="Idempotent Test Paper",
        year=2024,
    )

    analysis = PaperAnalysis(
        observables=["weak lensing"],
        datasets=[],
        instruments=[],
        missions=[],
        parameters=[],
        redshift_range=None,
        wavelength_band=None,
        cosmological_model=None,
        methods=[],
        systematics=[],
        key_results=["Repeated result."],
        limitations=[],
        open_questions=[],
    )

    write_source_page(paper, analysis)
    write_source_page(paper, analysis)

    concept_path = WIKI_ROOT / "concepts" / "weak-lensing.md"
    content = concept_path.read_text(encoding="utf-8")

    assert content.count("[[sources/idempotent-test-paper|Idempotent Test Paper]]") == 1