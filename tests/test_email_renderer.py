from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from processors.email_renderer import build_and_render, render_email


class TestRenderEmail:
    def test_returns_html_string(self) -> None:
        html = render_email()
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_includes_date(self) -> None:
        html = render_email(mail_date="2025-07-15")
        assert "2025-07-15" in html

    def test_includes_article_title(self) -> None:
        html = render_email(
            world_news=[{"title": "Test Story", "source": "Reuters", "link": "https://ex.com"}]
        )
        assert "Test Story" in html
        assert "https://ex.com" in html

    def test_includes_trend(self) -> None:
        html = render_email(
            trend={"trend": "AI Boom", "evidence": ["A", "B"], "confidence": "high"}
        )
        assert "AI Boom" in html

    def test_includes_deep_dive(self) -> None:
        html = render_email(
            deep_dive={
                "headline": "Big Story",
                "reason": "It matters",
                "analysis": ["Point one", "Point two"],
            }
        )
        assert "Big Story" in html
        assert "Point one" in html
        assert "Point two" in html

    def test_shows_empty_state_for_missing_sections(self) -> None:
        html = render_email()
        assert "No articles available" in html
        assert "No trend data available" in html
        assert "No deep dive available" in html

    def test_date_object_formatted(self) -> None:
        html = render_email(mail_date=date(2025, 12, 25))
        assert "2025-12-25" in html


class TestBuildAndRender:
    @patch("processors.email_renderer.aggregate_news")
    @patch("processors.email_renderer.load_last_n_days")
    @patch("processors.email_renderer.detect_trends")
    @patch("processors.email_renderer.select_deep_dive")
    def test_builds_complete_email(
        self,
        mock_deep: MagicMock,
        mock_trend: MagicMock,
        mock_history: MagicMock,
        mock_agg: MagicMock,
    ) -> None:
        mock_agg.return_value = [
            {"title": "World News", "category": "top", "source": "Reuters", "link": "https://ex.com/w"},
            {"title": "Biz News", "category": "business", "source": "Reuters", "link": "https://ex.com/b"},
            {"title": "TC Story", "category": "tech", "source": "TechCrunch", "link": "https://ex.com/t"},
        ]
        mock_history.return_value = [{"title": "Old Story"}]
        mock_trend.return_value = {"trend": "Cloud", "evidence": ["A"], "confidence": "medium"}
        mock_deep.return_value = {"headline": "Deep", "reason": "Why", "analysis": ["Impact"]}

        html = build_and_render()

        assert "World News" in html
        assert "Biz News" in html
        assert "TC Story" in html
        assert "Cloud" in html
        assert "Deep" in html
