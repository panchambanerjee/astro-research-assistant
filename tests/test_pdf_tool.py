from __future__ import annotations

from pathlib import Path
import types

from schemas.paper import PaperMetadata
from tools.pdf_tool import download_pdf, extract_text_from_pdf


def test_download_pdf_returns_none_without_url(tmp_path: Path) -> None:
    paper = PaperMetadata(title="No PDF URL")
    assert download_pdf(paper, tmp_path) is None


def test_download_pdf_skips_when_file_exists(tmp_path: Path) -> None:
    paper = PaperMetadata(
        title="S8 tension: weak lensing / Planck",
        arxiv_id="2401.12345",
        pdf_url="https://example.org/file.pdf",
    )
    existing = tmp_path / "s8-tension-weak-lensing-planck__arxiv-2401-12345.pdf"
    existing.write_bytes(b"already-here")

    result = download_pdf(paper, tmp_path)

    assert result == existing
    assert result.read_bytes() == b"already-here"


def test_download_pdf_writes_streamed_content(tmp_path: Path, monkeypatch) -> None:
    class _FakeResponse:
        headers = {"Content-Type": "application/pdf"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int = 65536):
            del chunk_size
            yield b"%PDF-"
            yield b"fake"

    def _fake_get(*args, **kwargs):
        del args, kwargs
        return _FakeResponse()

    monkeypatch.setattr("tools.pdf_tool.requests.get", _fake_get)

    paper = PaperMetadata(
        title="Example Paper",
        year=2023,
        pdf_url="https://example.org/paper.pdf",
    )
    path = download_pdf(paper, tmp_path)

    assert path is not None
    assert path.exists()
    assert path.read_bytes() == b"%PDF-fake"


def test_extract_text_from_pdf_missing_file_returns_empty(tmp_path: Path) -> None:
    assert extract_text_from_pdf(tmp_path / "missing.pdf") == ""


def test_extract_text_from_pdf_falls_back_to_pdfplumber(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    class _FakePage:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _FakePdf:
        def __init__(self):
            self.pages = [_FakePage("first"), _FakePage("second"), _FakePage("third")]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_fitz = types.SimpleNamespace(open=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    fake_pdfplumber = types.SimpleNamespace(open=lambda *_args, **_kwargs: _FakePdf())

    monkeypatch.setitem(__import__("sys").modules, "fitz", fake_fitz)
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber", fake_pdfplumber)

    text = extract_text_from_pdf(pdf_path, max_pages=2)
    assert text == "first\n\nsecond"
