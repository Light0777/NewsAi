from __future__ import annotations

import logging
import os
import sys
from datetime import date
from typing import Any

import dotenv
import requests

from processors.classifier import classify_articles
from processors.deep_dive import ai_deep_dive, business_deep_dive
from processors.email_renderer import render_email
from processors.email_sender import create_email_sender
from processors.news_aggregator import aggregate as aggregate_news
from processors.selector import select_top_articles
from processors.summarizer import AIProvider, batch_summarize_articles, create_provider
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
        from bs4 import BeautifulSoup
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
    total_steps = 7

    recipient = os.getenv("EMAIL_RECIPIENT", "")
    if not recipient:
        logger.error("EMAIL_RECIPIENT is not set")
        return 1

    fetcher_count = int(os.getenv("MAX_ARTICLES", "10"))

    ai_provider: AIProvider | None = None
    try:
        ai_provider = create_provider()
    except ValueError as exc:
        logger.warning("No AI provider configured: %s — AI features will be skipped", exc)

    # ---- Step 1: Fetch Layer (NO AI) ----
    _step("Fetching raw articles from all sources", 1, total_steps)
    all_articles: list[dict[str, Any]] = []
    try:
        all_articles = aggregate_news(fetcher_count)
        logger.info("Collected %d raw articles", len(all_articles))
    except Exception as exc:
        logger.error("News aggregation failed: %s", exc)

    if not all_articles:
        logger.error("No articles fetched — aborting")
        return 1

    # ---- Step 2: Classification (keyword-based, NO AI) ----
    _step("Classifying articles by category", 2, total_steps)
    classified = classify_articles(all_articles)

    # ---- Step 3: Selection (strict limits: 2 local, 2 global, 1 AI, 1 business) ----
    _step("Selecting top articles (2 local, 2 global, 1 AI, 1 business)", 3, total_steps)
    selected = select_top_articles(classified)
    total_selected = sum(len(v) for v in selected.values())
    logger.info("Selected %d articles total for summarization", total_selected)

    # ---- Step 4: Summarization + Deep Dives (with throttling) ----
    _step("Summarizing articles with AI (throttled, 1.5s between calls)", 4, total_steps)

    local_items: list[dict[str, Any]] = []
    global_items: list[dict[str, Any]] = []
    ai_dive: dict[str, Any] = {}
    business_dive: dict[str, Any] = {}

    def _build_batch(articles: list[dict[str, Any]]) -> list[dict[str, str]]:
        batch: list[dict[str, str]] = []
        for a in articles:
            text = _fetch_article_text(a.get("link", ""))
            batch.append({"title": a.get("title", ""), "text": text, "link": a.get("link", ""), "source": a.get("source", "")})
        return batch

    if ai_provider:
        # --- Batch summarize 2 LOCAL articles (1 call) ---
        local_articles = selected.get("LOCAL", [])
        if local_articles:
            batch = _build_batch(local_articles)
            try:
                results = batch_summarize_articles(batch, provider=ai_provider)
                for i, r in enumerate(results):
                    r["link"] = batch[i].get("link", "")
                    r["source"] = batch[i].get("source", "")
                    local_items.append(r)
            except Exception as exc:
                logger.warning("Local batch summarization failed: %s", exc)
                for a in local_articles:
                    local_items.append({
                        "title": a.get("title", ""),
                        "summary": "Summary unavailable due to API limit",
                        "why_it_matters": "",
                        "link": a.get("link", ""),
                        "source": a.get("source", ""),
                    })

        # --- Batch summarize 2 GLOBAL articles (1 call) ---
        global_articles = selected.get("GLOBAL", [])
        if global_articles:
            batch = _build_batch(global_articles)
            try:
                results = batch_summarize_articles(batch, provider=ai_provider)
                for i, r in enumerate(results):
                    r["link"] = batch[i].get("link", "")
                    r["source"] = batch[i].get("source", "")
                    global_items.append(r)
            except Exception as exc:
                logger.warning("Global batch summarization failed: %s", exc)
                for a in global_articles:
                    global_items.append({
                        "title": a.get("title", ""),
                        "summary": "Summary unavailable due to API limit",
                        "why_it_matters": "",
                        "link": a.get("link", ""),
                        "source": a.get("source", ""),
                    })

        # --- AI Deep Dive (1 call) ---
        ai_articles = selected.get("AI", [])
        if ai_articles:
            article = ai_articles[0]
            text = _fetch_article_text(article.get("link", ""))
            try:
                ai_dive = ai_deep_dive(article, text, provider=ai_provider)
                ai_dive["link"] = article.get("link", "")
                ai_dive["source"] = article.get("source", "")
            except Exception as exc:
                logger.warning("AI deep dive failed: %s", exc)
                ai_dive = {
                    "title": article.get("title", ""),
                    "what_happened": "Summary unavailable due to API limit",
                    "who_is_involved": "",
                    "why_it_matters": "",
                    "link": article.get("link", ""),
                    "source": article.get("source", ""),
                }

        # --- Business Deep Dive (1 call) ---
        business_articles = selected.get("BUSINESS", [])
        if business_articles:
            article = business_articles[0]
            text = _fetch_article_text(article.get("link", ""))
            try:
                business_dive = business_deep_dive(article, text, provider=ai_provider)
                business_dive["link"] = article.get("link", "")
                business_dive["source"] = article.get("source", "")
            except Exception as exc:
                logger.warning("Business deep dive failed: %s", exc)
                business_dive = {
                    "title": article.get("title", ""),
                    "company_or_trend": "Summary unavailable due to API limit",
                    "financial_implication": "",
                    "future_impact": "",
                    "link": article.get("link", ""),
                    "source": article.get("source", ""),
                }
    else:
        # No AI provider: raw headlines fallback
        for a in selected.get("LOCAL", []):
            local_items.append({
                "title": a.get("title", ""),
                "summary": "Summary unavailable due to API limit",
                "why_it_matters": "",
                "link": a.get("link", ""),
                "source": a.get("source", ""),
            })
        for a in selected.get("GLOBAL", []):
            global_items.append({
                "title": a.get("title", ""),
                "summary": "Summary unavailable due to API limit",
                "why_it_matters": "",
                "link": a.get("link", ""),
                "source": a.get("source", ""),
            })
        if selected.get("AI"):
            a = selected["AI"][0]
            ai_dive = {"title": a.get("title", ""), "what_happened": "Summary unavailable due to API limit", "who_is_involved": "", "why_it_matters": "", "link": a.get("link", ""), "source": a.get("source", "")}
        if selected.get("BUSINESS"):
            a = selected["BUSINESS"][0]
            business_dive = {"title": a.get("title", ""), "company_or_trend": "Summary unavailable due to API limit", "financial_implication": "", "future_impact": "", "link": a.get("link", ""), "source": a.get("source", "")}

    logger.info("Summarized: %d local, %d global, AI dive=%s, Business dive=%s",
                len(local_items), len(global_items),
                "yes" if ai_dive else "no",
                "yes" if business_dive else "no")

    # ---- Step 5: Save history ----
    _step("Saving history", 5, total_steps)
    try:
        if all_articles:
            path = save_daily_news(all_articles)
            logger.info("History saved to %s", path)
    except Exception as exc:
        logger.warning("Failed to save history: %s", exc)

    # ---- Step 6: Render email ----
    _step("Rendering email", 6, total_steps)
    html: str = ""
    try:
        html = render_email(
            local_news=local_items,
            global_news=global_items,
            ai_dive=ai_dive,
            business_dive=business_dive,
            mail_date=date.today(),
        )
        logger.info("Email rendered (%d characters)", len(html))
    except Exception as exc:
        logger.error("Email rendering failed: %s", exc)
        return 1

    # ---- Step 7: Send email ----
    _step("Sending email", 7, total_steps)
    try:
        sender = create_email_sender()
        result = sender.send_email(
            recipient=recipient,
            subject=f"Daily News Intelligence \u2014 {date.today().isoformat()}",
            html_content=html,
        )
        logger.info("Email sent via %s to %s", result.get("provider"), recipient)
    except Exception as exc:
        logger.error("Email delivery failed: %s", exc)
        return 1

    logger.info("Pipeline complete: 6 curated items, %d Gemini calls", 4 if ai_provider else 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
