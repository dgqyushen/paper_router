from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime

from ..models import Paper, SearchRequest
from ..rate_limit import RateLimit
from .base import PaperProvider

__all__ = ["ArXivProvider"]

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


class ArXivProvider(PaperProvider):
    name = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    @classmethod
    def default_rate_limit(cls) -> RateLimit:
        return RateLimit(requests_per_second=3)

    def build_params(self, request: SearchRequest) -> dict[str, str | int]:
        search_query = f"all:{request.query}"
        if request.start_date:
            search_query += f"+AND+submittedDate:[{request.start_date.strftime('%Y%m%d')}+TO+"
            search_query += request.end_date.strftime("%Y%m%d") if request.end_date else "99991231"
            search_query += "]"

        return {
            "search_query": search_query,
            "start": 0,
            "max_results": request.limit or 50,
        }

    def _parse_response_text(self, text: str) -> list[Paper]:
        return self._parse_xml(text)

    def _parse_xml(self, xml_text: str) -> list[Paper]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        papers: list[Paper] = []
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            paper = self._entry_to_paper(entry)
            if paper:
                papers.append(paper)
        return papers

    def _entry_to_paper(self, entry: ET.Element) -> Paper | None:
        paper_id_el = entry.find(f"{{{ATOM_NS}}}id")
        if paper_id_el is None or not paper_id_el.text:
            return None
        paper_id = paper_id_el.text
        arxiv_id = paper_id.rsplit("/", 1)[-1].split("v", 1)[0]

        title_el = entry.find(f"{{{ATOM_NS}}}title")
        title = re.sub(r"\s+", " ", title_el.text.strip()) if title_el is not None and title_el.text else ""

        summary_el = entry.find(f"{{{ATOM_NS}}}summary")
        summary = summary_el.text.strip() if summary_el is not None and summary_el.text else None

        published_el = entry.find(f"{{{ATOM_NS}}}published")
        pub_date = None
        if published_el is not None and published_el.text:
            pub_date = datetime.fromisoformat(published_el.text).date()

        authors = tuple(
            author.find(f"{{{ATOM_NS}}}name").text
            for author in entry.findall(f"{{{ATOM_NS}}}author")
            if author.find(f"{{{ATOM_NS}}}name") is not None
            and author.find(f"{{{ATOM_NS}}}name").text
        )

        doi = _extract_doi_from_arxiv(entry)
        categories = _extract_categories(entry)

        return Paper(
            source=self.name,
            external_id=arxiv_id,
            title=title,
            abstract=summary,
            publication_date=pub_date,
            doi=doi,
            authors=authors,
            venue=None,
            quartile=None,
            url=paper_id,
            raw={"categories": categories},
        )


def _extract_doi_from_arxiv(entry: ET.Element) -> str | None:
    comment_el = entry.find(f"{{{ARXIV_NS}}}comment")
    if comment_el is not None and comment_el.text:
        match = re.search(r"10\.\d{4,}/[^\s,;]+", comment_el.text)
        if match:
            return match.group(0).rstrip(".,;:)")

    primary = entry.find(f"{{{ARXIV_NS}}}primary_category")
    if primary is not None:
        for cat_el in entry.findall(f"{{{ARXIV_NS}}}category"):
            if cat_el.get("term", "").startswith("doi:"):
                return cat_el.get("term")[4:]

    for link in entry.findall(f"{{{ATOM_NS}}}link"):
        if link.get("title") == "doi":
            return link.get("href", "").removeprefix("https://doi.org/")

    return None


def _extract_categories(entry: ET.Element) -> list[str]:
    categories: list[str] = []
    primary = entry.find(f"{{{ARXIV_NS}}}primary_category")
    if primary is not None and primary.get("term"):
        categories.append(primary.get("term"))
    for cat_el in entry.findall(f"{{{ARXIV_NS}}}category"):
        term = cat_el.get("term")
        if term and term not in categories:
            categories.append(term)
    return categories
