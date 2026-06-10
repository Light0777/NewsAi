from __future__ import annotations

import logging
from typing import Any

from fetchers.india import fetch_news as fetch_india_news
from fetchers.reuters import fetch_business_news, fetch_top_news
from fetchers.techcrunch import fetch_news as fetch_techcrunch_news

logger = logging.getLogger(__name__)

PER_SOURCE: int = 10

OUTPUT_FIELDS = ("title", "source", "category", "link", "image", "published")


def _deduplicate(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def aggregate(count: int = PER_SOURCE) -> list[dict[str, Any]]:
    reuters_top = fetch_top_news(count)
    reuters_biz = fetch_business_news(count)
    techcrunch = fetch_techcrunch_news(count)
    india = fetch_india_news(count)

    combined = reuters_top + reuters_biz + techcrunch + india
    combined = _deduplicate(combined)
    logger.info("Aggregated %d raw articles total", len(combined))
    return combined
