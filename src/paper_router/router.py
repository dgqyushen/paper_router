from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import date

from .filters import filter_papers
from .models import Paper, SearchRequest
from .providers.base import PaperProvider


class PaperRouter:
    def __init__(self, providers: Iterable[PaperProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    async def search(self, request: SearchRequest) -> list[Paper]:
        providers = self._select_providers(request)
        results = await asyncio.gather(*(provider.search(request) for provider in providers))
        deduped = self._dedupe(paper for provider_papers in results for paper in provider_papers)
        filtered = filter_papers(deduped, request)
        return sorted(
            filtered,
            key=lambda paper: paper.publication_date or date.min,
            reverse=True,
        )

    def _select_providers(self, request: SearchRequest) -> list[PaperProvider]:
        if not request.providers:
            return list(self._providers.values())

        missing = [provider for provider in request.providers if provider not in self._providers]
        if missing:
            raise ValueError(f"Unknown providers requested: {', '.join(missing)}")

        return [self._providers[name] for name in request.providers]

    @staticmethod
    def _dedupe(papers: Iterable[Paper]) -> list[Paper]:
        unique: dict[str, Paper] = {}
        for paper in papers:
            unique.setdefault(paper.dedupe_key, paper)
        return list(unique.values())

    async def aclose(self) -> None:
        await asyncio.gather(*(provider.aclose() for provider in self._providers.values()))
