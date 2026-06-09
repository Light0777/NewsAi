from typing import Any
from unittest.mock import MagicMock, patch

from fetchers.techcrunch import (
    TECHCRUNCH_FEED,
    _parse_entry,
    _remove_duplicates,
    fetch_news,
)


def _make_entry(
    title: str = "Test Title",
    link: str = "https://techcrunch.com/article/test",
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
        result = _parse_entry(_make_entry(), "tech")
        assert result["title"] == "Test Title"

    def test_parses_link(self) -> None:
        result = _parse_entry(
            _make_entry(link="https://techcrunch.com/story"), "tech"
        )
        assert result["link"] == "https://techcrunch.com/story"

    def test_parses_published(self) -> None:
        result = _parse_entry(
            _make_entry(published="Mon, 15 Mar 2025 08:30:00 +0000"), "tech"
        )
        assert result["published"] == "Mon, 15 Mar 2025 08:30:00 +0000"

    def test_falls_back_to_updated_when_published_missing(self) -> None:
        entry: dict[str, Any] = {
            "title": "No published date",
            "link": "https://techcrunch.com/article/test2",
            "updated": "Wed, 20 Mar 2025 10:00:00 GMT",
        }
        result = _parse_entry(entry, "tech")
        assert result["published"] == "Wed, 20 Mar 2025 10:00:00 GMT"

    def test_parses_source(self) -> None:
        result = _parse_entry(_make_entry(), "tech")
        assert result["source"] == "TechCrunch"

    def test_parses_category(self) -> None:
        result = _parse_entry(_make_entry(), "tech")
        assert result["category"] == "tech"

    def test_handles_empty_entry(self) -> None:
        result = _parse_entry({}, "tech")
        assert result == {
            "title": "",
            "link": "",
            "published": "",
            "category": "tech",
            "source": "TechCrunch",
            "image": "",
        }


class TestRemoveDuplicates:
    def test_removes_duplicate_links(self) -> None:
        articles = [
            {"link": "https://techcrunch.com/a", "title": "A"},
            {"link": "https://techcrunch.com/b", "title": "B"},
            {"link": "https://techcrunch.com/a", "title": "A duplicate"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 2

    def test_keeps_all_unique(self) -> None:
        articles = [
            {"link": "https://techcrunch.com/1"},
            {"link": "https://techcrunch.com/2"},
            {"link": "https://techcrunch.com/3"},
        ]
        assert len(_remove_duplicates(articles)) == 3

    def test_skips_empty_link(self) -> None:
        articles = [
            {"link": "", "title": "No link"},
            {"link": "https://techcrunch.com/a", "title": "A"},
            {"link": "", "title": "Another no link"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 3

    def test_returns_empty_list_for_empty_input(self) -> None:
        assert _remove_duplicates([]) == []

    def test_skips_missing_link_key(self) -> None:
        articles = [
            {"title": "Missing link key"},
            {"link": "https://techcrunch.com/a", "title": "A"},
        ]
        result = _remove_duplicates(articles)
        assert len(result) == 2


class TestFetchNews:
    @patch("fetchers.techcrunch.feedparser.parse")
    def test_returns_articles(self, mock_parse: MagicMock) -> None:
        entries = [
            _make_entry(title="Article 1", link="https://techcrunch.com/a"),
            _make_entry(title="Article 2", link="https://techcrunch.com/b"),
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news(count=10)
        assert len(result) == 2
        assert result[0]["title"] == "Article 1"
        assert result[1]["source"] == "TechCrunch"

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_uses_correct_feed_url(self, mock_parse: MagicMock) -> None:
        mock_parse.return_value = _make_feed([])
        fetch_news()
        mock_parse.assert_called_once_with(TECHCRUNCH_FEED)

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_limits_by_count(self, mock_parse: MagicMock) -> None:
        entries = [
            _make_entry(
                title=f"Article {i}", link=f"https://techcrunch.com/{i}"
            )
            for i in range(20)
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news(count=5)
        assert len(result) == 5

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_removes_duplicates_before_limiting(
        self, mock_parse: MagicMock
    ) -> None:
        entries = [
            _make_entry(title="Original", link="https://techcrunch.com/dup"),
            _make_entry(title="Duplicate", link="https://techcrunch.com/dup"),
            _make_entry(title="Unique", link="https://techcrunch.com/unique"),
        ]
        mock_parse.return_value = _make_feed(entries)

        result = fetch_news(count=10)
        assert len(result) == 2

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_handles_network_error(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ConnectionError("DNS failure")

        result = fetch_news()
        assert result == []

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_handles_generic_exception(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ValueError("Unexpected data")

        result = fetch_news()
        assert result == []

    @patch("fetchers.techcrunch.feedparser.parse")
    def test_handles_bozo_feed(self, mock_parse: MagicMock) -> None:
        feed = _make_feed(
            [_make_entry(title="Article 1", link="https://techcrunch.com/a")]
        )
        feed.bozo = 1
        feed.bozo_exception = Exception("Malformed XML")
        mock_parse.return_value = feed

        result = fetch_news()
        assert len(result) == 1
