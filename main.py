from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date
from typing import Any

import dotenv
import requests
from bs4 import BeautifulSoup

from processors.deep_dive import select_deep_dive
from processors.email_renderer import render_email
from processors.email_sender import create_email_sender
from processors.news_aggregator import aggregate as aggregate_news
from processors.summarizer import AIProvider, create_provider, summarize_article
from processors.trend_detector import detect_trends
from storage.history_manager import save_daily_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("news_ai")


def _fetch_article_text(url: str, timeout: int = 15) -> str:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return text[:5000] if text else ""
    except requests.RequestException as exc:
        logger.warning("Failed to fetch article body from %s: %s", url, exc)
        return ""


def _step(label: str, step_num: int, total: int) -> None:
    logger.info("[%d/%d] %s", step_num, total, label)


def main() -> int:
    dotenv.load_dotenv()
    total_steps = 8

    recipient = os.getenv("EMAIL_RECIPIENT", "")
    if not recipient:
        logger.error("EMAIL_RECIPIENT is not set")
        return 1

    fetcher_count = int(os.getenv("MAX_ARTICLES", "5"))
    historical_days = int(os.getenv("HISTORICAL_DAYS", "30"))

    ai_provider: AIProvider | None = None
    try:
        ai_provider = create_provider()
    except ValueError as exc:
        logger.warning("No AI provider configured: %s — AI features will be skipped", exc)

    today: list[dict[str, Any]] = []
    trend: dict[str, Any] = {}
    deep_dive: dict[str, Any] = {}

    # ---- Step 1-3: Fetch and aggregate ----
    _step("Fetching and aggregating news", 1, total_steps)
    try:
        today = aggregate_news(fetcher_count)
        logger.info("Collected %d articles", len(today))
    except Exception as exc:
        logger.error("News aggregation failed: %s", exc)

    # Fetch OG images for articles that don't have one
    for article in today:
        if not article.get("image") and article.get("link"):
            from bs4 import BeautifulSoup as _bs
            try:
                resp = requests.get(article["link"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                soup = _bs(resp.text, "html.parser")
                og = soup.find("meta", property="og:image")
                if og and og.get("content"):
                    article["image"] = og["content"]
            except Exception:
                pass

    # ---- Step 4: Generate summaries ----
    _step("Generating article summaries", 2, total_steps)
    summaries: list[dict[str, str]] = []
    if ai_provider and today:
        for article in today:
            link = article.get("link", "")
            title = article.get("title", "")
            if not link or not title:
                continue
            text = _fetch_article_text(link)
            if not text:
                continue
            try:
                summary = summarize_article(title, text, provider=ai_provider)
                summary["link"] = link
                summary["title"] = title
                summaries.append(summary)
            except Exception as exc:
                logger.warning("Failed to summarize '%s': %s", title, exc)
            time.sleep(6)

        logger.info("Generated %d summaries", len(summaries))

    # ---- Step 5: Trend analysis ----
    _step("Detecting trends", 3, total_steps)
    try:
        if today:
            time.sleep(2)
            from storage.history_manager import load_last_n_days as _load_n_days

            history = _load_n_days(historical_days)
            trend = detect_trends(today, history, provider=ai_provider)
            logger.info("Trend detected: %s", trend.get("trend", "(none)"))
    except (ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        logger.warning("Trend detection skipped: %s", exc)

    # ---- Step 6: Deep dive ----
    _step("Selecting deep dive story", 4, total_steps)
    try:
        if today:
            time.sleep(2)
            deep_dive = select_deep_dive(today, provider=ai_provider)
            logger.info("Deep dive: %s", deep_dive.get("headline", "(none)"))
    except (ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        logger.warning("Deep dive skipped: %s", exc)

    # ---- Step 7: Save history ----
    _step("Saving history", 5, total_steps)
    try:
        if today:
            path = save_daily_news(today)
            logger.info("History saved to %s", path)
    except Exception as exc:
        logger.warning("Failed to save history: %s", exc)

    # ---- Step 8: Render email ----
    _step("Rendering email", 6, total_steps)
    html: str = ""
    try:
        world = [a for a in today if a.get("category") == "top"]
        business = [a for a in today if a.get("category") == "business"]
        ai_tech = [a for a in today if a.get("category") == "tech"]

        html = render_email(
            world_news=world,
            business_news=business,
            ai_tech=ai_tech,
            trend=trend,
            deep_dive=deep_dive,
            mail_date=date.today(),
        )
        logger.info("Email rendered (%d characters)", len(html))
    except Exception as exc:
        logger.error("Email rendering failed: %s", exc)
        return 1

    # ---- Step 9: Send email ----
    _step("Sending email", 7, total_steps)
    try:
        sender = create_email_sender()
        result = sender.send_email(
            recipient=recipient,
            subject=f"Morning News Intelligence — {date.today().isoformat()}",
            html_content=html,
        )
        logger.info("Email sent via %s to %s", result.get("provider"), recipient)
    except Exception as exc:
        logger.error("Email delivery failed: %s", exc)
        return 1

    _step("Done", 8, total_steps)
    return 0


if __name__ == "__main__":
    sys.exit(main())
