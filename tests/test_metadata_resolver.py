from schemas.paper import CitationCounts, PaperMetadata
from tools.metadata_resolver import deduplicate_papers


def test_deduplicate_by_ids_and_preserve_identifiers() -> None:
    p1 = PaperMetadata(
        doi="10.1234/example.1",
        title="Cosmology Constraints from Survey A",
        ads_bibcode="2024A&A...123A...1X",
        citation_counts=CitationCounts(ads=42),
        abstract="Short abstract.",
        pdf_url="https://example.org/not-arxiv.pdf",
    )
    p2 = PaperMetadata(
        doi="https://doi.org/10.1234/example.1",
        title="Cosmology Constraints from Survey A",
        arxiv_id="2401.00001",
        openalex_id="W123",
        semantic_scholar_id="abc123",
        citation_counts=CitationCounts(openalex=15, semantic_scholar=18),
        abstract="Longer abstract with more detail and context.",
        pdf_url="https://arxiv.org/pdf/2401.00001.pdf",
    )

    merged = deduplicate_papers([p1, p2])

    assert len(merged) == 1
    paper = merged[0]
    assert paper.doi == "10.1234/example.1"
    assert paper.ads_bibcode == "2024A&A...123A...1X"
    assert paper.arxiv_id == "2401.00001"
    assert paper.openalex_id == "W123"
    assert paper.semantic_scholar_id == "abc123"
    assert paper.abstract == "Longer abstract with more detail and context."
    assert paper.pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"


def test_selected_citation_priority_ads_then_s2_then_openalex() -> None:
    ads = PaperMetadata(
        doi="10.2000/priority",
        citation_counts=CitationCounts(ads=25, semantic_scholar=5, openalex=7),
    )
    merged_ads = deduplicate_papers([ads])[0]
    assert merged_ads.citation_counts.selected == 25
    assert merged_ads.citation_counts.selected_source == "ads"

    s2 = PaperMetadata(
        doi="10.2000/priority2",
        citation_counts=CitationCounts(semantic_scholar=11, openalex=9),
    )
    merged_s2 = deduplicate_papers([s2])[0]
    assert merged_s2.citation_counts.selected == 11
    assert merged_s2.citation_counts.selected_source == "semantic_scholar"

    oa = PaperMetadata(doi="10.2000/priority3", citation_counts=CitationCounts(openalex=4))
    merged_oa = deduplicate_papers([oa])[0]
    assert merged_oa.citation_counts.selected == 4
    assert merged_oa.citation_counts.selected_source == "openalex"


def test_deduplicate_by_fuzzy_title_when_ids_missing() -> None:
    p1 = PaperMetadata(
        title="S8 tension from weak lensing and CMB combined analysis",
        abstract="a",
    )
    p2 = PaperMetadata(
        title="S8 Tension from Weak Lensing and CMB: combined analysis",
        abstract="A much longer abstract for the same paper.",
    )
    p3 = PaperMetadata(
        title="Completely different title",
        abstract="Different paper.",
    )

    merged = deduplicate_papers([p1, p2, p3])
    assert len(merged) == 2
    assert any(p.title == "Completely different title" for p in merged)
    s8_paper = next(p for p in merged if p.title != "Completely different title")
    assert s8_paper.abstract == "A much longer abstract for the same paper."
