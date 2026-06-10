from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
    local_news: list[dict[str, Any]] | None = None,
    global_news: list[dict[str, Any]] | None = None,
    ai_dive: dict[str, Any] | None = None,
    business_dive: dict[str, Any] | None = None,
    mail_date: str | date | None = None,
) -> str:
    template = _get_env().get_template("email.html")

    if isinstance(mail_date, date):
        mail_date = mail_date.isoformat()
    elif mail_date is None:
        mail_date = date.today().isoformat()

    context: dict[str, Any] = {
        "date": mail_date,
        "local_news": local_news or [],
        "global_news": global_news or [],
        "ai_dive": ai_dive or {},
        "business_dive": business_dive or {},
    }

    return template.render(context)
