from __future__ import annotations

import re
from difflib import SequenceMatcher

_FUZZY_THRESHOLD = 0.45


def normalize_journal_name(name: str) -> str:
    """Normalize a journal name for matching: lowercase, strip punctuation, collapse whitespace."""
    lowered = name.lower()
    no_punct = re.sub(r"[^\w\s]", "", lowered)
    return " ".join(no_punct.split())


def fuzzy_match_journal(
    query_name: str,
    candidates: set[str],
    threshold: float = _FUZZY_THRESHOLD,
) -> str | None:
    """Find the best matching normalized journal name for query_name.

    Returns the matched normalized name, or None if no candidate meets the threshold.
    """
    norm_query = normalize_journal_name(query_name)

    # Exact match first
    if norm_query in candidates:
        return norm_query

    # Fuzzy match
    best_match: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = SequenceMatcher(None, norm_query, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match
    return None
