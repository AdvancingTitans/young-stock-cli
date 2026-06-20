"""Evidence packs for deterministic and LLM-assisted market reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from young_stock.health import SOURCE_HEALTH, SourceHealthBook

from .sources import SourcePolicy, resolve_news, resolve_quote
from .sources.extras import StockExtras, collect_stock_extras

MODULE_WEIGHTS = {"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10}


@dataclass
class EvidenceBundle:
    modules: dict[str, dict[str, Any]]
    meta: dict[str, Any] = field(default_factory=dict)
    quality_score: int = 0
    missing_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"modules": self.modules, "_meta": self.meta}


def _call(default: Any, function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        if isinstance(default, dict):
            return {"_error": str(exc)}
        return default


def _quote_dict(quote: Any) -> dict[str, Any]:
    if quote is None:
        return {}
    if isinstance(quote, dict):
        return {
            key: quote.get(key)
            for key in ("symbol", "name", "market", "date", "price", "change_pct", "turnover", "source", "currency")
        }
    if hasattr(quote, "to_dict"):
        return quote.to_dict()
    if hasattr(quote, "__dataclass_fields__"):
        return asdict(quote)
    return {
        key: getattr(quote, key, None)
        for key in ("symbol", "name", "market", "date", "price", "change_pct", "turnover", "source", "currency")
    }


def _optional_section(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("_error") or value.get("_unavailable"):
            return None
        rows = value.get("rows")
        data = value.get("data")
        if isinstance(rows, list) and not rows:
            return None
        if isinstance(data, list) and not data:
            return None
        if value.get("source") == "none":
            return None
    return value


def _record_source_event(meta: dict[str, Any], label: str, source: str, attempts: tuple[str, ...]) -> None:
    if not source:
        return
    attempt_suffix = f" ({'; '.join(attempts)})" if attempts else ""
    meta.setdefault("source_events", []).append(f"{label}:{source}{attempt_suffix}")


def _index_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": item.get("f12"),
        "name": item.get("f14"),
        "price": item.get("f2"),
        "change": item.get("f4"),
        "change_pct": item.get("f3"),
        "turnover": item.get("f6"),
        "trade_date": item.get("_source_date"),
        "source": item.get("_source") or "",
    }


def _pool(data: dict[str, Any]) -> tuple[int | None, list[dict[str, Any]]]:
    if not isinstance(data, dict) or "_error" in data:
        return None, []
    payload = data.get("data") or {}
    rows = payload.get("pool") or []
    return payload.get("tc", len(rows)), rows


def _board_list(core: Any, board_type: str, trade_date: str) -> dict[str, Any]:
    if hasattr(core, "get_board_list"):
        return _call({}, core.get_board_list, board_type, trade_date, limit=100)
    result = _call({}, core.fetch_eastmoney_board_list, board_type, trade_date, limit=100)
    if (
        result.get("rows")
        or not getattr(core, "BROWSER_FALLBACK", False)
        or not hasattr(core, "browser_board_list")
    ):
        return result
    browser_result = _call({}, core.browser_board_list, board_type)
    return browser_result if browser_result.get("rows") else result


def _fund_flow_available(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict) or data.get("_unavailable") or data.get("_error"):
        return False
    return any(
        isinstance(value, (int, float)) or bool(value)
        for key, value in data.items()
        if not str(key).startswith("_") and key != "date"
    )


def build_daily_evidence(
    core: Any,
    trade_date: str,
    profile: dict[str, Any] | None = None,
    *,
    rich_source: bool = False,
    health: SourceHealthBook | None = None,
) -> EvidenceBundle:
    profile = profile or {}
    a_indices = [_index_dict(item) for item in _call([], core.get_index, trade_date)]
    hk_quotes = _call(
        [],
        core.fetch_hk_indices_sina,
        {"^HSI": "恒生指数", "^HSCE": "国企指数", "HSTECH.HK": "恒生科技指数"},
        trade_date,
    )
    us_quotes = _call(
        [],
        core.fetch_us_indices_sina,
        {"^GSPC": "标普 500", "^IXIC": "纳斯达克"},
        trade_date,
    )
    northbound = _call({}, core.fetch_northbound_flow_snapshot, trade_date)
    fund_flow = _call({}, core.get_fund_flow, trade_date, strict_date=True)
    industry = _board_list(core, "industry", trade_date)
    concept = _board_list(core, "concept", trade_date)
    zt = _call({}, core.get_zt_pool, trade_date)
    dt = _call({}, core.get_dt_pool, trade_date)
    zb = _call({}, core.get_zb_pool, trade_date)
    zt_count, zt_rows = _pool(zt)
    dt_count, dt_rows = _pool(dt)
    zb_count, zb_rows = _pool(zb)
    denominator = (zt_count or 0) + (zb_count or 0)
    blowup_ratio = (zb_count / denominator) if zb_count is not None and denominator else None
    board_rows = list(industry.get("rows") or []) + list(concept.get("rows") or [])
    breadth_up = sum(int(row.get("up_count") or 0) for row in industry.get("rows") or [])
    breadth_down = sum(int(row.get("down_count") or 0) for row in industry.get("rows") or [])

    holdings = []
    holdings_extras = []
    policy = SourcePolicy(rich_source=rich_source)
    for symbol in profile.get("stocks") or []:
        quote_result = resolve_quote(core, symbol, trade_date, policy=policy, health=health or SOURCE_HEALTH)
        quote_payload = _quote_dict(quote_result.data)
        if quote_payload:
            holdings.append(quote_payload)
        if rich_source:
            extras = _call(None, collect_stock_extras, core, symbol, trade_date, rich_source=True)
            if extras:
                payload = extras.to_dict()
                holdings_extras.append(
                    {
                        "symbol": symbol,
                        "lhb_count": len((payload.get("lhb") or {}).get("rows") or []),
                        "social_heat": (payload.get("social_heat") or {}).get("count"),
                        "events": (payload.get("events") or {}).get("rows") or [],
                    }
                )

    modules = {
        "M1": {
            "available": bool(a_indices or hk_quotes or us_quotes),
            "a_indices": a_indices,
            "hk_indices": [_quote_dict(item) for item in hk_quotes],
            "us_indices": [_quote_dict(item) for item in us_quotes],
            "northbound": northbound,
            "breadth": {
                "up": breadth_up or None,
                "down": breadth_down or None,
                "scope": "行业板块成分汇总",
            },
        },
        "M2": {
            "available": bool(board_rows) or _fund_flow_available(fund_flow),
            "industry": industry.get("rows") or [],
            "concept": concept.get("rows") or [],
            "fund_flow": fund_flow,
        },
        "M3": {
            "available": zt_count is not None and bool(zt_rows),
            "zt_count": zt_count,
            "zt_pool": zt_rows,
            "early_limit_up_count": (
                sum(1 for row in zt_rows if row.get("fbt") and int(row["fbt"]) <= 100000) if zt_count is not None else None
            ),
        },
        "M4": {
            "available": dt_count is not None and zb_count is not None,
            "dt_count": dt_count,
            "zb_count": zb_count,
            "blowup_ratio": blowup_ratio,
            "dt_pool": dt_rows,
            "zb_pool": zb_rows,
        },
        "M5": {
            "available": bool(holdings or zt_rows),
            "holdings": holdings,
            "holdings_extras": holdings_extras,
            "style_signals": {
                "growth_board_count": sum(
                    1 for row in zt_rows if str(row.get("c") or "").startswith(("30", "68"))
                )
            },
        },
        "M6": {
            "available": bool(board_rows),
            "resilient": [
                row
                for row in board_rows
                if isinstance(row.get("change_pct"), (int, float)) and row["change_pct"] >= 0
            ][:10],
        },
    }
    missing = [name for name, payload in modules.items() if not payload.get("available")]
    score = sum(weight for name, weight in MODULE_WEIGHTS.items() if name not in missing)
    degrade_mode = "full" if score >= 80 else "degraded" if score >= 60 else "simplified"
    meta = {
        "trade_date": trade_date,
        "quality_score": score,
        "missing_modules": missing,
        "degrade_mode": degrade_mode,
        "source_events": [],
        "methodology": "young M1-M7",
    }
    return EvidenceBundle(modules=modules, meta=meta, quality_score=score, missing_modules=missing)


def build_stock_evidence(
    core: Any,
    symbol: str,
    trade_date: str,
    *,
    rich_source: bool = False,
    health: SourceHealthBook | None = None,
) -> EvidenceBundle:
    policy = SourcePolicy(rich_source=rich_source)
    daily = build_daily_evidence(core, trade_date, {"stocks": [symbol], "funds": []}, rich_source=rich_source, health=health)
    daily_holdings = daily.modules.get("M5", {}).get("holdings") or []
    quote_payload = next((item for item in daily_holdings if str(item.get("symbol") or "") == str(symbol)), {})
    quote_attempts: tuple[str, ...] = ()
    if not quote_payload:
        quote_result = resolve_quote(core, symbol, trade_date, policy=policy, health=health or SOURCE_HEALTH)
        quote_payload = _quote_dict(quote_result.data)
        quote_attempts = quote_result.attempts
    normalized_symbol = str(quote_payload.get("symbol") or symbol)
    flow = _call({}, core.fetch_stock_fund_flow_daily, normalized_symbol, trade_date, limit=20)
    block_trades = _call({}, core.fetch_block_trades, normalized_symbol, trade_date, limit=10)
    news_result = resolve_news(
        core,
        normalized_symbol,
        trade_date,
        quote_payload=quote_payload,
        policy=policy,
        health=health or SOURCE_HEALTH,
    )
    extras = _call(
        StockExtras(source_trace=["extras unavailable"]),
        collect_stock_extras,
        core,
        normalized_symbol,
        trade_date,
        rich_source=rich_source,
    )
    stock_module = {
        "available": bool(quote_payload),
        "quote": quote_payload,
        "extras": extras.to_dict(),
    }
    optional_sections = {
        "fund_flow": _optional_section(flow),
        "block_trades": _optional_section(block_trades),
        "news": _optional_section(news_result.data),
    }
    for key, value in optional_sections.items():
        if value is not None:
            stock_module[key] = value
    daily.modules["STOCK"] = stock_module
    daily.meta["analysis_symbol"] = normalized_symbol
    daily.meta["report_type"] = "single-stock"
    _record_source_event(daily.meta, "quote", str(quote_payload.get("source") or ""), quote_attempts)
    _record_source_event(daily.meta, "news", news_result.source, news_result.attempts)
    return daily
