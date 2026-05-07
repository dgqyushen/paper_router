from __future__ import annotations

from datetime import date

from .models import Paper


def paper_to_dict(paper: Paper) -> dict:
    return {
        "source": paper.source,
        "external_id": paper.external_id,
        "title": paper.title,
        "authors": list(paper.authors),
        "publication_date": paper.publication_date.isoformat() if paper.publication_date else None,
        "doi": paper.doi,
        "venue": paper.venue,
        "abstract": paper.abstract,
        "url": paper.url,
        "quartile": paper.quartile.value if paper.quartile else None,
    }


def parse_date(value: str | None, field_name: str | None = None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid date format for {field_name or 'date'}: {value!r}. Expected YYYY-MM-DD."
        )
