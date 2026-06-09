from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fetchers.reuters import (
    NEWS_FEEDS,
    _parse_entry,
    _remove_duplicates,
    fetch_all,
    fetch_business_news,
    fetch_news,
    fetch_top_news,
)


def _make_entry(
    title: str = "Test Title",
    link: str = "https://reuters.com/article/test",
    published: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "title": title,
        "link": link,
        "published": published or "Tue, 01 Jan 2025 12:00:00 GMT",
        "summary": "Test summary",
    }
    entry.update(kwargs)
    return entry


def _make_feed(entries: list[dict[str, Any]]) -> MagicMock:
    feed = MagicMock()
    feed.entries = entries
    feed.bozo = 0
    feed.bozo_exception = None
    return feed


class TestParseEntry:
    def test_parses_title(self) -> None:
        result = _parse_entry(_make_entry(), "top")
        assert result["title"] == "Test Title"

    def test_parses_link(self) -> None:
        result = _parse_entry(_make_entry(link="https://example.com/story"), "top")
        assert result["link"] == "https://example.com/story"

    def test_parses_published(self) -> None:
        result = _parse_entry(
            _make_entry(published="Mon, 15 Mar 2025 08:30:00 +0000"), "top"
        )
        assert result["published"] == "Mon, 15 Mar 2025 08:30:00 +0000"

    def test_falls_back_to_updated_when_published_missing(self) -> None:
        entry: dict[str, Any] = {
            "title": "No published date",
            "link": "https://reuters.com/article/test2",
            "updated": "Wed, 20 Mar 2025 10:00:00 GMT",
        }
        result = _parse_entry(entry, "business")
        assert result["published"] == "Wed, 20 Mar 2025 10:00:00 GMT"

    def test_parses_source(self) -> None:
        result = _parse_entry(_make_entry(), "top")
        assert result["source"] == "BBC"

    def test_parses_category(self) -> None:
        result = _parse_entry(_make_entry(), "business")
        assert result["category"] == "business"

    def test_handles_empty_entry(self) -> None:
        result = _parse_entry({}, "top")
        assert result == {
            "title": "",
            "link": "",
            "published": "",
            "category": "top",
            "source": "BBC",
            "image": "",
        }


class TestRemoveDuplicates:
    def test_removes_duplicate_links(self) -> None:
        articles = [
            {"link": "https://reuters.com/a", "title": "A"},
            {"link": "https://reuters.com/b", "title": "B"},
            {"link": "https://reuters.com/a", "title": "A duplicate"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 2

    def test_keeps_all_unique(self) -> None:
        articles = [
            {"link": "https://reuters.com/1"},
            {"link": "https://reuters.com/2"},
            {"link": "https://reuters.com/3"},
        ]
        assert len(_remove_duplicates(articles)) == 3

    def test_skips_empty_link(self) -> None:
        articles = [
            {"link": "", "title": "No link"},
            {"link": "https://reuters.com/a", "title": "A"},
            {"link": "", "title": "Another no link"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 3

    def test_returns_empty_list_for_empty_input(self) -> None:
        assert _remove_duplicates([]) == []

    def test_skips_missing_link_key(self) -> None:
        articles = [
            {"title": "Missing link key"},
            {"link": "https://reuters.com/a", "title": "A"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 2


class TestFetchNews:
    @patch("fetchers.reuters.feedparser.parse")
    def test_returns_articles(self, mock_parse: MagicMock) -> None:
        entries = [
            _make_entry(title="Article 1", link="https://reuters.com/a"),
            _make_entry(title="Article 2", link="https://reuters.com/b"),
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news("top", count=10)
        assert len(result) == 2
        assert result[0]["title"] == "Article 1"
        assert result[1]["source"] == "BBC"

    @patch("fetchers.reuters.feedparser.parse")
    def test_limits_by_count(self, mock_parse: MagicMock) -> None:
        entries = [
            _make_entry(title=f"Article {i}", link=f"https://reuters.com/{i}")
            for i in range(20)
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news("top", count=5)
        assert len(result) == 5

    @patch("fetchers.reuters.feedparser.parse")
    def test_removes_duplicates_before_limiting(self, mock_parse: MagicMock) -> None:
        entries = [
            _make_entry(title="Original", link="https://reuters.com/dup"),
            _make_entry(title="Duplicate", link="https://reuters.com/dup"),
            _make_entry(title="Unique", link="https://reuters.com/unique"),
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news("top", count=10)
        assert len(result) == 2

    @patch("fetchers.reuters.feedparser.parse")
    def test_handles_network_error(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ConnectionError("DNS failure")

        result = fetch_news("top")
        assert result == []

    @patch("fetchers.reuters.feedparser.parse")
    def test_handles_generic_exception(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ValueError("Unexpected data")

        result = fetch_news("top")
        assert result == []

    @patch("fetchers.reuters.feedparser.parse")
    def test_handles_bozo_feed(self, mock_parse: MagicMock) -> None:
        feed = _make_feed(
            [_make_entry(title="Article 1", link="https://reuters.com/a")]
        )
        feed.bozo = 1
        feed.bozo_exception = Exception("Malformed XML")
        mock_parse.return_value = feed

        result = fetch_news("top")
        assert len(result) == 1

    def test_falls_back_for_unknown_category(self) -> None:
        with patch("fetchers.reuters.feedparser.parse") as mock_parse:
            mock_parse.return_value = _make_feed([])
            result = fetch_news("nonexistent")
            mock_parse.assert_called_with(NEWS_FEEDS["top"])
            assert result == []


class TestConvenienceFunctions:
    @patch("fetchers.reuters.fetch_news")
    def test_fetch_top_news_calls_fetch_news(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.return_value = [{"title": "Top Story"}]
        result = fetch_top_news(count=7)
        mock_fetch.assert_called_once_with("top", 7)
        assert result == [{"title": "Top Story"}]

    @patch("fetchers.reuters.fetch_news")
    def test_fetch_business_news_calls_fetch_news(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.return_value = [{"title": "Biz Story"}]
        result = fetch_business_news(count=3)
        mock_fetch.assert_called_once_with("business", 3)
        assert result == [{"title": "Biz Story"}]


class TestFetchAll:
    @patch("fetchers.reuters.fetch_news")
    def test_fetches_from_all_categories(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = [
            [{"link": "https://reuters.com/top-story"}],
            [{"link": "https://reuters.com/biz-story"}],
        ]

        result = fetch_all(count=10)

        assert mock_fetch.call_count == len(NEWS_FEEDS)
        assert len(result) == len(NEWS_FEEDS)

    @patch("fetchers.reuters.fetch_news")
    def test_global_count_limit(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {"link": f"https://reuters.com/{i}"} for i in range(5)
        ]
        result = fetch_all(count=3)
        assert len(result) == 3

    @patch("fetchers.reuters.fetch_news")
    def test_removes_duplicates_across_categories(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.side_effect = [
            [{"link": "https://reuters.com/dup", "title": "From top"}],
            [{"link": "https://reuters.com/dup", "title": "From business"}],
        ]
        result = fetch_all(count=10)
        assert len(result) == 1
        assert result[0]["link"] == "https://reuters.com/dup"
