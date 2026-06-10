from typing import Any
from unittest.mock import MagicMock, patch

from processors.news_aggregator import _deduplicate, aggregate


def _article(
    title: str = "Story",
    link: str = "https://example.com/a",
    source: str = "Reuters",
    category: str = "top",
    image: str = "",
    published: str = "2025-01-01",
) -> dict[str, str]:
    return {"title": title, "link": link, "source": source, "category": category, "image": image, "published": published}


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


class TestAggregate:
    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    @patch("processors.news_aggregator.fetch_india_news")
    def test_collects_from_all_sources(
        self,
        mock_india: MagicMock,
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
        mock_india.return_value = [
            _article(title="I1", link="https://ex.com/i1", source="The Hindu"),
        ]

        result = aggregate(count=3)

        assert len(result) == 5

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    @patch("processors.news_aggregator.fetch_india_news")
    def test_deduplicates_across_sources(
        self,
        mock_india: MagicMock,
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
        mock_india.return_value = []

        result = aggregate(count=3)
        assert len(result) == 1
        assert result[0]["title"] == "Dup"

    @patch("processors.news_aggregator.fetch_top_news")
    @patch("processors.news_aggregator.fetch_business_news")
    @patch("processors.news_aggregator.fetch_techcrunch_news")
    @patch("processors.news_aggregator.fetch_india_news")
    def test_handles_empty_feeds(
        self,
        mock_india: MagicMock,
        mock_tc: MagicMock,
        mock_biz: MagicMock,
        mock_top: MagicMock,
    ) -> None:
        mock_top.return_value = []
        mock_biz.return_value = []
        mock_tc.return_value = []
        mock_india.return_value = []

        result = aggregate()
        assert result == []
