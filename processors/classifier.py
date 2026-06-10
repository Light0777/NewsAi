from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

CATEGORY_LOCAL = "LOCAL"
CATEGORY_GLOBAL = "GLOBAL"
CATEGORY_AI = "AI"
CATEGORY_BUSINESS = "BUSINESS"

LOCAL_KEYWORDS = [
    "india", "chennai", "tamil nadu", "bengaluru", "mumbai", "delhi",
    "kolkata", "hyderabad", "ahmedabad", "pune", "indian", "india:",
    "narendra modi", "rahul gandhi", "parliament", "supreme court",
    "bihar", "kerala", "karnataka", "andhra pradesh", "telangana",
    "maharashtra", "gujarat", "uttar pradesh", "rajasthan", "odisha",
    "madras", "bombay", "high court", "eci", "election commission",
    "police", "traffic", "state government", "central government",
    "the hindu", "times of india", "ndtv", "hindustan times",
    "the hindu businessline", "indian express", "india today",
    "timesofindia", "moneycontrol",
]

GLOBAL_KEYWORDS = [
    "world", "international", "global", "war", "conflict", "diplomatic",
    "united nations", "nato", "eu", "european union", "china", "russia",
    "ukraine", "president", "prime minister", "foreign",
    "treaty", "sanction", "military", "defense", "election",
    "climate", "pandemic", "refugee", "border",
    "britain", "europe", "africa", "middle east", "asia-pacific",
    "white house", "kremlin", "beijing", "moscow",
    "bbc", "reuters", "associated press", "ap ",
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "openai", "google ai", "gemini",
    "claude", "anthropic", "meta ai", "llama", "nvidia", "gpu",
    "machine learning", "deep learning", "chatgpt", "gpt-4", "gpt-5",
    "neural", "transformer", "large language model", "llm",
    "ai chip", "ai regulation", "ai safety", "alignment",
    "copilot", "ai assistant", "agentic", "agi", "reasoning model",
    "deepseek", "mistral", "cohere", "ai research",
    "ai model", "foundation model", "open source ai",
    "techcrunch", "wired", "the verge",
]

BUSINESS_KEYWORDS = [
    "stock", "stocks", "market", "ipo", "revenue", "profit", "earnings",
    "startup", "start-up", "economy", "inflation", "gdp", "interest rate",
    "federal reserve", "rbi", "reserve bank", "sensex", "nifty",
    "investment", "investor", "funding", "valuation", "acquisition",
    "merger", "deal", "m&a", "ceo", "cfo", "layoff", "hiring",
    "bank", "banking", "finance", "fintech", "cryptocurrency", "bitcoin",
    "bond", "treasury", "trade", "tariff", "market cap",
    "dow jones", "nasdaq", "s&p 500", "nifty 50", "bse", "nse",
    "sebi", "fii", "dii", "retail investor", "quarterly results",
    "bloomberg", "financial times", "economic times", "moneycontrol",
    "business", "corporate", "enterprise", "small business",
]


def _keyword_score(title: str, keywords: list[str]) -> int:
    title_lower = title.lower()
    score = 0
    for kw in keywords:
        if kw in title_lower:
            score += 1
    return score


SOURCE_CATEGORY_MAP: dict[str, str] = {
    "tech": CATEGORY_AI,
    "business": CATEGORY_BUSINESS,
}


def classify_article(article: dict[str, Any]) -> str:
    title = article.get("title", "")
    source = article.get("source", "")
    feed_category = article.get("category", "")

    mapped = SOURCE_CATEGORY_MAP.get(feed_category)
    if mapped:
        return mapped

    local_score = _keyword_score(title, LOCAL_KEYWORDS)
    global_score = _keyword_score(title, GLOBAL_KEYWORDS)
    ai_score = _keyword_score(title, AI_KEYWORDS)
    business_score = _keyword_score(title, BUSINESS_KEYWORDS)

    scores = {
        CATEGORY_LOCAL: local_score,
        CATEGORY_GLOBAL: global_score,
        CATEGORY_AI: ai_score,
        CATEGORY_BUSINESS: business_score,
    }

    if source in ("The Hindu", "Times of India", "NDTV", "Hindustan Times", "Indian Express"):
        scores[CATEGORY_LOCAL] += 1

    best_category = max(scores, key=scores.get)

    if scores[best_category] == 0:
        best_category = CATEGORY_GLOBAL

    return best_category


def classify_articles(articles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    classified: dict[str, list[dict[str, Any]]] = {
        CATEGORY_LOCAL: [],
        CATEGORY_GLOBAL: [],
        CATEGORY_AI: [],
        CATEGORY_BUSINESS: [],
    }

    for article in articles:
        category = classify_article(article)
        classified[category].append(article)

    logger.info(
        "Classification: %d local, %d global, %d ai, %d business",
        len(classified[CATEGORY_LOCAL]),
        len(classified[CATEGORY_GLOBAL]),
        len(classified[CATEGORY_AI]),
        len(classified[CATEGORY_BUSINESS]),
    )
    return classified
