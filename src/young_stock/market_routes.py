"""Shared market-data routing for reports and terminal dashboards."""

from __future__ import annotations

from typing import Any, Callable


def _rows(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("rows"))


def route_board_data(
    board_type: str,
    trade_date: str,
    *,
    direct: Callable[[str, str, int], dict[str, Any]],
    camofox: Callable[[str], dict[str, Any]],
    playwright: Callable[[str], dict[str, Any]],
    limit: int = 100,
    current_trade_date: str | None = None,
) -> dict[str, Any]:
    result = direct(board_type, trade_date, limit)
    if _rows(result):
        return result
    if current_trade_date and trade_date != current_trade_date:
        return {"board_type": board_type, "rows": [], "_unavailable": "历史数据不可得"}
    for browser_source in (camofox, playwright):
        candidate = browser_source(board_type)
        if _rows(candidate):
            return candidate
    return result or {"board_type": board_type, "rows": [], "_unavailable": "本模块证据暂缺"}


def _flow_available(result: Any) -> bool:
    if not isinstance(result, dict) or result.get("_error") or result.get("_unavailable"):
        return False
    return any(
        key != "date" and not str(key).startswith("_") and value not in (None, "")
        for key, value in result.items()
    )


def route_fund_flow_data(
    trade_date: str,
    *,
    online_sources: list[Callable[[str], dict[str, Any]]],
    browser: Callable[[str], dict[str, Any]],
    cached: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    for source in online_sources:
        result = source(trade_date)
        if _flow_available(result):
            return result
    browser_result = browser(trade_date)
    if _flow_available(browser_result):
        return browser_result
    cached_result = cached(trade_date)
    if _flow_available(cached_result):
        return cached_result
    return {"date": trade_date, "_unavailable": "本模块证据暂缺"}
