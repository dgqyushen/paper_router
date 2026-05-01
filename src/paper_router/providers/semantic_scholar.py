from __future__ import annotations

from datetime import date

from ..models import Paper, Quartile, SearchRequest
from ..rate_limit import RateLimit
from .base import PaperProvider


class SemanticScholarProvider(PaperProvider):
    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    @classmethod
    def default_rate_limit(cls) -> RateLimit:
        return RateLimit(requests_per_second=1)

    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "query": request.query,
            "limit": request.limit or 50,
            "fields": (
                "paperId,title,abstract,publicationDate,externalIds,authors.name,"
                "venue,url,journal"
            ),
        }
        if request.start_date:
            params["year"] = request.start_date.year
        return params

    def parse_response(self, payload: dict) -> list[Paper]:
        papers: list[Paper] = []
        for item in payload.get("data", []):
            publication_date = _parse_date(item.get("publicationDate"))
            journal = item.get("journal") or {}
            papers.append(
                Paper(
                    source=self.name,
                    external_id=item["paperId"],
                    title=item.get("title", ""),
                    abstract=item.get("abstract"),
                    publication_date=publication_date,
                    doi=(item.get("externalIds") or {}).get("DOI"),
                    authors=tuple(author.get("name", "") for author in item.get("authors", []) if author.get("name")),
                    venue=item.get("venue") or journal.get("name"),
                    quartile=_extract_quartile(journal),
                    url=item.get("url"),
                    raw=item,
                )
            )
        return papers


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    if len(value) == 4:
        return date(int(value), 1, 1)

    return date.fromisoformat(value)


def _extract_quartile(journal: dict) -> Quartile | None:
    value = journal.get("quartile")
    if value in Quartile._value2member_map_:
        return Quartile(value)
    return None
