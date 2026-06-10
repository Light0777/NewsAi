from __future__ import annotations

from datetime import date

from processors.email_renderer import render_email


class TestRenderEmail:
    def test_returns_html_string(self) -> None:
        html = render_email()
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")

    def test_includes_date(self) -> None:
        html = render_email(mail_date="2025-07-15")
        assert "2025-07-15" in html

    def test_includes_local_article(self) -> None:
        html = render_email(
            local_news=[{"title": "Local Story", "summary": "Details", "why_it_matters": "Important", "source": "The Hindu", "link": "https://ex.com"}]
        )
        assert "Local Story" in html
        assert "Details" in html
        assert "Important" in html
        assert "https://ex.com" in html

    def test_includes_global_article(self) -> None:
        html = render_email(
            global_news=[{"title": "Global Story", "summary": "Details", "why_it_matters": "Important", "source": "BBC", "link": "https://ex.com"}]
        )
        assert "Global Story" in html

    def test_includes_ai_deep_dive(self) -> None:
        html = render_email(
            ai_dive={
                "title": "AI Breakthrough",
                "what_happened": "New model released",
                "who_is_involved": "OpenAI",
                "why_it_matters": "Changes AI race",
            }
        )
        assert "AI Breakthrough" in html
        assert "New model released" in html
        assert "OpenAI" in html
        assert "Changes AI race" in html

    def test_includes_business_deep_dive(self) -> None:
        html = render_email(
            business_dive={
                "title": "Market Rally",
                "company_or_trend": "S&P 500 up",
                "financial_implication": "Investors bullish",
                "future_impact": "Continued growth expected",
            }
        )
        assert "Market Rally" in html
        assert "S&amp;P 500 up" in html
        assert "Investors bullish" in html
        assert "Continued growth expected" in html

    def test_shows_empty_state_for_missing_sections(self) -> None:
        html = render_email()
        assert "No local news available" in html
        assert "No global news available" in html
        assert "No AI deep dive available" in html
        assert "No business deep dive available" in html

    def test_date_object_formatted(self) -> None:
        html = render_email(mail_date=date(2025, 12, 25))
        assert "2025-12-25" in html
