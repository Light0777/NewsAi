from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from processors.trend_detector import (
    _format_articles,
    _parse_response,
    detect_trends,
)


def _article(title: str = "Story", source: str = "Reuters") -> dict[str, str]:
    return {"title": title, "source": source}


class TestFormatArticles:
    def test_formats_single_article(self) -> None:
        result = _format_articles([_article(title="Test", source="BBC")])
        assert result == "1. [BBC] Test"

    def test_formats_multiple_articles(self) -> None:
        articles = [
            _article(title="A", source="Reuters"),
            _article(title="B", source="TechCrunch"),
        ]
        result = _format_articles(articles)
        assert result == "1. [Reuters] A\n2. [TechCrunch] B"

    def test_handles_empty_list(self) -> None:
        assert _format_articles([]) == ""

    def test_handles_missing_fields(self) -> None:
        result = _format_articles([{"title": "Only Title"}])
        assert result == "1. [unknown] Only Title"

        result = _format_articles([{"source": "Only Source"}])
        assert result == "1. [Only Source] (no title)"


class TestParseResponse:
    def test_parses_valid_json(self) -> None:
        raw = '{"trend": "AI", "evidence": ["Article A"], "confidence": "high"}'
        result = _parse_response(raw)
        assert result == {
            "trend": "AI",
            "evidence": ["Article A"],
            "confidence": "high",
        }

    def test_strips_markdown_fences(self) -> None:
        raw = '```json\n{"trend": "Data Centers", "evidence": ["X", "Y"], "confidence": "medium"}\n```'
        result = _parse_response(raw)
        assert result["trend"] == "Data Centers"
        assert result["evidence"] == ["X", "Y"]

    def test_wraps_non_list_evidence(self) -> None:
        raw = '{"trend": "Cloud", "evidence": "Single article", "confidence": "low"}'
        result = _parse_response(raw)
        assert result["evidence"] == ["Single article"]

    def test_handles_empty_values(self) -> None:
        result = _parse_response('{"trend": "", "evidence": [], "confidence": ""}')
        assert result == {"trend": "", "evidence": [], "confidence": ""}


class TestDetectTrends:
    @patch("processors.trend_detector.create_provider")
    def test_returns_empty_for_no_input(self, mock_factory: MagicMock) -> None:
        mock_factory.assert_not_called()
        result = detect_trends([], [])
        assert result == {"trend": "", "evidence": [], "confidence": ""}

    @patch("processors.trend_detector.create_provider")
    def test_returns_empty_for_no_today(self, mock_factory: MagicMock) -> None:
        result = detect_trends([], [])
        assert result == {"trend": "", "evidence": [], "confidence": ""}

    @patch("processors.trend_detector.create_provider")
    def test_calls_provider_with_prompt(
        self, mock_factory: MagicMock
    ) -> None:
        mock_provider = MagicMock()
        mock_provider.generate.return_value = (
            '{"trend": "AI", "evidence": ["A"], "confidence": "high"}'
        )
        mock_factory.return_value = mock_provider

        today = [_article(title="AI chip boom")]
        history = [_article(title="Nvidia earnings"), _article(title="Data center spend")]
        result = detect_trends(today, history, provider=mock_provider)

        mock_provider.generate.assert_called_once()
        prompt = mock_provider.generate.call_args[0][0]
        assert "[Reuters] AI chip boom" in prompt
        assert "[Reuters] Nvidia earnings" in prompt
        assert "[Reuters] Data center spend" in prompt
        assert result == {"trend": "AI", "evidence": ["A"], "confidence": "high"}

    @patch("processors.trend_detector.create_provider")
    def test_handles_provider_error(
        self, mock_factory: MagicMock
    ) -> None:
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = ValueError("API error")
        mock_factory.return_value = mock_provider

        with pytest.raises(ValueError, match="API error"):
            detect_trends(
                [_article(title="X")],
                [_article(title="Y")],
                provider=mock_provider,
            )
