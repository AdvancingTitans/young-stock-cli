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


def test_fund_flow_falls_back_to_push2his(monkeypatch):
    monkeypatch.setattr(_core, "cache_load", lambda *args, **kwargs: None)
    saved = []
    monkeypatch.setattr(_core, "cache_save", lambda *args, **kwargs: saved.append(args))

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


def test_report_footer_is_user_friendly(capsys):
    _core.print_report_footer()

    output = capsys.readouterr().out
    assert "输出结束" not in output
    assert "复盘仅供参考" in output
