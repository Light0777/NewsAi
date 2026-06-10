from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

SOURCE_CREDIBILITY: dict[str, int] = {
    "BBC": 10,
    "Reuters": 10,
    "Associated Press": 10,
    "The Hindu": 8,
    "Times of India": 7,
    "NDTV": 7,
    "Hindustan Times": 7,
    "TechCrunch": 8,
    "Wired": 8,
    "The Verge": 6,
    "Indian Express": 7,
    "Bloomberg": 9,
    "Financial Times": 9,
    "Economic Times": 7,
    "Moneycontrol": 6,
}

SELECTION_LIMITS: dict[str, int] = {
    "LOCAL": 2,
    "GLOBAL": 2,
    "AI": 1,
    "BUSINESS": 1,
}


def _parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.min
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return datetime.min


def _recency_score(date_str: str) -> float:
    pub_date = _parse_date(date_str)
    if pub_date == datetime.min:
        return 0.5
    now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
    age_hours = (now - pub_date).total_seconds() / 3600
    if age_hours < 6:
        return 1.0
    if age_hours < 24:
        return 0.8
    if age_hours < 48:
        return 0.5
    return 0.2


def _credibility_score(source: str) -> float:
    return SOURCE_CREDIBILITY.get(source, 5) / 10.0


def _rank_article(article: dict[str, Any]) -> float:
    recency = _recency_score(article.get("published", ""))
    credibility = _credibility_score(article.get("source", ""))
    return recency * 0.5 + credibility * 0.5


def select_top_articles(
    classified: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    selected: dict[str, list[dict[str, Any]]] = {}

    for category, limit in SELECTION_LIMITS.items():
        articles = classified.get(category, [])
        ranked = sorted(articles, key=_rank_article, reverse=True)
        chosen = ranked[:limit]
        selected[category] = chosen
        logger.info("Selected %d/%d for %s", len(chosen), limit, category)

    return selected
