from __future__ import annotations

from datetime import date, timedelta

import pytest

from paper_router.models import Quartile
from paper_router.quartiles.store import QuartileStore


@pytest.fixture
def store(tmp_path) -> QuartileStore:
    db_path = tmp_path / "test_quartiles.db"
    return QuartileStore(db_path)


def _populate_store(store: QuartileStore) -> None:
    store.upsert_batch([
        ("Nature", "Q1", 2024, "Multidisciplinary"),
        ("Science", "Q1", 2024, "Multidisciplinary"),
        ("Cell", "Q1", 2024, "Biology"),
        ("PLOS ONE", "Q3", 2024, "Multidisciplinary"),
    ], jcr_year=2024)


def test_lookup_exact_match(store: QuartileStore) -> None:
    _populate_store(store)
    result = store.lookup("Nature")
    assert result == Quartile.Q1


def test_lookup_case_insensitive(store: QuartileStore) -> None:
    _populate_store(store)
    result = store.lookup("nature")
    assert result == Quartile.Q1


def test_lookup_fuzzy_match(store: QuartileStore) -> None:
    _populate_store(store)
    # "PLOS ONE" normalized is "plos one", fuzzy match from "PLoS ONE"
    result = store.lookup("PLoS ONE")
    assert result == Quartile.Q3


def test_lookup_unknown_returns_none(store: QuartileStore) -> None:
    _populate_store(store)
    result = store.lookup("Unknown Journal That Does Not Exist")
    assert result is None


def test_staleness_no_data(store: QuartileStore) -> None:
    assert store.is_stale(max_age_days=180) is True


def test_staleness_fresh_data(store: QuartileStore) -> None:
    _populate_store(store)
    # Force last_updated to now
    store._set_meta("last_updated", date.today().isoformat())
    assert store.is_stale(max_age_days=180) is False


def test_staleness_old_data(store: QuartileStore) -> None:
    _populate_store(store)
    old_date = date.today() - timedelta(days=200)
    store._set_meta("last_updated", old_date.isoformat())
    assert store.is_stale(max_age_days=180) is True


def test_record_count(store: QuartileStore) -> None:
    _populate_store(store)
    assert store.record_count() == 4


def test_meta_get_set(store: QuartileStore) -> None:
    store._set_meta("foo", "bar")
    assert store._get_meta("foo") == "bar"
    assert store._get_meta("nonexistent") is None
