"""Runtime source resolution helpers used by evidence/CLI paths."""

from __future__ import annotations

from typing import Any

from young_stock.health import SOURCE_HEALTH, SourceHealthBook

from .adapters import build_core_adapters
from .contracts import SourcePolicy, SourceResult
from .resolver import SourceResolver


def _market_key(market: str) -> str:
    return {
        "cn_market": "a",
        "hk_market": "hk",
        "us_market": "us",
    }.get(market, market)


def resolve_quote(
    core: Any,
    symbol: str,
    trade_date: str,
    *,
    policy: SourcePolicy | None = None,
    health: SourceHealthBook | None = None,
    resolver: SourceResolver | None = None,
    session: Any = None,
) -> SourceResult:
    normalized, market = core.normalize_stock_symbol(symbol)
    runtime_resolver = resolver or SourceResolver(health=health or SOURCE_HEALTH)
    return runtime_resolver.resolve(
        _market_key(market),
        "quote",
        build_core_adapters(core, session),
        normalized,
        trade_date,
        policy=policy,
    )


def resolve_news(
    core: Any,
    symbol: str,
    trade_date: str,
    *,
    quote_payload: dict[str, Any] | None = None,
    policy: SourcePolicy | None = None,
    health: SourceHealthBook | None = None,
    resolver: SourceResolver | None = None,
) -> SourceResult:
    normalized, market = core.normalize_stock_symbol(symbol)
    payload = quote_payload or {}
    name = str(payload.get("name") or normalized)
    aliases = core._news_aliases(normalized, name) if hasattr(core, "_news_aliases") else [normalized, name]
    runtime_resolver = resolver or SourceResolver(health=health or SOURCE_HEALTH)
    adapters = build_core_adapters(core)
    news_adapters = {
        "eastmoney": adapters.get("eastmoney.news"),
        "sina": adapters.get("sina.news"),
        "futu": adapters.get("futu.news"),
    }
    return runtime_resolver.resolve(
        _market_key(market),
        "news",
        news_adapters,
        name,
        size=8,
        lang="zh-CN" if payload.get("market") in {"cn_market", "hk_market"} else "en",
        aliases=aliases,
        date_str=trade_date,
        policy=policy,
    )
