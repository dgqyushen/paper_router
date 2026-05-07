from __future__ import annotations

from datetime import date

import pytest

from paper_router import PaperRouter, Quartile, SearchRequest
from paper_router.models import Paper
from paper_router.providers.base import PaperProvider
from paper_router.quartiles import QuartileStore
from paper_router.rate_limit import RateLimit


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
async def test_enrich_quartiles_from_local_db(tmp_path) -> None:
    db_path = tmp_path / "quartiles.db"
    store = QuartileStore(db_path)
    store.upsert_batch([("Nature", "Q1", 2024, "Multidisciplinary")], jcr_year=2024)

    router = PaperRouter(
        [
            StubProvider(
                "openalex",
                [
                    Paper(
                        source="openalex",
                        external_id="1",
                        title="Paper A",
                        venue="Nature",
                        publication_date=date(2024, 6, 1),
                        quartile=None,
                    )
                ],
            )
        ]
    )

    papers, warnings = await router.search(
        SearchRequest(query="test", quartiles=frozenset({Quartile.Q1})),
        quartile_store=store,
    )

    assert len(papers) == 1
    assert papers[0].quartile == Quartile.Q1
    assert not warnings


@pytest.mark.asyncio
async def test_preserves_existing_quartile_from_provider(tmp_path) -> None:
    db_path = tmp_path / "quartiles.db"
    store = QuartileStore(db_path)
    # DB says Q1, but provider already says Q2
    store.upsert_batch([("Nature", "Q1", 2024, "Multidisciplinary")], jcr_year=2024)

    router = PaperRouter(
        [
            StubProvider(
                "openalex",
                [
                    Paper(
                        source="openalex",
                        external_id="1",
                        title="Paper A",
                        venue="Nature",
                        publication_date=date(2024, 6, 1),
                        quartile=Quartile.Q2,
                    )
                ],
            )
        ]
    )

    papers, _ = await router.search(
        SearchRequest(query="test"),
        quartile_store=store,
    )

    # Provider quartile takes priority
    assert papers[0].quartile == Quartile.Q2


@pytest.mark.asyncio
async def test_staleness_warning(tmp_path) -> None:
    db_path = tmp_path / "quartiles.db"
    store = QuartileStore(db_path)
    # No data => is_stale returns True

    router = PaperRouter([StubProvider("openalex", [])])

    papers, warnings = await router.search(
        SearchRequest(query="test"),
        quartile_store=store,
    )

    assert len(warnings) == 1
    assert "update-quartiles" in warnings[0]
