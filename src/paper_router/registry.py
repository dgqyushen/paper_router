"""Central provider registry shared by CLI and MCP."""

from __future__ import annotations

from typing import Any

from paper_router.config import load_config
from paper_router.providers.arxiv import ArXivProvider
from paper_router.providers.crossref import CrossrefProvider
from paper_router.providers.openalex import OpenAlexProvider
from paper_router.providers.semantic_scholar import SemanticScholarProvider
from paper_router.router import PaperRouter

PROVIDER_INFO: dict[str, dict[str, Any]] = {
    "arxiv": {
        "class": ArXivProvider,
        "description": "arXiv preprint server (physics, math, CS, q-bio)",
    },
    "crossref": {
        "class": CrossrefProvider,
        "description": "CrossRef DOI registry (all disciplines)",
    },
    "openalex": {
        "class": OpenAlexProvider,
        "description": "OpenAlex open scholarly index (all disciplines)",
    },
    "semantic_scholar": {
        "class": SemanticScholarProvider,
        "description": "Semantic Scholar (AI/CS focused)",
    },
}

PROVIDER_MAP: dict[str, type] = {
    k: v["class"] for k, v in PROVIDER_INFO.items()
}

PROVIDER_DESCRIPTIONS: dict[str, str] = {
    k: v["description"] for k, v in PROVIDER_INFO.items()
}

VALID_PROVIDER_NAMES: list[str] = list(PROVIDER_INFO.keys())


def create_router(provider_names: list[str] | None) -> PaperRouter:
    """Create a PaperRouter with the requested providers.

    Raises ValueError if any provider name is unknown.
    """
    names = provider_names or list(PROVIDER_MAP.keys())
    unknown = set(names) - set(PROVIDER_MAP.keys())
    if unknown:
        raise ValueError(
            f"Unknown provider(s): {', '.join(sorted(unknown))}. "
            f"Available: {', '.join(PROVIDER_MAP)}"
        )
    config = load_config()
    providers = [
        PROVIDER_MAP[name](api_key=getattr(config, name).api_key)
        for name in names
    ]
    return PaperRouter(providers)
