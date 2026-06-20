"""Declarative source registry; fetch logic belongs in adapters."""

from __future__ import annotations

from .contracts import DataSource, SourcePolicy

DATA_SOURCES = (
    DataSource(
        "eastmoney",
        ("a", "hk", "us"),
        ("quote", "history", "news", "announcements", "flow", "boards", "lhb"),
        "primary",
        "http",
        "eastmoney",
    ),
    DataSource("tencent", ("a", "hk", "us"), ("quote",), "primary", "http", "tencent"),
    DataSource("sina", ("a", "hk", "us"), ("quote", "news", "heat"), "primary", "http", "sina"),
    DataSource("ths", ("a",), ("flow", "news", "boards"), "primary", "http", "ths"),
    DataSource("yahoo", ("hk", "us"), ("history",), "fallback", "http", "yahoo"),
    DataSource("investing", ("hk", "us"), ("macro", "news"), "fallback", "http", "investing", slow=True),
    DataSource(
        "companiesmarketcap",
        ("us",),
        ("profile", "valuation"),
        "fallback",
        "http",
        "companiesmarketcap",
        slow=True,
    ),
    DataSource("cls", ("a",), ("news",), "fallback", "http", "cls"),
    DataSource("aastocks", ("hk",), ("quote", "news"), "fallback", "http", "aastocks"),
    DataSource("futu", ("a", "hk", "us"), ("news", "social"), "fallback", "http", "futu", slow=True),
    DataSource("jin10", ("a", "hk", "us"), ("news", "macro"), "fallback", "http", "jin10", slow=True),
    DataSource(
        "akshare",
        ("a",),
        ("financials", "lhb", "announcements", "events"),
        "fallback",
        "library",
        "akshare",
        slow=True,
        optional_dependency="akshare",
    ),
    DataSource(
        "yfinance",
        ("hk", "us"),
        ("technical", "financials"),
        "fallback",
        "library",
        "yfinance",
        slow=True,
        optional_dependency="yfinance",
    ),
    DataSource(
        "search_news",
        ("a", "hk", "us"),
        ("news",),
        "fallback",
        "search",
        "search_news",
        slow=True,
    ),
    DataSource("securities_times", ("a",), ("news",), "fallback", "search", "securities_times", slow=True),
    DataSource("cs", ("a",), ("news",), "fallback", "search", "cs", slow=True),
    DataSource("cnstock", ("a",), ("news",), "fallback", "search", "cnstock", slow=True),
    DataSource(
        "browser_board",
        ("a",),
        ("boards",),
        "fallback",
        "browser",
        "browser_board",
        slow=True,
        optional_dependency="configured browser service or playwright",
    ),
    DataSource("cninfo", ("a",), ("announcements", "events"), "official", "http", "cninfo"),
    DataSource("hkexnews", ("hk",), ("announcements", "events"), "official", "http", "hkexnews"),
)

_TIER_ORDER = {"primary": 0, "fallback": 1, "official": 2}


def _allowed(source: DataSource, policy: SourcePolicy) -> bool:
    if source.access == "browser":
        return policy.browser_fallback
    if source.access in {"library", "search"}:
        return policy.rich_source
    if source.slow:
        return policy.rich_source
    return source.access == "http"


def find_sources(
    market: str,
    capability: str,
    policy: SourcePolicy | None = None,
    *,
    registry: tuple[DataSource, ...] = DATA_SOURCES,
) -> list[DataSource]:
    selected_policy = policy or SourcePolicy()
    matches = [
        source
        for source in registry
        if market in source.markets
        and capability in source.capabilities
        and _allowed(source, selected_policy)
    ]
    return sorted(matches, key=lambda source: _TIER_ORDER[source.tier])
