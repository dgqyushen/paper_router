from __future__ import annotations

import time

import httpx
from bs4 import BeautifulSoup

_LETPUB_BASE = "https://www.letpub.com.cn"
_LETPUB_SEARCH_URL = f"{_LETPUB_BASE}/index.php?page=journalapp&view=search"


def _parse_letpub_page(html: str) -> list[tuple[str, str, str]]:
    """Parse a LetPub journal list HTML page.

    Returns list of (journal_name, major_quartile, minor_quartile).
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, str]] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr")[1:]:  # skip header
            tds = tr.find_all("td")
            if len(tds) >= 4:
                name = tds[0].get_text(strip=True)
                major_q = tds[2].get_text(strip=True)
                minor_q = tds[3].get_text(strip=True)
                if name and major_q in {"Q1", "Q2", "Q3", "Q4"}:
                    rows.append((name, major_q, minor_q))

    return rows


async def scrape_letpub(
    client: httpx.AsyncClient,
    jcr_year: int = 2024,
    delay_seconds: float = 2.0,
) -> list[tuple[str, str, str | None]]:
    """Scrape LetPub for SCI/SSCI journal quartile data.

    Returns list of (journal_name, quartile, category).
    Category is None — LetPub page does not expose it in the search table.
    """
    all_journals: list[tuple[str, str, str | None]] = []
    page = 1

    while True:
        params = {
            "page": page,
            "year": jcr_year,
            "field": "all",
        }
        response = await client.get(_LETPUB_SEARCH_URL, params=params, timeout=30.0)
        response.raise_for_status()

        rows = _parse_letpub_page(response.text)
        if not rows:
            break

        for name, major_q, _minor_q in rows:
            all_journals.append((name, major_q, None))

        page += 1
        time.sleep(delay_seconds)

    return all_journals
