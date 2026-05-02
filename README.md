# paper_router

English | [中文](./README_CN.md)

[![Tests](https://img.shields.io/badge/tests-80%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

Async aggregation layer for academic paper search across multiple providers. Normalizes results into a unified format with deduplication, filtering, and rate limiting.

Designed for **agent consumption** — CLI outputs a line-delimited JSON stream (NDJSON), all errors are parseable, provider failures are isolated.

## Features

- **4 providers**: OpenAlex, Semantic Scholar, CrossRef, arXiv
- **Provider-level fault tolerance**: single provider failure doesn't block results
- **Deduplication**: by DOI first, then title+date fallback
- **Filtering**: date range, journal quartile (Q1–Q4)
- **Rate limiting**: per-provider async rate limits
- **Two interfaces**: CLI for scripts/agents, MCP for AI hosts

## Quick Start

```bash
# Install
poetry install

# Search (all 4 providers by default)
paper-router search --queries "silicon anode" --limit 10

# With date filter
paper-router search --queries "battery cathode" --start_date 2024-01-01 --end_date 2024-12-31

# Specific providers only
paper-router search --queries "perovskite solar" --providers openalex crossref
```

## CLI Reference

```
paper-router search --queries QUERIES [--providers PROVIDERS ...]
                   [--start_date YYYY-MM-DD] [--end_date YYYY-MM-DD]
                   [--limit N] [--quartiles Q1 Q2 ...]
```

| Parameter | Required | Description |
|---|---|---|
| `--queries` | Yes | Search terms (one or more) |
| `--providers` | No | Providers to use (default: all). Choices: `openalex`, `semantic_scholar`, `crossref`, `arxiv` |
| `--start_date` | No | Earliest publication date |
| `--end_date` | No | Latest publication date |
| `--limit` | No | Max results per query |
| `--quartiles` | No | Filter by JCR quartile (e.g. `Q1 Q2`) |

### Output Format (NDJSON Stream)

stdout is a newline-delimited JSON stream. Each line is a self-contained event.
Read line by line to process results incrementally.

**Progress** — emitted before each provider call:
```json
{"finish":false,"type":"progress","current":1,"total":4,"message":"searching openalex for 'silicon anode'..."}
```

**Papers** — emitted when a provider returns results:
```json
{"finish":false,"type":"papers","provider":"openalex","query":"silicon anode","count":50,"papers":[
  {"source":"openalex","external_id":"W123","title":"...","authors":["..."],"publication_date":"2024-06-01","doi":"10.xxx","venue":"Nature","abstract":"...","url":"https://...","quartile":"Q1"}
]}
```

**Error** — emitted when a provider call fails (search continues):
```json
{"finish":false,"type":"error","provider":"arxiv","query":"silicon anode","message":"Connection timeout"}
```

**Result** — always the last line. Deduplicated, sorted final output:
```json
{"finish":true,"type":"result","success":true,"queries":["silicon anode"],"providers":["openalex","arxiv"],"count":27,"results":[...],"warnings":["JCR quartile data is outdated..."]}
```

On fatal error:
```json
{"finish":true,"type":"result","success":false,"error":"Unknown provider(s): fake_provider","available_providers":["arxiv","crossref","openalex","semantic_scholar"]}
```

> **Consuming the stream**: Parse each line as independent JSON. The `finish` field signals completion. The `papers` events contain raw per-provider results (may overlap); the final `result` event has the deduplicated set.

### Partial Failure

When some providers fail, results from successful ones are still returned.
The `result` event contains warnings for each failure.

## Python API

```python
import asyncio
from datetime import date

from paper_router import PaperRouter, SearchRequest
from paper_router.providers import OpenAlexProvider, SemanticScholarProvider


async def main():
    router = PaperRouter([OpenAlexProvider(), SemanticScholarProvider()])
    papers = await router.search(SearchRequest(
        query="silicon anode",
        start_date=date(2024, 1, 1),
        limit=20,
    ))
    for paper in papers:
        print(f"{paper.publication_date} | {paper.title} ({paper.source})")
    await router.aclose()


asyncio.run(main())
```

## Providers

| Provider | CLI name | Rate Limit | API Key | Notes |
|---|---|---|---|---|
| OpenAlex | `openalex` | 10 req/s | Optional | Free, all disciplines |
| Semantic Scholar | `semantic_scholar` | 1 req/s | Optional | AI/CS focused |
| CrossRef | `crossref` | 50 req/s | Optional | DOI registry, all disciplines |
| arXiv | `arxiv` | 3 req/s | No | Preprints (physics, math, CS) |

API keys are optional for most providers. Set them in a `.env` file (see `.env.example`) for higher rate limits.

## MCP Server

For AI hosts that support the Model Context Protocol:

```bash
# Start MCP server (stdio transport)
paper-router-mcp
```

Available tools:
- `search_papers(query, providers?, start_date?, end_date?, limit?)` — Search papers
- `list_providers()` — List available providers

## Testing

```bash
poetry install
.venv/Scripts/pytest -q
# 80 passed
```

## Project Structure

```
src/paper_router/
├── cli.py              # CLI entry point (agent-facing)
├── mcp_server.py       # MCP server entry point
├── registry.py         # Shared provider registry
├── router.py           # PaperRouter: search, dedupe, filter
├── models.py           # SearchRequest, Paper, Quartile
├── config.py           # .env / environment config loading
├── filters.py          # Date range and quartile filtering
├── rate_limit.py       # Async rate limiter
└── providers/
    ├── base.py         # PaperProvider abstract base
    ├── openalex.py     # OpenAlex implementation
    ├── semantic_scholar.py
    ├── crossref.py     # CrossRef implementation
    └── arxiv.py        # arXiv implementation (XML)
```

## Adding a Provider

1. Create `src/paper_router/providers/your_provider.py`
2. Subclass `PaperProvider`, implement `default_rate_limit()`, `build_params()`, `parse_response()`
3. For non-JSON APIs, override `_parse_response_text()` instead
4. Register in `providers/__init__.py` and `registry.py`

## License

MIT
