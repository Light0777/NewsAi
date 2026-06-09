from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import requests

from processors.retry import RetryConfig, reset_call_counter, retry_request

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE: str = (
    "Summarize the following news article.\n\n"
    'Return a JSON object with exactly two keys:\n'
    '  - "summary": a 2-to-3 sentence summary of the article.\n'
    '  - "why_it_matters": a single concise sentence explaining why this story is important.\n\n'
    "---\nTitle: {title}\n\n{text}\n---"
)


class AIProvider(ABC):
    @abstractmethod
    def summarize(self, title: str, text: str) -> dict[str, str]:
        """Summarize an article and return {"summary": str, "why_it_matters": str}."""
        ...

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Send a raw prompt to the model and return the text response."""
        ...

class OpenAIProvider(AIProvider):
    API_BASE: ClassVar[str] = "https://api.openai.com/v1"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider")
        self.model = model
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        self._retry_config = RetryConfig()

    def _request(self, payload: dict[str, Any]) -> requests.Response:
        def _do() -> requests.Response:
            return self._session.post(
                f"{self.API_BASE}/chat/completions",
                json=payload,
                timeout=self._retry_config.timeout,
            )
        return retry_request(_do, "OpenAI", self._retry_config)

    def summarize(self, title: str, text: str) -> dict[str, str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT_TEMPLATE.format(title=title, text=text),
                }
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Unexpected OpenAI response format: %s", exc)
            raise ValueError(f"Failed to parse OpenAI response: {exc}") from exc

    def generate(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500,
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected OpenAI response format: %s", exc)
            raise ValueError(f"Failed to parse OpenAI response: {exc}") from exc

    @staticmethod
    def _parse_response(content: str) -> dict[str, str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        parsed = json.loads(cleaned)
        return {
            "summary": str(parsed.get("summary", "")),
            "why_it_matters": str(parsed.get("why_it_matters", "")),
        }

class GeminiProvider(AIProvider):
    API_BASE: ClassVar[str] = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiProvider")
        self.model = model
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._retry_config = RetryConfig()

    def _request(self, payload: dict[str, Any]) -> requests.Response:
        def _do() -> requests.Response:
            return self._session.post(
                f"{self.API_BASE}/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json=payload,
                timeout=self._retry_config.timeout,
            )
        return retry_request(_do, "Gemini", self._retry_config)

    def summarize(self, title: str, text: str) -> dict[str, str]:
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [
                        {"text": PROMPT_TEMPLATE.format(title=title, text=text)}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 300,
            },
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_response(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Unexpected Gemini response format: %s", exc)
            raise ValueError(f"Failed to parse Gemini response: {exc}") from exc

    def generate(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 500,
            },
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected Gemini response format: %s", exc)
            raise ValueError(f"Failed to parse Gemini response: {exc}") from exc

    @staticmethod
    def _parse_response(content: str) -> dict[str, str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        parsed = json.loads(cleaned)
        return {
            "summary": str(parsed.get("summary", "")),
            "why_it_matters": str(parsed.get("why_it_matters", "")),
        }


class OpenRouterProvider(AIProvider):
    API_BASE: ClassVar[str] = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-4o-mini") -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterProvider")
        self.model = model
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        self._retry_config = RetryConfig()

    def _request(self, payload: dict[str, Any]) -> requests.Response:
        def _do() -> requests.Response:
            return self._session.post(
                f"{self.API_BASE}/chat/completions",
                json=payload,
                timeout=self._retry_config.timeout,
            )
        return retry_request(_do, "OpenRouter", self._retry_config)

    def summarize(self, title: str, text: str) -> dict[str, str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT_TEMPLATE.format(title=title, text=text),
                }
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_response(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Unexpected OpenRouter response format: %s", exc)
            raise ValueError(f"Failed to parse OpenRouter response: {exc}") from exc

    def generate(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500,
        }

        try:
            resp = self._request(payload)
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected OpenRouter response format: %s", exc)
            raise ValueError(f"Failed to parse OpenRouter response: {exc}") from exc

    @staticmethod
    def _parse_response(content: str) -> dict[str, str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()

        parsed = json.loads(cleaned)
        return {
            "summary": str(parsed.get("summary", "")),
            "why_it_matters": str(parsed.get("why_it_matters", "")),
        }


PROVIDER_MAP: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}


def create_provider(name: str | None = None) -> AIProvider:
    reset_call_counter()
    name = (name or os.getenv("AI_PROVIDER", "openai")).strip().lower()
    provider_cls = PROVIDER_MAP.get(name)
    if not provider_cls:
        available = ", ".join(PROVIDER_MAP)
        raise ValueError(
            f"Unknown provider '{name}'. Available: {available}"
        )
    return provider_cls()


def summarize_article(
    title: str,
    text: str,
    provider: AIProvider | None = None,
) -> dict[str, str]:
    provider = provider or create_provider()
    return provider.summarize(title, text)
