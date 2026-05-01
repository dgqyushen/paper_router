# paper_router

[![Tests](https://img.shields.io/badge/tests-80%20passed-brightgreen)]()
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

Async aggregation layer for academic paper search across multiple providers. Normalizes results into a unified format with deduplication, filtering, and rate limiting.

Designed for **agent consumption** — CLI outputs structured JSON, all errors are parseable, provider failures are isolated.

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
paper-router --queries "silicon anode" --limit 10

# With date filter
paper-router --queries "battery cathode" --start_date 2024-01-01 --end_date 2024-12-31

# Specific providers only
paper-router --queries "perovskite solar" --providers openalex crossref

# Compact single-line JSON output
paper-router --queries "graph neural network" --compact
```

## CLI Reference

```
paper-router --queries QUERIES [--providers PROVIDERS ...]
             [--start_date YYYY-MM-DD] [--end_date YYYY-MM-DD]
             [--limit N] [--compact]
```

| Parameter | Required | Description |
|---|---|---|
| `--queries` | Yes | Search terms (one or more) |
| `--providers` | No | Providers to use (default: all). Choices: `openalex`, `semantic_scholar`, `crossref`, `arxiv` |
| `--start_date` | No | Earliest publication date |
| `--end_date` | No | Latest publication date |
| `--limit` | No | Max results per query |
| `--compact` | No | Single-line JSON output |

### Output Format

**Success** (`exit 0`):
```json
{
  "success": true,
  "queries": ["silicon anode"],
  "providers": ["arxiv", "crossref", "openalex", "semantic_scholar"],
  "count": 91,
  "results": [
    {
      "source": "crossref",
      "external_id": "10.1007/s40820-026-02157-0",
      "title": "Revisiting the Modification Strategies...",
      "authors": ["Yueying Chen", "Hanyi Yu", "..."],
      "publication_date": "2026-12-01",
      "doi": "10.1007/s40820-026-02157-0",
      "venue": "Nano-Micro Letters",
      "abstract": "In recent years, advanced battery systems...",
      "url": "https://doi.org/10.1007/s40820-026-02157-0",
      "quartile": null
    }
  ],
  "warnings": []
}
```

**Error** (`exit 1`):
```json
{
  "success": false,
  "error": "Unknown provider(s): fake_provider",
  "available_providers": ["arxiv", "crossref", "openalex", "semantic_scholar"]
}
```

### Partial Failure

When some providers fail, results from successful ones are still returned:

```json
{
  "success": true,
  "count": 42,
  "results": ["..."],
  "warnings": ["Provider 'arxiv' failed for query 'test': timeout"]
}
```

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
