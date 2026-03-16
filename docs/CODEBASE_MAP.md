# SIEVE — Codebase Map

## Overview

SIEVE is a content filtering pipeline that separates signal from noise in technical content. It classifies content on a four-level signal scale, extracts structured knowledge nodes, and flags marketing/engagement patterns.

**Version:** 0.1.0
**Python:** 3.10+
**Status:** Early build — models and core filter prompt implemented, pipeline not yet wired.

## Project Structure

```
sieve/
├── CLAUDE.md                  # Project instructions and design decisions
├── pyproject.toml             # Package config, deps, CLI entry point
├── .gitignore
│
├── sieve/                     # Main package
│   ├── __init__.py            # Exports all models, __version__
│   ├── models.py              # Data models (dataclasses + enums)
│   ├── filter_prompt.py       # LLM signal filter (SYSTEM_PROMPT, parser, API wrapper)
│   ├── extractor.py           # [planned] trafilatura HTML → clean text
│   ├── fetcher.py             # [planned] URL fetching (httpx, scrapling)
│   ├── pipeline.py            # [planned] Orchestrator (SievePipeline)
│   ├── athena_adapter.py      # [planned] FilteredContent → ATHENA graph nodes
│   ├── dedup.py               # [planned] MinHash fingerprinting / near-duplicate detection
│   ├── cli.py                 # [planned] argparse CLI
│   ├── mcp_server.py          # [planned] MCP server wrapper
│   └── spider.py              # [future] Scrapling-based crawler
│
├── tests/
│   ├── test_models.py         # 12 tests — enums, word count, serialization
│   └── test_filter_prompt.py  # 16 tests — prompt content, parsing, edge cases
│
├── docs/
│   └── CODEBASE_MAP.md        # This file
│
├── config/
│   └── sources.yaml           # [planned] Source monitoring config
│
├── sieve_output/              # Default output directory (gitignored)
│
├── prompts/                   # Build prompts (not shipped, not committed)
│   ├── 01_scaffolding_and_models.md
│   ├── 02_filter_prompt.md
│   ├── 03_extractor_and_mvp_pipeline.md
│   ├── 04_url_fetching_and_cli.md
│   └── 05_athena_adapter_and_integration.md
│
└── reference/                 # Reference implementation (design spec, not production code)
    ├── *.py                   # Validated prototype from brainstorm session
    ├── v0.1/                  # Earlier prototype archive
    ├── v0.2/                  # Second iteration archive
    └── v0.3/                  # Current prompt/spec archive
```

## Implemented Modules

### sieve/models.py
All data models as dataclasses (no Pydantic).

| Class              | Purpose                                          |
|--------------------|--------------------------------------------------|
| `SignalClass`      | Enum: `high_signal`, `moderate_signal`, `low_signal`, `noise` |
| `ContentType`      | Enum: `linkedin_post`, `blog_post`, `medium_article`, `github_readme`, `arxiv_paper`, `rss_item`, `generic_web` |
| `RawContent`       | Raw fetched HTML before extraction               |
| `ExtractedContent` | Clean text after trafilatura extraction. Auto-computes `word_count` in `__post_init__` |
| `Claim`            | Single claim with `evidence_type`, `confidence`, `verifiable` |
| `FilteredContent`  | Full filter output: signal class/score, claims, insights, BS patterns, knowledge nodes. Has `to_dict()` and `to_json()` |
| `SourceConfig`     | Configuration for a monitored content source     |

### sieve/filter_prompt.py
The core BS detector. Four components:

| Component                | Description                                      |
|--------------------------|--------------------------------------------------|
| `SYSTEM_PROMPT`          | 1762-char evaluation framework with signal/noise indicators and context-matters rules |
| `build_filter_prompt()`  | Builds user message with source metadata + content (truncated to 8000 chars) + JSON output schema |
| `parse_filter_response()`| 3-step JSON parsing: direct → strip markdown fences → regex `{…}` fallback → `ValueError` |
| `filter_with_claude()`   | Anthropic SDK wrapper. Default: Haiku for volume. Optional: Sonnet for precision |

## Data Flow (target architecture)

```
URL or raw text
    │
    ▼
fetcher.py          Fetch HTML (httpx or scrapling)
    │
    ▼
extractor.py        HTML → ExtractedContent (trafilatura)
    │
    ▼
dedup.py            Check MinHash fingerprint → skip if near-duplicate
    │
    ▼
filter_prompt.py    ExtractedContent → LLM → FilteredContent
    │
    ▼
athena_adapter.py   FilteredContent → AthenaNode/AthenaEdge
    │
    ▼
pipeline.py         Orchestrates above, saves JSON + markdown digest
    │
    ▼
cli.py              CLI entry point: `sieve <url-or-text>`
```

## Dependencies

| Dependency     | Group    | Purpose                          |
|----------------|----------|----------------------------------|
| trafilatura    | core     | HTML content extraction          |
| anthropic      | api      | LLM signal filtering             |
| httpx          | simple   | Basic URL fetching               |
| scrapling      | fetch    | Stealth fetching (anti-bot)      |
| mcp            | mcp      | MCP server protocol              |

Install: `pip install -e .` (core) or `pip install -e ".[all]"` (everything).

## Test Suite

```
tests/test_models.py          12 tests    Models, enums, serialization
tests/test_filter_prompt.py   16 tests    Prompt, parser, edge cases
                              ── ──────
                              28 total
```

Run: `python -m pytest tests/ -v`

## Build Sequence (prompts)

The project is built incrementally via numbered prompts:

1. **Scaffolding & Models** — project structure, dataclasses, pyproject.toml ✅
2. **Filter Prompt** — SYSTEM_PROMPT, builder, parser, API wrapper ✅
3. **Extractor & MVP Pipeline** — trafilatura wrapper, basic pipeline
4. **URL Fetching & CLI** — httpx/scrapling fetcher, argparse CLI
5. **ATHENA Adapter & Integration** — graph nodes, dedup, full pipeline test

## Conventions

- Type hints on all function signatures
- `[SIEVE]` prefix on print-based logging (no logging framework)
- `ensure_ascii=False` in all JSON output (multilingual content)
- `encoding="utf-8"` on all file I/O
- Optional deps guarded with `try/import/except`
- CLI via argparse (not click)
