from young_stock.market_routes import route_board_data, route_fund_flow_data


def test_board_route_tries_direct_then_browser_service_then_playwright():
    calls = []

    result = route_board_data(
        "industry",
        "20260618",
        direct=lambda kind, date, limit: calls.append("direct") or {"rows": []},
        browser_service=lambda kind: calls.append("browser_service") or {"rows": []},
        playwright=lambda kind: calls.append("playwright") or {
            "rows": [{"name": "半导体", "change_pct": 2.0}]
        },
        browser_fallback=True,
    )

    assert calls == ["direct", "browser_service", "playwright"]
    assert result["rows"][0]["name"] == "半导体"


def test_board_route_does_not_mix_current_rows_into_historical_report():
    calls = []
    result = route_board_data(
        "industry",
        "20250101",
        direct=lambda kind, date, limit: calls.append("direct") or {"rows": []},
        browser_service=lambda kind: calls.append("browser_service") or {"rows": [{"name": "实时"}]},
        playwright=lambda kind: calls.append("playwright") or {"rows": [{"name": "实时"}]},
        current_trade_date="20260618",
        browser_fallback=True,
    )

    assert calls == ["direct"]
    assert result["_unavailable"] == "历史数据不可得"


def test_board_route_is_http_only_by_default():
    calls = []
    result = route_board_data(
        "industry",
        "20260618",
        direct=lambda kind, date, limit: calls.append("direct") or {"rows": []},
        browser_service=lambda kind: calls.append("browser_service") or {"rows": [{"name": "浏览器"}]},
        playwright=lambda kind: calls.append("playwright") or {"rows": [{"name": "浏览器"}]},
    )

    assert calls == ["direct"]
    assert result["rows"] == []


def test_fund_flow_route_uses_browser_before_local_record():
    calls = []
    result = route_fund_flow_data(
        "20260618",
        online_sources=[
            lambda date: calls.append("online-1") or {},
            lambda date: calls.append("online-2") or {},
        ],
        browser=lambda date: calls.append("browser") or {"date": "2026-06-18", "主力净流入": "10"},
        cached=lambda date: calls.append("cache") or {"date": "2026-06-17", "主力净流入": "5"},
    )

    assert calls == ["online-1", "online-2", "browser"]
    assert result["主力净流入"] == "10"
