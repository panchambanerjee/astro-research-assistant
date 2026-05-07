# Astro Research Assistant (CrewAI)

Python project for an astrophysics/cosmology/astronomy research assistant built with CrewAI.

## Project Goal

Build a multi-agent research workflow that can:
- discover and retrieve relevant papers,
- normalize metadata from trusted sources,
- analyze and synthesize findings into structured outputs,
- maintain an evolving research wiki and reports.

## Current Status

- Project scaffold is in place.
- Core Pydantic schemas are implemented.
- Retrieval and enrichment tools are implemented for OpenAlex, arXiv, NASA ADS, and Semantic Scholar.
- Metadata deduplication, deterministic ranking, PDF handling, and wiki source-page tooling are implemented.
- Agent and crew orchestration is not implemented yet.

## Quick Start

```bash
uv sync
uv run python main.py
```

## Repository Layout

High-level directories:

- `app/`: app-level config and CLI entry scaffolding.
- `agents/`: future CrewAI agent implementations.
- `crews/`: future crew orchestration.
- `tools/`: retrieval, enrichment, ranking, PDF, and wiki tooling.
- `schemas/`: Pydantic models for paper metadata and analysis/report structures.
- `storage/raw/`: source artifacts (papers, metadata, bibtex).
- `storage/wiki/`: generated wiki artifacts (`sources/`, `index.md`, `log.md`).
- `tests/`: unit and integration tests.

## Implemented Modules

### Schemas

- `schemas/paper.py`
  - `PaperIdentity`, `CitationCounts`, `PaperMetadata`, `PaperCandidate`, `RankedPaper`
  - supports DOI/arXiv/ADS/OpenAlex/S2 IDs and multi-source citation counts.
- `schemas/paper_analysis.py`
  - `PaperAnalysis` with astrophysics fields (observables, datasets, instruments, missions, parameters, redshift, wavelength, systematics, methods, limitations, open questions).
- `schemas/hypothesis.py`, `schemas/synthesis.py`, `schemas/report.py`
  - structured outputs for hypothesis generation, synthesis, and final report packaging.

### Tools

- `tools/openalex_tool.py`
  - `search_openalex_works(query, max_results, sort)`
  - reconstructs abstract from OpenAlex inverted index and maps to `PaperMetadata`.
- `tools/arxiv_tool.py`
  - `search_arxiv_papers(query, max_results)`
  - includes astro-ph-aware query fallback strategy.
- `tools/ads_tool.py`
  - `search_ads_papers(query, max_results)`
  - requires `NASA_ADS_API_KEY`.
- `tools/semantic_scholar_tool.py`
  - `enrich_paper_with_semantic_scholar(paper)`
  - DOI -> arXiv -> title fallback, non-destructive merge behavior.
- `tools/metadata_resolver.py`
  - `deduplicate_papers(papers)`
  - merges by IDs first, then fuzzy title fallback when IDs are missing.
- `tools/ranking_tool.py`
  - `rank_papers(papers, topic, current_year)`
  - `select_canonical_papers(...)`
  - `select_recent_high_signal_papers(...)`
  - deterministic scoring with paper-type multipliers.
- `tools/pdf_tool.py`
  - `download_pdf(paper, output_dir)`
  - `extract_text_from_pdf(path, max_pages)`
  - PyMuPDF-first extraction with pdfplumber fallback.
- `tools/wiki_tool.py`
  - `create_source_page(...)`, `write_source_page(...)`, `update_index(...)`, `append_log(...)`, `slugify_title(...)`
  - writes source pages under `storage/wiki/sources/` with YAML frontmatter and Obsidian-style links.

## Environment Variables

Create a local `.env` file:

```bash
OPENALEX_MAILTO=your_email@example.com
NASA_ADS_API_KEY=...
SEMANTIC_SCHOLAR_API_KEY=...
OPENAI_API_KEY=...
```

Notes:
- `NASA_ADS_API_KEY` is required for ADS queries.
- Semantic Scholar can run without an API key, but keyless calls are rate-limited.
- `.env` is gitignored and should never be committed.

## Tool Smoke Tests

Run each tool directly from the repo root:

```bash
uv run python tools/openalex_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/arxiv_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/ads_tool.py "S8 tension weak lensing Planck" --max-results 5
S2_DEBUG=1 uv run python tools/semantic_scholar_tool.py
```

## Tests

Run all unit tests:

```bash
uv run pytest -q
```

Run targeted suites:

```bash
uv run pytest tests/test_metadata_resolver.py -q
uv run pytest tests/test_ranking_tool.py -q
uv run pytest tests/test_pdf_tool.py -q
uv run pytest tests/test_wiki_tool.py -q
uv run pytest tests/test_retrieval_tools.py -q
```

Run a single test:

```bash
uv run pytest tests/test_pdf_tool.py::test_download_pdf_skips_when_file_exists -q
```

Integration marker:

```bash
uv run pytest -m integration -q
```

## Deterministic Ranking Summary

`rank_papers` currently combines:
- citation score: log-normalized selected citation count,
- velocity score: citations per year, log-normalized,
- recency score: deterministic age-decay,
- relevance score: lexical overlap vs topic.

Paper-type multipliers:
- `review` x `0.85`
- `survey_data_release`, `methodology`, `observational_constraint` x `1.05`

## Wiki Output Behavior

- Source pages are written to `storage/wiki/sources/<slug>.md`.
- `storage/wiki/index.md` is updated with Obsidian links.
- `storage/wiki/log.md` receives timestamped append-only events.
- Concept-page updates are intentionally not implemented yet.

## Operational Notes

- `uv.lock` is tracked in git for reproducible installs.
- Tool scripts support direct execution (`uv run python tools/<tool>.py ...`) and package-style imports.
- In restricted/proxy environments, API-backed tool calls may fail with network tunnel/proxy errors; this is environmental rather than schema/tool import failure.
