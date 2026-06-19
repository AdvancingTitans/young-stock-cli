"""Trading-calendar helpers used by CLI commands and skills."""

from __future__ import annotations

from datetime import date, datetime, timedelta

A_SHARE_HOLIDAYS_2026 = {
    "20260101",
    "20260216", "20260217", "20260218", "20260219", "20260220", "20260221", "20260222",
    "20260404", "20260405", "20260406",
    "20260501", "20260502", "20260503", "20260504", "20260505",
    "20260619", "20260620", "20260621",
    "20260925", "20260926", "20260927",
    "20261001", "20261002", "20261003", "20261004", "20261005", "20261006", "20261007", "20261008",
}

HK_MARKET_HOLIDAYS_2026 = {
    "20260101",
    "20260217", "20260218", "20260219",
    "20260403", "20260406", "20260407",
    "20260501", "20260525",
    "20260701",
    "20260926",
    "20261001", "20261019",
    "20261225",
}

US_MARKET_HOLIDAYS_2026 = {
    "20260101", "20260119", "20260216", "20260403", "20260525",
    "20260619", "20260703", "20260907", "20261126", "20261225",
}


def _yyyymmdd(value: date | datetime | str) -> str:
    if isinstance(value, str):
        return value.replace("-", "")
    return value.strftime("%Y%m%d")


def market_holidays(market: str = "a") -> set[str]:
    market = market.lower()
    if market in {"a", "cn", "cn_market", "ashare"}:
        return A_SHARE_HOLIDAYS_2026
    if market in {"hk", "hk_market"}:
        return HK_MARKET_HOLIDAYS_2026
    if market in {"us", "us_market"}:
        return US_MARKET_HOLIDAYS_2026
    return set()


def is_trade_day(value: date | datetime | str, market: str = "a") -> bool:
    day = _yyyymmdd(value)
    if isinstance(value, str):
        dt = datetime.strptime(day, "%Y%m%d")
    else:
        dt = value
    return dt.weekday() < 5 and day not in market_holidays(market)


def previous_trade_day(value: date | datetime | str, market: str = "a") -> str:
    if isinstance(value, str):
        dt = datetime.strptime(_yyyymmdd(value), "%Y%m%d")
    elif isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, datetime.min.time())
    dt -= timedelta(days=1)
    while not is_trade_day(dt, market):
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def nearest_trade_date(dt: datetime | None = None, market: str = "a") -> str:
    if dt is None:
        dt = datetime.now()
    if market.lower() in {"a", "cn", "cn_market", "ashare"} and (dt.hour, dt.minute) < (15, 0):
        return previous_trade_day(dt, market)
    while not is_trade_day(dt, market):
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def a_share_session(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    if not is_trade_day(dt, "a"):
        return "休市"
    minute = dt.hour * 60 + dt.minute
    if minute < 9 * 60:
        return "盘前"
    if minute < 11 * 60 + 30:
        return "早盘"
    if minute < 13 * 60:
        return "午间"
    if minute < 15 * 60:
        return "盘中"
    return "盘后"


def latest_report_trade_date(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    if a_share_session(dt) in {"休市", "盘前"}:
        return nearest_trade_date(dt, "a")
    return dt.strftime("%Y%m%d")
