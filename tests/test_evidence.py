import json
from types import SimpleNamespace

from young_stock.evidence import _quote_dict, build_daily_evidence, build_fund_evidence, build_stock_evidence
from young_stock.health import SourceHealthBook


def fake_core():
    quote = SimpleNamespace(
        symbol="600519",
        name="贵州茅台",
        market="cn_market",
        date="20260618",
        price=1500.0,
        change_pct=1.2,
        turnover=10_000_000,
        source="test",
        currency="CNY",
    )
    return SimpleNamespace(
        normalize_stock_symbol=lambda symbol: (symbol, "cn_market"),
        get_index=lambda date: [
            {"f12": "000001", "f14": "上证指数", "f2": 3000.0, "f3": 0.8, "f6": 500_000_000, "_source": "test"}
        ],
        fetch_hk_indices_sina=lambda symbols, date: [],
        fetch_us_indices_sina=lambda symbols, date: [],
        fetch_northbound_flow_snapshot=lambda date: {"date": date, "total_yi": 12.3, "_source": "test"},
        get_fund_flow=lambda date, strict_date=False: {"date": date, "主力净流入": 1_000_000, "_source": "test"},
        fetch_eastmoney_board_list=lambda kind, date, limit=100: {
            "rows": [{"name": "白酒", "change_pct": 2.0, "up_count": 8, "down_count": 2, "leader": "贵州茅台"}]
        },
        get_zt_pool=lambda date: {"data": {"tc": 2, "pool": [{"n": "甲", "c": "000001", "hybk": "白酒", "fbt": 93000, "zttj": {"days": 2}}]}},
        get_dt_pool=lambda date: {"data": {"tc": 1, "pool": [{"n": "乙", "c": "000002"}]}},
        get_zb_pool=lambda date: {"data": {"tc": 1, "pool": [{"n": "丙", "c": "000003"}]}},
        fetch_cn_stocks_sina=lambda symbols, date: [quote],
        fetch_cn_stocks_tencent=lambda symbols, date: [quote],
        fetch_cn_stocks_direct=lambda symbols, date: [quote],
        eastmoney_fast_news=lambda keyword, **kwargs: {"data": [{"title": "公司公告", "source": "eastmoney"}]},
        sina_roll_news=lambda keyword, **kwargs: {"data": []},
        futu_news_search=lambda keyword, **kwargs: {"data": []},
        get_single_stock_quote=lambda symbol, date: quote,
    )


def test_complete_evidence_has_six_modules_and_real_values():
    evidence = build_daily_evidence(
        fake_core(),
        "20260618",
        {"stocks": ["600519"], "funds": [], "positions": {"stocks": {}, "funds": {}}},
    )

    assert set(evidence.modules) == {"M1", "M2", "M3", "M4", "M5", "M6"}
    assert evidence.modules["M1"]["a_indices"][0]["price"] == 3000.0
    assert evidence.modules["M3"]["zt_count"] == 2
    assert evidence.modules["M4"]["blowup_ratio"] == 1 / 3
    assert evidence.meta["trade_date"] == "20260618"
    assert evidence.quality_score >= 80
    payload = evidence.to_dict()
    json.dumps(payload, ensure_ascii=False)
    assert payload["schema_version"] == 1
    assert payload["_meta"]["requested_date"] == "20260618"
    assert payload["_meta"]["as_of"] == "20260618"


def test_quote_evidence_preserves_quality_and_provenance_fields():
    payload = _quote_dict(
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "market": "cn_market",
            "date": "2026-07-14",
            "price": 1500.0,
            "source": "sina",
            "source_url": "https://example.com/quote",
            "requested_date": "20260714",
            "quality_flags": ["turnover_missing"],
            "notes": ["fallback enrichment unavailable"],
            "completeness": 80.0,
        }
    )

    assert payload["source_url"] == "https://example.com/quote"
    assert payload["requested_date"] == "20260714"
    assert payload["quality_flags"] == ["turnover_missing"]
    assert payload["notes"] == ["fallback enrichment unavailable"]
    assert payload["completeness"] == 80.0


def test_daily_evidence_uses_compressed_news_radar_when_core_provides_it():
    core = fake_core()
    calls = []

    def fake_news_radar(*, mode, date_str, profile=None, rich_source=False, **kwargs):
        calls.append((mode, date_str, profile, rich_source, kwargs))
        return {
            "raw_count": 12,
            "event_count": 1,
            "events": [{"title": "raw title that should not enter evidence"}],
            "compressed": {"events": [{"title": "Fed holds rates", "sources": ["Reuters"]}]},
            "truncated": True,
        }

    core.fetch_news_radar = fake_news_radar

    evidence = build_daily_evidence(core, "20260618", {"stocks": ["600519"], "industries": ["semiconductor"]})

    assert calls[0][0:4] == ("daily", "20260618", {"stocks": ["600519"], "industries": ["semiconductor"]}, False)
    assert evidence.modules["M1"]["news_radar"] == {"events": [{"title": "Fed holds rates", "sources": ["Reuters"]}]}
    assert evidence.meta["news_radar"] == {"raw_count": 12, "event_count": 1, "truncated": True}
    assert "raw title that should not enter evidence" not in json.dumps(evidence.to_dict(), ensure_ascii=False)


def test_missing_modules_lower_quality_without_fabricating_zero():
    core = fake_core()
    core.fetch_eastmoney_board_list = lambda kind, date, limit=100: {"rows": []}
    core.get_fund_flow = lambda date, strict_date=False: {"_unavailable": "not disclosed"}
    core.get_zt_pool = lambda date: {"_error": "unavailable"}
    core.get_dt_pool = lambda date: {"_error": "unavailable"}
    core.get_zb_pool = lambda date: {"_error": "unavailable"}

    evidence = build_daily_evidence(core, "20260618", {"stocks": [], "funds": []})

    assert evidence.quality_score < 60
    assert {"M2", "M3", "M4", "M6"} <= set(evidence.missing_modules)
    assert evidence.modules["M3"]["zt_count"] is None
    assert evidence.meta["degrade_mode"] == "simplified"
    assert evidence.meta["supplemental_evidence"]["missing_modules"] == evidence.missing_modules
    assert "M2" in evidence.meta["supplemental_evidence"]["candidates"]


def test_board_evidence_uses_browser_rows_when_lightweight_source_is_empty():
    core = fake_core()
    core.BROWSER_FALLBACK = True
    core.fetch_eastmoney_board_list = lambda kind, date, limit=100: {"rows": []}
    core.browser_board_list = lambda kind: {
        "rows": [{"name": f"{kind}-浏览器", "change_pct": 1.5, "up_count": 6, "down_count": 2}]
    }

    evidence = build_daily_evidence(core, "20260618", {"stocks": [], "funds": []})

    assert evidence.modules["M2"]["available"] is True
    assert evidence.modules["M2"]["industry"][0]["name"] == "industry-浏览器"
    assert evidence.modules["M2"]["concept"][0]["name"] == "concept-浏览器"


def test_fund_flow_keeps_module_two_available_when_board_rows_are_missing():
    core = fake_core()
    core.fetch_eastmoney_board_list = lambda kind, date, limit=100: {"rows": []}
    core.browser_board_list = lambda kind: {"rows": []}

    evidence = build_daily_evidence(core, "20260618", {"stocks": [], "funds": []})

    assert evidence.modules["M2"]["available"] is True
    assert evidence.modules["M2"]["fund_flow"]["主力净流入"] == 1_000_000


def test_stock_evidence_includes_quote_flow_trades_and_news():
    core = fake_core()
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": [{"date": date, "main_net": 10}]}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": [{"date": date, "amount": 20}]}
    core.eastmoney_fast_news = lambda keyword, **kwargs: {"data": [{"title": "公司公告", "source": "test"}]}
    core._news_aliases = lambda symbol, name="": [symbol, name]

    evidence = build_stock_evidence(core, "600519", "20260618")

    stock = evidence.modules["STOCK"]
    assert stock["quote"]["symbol"] == "600519"
    assert stock["fund_flow"]["rows"]
    assert stock["block_trades"]["rows"]
    assert stock["news"]["data"][0]["title"] == "公司公告"


def test_stock_evidence_uses_stock_scoped_compressed_news_radar():
    core = fake_core()
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": []}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": []}
    core.eastmoney_fast_news = lambda *args, **kwargs: {"data": []}
    core._news_aliases = lambda symbol, name="": [symbol, name]
    core.fetch_a_share_extensions = lambda symbol, date, rich_source=False: {
        "classification": {"industry": ["白酒"], "concepts": ["消费"]}
    }
    calls = []

    def fake_news_radar(*, mode, date_str, symbol=None, stock_context=None, rich_source=False, **kwargs):
        calls.append((mode, date_str, symbol, stock_context, rich_source, kwargs))
        return {
            "raw_count": 8,
            "event_count": 1,
            "events": [{"title": "uncompressed stock news"}],
            "compressed": {"events": [{"title": "贵州茅台公告", "sources": ["东方财富"]}]},
            "truncated": False,
        }

    core.fetch_news_radar = fake_news_radar

    evidence = build_stock_evidence(core, "600519", "20260618", rich_source=True)

    stock = evidence.modules["STOCK"]
    assert stock["news_radar"] == {"events": [{"title": "贵州茅台公告", "sources": ["东方财富"]}]}
    assert calls[0][0:3] == ("stock", "20260618", "600519")
    assert set(calls[0][3]["company_keywords"]) == {"600519", "贵州茅台"}
    assert calls[0][3]["industry_keywords"] == ["白酒", "消费"]
    assert calls[0][4] is True
    assert "uncompressed stock news" not in json.dumps(evidence.to_dict(), ensure_ascii=False)


def test_stock_evidence_maps_a_share_extensions_to_modules_and_risk_calendar():
    core = fake_core()
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": []}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": []}
    core.eastmoney_fast_news = lambda *args, **kwargs: {"data": []}
    core._news_aliases = lambda symbol, name="": [symbol, name]
    core.fetch_a_share_extensions = lambda symbol, date, rich_source=False: {
        "stock_fund_flow": {"rows": [{"date": date, "main_net_yuan": 100}], "mapping": "stock.M2"},
        "margin": {"rows": [{"date": date, "fin_balance_yuan": 200}], "mapping": "stock.M4"},
        "lhb": {"rows": [{"date": date, "net_buy_yuan": 300}], "mapping": "stock.M3"},
        "lockup": {"rows": [{"date": "2026-06-20", "lift_market_cap_yuan": 400}], "mapping": "risk_calendar"},
        "holder_count": {"rows": [{"date": "2026-03-31", "holder_count": 123}], "mapping": "stock.M5"},
        "block_trades": {"rows": [{"date": date, "amount_yuan": 500}], "mapping": "stock.M5"},
        "dividend": {"rows": [{"date": "2026-06-25", "cash_dividend_per_10": 6}], "mapping": "risk_calendar"},
        "announcements": {"rows": [{"date": date, "title": "重大事项"}], "mapping": "risk_calendar"},
        "research_reports": {"rows": [{"date": date, "title": "点评"}], "mapping": "stock.supplemental"},
        "classification": {"industry": ["白酒"], "concepts": ["国企改革"], "mapping": "stock.M2/M5/M6"},
        "rich_source_skipped": ["mootdx", "level2_orderbook", "tick_trades", "full_financials", "pdf_reports"],
    }

    evidence = build_stock_evidence(core, "600519", "20260618")

    stock = evidence.modules["STOCK"]
    assert stock["a_share_extensions"]["stock_fund_flow"]["rows"][0]["main_net_yuan"] == 100
    assert evidence.modules["M2"]["a_share_classification"]["industry"] == ["白酒"]
    assert evidence.modules["M3"]["lhb"]["rows"][0]["net_buy_yuan"] == 300
    assert evidence.modules["M4"]["margin"]["rows"][0]["fin_balance_yuan"] == 200
    assert evidence.modules["M5"]["holder_count"]["rows"][0]["holder_count"] == 123
    assert evidence.modules["M6"]["a_share_classification"]["concepts"] == ["国企改革"]
    assert evidence.meta["risk_calendar"] == [
        {"type": "lockup", "date": "2026-06-20", "lift_market_cap_yuan": 400},
        {"type": "dividend", "date": "2026-06-25", "cash_dividend_per_10": 6},
        {"type": "announcements", "date": "20260618", "title": "重大事项"},
    ]
    assert "mootdx" in stock["a_share_extensions"]["rich_source_skipped"]


def test_stock_evidence_quote_resolution_uses_source_health_fallback():
    core = fake_core()
    calls = []
    quote_primary = SimpleNamespace(symbol="600519", name="茅台", market="cn_market", date="20260618", price=1.0, source="sina")
    quote_fallback = SimpleNamespace(symbol="600519", name="茅台", market="cn_market", date="20260618", price=2.0, source="tencent")
    core.fetch_cn_stocks_sina = lambda symbols, date: calls.append("sina") or [quote_primary]
    core.fetch_cn_stocks_tencent = lambda symbols, date: calls.append("tencent") or [quote_fallback]
    core.fetch_cn_stocks_direct = lambda symbols, date: calls.append("eastmoney") or []
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": []}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": []}
    core.eastmoney_fast_news = lambda *args, **kwargs: {"data": []}
    core._news_aliases = lambda symbol, name="": [symbol, name]
    health = SourceHealthBook(window_size=3)
    for _ in range(3):
        health.record("sina", ok=False, latency_ms=1)

    evidence = build_stock_evidence(core, "600519", "20260618", health=health)

    assert evidence.modules["STOCK"]["quote"]["price"] == 2.0
    assert calls == ["eastmoney", "tencent"]
    assert "sina" not in calls
    assert evidence.meta["source_events"][0].startswith("quote:tencent")


def test_stock_evidence_omits_optional_sections_when_resolved_unavailable():
    core = fake_core()
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": [], "_error": "down"}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": [], "_error": "down"}
    core.eastmoney_fast_news = lambda *args, **kwargs: {"data": [], "source": "none", "all_count": 0}
    core._news_aliases = lambda symbol, name="": [symbol, name]

    evidence = build_stock_evidence(core, "600519", "20260618")

    stock = evidence.modules["STOCK"]
    assert "fund_flow" not in stock
    assert "block_trades" not in stock
    assert "news" not in stock


def test_fund_evidence_includes_profile_and_stock_scoped_news_radar_for_holdings():
    core = fake_core()
    core.normalize_fund_code = lambda code: code
    core.fetch_fund_estimate = lambda code, date: {
        "fundcode": code,
        "name": "招商中证白酒指数",
        "estimate_nav": 1.23,
        "estimate_change_pct": 0.8,
        "_source": "eastmoney_fund",
        "date": date,
    }
    core.fetch_fund_profile = lambda code, date: {
        "returns": {"近1年": 12.3},
        "fees": {"front_end_rate_pct": 0.12},
        "scale": {"latest_size_yi": 88.6, "asof": "2026-06-30"},
        "managers": [{"name": "张三", "work_time": "5年"}],
        "_source": "eastmoney_pingzhongdata",
    }
    core.fetch_fund_holdings = lambda code, date, limit=10: {
        "asof": "2026-03-31",
        "holdings": [
            {"code": "600519", "name": "贵州茅台", "weight_pct": 18.0},
            {"code": "000858", "name": "五粮液", "weight_pct": 8.0},
        ],
    }
    core.fetch_fund_holding_quotes = lambda holdings, date: {
        "600519": SimpleNamespace(symbol="600519", name="贵州茅台", market="cn_market", date=date, price=1500, change_pct=1.0, source="test"),
    }
    calls = []

    def fake_news_radar(*, mode, date_str, symbol=None, stock_context=None, rich_source=False, **kwargs):
        calls.append((mode, date_str, symbol, stock_context, rich_source, kwargs))
        return {
            "raw_count": 6,
            "event_count": 1,
            "compressed": {"events": [{"title": "白酒批价改善", "sources": ["东方财富"]}]},
            "truncated": False,
        }

    core.fetch_news_radar = fake_news_radar

    evidence = build_fund_evidence(core, "161725", "20260618", rich_source=True)

    fund = evidence.modules["FUND"]
    assert fund["profile"]["returns"]["近1年"] == 12.3
    assert fund["profile"]["fees"]["front_end_rate_pct"] == 0.12
    assert fund["holding_news_radar"] == {"events": [{"title": "白酒批价改善", "sources": ["东方财富"]}]}
    assert calls[0][0:3] == ("fund", "20260618", "161725")
    assert {"600519", "贵州茅台", "000858", "五粮液"} <= set(calls[0][3]["company_keywords"])
    assert calls[0][3]["industry_keywords"] == ["基金重仓股", "白酒"]
    assert evidence.meta["news_radar"]["event_count"] == 1
