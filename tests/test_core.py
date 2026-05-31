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
