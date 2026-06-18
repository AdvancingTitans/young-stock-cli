import json
from types import SimpleNamespace

from young_stock.evidence import build_daily_evidence, build_stock_evidence


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
    json.dumps(evidence.to_dict(), ensure_ascii=False)


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


def test_board_evidence_uses_browser_rows_when_lightweight_source_is_empty():
    core = fake_core()
    core.fetch_eastmoney_board_list = lambda kind, date, limit=100: {"rows": []}
    core.camofox_board_list = lambda kind: {
        "rows": [{"name": f"{kind}-浏览器", "change_pct": 1.5, "up_count": 6, "down_count": 2}]
    }

    evidence = build_daily_evidence(core, "20260618", {"stocks": [], "funds": []})

    assert evidence.modules["M2"]["available"] is True
    assert evidence.modules["M2"]["industry"][0]["name"] == "industry-浏览器"
    assert evidence.modules["M2"]["concept"][0]["name"] == "concept-浏览器"


def test_fund_flow_keeps_module_two_available_when_board_rows_are_missing():
    core = fake_core()
    core.fetch_eastmoney_board_list = lambda kind, date, limit=100: {"rows": []}
    core.camofox_board_list = lambda kind: {"rows": []}

    evidence = build_daily_evidence(core, "20260618", {"stocks": [], "funds": []})

    assert evidence.modules["M2"]["available"] is True
    assert evidence.modules["M2"]["fund_flow"]["主力净流入"] == 1_000_000


def test_stock_evidence_includes_quote_flow_trades_and_news():
    core = fake_core()
    core.fetch_stock_fund_flow_daily = lambda symbol, date, limit=20: {"rows": [{"date": date, "main_net": 10}]}
    core.fetch_block_trades = lambda symbol, date, limit=10: {"rows": [{"date": date, "amount": 20}]}
    core.combined_news_search = lambda keyword, **kwargs: {"data": [{"title": "公司公告", "source": "test"}]}
    core._news_aliases = lambda symbol, name="": [symbol, name]

    evidence = build_stock_evidence(core, "600519", "20260618")

    stock = evidence.modules["STOCK"]
    assert stock["quote"]["symbol"] == "600519"
    assert stock["fund_flow"]["rows"]
    assert stock["block_trades"]["rows"]
    assert stock["news"]["data"][0]["title"] == "公司公告"
