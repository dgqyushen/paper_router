"""paper_router CLI — synchronous JSON interface for agent consumption.

Usage:
  paper-router --queries "silicon anode" --providers openalex arxiv --limit 10
  paper-router --queries "battery" "cathode" --start_date 2024-01-01 --compact
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date

from paper_router.models import Paper, SearchRequest
from paper_router.registry import (
    VALID_PROVIDER_NAMES,
    create_router,
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _output(data: dict, *, compact: bool = False) -> None:
    indent = None if compact else 2
    if sys.platform == "win32":
        print(json.dumps(data, ensure_ascii=True, indent=indent))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=indent))


def _error(message: str, *, compact: bool = False, **extra: object) -> None:
    payload: dict = {"success": False, "error": message, **extra}
    _output(payload, compact=compact)


def _paper_to_dict(paper: Paper) -> dict:
    return {
        "source": paper.source,
        "external_id": paper.external_id,
        "title": paper.title,
        "authors": list(paper.authors),
        "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
        "doi": paper.doi,
        "venue": paper.venue,
        "abstract": paper.abstract,
        "url": paper.url,
        "quartile": paper.quartile.value if paper.quartile else None,
    }


# ---------------------------------------------------------------------------
# Date parsing with structured errors
# ---------------------------------------------------------------------------

def _parse_date(value: str | None, field_name: str, *, compact: bool) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        _error(
            f"Invalid date format for {field_name}: {value!r}. Expected YYYY-MM-DD.",
            compact=compact,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core search logic — query × provider granularity
# ---------------------------------------------------------------------------

async def _run_search(
    queries: list[str],
    provider_names: list[str],
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
    compact: bool,
) -> None:
    """Execute search synchronously, print structured JSON, exit."""
    warnings: list[str] = []
    all_papers: list[Paper] = []
    success_count = 0
    total_attempts = len(queries) * len(provider_names)

    router = create_router(provider_names)

    try:
        for query in queries:
            for provider_name in provider_names:
                try:
                    request = SearchRequest(
                        query=query,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit,
                        providers=(provider_name,),
                    )
                    papers = await router.search(request)
                    all_papers.extend(papers)
                    success_count += 1
                except Exception as exc:
                    warnings.append(
                        f"Provider '{provider_name}' failed for query '{query}': {exc}"
                    )

        # Deduplicate across queries/providers
        seen_keys: set[str] = set()
        unique: list[Paper] = []
        for paper in all_papers:
            key = paper.dedupe_key
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(paper)

        # Sort by date (newest first)
        unique.sort(key=lambda p: p.publication_date or date.min, reverse=True)

        results = [_paper_to_dict(p) for p in unique]

        if success_count == 0:
            # All attempts failed
            _error(
                "All search attempts failed.",
                compact=compact,
                warnings=warnings,
            )
            sys.exit(1)

        output: dict = {
            "success": True,
            "queries": queries,
            "providers": provider_names,
            "count": len(results),
            "results": results,
        }
        if warnings:
            output["warnings"] = warnings

        _output(output, compact=compact)

    finally:
        await router.aclose()


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-router",
        description="Academic paper search CLI for agent consumption",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  paper-router --queries "silicon anode" --limit 10
  paper-router --queries "battery" "cathode" --providers openalex arxiv
  paper-router --queries "Li-ion" --start_date 2024-01-01 --end_date 2024-12-31 --compact
""",
    )

    parser.add_argument(
        "--queries",
        type=str,
        nargs="+",
        help="Search queries (one or more)",
    )
    parser.add_argument(
        "--providers",
        type=str,
        nargs="+",
        action="append",
        help=f"Providers to use (default: all). Choices: {', '.join(VALID_PROVIDER_NAMES)}",
    )
    parser.add_argument(
        "--start_date",
        type=str,
        help="Earliest publication date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end_date",
        type=str,
        help="Latest publication date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum results per query",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )

    return parser


def _flatten_providers(raw: list[list[str]] | None) -> list[str] | None:
    """Flatten repeated --providers flags and deduplicate preserving order."""
    if not raw:
        return None
    flat: list[str] = []
    seen: set[str] = set()
    for group in raw:
        for name in group:
            if name not in seen:
                seen.add(name)
                flat.append(name)
    return flat


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    compact = args.compact

    # --- Validate queries ---
    if not args.queries:
        _error("No queries provided. Use --queries to specify search terms.", compact=compact)
        sys.exit(1)

    # Reject blank / whitespace-only queries
    queries = [q.strip() for q in args.queries]
    blank = [i for i, q in enumerate(queries) if not q]
    if blank:
        _error(
            f"Empty query at position {blank[0]}. Queries must be non-empty strings.",
            compact=compact,
        )
        sys.exit(1)

    # --- Validate providers ---
    provider_names = _flatten_providers(args.providers) or list(VALID_PROVIDER_NAMES)
    unknown = sorted(set(provider_names) - set(VALID_PROVIDER_NAMES))
    if unknown:
        _error(
            f"Unknown provider(s): {', '.join(unknown)}",
            compact=compact,
            available_providers=VALID_PROVIDER_NAMES,
        )
        sys.exit(1)

    # --- Validate limit ---
    if args.limit is not None and args.limit <= 0:
        _error(f"limit must be positive, got {args.limit}", compact=compact)
        sys.exit(1)

    # --- Validate dates ---
    start_date = _parse_date(args.start_date, "start_date", compact=compact)
    end_date = _parse_date(args.end_date, "end_date", compact=compact)

    if start_date and end_date and start_date > end_date:
        _error("start_date must be <= end_date", compact=compact)
        sys.exit(1)

    asyncio.run(_run_search(
        queries=queries,
        provider_names=provider_names,
        start_date=start_date,
        end_date=end_date,
        limit=args.limit,
        compact=compact,
    ))


if __name__ == "__main__":
    main()
