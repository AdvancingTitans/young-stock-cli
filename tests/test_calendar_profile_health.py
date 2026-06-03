from datetime import datetime

from young_stock import calendar as trade_calendar
from young_stock.health import SourceHealthBook
from young_stock.profile import add_profile_item, load_profile, profile_path


def test_nearest_trade_date_skips_a_share_holiday():
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 19, 16, 0)) == "20260618"


def test_nearest_trade_date_before_close_uses_previous_trade_day():
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 1, 14, 59)) == "20260529"
    assert trade_calendar.nearest_trade_date(datetime(2026, 6, 1, 15, 1)) == "20260601"


def test_profile_read_write_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))

    add_profile_item("stocks", "600519")
    add_profile_item("funds", "161725")
    add_profile_item("stocks", "600519")

    assert profile_path() == tmp_path / "profile.json"
    assert load_profile() == {"stocks": ["600519"], "funds": ["161725"]}


def test_source_health_book_tracks_recent_failures():
    book = SourceHealthBook(window_size=3)
    book.record("eastmoney", ok=False, latency_ms=900)
    book.record("eastmoney", ok=False, latency_ms=1000)
    book.record("eastmoney", ok=True, latency_ms=100)

    snapshot = book.snapshot("eastmoney")

    assert snapshot.success_rate == 1 / 3
    assert snapshot.average_latency_ms == 2000 / 3
    assert snapshot.should_skip
