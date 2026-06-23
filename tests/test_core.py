import inspect
from datetime import datetime

import pytest

from young_stock import _core, reports


@pytest.fixture(autouse=True)
def disable_ths_flow_network(monkeypatch):
    monkeypatch.setattr(_core, "fetch_ths_concept_money_flow_snapshot", lambda date_str: {})


def test_daily_report_internal_api_no_longer_exposes_only_or_quick():
    assert "only" not in inspect.signature(_core.run_daily_report).parameters
    assert "quick" not in inspect.signature(_core.run_daily_report).parameters
    assert "only" not in inspect.signature(reports.run_daily_report).parameters
    assert "quick" not in inspect.signature(reports.run_daily_report).parameters


def test_format_helpers():
    assert _core.fmt_price(12.345) == "12.35"
    assert _core.fmt_pct(1.234).endswith("%")
    assert "亿" in _core.fmt_amount(1.5e8) or "万" in _core.fmt_amount(1.5e8)


def test_detect_market_type():
    assert _core.detect_market_type("000001") == "cn_market"
    assert _core.detect_market_type("0700.HK") == "hk_market"
    assert _core.detect_market_type("AAPL") == "us_market"
    assert _core.detect_market_type("N225") == "jp_market"


def test_normalize_single_stock_symbol():
    assert _core.normalize_stock_symbol("600519") == ("600519", "cn_market")
    assert _core.normalize_stock_symbol("000001.SZ") == ("000001", "cn_market")
    assert _core.normalize_stock_symbol("0700") == ("0700.HK", "hk_market")
    assert _core.normalize_stock_symbol("700.hk") == ("0700.HK", "hk_market")
    assert _core.normalize_stock_symbol("AAPL") == ("AAPL", "us_market")


def test_cache_key_deterministic():
    a = _core._cache_key("000001", "20250101", "em")
    b = _core._cache_key("000001", "20250101", "em")
    assert a == b


def test_cache_load_missing_entry_does_not_create_directory(monkeypatch, tmp_path):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(_core, "CACHE_DIR", cache_dir)

    assert _core.cache_load("index_all", "20260612", "eastmoney") is None
    assert not cache_dir.exists()


def test_get_index_ignores_invalid_cached_shape(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: {"data": {"diff": "bad-shape"}})
    monkeypatch.setattr(_core, "fetch_json", lambda *args, **kwargs: {"_error": "blocked"})
    monkeypatch.setattr(_core, "_fetch_a_indices_sina", lambda: [])
    monkeypatch.setattr(_core, "_fetch_a_indices_tencent", lambda: [])

    assert _core.get_index("20260612") == []


def test_hk_indices_use_full_hsi_quote_with_volume(monkeypatch):
    def fake_fetch_sina_batch(codes):
        assert "hkHSI" in codes
        return {
            "hkHSI": [
                "HSI", "恒生指数", "25161.520", "25006.160", "25313.330", "25055.800",
                "25199.990", "193.830", "0.775", "0.00000", "0.00000", "363571783",
                "22858777046", "0.000", "0.000", "28056.100", "22668.350", "2026/05/29", "16:08",
            ],
        }

    monkeypatch.setattr(_core, "fetch_sina_batch", fake_fetch_sina_batch)

    quotes = _core.fetch_hk_indices_sina({"^HSI": "恒生指数"}, "20260529")

    assert len(quotes) == 1
    assert quotes[0].name == "恒生指数"
    assert quotes[0].volume == 22858777046
    assert "volume_missing_index" not in quotes[0].quality_flags


def test_sina_a_stock_quote_uses_source_trade_date():
    fields = [
        "贵州茅台", "1270.600", "1275.980", "1326.000", "1329.000", "1270.000",
        "1325.990", "1326.000", "7647805", "10037388211.000", "100", "1325.990",
        "200", "1325.900", "800", "1325.880", "100", "1325.870", "100",
        "1325.860", "434", "1326.000", "100", "1326.040", "100", "1326.050",
        "700", "1326.090", "200", "1326.100", "2026-05-29", "15:00:02", "00", "",
    ]

    qd = _core._sina_a_to_quote(fields, "600519", "20260601")

    assert qd is not None
    assert qd.name == "贵州茅台"
    assert qd.market == "cn_market"
    assert qd.date == "2026-05-29"
    assert qd.price == 1326.0
    assert round(qd.change_pct or 0, 2) == 3.92
    assert qd.turnover == 10037388211.0
    assert qd.source == "sina"


def test_get_single_stock_quote_uses_hk_fallback_chain(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "fetch_hk_stocks_sina", lambda symbols, date: [])
    monkeypatch.setattr(_core, "fetch_hk_stocks_tencent", lambda symbols, date: [])

    fallback = _core.QuoteData(
        symbol="0700.HK",
        name="腾讯控股",
        market="hk_market",
        date="2026-05-29",
        price=427.2,
        prev_close=425.0,
        change=2.2,
        change_pct=0.518,
        volume=48005475,
        currency="HKD",
        source="eastmoney_stock_get",
        completeness=100,
    )
    monkeypatch.setattr(_core, "fetch_hk_stocks_direct", lambda symbols, date: [fallback])
    monkeypatch.setattr(_core, "fetch_em_stocks", lambda *args, **kwargs: [])

    qd = _core.get_single_stock_quote("0700", "20260529")

    assert qd is not None
    assert qd.symbol == "0700.HK"
    assert qd.name == "腾讯控股"
    assert qd.source == "eastmoney_stock_get"


def test_fetch_stock_fund_flow_daily_parses_hk_push2his(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    seen = {}

    def fake_fetch_json(url, headers=None):
        seen["url"] = url
        return {
            "data": {
                "code": "00700",
                "market": 116,
                "name": "腾讯控股",
                "klines": ["2026-06-12,-447621104.0,323693584.0,-80154432.0,-291691920.0,-155929184.0,-4.33"],
            }
        }

    monkeypatch.setattr(_core, "fetch_json", fake_fetch_json)

    data = _core.fetch_stock_fund_flow_daily("0700.HK", "20260612", limit=3)

    assert "secid=116.00700" in seen["url"]
    assert data["symbol"] == "0700.HK"
    assert data["market"] == "hk_market"
    assert data["name"] == "腾讯控股"
    assert data["rows"][0]["date"] == "2026-06-12"
    assert data["rows"][0]["main_net"] == -447621104.0
    assert data["rows"][0]["main_pct"] == -4.33


def test_fetch_northbound_flow_snapshot_parses_ths(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        _core,
        "_fetch_raw",
        lambda *args, **kwargs: '{"time":["09:30","15:00"],"hgt":[1.2,3.4],"sgt":[0.8,1.1]}',
    )

    data = _core.fetch_northbound_flow_snapshot("20260612")

    assert data["latest_time"] == "15:00"
    assert data["hgt_yi"] == 3.4
    assert data["sgt_yi"] == 1.1
    assert data["total_yi"] == 4.5
    assert data["points"] == 2


def test_fetch_block_trades_parses_datacenter_rows(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)

    def fake_datacenter(report_name, **kwargs):
        assert report_name == "RPT_DATA_BLOCKTRADE"
        assert kwargs["filter_str"] == '(SECURITY_CODE="600519")'
        return [
            {
                "SECURITY_CODE": "600519",
                "SECURITY_NAME_ABBR": "贵州茅台",
                "TRADE_DATE": "2026-06-12 00:00:00",
                "DEAL_PRICE": 1227.32,
                "CLOSE_PRICE": 1291.91,
                "DEAL_VOLUME": 143200,
                "DEAL_AMT": 175721500,
                "BUYER_NAME": "买方席位",
                "SELLER_NAME": "卖方席位",
            }
        ]

    monkeypatch.setattr(_core, "eastmoney_datacenter", fake_datacenter)

    data = _core.fetch_block_trades("600519", "20260612", limit=5)

    assert data["symbol"] == "600519"
    assert data["name"] == "贵州茅台"
    assert data["rows"][0]["date"] == "2026-06-12"
    assert data["rows"][0]["price"] == 1227.32
    assert data["rows"][0]["premium_pct"] == -5.0
    assert data["rows"][0]["buyer"] == "买方席位"


def test_fetch_eastmoney_board_list_parses_industry_rows(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    seen = {}

    def fake_fetch_json(url, headers=None):
        seen["url"] = url
        return {
            "data": {
                "diff": [
                    {"f14": "半导体", "f12": "BK1036", "f3": 2.34, "f104": 80, "f105": 12, "f140": "测试龙头", "f136": 8.8},
                ]
            }
        }

    monkeypatch.setattr(_core, "fetch_json", fake_fetch_json)

    data = _core.fetch_eastmoney_board_list("industry", "20260612")

    assert "fs=m%3A90%2Bt%3A2" in seen["url"]
    assert data["rows"][0]["name"] == "半导体"
    assert data["rows"][0]["change_pct"] == 2.34
    assert data["rows"][0]["up_count"] == 80
    assert data["rows"][0]["leader"] == "测试龙头"


def test_get_board_list_uses_browser_when_lightweight_source_is_empty(monkeypatch):
    monkeypatch.setattr(_core, "BROWSER_FALLBACK", True)
    monkeypatch.setattr(_core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(
        _core,
        "fetch_eastmoney_board_list",
        lambda board_type, date_str, limit=100: {"rows": [], "_error": "temporarily unavailable"},
    )
    monkeypatch.setattr(
        _core,
        "browser_board_list",
        lambda board_type: {"rows": [{"name": "半导体", "change_pct": 2.34}]},
    )

    data = _core.get_board_list("industry", "20260618")

    assert data["rows"][0]["name"] == "半导体"


def test_parse_browser_board_snapshot_returns_structured_rows():
    markdown = (
        'row "1  半导体  2.34%  80  12  测试龙头  8.80%"\n'
        'row "2  白酒  -1.20%  15  40  贵州茅台  -0.50%"\n'
    )

    rows = _core._parse_browser_board_snapshot(markdown)

    assert rows[0] == {
        "rank": 1,
        "name": "半导体",
        "change_pct": 2.34,
        "up_count": 80,
        "down_count": 12,
        "leader": "测试龙头",
        "leader_change_pct": 8.8,
    }
    assert rows[1]["change_pct"] == -1.2


def test_print_boards_supports_structured_rows(capsys):
    _core.print_boards(
        {"rows": [{"name": "半导体", "change_pct": 2.34, "up_count": 80, "down_count": 12, "leader": "测试龙头"}]},
        "行业板块涨幅",
    )

    output = capsys.readouterr().out
    assert "行业板块涨幅" in output
    assert "半导体" in output
    assert "测试龙头" in output


def test_tencent_hk_stock_quote_adds_valuation_fields():
    fields = (
        "100~腾讯控股~00700~466.000~463.600~475.000~5205932.0~0~0~466.000~0~0~0~0~0~0~0~0~0~466.000~0~0~0~0~0~0~0~0~0~"
        "5205932.0~2026/06/15 09:51:44~2.400~0.52~476.800~465.600~466.000~5205932.0~2452275137.198~0~17.05~~0~0~2.42~"
        "42443.4358~42443.4358~TENCENT~1.14~677.700~420.400~2.67~9.09~0~0~0~0~0~15.94~3.35~0.06~100~-21.51~4.39~"
        "GP~20.59~11.53~6.88~2.10~-15.76~9108033432.00~9108033432.00~16.13~5.306~471.054~-27.15~HKD~1~30"
    ).split("~")

    qd = _core._tencent_stock_to_quote(fields, "0700.HK", "hk_market", "20260615")

    assert qd is not None
    assert qd.name == "腾讯控股"
    assert qd.date == "2026-06-15"
    assert qd.turnover == 2452275137.198
    assert qd.market_cap == 42443.4358
    assert qd.pe == 17.05
    assert qd.pb == 3.35
    assert qd.high_52w == 677.7
    assert qd.low_52w == 420.4


def test_enrich_quotes_by_symbol_keeps_primary_source_and_adds_details():
    primary = _core.QuoteData(
        symbol="AAPL",
        name="Apple",
        market="us_market",
        date="2026-06-12",
        price=291.13,
        source="sina",
        completeness=100,
    )
    extra = _core.QuoteData(
        symbol="AAPL",
        name="Apple",
        market="us_market",
        date="2026-06-12",
        price=291.13,
        turnover=11308608965,
        market_cap=42759.29952,
        pe=35.25,
        source="tencent",
        completeness=100,
    )

    result = _core.enrich_quotes_by_symbol([primary], [extra], ["AAPL"])

    assert result[0].source == "sina"
    assert result[0].turnover == 11308608965
    assert result[0].market_cap == 42759.29952
    assert result[0].pe == 35.25
    assert any("腾讯财经补充" in note for note in result[0].notes)


def test_fetch_fund_estimate_parses_jsonp(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        _core,
        "fetch_json",
        lambda url, headers=None: {
            "fundcode": "161725",
            "name": "招商中证白酒指数(LOF)A",
            "jzrq": "2026-05-29",
            "dwjz": "0.5866",
            "gsz": "0.5828",
            "gszzl": "-0.65",
            "gztime": "2026-06-01 15:00",
        },
    )

    data = _core.fetch_fund_estimate("161725", "20260601")

    assert data["name"].startswith("招商中证白酒")
    assert data["date"] == "2026-06-01"
    assert data["estimate_change_pct"] == "-0.65"


def test_fetch_fund_holdings_parses_eastmoney_html(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    html = """
    var apidata={ content:"<h4 class='t'><label class='left'><a>招商中证白酒指数(LOF)A</a>&nbsp;&nbsp;2026年1季度股票投资明细</label><label class='right'>截止至：<font class='px12'>2026-03-31</font></label></h4>
    <table><tbody><tr><td>1</td><td><a>600519</a></td><td class='tol'><a>贵州茅台</a></td><td></td><td></td><td></td><td class='tor'>18.33%</td><td class='tor'>508.34</td><td class='tor'>737,086.62</td></tr></tbody></table>",arryear:[2026]};
    """
    monkeypatch.setattr(_core, "_fetch_raw", lambda *args, **kwargs: html)

    data = _core.fetch_fund_holdings("161725", "20260601")

    assert data["asof"] == "2026-03-31"
    assert data["holdings"][0]["code"] == "600519"
    assert data["holdings"][0]["name"] == "贵州茅台"
    assert data["holdings"][0]["weight_pct"] == 18.33


def test_print_fund_report_shows_estimate_and_holdings(capsys):
    _core.print_fund_report(
        {
            "fundcode": "161725",
            "name": "招商中证白酒指数(LOF)A",
            "nav_date": "2026-05-29",
            "nav": "0.5866",
            "estimate_nav": "0.5828",
            "estimate_change_pct": "-0.65",
            "estimate_time": "2026-06-01 15:00",
            "date": "2026-06-01",
            "_source": "天天基金实时估值",
        },
        {"fundcode": "161725", "asof": "2026-03-31", "holdings": [{"code": "600519", "name": "贵州茅台", "weight_pct": 18.33}]},
        {
            "600519": _core.QuoteData(
                symbol="600519",
                name="贵州茅台",
                market="cn_market",
                date="2026-06-01",
                price=1300,
                change_pct=1.2,
                source="sina",
                completeness=100,
            )
        },
        "20260601",
    )

    output = capsys.readouterr().out
    assert "基金持仓速览" in output
    assert "当日估算" in output
    assert "贵州茅台(600519)" in output
    assert "估算贡献" in output
    assert "持仓时效" in output
    assert "可能已调仓" in output


def test_print_single_stock_unavailable_is_clear(capsys):
    _core.print_single_stock_unavailable("BAD", "暂未拿到可核验行情")

    output = capsys.readouterr().out
    assert "暂未拿到可核验行情" in output
    assert "BAD" in output


def test_fund_flow_falls_back_to_push2his(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    saved = []
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: saved.append(args))
    monkeypatch.setattr(_core, "fetch_market_fund_flow_snapshot", lambda date_str: {})

    calls = []

    def fake_fetch_fund_flow_json(url):
        calls.append(url)
        if "push2.eastmoney.com" in url:
            return {"_error": "Empty reply from server"}
        return {
            "data": {
                "klines": [
                    "2026-05-29,-42899849216.0,24645406720.0,18254442496.0,"
                    "-14700744704.0,-28199104512.0,-2.80,1.61,1.19,-0.96,"
                    "-1.84,4068.57,-0.73,0.00,0.00"
                ]
            }
        }

    monkeypatch.setattr(_core, "fetch_fund_flow_json", fake_fetch_fund_flow_json)

    flow = _core.get_fund_flow("20260529")

    assert "push2.eastmoney.com" in calls[0]
    assert "push2his.eastmoney.com" in calls[1]
    assert flow["主力净流入"] == "-42899849216.0"
    assert saved


def test_fund_flow_returns_latest_record_with_date_note(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)

    def fake_fetch_fund_flow_json(url):
        return {
            "data": {
                "klines": [
                    "2026-05-29,-42899849216.0,24645406720.0,18254442496.0,"
                    "-14700744704.0,-28199104512.0,-2.80,1.61,1.19,-0.96,"
                    "-1.84,4068.57,-0.73,0.00,0.00"
                ]
            }
        }

    monkeypatch.setattr(_core, "fetch_fund_flow_json", fake_fetch_fund_flow_json)

    flow = _core.get_fund_flow("20260601")

    assert flow["date"] == "2026-05-29"
    assert flow["_date_note"] == "latest_available"
    assert flow["_requested_date"] == "2026-06-01"
    assert flow["主力净流入"] == "-42899849216.0"


def test_fund_flow_can_return_latest_available_for_flow_command(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)

    def fake_fetch_fund_flow_json(url):
        return {
            "data": {
                "klines": [
                    "2026-05-29,-42899849216.0,24645406720.0,18254442496.0,"
                    "-14700744704.0,-28199104512.0,-2.80,1.61,1.19,-0.96,"
                    "-1.84,4068.57,-0.73,0.00,0.00"
                ]
            }
        }

    monkeypatch.setattr(_core, "fetch_fund_flow_json", fake_fetch_fund_flow_json)

    flow = _core.get_fund_flow("20260601", strict_date=False)

    assert flow["date"] == "2026-05-29"
    assert flow["_date_note"] == "latest_available"
    assert flow["_scope"] == "A股"
    assert flow["主力净流入"] == "-42899849216.0"


def test_market_fund_flow_snapshot_sums_shanghai_and_shenzhen(monkeypatch):
    monkeypatch.setattr(
        _core,
        "fetch_json",
        lambda url, headers=None: {
            "data": {
                "diff": [
                    {"f62": -100.0, "f66": -70.0, "f72": -30.0, "f78": 40.0, "f84": 60.0, "f6": 1000.0, "f124": 1780156800},
                    {"f62": -200.0, "f66": -80.0, "f72": -120.0, "f78": 90.0, "f84": 110.0, "f6": 2000.0, "f124": 1780156800},
                ]
            }
        },
    )

    flow = _core.fetch_market_fund_flow_snapshot("20260601")

    assert flow["主力净流入"] == "-300.0"
    assert flow["超大单净流入"] == "-150.0"
    assert flow["大单净流入"] == "-150.0"
    assert flow["中单净流入"] == "130.0"
    assert flow["小单净流入"] == "170.0"
    assert flow["_source"] == "东财资金流页面实时指标"
    assert flow["_date_note"] == "latest_available"


def test_parse_ths_money_flow_table():
    raw = """
    <table><tbody><tr class="even">
      <td class="first tc">1</td>
      <td class="tl"><a>ERP概念</a></td>
      <td class=" c-rise">1447.8</td>
      <td class="tr cur c-rise">4.78%</td>
      <td class="tr c-rise">61.53</td>
      <td class="tr c-fall">47.25</td>
      <td class="tr c-rise">14.28</td>
      <td class="tr">35</td>
      <td class="tc"><a>软通动力</a></td>
      <td class="tr c-rise">20.01%</td>
      <td class="tr c-rise">39.65</td>
    </tr></tbody></table>
    """

    rows = _core._parse_ths_money_flow_table(raw)

    assert rows[0]["name"] == "ERP概念"
    assert rows[0]["net"] == 14.28
    assert rows[0]["leader"] == "软通动力"


def test_fund_flow_prefers_ths_concept_flow(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        _core,
        "fetch_ths_concept_money_flow_snapshot",
        lambda date_str: {
            "date": "2026-06-01",
            "_source": "同花顺概念资金流",
            "_fallback_indicator": "concept_money_flow",
            "_concept_in": '[{"name":"ERP概念","net":14.28}]',
            "_concept_out": '[{"name":"有色金属","net":-8.0}]',
        },
    )
    monkeypatch.setattr(_core, "fetch_fund_flow_json", lambda url: (_ for _ in ()).throw(AssertionError("should not call Eastmoney first")))

    flow = _core.get_fund_flow("20260601")

    assert flow["_source"] == "同花顺概念资金流"
    assert flow["_fallback_indicator"] == "concept_money_flow"


def test_print_fund_flow_concept_indicator(capsys):
    _core.print_fund_flow(
        {
            "date": "2026-06-01",
            "_source": "同花顺概念资金流",
            "_fallback_indicator": "concept_money_flow",
            "_indicator_note": "概念板块资金流参考",
            "_concept_in": '[{"name":"ERP概念","net":14.28,"leader":"软通动力","leader_change_pct":20.01}]',
            "_concept_out": '[{"name":"有色金属","net":-8.0,"leader":"示例股","leader_change_pct":-3.0}]',
        }
    )

    output = capsys.readouterr().out
    assert "概念板块口径" in output
    assert "同花顺概念资金流" in output
    assert "ERP概念" in output
    assert "主力净流入:" not in output


def test_fund_flow_ignores_old_unavailable_cache(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: {"_unavailable": "old"})
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)

    def fake_fetch_fund_flow_json(url):
        return {
            "data": {
                "klines": [
                    "2026-05-29,-42899849216.0,24645406720.0,18254442496.0,"
                    "-14700744704.0,-28199104512.0,-2.80,1.61,1.19,-0.96,"
                    "-1.84,4068.57,-0.73,0.00,0.00"
                ]
            }
        }

    monkeypatch.setattr(_core, "fetch_fund_flow_json", fake_fetch_fund_flow_json)

    flow = _core.get_fund_flow("20260601")

    assert flow["date"] == "2026-05-29"
    assert flow["主力净流入"] == "-42899849216.0"


def test_fund_flow_uses_latest_good_cache_when_sources_fail(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "fetch_fund_flow_json", lambda url: {"_error": "blocked"})
    monkeypatch.setattr(_core, "fetch_market_fund_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(_core, "fetch_sina_sector_money_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(_core, "fetch_sina_market_activity_snapshot", lambda date_str: {})
    monkeypatch.setattr(_core, "fetch_tencent_market_activity_snapshot", lambda date_str: {})
    monkeypatch.setattr(
        _core,
        "load_latest_fund_flow_cache",
        lambda date_str: {
            "date": "2026-05-29",
            "主力净流入": "-42899849216.0",
            "_requested_date": "2026-06-01",
            "_date_note": "latest_available",
            "_source": "东财实时资金流",
        },
    )

    flow = _core.get_fund_flow("20260601")

    assert flow["date"] == "2026-05-29"
    assert flow["_cache_note"] == "last_known_good"
    assert flow["主力净流入"] == "-42899849216.0"


def test_fund_flow_uses_online_snapshot_before_cache(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "fetch_ths_concept_money_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(_core, "fetch_fund_flow_json", lambda url: {"_error": "blocked"})
    monkeypatch.setattr(
        _core,
        "fetch_market_fund_flow_snapshot",
        lambda date_str: {
            "date": "2026-05-29",
            "主力净流入": "-42000000000",
            "_requested_date": "2026-06-01",
            "_date_note": "latest_available",
            "_source": "东财资金流页面实时指标",
        },
    )
    monkeypatch.setattr(
        _core,
        "load_latest_fund_flow_cache",
        lambda date_str: {
            "date": "2026-05-28",
            "主力净流入": "-1",
            "_source": "本地最近可用资金流缓存",
        },
    )

    flow = _core.get_fund_flow("20260601")

    assert flow["_source"] == "东财资金流页面实时指标"
    assert flow["date"] == "2026-05-29"
    assert flow["主力净流入"] == "-42000000000"


def test_fund_flow_uses_sina_activity_before_cache(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "fetch_fund_flow_json", lambda url: {"_error": "blocked"})
    monkeypatch.setattr(_core, "fetch_market_fund_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(_core, "fetch_sina_sector_money_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(
        _core,
        "fetch_sina_market_activity_snapshot",
        lambda date_str: {
            "date": "2026-06-01",
            "_source": "新浪财经A股指数行情",
            "_fallback_indicator": "market_activity",
            "总成交额": "3000",
        },
    )
    monkeypatch.setattr(
        _core,
        "load_latest_fund_flow_cache",
        lambda date_str: {
            "date": "2026-05-29",
            "主力净流入": "-42899849216.0",
            "_source": "本地最近可用资金流缓存",
        },
    )

    flow = _core.get_fund_flow("20260601")

    assert flow["_source"] == "新浪财经A股指数行情"
    assert flow["_fallback_indicator"] == "market_activity"
    assert "_cache_note" not in flow


def test_fund_flow_uses_sina_sector_flow_before_activity(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    monkeypatch.setattr(_core, "fetch_fund_flow_json", lambda url: {"_error": "blocked"})
    monkeypatch.setattr(_core, "fetch_market_fund_flow_snapshot", lambda date_str: {})
    monkeypatch.setattr(
        _core,
        "fetch_sina_sector_money_flow_snapshot",
        lambda date_str: {
            "date": "2026-06-01",
            "_source": "新浪财经资金流页面行业流向",
            "_fallback_indicator": "sector_money_flow",
            "_sector_in": '[["化工行业", 52.94]]',
            "_sector_out": '[["有色金属", -20.0]]',
        },
    )
    monkeypatch.setattr(_core, "fetch_sina_market_activity_snapshot", lambda date_str: {"_fallback_indicator": "market_activity"})

    flow = _core.get_fund_flow("20260601")

    assert flow["_source"] == "新浪财经资金流页面行业流向"
    assert flow["_fallback_indicator"] == "sector_money_flow"


def test_print_fund_flow_sector_indicator(capsys):
    _core.print_fund_flow(
        {
            "date": "2026-06-01",
            "_source": "新浪财经资金流页面行业流向",
            "_fallback_indicator": "sector_money_flow",
            "_indicator_note": "行业资金流参考",
            "_sector_in": '[["化工行业", 52.94]]',
            "_sector_out": '[["有色金属", -20.0]]',
        }
    )

    output = capsys.readouterr().out
    assert "行业资金流参考" in output
    assert "化工行业" in output
    assert "主力净流入:" not in output


def test_market_activity_uses_latest_trade_date_when_source_has_no_date(monkeypatch):
    monkeypatch.setattr(_core, "nearest_trade_date", lambda: "20260529")

    flow = _core._market_activity_snapshot(
        [{"f12": "000001", "f14": "上证指数", "f2": "3000", "f3": "1.0", "f6": "1000"}],
        "新浪财经A股指数行情",
        "20260601",
    )

    assert flow["date"] == "2026-05-29"
    assert flow["_requested_date"] == "2026-06-01"
    assert flow["_date_note"] == "latest_available"


def test_print_fund_flow_labels_a_share_and_stale_notice(capsys):
    _core.print_fund_flow(
        {
            "date": "2026-05-29",
            "_date_note": "latest_available",
            "_requested_date": "2026-06-01",
            "主力净流入": "-42899849216.0",
        }
    )

    output = capsys.readouterr().out
    assert "A股资金流向" in output
    assert "阶段: 2026-05-29 交易日盘后" in output
    assert "当前展示来源最新可用数据" in output
    assert "主力净流入" in output
    assert "暂不展示" not in output


def test_print_fund_flow_market_activity_indicator(capsys):
    _core.print_fund_flow(
        {
            "date": "2026-06-01",
            "_source": "新浪财经A股指数行情",
            "_fallback_indicator": "market_activity",
            "_indicator_note": "不等同于主力资金净流入",
            "总成交额": "3000",
            "上证指数点位": "3000.0",
            "上证指数涨跌幅": "1.2",
            "上证指数成交额": "1000",
        }
    )

    output = capsys.readouterr().out
    assert "不等同于主力资金净流入" in output
    assert "指数活跃度参考" in output
    assert "合计成交额" in output
    assert "主力净流入:" not in output


def test_print_global_indices_hides_completeness(capsys):
    _core.print_global_indices(
        [
            _core.QuoteData(
                symbol="^HSI",
                name="恒生指数",
                market="hk_market",
                price=25182.39,
                change_pct=0.70,
                turnover=462070141280.0,
                source="tencent",
                completeness=100,
            )
        ],
        "港股",
    )

    output = capsys.readouterr().out
    assert "完整度" not in output
    assert "100%" not in output


def test_print_data_quality_report_is_quiet_by_default(capsys):
    _core.DIAGNOSTICS[:] = ["Tencent HK index口径提示"]

    _core.print_data_quality_report(
        [
            _core.QuoteData(
                symbol="^HSI",
                name="恒生指数",
                completeness=100,
                notes=["港股指数采用腾讯收盘口径"],
            )
        ]
    )

    assert capsys.readouterr().out == ""
    _core.DIAGNOSTICS[:] = []


def test_print_single_stock_report_hides_completeness(capsys):
    _core.print_single_stock_report(
        _core.QuoteData(
            symbol="600519",
            name="贵州茅台",
            market="cn_market",
            date="2026-06-01",
            price=1500.0,
            prev_close=1490.0,
            change=10.0,
            change_pct=0.67,
            volume=123456,
            source="sina",
            completeness=100,
        ),
        requested_date="20260601",
    )

    output = capsys.readouterr().out
    assert "完整度" not in output
    assert "100%" not in output


def test_run_daily_report_prints_watchlist_and_market_sections(monkeypatch, capsys):
    calls = []

    monkeypatch.setattr(
        _core,
        "get_single_stock_quote",
        lambda symbol, date: _core.QuoteData(
            symbol=symbol,
            name="测试股票",
            market="cn_market",
            date="2026-05-29",
            price=10,
            change_pct=1.2,
            source="test",
        ),
    )
    monkeypatch.setattr(_core, "run_fund_report", lambda code, date, include_news=True: calls.append(("fund", code, date, include_news)))
    monkeypatch.setattr(_core, "run_a_share", lambda date, include_news=True: calls.append(("a", date, include_news)))
    monkeypatch.setattr(_core, "print_report_footer", lambda: None)

    _core.run_daily_report("20260529", {"stocks": ["600519"], "funds": ["161725"]}, include_news=False)

    output = capsys.readouterr().out
    assert "每日行情日报" in output
    assert "一、关注标的" in output
    assert "测试股票 (600519)" in output
    assert "三、投资建议" in output
    assert "全球指数" not in output
    assert calls == [("fund", "161725", "20260529", False), ("a", "20260529", False)]


def test_run_daily_report_uses_safe_markdown_link_for_watchlist_news(monkeypatch, capsys):
    monkeypatch.setattr(
        _core,
        "get_single_stock_quote",
        lambda symbol, date: _core.QuoteData(
            symbol=symbol,
            name="测试股票",
            market="cn_market",
            date="2026-05-29",
            price=10,
            change_pct=1.2,
            source="test",
        ),
    )
    monkeypatch.setattr(_core, "_news_aliases", lambda symbol, name: [symbol, name])
    monkeypatch.setattr(
        _core,
        "combined_news_search",
        lambda *args, **kwargs: {
            "data": [
                {"title": "主标题", "url": "javascript:alert(1)", "link": "https://example.com/news"},
            ]
        },
    )
    monkeypatch.setattr(_core, "run_a_share", lambda date, include_news=True: None)
    monkeypatch.setattr(_core, "print_report_footer", lambda: None)

    _core.run_daily_report("20260529", {"stocks": ["600519"], "funds": []}, include_news=True)

    output = capsys.readouterr().out
    assert "相关新闻: [主标题](https://example.com/news)" in output
    assert "javascript:alert(1)" not in output


def test_run_daily_report_uses_only_relevant_stock_markets(monkeypatch, capsys):
    calls = []

    monkeypatch.setattr(
        _core,
        "get_single_stock_quote",
        lambda symbol, date: _core.QuoteData(
            symbol="0700.HK",
            name="腾讯控股",
            market="hk_market",
            date="2026-05-29",
            price=390,
            change_pct=1.2,
            source="test",
        ),
    )
    monkeypatch.setattr(_core, "run_a_share", lambda date, include_news=True: calls.append(("a", date, include_news)))
    monkeypatch.setattr(_core, "run_hk_market", lambda date, include_news=True: calls.append(("hk", date, include_news)))
    monkeypatch.setattr(_core, "run_us_market", lambda date, include_news=True: calls.append(("us", date, include_news)))
    monkeypatch.setattr(_core, "run_global_market", lambda date: calls.append(("global", date)))
    monkeypatch.setattr(_core, "print_report_footer", lambda: None)

    _core.run_daily_report("20260529", {"stocks": ["0700.HK"], "funds": []}, include_news=False)

    output = capsys.readouterr().out
    assert "相关市场概览" in output
    assert "全球指数" not in output
    assert calls == [("hk", "20260529", False)]


def test_run_daily_report_uses_fund_top_holdings_market(monkeypatch, capsys):
    calls = []

    monkeypatch.setattr(_core, "run_fund_report", lambda code, date, include_news=True: calls.append(("fund", code, date, include_news)))
    monkeypatch.setattr(
        _core,
        "fetch_fund_holdings",
        lambda code, date, limit=10: {"holdings": [{"code": "600519", "name": "贵州茅台"}]},
    )
    monkeypatch.setattr(_core, "run_a_share", lambda date, include_news=True: calls.append(("a", date, include_news)))
    monkeypatch.setattr(_core, "run_hk_market", lambda date, include_news=True: calls.append(("hk", date, include_news)))
    monkeypatch.setattr(_core, "run_global_market", lambda date: calls.append(("global", date)))
    monkeypatch.setattr(_core, "print_report_footer", lambda: None)

    _core.run_daily_report("20260529", {"stocks": [], "funds": ["161725"]}, include_news=False)

    output = capsys.readouterr().out
    assert "相关市场概览" in output
    assert calls == [("fund", "161725", "20260529", False), ("a", "20260529", False)]


def test_daily_key_points_use_portfolio_specific_advice(monkeypatch, capsys):
    quotes = {
        "NVDA": _core.QuoteData(
            symbol="NVDA",
            name="英伟达",
            market="us_market",
            date="2026-06-03",
            price=145.0,
            change_pct=4.2,
            currency="USD",
            source="test",
        ),
        "AAPL": _core.QuoteData(
            symbol="AAPL",
            name="苹果",
            market="us_market",
            date="2026-06-03",
            price=205.0,
            change_pct=-0.8,
            currency="USD",
            source="test",
        ),
    }

    monkeypatch.setattr(_core, "get_single_stock_quote", lambda symbol, date: quotes.get(symbol))
    monkeypatch.setattr(
        _core,
        "fetch_fund_estimate",
        lambda code, date: {
            "fundcode": code,
            "name": "测试科技基金",
            "estimate_change_pct": "2.10",
            "date": "2026-06-03",
        },
    )
    monkeypatch.setattr(_core, "get_index", lambda date: [])
    monkeypatch.setattr(_core, "get_fund_flow", lambda date, strict_date=False: {})
    monkeypatch.setattr(_core, "fetch_stock_close_on_or_after", lambda symbol, buy_date: {"symbol": symbol, "date": buy_date, "close": 120.0 if symbol == "NVDA" else 210.0})
    monkeypatch.setattr(_core, "fetch_fund_nav_on_or_after", lambda code, buy_date: {"fundcode": code, "date": buy_date, "nav": 1.0})
    monkeypatch.setattr(
        _core,
        "combined_news_search",
        lambda *args, **kwargs: {
            "data": [
                {"title": "英伟达 AI 芯片需求继续增长"},
                {"title": "苹果服务业务现金流保持韧性"},
            ]
        },
    )

    _core.run_daily_report(
        "20260603",
        {
            "stocks": ["NVDA", "AAPL"],
            "funds": ["021528"],
            "positions": {
                "stocks": {
                    "NVDA": {"buy_date": "2026-01-15", "quantity": 10},
                    "AAPL": {"buy_date": "2026-02-01", "quantity": 5},
                },
                "funds": {"021528": {"buy_date": "2026-01-10", "quantity": 1000}},
            },
        },
        include_news=True,
        report_format="key-points",
    )

    output = capsys.readouterr().out
    assert "英伟达(NVDA)" in output
    assert "基金分析" in output
    assert "个股分析" in output
    assert "综合持仓" in output
    assert "新闻偏正面" in output
    assert "持有观察" in output
    assert "买入以来" in output
    assert "组合买入以来估算收益" in output
    assert "021528" in output


def test_daily_key_points_support_fund_only_positions(monkeypatch, capsys):
    monkeypatch.setattr(
        _core,
        "fetch_fund_estimate",
        lambda code, date: {
            "fundcode": code,
            "name": "测试基金",
            "estimate_nav": "1.12",
            "estimate_change_pct": "1.50",
            "date": "2026-06-03",
        },
    )
    monkeypatch.setattr(_core, "fetch_fund_nav_on_or_after", lambda code, buy_date: {"fundcode": code, "date": buy_date, "nav": 1.0})
    monkeypatch.setattr(_core, "get_index", lambda date: [])
    monkeypatch.setattr(_core, "get_fund_flow", lambda date, strict_date=False: {})

    _core.run_daily_report(
        "20260603",
        {
            "stocks": [],
            "funds": ["021528"],
            "positions": {"stocks": {}, "funds": {"021528": {"buy_date": "2026-01-10", "quantity": 1000}}},
        },
        include_news=False,
        report_format="key-points",
    )

    output = capsys.readouterr().out
    assert "基金分析" in output
    assert "综合持仓" in output
    assert "个股分析" not in output
    assert "买入以来 +12.00%" in output
    assert "当前以基金为主" in output


def test_daily_key_points_support_stock_only_positions(monkeypatch, capsys):
    monkeypatch.setattr(
        _core,
        "get_single_stock_quote",
        lambda symbol, date: _core.QuoteData(
            symbol=symbol,
            name="测试股票",
            market="cn_market",
            date="2026-06-03",
            price=12.0,
            change_pct=-2.5,
            currency="CNY",
            source="test",
        ),
    )
    monkeypatch.setattr(_core, "fetch_stock_close_on_or_after", lambda symbol, buy_date: {"symbol": symbol, "date": buy_date, "close": 10.0})
    monkeypatch.setattr(
        _core,
        "combined_news_search",
        lambda *args, **kwargs: {"data": [{"title": "测试股票需求放缓，短期风险上升"}]},
    )

    _core.run_daily_report(
        "20260603",
        {
            "stocks": ["600519"],
            "funds": [],
            "positions": {"stocks": {"600519": {"buy_date": "2026-01-10", "quantity": 100}}, "funds": {}},
        },
        include_news=True,
        report_format="key-points",
    )

    output = capsys.readouterr().out
    assert "个股分析" in output
    assert "综合持仓" in output
    assert "基金分析" not in output
    assert "新闻偏负面" in output
    assert "买入以来 +20.00%" in output
    assert "当前以个股为主" in output


def test_diagnostic_summary_is_quiet_by_default(capsys):
    _core.DIAGNOSTICS[:] = ["Sina missing AAPL"]

    _core.print_diagnostic_summary()

    assert capsys.readouterr().out == ""


def test_nearest_trade_date_before_a_share_close_returns_previous_trade_day():
    assert _core.nearest_trade_date(datetime(2026, 6, 1, 3, 30)) == "20260529"
    assert _core.nearest_trade_date(datetime(2026, 6, 1, 14, 59)) == "20260529"
    assert _core.nearest_trade_date(datetime(2026, 6, 1, 15, 1)) == "20260601"


def test_tencent_hk_index_quote_uses_close_turnover_and_source(monkeypatch):
    raw = (
        'v_hkHSI="100~恒生指数~HSI~25182.390~25006.160~25161.520~46207014.1280~0~0~'
        '25182.390~0~0~0~0~0~0~0~0~0~25182.390~0~0~0~0~0~0~0~0~0~0.0~'
        '2026/05/29 18:31:24~176.230~0.70~25313.330~25055.800~25182.390~'
        '46207014.1280~46207014.128~0~0~~0~0~1.03~0~0~Hang Seng Index";'
    )

    monkeypatch.setattr(_core, "fetch_tencent_batch", lambda codes: raw)

    quotes = _core.fetch_hk_indices_tencent({"^HSI": "恒生指数"}, "20260529")

    assert len(quotes) == 1
    assert quotes[0].name == "恒生指数"
    assert quotes[0].price == 25182.39
    assert quotes[0].change_pct == 0.70
    assert quotes[0].turnover == 462070141280.0
    assert quotes[0].source == "tencent"


def test_merge_quotes_fills_only_missing_symbols():
    primary = [
        _core.QuoteData(symbol="AAPL", name="苹果", price=1, source="sina"),
    ]
    fallback = [
        _core.QuoteData(symbol="AAPL", name="Apple", price=2, source="eastmoney"),
        _core.QuoteData(symbol="NVDA", name="英伟达", price=3, source="eastmoney"),
    ]

    merged = _core.merge_quotes_by_symbol(primary, fallback, ["AAPL", "NVDA"])

    assert [q.symbol for q in merged] == ["AAPL", "NVDA"]
    assert merged[0].price == 1
    assert merged[1].source == "eastmoney"


def test_news_chain_falls_back_to_sina(monkeypatch):
    monkeypatch.setattr(_core, "futu_news_search", lambda *args, **kwargs: {"_error": "blocked"})
    monkeypatch.setattr(_core, "futu_stock_feed", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(
        _core,
        "sina_roll_news",
        lambda keyword, size=5, aliases=None: {
            "source": "sina_roll",
            "data": [{"title": "英伟达发布新一代 AI PC", "url": "https://example.com", "publish_time": 1780224318}],
        },
    )

    news = _core.news_search_chain("NVDA", size=5, lang="zh-CN", aliases=["英伟达"])

    assert news["source"] == "sina_roll"
    assert news["data"][0]["title"].startswith("英伟达")


def test_news_chain_falls_back_to_eastmoney(monkeypatch):
    monkeypatch.setattr(_core, "futu_news_search", lambda *args, **kwargs: {"_error": "blocked"})
    monkeypatch.setattr(_core, "futu_stock_feed", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(_core, "sina_roll_news", lambda *args, **kwargs: {"source": "sina_roll", "data": []})
    monkeypatch.setattr(
        _core,
        "eastmoney_fast_news",
        lambda keyword, size=5, aliases=None: {
            "source": "eastmoney_fast",
            "data": [{"title": "腾讯控股回购", "url": "https://example.com", "publish_time": 1780224318}],
        },
    )

    news = _core.news_search_chain("腾讯", size=5, lang="zh-CN", aliases=["腾讯控股"])

    assert news["source"] == "eastmoney_fast"
    assert news["data"][0]["title"].startswith("腾讯")


def test_combined_news_filters_to_requested_date(monkeypatch):
    monkeypatch.setattr(
        _core,
        "futu_news_search",
        lambda *args, **kwargs: {
            "source": "futu_news",
            "data": [
                {"title": "腾讯今日新闻", "url": "https://today.example", "publish_time": 1780300000},
                {"title": "腾讯旧新闻", "url": "https://old.example", "publish_time": 1780210000},
            ],
        },
    )
    monkeypatch.setattr(_core, "futu_stock_feed", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(_core, "sina_roll_news", lambda *args, **kwargs: {"source": "sina_roll", "data": []})
    monkeypatch.setattr(_core, "eastmoney_fast_news", lambda *args, **kwargs: {"source": "eastmoney_fast", "data": []})

    news = _core.combined_news_search("腾讯", size=5, date_str="20260601")

    assert [item["title"] for item in news["data"]] == ["腾讯今日新闻"]


def test_rank_symbols_only_returns_positive_news(monkeypatch):
    def fake_combined(keyword, size=5, lang="zh-CN", aliases=None, date_str=None):
        if keyword == "AAA":
            return {"data": [{"title": "AAA today", "publish_time": 1780300000}], "all_count": 1, "source_counts": {"futu_news": 1}}
        return {"data": [], "all_count": 0, "source_counts": {}}

    monkeypatch.setattr(_core, "combined_news_search", fake_combined)

    ranked, heat = _core.rank_symbols_by_news_heat(["AAA", "BBB"], date_str="20260601")

    assert ranked == ["AAA"]
    assert heat["BBB"]["score"] == 0


def test_combined_news_preserves_per_item_source_and_url(monkeypatch):
    monkeypatch.setattr(
        _core,
        "futu_news_search",
        lambda *args, **kwargs: {
            "source": "futu_news",
            "data": [{"title": "腾讯发布新品", "url": "https://futu.example", "publish_time": 1780300000}],
        },
    )
    monkeypatch.setattr(_core, "futu_stock_feed", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(
        _core,
        "sina_roll_news",
        lambda *args, **kwargs: {
            "source": "sina_roll",
            "data": [{"title": "腾讯云签约", "url": "https://sina.example", "publish_time": 1780200000}],
        },
    )
    monkeypatch.setattr(_core, "eastmoney_fast_news", lambda *args, **kwargs: {"source": "eastmoney_fast", "data": []})

    news = _core.combined_news_search("腾讯", size=5, lang="zh-CN", aliases=["腾讯控股"])

    assert news["source_counts"] == {"futu_news": 1, "sina_roll": 1}
    assert {item["source"] for item in news["data"]} == {"futu_news", "sina_roll"}
    assert all(item["url"] for item in news["data"])


def test_combined_news_skips_empty_content_links(monkeypatch):
    monkeypatch.setattr(
        _core,
        "futu_news_search",
        lambda *args, **kwargs: {
            "source": "futu_news",
            "data": [
                {"title": "坏链接新闻", "url": "https://bad.example", "publish_time": 1780300000},
                {"title": "好链接新闻", "url": "https://good.example", "publish_time": 1780290000},
            ],
        },
    )
    monkeypatch.setattr(_core, "futu_stock_feed", lambda *args, **kwargs: {"data": []})
    monkeypatch.setattr(_core, "sina_roll_news", lambda *args, **kwargs: {"source": "sina_roll", "data": []})
    monkeypatch.setattr(_core, "eastmoney_fast_news", lambda *args, **kwargs: {"source": "eastmoney_fast", "data": []})
    monkeypatch.setattr(_core, "_news_url_has_readable_content", lambda url: "good" in url)

    news = _core.combined_news_search("腾讯", size=1, date_str="20260601")

    assert [item["title"] for item in news["data"]] == ["好链接新闻"]


def test_print_news_shows_source_and_link_status(capsys):
    _core.print_futu_news(
        {
            "source": "futu_news+sina_roll",
            "source_counts": {"futu_news": 1, "sina_roll": 1},
            "data": [
                {"title": "腾讯发布新品", "source": "futu_news", "url": "https://futu.example", "publish_time": 1780300000},
                {"title": "腾讯云签约", "source": "sina_roll", "url": "", "publish_time": 1780200000},
            ],
        },
        "腾讯",
    )

    output = capsys.readouterr().out
    assert "来源覆盖" in output
    assert "来源: 富途资讯 | 链接: https://futu.example" in output
    assert "来源: 新浪财经 | 链接: 暂无公开链接" in output


def test_print_news_empty_is_clear(capsys):
    _core.print_futu_news({"source": "none", "data": []}, "A股市场")

    output = capsys.readouterr().out
    assert "目前暂未获取到有效新闻信息" in output


def test_session_stage_labels_date_mismatch_as_after_hours():
    assert _core.session_stage_label(data_date="2026-05-29", requested_date="20260601") == "交易日盘后"
    assert _core.dated_stage_label(data_date="2026-05-29", requested_date="20260601") == "2026-05-29 交易日盘后"


def test_report_footer_is_user_friendly(capsys):
    _core.print_report_footer()

    output = capsys.readouterr().out
    assert "输出结束" not in output
    assert "复盘仅供参考" in output
