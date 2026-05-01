# paper_router

`paper_router` is a small aggregation layer for academic paper providers. It normalizes provider responses into one paper array and applies filtering before returning data to the caller.

## Current capabilities

- Aggregate results from multiple providers.
- Configure provider-level rate limits.
- Accept `start_date` and `end_date` from the frontend to avoid fetching an unbounded range.
- Accept quartile filters and return already-filtered paper data.
- Deduplicate papers by DOI first, then by title/date fallback.

## Two interfaces

| Interface | Entry point | Use case |
|---|---|---|
| **CLI** | `paper-router` or `python -m paper_router` | Command-line agents, scripts, one-shot queries |
| **MCP** | `paper-router-mcp` | MCP hosts (Claude Code, etc.) |

## CLI quick start

```bash
# Simple search
paper-router --queries "silicon anode" --limit 10

# Multiple queries, specific providers
paper-router --queries "battery" "cathode" --providers openalex arxiv

# Date range filter
paper-router --queries "Li-ion" --start_date 2024-01-01 --end_date 2024-12-31 --compact

# All four providers (default when --providers omitted)
paper-router --queries "perovskite solar cell"
```

All output is structured JSON to stdout. Errors are also JSON with non-zero exit codes.

**JSON output fields:**
- `success`: boolean
- `queries`: list of search terms
- `providers`: list of providers used
- `count`: number of results
- `results`: list of paper objects (source, external_id, title, authors, publication_date, doi, venue, abstract, url, quartile)
- `warnings`: list of per-query failure messages (partial failures still return results)

## Python API

```python
import asyncio
from datetime import date

from paper_router import PaperRouter, Quartile, SearchRequest
from paper_router.providers import OpenAlexProvider, SemanticScholarProvider


async def main() -> None:
    router = PaperRouter(
        providers=[
            OpenAlexProvider(),
            SemanticScholarProvider(api_key="your-api-key-here"),
        ]
    )

    request = SearchRequest(
        query="graph neural network",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        quartiles=frozenset({Quartile.Q1, Quartile.Q2}),
        providers=("openalex", "semantic_scholar"),
        limit=20,
    )

    papers = await router.search(request)
    for paper in papers:
        print(paper.title, paper.publication_date, paper.quartile)

    await router.aclose()


asyncio.run(main())
```

## Available providers

| Provider | Name | Rate Limit |
|---|---|---|
| OpenAlex | `openalex` | 10 req/s |
| Semantic Scholar | `semantic_scholar` | 1 req/s |
| CrossRef | `crossref` | 50 req/s |
| arXiv | `arxiv` | 3 req/s |

## Notes

- Quartile data is provider-dependent. If an upstream API does not expose quartile directly, you will need a mapping or enrichment step later.
- Single provider failures don't block the entire query; failed providers appear in `warnings`.
