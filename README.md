# Astro Research Assistant

Python project for an astrophysics/cosmology/astronomy research assistant built with CrewAI.

<img width="1254" height="1254" alt="image" src="https://github.com/user-attachments/assets/ae9f2a9a-e2fe-4534-89d9-22a2efbf2d9e" />


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
- **Topic profiling** (`TopicProfile` from `config/astro_ontology.yaml`) drives retrieval expansion, **deterministic relevance** (`profile_relevance_score`, including **`expected_paper_types` alignment**), and **quota-based primary selection** (`selection_policy_from_profile`, `classify_paper_role`).
- Agent scaffolds and prompt files are implemented for topic expansion, paper analysis, synthesis, hypothesis generation, skeptical review, and report compilation.
- A sequential CrewAI research pipeline is implemented in `crews/research_crew.py` and is ready to consume pre-selected papers from app/CLI.

## Quick Start (New User)

### 1) Prerequisites

- Python `3.12+`
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

### 2) Install dependencies

```bash
uv sync
```

### 3) Configure environment

Create `.env` in the repo root:

```bash
OPENALEX_MAILTO=your_email@example.com
NASA_ADS_API_KEY=...
SEMANTIC_SCHOLAR_API_KEY=...
OPENAI_API_KEY=...
BRAVE_SEARCH_API_KEY=...
```

Minimum recommended for first live run:
- `OPENALEX_MAILTO`
- `OPENAI_API_KEY`

### 4) Run your first research command

Live retrieval (recommended real run):

```bash
uv run python main.py research "Dark Energy evolution over time" --max-papers 5
```

Offline deterministic run (no external retrieval APIs):

```bash
uv run python main.py research "Dark Energy evolution over time" --max-papers 5 --input-json evals/fixture_papers_dark_energy.json
```

### 5) Where outputs go

- Report markdown: `reports/<topic-slug>.md`
- Wiki source pages: `storage/wiki/sources/`
- Wiki index/log: `storage/wiki/index.md`, `storage/wiki/log.md`

If you only want to see CLI options:

```bash
uv run python main.py research --help
```

## Repository Layout

High-level directories:

- `app/`: app-level config and Typer CLI (`app/cli.py`).
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
  - `TopicExpansion`: retrieval/query layer (search strings, aliases, observables, surveys, parameters, systematics, subfields, arXiv categories). **Not** copied into per-paper `PaperAnalysis` unless the paper text supports it.
- `schemas/topic_profile.py`
  - `TopicProfile`: deterministic interpretation of the user topic (`profile_version`, `source`, `primary_domain`, vocabulary lists, **`expected_paper_types`**, `negative_topics`, `conditional_negatives`, `conditional_allow_terms`, `matched_terms` including **`profile_overlays`** / **`method_overlays`** keys, `profile_confidence`). Drives relevance scoring, expected-type alignment bonus, selection quotas, and role classification; distinct from `TopicExpansion` and `PaperAnalysis`.
- `schemas/paper_analysis.py`, `schemas/hypothesis.py`, and `schemas/synthesis.py` include extended fields aligned to current agent outputs.

### Tools

- `config/astro_ontology.yaml`
  - **Domains**: reusable vocabulary packs, e.g. `cosmology`, **`galaxy_clusters`**, `galaxy_formation`, plus sparse `gravitational_waves` / `exoplanets`.
  - **Global** `relevance_weights`, per-domain optional overrides, `arxiv_categories`, and `paper_role_hints`.
  - **`profile_overlays`**: narrow refinements (S8/weak lensing, dark-energy equation of state, JWST high-z) with `match.any` / `match.boost_if` and `applies_to_domains`. Gated when pre-profile confidence is low (see `tools/topic_profiler.py`).
  - **`method_overlays`**: cross-cutting method layers (e.g. **machine learning**) that add `methods`, **`expected_paper_types`**, and optional canonical queries without inventing a fake “ML astrophysics” science domain.
- `tools/ontology_loader.py`
  - Loads `astro_ontology.yaml` into typed `DomainOntology`, `ProfileOverlay`, and **`MethodOverlay`** structures (`AstroOntology`).
- `tools/topic_profiler.py`
  - `build_topic_profile(topic, source=...)` builds a `TopicProfile` from the topic string and ontology (domains, gated **`profile_overlays`**, always-applicable **`method_overlays`** when matched, **`profile_confidence`** heuristic).
- `tools/query_generator.py`
  - `topic_profile_to_expansion(profile)` maps a profile to `TopicExpansion` (retrieval only), including **`profile_overlays`** and **`method_overlays`** canonical queries and domain-specific combinations (e.g. galaxy clusters + machine learning).
- `tools/paper_role_classifier.py`
  - `classify_paper_role` (uses merged `paper_role_hints`; when **`expected_paper_types`** implies methods/pipelines, extra ML-related phrases count toward **direct_evidence**).
  - **`selection_policy_from_profile(profile, max_papers)`** widens **`max_method_or_instrument`** and optionally **`max_theory_interpretation`** when the profile lists method/calibration/pipeline/catalog/inference expectations (from **`method_overlays`** or future ontology fields).
  - **`select_primary_ranked_with_quotas`**, **`SelectionPolicy`** (includes **`max_method_or_instrument`** separate from background caps), **`PaperSelectionResult`**.
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
  - `rank_papers(papers, topic, current_year, negative_terms=..., topic_profile=...)`
  - `profile_relevance_score(paper, topic_profile)` — profile vocabulary, conditional negatives, and a small bonus when paper text aligns with **`expected_paper_types`** (phrase families for *method*, *simulation calibration*, *observational pipeline*, *catalog construction*, *inference*).
  - `topic_relevance_score(..., topic_profile=...)` for profile-aware relevance (normalized to `[0,1]` for blending).
  - `select_primary_papers(...)` (ranking bucket `primary`; `select_canonical_papers` remains as a deprecated alias).
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
- What each agent does:
  - `topic_expander`: expands a user topic into retrieval-oriented queries, aliases, observables, surveys, parameters, and systematics.
  - `paper_analyzer`: converts each selected paper into structured `PaperAnalysis` fields (question, methods, datasets, constraints, systematics, limitations).
  - `synthesis_agent`: aggregates multiple paper analyses into a field-level synthesis (consensus, tensions, recurring weaknesses, open problems).
  - `research_strategist`: proposes concrete, testable research hypotheses grounded in extracted evidence.
  - `skeptical_referee`: critiques and re-labels hypotheses (`validated`/`plausible`/`rejected`) based on explicit evidence and falsifiability.
  - `report_compiler`: assembles the final narrative report from analyses, synthesis, and labeled hypotheses.
- Crew orchestration:
  - `crews/research_crew.py` exposes `build_research_crew(llm) -> Crew`
  - Uses `Process.sequential` with tasks:
    1. analyze selected papers
    2. synthesize field
    3. generate hypotheses
    4. critique hypotheses
    5. compile report
  - Data flow (high level):
    1. CLI retrieves/ranks papers (outside crew).
    2. Crew analyzes selected papers.
    3. Crew synthesizes cross-paper findings.
    4. Crew generates and critiques hypotheses.
    5. Crew compiles the final report text.
  - Visual flow:

```mermaid
flowchart TD
    UserTopic[User topic string]
    UserTopic --> Profiler[build_topic_profile]
    Ontology[config/astro_ontology.yaml domains profile_overlays method_overlays]
    Ontology --> Profiler
    Profiler --> Profile[TopicProfile vocabulary negatives matched_terms expected_paper_types profile_confidence]
    Profile --> QGen[topic_profile_to_expansion]
    Profile --> Rank[rank_papers with topic_profile]
    Profile --> Policy[selection_policy_from_profile]
    Profile --> Roles[classify_paper_role]
    QGen --> Legacy[legacy YAML expansion merge in CLI]
    Legacy --> Expansion[TopicExpansion retrieval queries only]
    Expansion --> Retrieval[Retrieve OpenAlex arXiv ADS]
    Retrieval --> Dedup[Deduplicate enrich]
    Dedup --> Rank
    Rank --> Roles
    Rank --> Select[select_primary_ranked_with_quotas]
    Policy --> Select
    Roles --> Select
    Select --> Payload[Selected paper payload PDFs optional]
    Payload --> Crew[Research crew sequential tasks]
    Crew --> Report[Report markdown]
    Crew --> Wiki[Wiki source and evidence pages]
```

Notes:

- **Retrieval and ranking run outside the crew**; the crew consumes the pre-selected payload.
- **`TopicExpansion`** must not be treated as per-paper evidence; **`PaperAnalysis`** is grounded in paper text (see bootstrap and sanitization in `app/cli.py`).
- When **`profile_confidence`** is low, **`profile_overlays`** are skipped and secondary domains are collapsed so weak domain matches do not flood vocabulary; **`method_overlays`** (e.g. machine learning) still apply when the topic mentions them.

### Crew-only flow (after papers are selected)

```mermaid
flowchart TD
    Payload[Selected paper payload from CLI] --> Analyze[Paper analyzer task]
    Analyze --> Synth[Synthesis task]
    Synth --> Hyp[Hypothesis generation task]
    Hyp --> Referee[Skeptical referee task]
    Referee --> Compile[Report compiler task]
    Compile --> ReportOut[Final report markdown]
    Compile --> WikiOut[Wiki updates]
```

## Reference YAML ontologies (`ontology/`)

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
BRAVE_SEARCH_API_KEY=...
```

Notes:
- `NASA_ADS_API_KEY` is required for ADS queries.
- Semantic Scholar can run without an API key, but keyless calls are rate-limited.
- `BRAVE_SEARCH_API_KEY` is optional and only needed for `--web-expand`.
- `.env` is gitignored and should never be committed.

## Tool Smoke Tests

Run each tool directly from the repo root:

```bash
uv run python tools/openalex_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/arxiv_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/ads_tool.py "S8 tension weak lensing Planck" --max-results 5
S2_DEBUG=1 uv run python tools/semantic_scholar_tool.py
```

Offline fixture mode (no live retrieval APIs):

```bash
python main.py research "S8 tension between weak lensing and Planck" --max-papers 10 --input-json evals/fixture_papers_s8.json
```

Fixture JSON format:

```json
{
  "papers": [
    {
      "title": "KiDS-450 cosmological constraints",
      "year": 2017,
      "doi": "10.1093/mnras/stw2805",
      "arxiv_id": "1606.05338",
      "abstract": "..."
    }
  ],
  "extracted_text_by_key": {
    "10.1093/mnras/stw2805": "optional extracted text override"
  }
}
```

Notes:
- You can also provide a bare JSON list of paper objects.
- `extracted_text_by_key` is optional and keyed by DOI/arXiv/ADS/OpenAlex/title key used by the CLI.
- In fixture mode, retrieval APIs are bypassed to validate payload, Crew context, and report/wiki flow offline.
- A ready-to-run fixture is included at `evals/fixture_papers_s8.json`.
- A second ready-to-run fixture is included at `evals/fixture_papers_jwst_highz.json`.
- A third ready-to-run fixture is included at `evals/fixture_papers_dark_energy.json`.
- By default, fixture mode now validates topic/fixture relevance and exits early on obvious mismatch. Override with `--no-strict-fixture-topic-match` only when intentionally reusing a fixture across topics.

### Fixture Workflow (Important)

`--input-json` is intentionally strict and should be treated as an "offline evidence lock":

- The topic string can change, but the paper evidence will only come from the fixture file.
- No OpenAlex/arXiv/ADS retrieval runs when fixture mode is active.
- Ranking and report generation are still executed, but only over fixture papers.

This means topic/fixture mismatch can produce scientifically incoherent reports unless guarded.

#### Topic/Fixture mismatch guard

When fixture mode is enabled, the CLI computes a lightweight keyword-overlap check between:
- your requested topic
- fixture paper titles/abstracts

If overlap is too low, the run exits with a clear error and suggestions.

Example mismatch:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 5 --input-json evals/fixture_papers_s8.json
```

Expected behavior: exits early with a fixture/topic mismatch message.

To intentionally bypass guardrails (advanced/debug use only):

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 5 --input-json evals/fixture_papers_s8.json --no-strict-fixture-topic-match
```

#### Recommended fixture commands

S8 fixture:

```bash
uv run python main.py research "S8 tension between weak lensing and Planck" --max-papers 5 --input-json evals/fixture_papers_s8.json
```

JWST high-z fixture:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 5 --input-json evals/fixture_papers_jwst_highz.json
```

Dark-energy fixture:

```bash
uv run python main.py research "Dark Energy evolution over time" --max-papers 5 --input-json evals/fixture_papers_dark_energy.json
```

#### Choosing live mode vs fixture mode

Use fixture mode when you need reproducible offline debugging for:
- payload shaping,
- schema parsing,
- report rendering,
- wiki update behavior.

Use live mode (omit `--input-json`) when you want topic-true retrieval and discovery:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 10
```

Mode branch (high level):

```mermaid
flowchart TD
    runCmd[Research command] --> modeChoice{Input JSON provided}
    modeChoice -->|Yes| fixtureMode[Fixture mode]
    modeChoice -->|No| liveMode[Live mode]
    fixtureMode --> fixtureLoad[Load fixture papers]
    fixtureLoad --> profileRank[TopicProfile rank select bootstrap]
    liveMode --> profile[TopicProfile plus TopicExpansion]
    profile --> retrieval[Retrieve OpenAlex arXiv ADS]
    retrieval --> profileRank
    profileRank --> crewWiki[Crew when available report wiki]
```

### Live Retrieval Controls

To reduce arXiv rate-limit failures in live mode, the CLI now supports three controls:

- arXiv query fanout is intentionally limited to the first canonical query (lower burst pressure).
- arXiv requests use retry + exponential backoff on HTTP 429 behavior.
- Source selection flags allow explicit control over retrieval providers.

Examples:

Skip arXiv entirely:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 10 --skip-arxiv
```

Use only OpenAlex + ADS (exclude arXiv):

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 10 --sources openalex,ads
```

Use only arXiv:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 10 --sources arxiv
```

Notes:
- `--sources` applies to live mode only (fixture mode bypasses external retrieval).
- Valid source values: `openalex`, `arxiv`, `ads`.
- `--skip-arxiv` takes precedence over including `arxiv` in `--sources`.
- Fixture papers can include enriched IDs (`doi`, `openalex_id`, `semantic_scholar_id`) and `citation_counts` for more realistic ranking/report behavior.

### Web-Assisted Topic Expansion

You can optionally add a web discovery layer before retrieval:

```bash
uv run python main.py research "Massive high z galaxies from the JWST" --max-papers 10 --web-expand
```

Behavior:
- ontology/rule expansion runs first,
- optional Brave-based web expansion discovers extra vocabulary (surveys, instruments, systematics, phrase-level query terms),
- merged expansion drives retrieval query generation,
- ranking remains deterministic and local (web results are discovery hints, not ranking authority).

If `BRAVE_SEARCH_API_KEY` is missing or web calls fail, the run continues with deterministic expansion.

Dark-energy runs now also include deterministic topic-expansion templates (`w0`, `wa`, CPL, BAO/SNe/CMB combos, Pantheon+/DESI/eBOSS terms) so expansion is not generic for `Dark Energy evolution over time`.

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

Run unit tests under `tests/` (recommended: avoids name collisions with similarly named scripts under `scripts/`):

```bash
uv run pytest tests/ -q
```

Run all paths pytest discovers from the repo root (may error if `scripts/` test modules shadow `tests/`):

```bash
uv run pytest -q
```

Run targeted suites:

```bash
uv run pytest tests/test_metadata_resolver.py -q
uv run pytest tests/test_ranking_tool.py -q
uv run pytest tests/test_topic_profiler.py -q
uv run pytest tests/test_paper_role_classifier.py -q
uv run pytest tests/test_cli_pipeline_helpers.py -q
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

## Topic profiling and data boundaries

The CLI separates three objects end-to-end:

| Layer | Schema / artifact | Role |
|-------|---------------------|------|
| Topic interpretation | `TopicProfile` (`schemas/topic_profile.py`) | Ontology-backed **`primary_domain`**, vocabulary, `arxiv_categories`, `paper_role_hints`, `relevance_weights`, negatives, conditional GW rules, **`matched_terms`** (keys such as domain names, **`profile_overlays`**, **`method_overlays`**), **`expected_paper_types`** (from method overlays or future domain fields), **`profile_confidence`**. |
| Retrieval planning | `TopicExpansion` (`schemas/topic_expansion.py`) | Search queries and hints for OpenAlex / ADS / arXiv only. |
| Per-paper evidence | `PaperAnalysis` | Only what the paper title, abstract, metadata, or extracted text supports; bootstrap does **not** merge expansion vocabulary into list fields, and short survey codes use **word-boundary** matching for `datasets`. |

Pipeline sketch: `config/astro_ontology.yaml` → `build_topic_profile` (domains + gated **`profile_overlays`** + **`method_overlays`**) → `topic_profile_to_expansion` (merged with legacy YAML expansion in `app/cli.py`) → retrieval → `rank_papers(..., topic_profile=...)` (vocabulary + **`expected_paper_types` alignment bonus**) → `selection_policy_from_profile` → `select_primary_ranked_with_quotas` (`classify_paper_role` with merged hints + ML direct cues when expected) → Crew.

### `expected_paper_types`, ranking, and selection quotas

- **Source**: Populated from YAML (e.g. `method_overlays.machine_learning.expected_paper_types`); plain strings such as `method`, `simulation calibration`, `catalog construction`, `inference`.
- **Ranking**: `profile_relevance_score` adds a capped raw bonus when the paper title/abstract (plus journal/venue/categories) contains short phrase families aligned with those types (see `_EXPECTED_TYPE_PHRASES` in `tools/ranking_tool.py`). This nudges method-heavy papers up without moving ranking logic into prompts.
- **Selection**: `selection_policy_from_profile(profile, max_papers)` returns a `SelectionPolicy` derived from `default_selection_policy` but may raise **`max_method_or_instrument`** (and **`max_theory_interpretation`** when *inference* is expected) so quota filling can admit more pipeline/calibration papers for ML/calibration-style topics. The early quota pass uses **`max_method_or_instrument`** for `method_or_instrument` roles (not the background cap).
- **Roles**: When `expected_paper_types` implies methods or inference, additional ML-related substrings are merged into **direct_evidence** hints so cluster+ML papers are less likely to be mis-bucketed as generic background.

Reports label the main ranked set **Selected Primary Papers** (fixture mode still uses **Selected Fixture Papers**). Optional **Selection Diagnostics** and **TopicProfile (debug)** sections are included by default; pass `--no-debug-report` to omit them. Diagnostics include **`max_method_or_instrument`** in the selection policy line.

## Deterministic Ranking Summary

`rank_papers` now combines:
- relevance score: profile-driven `profile_relevance_score` when a `TopicProfile` is supplied (per-field weights from `relevance_weights`, vocabulary hits, `negative_topics`, `conditional_negatives` / `conditional_allow_terms` for GW cosmology, plus **`expected_paper_types` phrase-family bonus**), else legacy topic-string heuristics,
- citation score: log-normalized selected citation count,
- source confidence score: deterministic metadata-confidence signal,
- recency score: deterministic age-decay,
- paper-type multiplier: review downweight; selected observational/data/method classes upweight.

Primary scoring blend:
- `0.50 * relevance + 0.25 * citation + 0.15 * source_confidence + 0.10 * recency`

Recent high-signal scoring blend:
- `0.50 * relevance + 0.25 * recency + 0.15 * velocity + 0.10 * citation`

For JWST/high-z-style topics, explicit negative terms (e.g. axion/biology-style drift) are penalized in relevance scoring.
For dark-energy topics, non-cosmology GW discovery papers (e.g. GW150914 binary-black-hole discovery without standard-siren/dark-energy context) receive strong negative relevance penalties; papers that mention allowed phrases (e.g. standard siren, luminosity distance) are not over-penalized.

Primary selection uses **`selection_policy_from_profile`** and **`select_primary_ranked_with_quotas`** (`tools/paper_role_classifier.py`): defaults favor **direct_evidence** papers, then **theory_interpretation**, then **method_or_instrument**, each capped by **`SelectionPolicy`** (`max_theory_interpretation`, **`max_method_or_instrument`**, `max_background` for the background list only).

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

- **`expected_paper_types` wiring**: `profile_relevance_score` alignment bonus; **`selection_policy_from_profile`** adjusts **`max_method_or_instrument`** / **`max_theory_interpretation`**; **`classify_paper_role`** merges ML direct hints when the profile expects method-style papers; CLI uses **`selection_policy_from_profile`** and reports **`max_method_or_instrument`** in selection diagnostics. Tests: `tests/test_ranking_tool.py`, **`tests/test_paper_role_classifier.py`**.
- **TopicProfile architecture** (ongoing): unified `config/astro_ontology.yaml` (**`galaxy_clusters`**, **`method_overlays`**, gated **`profile_overlays`**), `tools/topic_profiler.py`, `tools/query_generator.py`, profile-aware `rank_papers` / `profile_relevance_score`, and quota-based primary selection in `tools/paper_role_classifier.py`. CLI builds a `TopicProfile` and merged `TopicExpansion`; reports use **Selected Primary Papers** and optional diagnostics (`--debug-report` / `--no-debug-report`).
- Strengthened Crew task contracts in `crews/research_crew.py` to request strict JSON for:
  - paper analysis extraction (`paper_analyses`)
  - hypothesis generation (`hypotheses`)
  - skeptical review output (status-corrected hypotheses)
- Added explicit hypothesis status rubric: `validated`, `plausible`, `rejected`.
- Added deterministic topic expansion for S8/weak-lensing topics (Planck, DES, KiDS, HSC, ACT, SPT; key observables/parameters/systematics).
- Improved bootstrap structured extraction in CLI:
  - dataset detection from title/text (e.g. DES Y3, KiDS-450),
  - methods/systematics extraction only when explicit in supplied text,
  - unknown list fields now default to `[]` (not `["not extracted"]`).
- Added deterministic structured hypotheses in CLI with evidence-grounding checks:
  - only marks `validated` when mechanism appears in extracted analyses,
  - otherwise marks `plausible` with grounding notes.
- Report rendering improvements:
  - fixture-aware heading (`Selected Fixture Papers`),
  - de-duplicated recent list against canonical/primary selected papers,
  - hypothesis display rank normalization (`Hypothesis 1`, `Hypothesis 2`, ...),
  - explicit fixture-mode caveat on citation/ranking confidence.
- Upgraded `evals/fixture_papers_s8.json` with richer abstracts, systematics, methods, IDs, and citation counts for better evidence-grounded offline runs.
- Added `evals/fixture_papers_jwst_highz.json` as a topic-aligned offline fixture for JWST high-z massive-galaxy workflows.
- Added strict fixture/topic mismatch guard in CLI (enabled by default), with explicit override flag `--no-strict-fixture-topic-match`.
- Added live retrieval controls for arXiv rate-limit resilience:
  - arXiv limited to one canonical query in live mode,
  - exponential backoff retries for arXiv rate limits,
  - source flags `--skip-arxiv` and `--sources`.
- Added deterministic JWST/high-z expansion branch with richer queries, observables, surveys/programs, parameters, and systematics.
- Added optional web-assisted topic expansion (`--web-expand`) via Brave Search for vocabulary discovery.
- Added weighted topic relevance filtering before ranking (including negative term penalties) to suppress off-topic canonical selections.
- Rebalanced ranking to make relevance the dominant signal for canonical and recent-high-signal lists.
- Added deterministic dark-energy topic expansion branch and GW-specific negative relevance filtering.
- Added primary/background/off-topic paper-role separation and report section for background/infrastructure papers.
- Added analysis sanitization to prevent topic-expansion leakage into per-paper datasets/instruments/missions unless explicitly evidenced in paper text.
- Extended deterministic hypothesis fallback for JWST/high-z topics so structured `hypotheses` no longer stay empty by default.
- Extended deterministic hypothesis fallback for dark-energy topics and added crew-output hypothesis JSON extraction path before fallback.
- Added targeted tests for ranking relevance, analysis sanitization, role classification, and JWST structured hypothesis fallback.
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
