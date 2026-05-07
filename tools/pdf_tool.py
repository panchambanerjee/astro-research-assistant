"""PDF download and text extraction helpers."""

from __future__ import annotations

import re
from pathlib import Path

import requests

from schemas.paper import PaperMetadata

_SAFE_CHARS_RE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 100
_DOWNLOAD_TIMEOUT_SECONDS = 45


def _slugify(value: str | None) -> str:
    if not value:
        return "untitled"
    slug = _SAFE_CHARS_RE.sub("-", value.lower()).strip("-")
    if not slug:
        slug = "untitled"
    return slug[:_MAX_SLUG_LEN].strip("-") or "untitled"


def _build_pdf_filename(paper: PaperMetadata) -> str:
    title_part = _slugify(paper.title)
    extras: list[str] = []

    if paper.arxiv_id:
        arxiv_slug = _slugify(paper.arxiv_id.replace("/", "-"))
        extras.append(f"arxiv-{arxiv_slug}")
    elif paper.year is not None:
        extras.append(str(paper.year))

    if extras:
        return f"{title_part}__{'__'.join(extras)}.pdf"
    return f"{title_part}.pdf"


def download_pdf(paper: PaperMetadata, output_dir: Path) -> Path | None:
    """
    Download a paper PDF to output_dir.

    - Uses paper.pdf_url when present.
    - Uses safe filename based on title + arXiv ID/year.
    - Skips network call if target file already exists.
    """
    pdf_url = (paper.pdf_url or "").strip()
    if not pdf_url:
        return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    target_path = output_dir / _build_pdf_filename(paper)
    if target_path.exists() and target_path.is_file():
        return target_path

    tmp_path = target_path.with_suffix(".pdf.part")
    try:
        with requests.get(pdf_url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type and content_type:
                # Continue anyway; some servers return octet-stream for PDFs.
                pass

            with tmp_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        tmp_path.replace(target_path)
        return target_path
    except (requests.RequestException, OSError):
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        return None


def extract_text_from_pdf(path: Path, max_pages: int = 20) -> str:
    """
    Extract text from a PDF.

    Prefers PyMuPDF, falls back to pdfplumber, and returns empty string on failure.
    """
    if max_pages <= 0:
        max_pages = 1
    if not path.exists() or not path.is_file():
        return ""

    # First choice: PyMuPDF (fitz)
    try:
        import fitz  # pymupdf

        text_chunks: list[str] = []
        with fitz.open(path) as doc:
            page_count = min(max_pages, len(doc))
            for page_idx in range(page_count):
                page_text = doc[page_idx].get_text("text") or ""
                page_text = page_text.strip()
                if page_text:
                    text_chunks.append(page_text)
        return "\n\n".join(text_chunks).strip()
    except Exception:
        pass

    # Fallback: pdfplumber
    try:
        import pdfplumber

        text_chunks: list[str] = []
        with pdfplumber.open(path) as pdf:
            page_count = min(max_pages, len(pdf.pages))
            for page_idx in range(page_count):
                page_text = pdf.pages[page_idx].extract_text() or ""
                page_text = page_text.strip()
                if page_text:
                    text_chunks.append(page_text)
        return "\n\n".join(text_chunks).strip()
    except Exception:
        return ""
