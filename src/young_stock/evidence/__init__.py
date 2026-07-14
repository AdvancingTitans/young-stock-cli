"""Evidence packs for deterministic and LLM-assisted market reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from young_stock.health import SOURCE_HEALTH, SourceHealthBook

from ..sources import SourcePolicy, resolve_news, resolve_quote
from ..sources.extras import StockExtras, collect_stock_extras
from .emotion import build_market_emotion, compress_emotion_for_m7, map_emotion_to_modules

MODULE_WEIGHTS = {"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10}


@dataclass
class EvidenceBundle:
    modules: dict[str, dict[str, Any]]
    meta: dict[str, Any] = field(default_factory=dict)
    quality_score: int = 0
    missing_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "modules": self.modules, "_meta": self.meta}


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
            for key in (
                "symbol",
                "name",
                "market",
                "date",
                "requested_date",
                "price",
                "change_pct",
                "turnover",
                "source",
                "source_url",
                "currency",
                "quality_flags",
                "notes",
                "completeness",
            )
        }
    if hasattr(quote, "to_dict"):
        return quote.to_dict()
    if hasattr(quote, "__dataclass_fields__"):
        return asdict(quote)
    return {
        key: getattr(quote, key, None)
        for key in (
            "symbol",
            "name",
            "market",
            "date",
            "requested_date",
            "price",
            "change_pct",
            "turnover",
            "source",
            "source_url",
            "currency",
            "quality_flags",
            "notes",
            "completeness",
        )
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


def _attach_news_radar(
    container: dict[str, Any],
    meta: dict[str, Any],
    radar_evidence: Any,
) -> None:
    if not isinstance(radar_evidence, dict) or radar_evidence.get("_error"):
        return
    compressed = radar_evidence.get("compressed")
    if isinstance(compressed, dict) and compressed.get("events"):
        container["news_radar"] = compressed
    meta["news_radar"] = {
        "raw_count": radar_evidence.get("raw_count", 0),
        "event_count": radar_evidence.get("event_count", 0),
        "truncated": bool(radar_evidence.get("truncated")),
    }


def _stock_news_context(symbol: str, quote_payload: dict[str, Any], extensions: dict[str, Any]) -> dict[str, list[str]]:
    company = [symbol]
    if quote_payload.get("name"):
        company.append(str(quote_payload["name"]))
    classification = extensions.get("classification") if isinstance(extensions, dict) else {}
    industries: list[str] = []
    if isinstance(classification, dict):
        industries.extend(str(value) for value in classification.get("industry") or [] if value)
        industries.extend(str(value) for value in classification.get("concepts") or [] if value)
    return {
        "company_keywords": list(dict.fromkeys(company)),
        "industry_keywords": list(dict.fromkeys(industries)),
        "upstream_keywords": [],
        "downstream_keywords": [],
    }


def _fund_news_context(fund_code: str, fund_name: str, holdings: list[dict[str, Any]]) -> dict[str, list[str]]:
    company: list[str] = [fund_code]
    if fund_name:
        company.append(fund_name)
    industry: list[str] = ["基金重仓股"]
    for item in holdings[:10]:
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        if code:
            company.append(code)
        if name:
            company.append(name)
            if any(token in name for token in ("茅台", "五粮液", "泸州", "白酒")):
                industry.append("白酒")
    return {
        "company_keywords": list(dict.fromkeys(company)),
        "industry_keywords": list(dict.fromkeys(industry)),
        "upstream_keywords": [],
        "downstream_keywords": [],
    }


def _supplemental_evidence_status(missing_modules: list[str]) -> dict[str, Any]:
    candidates = {
        "M1": ["腾讯/新浪/东方财富指数", "北向资金快照", "精选宏观与全球市场资讯"],
        "M2": ["行业/概念板块榜", "同花顺公开板块页", "板块资金流"],
        "M3": ["东财涨停池", "成交额 Top 榜", "短线情绪扩散指标"],
        "M4": ["东财跌停池/炸板池", "融资融券与风险事件", "公告风险日历"],
        "M5": ["持仓行情", "基金重仓股行情", "股东户数/大宗交易/风格暴露"],
        "M6": ["抗跌板块", "公告/研报/精选资讯", "持仓相关行业资讯雷达"],
    }
    return {
        "missing_modules": missing_modules,
        "candidates": {name: candidates[name] for name in missing_modules if name in candidates},
        "rule": "缺失指标只补稳定公开源与精选资讯；仍不可得时保留缺口，不补零。",
    }


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return [row for row in value["rows"] if isinstance(row, dict)]
    return []


def _collect_a_share_extensions(core: Any, symbol: str, trade_date: str, rich_source: bool) -> dict[str, Any]:
    normalized, market = core.normalize_stock_symbol(symbol)
    if market != "cn_market" or not hasattr(core, "fetch_a_share_extensions"):
        return {}
    payload = _call({}, core.fetch_a_share_extensions, normalized, trade_date, rich_source=rich_source)
    return payload if isinstance(payload, dict) else {}


def _collect_global_market_extensions(core: Any, symbol: str, trade_date: str, rich_source: bool) -> dict[str, Any]:
    normalized, market = core.normalize_stock_symbol(symbol)
    if market not in {"hk_market", "us_market"} or not hasattr(core, "fetch_global_market_extensions"):
        return {}
    payload = _call({}, core.fetch_global_market_extensions, normalized, trade_date, rich_source=rich_source)
    return payload if isinstance(payload, dict) else {}


def _risk_calendar(extensions: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event_type in ("lockup", "dividend", "announcements"):
        for row in _rows(extensions.get(event_type)):
            item = {"type": event_type}
            item.update(row)
            events.append(item)
    return sorted(events, key=lambda item: str(item.get("date") or ""))


def _map_a_share_extensions(modules: dict[str, dict[str, Any]], meta: dict[str, Any], extensions: dict[str, Any]) -> None:
    if not extensions:
        return
    classification = extensions.get("classification")
    if isinstance(classification, dict):
        modules["M2"]["a_share_classification"] = classification
        modules["M5"]["a_share_classification"] = classification
        modules["M6"]["a_share_classification"] = classification
    for key, module_name in (
        ("stock_fund_flow", "M2"),
        ("lhb", "M3"),
        ("margin", "M4"),
        ("holder_count", "M5"),
        ("block_trades", "M5"),
    ):
        value = extensions.get(key)
        if isinstance(value, dict):
            modules[module_name][key] = value
    risks = _risk_calendar(extensions)
    if risks:
        meta["risk_calendar"] = risks


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
    include_news_radar: bool = True,
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
    denominator = zt_count + zb_count if zt_count is not None and zb_count is not None else None
    blowup_ratio = (zb_count / denominator) if zb_count is not None and denominator else None
    emotion = build_market_emotion(core, trade_date, zt_data=zt, dt_data=dt, zb_data=zb)
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

    emotion_modules = map_emotion_to_modules(emotion, holdings=[item.get("symbol") for item in holdings])
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
    for name, payload in emotion_modules.items():
        modules[name].update(payload)
    missing = [name for name, payload in modules.items() if not payload.get("available")]
    score = sum(weight for name, weight in MODULE_WEIGHTS.items() if name not in missing)
    degrade_mode = "full" if score >= 80 else "degraded" if score >= 60 else "simplified"
    meta = {
        "trade_date": trade_date,
        "requested_date": trade_date,
        "as_of": trade_date,
        "quality_score": score,
        "missing_modules": missing,
        "degrade_mode": degrade_mode,
        "source_events": [],
        "methodology": "young M1-M7",
        "report_type": "daily",
        "m7_emotion_summary": compress_emotion_for_m7(emotion),
    }
    if missing:
        meta["supplemental_evidence"] = _supplemental_evidence_status(missing)
    if include_news_radar and hasattr(core, "fetch_news_radar"):
        radar = _call(
            {},
            core.fetch_news_radar,
            mode="daily",
            date_str=trade_date,
            profile=profile,
            rich_source=rich_source,
        )
        _attach_news_radar(modules["M1"], meta, radar)
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
    daily = build_daily_evidence(
        core,
        trade_date,
        {"stocks": [symbol], "funds": []},
        rich_source=rich_source,
        include_news_radar=False,
        health=health,
    )
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
    a_share_extensions = _collect_a_share_extensions(core, normalized_symbol, trade_date, rich_source)
    global_market = _collect_global_market_extensions(core, normalized_symbol, trade_date, rich_source)
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
    if a_share_extensions:
        stock_module["a_share_extensions"] = a_share_extensions
    if global_market:
        stock_module["global_market"] = global_market
    if hasattr(core, "fetch_news_radar"):
        radar = _call(
            {},
            core.fetch_news_radar,
            mode="stock",
            date_str=trade_date,
            symbol=normalized_symbol,
            stock_context=_stock_news_context(normalized_symbol, quote_payload, a_share_extensions),
            rich_source=rich_source,
        )
        _attach_news_radar(stock_module, daily.meta, radar)
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
    _map_a_share_extensions(daily.modules, daily.meta, a_share_extensions)
    if global_market:
        _record_source_event(
            daily.meta,
            "global_market",
            str(global_market.get("history", {}).get("_source") or "global_market"),
            tuple(global_market.get("quote_source_plan") or ()),
        )
    _record_source_event(daily.meta, "quote", str(quote_payload.get("source") or ""), quote_attempts)
    _record_source_event(daily.meta, "news", news_result.source, news_result.attempts)
    return daily


def build_fund_evidence(
    core: Any,
    code: str,
    trade_date: str,
    *,
    rich_source: bool = False,
    health: SourceHealthBook | None = None,
) -> EvidenceBundle:
    del health
    fund_code = _call(code, core.normalize_fund_code, code) if hasattr(core, "normalize_fund_code") else code
    daily = build_daily_evidence(
        core,
        trade_date,
        {"stocks": [], "funds": [fund_code]},
        rich_source=rich_source,
        include_news_radar=False,
    )
    estimate = _call({}, core.fetch_fund_estimate, fund_code, trade_date)
    profile = _call({}, core.fetch_fund_profile, fund_code, trade_date) if hasattr(core, "fetch_fund_profile") else {}
    holdings_data = _call({}, core.fetch_fund_holdings, fund_code, trade_date, limit=10)
    holdings = holdings_data.get("holdings") if isinstance(holdings_data, dict) else []
    quotes_by_code = _call({}, core.fetch_fund_holding_quotes, holdings or [], trade_date) if holdings else {}
    missing: list[str] = []
    if not estimate or estimate.get("_error"):
        missing.append("基金净值估值")
    if not holdings:
        missing.append("持仓结构")
    fund_module = {
        "available": bool(estimate and not estimate.get("_error")) or bool(holdings),
        "fundcode": fund_code,
        "name": estimate.get("name") or holdings_data.get("title") or fund_code if isinstance(estimate, dict) and isinstance(holdings_data, dict) else fund_code,
        "fund_type": estimate.get("fund_type") if isinstance(estimate, dict) else None,
        "nav": estimate.get("nav") if isinstance(estimate, dict) else None,
        "nav_date": estimate.get("nav_date") if isinstance(estimate, dict) else None,
        "estimate_nav": estimate.get("estimate_nav") if isinstance(estimate, dict) else None,
        "estimate_change_pct": estimate.get("estimate_change_pct") if isinstance(estimate, dict) else None,
        "estimate_time": estimate.get("estimate_time") if isinstance(estimate, dict) else None,
        "fund_company": estimate.get("fund_company") if isinstance(estimate, dict) else None,
        "fund_manager": estimate.get("fund_manager") if isinstance(estimate, dict) else None,
        "fund_size": estimate.get("fund_size") if isinstance(estimate, dict) else None,
        "holdings": holdings or [],
        "holding_quotes": {
            key: _quote_dict(value)
            for key, value in (quotes_by_code or {}).items()
        } if isinstance(quotes_by_code, dict) else {},
        "tracking_index": estimate.get("tracking_index") if isinstance(estimate, dict) else None,
        "tracking_error": estimate.get("tracking_error") if isinstance(estimate, dict) else None,
        "premium_discount": estimate.get("premium_discount") if isinstance(estimate, dict) else None,
        "liquidity": estimate.get("liquidity") if isinstance(estimate, dict) else None,
        "fee": estimate.get("fee") if isinstance(estimate, dict) else None,
        "source": estimate.get("_source") if isinstance(estimate, dict) else "公开基金数据",
        "data_date": estimate.get("date") if isinstance(estimate, dict) else trade_date,
        "missing_evidence": missing,
    }
    if isinstance(profile, dict) and profile and not profile.get("_error"):
        fund_module["profile"] = profile
    if hasattr(core, "fetch_news_radar") and holdings:
        radar = _call(
            {},
            core.fetch_news_radar,
            mode="fund",
            date_str=trade_date,
            symbol=fund_code,
            stock_context=_fund_news_context(fund_code, str(fund_module.get("name") or ""), holdings),
            rich_source=rich_source,
        )
        compressed = radar.get("compressed") if isinstance(radar, dict) else None
        if isinstance(compressed, dict) and compressed.get("events"):
            fund_module["holding_news_radar"] = compressed
            daily.meta["news_radar"] = {
                "raw_count": radar.get("raw_count", 0),
                "event_count": radar.get("event_count", 0),
                "truncated": bool(radar.get("truncated")),
            }
    daily.modules["FUND"] = {key: value for key, value in fund_module.items() if value not in (None, "", {}, [])}
    daily.meta["analysis_symbol"] = fund_code
    daily.meta["asset_kind"] = "fund"
    daily.meta["report_type"] = "single-fund"
    daily.meta["missing_modules"] = sorted(set(daily.meta.get("missing_modules", []) + missing))
    if daily.meta.get("missing_modules"):
        daily.meta["supplemental_evidence"] = _supplemental_evidence_status(list(daily.meta["missing_modules"]))
    return daily
