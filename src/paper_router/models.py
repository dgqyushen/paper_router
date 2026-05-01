from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class Quartile(StrEnum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


@dataclass(slots=True, frozen=True)
class SearchRequest:
    query: str
    start_date: date | None = None
    end_date: date | None = None
    quartiles: frozenset[Quartile] = field(default_factory=frozenset)
    providers: tuple[str, ...] = ()
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")

        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be positive")


@dataclass(slots=True, frozen=True)
class Paper:
    source: str
    external_id: str
    title: str
    abstract: str | None = None
    publication_date: date | None = None
    doi: str | None = None
    authors: tuple[str, ...] = ()
    venue: str | None = None
    quartile: Quartile | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"

        normalized_title = " ".join(self.title.casefold().split())
        return f"title:{normalized_title}|date:{self.publication_date}"
