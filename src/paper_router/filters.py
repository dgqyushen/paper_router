from __future__ import annotations

from .models import Paper, SearchRequest


def paper_matches_request(paper: Paper, request: SearchRequest) -> bool:
    if (request.start_date or request.end_date) and paper.publication_date is None:
        return False

    if request.start_date and paper.publication_date and paper.publication_date < request.start_date:
        return False

    if request.end_date and paper.publication_date and paper.publication_date > request.end_date:
        return False

    return not (request.quartiles and paper.quartile not in request.quartiles)


def filter_papers(papers: list[Paper], request: SearchRequest) -> list[Paper]:
    filtered = [paper for paper in papers if paper_matches_request(paper, request)]
    if request.limit is not None:
        return filtered[: request.limit]
    return filtered
