from typing import Any
from unittest.mock import MagicMock, patch

from processors.news_aggregator import _deduplicate, _project, aggregate


def _article(
    title: str = "Story",
    link: str = "https://example.com/a",
    source: str = "Reuters",
    category: str = "top",
    image: str = "",
) -> dict[str, str]:
    return {"title": title, "link": link, "source": source, "category": category, "image": image}


class TestDeduplicate:
    def test_removes_duplicates_by_link(self) -> None:
        articles = [
            _article(title="A", link="https://ex.com/1"),
            _article(title="B", link="https://ex.com/2"),
            _article(title="A dup", link="https://ex.com/1"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 2
        assert result[0]["title"] == "A"

    def test_keeps_all_unique(self) -> None:
        articles = [
            _article(link="https://ex.com/1"),
            _article(link="https://ex.com/2"),
        ]
        assert len(_deduplicate(articles)) == 2

    def test_keeps_empty_link_articles(self) -> None:
        articles = [
            _article(link="", title="No link A"),
            _article(link="https://ex.com/1", title="Has link"),
            _article(link="", title="No link B"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 3

    def test_empty_list(self) -> None:
        assert _deduplicate([]) == []


class TestProject:
    def test_extracts_output_fields(self) -> None:
        article: dict[str, str] = {
            "title": "Hello",
            "link": "https://ex.com",
            "published": "2025-01-01",
            "category": "top",
            "source": "Reuters",
        }
        result = _project(article)
        assert result == {
            "title": "Hello",
            "source": "Reuters",
            "category": "top",
            "link": "https://ex.com",
            "image": "",
        }

    def test_missing_fields_default_to_empty(self) -> None:
        result = _project({})
        assert result == {"title": "", "source": "", "category": "", "link": "", "image": ""}


class TestAggregate:
    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    def test_collects_from_all_sources(
        self,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = [
            _article(title="T1", link="https://ex.com/t1", source="Reuters"),
            _article(title="T2", link="https://ex.com/t2", source="Reuters"),
        ]
        mock_biz.return_value = [
            _article(title="B1", link="https://ex.com/b1", source="Reuters"),
        ]
        mock_tc.return_value = [
            _article(title="C1", link="https://ex.com/c1", source="TechCrunch"),
        ]

        result = aggregate(count=3)

        assert len(result) == 4
        assert result[0] == {
            "title": "T1", "source": "Reuters", "category": "top", "link": "https://ex.com/t1", "image": "",
        }
        assert result[-1] == {
            "title": "C1",
            "source": "TechCrunch",
            "category": "top",
            "link": "https://ex.com/c1",
            "image": "",
        }

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    def test_deduplicates_across_sources(
        self,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = [
            _article(title="Dup", link="https://ex.com/dup", source="Reuters"),
        ]
        mock_biz.return_value = []
        mock_tc.return_value = [
            _article(title="Dup", link="https://ex.com/dup", source="TechCrunch"),
        ]

        result = aggregate(count=3)
        assert len(result) == 1
        assert result[0]["title"] == "Dup"

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    def test_passes_count_to_each_source(
        self,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = []
        mock_biz.return_value = []
        mock_tc.return_value = []

        aggregate(count=5)

        mock_top.assert_called_once_with(5)
        mock_biz.assert_called_once_with(5)
        mock_tc.assert_called_once_with(5)

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    def test_output_format(
        self,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = [
            _article(title="X", source="Reuters"),
        ]
        mock_biz.return_value = []
        mock_tc.return_value = []

        result = aggregate()
        assert len(result) == 1
        item = result[0]
        assert set(item.keys()) == {"title", "source", "category", "link", "image"}
        assert all(isinstance(v, str) for v in item.values())

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    def test_handles_empty_feeds(
        self,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = []
        mock_biz.return_value = []
        mock_tc.return_value = []

        result = aggregate()
        assert result == []
