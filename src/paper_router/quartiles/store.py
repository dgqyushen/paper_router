from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from ..models import Quartile
from .fuzzy import fuzzy_match_journal, normalize_journal_name

_DDL = """
CREATE TABLE IF NOT EXISTS journals (
    id INTEGER PRIMARY KEY,
    journal_name TEXT NOT NULL,
    journal_name_norm TEXT NOT NULL,
    issn TEXT,
    jcr_year INTEGER NOT NULL,
    jcr_quartile TEXT NOT NULL,
    category TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journal_name_norm ON journals(journal_name_norm);
CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_unique ON journals(journal_name, jcr_year);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class QuartileStore:
    """SQLite-backed journal quartile store."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("db/quartiles.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_DDL)
        self._cache: dict[str, Quartile | None] = {}

    def upsert_batch(
        self,
        rows: list[tuple[str, str, int, str | None]],
        jcr_year: int,
    ) -> int:
        """Insert or update journal quartile records.

        Each row: (journal_name, quartile, jcr_year, category)
        Returns number of rows written.
        """
        now = date.today().isoformat()
        self._conn.executemany(
            """
            INSERT INTO journals (journal_name, journal_name_norm, jcr_year, jcr_quartile, category, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(journal_name, jcr_year) DO UPDATE SET
                jcr_quartile = excluded.jcr_quartile,
                category = excluded.category,
                updated_at = excluded.updated_at
            """,
            [
                (name, normalize_journal_name(name), jcr_year, q, cat, now)
                for name, q, _jcr_year_val, cat in rows
            ],
        )
        self._conn.commit()
        self._set_meta("last_updated", now)
        self._set_meta("jcr_year", str(jcr_year))
        self._cache.clear()
        return len(rows)

    def lookup(self, journal_name: str) -> Quartile | None:
        """Look up quartile by journal name. Uses fuzzy matching. Results are cached."""
        norm = normalize_journal_name(journal_name)

        # Check cache first
        if norm in self._cache:
            return self._cache[norm]

        # Load all normalized names from DB
        cursor = self._conn.execute(
            "SELECT journal_name_norm, jcr_quartile FROM journals"
        )
        candidates: dict[str, str] = {}
        for row in cursor:
            candidates[row[0]] = row[1]

        if not candidates:
            self._cache[norm] = None
            return None

        # Try exact match
        if norm in candidates:
            q = Quartile(candidates[norm])
            self._cache[norm] = q
            return q

        # Fuzzy match
        match = fuzzy_match_journal(journal_name, set(candidates.keys()))
        if match:
            q = Quartile(candidates[match])
            self._cache[norm] = q
            return q

        self._cache[norm] = None
        return None

    def is_stale(self, max_age_days: int = 180) -> bool:
        """Check if the quartile data is older than max_age_days."""
        last_updated_str = self._get_meta("last_updated")
        if not last_updated_str:
            return True
        try:
            last_updated = date.fromisoformat(last_updated_str)
        except ValueError:
            return True
        return (date.today() - last_updated).days > max_age_days

    def last_updated(self) -> str | None:
        return self._get_meta("last_updated")

    def record_count(self) -> int:
        cursor = self._conn.execute("SELECT COUNT(*) FROM journals")
        return cursor.fetchone()[0]

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def _get_meta(self, key: str) -> str | None:
        cursor = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()
