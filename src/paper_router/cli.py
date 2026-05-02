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


def _emit(event: dict) -> None:
    """Emit a single NDJSON event line to stdout. Flush immediately for pipe consumers."""
    if sys.platform == "win32":
        print(json.dumps(event, ensure_ascii=True), flush=True)
    else:
        print(json.dumps(event, ensure_ascii=False), flush=True)


def _error(message: str, **extra: object) -> None:
    """Emit a fatal error result event and exit."""
    _emit({"finish": True, "type": "result", "success": False, "error": message, **extra})
    sys.exit(1)


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


def _parse_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        _error(f"Invalid date format for {field_name}: {value!r}. Expected YYYY-MM-DD.")


async def _run_search(
    queries: list[str],
    provider_names: list[str],
    start_date: date | None,
    end_date: date | None,
    limit: int | None,
    quartiles: frozenset,
) -> None:
    warnings: list[str] = []
    all_papers: list[Paper] = []
    success_count = 0
    total = len(queries) * len(provider_names)
    current = 0

    router = create_router(provider_names)

    try:
        _emit({"finish": False, "type": "progress", "current": current, "total": total, "message": "Starting search..."})
        print(f"[{current}/{total}] Starting search...", file=sys.stderr)

        for query in queries:
            for provider_name in provider_names:
                current += 1
                msg = f"searching {provider_name} for '{query}'..."
                _emit({"finish": False, "type": "progress", "current": current, "total": total, "message": msg})
                print(f"[{current}/{total}] {provider_name}: searching '{query}'...", file=sys.stderr)

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

                    _emit({
                        "finish": False,
                        "type": "papers",
                        "provider": provider_name,
                        "query": query,
                        "count": len(papers),
                        "papers": [_paper_to_dict(p) for p in papers],
                    })
                except Exception as exc:
                    msg = f"Provider '{provider_name}' failed for query '{query}': {exc}"
                    warnings.append(msg)
                    _emit({
                        "finish": False,
                        "type": "error",
                        "provider": provider_name,
                        "query": query,
                        "message": str(exc),
                    })

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
            _emit({
                "finish": True,
                "type": "result",
                "success": False,
                "error": "All search attempts failed.",
                "warnings": warnings,
            })
            sys.exit(1)

        output: dict = {
            "finish": True,
            "type": "result",
            "success": True,
            "queries": queries,
            "providers": provider_names,
            "count": len(results),
            "results": results,
        }
        if warnings:
            output["warnings"] = warnings

        _emit(output)

    finally:
        await router.aclose()


async def _run_update_quartiles(year: int) -> None:
    store = QuartileStore()
    print(f"Updating JCR quartile data (year={year})...", file=sys.stderr)
    async with httpx.AsyncClient(timeout=30.0) as client:
        rows = await scrape_letpub(client, jcr_year=year)
    if not rows:
        _error("No journals found. LetPub may have changed its page layout.")

    records = [(name, q, year, cat) for name, q, cat in rows]
    count = store.upsert_batch(records, jcr_year=year)
    _emit({"finish": True, "type": "result", "success": True, "message": f"Updated {count} journal quartile records."})


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
        queries = [q.strip() for q in args.queries]
        blank = [i for i, q in enumerate(queries) if not q]
        if blank:
            _error(f"Empty query at position {blank[0]}. Queries must be non-empty.")

        provider_names = _flatten_providers(args.providers) or list(VALID_PROVIDER_NAMES)
        unknown = sorted(set(provider_names) - set(VALID_PROVIDER_NAMES))
        if unknown:
            _error(
                f"Unknown provider(s): {', '.join(unknown)}",
                available_providers=list(VALID_PROVIDER_NAMES),
            )

        if args.limit is not None and args.limit <= 0:
            _error(f"limit must be positive, got {args.limit}")

        start_date = _parse_date(args.start_date, "start_date")
        end_date = _parse_date(args.end_date, "end_date")

        if start_date and end_date and start_date > end_date:
            _error("start_date must be <= end_date")

        quartiles = frozenset(args.quartiles) if args.quartiles else frozenset()

        asyncio.run(_run_search(
            queries=queries,
            provider_names=provider_names,
            start_date=start_date,
            end_date=end_date,
            limit=args.limit,
            quartiles=quartiles,
        ))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
