from __future__ import annotations

from datetime import date

from paper_router.models import SearchRequest
from paper_router.providers.crossref import CrossrefProvider, _parse_crossref_date


class TestCrossrefBuildParams:
    def test_minimal_query(self) -> None:
        provider = CrossrefProvider()
        params = provider.build_params(SearchRequest(query="machine learning"))
        assert params["query"] == "machine learning"
        assert params["rows"] == 50
        assert "filter" not in params

    def test_with_dates(self) -> None:
        provider = CrossrefProvider()
        params = provider.build_params(
            SearchRequest(
                query="test",
                start_date=date(2023, 1, 1),
                end_date=date(2024, 12, 31),
            )
        )
        assert "from-pub-date:2023-01-01" in params["filter"]
        assert "until-pub-date:2024-12-31" in params["filter"]

    def test_with_start_date_only(self) -> None:
        provider = CrossrefProvider()
        params = provider.build_params(
            SearchRequest(query="test", start_date=date(2023, 1, 1))
        )
        assert "from-pub-date:2023-01-01" in params["filter"]
        assert "until-pub-date:" not in params["filter"]

    def test_with_end_date_only(self) -> None:
        provider = CrossrefProvider()
        params = provider.build_params(
            SearchRequest(query="test", end_date=date(2024, 12, 31))
        )
        assert "until-pub-date:2024-12-31" in params["filter"]
        assert "from-pub-date:" not in params["filter"]


class TestCrossrefParseResponse:
    def test_parse_full_item(self) -> None:
        provider = CrossrefProvider()
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/example",
                        "title": ["Test Paper"],
                        "author": [
                            {"given": "John", "family": "Doe"},
                            {"given": "Jane", "family": "Smith"},
                        ],
                        "published-print": {"date-parts": [[2024, 6, 15]]},
                        "abstract": "An abstract about <jats:p>science</jats:p>.",
                        "URL": "https://doi.org/10.1000/example",
                        "container-title": ["Journal of Testing"],
                    }
                ]
            }
        }

        papers = provider.parse_response(payload)
        assert len(papers) == 1
        paper = papers[0]
        assert paper.doi == "10.1000/example"
        assert paper.title == "Test Paper"
        assert paper.authors == ("John Doe", "Jane Smith")
        assert paper.publication_date == date(2024, 6, 15)
        assert paper.abstract == "An abstract about science."
        assert paper.venue == "Journal of Testing"
        assert paper.url == "https://doi.org/10.1000/example"
        assert paper.source == "crossref"

    def test_parse_minimal_item(self) -> None:
        provider = CrossrefProvider()
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1000/minimal",
                        "title": ["Minimal"],
                        "author": [],
                    }
                ]
            }
        }
        papers = provider.parse_response(payload)
        assert len(papers) == 1
        assert papers[0].title == "Minimal"
        assert papers[0].authors == ()
        assert papers[0].publication_date is None
        assert papers[0].abstract is None

    def test_empty_results(self) -> None:
        provider = CrossrefProvider()
        assert provider.parse_response({"message": {"items": []}}) == []


class TestCrossrefHelpers:
    def test_parse_crossref_date_prefers_print(self) -> None:
        item = {
            "published-print": {"date-parts": [[2023, 5, 10]]},
            "published-online": {"date-parts": [[2023, 4, 1]]},
        }
        assert _parse_crossref_date(item) == date(2023, 5, 10)

    def test_parse_crossref_date_falls_back_to_online(self) -> None:
        item = {
            "published-online": {"date-parts": [[2023, 4, 1]]},
        }
        assert _parse_crossref_date(item) == date(2023, 4, 1)

    def test_parse_crossref_date_none_when_missing(self) -> None:
        assert _parse_crossref_date({}) is None

    def test_parse_crossref_date_falls_back_to_issued(self) -> None:
        item = {"issued": {"date-parts": [[2022, 3, 15]]}}
        assert _parse_crossref_date(item) == date(2022, 3, 15)

    def test_parse_crossref_date_partial_year_only(self) -> None:
        item = {"published-print": {"date-parts": [[2021]]}}
        assert _parse_crossref_date(item) == date(2021, 1, 1)

    def test_parse_crossref_date_partial_year_month(self) -> None:
        item = {"published-print": {"date-parts": [[2021, 6]]}}
        assert _parse_crossref_date(item) == date(2021, 6, 1)

    def test_parse_crossref_date_empty_date_parts(self) -> None:
        item = {"issued": {"date-parts": [[]]}}
        assert _parse_crossref_date(item) is None
