from __future__ import annotations

import html
import re
from datetime import date

from ..models import Paper, SearchRequest
from ..rate_limit import RateLimit
from .base import PaperProvider

__all__ = ["CrossrefProvider"]


class CrossrefProvider(PaperProvider):
    name = "crossref"
    base_url = "https://api.crossref.org/works"

    @classmethod
    def default_rate_limit(cls) -> RateLimit:
        return RateLimit(requests_per_second=50)

    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        filters: list[str] = []
        if request.start_date:
            filters.append(f"from-pub-date:{request.start_date.isoformat()}")
        if request.end_date:
            filters.append(f"until-pub-date:{request.end_date.isoformat()}")

        params: dict[str, str | int] = {
            "query": request.query,
            "rows": request.limit or 50,
        }
        if filters:
            params["filter"] = ",".join(filters)
        return params

    def parse_response(self, payload: dict) -> list[Paper]:
        papers: list[Paper] = []
        for item in payload.get("message", {}).get("items", []):
            publication_date = _parse_crossref_date(item)
            doi = item.get("DOI")
            title = _extract_title(item)
            abstract = _strip_html_tags(item.get("abstract") or "")

            papers.append(
                Paper(
                    source=self.name,
                    external_id=doi or title or item.get("URL") or "crossref:unknown",
                    title=title or "",
                    abstract=abstract or None,
                    publication_date=publication_date,
                    doi=doi,
                    authors=tuple(
                        _format_author(a) for a in item.get("author", [])
                        if _format_author(a)
                    ),
                    venue=_get_container(item),
                    quartile=None,
                    url=item.get("URL"),
                    raw=item,
                )
            )
        return papers


def _parse_crossref_date(item: dict) -> date | None:
    for key in ("published-print", "published-online", "issued"):
        parts = item.get(key, {}).get("date-parts")
        if parts and len(parts[0]) >= 3:
            return date(parts[0][0], parts[0][1], parts[0][2])
        if parts and len(parts[0]) >= 2:
            return date(parts[0][0], parts[0][1], 1)
        if parts and len(parts[0]) >= 1:
            return date(parts[0][0], 1, 1)
    return None


def _extract_title(item: dict) -> str | None:
    titles = item.get("title", [])
    return titles[0] if titles else None


def _format_author(author: dict) -> str | None:
    given = author.get("given", "")
    family = author.get("family", "")
    name = f"{given} {family}".strip()
    return name or None


def _get_container(item: dict) -> str | None:
    containers = item.get("container-title", [])
    return containers[0] if containers else None


def _strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip() if text else ""
