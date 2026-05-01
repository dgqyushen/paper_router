# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This project uses Poetry for dependency management and pytest for testing.

```bash
# Install dependencies
poetry install

# Run all tests
.venv/Scripts/pytest

# Run a single test file
.venv/Scripts/pytest tests/test_router.py -v

# Run a specific test
.venv/Scripts/pytest tests/test_router.py::test_router_filters_by_date_and_quartile -v
```

## Two Interfaces

| Interface | Entry point | Use case |
|---|---|---|
| **CLI** | `paper-router` or `python -m paper_router` | Command-line agents, scripts, one-shot queries |
| **MCP** | `paper-router-mcp` | MCP hosts (Claude Code, etc.) |

## MCP Server

Provides MCP tools for agent-native access. Registered in `.claude/settings.local.json`.

**Available MCP tools:**
- `search_papers` — Search academic papers across multiple databases (arXiv, CrossRef, OpenAlex, Semantic Scholar). Returns deduplicated, date-sorted results.
- `list_providers` — List available search providers.

**Usage from Claude Code:** Just ask "search for papers about [topic]" and the tools will be invoked automatically.

## CLI

The CLI (`paper-router`) outputs structured JSON to stdout and uses non-zero exit codes for errors. Designed for agent consumption.

```bash
# Simple search
paper-router --queries "silicon anode" --limit 10

# Specific providers
paper-router --queries "battery" --providers openalex arxiv

# Date range
paper-router --queries "Li-ion" --start_date 2024-01-01 --end_date 2024-12-31

# Compact output
paper-router --queries "cathode" --compact
```

## Architecture Overview

**paper_router** is an async aggregation layer that normalizes academic paper search results from multiple providers (OpenAlex, Semantic Scholar, arXiv, CrossRef) into a unified format with filtering and deduplication.

### Core Flow

1. **PaperRouter.search()** (router.py:16) — Entry point that orchestrates the search:
   - Selects providers based on `request.providers` (empty = all)
   - Runs searches concurrently via `asyncio.gather`
   - Deduplicates by DOI first, then title+date fallback (using `Paper.dedupe_key`)
   - Applies filters (date range, quartile) via `filter_papers()`
   - Returns sorted by publication date (newest first)

2. **Provider Registry** (registry.py) — Central registry shared by CLI and MCP:
   - `PROVIDER_INFO`, `PROVIDER_MAP`, `PROVIDER_DESCRIPTIONS` — single source of truth
   - `create_router(provider_names)` — creates a `PaperRouter` with the requested providers

3. **PaperProvider** (providers/base.py:11) — Abstract base for all providers:
   - Handles HTTP client lifecycle (creates default if none provided)
   - Applies per-provider rate limiting via `AsyncRateLimiter`
   - Subclasses implement `build_params()`, `parse_response()`, and `default_rate_limit()`

4. **Models** (models.py):
   - `SearchRequest` — Immutable dataclass with validation in `__post_init__`
   - `Paper` — Immutable dataclass; `dedupe_key` property handles DOI/title+date fallback
   - `Quartile` — StrEnum for Q1-Q4 journal rankings

5. **Rate Limiting** (rate_limit.py):
   - `AsyncRateLimiter` uses `asyncio.Lock` + timestamp tracking
   - Default rates: Semantic Scholar = 1 req/s, OpenAlex = 10 req/s, CrossRef = 50 req/s, arXiv = 3 req/s

### Providers Reference

| Provider | Name | Rate Limit | API Key | Response Format |
|---|---|---|---|---|
| OpenAlex | `openalex` | 10 req/s | No | JSON |
| Semantic Scholar | `semantic_scholar` | 1 req/s | Optional | JSON |
| CrossRef | `crossref` | 50 req/s | No | JSON |
| arXiv | `arxiv` | 3 req/s | No | XML Atom |

### Key Design Decisions

- **Immutability**: All models use `@dataclass(slots=True, frozen=True)` for hashability and safety
- **Deduplication priority**: First provider's result wins for duplicate papers
- **Provider selection**: Request can specify subset; missing providers raise `ValueError`
- **Client ownership**: Provider only closes HTTP client if it created it (`_owns_client` flag)
- **Shared registry**: CLI and MCP both use `registry.py` for provider definitions

### Common Agent Workflows

**Search papers (CLI):**
```bash
paper-router --queries "silicon anode" --providers openalex arxiv --limit 10
```

**Search papers (Python API):**
```python
from paper_router import PaperRouter, SearchRequest
from paper_router.providers.openalex import OpenAlexProvider

router = PaperRouter([OpenAlexProvider()])
results = await router.search(SearchRequest(query="silicon anode"))
await router.aclose()
```

**Add a new provider:**
1. Create `providers/your_source.py`
2. Subclass `PaperProvider`, implement `default_rate_limit()`, `build_params()`, `parse_response()`
3. If the API returns non-JSON, override `_parse_response_text()` instead of `parse_response()`
4. Export in `providers/__init__.py`
5. Register in `registry.py`'s `PROVIDER_INFO`
6. Add to `mcp_server.py`'s `PROVIDER_INFO` (imports from registry)
