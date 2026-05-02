from __future__ import annotations

from paper_router.quartiles.fuzzy import normalize_journal_name, fuzzy_match_journal


def test_normalize_lowercases() -> None:
    assert normalize_journal_name("Nature") == "nature"


def test_normalize_strips_extra_whitespace() -> None:
    assert normalize_journal_name("  Journal  of   Physics  ") == "journal of physics"


def test_normalize_strips_punctuation() -> None:
    assert normalize_journal_name("J. Am. Chem. Soc.") == "j am chem soc"


def test_fuzzy_exact_match() -> None:
    names = {"nature", "science", "cell"}
    result = fuzzy_match_journal("Nature", names)
    assert result == "nature"


def test_fuzzy_close_match() -> None:
    names = {"journal of the american chemical society", "nature", "science"}
    result = fuzzy_match_journal("J Am Chem Soc", names)
    assert result == "journal of the american chemical society"


def test_fuzzy_no_match_below_threshold() -> None:
    names = {"nature", "science", "cell"}
    result = fuzzy_match_journal("Completely Unrelated Journal Xyz", names)
    assert result is None
