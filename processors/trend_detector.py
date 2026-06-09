from __future__ import annotations

import json
import logging
from typing import Any

from processors.summarizer import AIProvider, create_provider

logger = logging.getLogger(__name__)

TREND_PROMPT: str = (
    "You are a news trend analyst. Analyze the following sets of articles to detect "
    "the single most prominent recurring theme or trend.\n\n"
    "Today's articles:\n{today_articles}\n\n"
    "Articles from the past 30 days:\n{historical_articles}\n\n"
    "Identify the strongest recurring theme that appears across both time periods.\n"
    'Return a JSON object with exactly three keys:\n'
    '  - "trend": a short, descriptive name for the trend '
    '(e.g. "AI Infrastructure", "Data Centers", "Quick Commerce").\n'
    '  - "evidence": an array of article titles (from either list) '
    "that support this trend. Include 3\u20135 titles.\n"
    '  - "confidence": one of "high", "medium", or "low" '
    "based on how much evidence supports this trend.\n\n"
    "Only return the JSON object, no other text."
)


def _format_articles(articles: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for i, article in enumerate(articles, 1):
        title = article.get("title", "(no title)")
        source = article.get("source", "unknown")
        lines.append(f"{i}. [{source}] {title}")
    return "\n".join(lines)


def _parse_response(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    parsed = json.loads(cleaned)

    evidence = parsed.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = [str(evidence)]

    return {
        "trend": str(parsed.get("trend", "")),
        "evidence": [str(e) for e in evidence],
        "confidence": str(parsed.get("confidence", "")),
    }


def detect_trends(
    today_articles: list[dict[str, str]],
    historical_articles: list[dict[str, str]],
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    if not today_articles and not historical_articles:
        logger.warning("No articles provided for trend detection")
        return {"trend": "", "evidence": [], "confidence": ""}

    provider = provider or create_provider()

    prompt = TREND_PROMPT.format(
        today_articles=_format_articles(today_articles) or "(none)",
        historical_articles=_format_articles(historical_articles) or "(none)",
    )

    try:
        raw = provider.generate(prompt)
        return _parse_response(raw)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("Trend detection parsing failed: %s", exc)
        raise
