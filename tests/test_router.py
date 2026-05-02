from __future__ import annotations

import asyncio
from datetime import date

import pytest

from paper_router import PaperRouter, Quartile, SearchRequest
from paper_router.models import Paper
from paper_router.providers.base import PaperProvider
from paper_router.rate_limit import AsyncRateLimiter, RateLimit


class StubProvider(PaperProvider):
    def __init__(self, name: str, papers: list[Paper]) -> None:
        self.name = name
        self.base_url = "https://example.com"
        self._papers = papers

    @classmethod
    def default_rate_limit(cls) -> RateLimit:
        return RateLimit(requests_per_second=1000)

    async def search(self, request: SearchRequest) -> list[Paper]:
        return self._papers

    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        raise NotImplementedError

    def parse_response(self, payload: dict) -> list[Paper]:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_router_filters_by_date_and_quartile() -> None:
    router = PaperRouter(
        [
            StubProvider(
                "openalex",
                [
                    Paper(
                        source="openalex",
                        external_id="1",
                        title="Paper A",
                        publication_date=date(2024, 6, 1),
                        quartile=Quartile.Q1,
                    ),
                    Paper(
                        source="openalex",
                        external_id="2",
                        title="Paper B",
                        publication_date=date(2023, 6, 1),
                        quartile=Quartile.Q3,
                    ),
                ],
            )
        ]
    )

    result, _ = await router.search(
        SearchRequest(
            query="test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            quartiles=frozenset({Quartile.Q1}),
        )
    )

    assert [paper.title for paper in result] == ["Paper A"]


@pytest.mark.asyncio
async def test_router_dedupes_by_doi_across_providers() -> None:
    shared_doi = "10.1000/example"
    router = PaperRouter(
        [
            StubProvider(
                "openalex",
                [
                    Paper(
                        source="openalex",
                        external_id="1",
                        title="Same Paper",
                        publication_date=date(2024, 6, 1),
                        doi=shared_doi,
                    )
                ],
            ),
            StubProvider(
                "semantic_scholar",
                [
                    Paper(
                        source="semantic_scholar",
                        external_id="2",
                        title="Same Paper",
                        publication_date=date(2024, 6, 1),
                        doi=shared_doi,
                    )
                ],
            ),
        ]
    )

    result, _ = await router.search(SearchRequest(query="test"))

    assert len(result) == 1
    assert result[0].source == "openalex"


@pytest.mark.asyncio
async def test_router_restricts_selected_providers() -> None:
    router = PaperRouter(
        [
            StubProvider(
                "openalex",
                [Paper(source="openalex", external_id="1", title="OpenAlex Paper")],
            ),
            StubProvider(
                "semantic_scholar",
                [Paper(source="semantic_scholar", external_id="2", title="S2 Paper")],
            ),
        ]
    )

    result, _ = await router.search(SearchRequest(query="test", providers=("semantic_scholar",)))

    assert [paper.source for paper in result] == ["semantic_scholar"]


@pytest.mark.asyncio
async def test_rate_limiter_waits_between_requests() -> None:
    limiter = AsyncRateLimiter(RateLimit(requests_per_second=5))

    start = asyncio.get_running_loop().time()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = asyncio.get_running_loop().time() - start

    assert elapsed >= 0.19
