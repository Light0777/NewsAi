from __future__ import annotations

import json
import logging
from typing import Any

from processors.summarizer import AIProvider, create_provider

logger = logging.getLogger(__name__)

DEEP_DIVE_PROMPT: str = (
    "You are a senior financial analyst. Below is today's collection of news articles.\n\n"
    "{articles}\n\n"
    "Select the single most important story from the list above.\n"
    'Return a JSON object with exactly three keys:\n'
    '  - "headline": the full headline of the chosen article.\n'
    '  - "reason": one concise sentence explaining why this story was chosen over the others.\n'
    '  - "analysis": an array of exactly three strings covering:\n'
    '      1. Business impact — how this affects companies, industries, or operations.\n'
    '      2. Market impact — how this influences financial markets, investors, or valuations.\n'
    '      3. Future implications — what this means going forward (regulation, trends, geopolitics).\n\n'
    "Each analysis point should be 1–2 sentences."
)


def _format_articles(articles: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for i, article in enumerate(articles, 1):
        title = article.get("title", "(no title)")
        source = article.get("source", "unknown")
        category = article.get("category", "")
        lines.append(f"{i}. [{source}] {title}  [{category}]")
    return "\n".join(lines)


def _parse_response(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    parsed = json.loads(cleaned)

    analysis = parsed.get("analysis", [])
    if not isinstance(analysis, list):
        analysis = [str(analysis)]

    return {
        "headline": str(parsed.get("headline", "")),
        "reason": str(parsed.get("reason", "")),
        "analysis": [str(p) for p in analysis],
    }


def select_deep_dive(
    articles: list[dict[str, str]],
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    if not articles:
        raise ValueError("At least one article is required for deep dive selection")

    provider = provider or create_provider()
    formatted = _format_articles(articles)
    prompt = DEEP_DIVE_PROMPT.format(articles=formatted)

    try:
        raw = provider.generate(prompt)
        return _parse_response(raw)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("Deep dive parsing failed: %s", exc)
        raise
