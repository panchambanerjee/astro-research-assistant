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
- Agent scaffolds and prompt files are implemented for topic expansion, paper analysis, synthesis, hypothesis generation, skeptical review, and report compilation.
- A sequential CrewAI research pipeline is implemented in `crews/research_crew.py` and is ready to consume pre-selected papers from app/CLI.

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
- `schemas/topic_expansion.py`
  - `TopicExpansion` schema for canonical queries, aliases, observables, surveys, parameters, systematics, subfields, and arXiv categories.
- `schemas/paper_analysis.py`, `schemas/hypothesis.py`, and `schemas/synthesis.py` include extended fields aligned to current agent outputs.

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
  - updates evidence pages under `storage/wiki/concepts/`, `storage/wiki/datasets/`, `storage/wiki/parameters/`, and `storage/wiki/methods/`.

### Agents and Crew

- Prompt files:
  - `prompts/topic_expansion.md`
  - `prompts/paper_analysis.md`
  - `prompts/synthesis.md`
  - `prompts/hypothesis_generation.md`
  - `prompts/skeptical_review.md`
  - `prompts/report_compilation.md`
- Agent scaffolds:
  - `agents/topic_expander.py`
  - `agents/paper_analyzer.py`
  - `agents/synthesis_agent.py`
  - `agents/research_strategist.py`
  - `agents/skeptical_referee.py`
  - `agents/report_compiler.py`
- Crew orchestration:
  - `crews/research_crew.py` exposes `build_research_crew(llm) -> Crew`
  - Uses `Process.sequential` with tasks:
    1. analyze selected papers
    2. synthesize field
    3. generate hypotheses
    4. critique hypotheses
    5. compile report
  - Paper retrieval/ranking/download is intentionally outside the crew (to be handled by app/CLI before kickoff).

### Ontology

- `ontology/parameters.yaml`:
  - core parameter entries (e.g. `S8`, `H0`, `Omega_m`, `sigma8`).
- `ontology/surveys_and_missions.yaml`:
  - survey/mission metadata (e.g. Planck, DES, KiDS, HSC, DESI, JWST).
- `ontology/systematics.yaml`:
  - probe-specific systematic effects (weak lensing, CMB, high-z galaxies).
- `ontology/cosmology_topics.yaml`:
  - populated topic ontology (Hubble tension, S8 tension, dark energy evolution, inflation, neutrino cosmology, LSS, modified gravity, reionization, etc.).
- `ontology/observables.yaml`:
  - populated observable ontology (CMB TT/EE, CMB lensing, BAO, RSD, SN Ia, cosmic shear, galaxy clustering, cluster counts, standard sirens, Ly-alpha forest, 21cm).

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

Wiki smoke script:

```bash
uv run python scripts/test_wiki_tool.py
```

Idempotency check (run twice):

```bash
uv run python scripts/test_wiki_tool.py
uv run python scripts/test_wiki_tool.py
```

Expected behavior: evidence bullets are not duplicated when the same source/analysis is written repeatedly.

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
- Source page frontmatter currently uses `updated_at` (MVP behavior) and rewrites the page on updates.
- `storage/wiki/index.md` is updated with Obsidian links.
- `storage/wiki/log.md` receives timestamped append-only events.
- Evidence pages are updated under:
  - `storage/wiki/concepts/`
  - `storage/wiki/datasets/`
  - `storage/wiki/parameters/`
  - `storage/wiki/methods/`
- Evidence pages use YAML frontmatter (`page_type`, `title`) and keep an `## Evidence from sources` section.
- Legacy evidence pages are auto-upgraded to frontmatter format the next time they are updated.
- Evidence entries are append-only and deduplicated per source bullet.

## Recent Updates

- Added smoke test script for wiki flows: `scripts/test_wiki_tool.py`.
- Verified idempotency by running the wiki smoke flow multiple times (no duplicate evidence bullets for identical source entries).
- Added YAML frontmatter for evidence pages (`page_type`, `title`) and auto-upgrade for legacy pages.
- Switched source page frontmatter timestamp from `created_at` to `updated_at` for MVP semantics.
- Populated previously empty ontology files:
  - `ontology/cosmology_topics.yaml`
  - `ontology/observables.yaml`
- Added topic expansion schema (`schemas/topic_expansion.py`) and expanded analysis/synthesis/hypothesis schemas for agent outputs.
- Added agent prompt files and typed agent scaffolds.
- Added sequential CrewAI pipeline in `crews/research_crew.py`.

## Operational Notes

- `uv.lock` is tracked in git for reproducible installs.
- Tool scripts support direct execution (`uv run python tools/<tool>.py ...`) and package-style imports.
- In restricted/proxy environments, API-backed tool calls may fail with network tunnel/proxy errors; this is environmental rather than schema/tool import failure.
