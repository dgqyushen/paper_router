from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import date

from .filters import filter_papers
from .models import Paper, SearchRequest
from .providers.base import PaperProvider
from .quartiles import QuartileStore


class PaperRouter:
    def __init__(self, providers: Iterable[PaperProvider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    async def search(
        self,
        request: SearchRequest,
        quartile_store: QuartileStore | None = None,
    ) -> tuple[list[Paper], list[str]]:
        warnings: list[str] = []
        store = quartile_store or QuartileStore()

        providers = self._select_providers(request)
        results = await asyncio.gather(*(provider.search(request) for provider in providers))
        deduped = self._dedupe(paper for provider_papers in results for paper in provider_papers)

        # Enrich quartiles from local DB
        papers = self._enrich_quartiles(deduped, store)

        filtered = filter_papers(papers, request)

        # Staleness check
        if store.is_stale():
            last = store.last_updated()
            msg = (
                f"JCR quartile data is outdated"
                f"{f' (last updated: {last})' if last else ''}. "
                "Run 'paper-router update-quartiles' to refresh."
            )
            warnings.append(msg)

        return (
            sorted(
                filtered,
                key=lambda paper: paper.publication_date or date.min,
                reverse=True,
            ),
            warnings,
        )

    @staticmethod
    def _enrich_quartiles(papers: list[Paper], store: QuartileStore) -> list[Paper]:
        """Fill in missing quartiles from the local store."""
        enriched: list[Paper] = []
        for paper in papers:
            if paper.quartile is not None:
                enriched.append(paper)
                continue

            if paper.venue:
                q = store.lookup(paper.venue)
                if q is not None:
                    enriched.append(
                        Paper(
                            source=paper.source,
                            external_id=paper.external_id,
                            title=paper.title,
                            abstract=paper.abstract,
                            publication_date=paper.publication_date,
                            doi=paper.doi,
                            authors=paper.authors,
                            venue=paper.venue,
                            quartile=q,
                            url=paper.url,
                            raw=paper.raw,
                        )
                    )
                    continue

            enriched.append(paper)
        return enriched

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
