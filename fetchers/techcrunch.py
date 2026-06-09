import logging
from dataclasses import dataclass, asdict
from typing import Any

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TECHCRUNCH_FEED: str = "https://techcrunch.com/feed/"

REQUEST_TIMEOUT: int = 15


@dataclass
class NewsArticle:
    title: str = ""
    link: str = ""
    published: str = ""
    category: str = ""
    source: str = "TechCrunch"
    image: str = ""


def _fetch_og_image(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        twitter = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter and twitter.get("content"):
            return twitter["content"]
    except Exception:
        pass
    return ""


def _parse_entry(entry: dict[str, Any], category: str) -> dict[str, Any]:
    published = entry.get("published", "")
    if not published:
        published = entry.get("updated", "")

    image = ""
    media = entry.get("media_content", [])
    if media and isinstance(media, list):
        image = media[0].get("url", "")
    if not image:
        thumbnails = entry.get("media_thumbnail", [])
        if thumbnails and isinstance(thumbnails, list):
            image = thumbnails[0].get("url", "")

    result = asdict(
        NewsArticle(
            title=entry.get("title", ""),
            link=entry.get("link", ""),
            published=published,
            category=category,
            image=image,
        )
    )
    return result


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


def fetch_news(count: int = 10) -> list[dict[str, Any]]:
    try:
        raw = feedparser.parse(TECHCRUNCH_FEED)
    except requests.RequestException as exc:
        logger.error("Network error fetching TechCrunch feed: %s", exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error parsing TechCrunch feed: %s", exc)
        return []

    if raw.bozo and raw.bozo_exception:
        logger.warning("Feed parse warning: %s", raw.bozo_exception)

    articles: list[dict[str, Any]] = []
    for entry in raw.entries:
        articles.append(_parse_entry(entry, "tech"))

    articles = _remove_duplicates(articles)
    return articles[:count]
