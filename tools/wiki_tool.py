"""Wiki helpers for source pages under storage/wiki/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from schemas.paper import PaperMetadata
from schemas.paper_analysis import PaperAnalysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WIKI_ROOT = PROJECT_ROOT / "storage/wiki"
SOURCES_DIR = WIKI_ROOT / "sources"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
DATASETS_DIR = WIKI_ROOT / "datasets"
PARAMETERS_DIR = WIKI_ROOT / "parameters"
METHODS_DIR = WIKI_ROOT / "methods"
INDEX_PATH = WIKI_ROOT / "index.md"
LOG_PATH = WIKI_ROOT / "log.md"


def slugify_title(title: str) -> str:
    """Create filesystem-safe slug from a title."""
    value = (title or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:100] or "untitled"


def _yaml_escape(value: str) -> str:
    return value.replace('"', '\\"')


def _line_or_none(items: list[str]) -> str:
    if not items:
        return "_None_"
    return ", ".join(items)


def _update_evidence_page(
    *,
    directory: Path,
    page_name: str,
    page_type: str,
    source_link: str,
    evidence_text: str,
) -> Path:
    """
    Create or update a wiki evidence page while preserving existing content.

    Appends a bullet under '## Evidence from sources' only if that bullet is new.
    """
    directory.mkdir(parents=True, exist_ok=True)
    slug = slugify_title(page_name)
    page_path = directory / f"{slug}.md"
    bullet = f"- {source_link}: {evidence_text.strip()}"

    if page_path.exists():
        content = page_path.read_text(encoding="utf-8")
        if not content.lstrip().startswith("---"):
            # Backfill legacy evidence pages to frontmatter format.
            lines = content.splitlines()
            lines = [ln for ln in lines if not ln.strip().lower().startswith("type:")]
            normalized = "\n".join(lines).strip()
            content = (
                "---\n"
                f'page_type: "{page_type}"\n'
                f'title: "{_yaml_escape(page_name.strip() or "Untitled")}"\n'
                "---\n\n"
                f"{normalized}\n"
            )
    else:
        title = page_name.strip() or "Untitled"
        content = (
            "---\n"
            f'page_type: "{page_type}"\n'
            f'title: "{_yaml_escape(title)}"\n'
            "---\n\n"
            f"# {title}\n\n"
            "## Evidence from sources\n\n"
        )

    lines = content.splitlines()
    heading = "## Evidence from sources"

    if heading not in lines:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([heading, ""])

    # If exact bullet already exists, keep content unchanged.
    if bullet in lines:
        page_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return page_path

    out: list[str] = []
    in_section = False
    inserted = False
    for line in lines:
        if line.strip() == heading:
            in_section = True
            out.append(line)
            continue
        if in_section and line.startswith("## "):
            if not inserted:
                if out and out[-1].strip():
                    out.append("")
                out.append(bullet)
                inserted = True
            in_section = False
        out.append(line)

    if in_section and not inserted:
        if out and out[-1].strip():
            out.append("")
        out.append(bullet)
        inserted = True
    if not inserted:
        out.extend(["", heading, "", bullet])

    page_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    return page_path


def _update_analysis_pages(paper: PaperMetadata, analysis: PaperAnalysis, source_slug: str, source_title: str) -> list[Path]:
    """Update concept/dataset/parameter/method evidence pages from a PaperAnalysis."""
    source_link = f"[[sources/{source_slug}|{source_title}]]"
    updated_paths: list[Path] = []

    for concept in analysis.observables:
        updated_paths.append(
            _update_evidence_page(
                directory=CONCEPTS_DIR,
                page_name=concept,
                page_type="concept",
                source_link=source_link,
                evidence_text="Reported as an observable in this source.",
            )
        )
    if analysis.cosmological_model:
        updated_paths.append(
            _update_evidence_page(
                directory=CONCEPTS_DIR,
                page_name=analysis.cosmological_model,
                page_type="concept",
                source_link=source_link,
                evidence_text="Used or discussed as the cosmological model.",
            )
        )

    for dataset in analysis.datasets:
        updated_paths.append(
            _update_evidence_page(
                directory=DATASETS_DIR,
                page_name=dataset,
                page_type="dataset",
                source_link=source_link,
                evidence_text="Used or analyzed in this source.",
            )
        )

    for parameter in analysis.parameters:
        updated_paths.append(
            _update_evidence_page(
                directory=PARAMETERS_DIR,
                page_name=parameter,
                page_type="parameter",
                source_link=source_link,
                evidence_text="Constrained or discussed in this source.",
            )
        )

    for method in analysis.methods:
        updated_paths.append(
            _update_evidence_page(
                directory=METHODS_DIR,
                page_name=method,
                page_type="method",
                source_link=source_link,
                evidence_text="Applied in this source.",
            )
        )

    return updated_paths


def create_source_page(paper: PaperMetadata, analysis: PaperAnalysis) -> str:
    """Create markdown content for a source page (with YAML frontmatter)."""
    title = (paper.title or "Untitled Paper").strip()
    slug = slugify_title(title)
    now_iso = datetime.now(timezone.utc).isoformat()

    summary = analysis.key_results[0] if analysis.key_results else (paper.abstract or "")
    summary = summary.strip().replace("\n", " ")
    summary = summary[:240]

    obsidian_id_links = [
        f"doi:{paper.doi}" if paper.doi else None,
        f"arxiv:{paper.arxiv_id}" if paper.arxiv_id else None,
        f"ads:{paper.ads_bibcode}" if paper.ads_bibcode else None,
        f"openalex:{paper.openalex_id}" if paper.openalex_id else None,
        f"s2:{paper.semantic_scholar_id}" if paper.semantic_scholar_id else None,
    ]
    obsidian_id_links = [x for x in obsidian_id_links if x]

    lines = [
        "---",
        f'title: "{_yaml_escape(title)}"',
        f"slug: {slug}",
        "page_type: source",
        f"updated_at: {now_iso}",
        f"year: {paper.year if paper.year is not None else 'null'}",
        f'doi: "{_yaml_escape(paper.doi)}"' if paper.doi else "doi: null",
        f'arxiv_id: "{_yaml_escape(paper.arxiv_id)}"' if paper.arxiv_id else "arxiv_id: null",
        f'ads_bibcode: "{_yaml_escape(paper.ads_bibcode)}"' if paper.ads_bibcode else "ads_bibcode: null",
        f'openalex_id: "{_yaml_escape(paper.openalex_id)}"' if paper.openalex_id else "openalex_id: null",
        (
            f'semantic_scholar_id: "{_yaml_escape(paper.semantic_scholar_id)}"'
            if paper.semantic_scholar_id
            else "semantic_scholar_id: null"
        ),
        "---",
        "",
        f"# {title}",
        "",
        f"[[index]] | [[sources/{slug}]]",
        "",
        "## Summary",
        summary or "_No summary available._",
        "",
        "## Metadata",
        f"- Authors: {_line_or_none(paper.authors)}",
        f"- Year: {paper.year if paper.year is not None else '_Unknown_'}",
        f"- Journal/Venue: {(paper.journal or paper.venue or '_Unknown_')}",
        f"- PDF: {paper.pdf_url or '_Unavailable_'}",
        f"- Landing Page: {paper.landing_page_url or '_Unavailable_'}",
        f"- IDs: {_line_or_none(obsidian_id_links)}",
        "",
        "## Analysis",
        f"- Observables: {_line_or_none(analysis.observables)}",
        f"- Datasets: {_line_or_none(analysis.datasets)}",
        f"- Instruments: {_line_or_none(analysis.instruments)}",
        f"- Missions: {_line_or_none(analysis.missions)}",
        f"- Parameters: {_line_or_none(analysis.parameters)}",
        f"- Redshift Range: {analysis.redshift_range or '_Not specified_'}",
        f"- Wavelength Band: {analysis.wavelength_band or '_Not specified_'}",
        f"- Cosmological Model: {analysis.cosmological_model or '_Not specified_'}",
        f"- Methods: {_line_or_none(analysis.methods)}",
        f"- Systematics: {_line_or_none(analysis.systematics)}",
        "",
        "## Key Results",
    ]
    if analysis.key_results:
        lines.extend([f"- {item}" for item in analysis.key_results])
    else:
        lines.append("- _None extracted yet._")

    lines.extend(
        [
            "",
            "## Limitations",
        ]
    )
    if analysis.limitations:
        lines.extend([f"- {item}" for item in analysis.limitations])
    else:
        lines.append("- _None listed._")

    lines.extend(
        [
            "",
            "## Open Questions",
        ]
    )
    if analysis.open_questions:
        lines.extend([f"- {item}" for item in analysis.open_questions])
    else:
        lines.append("- _None listed._")

    return "\n".join(lines).rstrip() + "\n"


def update_index(page_path: Path, title: str, summary: str, page_type: str) -> None:
    """Append or update source entry in storage/wiki/index.md."""
    WIKI_ROOT.mkdir(parents=True, exist_ok=True)
    relative = page_path.relative_to(WIKI_ROOT).as_posix()
    relative_link = relative[:-3] if relative.endswith(".md") else relative
    link = f"[[{relative_link}|{title}]]"
    summary = (summary or "").strip().replace("\n", " ")
    entry = f"- {link} — {summary}" if summary else f"- {link}"

    if INDEX_PATH.exists():
        text = INDEX_PATH.read_text(encoding="utf-8")
    else:
        text = "# Research Wiki Index\n\n"

    heading = f"## {page_type.title()} Pages"
    lines = text.splitlines()
    if heading not in lines:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([heading, ""])

    out: list[str] = []
    in_section = False
    replaced = False
    for line in lines:
        if line.strip() == heading:
            in_section = True
            out.append(line)
            continue
        if in_section and line.startswith("## "):
            if not replaced:
                out.append(entry)
                replaced = True
            in_section = False
        if in_section and f"[[{relative_link}|" in line:
            if not replaced:
                out.append(entry)
                replaced = True
            continue
        out.append(line)

    if in_section and not replaced:
        out.append(entry)
        replaced = True
    if not replaced:
        out.extend(["", heading, "", entry])

    INDEX_PATH.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def append_log(event_type: str, message: str) -> None:
    """Append event to storage/wiki/log.md."""
    WIKI_ROOT.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        base = LOG_PATH.read_text(encoding="utf-8").rstrip()
    else:
        base = "# Research Wiki Log\n\nChronological log of wiki updates.\n"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    line = f"- [{ts}] ({event_type}) {message.strip()}"
    LOG_PATH.write_text(base + "\n" + line + "\n", encoding="utf-8")


def write_source_page(paper: PaperMetadata, analysis: PaperAnalysis) -> Path:
    """
    Write source page and perform index/log updates.

    Returns absolute path to written page.
    """
    title = (paper.title or "Untitled Paper").strip()
    slug = slugify_title(title)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    page_path = SOURCES_DIR / f"{slug}.md"

    content = create_source_page(paper=paper, analysis=analysis)
    page_path.write_text(content, encoding="utf-8")

    summary = analysis.key_results[0] if analysis.key_results else (paper.abstract or "")
    update_index(page_path=page_path, title=title, summary=summary[:180], page_type="source")
    append_log(event_type="source_page_written", message=f"Wrote [[sources/{slug}|{title}]]")
    updated_pages = _update_analysis_pages(paper=paper, analysis=analysis, source_slug=slug, source_title=title)
    for updated in updated_pages:
        rel = updated.relative_to(WIKI_ROOT).as_posix()
        rel = rel[:-3] if rel.endswith(".md") else rel
        append_log(event_type="evidence_page_updated", message=f"Updated [[{rel}]] from [[sources/{slug}|{title}]]")
    return page_path
