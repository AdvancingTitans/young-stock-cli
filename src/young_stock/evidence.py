"""Evidence packs for deterministic and LLM-assisted market reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

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
    if hasattr(quote, "to_dict"):
        return quote.to_dict()
    if hasattr(quote, "__dataclass_fields__"):
        return asdict(quote)
    return {
        key: getattr(quote, key, None)
        for key in ("symbol", "name", "market", "date", "price", "change_pct", "turnover", "source", "currency")
    }


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


def build_daily_evidence(core: Any, trade_date: str, profile: dict[str, Any] | None = None) -> EvidenceBundle:
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
    fund_flow = _call({}, core.get_fund_flow, trade_date, strict_date=False)
    industry = _call({}, core.fetch_eastmoney_board_list, "industry", trade_date, limit=100)
    concept = _call({}, core.fetch_eastmoney_board_list, "concept", trade_date, limit=100)
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
    for symbol in profile.get("stocks") or []:
        quote = _call(None, core.get_single_stock_quote, symbol, trade_date)
        if quote:
            holdings.append(_quote_dict(quote))

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
            "available": bool(board_rows),
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
        "methodology": "AdvancingTitans/stock-analysis M1-M6",
    }
    return EvidenceBundle(modules=modules, meta=meta, quality_score=score, missing_modules=missing)


def build_stock_evidence(core: Any, symbol: str, trade_date: str) -> EvidenceBundle:
    daily = build_daily_evidence(core, trade_date, {"stocks": [symbol], "funds": []})
    quote = _call(None, core.get_single_stock_quote, symbol, trade_date)
    quote_payload = _quote_dict(quote)
    normalized_symbol = str(quote_payload.get("symbol") or symbol)
    name = str(quote_payload.get("name") or normalized_symbol)
    flow = _call({}, core.fetch_stock_fund_flow_daily, normalized_symbol, trade_date, limit=20)
    block_trades = _call({}, core.fetch_block_trades, normalized_symbol, trade_date, limit=10)
    aliases = _call([normalized_symbol, name], core._news_aliases, normalized_symbol, name)
    news = _call(
        {},
        core.combined_news_search,
        name,
        size=8,
        lang="zh-CN" if quote_payload.get("market") in {"cn_market", "hk_market"} else "en",
        aliases=aliases,
        date_str=trade_date,
    )
    daily.modules["STOCK"] = {
        "available": bool(quote_payload),
        "quote": quote_payload,
        "fund_flow": flow,
        "block_trades": block_trades,
        "news": news,
    }
    daily.meta["analysis_symbol"] = normalized_symbol
    daily.meta["report_type"] = "single-stock"
    return daily
