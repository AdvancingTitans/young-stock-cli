"""Lightweight HK/US/global market helpers for Evidence Bundle inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class GlobalSymbol:
    symbol: str
    market: str
    source_codes: dict[str, str]


_DERIVATIVE_NAME_HINTS = (
    "票据",
    "认购",
    "认沽",
    "牛",
    "熊",
    "法兴",
    "摩通",
    "瑞银",
    "高盛",
    "杠杆",
    "反向",
    "WARRANT",
    "CALL",
    "PUT",
    "BULL",
    "BEAR",
    "2X",
    "3X",
    "ETN",
)

_US_INDEX_MAP = {"^GSPC": "标普 500", "^IXIC": "纳斯达克", "^DJI": "道琼斯"}
_HK_INDEX_MAP = {"^HSI": "恒生指数", "^HSCE": "国企指数", "HSTECH.HK": "恒生科技指数"}


def _compact_date(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))[:8]


def _display_date(value: str) -> str:
    compact = _compact_date(value)
    if re.fullmatch(r"\d{8}", compact):
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return str(value or "")


def _float(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def normalize_global_symbol(symbol: str) -> GlobalSymbol:
    raw = str(symbol).strip().upper()
    if not raw:
        raise ValueError("股票代码不能为空")
    if raw.endswith(".HK") or raw.isdigit():
        code = raw[:-3] if raw.endswith(".HK") else raw
        if code.isdigit() and 1 <= len(code) <= 5:
            hk_code = (code.lstrip("0") or "0").zfill(5)
            return GlobalSymbol(f"{hk_code}.HK", "hk_market", {"eastmoney": hk_code, "sina": hk_code, "tencent": hk_code})
        raise ValueError(f"无法识别的港股代码: {symbol}")
    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", raw):
        return GlobalSymbol(raw, "us_market", {"eastmoney": raw, "sina": raw, "tencent": raw})
    raise ValueError(f"无法识别的全球股票代码: {symbol}")


def _normal_code(value: Any, market: str) -> str:
    code = str(value or "").upper().replace(".HK", "")
    if market == "hk_market" and code.isdigit():
        return (code.lstrip("0") or "0").zfill(5)
    return code


def _is_plain_stock_name(name: str) -> bool:
    upper = name.upper()
    return not any(hint in upper for hint in _DERIVATIVE_NAME_HINTS)


def select_exact_eastmoney_match(rows: list[dict[str, Any]], symbol: str, market: str) -> dict[str, Any] | None:
    normalized = normalize_global_symbol(symbol) if market in {"hk_market", "us_market"} else None
    target = (normalized.source_codes["eastmoney"] if normalized else str(symbol)).upper()
    exact = [
        row
        for row in rows
        if _normal_code(row.get("f12"), market) == target
        and _is_plain_stock_name(str(row.get("f14") or row.get("name") or ""))
    ]
    return exact[0] if exact else None


def lightweight_source_plan(market: str, capability: str) -> tuple[str, ...]:
    if capability == "history" and market in {"hk_market", "us_market"}:
        return ("eastmoney", "yahoo")
    if capability == "indices" and market == "hk_market":
        return ("tencent", "sina", "eastmoney")
    if capability == "indices" and market == "us_market":
        return ("sina", "tencent", "eastmoney")
    if capability == "quote" and market in {"hk_market", "us_market"}:
        return ("sina", "tencent", "eastmoney")
    return ()


def parse_eastmoney_kline_close(
    symbol: str,
    market: str,
    klines: list[str],
    *,
    requested_date: str,
    today: str | None = None,
) -> dict[str, Any]:
    requested = _compact_date(requested_date)
    today_compact = _compact_date(today or datetime.now().strftime("%Y%m%d"))
    if not re.fullmatch(r"\d{8}", requested):
        return {"_error": "历史日期应为 YYYYMMDD 或 YYYY-MM-DD"}
    if requested > today_compact:
        return {
            "_error": "历史K线不能返回未来数据",
            "requested_date": _display_date(requested),
            "today": _display_date(today_compact),
        }
    for row in klines:
        parts = str(row).split(",")
        if len(parts) < 3:
            continue
        row_date = _compact_date(parts[0])
        if row_date < requested or row_date > today_compact:
            continue
        close = _float(parts[2])
        if close is None:
            continue
        return {
            "symbol": symbol,
            "market": market,
            "date": _display_date(row_date),
            "close": close,
            "_source": "东方财富历史K线",
            "_requested_date": _display_date(requested),
        }
    return {"_error": "请求日到当前日期之间未获取到可用历史K线"}


def _quote_dict(quote: Any) -> dict[str, Any]:
    if isinstance(quote, dict):
        return {
            "symbol": quote.get("symbol") or quote.get("f12"),
            "name": quote.get("name") or quote.get("f14"),
            "price": quote.get("price") or quote.get("f2"),
            "change_pct": quote.get("change_pct") or quote.get("f3"),
            "turnover": quote.get("turnover") or quote.get("f6"),
            "trade_date": quote.get("date") or quote.get("_source_date"),
            "source": quote.get("source") or quote.get("_source") or "",
        }
    if hasattr(quote, "to_dict"):
        data = quote.to_dict()
    else:
        data = dict(getattr(quote, "__dict__", {}))
    return {
        "symbol": data.get("symbol"),
        "name": data.get("name"),
        "price": data.get("price"),
        "change_pct": data.get("change_pct"),
        "turnover": data.get("turnover"),
        "trade_date": data.get("date"),
        "source": data.get("source") or "",
    }


def _merge_by_symbol(primary: list[Any], fallback: list[Any], order: list[str]) -> list[Any]:
    lookup = {str(getattr(item, "symbol", item.get("symbol") if isinstance(item, dict) else "")).upper(): item for item in fallback}
    lookup.update({str(getattr(item, "symbol", item.get("symbol") if isinstance(item, dict) else "")).upper(): item for item in primary})
    return [lookup[symbol.upper()] for symbol in order if symbol.upper() in lookup]


def _has_all(rows: list[Any], order: list[str]) -> bool:
    found = {str(getattr(item, "symbol", item.get("symbol") if isinstance(item, dict) else "")).upper() for item in rows}
    return all(symbol.upper() in found for symbol in order)


def collect_global_indices(core: Any, trade_date: str) -> dict[str, list[dict[str, Any]]]:
    us_order = list(_US_INDEX_MAP)
    us = core.fetch_us_indices_sina(_US_INDEX_MAP, trade_date)
    if not _has_all(us, us_order):
        us = _merge_by_symbol(us, core.fetch_us_indices_tencent(_US_INDEX_MAP, trade_date), us_order)
    if not _has_all(us, us_order):
        us = _merge_by_symbol(us, core.fetch_indices_direct(_US_INDEX_MAP, trade_date, getattr(core, "EM_US_INDEX_SECID", {})), us_order)

    hk_order = list(_HK_INDEX_MAP)
    hk = core.fetch_hk_indices_tencent(_HK_INDEX_MAP, trade_date)
    if not _has_all(hk, hk_order):
        hk = _merge_by_symbol(hk, core.fetch_hk_indices_sina(_HK_INDEX_MAP, trade_date), hk_order)
    if not _has_all(hk, hk_order):
        hk = _merge_by_symbol(hk, core.fetch_indices_direct(_HK_INDEX_MAP, trade_date, getattr(core, "EM_HK_INDEX_SECID", {})), hk_order)

    a_rows = core.get_index(trade_date) if hasattr(core, "get_index") else []
    return {
        "us_indices": [_quote_dict(item) for item in us],
        "hk_indices": [_quote_dict(item) for item in hk],
        "a_indices": [_quote_dict(item) for item in a_rows],
    }


def parse_sec_filing_fixture(filing: dict[str, Any]) -> dict[str, Any]:
    items = filing.get("items") if isinstance(filing.get("items"), dict) else {}
    key_sections = [
        {"item": item, "snippet": str(text)[:500]}
        for item, text in items.items()
        if item in {"Item 1A", "Item 7", "Item 2.02", "Item 8.01"}
    ]
    return {
        "form": filing.get("form"),
        "filed": filing.get("filed"),
        "accession_number": filing.get("accessionNumber") or filing.get("accession_number"),
        "key_sections": key_sections,
        "source": "sec",
    }


def collect_rich_source_bundle(
    symbol: str,
    trade_date: str,
    *,
    rich_source: bool = False,
    installed_dependencies: set[str] | None = None,
) -> dict[str, Any]:
    del symbol, trade_date
    rich_keys = (
        "sec_filings",
        "xbrl_financials",
        "analyst_estimates",
        "institutional_holdings",
        "us_options",
        "full_financials",
    )
    if not rich_source:
        return {"rich_source_skipped": list(rich_keys)}
    installed = installed_dependencies or set()
    sec_message = "SEC 10-K/10-Q/8-K 需要安装 rich-source SEC adapter"
    payload = {
        "sec_filings": {"_unavailable": sec_message},
        "xbrl_financials": {"_unavailable": "XBRL 财务需要安装 rich-source SEC adapter"},
        "analyst_estimates": {"_unavailable": "分析师预期需要安装 rich-source 数据 adapter"},
        "institutional_holdings": {"_unavailable": "机构持仓需要安装 rich-source 数据 adapter"},
        "us_options": {"_unavailable": "美股期权需要安装 rich-source 期权 adapter"},
        "full_financials": {"_unavailable": "完整财务报表需要安装 rich-source 财务 adapter"},
    }
    if installed:
        payload["_installed_dependencies"] = sorted(installed)
    return payload


def collect_global_market_extensions(core: Any, symbol: str, trade_date: str, *, rich_source: bool = False) -> dict[str, Any]:
    normalized = normalize_global_symbol(symbol)
    history = core.fetch_stock_close_on_or_after(normalized.symbol, trade_date) if hasattr(core, "fetch_stock_close_on_or_after") else {}
    payload = {
        "symbol": normalized.symbol,
        "market": normalized.market,
        "quote_source_plan": list(lightweight_source_plan(normalized.market, "quote")),
        "history_source_plan": list(lightweight_source_plan(normalized.market, "history")),
        "history": history,
    }
    payload.update(collect_rich_source_bundle(normalized.symbol, trade_date, rich_source=rich_source))
    return payload
