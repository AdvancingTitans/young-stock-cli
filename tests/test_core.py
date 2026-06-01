from datetime import datetime

from young_stock import _core


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
    assert "合计成交额" in output
    assert "主力净流入:" not in output


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


def test_session_stage_labels_date_mismatch_as_after_hours():
    assert _core.session_stage_label(data_date="2026-05-29", requested_date="20260601") == "交易日盘后"


def test_report_footer_is_user_friendly(capsys):
    _core.print_report_footer()

    output = capsys.readouterr().out
    assert "输出结束" not in output
    assert "复盘仅供参考" in output
