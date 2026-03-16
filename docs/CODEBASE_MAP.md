# SIEVE — Codebase Map

## Overview

SIEVE is a content filtering pipeline that separates signal from noise in technical content. It classifies content on a four-level signal scale, extracts structured knowledge nodes, and flags marketing/engagement patterns.

**Version:** 0.1.0
**Python:** 3.10+
**Status:** Full pipeline operational — URL fetching, dedup, CLI, ATHENA export, text-in and URL-in paths working.

## Project Structure

```
sieve/
├── CLAUDE.md                  # Project instructions and design decisions
├── pyproject.toml             # Package config, deps, CLI entry point
├── .gitignore
│
├── sieve/                     # Main package
│   ├── __init__.py            # Exports all models + public API, __version__
│   ├── models.py              # Data models (dataclasses + enums)
│   ├── filter_prompt.py       # LLM signal filter (SYSTEM_PROMPT, parser, API wrapper)
│   ├── extractor.py           # trafilatura HTML → clean text + direct text input
│   ├── pipeline.py            # Orchestrator (SievePipeline, sieve_text, get_filter_prompt_for_text)
│   ├── fetcher.py             # URL fetching (httpx baseline, scrapling optional)
│   ├── dedup.py               # MinHash fingerprinting / near-duplicate detection
│   ├── cli.py                 # argparse CLI (text, file, url, batch, extract, prompt)
│   ├── athena_adapter.py      # FilteredContent → ATHENA graph nodes/edges/export
│   ├── mcp_server.py          # [planned] MCP server wrapper
│   └── spider.py              # [future] Scrapling-based crawler
│
├── tests/
│   ├── test_models.py         # 12 tests — enums, word count, serialization
│   ├── test_filter_prompt.py  # 16 tests — prompt content, parsing, edge cases
│   ├── test_pipeline.py       # 15 tests — extractor, pipeline, digest, save (+1 live skipped)
│   ├── test_fetcher.py        # 8 tests — source type detection, fetch failure handling
│   └── test_dedup.py          # 8 tests — fingerprint, jaccard, dedup store persistence
│
├── integration_test.py        # Full pipeline test with 4 realistic articles (no API key needed)
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

### sieve/extractor.py
Content extraction — two paths:

| Function              | Description                                      |
|-----------------------|--------------------------------------------------|
| `extract_content()`   | Full extraction from `RawContent` via trafilatura (comments off, tables on, min 50 chars) |
| `extract_from_html()` | Convenience: HTML string → `ExtractedContent` (wraps `extract_content`) |
| `extract_from_text()` | Direct text → `ExtractedContent` for pasted content. Defaults to `LINKEDIN_POST` |

### sieve/filter_prompt.py
The core BS detector. Four components:

| Component                | Description                                      |
|--------------------------|--------------------------------------------------|
| `SYSTEM_PROMPT`          | 1762-char evaluation framework with signal/noise indicators and context-matters rules |
| `build_filter_prompt()`  | Builds user message with source metadata + content (truncated to 8000 chars) + JSON output schema |
| `parse_filter_response()`| 3-step JSON parsing: direct → strip markdown fences → regex `{…}` fallback → `ValueError` |
| `filter_with_claude()`   | Anthropic SDK wrapper. Default: Haiku for volume. Optional: Sonnet for precision |

### sieve/pipeline.py
Main orchestrator and public convenience functions.

| Component                    | Description                                      |
|------------------------------|--------------------------------------------------|
| `SievePipeline`              | Main class: `process_text()`, `process_url()`, `process_batch()`, `_filter()`, `generate_digest()`, `save_results()` |
| `SievePipeline.process_text()`| Text-in path: text → ExtractedContent → LLM filter → FilteredContent |
| `SievePipeline.process_url()`| URL path: fetch → extract → filter |
| `SievePipeline.process_batch()`| Multi-URL with progress counter |
| `SievePipeline._filter()`   | Dedup check → LLM → signal indicator + BS count → dedup register → ATHENA ingest |
| `SievePipeline.generate_digest()` | Markdown digest grouped by signal class (high first), with insights/BS/questions/nodes |
| `SievePipeline.save_results()` | Saves JSON + markdown digest + ATHENA graph JSON to output_dir |
| `sieve_text()`               | One-liner: filter pasted text                    |
| `get_filter_prompt_for_text()`| Returns (system_prompt, user_prompt) for manual use in claude.ai |

### sieve/fetcher.py
URL fetching with httpx baseline and optional scrapling upgrade.

| Function              | Description                                      |
|-----------------------|--------------------------------------------------|
| `fetch_url()`         | Fetch URL → `RawContent`. Auto-selects method by domain (stealthy for LinkedIn). Falls back to httpx if scrapling unavailable |
| `fetch_batch()`       | Fetch multiple URLs, skip failures               |
| `_detect_source_type()`| Infer `ContentType` from URL patterns (linkedin.com, medium.com, github.com, arxiv.org) |

### sieve/dedup.py
Content fingerprinting for near-duplicate detection across runs.

| Component              | Description                                      |
|------------------------|--------------------------------------------------|
| `content_fingerprint()`| 16-char hex fingerprint from MinHash of 5-word shingles |
| `jaccard_similarity()` | Shingle-based Jaccard similarity (0.0–1.0)       |
| `DeduplicationStore`   | Persistent JSON store. Exact fingerprint match first, then Jaccard against last 500 entries |

### sieve/athena_adapter.py
Converts FilteredContent into ATHENA knowledge graph format.

| Component                    | Description                                      |
|------------------------------|--------------------------------------------------|
| `AthenaNode`                 | Dataclass: deterministic hash ID, concept, node_type, provenance, quality weight, claims, connections |
| `AthenaEdge`                 | Dataclass: source_id, target_id, relation, weight, evidence |
| `_make_node_id()`            | Deterministic 12-char hex hash from concept + source_url |
| `_signal_to_quality()`       | Blends signal class base (0.8/0.5/0.2/0.05) with score: base*0.6 + score*0.4 |
| `filtered_to_athena_nodes()` | Each knowledge_node dict → AthenaNode + source node. Quality propagated from signal |
| `filtered_to_athena_edges()` | Connects nodes to named connections + all knowledge nodes to source node |
| `AthenaExporter`             | Accumulator: ingest/ingest_batch, dedup by ID (merge connections, keep higher quality), export_json, export_cypher, stats |

### sieve/cli.py
Argparse CLI with 6 subcommands.

| Subcommand | Description                                      |
|------------|--------------------------------------------------|
| `text`     | Filter inline text (`sieve text "..." --author X --source linkedin`) |
| `file`     | Filter text from file (`sieve file post.txt`)    |
| `url`      | Fetch + filter URL (`sieve url URL --method auto`) |
| `batch`    | Batch process URLs from file (`sieve batch urls.txt`) |
| `extract`  | Extract only, no LLM (`sieve extract URL`)       |
| `prompt`   | Generate prompt for manual claude.ai use (`sieve prompt "..."`) |

## Data Flow

```
URL or raw text
    │
    ▼
fetcher.py          Fetch HTML (httpx baseline, scrapling for stealth)
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
athena_adapter.py   FilteredContent → AthenaNode/AthenaEdge → JSON/Cypher export
    │
    ▼
pipeline.py         Orchestrates above, saves JSON + markdown digest
    │
    ▼
cli.py              CLI entry point: `sieve <subcommand>`
```

## Dependencies

| Dependency     | Group    | Purpose                          |
|----------------|----------|----------------------------------|
| trafilatura    | core     | HTML content extraction          |
| httpx          | core     | HTTP fetching (baseline client)  |
| anthropic      | api      | LLM signal filtering             |
| scrapling      | fetch    | Stealth fetching (anti-bot)      |
| mcp            | mcp      | MCP server protocol              |

Install: `pip install -e .` (core) or `pip install -e ".[all]"` (everything).

## Test Suite

```
tests/test_models.py          12 tests    Models, enums, serialization
tests/test_filter_prompt.py   16 tests    Prompt, parser, edge cases
tests/test_pipeline.py        15 tests    Extractor, pipeline, digest, save (+1 live skipped)
tests/test_fetcher.py          8 tests    Source type detection, fetch failure handling
tests/test_dedup.py            8 tests    Fingerprint, jaccard, dedup store persistence
                              ── ──────
                              62 total (61 pass, 1 skipped without API key)
```

Run: `python -m pytest tests/ -v`

## Build Sequence (prompts)

The project is built incrementally via numbered prompts:

1. **Scaffolding & Models** — project structure, dataclasses, pyproject.toml ✅
2. **Filter Prompt** — SYSTEM_PROMPT, builder, parser, API wrapper ✅
3. **Extractor & MVP Pipeline** — trafilatura wrapper, basic pipeline ✅
4. **URL Fetching & CLI** — httpx/scrapling fetcher, dedup, argparse CLI ✅
5. **ATHENA Adapter & Integration** — graph nodes, full pipeline test ✅

## Conventions

- Type hints on all function signatures
- `[SIEVE]` prefix on print-based logging (no logging framework)
- `ensure_ascii=False` in all JSON output (multilingual content)
- `encoding="utf-8"` on all file I/O
- Optional deps guarded with `try/import/except`
- CLI via argparse (not click)
