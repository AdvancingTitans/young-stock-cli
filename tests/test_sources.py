from young_stock.health import SourceHealthBook
from young_stock.sources import (
    DATA_SOURCES,
    DataSource,
    SourcePolicy,
    SourceResolver,
    SourceResult,
    find_sources,
)


def test_registry_covers_requested_sources_and_metadata():
    required = {
        "eastmoney",
        "tencent",
        "sina",
        "ths",
        "mootdx",
        "cninfo",
        "hkexnews",
        "futu",
        "yahoo",
        "jin10",
        "cls",
        "aastocks",
        "investing",
        "companiesmarketcap",
        "securities_times",
        "cs",
        "cnstock",
    }

    assert required <= {source.id for source in DATA_SOURCES}
    assert all(source.markets for source in DATA_SOURCES)
    assert all(source.capabilities for source in DATA_SOURCES)
    assert all(source.access in {"http", "library", "browser", "search"} for source in DATA_SOURCES)
    assert all(source.tier in {"primary", "fallback", "official"} for source in DATA_SOURCES)


def test_default_policy_is_http_only_and_excludes_slow_sources():
    sources = find_sources("hk", "news")

    assert sources
    assert all(source.access == "http" and not source.slow for source in sources)
    assert "futu" not in {source.id for source in sources}


def test_registry_only_advertises_capabilities_with_runtime_adapters():
    by_id = {source.id: source for source in DATA_SOURCES}

    assert by_id["yahoo"].capabilities == ("history",)
    assert by_id["yfinance"].capabilities == ("technical", "financials")
    assert by_id["cninfo"].capabilities == ("announcements", "events")
    assert by_id["hkexnews"].capabilities == ("announcements", "events")
    assert {
        "flow",
        "margin",
        "lhb",
        "lockup",
        "holder_count",
        "block_trades",
        "dividend",
        "announcements",
        "research_reports",
        "classification",
    } <= set(by_id["eastmoney"].capabilities)


def test_rich_and_browser_sources_require_explicit_policy():
    rich = find_sources("us", "history", SourcePolicy(rich_source=True))
    browser = find_sources("a", "boards", SourcePolicy(browser_fallback=True))
    a_quote_rich = find_sources("a", "quote", SourcePolicy(rich_source=True))

    assert {source.id for source in rich} == {"eastmoney", "yahoo"}
    assert "mootdx" in {source.id for source in a_quote_rich}
    assert "mootdx" not in {source.id for source in find_sources("a", "quote")}
    assert "browser_board" in {source.id for source in browser}
    assert "browser_board" not in {
        source.id
        for source in find_sources(
            "a",
            "boards",
            SourcePolicy(rich_source=True, browser_fallback=False),
        )
    }


def test_resolver_tries_primary_before_fallback_and_official():
    registry = (
        DataSource("primary", ("a",), ("events",), "primary", "http", "primary"),
        DataSource("fallback", ("a",), ("events",), "fallback", "http", "fallback"),
        DataSource("official", ("a",), ("events",), "official", "http", "official"),
    )
    calls = []
    resolver = SourceResolver(registry=registry, health=SourceHealthBook())

    result = resolver.resolve(
        "a",
        "events",
        {
            "primary": lambda: calls.append("primary") or SourceResult(error="blocked", source="primary"),
            "fallback": lambda: calls.append("fallback") or SourceResult(error="empty", source="fallback"),
            "official": lambda: calls.append("official") or SourceResult(data={"rows": [1]}, source="official"),
        },
    )

    assert calls == ["primary", "fallback", "official"]
    assert result.source == "official"
    assert result.data == {"rows": [1]}
    assert result.attempts == ("primary: blocked", "fallback: empty", "official: ok")


def test_resolver_moves_unhealthy_source_to_end_of_same_tier():
    registry = (
        DataSource("weak", ("a",), ("quote",), "primary", "http", "weak"),
        DataSource("healthy", ("a",), ("quote",), "primary", "http", "healthy"),
    )
    health = SourceHealthBook(window_size=3)
    for _ in range(3):
        health.record("weak", ok=False, latency_ms=1)
    calls = []
    resolver = SourceResolver(registry=registry, health=health)

    result = resolver.resolve(
        "a",
        "quote",
        {
            "weak": lambda: calls.append("weak") or SourceResult(data={"price": 1}, source="weak"),
            "healthy": lambda: calls.append("healthy") or SourceResult(data={"price": 2}, source="healthy"),
        },
    )

    assert calls == ["healthy"]
    assert result.source == "healthy"


def test_resolver_does_not_promote_fallback_ahead_of_unhealthy_primary():
    registry = (
        DataSource("weak_primary", ("a",), ("quote",), "primary", "http", "weak_primary"),
        DataSource("fallback", ("a",), ("quote",), "fallback", "http", "fallback"),
    )
    health = SourceHealthBook(window_size=3)
    for _ in range(3):
        health.record("weak_primary", ok=False, latency_ms=1)
    calls = []
    resolver = SourceResolver(registry=registry, health=health)

    result = resolver.resolve(
        "a",
        "quote",
        {
            "weak_primary": lambda: calls.append("weak_primary")
            or SourceResult(data={"price": 1}, source="weak_primary"),
            "fallback": lambda: calls.append("fallback")
            or SourceResult(data={"price": 2}, source="fallback"),
        },
    )

    assert calls == ["weak_primary"]
    assert result.source == "weak_primary"


def test_resolver_reports_failures_without_raising_adapter_errors():
    source = DataSource("broken", ("us",), ("quote",), "primary", "http", "broken")
    resolver = SourceResolver(registry=(source,), health=SourceHealthBook())

    result = resolver.resolve(
        "us",
        "quote",
        {"broken": lambda: (_ for _ in ()).throw(RuntimeError("timeout"))},
    )

    assert result.data is None
    assert result.source == ""
    assert result.error == "all sources failed"
    assert result.attempts == ("broken: timeout",)
