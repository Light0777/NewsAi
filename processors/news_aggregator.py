from typing import Any

from fetchers.reuters import fetch_business_news, fetch_top_news
from fetchers.techcrunch import fetch_news as fetch_techcrunch_news

PER_SOURCE: int = 3
OUTPUT_FIELDS = ("title", "source", "category", "link", "image")


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


def _project(article: dict[str, Any]) -> dict[str, str]:
    return {field: article.get(field, "") for field in OUTPUT_FIELDS}


def aggregate(count: int = PER_SOURCE) -> list[dict[str, str]]:
    reuters_top = fetch_top_news(count)
    reuters_biz = fetch_business_news(count)
    techcrunch = fetch_techcrunch_news(count)

    combined = reuters_top + reuters_biz + techcrunch
    combined = _deduplicate(combined)
    return [_project(a) for a in combined]
