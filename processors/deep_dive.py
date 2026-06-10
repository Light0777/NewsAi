from __future__ import annotations

import json
import logging
from typing import Any

from processors.summarizer import AIProvider, create_provider

logger = logging.getLogger(__name__)

AI_DEEP_DIVE_PROMPT: str = (
    "You are an AI industry analyst. Provide a deep dive analysis on this article.\n\n"
    "Title: {title}\n"
    "Text: {text}\n\n"
    'Return a JSON object with exactly these keys:\n'
    '  - "title": the original headline\n'
    '  - "what_happened": a 2-3 line explanation of what happened\n'
    '  - "who_is_involved": who is involved (OpenAI, Google, Meta, NVIDIA, Anthropic, etc.)\n'
    '  - "why_it_matters": why this matters in the AI race\n\n'
    "Only return the JSON object, no other text."
)

BUSINESS_DEEP_DIVE_PROMPT: str = (
    "You are a financial analyst. Provide a deep dive analysis on this article.\n\n"
    "Title: {title}\n"
    "Text: {text}\n\n"
    'Return a JSON object with exactly these keys:\n'
    '  - "title": the original headline\n'
    '  - "company_or_trend": the company or macro trend involved\n'
    '  - "financial_implication": the financial or market implication (1-2 sentences)\n'
    '  - "future_impact": what this means going forward (1-2 sentences)\n\n'
    "Only return the JSON object, no other text."
)


def _parse_deep_dive(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    return json.loads(cleaned)


def ai_deep_dive(
    article: dict[str, str],
    text: str,
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    provider = provider or create_provider()
    title = article.get("title", "")
    prompt = AI_DEEP_DIVE_PROMPT.format(title=title, text=text)
    try:
        raw = provider.generate(prompt)
        result = _parse_deep_dive(raw)
        result.setdefault("title", title)
        return result
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("AI deep dive failed for '%s': %s", title, exc)
        return {
            "title": title,
            "what_happened": "Summary unavailable due to API limit",
            "who_is_involved": "",
            "why_it_matters": "",
        }


def business_deep_dive(
    article: dict[str, str],
    text: str,
    provider: AIProvider | None = None,
) -> dict[str, Any]:
    provider = provider or create_provider()
    title = article.get("title", "")
    prompt = BUSINESS_DEEP_DIVE_PROMPT.format(title=title, text=text)
    try:
        raw = provider.generate(prompt)
        result = _parse_deep_dive(raw)
        result.setdefault("title", title)
        return result
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("Business deep dive failed for '%s': %s", title, exc)
        return {
            "title": title,
            "company_or_trend": "Summary unavailable due to API limit",
            "financial_implication": "",
            "future_impact": "",
        }
