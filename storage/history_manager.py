from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).resolve().parent / "history"

_DATE_FORMAT = "%Y-%m-%d"


def _resolve_history_dir() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR


def _to_date(d: str | date) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, _DATE_FORMAT).date()


def _file_path(d: str | date) -> Path:
    day = _to_date(d)
    return _resolve_history_dir() / f"{day.strftime(_DATE_FORMAT)}.json"


def save_daily_news(
    articles: list[dict[str, Any]],
    day: str | date | None = None,
) -> str:
    day = day or date.today()
    path = _file_path(day)
    data = {"date": _to_date(day).strftime(_DATE_FORMAT), "articles": articles}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved %d articles to %s", len(articles), path)
    return str(path)


def load_daily_news(day: str | date) -> list[dict[str, Any]]:
    path = _file_path(day)
    if not path.exists():
        logger.warning("No history file found for %s", _to_date(day))
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("articles", [])
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Failed to load %s: %s", path, exc)
        return []


def load_last_n_days(
    n: int,
    reference_date: str | date | None = None,
) -> list[dict[str, Any]]:
    if n < 1:
        return []

    ref = _to_date(reference_date) if reference_date else date.today()
    articles: list[dict[str, Any]] = []
    for offset in range(n):
        day = ref - timedelta(days=offset)
        articles.extend(load_daily_news(day))
    return articles
