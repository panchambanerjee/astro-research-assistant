from __future__ import annotations

from pathlib import Path

from schemas.paper import PaperMetadata
from schemas.paper_analysis import PaperAnalysis
import tools.wiki_tool as wiki_tool


def _patch_wiki_paths(tmp_path: Path, monkeypatch) -> None:
    wiki_root = tmp_path / "storage/wiki"
    sources = wiki_root / "sources"
    index = wiki_root / "index.md"
    log = wiki_root / "log.md"
    monkeypatch.setattr(wiki_tool, "WIKI_ROOT", wiki_root)
    monkeypatch.setattr(wiki_tool, "SOURCES_DIR", sources)
    monkeypatch.setattr(wiki_tool, "INDEX_PATH", index)
    monkeypatch.setattr(wiki_tool, "LOG_PATH", log)


def test_slugify_title() -> None:
    assert wiki_tool.slugify_title("S8 tension: weak lensing / Planck") == "s8-tension-weak-lensing-planck"
    assert wiki_tool.slugify_title("   ") == "untitled"


def test_create_source_page_has_frontmatter_and_links() -> None:
    paper = PaperMetadata(title="Test Title", year=2024, doi="10.1234/abc", arxiv_id="2401.00001")
    analysis = PaperAnalysis(key_results=["Main result"], observables=["S8"])

    md = wiki_tool.create_source_page(paper, analysis)
    assert md.startswith("---\n")
    assert "page_type: source" in md
    assert "[[index]]" in md
    assert "[[sources/test-title]]" in md
    assert "## Key Results" in md


def test_write_source_page_updates_index_and_log(tmp_path: Path, monkeypatch) -> None:
    _patch_wiki_paths(tmp_path, monkeypatch)

    paper = PaperMetadata(
        title="KiDS-450 Cosmology",
        year=2017,
        abstract="Weak lensing constraints",
    )
    analysis = PaperAnalysis(
        key_results=["Constrained S8 with weak lensing"],
        observables=["S8"],
    )

    page_path = wiki_tool.write_source_page(paper, analysis)

    assert page_path.exists()
    assert page_path.parent.name == "sources"
    content = page_path.read_text(encoding="utf-8")
    assert "KiDS-450 Cosmology" in content

    index_text = wiki_tool.INDEX_PATH.read_text(encoding="utf-8")
    assert "## Source Pages" in index_text
    assert "[[sources/kids-450-cosmology|KiDS-450 Cosmology]]" in index_text

    log_text = wiki_tool.LOG_PATH.read_text(encoding="utf-8")
    assert "source_page_written" in log_text
    assert "[[sources/kids-450-cosmology|KiDS-450 Cosmology]]" in log_text
