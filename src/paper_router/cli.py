"""paper_router CLI — synchronous JSON interface for agent consumption.

Usage:
  paper-router search --queries "silicon anode" --providers openalex arxiv --limit 10
  paper-router update-quartiles [--year 2024]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date

import httpx

from paper_router.models import Paper, SearchRequest
from paper_router.quartiles import QuartileStore, scrape_letpub
from paper_router.registry import (
    VALID_PROVIDER_NAMES,
    create_router,
)


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


async def _run_search(
    queries: list[str],
    provider_names: list[str],
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
    compact: bool,
    quartiles: frozenset,
) -> None:
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
                        quartiles=quartiles,
                    )
                    papers, ws = await router.search(request)
                    all_papers.extend(papers)
                    warnings.extend(ws)
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


async def _run_update_quartiles(year: int) -> None:
    store = QuartileStore()
    print(f"Updating JCR quartile data (year={year})...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        rows = await scrape_letpub(client, jcr_year=year)
    if not rows:
        _error("No journals found. LetPub may have changed its page layout.")
        sys.exit(1)

    records = [(name, q, year, cat) for name, q, cat in rows]
    count = store.upsert_batch(records, jcr_year=year)
    print(f"Updated {count} journal quartile records.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper-router",
        description="Academic paper search CLI for agent consumption",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    # search subcommand
    search_parser = subparsers.add_parser("search", help="Search academic papers")
    search_parser.add_argument(
        "--queries",
        type=str,
        nargs="+",
        required=True,
        help="Search queries (one or more)",
    )
    search_parser.add_argument(
        "--providers",
        type=str,
        nargs="+",
        action="append",
        help=f"Providers to use (default: all). Choices: {', '.join(VALID_PROVIDER_NAMES)}",
    )
    search_parser.add_argument(
        "--start_date",
        type=str,
        help="Earliest publication date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--end_date",
        type=str,
        help="Latest publication date (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum results per query",
    )
    search_parser.add_argument(
        "--quartiles",
        type=str,
        nargs="+",
        choices=["Q1", "Q2", "Q3", "Q4"],
        help="Filter by JCR quartile(s)",
    )
    search_parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )

    # update-quartiles subcommand
    update_parser = subparsers.add_parser(
        "update-quartiles",
        help="Update local JCR quartile database from LetPub",
        description="Update local JCR quartile database from LetPub",
    )
    update_parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="JCR year to fetch (default: 2024)",
    )

    return parser


def _flatten_providers(raw: list[list[str]] | None) -> list[str] | None:
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


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "update-quartiles":
        asyncio.run(_run_update_quartiles(args.year))
        return

    if args.command == "search":
        compact = args.compact

        queries = [q.strip() for q in args.queries]
        blank = [i for i, q in enumerate(queries) if not q]
        if blank:
            _error(f"Empty query at position {blank[0]}. Queries must be non-empty.", compact=compact)
            sys.exit(1)

        provider_names = _flatten_providers(args.providers) or list(VALID_PROVIDER_NAMES)
        unknown = sorted(set(provider_names) - set(VALID_PROVIDER_NAMES))
        if unknown:
            _error(
                f"Unknown provider(s): {', '.join(unknown)}",
                compact=compact,
                available_providers=VALID_PROVIDER_NAMES,
            )
            sys.exit(1)

        if args.limit is not None and args.limit <= 0:
            _error(f"limit must be positive, got {args.limit}", compact=compact)
            sys.exit(1)

        start_date = _parse_date(args.start_date, "start_date", compact=compact)
        end_date = _parse_date(args.end_date, "end_date", compact=compact)

        if start_date and end_date and start_date > end_date:
            _error("start_date must be <= end_date", compact=compact)
            sys.exit(1)

        quartiles = frozenset(args.quartiles) if args.quartiles else frozenset()

        asyncio.run(_run_search(
            queries=queries,
            provider_names=provider_names,
            start_date=start_date,
            end_date=end_date,
            limit=args.limit,
            compact=compact,
            quartiles=quartiles,
        ))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
