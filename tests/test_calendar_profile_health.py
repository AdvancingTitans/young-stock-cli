from datetime import datetime

import pytest

from young_stock import calendar as trade_calendar
from young_stock.health import SourceHealthBook
from young_stock.profile import (
    ProfileCorruptError,
    add_profile_item,
    clear_profile,
    clear_profile_kind,
    load_profile,
    profile_path,
    remove_profile_item,
)


def test_profile_uses_young_stock_home_when_no_profile_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.delenv("YOUNG_STOCK_PROFILE", raising=False)

    add_profile_item("stocks", "600519")

    assert (tmp_path / "profile.json").exists()


def test_nearest_trade_date_skips_a_share_holiday():
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 19, 16, 0)) == "20260618"


def test_nearest_trade_date_before_close_uses_previous_trade_day():
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 1, 14, 59)) == "20260529"
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 1, 15, 1)) == "20260601"


def test_a_share_session_covers_holiday_pre_open_lunch_and_after_close():
    assert trade_calendar.a_share_session(datetime(2026, 6, 19, 10, 0)) == "休市"
    assert trade_calendar.a_share_session(datetime(2026, 6, 18, 8, 50)) == "盘前"
    assert trade_calendar.a_share_session(datetime(2026, 6, 18, 12, 0)) == "午间"
    assert trade_calendar.a_share_session(datetime(2026, 6, 18, 15, 10)) == "盘后"


def test_latest_report_trade_date_uses_current_day_during_trading_sessions():
    assert trade_calendar.latest_report_trade_date(datetime(2026, 6, 18, 9, 1)) == "20260618"
    assert trade_calendar.latest_report_trade_date(datetime(2026, 6, 18, 12, 0)) == "20260618"
    assert trade_calendar.latest_report_trade_date(datetime(2026, 6, 18, 14, 30)) == "20260618"


def test_latest_report_trade_date_avoids_holiday_and_pre_open():
    assert trade_calendar.latest_report_trade_date(datetime(2026, 6, 19, 10, 0)) == "20260618"
    assert trade_calendar.latest_report_trade_date(datetime(2026, 6, 18, 8, 50)) == "20260617"


def test_profile_read_write_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))

    add_profile_item("stocks", "600519")
    add_profile_item("funds", "161725")
    add_profile_item("stocks", "600519")

    assert profile_path() == tmp_path / "profile.json"
    assert load_profile() == {
        "stocks": ["600519"],
        "funds": ["161725"],
        "groups": {},
        "classifications": {"stocks": {}},
        "positions": {"stocks": {}, "funds": {}},
    }

    add_profile_item("stocks", "NVDA", buy_date="2026-01-15", quantity=10)
    assert load_profile()["positions"]["stocks"]["NVDA"] == {"buy_date": "2026-01-15", "quantity": 10.0}
    remove_profile_item("stocks", "600519")
    assert load_profile() == {
        "stocks": ["NVDA"],
        "funds": ["161725"],
        "groups": {},
        "classifications": {"stocks": {}},
        "positions": {"stocks": {"NVDA": {"buy_date": "2026-01-15", "quantity": 10.0}}, "funds": {}},
    }

    add_profile_item("stocks", "600000")
    clear_profile_kind("stocks")
    assert load_profile() == {
        "stocks": [],
        "funds": ["161725"],
        "groups": {},
        "classifications": {"stocks": {}},
        "positions": {"stocks": {}, "funds": {}},
    }

    clear_profile_kind("funds")
    assert load_profile() == {
        "stocks": [],
        "funds": [],
        "groups": {},
        "classifications": {"stocks": {}},
        "positions": {"stocks": {}, "funds": {}},
    }

    clear_profile()
    assert load_profile() == {"stocks": [], "funds": [], "groups": {}, "classifications": {"stocks": {}}, "positions": {"stocks": {}, "funds": {}}}


def test_profile_load_preserves_legacy_groups_without_new_group_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    profile_path().write_text(
        '{"stocks":["600519"],"funds":[],"groups":{"旧分组":{"stocks":["600519"],"funds":[]}},"positions":{"stocks":{},"funds":{}}}',
        encoding="utf-8",
    )

    assert load_profile()["groups"] == {"旧分组": {"stocks": ["600519"], "funds": []}}


def test_profile_load_keeps_legacy_style_and_exposes_category(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    profile_path().write_text(
        '{"stocks":["600519"],"funds":[],"classifications":{"stocks":{"600519":{"market":"A股","asset_type":"股票","style":"消费","evidence":["name=贵州茅台"]}}},"positions":{"stocks":{},"funds":{}}}',
        encoding="utf-8",
    )

    assert load_profile()["classifications"]["stocks"]["600519"] == {
        "market": "A股",
        "asset_type": "股票",
        "category": "消费",
        "style": "消费",
        "evidence": ["name=贵州茅台"],
    }


def test_profile_recovers_last_good_backup_when_primary_is_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    add_profile_item("stocks", "600519")
    add_profile_item("funds", "161725")

    profile_path().write_text("{broken", encoding="utf-8")

    recovered = load_profile()
    assert recovered["stocks"] == ["600519"]
    assert recovered["funds"] == []

    add_profile_item("funds", "161725")
    assert load_profile()["funds"] == ["161725"]


def test_profile_reports_corruption_instead_of_silently_returning_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    profile_path().write_text("{broken", encoding="utf-8")

    with pytest.raises(ProfileCorruptError, match="profile.json"):
        load_profile()


def test_source_health_book_tracks_recent_failures():
    book = SourceHealthBook(window_size=3)
    book.record("eastmoney", ok=False, latency_ms=900)
    book.record("eastmoney", ok=False, latency_ms=1000)
    book.record("eastmoney", ok=True, latency_ms=100)

    snapshot = book.snapshot("eastmoney")

    assert snapshot.success_rate == 1 / 3
    assert snapshot.average_latency_ms == 2000 / 3
    assert snapshot.should_skip
