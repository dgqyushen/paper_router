from __future__ import annotations

import json
from datetime import date

import pytest

from paper_router.mcp_server import (
    _handle_list_providers,
    _handle_search_papers,
    _parse_date_arg,
    _paper_to_dict,
)
from paper_router.registry import create_router
from paper_router.models import Paper, Quartile


class TestMCPHelpers:
    def test_parse_date_arg_valid(self) -> None:
        assert _parse_date_arg("2024-06-15") == date(2024, 6, 15)

    def test_parse_date_arg_none(self) -> None:
        assert _parse_date_arg(None) is None

    def test_parse_date_arg_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid date format"):
            _parse_date_arg("not-a-date")

    def test_create_router_selects_providers(self) -> None:
        router = create_router(["openalex"])
        assert list(router._providers.keys()) == ["openalex"]

    def test_create_router_all_providers(self) -> None:
        router = create_router(None)
        assert "openalex" in router._providers
        assert "semantic_scholar" in router._providers
        assert "crossref" in router._providers
        assert "arxiv" in router._providers

    def test_create_router_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider"):
            create_router(["nonexistent"])

    def test_paper_to_dict_full(self) -> None:
        paper = Paper(
            source="test",
            external_id="123",
            title="Test",
            authors=("John Doe",),
            publication_date=date(2024, 6, 1),
            doi="10.1000/test",
            abstract="An abstract",
            venue="Test Journal",
            quartile=Quartile.Q1,
            url="https://example.com",
        )
        d = _paper_to_dict(paper)
        assert d["title"] == "Test"
        assert d["authors"] == ["John Doe"]
        assert d["quartile"] == "Q1"
        assert d["doi"] == "10.1000/test"

    def test_paper_to_dict_minimal(self) -> None:
        paper = Paper(source="test", external_id="1", title="Minimal")
        d = _paper_to_dict(paper)
        assert d["quartile"] is None
        assert d["publication_date"] is None
        assert d["doi"] is None


@pytest.mark.asyncio
async def test_handle_list_providers_returns_markdown() -> None:
    result = await _handle_list_providers()
    assert len(result) == 1
    text = result[0].text
    assert "Available Providers" in text
    assert "arxiv" in text
    assert "openalex" in text
    assert "crossref" in text
    assert "semantic_scholar" in text


@pytest.mark.asyncio
async def test_handle_search_papers_returns_json_structure() -> None:
    from unittest.mock import AsyncMock, patch
    mock_papers = [
        Paper(source="arxiv", external_id="1234.5678", title="Test Paper", authors=("A. Author",))
    ]
    with patch("paper_router.mcp_server.create_router") as mock_create:
        mock_router = AsyncMock()
        mock_router.search.return_value = (mock_papers, [])
        mock_router.aclose = AsyncMock()
        mock_create.return_value = mock_router

        result = await _handle_search_papers({
            "query": "test query",
            "providers": ["arxiv"],
        })

    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["count"] == 1
    assert data["results"][0]["title"] == "Test Paper"


@pytest.mark.asyncio
async def test_handle_search_papers_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        await _handle_search_papers({
            "query": "test",
            "providers": ["fake_provider"],
        })
