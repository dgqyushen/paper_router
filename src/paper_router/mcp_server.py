from __future__ import annotations

import asyncio
import json
from datetime import date

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from paper_router.models import SearchRequest
from paper_router.registry import (
    PROVIDER_DESCRIPTIONS,
    PROVIDER_MAP,
    create_router,
)
from paper_router.serialization import paper_to_dict

server = Server("paper-router")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_papers",
            description="Search academic papers across one or more databases. "
                        "Returns deduplicated, date-sorted results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. topic, keyword, phrase)",
                    },
                    "providers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(PROVIDER_MAP.keys()),
                        },
                        "description": "Providers to query. Empty = all. "
                                        f"Available: {json.dumps(PROVIDER_DESCRIPTIONS)}",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Earliest publication date (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Latest publication date (YYYY-MM-DD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_providers",
            description="List available paper search providers and their descriptions",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]



async def _handle_search_papers(arguments: dict) -> list[TextContent]:
    """Execute search_papers tool. Extracted for testability."""
    query = arguments["query"]
    provider_names = arguments.get("providers")
    start_date = _parse_date_arg(arguments.get("start_date"))
    end_date = _parse_date_arg(arguments.get("end_date"))
    limit = arguments.get("limit")

    router = create_router(provider_names)
    try:
        request = SearchRequest(
            query=query,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        papers, warnings = await router.search(request)
        results = [paper_to_dict(p) for p in papers]
        output: dict = {"count": len(results), "results": results}
        if warnings:
            output["warnings"] = warnings
        text = json.dumps(output, indent=2)
        return [TextContent(type="text", text=text)]
    finally:
        await router.aclose()


async def _handle_list_providers() -> list[TextContent]:
    """Execute list_providers tool. Extracted for testability."""
    lines = [
        f"- **{k}**: {v}"
        for k, v in PROVIDER_DESCRIPTIONS.items()
    ]
    return [TextContent(type="text", text="## Available Providers\n\n" + "\n".join(lines))]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_providers":
        return await _handle_list_providers()
    if name == "search_papers":
        return await _handle_search_papers(arguments)
    raise ValueError(f"Unknown tool: {name}")


def _parse_date_arg(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date format: {value!r}. Expected YYYY-MM-DD.")


async def _run_server() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    """Entry point for the MCP server."""
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
