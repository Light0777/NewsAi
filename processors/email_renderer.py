from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from processors.deep_dive import select_deep_dive
from processors.news_aggregator import aggregate as aggregate_news
from processors.trend_detector import detect_trends
from storage.history_manager import load_last_n_days

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env: Environment | None = None


def _get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _env


def render_email(
    world_news: list[dict[str, Any]] | None = None,
    business_news: list[dict[str, Any]] | None = None,
    ai_tech: list[dict[str, Any]] | None = None,
    trend: dict[str, Any] | None = None,
    deep_dive: dict[str, Any] | None = None,
    mail_date: str | date | None = None,
) -> str:
    template = _get_env().get_template("email.html")

    if isinstance(mail_date, date):
        mail_date = mail_date.isoformat()
    elif mail_date is None:
        mail_date = date.today().isoformat()

    context: dict[str, Any] = {
        "date": mail_date,
        "world_news": world_news or [],
        "business_news": business_news or [],
        "ai_tech": ai_tech or [],
        "trend": trend or {},
        "deep_dive": deep_dive or {},
    }

    return template.render(context)


def build_and_render(
    trend_provider: Any = None,
    deep_dive_provider: Any = None,
    count: int = 5,
    historical_days: int = 30,
) -> str:
    today_articles = aggregate_news(count)

    world = [a for a in today_articles if a.get("category") == "top"]
    business = [a for a in today_articles if a.get("category") == "business"]
    ai_tech = [a for a in today_articles if a.get("category") == "tech"]

    history = load_last_n_days(historical_days)
    trend = detect_trends(today_articles, history, provider=trend_provider)
    deep_dive = select_deep_dive(today_articles, provider=deep_dive_provider)

    return render_email(
        world_news=world,
        business_news=business,
        ai_tech=ai_tech,
        trend=trend,
        deep_dive=deep_dive,
    )
