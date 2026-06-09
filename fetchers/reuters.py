import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

NEWS_FEEDS: dict[str, str] = {
    "top": "https://feeds.bbci.co.uk/news/rss.xml",
    "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
}

REQUEST_TIMEOUT: int = 15


@dataclass
class NewsArticle:
    title: str = ""
    link: str = ""
    published: str = ""
    category: str = ""
    source: str = "BBC"
    image: str = ""


def _parse_entry(entry: dict[str, Any], category: str) -> dict[str, Any]:
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
            category=category,
            image=image,
        )
    )


def _remove_duplicates(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


def fetch_news(category: str = "top", count: int = 10) -> list[dict[str, Any]]:
    if category not in NEWS_FEEDS:
        logger.warning("Unknown category '%s', falling back to 'top'", category)
        category = "top"

    url = NEWS_FEEDS[category]

    try:
        raw = feedparser.parse(url)
    except requests.RequestException as exc:
        logger.error("Network error fetching BBC %s feed: %s", category, exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error parsing BBC %s feed: %s", category, exc)
        return []

    if raw.bozo and raw.bozo_exception:
        logger.warning("Feed parse warning: %s", raw.bozo_exception)

    articles: list[dict[str, Any]] = []
    for entry in raw.entries:
        articles.append(_parse_entry(entry, category))

    articles = _remove_duplicates(articles)
    return articles[:count]


def fetch_top_news(count: int = 10) -> list[dict[str, Any]]:
    return fetch_news("top", count)


def fetch_business_news(count: int = 10) -> list[dict[str, Any]]:
    return fetch_news("business", count)


def fetch_all(count: int = 10) -> list[dict[str, Any]]:
    per_category = max(count // len(NEWS_FEEDS), 1)
    articles: list[dict[str, Any]] = []
    for cat in NEWS_FEEDS:
        articles.extend(fetch_news(cat, per_category))

    articles = _remove_duplicates(articles)
    return articles[:count]
