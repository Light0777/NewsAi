from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from storage.history_manager import (
    HISTORY_DIR,
    _file_path,
    _resolve_history_dir,
    _to_date,
    load_daily_news,
    load_last_n_days,
    save_daily_news,
)

_FAKE_DIR: Path | None = None


def _make_article(title: str = "Story", source: str = "Reuters") -> dict[str, str]:
    return {"title": title, "source": source}


@pytest.fixture(autouse=True)
def _isolate_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "history"
    fake.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("storage.history_manager.HISTORY_DIR", fake)
    global _FAKE_DIR
    _FAKE_DIR = fake


class TestToDate:
    def test_accepts_date_object(self) -> None:
        d = date(2025, 6, 1)
        assert _to_date(d) is d

    def test_parses_date_string(self) -> None:
        assert _to_date("2025-06-01") == date(2025, 6, 1)


class TestFilePath:
    def test_formats_correct_path(self) -> None:
        path = _file_path(date(2025, 6, 1))
        assert path.name == "2025-06-01.json"
        assert path.parent == _FAKE_DIR


class TestSaveDailyNews:
    def test_saves_to_correct_file(self) -> None:
        path = save_daily_news(
            [_make_article("A")], day=date(2025, 7, 15)
        )
        assert Path(path).exists()
        assert Path(path).name == "2025-07-15.json"

    def test_writes_valid_json(self) -> None:
        save_daily_news(
            [_make_article("A"), _make_article("B")],
            day=date(2025, 7, 15),
        )
        saved = json.loads(
            (_FAKE_DIR / "2025-07-15.json").read_text(encoding="utf-8")
        )
        assert saved["date"] == "2025-07-15"
        assert len(saved["articles"]) == 2

    def test_overwrites_existing_file(self) -> None:
        save_daily_news([_make_article("Old")], day=date(2025, 7, 15))
        save_daily_news([_make_article("New")], day=date(2025, 7, 15))
        articles = load_daily_news(date(2025, 7, 15))
        assert articles == [_make_article("New")]

    def test_uses_today_when_no_day_given(self) -> None:
        today = date.today()
        path = save_daily_news([_make_article("Now")])
        assert Path(path).name == f"{today.isoformat()}.json"


class TestLoadDailyNews:
    def test_loads_saved_articles(self) -> None:
        articles = [_make_article("A"), _make_article("B")]
        save_daily_news(articles, day=date(2025, 7, 15))
        loaded = load_daily_news(date(2025, 7, 15))
        assert loaded == articles

    def test_returns_empty_list_when_no_file(self) -> None:
        assert load_daily_news(date(2099, 1, 1)) == []

    def test_accepts_string_date(self) -> None:
        save_daily_news([_make_article("X")], day=date(2025, 7, 15))
        loaded = load_daily_news("2025-07-15")
        assert len(loaded) == 1

    def test_handles_corrupted_file(self) -> None:
        (_FAKE_DIR / "2025-07-15.json").write_text("not json", encoding="utf-8")
        assert load_daily_news(date(2025, 7, 15)) == []


class TestLoadLastNDays:
    def test_loads_multiple_days(self) -> None:
        save_daily_news(
            [_make_article("Day1")], day=date(2025, 7, 13)
        )
        save_daily_news(
            [_make_article("Day2")], day=date(2025, 7, 14)
        )
        save_daily_news(
            [_make_article("Day3")], day=date(2025, 7, 15)
        )

        result = load_last_n_days(3, reference_date=date(2025, 7, 15))
        titles = [a["title"] for a in result]
        assert titles == ["Day3", "Day2", "Day1"]

    def test_skips_days_with_no_file(self) -> None:
        save_daily_news(
            [_make_article("Exists")], day=date(2025, 7, 15)
        )
        result = load_last_n_days(3, reference_date=date(2025, 7, 15))
        assert len(result) == 1

    def test_returns_empty_for_n_less_than_one(self) -> None:
        assert load_last_n_days(0) == []
        assert load_last_n_days(-1) == []

    def test_defaults_to_today(self) -> None:
        today = date.today()
        save_daily_news([_make_article("Today")])
        result = load_last_n_days(1)
        assert len(result) == 1
        assert result[0]["title"] == "Today"

    def test_returns_articles_in_reverse_chronological_order(self) -> None:
        save_daily_news(
            [_make_article("Old")], day=date(2025, 7, 10)
        )
        save_daily_news(
            [_make_article("Mid")], day=date(2025, 7, 11)
        )
        save_daily_news(
            [_make_article("Recent")], day=date(2025, 7, 12)
        )
        result = load_last_n_days(
            4, reference_date=date(2025, 7, 12)
        )
        assert [a["title"] for a in result] == ["Recent", "Mid", "Old"]
