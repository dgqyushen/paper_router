from __future__ import annotations

from paper_router.quartiles.scraper import _parse_letpub_page

_SAMPLE_HTML = """
<html><body>
<table class="journal-table">
<tr><th>期刊名</th><th>ISSN</th><th>大类分区</th><th>小类分区</th></tr>
<tr><td>Nature</td><td>0028-0836</td><td>Q1</td><td>Q1</td></tr>
<tr><td>Science</td><td>0036-8075</td><td>Q1</td><td>Q1</td></tr>
<tr><td>PLOS ONE</td><td>1932-6203</td><td>Q3</td><td>Q2</td></tr>
</table>
</body></html>
"""


def test_parse_letpub_page() -> None:
    rows = _parse_letpub_page(_SAMPLE_HTML)
    assert len(rows) == 3
    assert rows[0] == ("Nature", "Q1", "Q1")
    assert rows[1] == ("Science", "Q1", "Q1")
    assert rows[2] == ("PLOS ONE", "Q3", "Q2")


def test_parse_empty_page() -> None:
    rows = _parse_letpub_page("<html></html>")
    assert rows == []


def test_parse_malformed_table() -> None:
    rows = _parse_letpub_page("<table><tr><td>Only</td></tr></table>")
    assert rows == []
