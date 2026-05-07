from __future__ import annotations

from datetime import date

from paper_router.models import SearchRequest
from paper_router.providers.arxiv import ArXivProvider

SAMPLE_ARXIV_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345</id>
    <title> A Novel Approach to Machine Learning </title>
    <author>
      <name>John Doe</name>
    </author>
    <author>
      <name>Jane Smith</name>
    </author>
    <summary>This paper presents a novel machine learning approach.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <arxiv:comment>Published in NeurIPS 2024. DOI: 10.1000/neurips.2024.1</arxiv:comment>
    <arxiv:primary_category term="cs.LG"/>
    <arxiv:category term="cs.LG"/>
    <arxiv:category term="stat.ML"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.67890</id>
    <title>Quantum Computing Survey</title>
    <author>
      <name>Alice Wang</name>
    </author>
    <summary>A comprehensive survey of quantum computing.</summary>
    <published>2024-02-20T00:00:00Z</published>
    <arxiv:primary_category term="quant-ph"/>
    <arxiv:category term="quant-ph"/>
  </entry>
</feed>"""


class TestArXivBuildParams:
    def test_minimal_query(self) -> None:
        provider = ArXivProvider()
        params = provider.build_params(SearchRequest(query="machine learning"))
        assert params["search_query"] == "all:machine learning"
        assert params["max_results"] == 50
        assert params["start"] == 0

    def test_with_limit(self) -> None:
        provider = ArXivProvider()
        params = provider.build_params(SearchRequest(query="test", limit=10))
        assert params["max_results"] == 10


class TestArXivParseXML:
    def test_parse_full_entry(self) -> None:
        provider = ArXivProvider()
        papers = provider._parse_xml(SAMPLE_ARXIV_XML)
        assert len(papers) == 2

        paper = papers[0]
        assert paper.source == "arxiv"
        assert paper.external_id == "2401.12345"
        assert paper.title == "A Novel Approach to Machine Learning"
        assert paper.abstract == "This paper presents a novel machine learning approach."
        assert paper.publication_date == date(2024, 1, 15)
        assert paper.doi == "10.1000/neurips.2024.1"
        assert paper.authors == ("John Doe", "Jane Smith")
        assert paper.venue is None
        assert paper.quartile is None
        assert paper.url == "http://arxiv.org/abs/2401.12345"
        assert "cs.LG" in paper.raw["categories"]
        assert "stat.ML" in paper.raw["categories"]

    def test_parse_without_doi(self) -> None:
        provider = ArXivProvider()
        papers = provider._parse_xml(SAMPLE_ARXIV_XML)

        paper = papers[1]
        assert paper.doi is None
        assert paper.external_id == "2402.67890"
        assert paper.title == "Quantum Computing Survey"
        assert paper.authors == ("Alice Wang",)
        assert paper.publication_date == date(2024, 2, 20)
        assert paper.raw["categories"] == ["quant-ph"]

    def test_empty_feed(self) -> None:
        provider = ArXivProvider()
        empty_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
</feed>"""
        papers = provider._parse_xml(empty_xml)
        assert papers == []


class TestArXivDefaultRateLimit:
    def test_rate_limit(self) -> None:
        assert ArXivProvider.default_rate_limit().requests_per_second == 3
