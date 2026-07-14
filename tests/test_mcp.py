import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from young_stock.health import SourceHealthBook


def _quote(symbol="600519", *, date="20260707", price=1500.0, source="sina"):
    return SimpleNamespace(
        symbol=symbol,
        name="贵州茅台",
        market="cn_market",
        date=date,
        price=price,
        change_pct=1.2,
        turnover=10_000_000,
        source=source,
        currency="CNY",
    )


def _core():
    quote = _quote()
    return SimpleNamespace(
        normalize_stock_symbol=lambda symbol: (symbol, "cn_market"),
        nearest_trade_date=lambda: "20260707",
        get_index=lambda date: [
            {
                "f12": "000001",
                "f14": "上证指数",
                "f2": 3000.0,
                "f3": 0.8,
                "f6": 500_000_000,
                "_source": "test",
                "_source_date": "20260707",
            }
        ],
        fetch_hk_indices_sina=lambda symbols, date: [],
        fetch_us_indices_sina=lambda symbols, date: [],
        fetch_northbound_flow_snapshot=lambda date: {"date": date, "total_yi": 12.3, "_source": "test"},
        get_fund_flow=lambda date, strict_date=False: {
            "date": "2026-07-07",
            "主力净流入": 1_000_000,
            "_source": "test-flow",
        },
        fetch_eastmoney_board_list=lambda kind, date, limit=100: {
            "rows": [{"name": "白酒", "change_pct": 2.0, "up_count": 8, "down_count": 2, "leader": "贵州茅台"}],
            "_source": "test-board",
        },
        get_zt_pool=lambda date: {
            "_source": "test-emotion",
            "as_of": "20260707",
            "data": {"tc": 1, "pool": [{"n": "甲", "c": "000001", "hybk": "白酒", "fbt": 93000, "zttj": {"days": 2}}]},
        },
        get_dt_pool=lambda date: {"_source": "test-emotion", "as_of": "20260707", "data": {"tc": 0, "pool": []}},
        get_zb_pool=lambda date: {"_source": "test-emotion", "as_of": "20260707", "data": {"tc": 0, "pool": []}},
        fetch_cn_stocks_sina=lambda symbols, date: [quote],
        fetch_cn_stocks_tencent=lambda symbols, date: [quote],
        fetch_cn_stocks_direct=lambda symbols, date: [quote],
        fetch_stock_fund_flow_daily=lambda symbol, date, limit=20: {
            "rows": [{"date": "2026-07-07", "main_net": 10}],
            "latest_date": "2026-07-07",
            "_source": "test-stock-flow",
        },
        fetch_block_trades=lambda symbol, date, limit=10: {"rows": []},
        eastmoney_fast_news=lambda keyword, **kwargs: {"data": [{"title": "公司公告", "source": "eastmoney"}]},
        sina_roll_news=lambda keyword, **kwargs: {"data": []},
        futu_news_search=lambda keyword, **kwargs: {"data": []},
        _news_aliases=lambda symbol, name="": [symbol, name],
        fetch_a_share_extensions=lambda symbol, date, rich_source=False: {
            "announcements": {"rows": [{"date": date, "title": "公告"}], "_source": "eastmoney-ann"},
            "research_reports": {"rows": [{"date": date, "title": "点评"}], "_source": "eastmoney-research"},
            "classification": {"industry": ["白酒"], "concepts": []},
        },
        normalize_fund_code=lambda code: code,
        fetch_fund_estimate=lambda code, date: {
            "fundcode": code,
            "name": "测试基金",
            "date": "2026-07-07",
            "estimate_nav": "1.0",
            "_source": "test-fund",
        },
        fetch_fund_holdings=lambda code, date, limit=10: {"holdings": [], "title": "测试基金", "_source": "test-fund"},
    )


def _jsonrpc(message):
    raw = json.dumps(message, ensure_ascii=False).encode()
    return f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw


def test_tool_schemas_are_read_only_and_exclude_write_tools():
    from young_stock.mcp_server import TOOL_NAMES, list_tools

    tools = list_tools()
    names = {tool["name"] for tool in tools}

    assert set(TOOL_NAMES) == names
    assert {
        "get_quote",
        "get_market_indices",
        "get_market_emotion",
        "get_daily_evidence",
        "get_stock_evidence",
        "get_fund_evidence",
        "get_stock_news",
        "get_announcements",
        "get_research_reports",
        "get_fund_flow",
        "get_source_health",
    } == names
    forbidden = ("add", "update", "delete", "clear", "send", "trade", "buy", "sell", "shell", "file", "memory", "profile", "diary")
    assert not any(token in name for name in names for token in forbidden)
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)
    assert all(tool["inputSchema"]["type"] == "object" for tool in tools)


def test_parameter_validation_rejects_bad_date_and_missing_symbol():
    from young_stock.mcp_server import MCPToolError, YoungMCPTools

    tools = YoungMCPTools(core=_core())

    with pytest.raises(MCPToolError, match="symbol"):
        tools.call("get_quote", {"date": "20260707"})
    with pytest.raises(MCPToolError, match="YYYYMMDD"):
        tools.call("get_daily_evidence", {"date": "2026/07/07"})


def test_quote_uses_source_resolver_and_standard_response_shape():
    from young_stock.mcp_server import YoungMCPTools

    core = _core()
    health = SourceHealthBook(window_size=3)
    for _ in range(3):
        health.record("sina", ok=False, latency_ms=1)
    calls = []
    core.fetch_cn_stocks_sina = lambda symbols, date: calls.append("sina") or [_quote(source="sina", price=1.0)]
    core.fetch_cn_stocks_tencent = lambda symbols, date: calls.append("tencent") or [_quote(source="tencent", price=2.0)]
    core.fetch_cn_stocks_direct = lambda symbols, date: calls.append("eastmoney") or []

    result = YoungMCPTools(core=core, health=health).call("get_quote", {"symbol": "600519", "date": "20260707"})

    assert calls == ["eastmoney", "tencent"]
    assert result["requested_date"] == "20260707"
    assert result["as_of"] == "20260707"
    assert result["source"] == "tencent"
    assert result["stale"] is False
    assert result["missing"] == []
    assert result["evidence"]["quote"]["price"] == 2.0


def test_stock_slices_reuse_stock_evidence_service(monkeypatch):
    import young_stock.mcp_server as mcp_server
    from young_stock.evidence import EvidenceBundle
    from young_stock.mcp_server import YoungMCPTools

    calls = []

    def fake_stock_evidence(core, symbol, trade_date, **kwargs):
        calls.append((core, symbol, trade_date, kwargs))
        return EvidenceBundle(
            modules={
                "STOCK": {
                    "available": True,
                    "news": {"data": [{"title": "新闻"}], "_source": "eastmoney-news"},
                    "a_share_extensions": {
                        "announcements": {"rows": [{"title": "公告"}], "_source": "eastmoney-ann"},
                        "research_reports": {"rows": [{"title": "研报"}], "_source": "eastmoney-research"},
                    },
                }
            },
            meta={"trade_date": "20260707", "report_type": "single-stock"},
        )

    monkeypatch.setattr(mcp_server, "build_stock_evidence", fake_stock_evidence)
    tools = YoungMCPTools(core=_core())

    news = tools.call("get_stock_news", {"symbol": "600519", "date": "20260707"})
    ann = tools.call("get_announcements", {"symbol": "600519", "date": "20260707"})
    reports = tools.call("get_research_reports", {"symbol": "600519", "date": "20260707"})

    assert [call[1:3] for call in calls] == [
        ("600519", "20260707"),
        ("600519", "20260707"),
        ("600519", "20260707"),
    ]
    assert news["evidence"]["news"]["data"][0]["title"] == "新闻"
    assert ann["evidence"]["announcements"]["rows"][0]["title"] == "公告"
    assert reports["evidence"]["research_reports"]["rows"][0]["title"] == "研报"


def test_missing_data_and_date_fallback_are_explicit():
    from young_stock.mcp_server import YoungMCPTools

    core = _core()
    core.fetch_cn_stocks_sina = lambda symbols, date: []
    core.fetch_cn_stocks_tencent = lambda symbols, date: []
    core.fetch_cn_stocks_direct = lambda symbols, date: []
    core.get_fund_flow = lambda date, strict_date=False: {
        "date": "2026-07-05",
        "_requested_date": "2026-07-07",
        "_date_note": "latest_available",
        "_source": "test-flow",
    }

    tools = YoungMCPTools(core=core)
    quote = tools.call("get_quote", {"symbol": "600519", "date": "20260707"})
    flow = tools.call("get_fund_flow", {"date": "20260707"})

    assert "quote" in quote["missing"]
    assert quote["warnings"]
    assert flow["requested_date"] == "20260707"
    assert flow["as_of"] == "20260705"
    assert flow["stale"] is True


def test_source_health_returns_snapshots():
    from young_stock.mcp_server import YoungMCPTools

    health = SourceHealthBook(window_size=3)
    health.record("eastmoney", ok=True, latency_ms=20)
    health.record("sina", ok=False, latency_ms=5)

    result = YoungMCPTools(core=_core(), health=health).call("get_source_health", {"sources": ["eastmoney", "sina"]})

    assert result["source"] == "young_source_health"
    assert result["evidence"]["health"]["eastmoney"]["attempts"] == 1
    assert result["evidence"]["health"]["sina"]["failures"] == 1


def test_unknown_write_tool_is_not_callable():
    from young_stock.mcp_server import MCPToolError, YoungMCPTools

    with pytest.raises(MCPToolError, match="unknown tool"):
        YoungMCPTools(core=_core()).call("profile_add", {"symbol": "600519"})


def test_mcp_jsonrpc_initialize_tools_call_and_exit(monkeypatch):
    import young_stock.mcp_server as mcp_server
    from young_stock.cli import cli

    monkeypatch.setattr(mcp_server, "_core", _core())
    payload = b"".join(
        [
            _jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            _jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            _jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "get_quote", "arguments": {"symbol": "600519", "date": "20260707"}},
                }
            ),
            _jsonrpc({"jsonrpc": "2.0", "id": 4, "method": "shutdown", "params": {}}),
        ]
    )

    result = CliRunner().invoke(cli, ["mcp"], input=payload)

    assert result.exit_code == 0
    assert '"serverInfo"' in result.output
    assert '"tools"' in result.output
    assert '"get_quote"' in result.output
    assert "贵州茅台" in result.output
