"""Thin adapters over existing core fetchers plus a minimal Yahoo chart fallback."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable
from urllib.parse import quote

import requests

from .contracts import SourceResult

_CORE_QUOTE_FETCHERS = {
    "sina": {
        "cn_market": "fetch_cn_stocks_sina",
        "hk_market": "fetch_hk_stocks_sina",
        "us_market": "fetch_us_stocks_sina",
    },
    "tencent": {
        "cn_market": "fetch_cn_stocks_tencent",
        "hk_market": "fetch_hk_stocks_tencent",
        "us_market": "fetch_us_stocks_tencent",
    },
    "eastmoney": {
        "cn_market": "fetch_cn_stocks_direct",
        "hk_market": "fetch_hk_stocks_direct",
        "us_market": "fetch_us_stocks_direct",
    },
}


def _payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def core_quote_adapter(core: Any, source_id: str):
    def fetch(symbol: str, trade_date: str) -> SourceResult:
        normalized, market = core.normalize_stock_symbol(symbol)
        fetcher_name = _CORE_QUOTE_FETCHERS.get(source_id, {}).get(market)
        if not fetcher_name:
            return SourceResult(source=source_id, error=f"{source_id} does not support {market}")
        rows = getattr(core, fetcher_name)([normalized], trade_date)
        if not rows:
            return SourceResult(source=source_id, error="no quote")
        quote_data = rows[0]
        payload = _payload_dict(quote_data)
        return SourceResult(data=payload, source=source_id, as_of=str(payload.get("date") or trade_date))

    return fetch


def yahoo_chart_adapter(session: Any = None):
    client = session or requests.Session()

    def fetch(symbol: str, trade_date: str = "") -> SourceResult:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
        try:
            response = client.get(
                url,
                params={"range": "5y", "interval": "1d", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            response.raise_for_status()
            result = ((response.json().get("chart") or {}).get("result") or [None])[0]
        except Exception as exc:
            return SourceResult(source="yahoo", error=str(exc))
        if not result:
            return SourceResult(source="yahoo", error="no chart data")
        timestamps = result.get("timestamp") or []
        quote_rows = (((result.get("indicators") or {}).get("quote") or [{}])[0])
        closes = quote_rows.get("close") or []
        rows = [
            {"timestamp": timestamp, "close": close}
            for timestamp, close in zip(timestamps, closes)
            if close is not None
        ]
        if not rows:
            return SourceResult(source="yahoo", error="no usable closes")
        return SourceResult(
            data={"symbol": symbol, "meta": result.get("meta") or {}, "rows": rows},
            source="yahoo",
            as_of=trade_date,
        )

    return fetch


def _call_news(fetcher: Callable[..., dict[str, Any]], source_id: str, *args: Any, **kwargs: Any) -> SourceResult:
    payload = fetcher(*args, **kwargs)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not rows:
        error = payload.get("_error") if isinstance(payload, dict) else None
        return SourceResult(source=source_id, error=error or "no news")
    return SourceResult(data=payload, source=source_id)


def core_news_adapter(core: Any, source_id: str):
    if source_id == "eastmoney" and hasattr(core, "eastmoney_fast_news"):
        return lambda keyword, **kwargs: _call_news(core.eastmoney_fast_news, source_id, keyword, **kwargs)
    if source_id == "sina" and hasattr(core, "sina_roll_news"):
        return lambda keyword, **kwargs: _call_news(core.sina_roll_news, source_id, keyword, **kwargs)
    if source_id == "futu" and hasattr(core, "futu_news_search"):
        return lambda keyword, **kwargs: _call_news(core.futu_news_search, source_id, keyword, **kwargs)
    return unavailable_adapter(source_id)


def unavailable_adapter(source_id: str, reason: str = "structured adapter unavailable"):
    def fetch(*args: object, **kwargs: object) -> SourceResult:
        return SourceResult(source=source_id, error=reason)

    return fetch


def build_core_adapters(core: Any, session: Any = None) -> dict[str, Any]:
    return {
        "sina": core_quote_adapter(core, "sina"),
        "tencent": core_quote_adapter(core, "tencent"),
        "eastmoney": core_quote_adapter(core, "eastmoney"),
        "sina.news": core_news_adapter(core, "sina"),
        "eastmoney.news": core_news_adapter(core, "eastmoney"),
        "futu.news": core_news_adapter(core, "futu"),
        "yahoo": yahoo_chart_adapter(session),
        "cninfo": unavailable_adapter("cninfo", "use events/announcement collector"),
        "hkexnews": unavailable_adapter("hkexnews", "use events/announcement collector"),
        "jin10": unavailable_adapter("jin10", "no structured result"),
        "cls": unavailable_adapter("cls", "no structured result"),
        "aastocks": unavailable_adapter("aastocks", "no structured result"),
        "investing": unavailable_adapter("investing", "macro/news HTTP adapter not selected"),
        "companiesmarketcap": unavailable_adapter("companiesmarketcap", "profile adapter not selected"),
        "securities_times": unavailable_adapter("securities_times", "use internal search bridge"),
        "cs": unavailable_adapter("cs", "use internal search bridge"),
        "cnstock": unavailable_adapter("cnstock", "use internal search bridge"),
    }
