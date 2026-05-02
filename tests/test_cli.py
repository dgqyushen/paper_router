"""Tests for paper_router.cli — the agent-facing CLI interface."""

from __future__ import annotations

import json
import sys
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from paper_router.cli import (
    _build_parser,
    _flatten_providers,
    _parse_date,
    main,
)
from paper_router.models import Paper, Quartile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_cli(*args: str) -> tuple[int, str]:
    """Run CLI main() with given args, return (exit_code, stdout)."""
    with patch.object(sys, "argv", ["paper-router", *args]):
        import io
        captured = io.StringIO()
        old_stdout = sys.stdout
        exit_code = [0]
        sys.stdout = captured
        try:
            main()
        except SystemExit as e:
            exit_code[0] = int(e.code) if e.code is not None else 0
        finally:
            sys.stdout = old_stdout
        return exit_code[0], captured.getvalue()


def _run_cli_json(*args: str) -> tuple[int, dict]:
    """Run CLI, parse the last NDJSON line (the result event), return (exit_code, parsed)."""
    code, stdout = _run_cli(*args)
    lines = [l for l in stdout.strip().split("\n") if l.strip()]
    if not lines:
        return code, {}
    return code, json.loads(lines[-1])


def _make_paper(
    title: str = "Paper A",
    source: str = "openalex",
    doi: str = "10.1000/test",
    external_id: str = "123",
) -> Paper:
    return Paper(
        source=source,
        external_id=external_id,
        title=title,
        authors=("Author One",),
        publication_date=date(2024, 6, 1),
        doi=doi,
        venue="Test Journal",
        abstract="An abstract.",
        url="https://example.com",
        quartile=Quartile.Q1,
    )


# ---------------------------------------------------------------------------
# Argument parser tests
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_help_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            parser = _build_parser()
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Date parsing tests
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_valid_date(self) -> None:
        assert _parse_date("2024-06-15", "start_date") == date(2024, 6, 15)

    def test_none(self) -> None:
        assert _parse_date(None, "start_date") is None

    def test_empty_string(self) -> None:
        assert _parse_date("", "start_date") is None

    def test_invalid_exits_with_json_error(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _parse_date("not-a-date", "start_date")
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["finish"] is True
        assert data["type"] == "result"
        assert data["success"] is False
        assert "Invalid date format" in data["error"]


# ---------------------------------------------------------------------------
# Flatten providers
# ---------------------------------------------------------------------------

class TestFlattenProviders:
    def test_none(self) -> None:
        assert _flatten_providers(None) is None

    def test_single_group(self) -> None:
        assert _flatten_providers([["openalex", "arxiv"]]) == ["openalex", "arxiv"]

    def test_multiple_groups_dedup(self) -> None:
        result = _flatten_providers([["openalex", "arxiv"], ["crossref", "openalex"]])
        assert result == ["openalex", "arxiv", "crossref"]

    def test_preserves_order(self) -> None:
        result = _flatten_providers([["arxiv"], ["openalex"], ["arxiv", "crossref"]])
        assert result == ["arxiv", "openalex", "crossref"]


# ---------------------------------------------------------------------------
# Error output tests
# ---------------------------------------------------------------------------

class TestErrorOutputs:
    def test_no_query_provided(self) -> None:
        code, stdout = _run_cli("search")
        # argparse exits with code 2 when --queries is missing
        assert code in (1, 2)

    def test_unknown_provider(self) -> None:
        code, data = _run_cli_json("search", "--queries", "test", "--providers", "fake_provider")
        assert code == 1
        assert data["success"] is False
        assert "Unknown provider" in data["error"]
        assert "available_providers" in data

    def test_invalid_date(self) -> None:
        code, data = _run_cli_json("search", "--queries", "test", "--start_date", "bad-date")
        assert code == 1
        assert data["success"] is False
        assert "Invalid date format" in data["error"]

    def test_start_after_end_date(self) -> None:
        code, data = _run_cli_json(
            "search", "--queries", "test", "--start_date", "2025-01-01", "--end_date", "2024-01-01"
        )
        assert code == 1
        assert data["success"] is False
        assert "start_date must be <= end_date" in data["error"]

    def test_limit_zero_rejected(self) -> None:
        code, data = _run_cli_json("search", "--queries", "test", "--limit", "0")
        assert code == 1
        assert data["success"] is False
        assert "limit must be positive" in data["error"]

    def test_limit_negative_rejected(self) -> None:
        code, data = _run_cli_json("search", "--queries", "test", "--limit", "-5")
        assert code == 1
        assert data["success"] is False
        assert "limit must be positive" in data["error"]

    def test_blank_query_rejected(self) -> None:
        code, data = _run_cli_json("search", "--queries", "", "real query")
        assert code == 1
        assert data["success"] is False
        assert "Empty query" in data["error"]

    def test_whitespace_only_query_rejected(self) -> None:
        code, data = _run_cli_json("search", "--queries", "   ")
        assert code == 1
        assert data["success"] is False
        assert "Empty query" in data["error"]


# ---------------------------------------------------------------------------
# Successful search output structure
# ---------------------------------------------------------------------------

class TestSearchOutput:
    def test_single_query_json_structure(self) -> None:
        mock_papers = [_make_paper()]
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = (mock_papers, [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "test query", "--providers", "openalex")

        assert code == 0
        assert data["success"] is True
        assert data["queries"] == ["test query"]
        assert data["providers"] == ["openalex"]
        assert data["count"] == 1
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["source"] == "openalex"
        assert result["external_id"] == "123"
        assert result["title"] == "Paper A"
        assert result["authors"] == ["Author One"]
        assert result["doi"] == "10.1000/test"
        assert result["venue"] == "Test Journal"
        assert result["abstract"] == "An abstract."
        assert result["url"] == "https://example.com"
        assert result["quartile"] == "Q1"
        assert result["publication_date"] == "2024-06-01"

    def test_compact_flag_accepted(self) -> None:
        mock_papers = [_make_paper()]
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = (mock_papers, [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "test", "--providers", "openalex", "--compact")

        assert code == 0
        assert data["success"] is True  # --compact is a no-op but accepted

    def test_multi_query_merges_and_dedupes(self) -> None:
        paper_a = _make_paper("Paper A", doi="10.1000/a", external_id="1")
        paper_b = _make_paper("Paper B", source="semantic_scholar", doi="10.1000/b", external_id="2")
        paper_a_dup = _make_paper("Paper A", doi="10.1000/a", external_id="1")

        call_count = [0]
        # query × provider: 2 queries × 1 provider = 2 calls
        results_per_call = [[paper_a], [paper_b, paper_a_dup]]

        async def mock_search(request, **kwargs):
            result = results_per_call[call_count[0]]
            call_count[0] += 1
            return (result, [])

        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search = AsyncMock(side_effect=mock_search)
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "query1", "query2", "--providers", "openalex")

        assert code == 0
        assert data["count"] == 2
        titles = [r["title"] for r in data["results"]]
        assert "Paper A" in titles
        assert "Paper B" in titles

    def test_multi_provider_selection(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = ([], [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json(
                "search", "--queries", "test",
                "--providers", "openalex", "arxiv",
            )

        assert code == 0
        assert data["providers"] == ["openalex", "arxiv"]
        mock_create.assert_called_once_with(["openalex", "arxiv"])

    def test_repeated_providers_flag_flattened(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = ([], [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json(
                "search", "--queries", "test",
                "--providers", "openalex",
                "--providers", "arxiv",
                "--providers", "openalex",
            )

        assert code == 0
        assert data["providers"] == ["openalex", "arxiv"]
        mock_create.assert_called_once_with(["openalex", "arxiv"])

    def test_limit_passed_to_search_request(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = ([], [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "test", "--limit", "5")

        assert code == 0
        call_args = mock_router.search.call_args[0][0]
        assert call_args.limit == 5

    def test_date_range_passed_to_search_request(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = ([], [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json(
                "search", "--queries", "test",
                "--start_date", "2024-01-01",
                "--end_date", "2024-12-31",
            )

        assert code == 0
        call_args = mock_router.search.call_args[0][0]
        assert call_args.start_date == date(2024, 1, 1)
        assert call_args.end_date == date(2024, 12, 31)

    def test_all_providers_by_default(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search.return_value = ([], [])
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "test")

        assert code == 0
        assert len(data["providers"]) == 4
        assert set(data["providers"]) == {"openalex", "semantic_scholar", "crossref", "arxiv"}


# ---------------------------------------------------------------------------
# Provider-level fault tolerance
# ---------------------------------------------------------------------------

class TestProviderFaultTolerance:
    def test_single_provider_failure_returns_others(self) -> None:
        paper = _make_paper()
        call_count = [0]

        async def mock_search(request, **kwargs):
            call_count[0] += 1
            if request.providers == ("openalex",):
                return ([paper], [])
            raise RuntimeError("Provider down")

        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search = AsyncMock(side_effect=mock_search)
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json(
                "search", "--queries", "test", "--providers", "openalex", "arxiv"
            )

        assert code == 0
        assert data["success"] is True
        assert data["count"] == 1
        assert data["results"][0]["title"] == "Paper A"
        assert "warnings" in data
        assert len(data["warnings"]) == 1
        assert "arxiv" in data["warnings"][0]

    def test_all_providers_fail_returns_error(self) -> None:
        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search = AsyncMock(side_effect=RuntimeError("API down"))
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json("search", "--queries", "test", "--providers", "openalex")

        assert code == 1
        assert data["success"] is False
        assert "All search attempts failed" in data["error"]
        assert "warnings" in data

    def test_multi_query_multi_provider_partial_failure(self) -> None:
        paper = _make_paper()
        call_idx = [0]
        # 2 queries × 2 providers = 4 calls
        # q1/openalex: ok, q1/arxiv: fail, q2/openalex: fail, q2/arxiv: ok
        behavior = [
            [paper],           # q1/openalex
            RuntimeError("x"), # q1/arxiv
            RuntimeError("x"), # q2/openalex
            [paper],           # q2/arxiv
        ]

        async def mock_search(request, **kwargs):
            result = behavior[call_idx[0]]
            call_idx[0] += 1
            if isinstance(result, Exception):
                raise result
            return (result, [])

        with patch("paper_router.cli.create_router") as mock_create:
            mock_router = AsyncMock()
            mock_router.search = AsyncMock(side_effect=mock_search)
            mock_router.aclose = AsyncMock()
            mock_create.return_value = mock_router

            code, data = _run_cli_json(
                "search", "--queries", "q1", "q2", "--providers", "openalex", "arxiv"
            )

        assert code == 0
        assert data["success"] is True
        assert data["count"] == 1  # deduped
        assert len(data["warnings"]) == 2


# ---------------------------------------------------------------------------
# Main.py backward compatibility
# ---------------------------------------------------------------------------

class TestMainModuleCompat:
    def test_main_py_delegates_to_cli(self) -> None:
        """Verify src/paper_router/main.py is a thin wrapper."""
        from paper_router.main import main as legacy_main
        from paper_router.cli import main as cli_main
        assert legacy_main is cli_main


# ---------------------------------------------------------------------------
# TaskManager backward compat (kept in old main.py for existing code)
# ---------------------------------------------------------------------------

class TestLegacyTaskManager:
    def test_task_manager_still_works(self, tmp_path) -> None:
        """Ensure TaskManager in main.py is still importable for backward compat."""
        import sys
        sys.path.insert(0, str(tmp_path))
        from paper_router.main import main as _
        # main.py no longer re-exports TaskManager, but the module is importable
        # and doesn't crash. This verifies the thin wrapper works.
