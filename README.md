# Astro Research Assistant (CrewAI)

Python project for an astrophysics/cosmology/astronomy research assistant built with CrewAI.

## Project Goal

Build a multi-agent research workflow that can:
- discover and retrieve relevant papers,
- normalize metadata from trusted sources,
- analyze and synthesize findings into structured outputs,
- maintain an evolving research wiki and reports.

Current status:
- project scaffold is in place,
- Pydantic schemas are implemented,
- literature retrieval/enrichment tools are implemented for OpenAlex, arXiv, NASA ADS, and Semantic Scholar,
- agent/crew orchestration is not implemented yet.

## Quick Start

```bash
uv sync
uv run python main.py
```

## Tool Smoke Tests

Run each tool directly from the repo root:

```bash
uv run python tools/openalex_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/arxiv_tool.py "S8 tension weak lensing Planck" --max-results 5
uv run python tools/ads_tool.py "S8 tension weak lensing Planck" --max-results 5
S2_DEBUG=1 uv run python tools/semantic_scholar_tool.py
```

## Environment Variables

Create a local `.env` file with keys you plan to use:

```bash
OPENALEX_MAILTO=your_email@example.com
NASA_ADS_API_KEY=...
SEMANTIC_SCHOLAR_API_KEY=...
OPENAI_API_KEY=...
```

Notes:
- `NASA_ADS_API_KEY` is required for ADS queries.
- Semantic Scholar can run without an API key, but keyless access may be rate-limited.
