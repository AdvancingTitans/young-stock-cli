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
