from __future__ import annotations

from datetime import date

from ..models import Paper, Quartile, SearchRequest
from ..rate_limit import RateLimit
from .base import PaperProvider


class OpenAlexProvider(PaperProvider):
    name = "openalex"
    base_url = "https://api.openalex.org/works"

    @classmethod
    def default_rate_limit(cls) -> RateLimit:
        return RateLimit(requests_per_second=10)

    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        filters = []
        if request.start_date:
            filters.append(f"from_publication_date:{request.start_date.isoformat()}")
        if request.end_date:
            filters.append(f"to_publication_date:{request.end_date.isoformat()}")

        params: dict[str, str | int] = {
            "search": request.query,
            "per-page": request.limit or 50,
        }
        if filters:
            params["filter"] = ",".join(filters)
        return params

    def parse_response(self, payload: dict) -> list[Paper]:
        papers: list[Paper] = []
        for item in payload.get("results", []):
            publication_date = _parse_date(item.get("publication_date"))
            papers.append(
                Paper(
                    source=self.name,
                    external_id=item["id"],
                    title=item.get("display_name", ""),
                    abstract=None,
                    publication_date=publication_date,
                    doi=_normalize_doi(item.get("doi")),
                    authors=tuple(
                        author.get("author", {}).get("display_name", "")
                        for author in item.get("authorships", [])
                        if author.get("author", {}).get("display_name")
                    ),
                    venue=_safe_get_venue(item),
                    quartile=_extract_quartile(item),
                    url=_safe_get_url(item),
                    raw=item,
                )
            )
        return papers


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.removeprefix("https://doi.org/")


def _safe_get_venue(item: dict) -> str | None:
    """安全获取期刊名称"""
    primary_location = item.get("primary_location")
    if not primary_location:
        return None
    source = primary_location.get("source")
    if not source:
        return None
    return source.get("display_name")


def _safe_get_url(item: dict) -> str | None:
    """安全获取 URL"""
    primary_location = item.get("primary_location")
    if not primary_location:
        return None
    return primary_location.get("landing_page_url")


def _extract_quartile(item: dict) -> Quartile | None:
    """提取期刊分区"""
    primary_location = item.get("primary_location")
    if not primary_location:
        return None
    source = primary_location.get("source")
    if not source:
        return None
    value = source.get("x_quartile")
    if value in Quartile.__members__:
        return Quartile[value]
    if value in Quartile._value2member_map_:
        return Quartile(value)
    return None
