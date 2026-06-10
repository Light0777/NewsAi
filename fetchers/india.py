from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

INDIAN_FEEDS: dict[str, dict[str, str]] = {
    "the_hindu": {
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "source": "The Hindu",
    },
    "times_of_india": {
        "url": "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
        "source": "Times of India",
    },
    "ndtv": {
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "source": "NDTV",
    },
}

REQUEST_TIMEOUT: int = 15


@dataclass
class NewsArticle:
    title: str = ""
    link: str = ""
    published: str = ""
    category: str = ""
    source: str = ""
    image: str = ""


def _parse_entry(entry: dict[str, Any], source_name: str) -> dict[str, Any]:
    published = entry.get("published", "")
    if not published:
        published = entry.get("updated", "")

    image = ""
    thumbnails = entry.get("media_thumbnail", [])
    if thumbnails and isinstance(thumbnails, list):
        image = thumbnails[0].get("url", "")

    return asdict(
        NewsArticle(
            title=entry.get("title", ""),
            link=entry.get("link", ""),
            published=published,
            category="india",
            source=source_name,
            image=image,
        )
    )


def _remove_duplicates(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for article in articles:
        key = article.get("link", "")
        if not key:
            deduplicated.append(article)
        elif key not in seen:
            seen.add(key)
            deduplicated.append(article)
    return deduplicated


def fetch_news(count: int = 10) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []

    for feed_key, feed_info in INDIAN_FEEDS.items():
        url = feed_info["url"]
        source_name = feed_info["source"]
        try:
            raw = feedparser.parse(url)
        except requests.RequestException as exc:
            logger.error("Network error fetching %s feed: %s", feed_key, exc)
            continue
        except Exception as exc:
            logger.error("Unexpected error parsing %s feed: %s", feed_key, exc)
            continue

        if raw.bozo and raw.bozo_exception:
            logger.warning("Feed parse warning for %s: %s", feed_key, raw.bozo_exception)

        for entry in raw.entries:
            articles.append(_parse_entry(entry, source_name))

    articles = _remove_duplicates(articles)
    return articles[:count]
