"""Reserve test_core sanity to ensure module imports without side-effects."""
import importlib


def test_core_imports():
    mod = importlib.import_module("young_stock_cli._core")
    assert hasattr(mod, "main")
    # Key public-ish helpers used elsewhere
    for fn in ("nearest_trade_date", "detect_market_type", "fmt_price", "fmt_pct"):
        assert hasattr(mod, fn), f"_core.{fn} missing"


def test_detect_market_type():
    from young_stock_cli._core import detect_market_type

    assert "cn" in detect_market_type("000001") or detect_market_type("000001") == "a"
    assert "hk" in detect_market_type("00700.HK")
    # US tickers fall through to a default (us_market or us)
    assert "us" in detect_market_type("AAPL")


def test_formatters():
    from young_stock_cli._core import fmt_pct, fmt_price

    assert "+" in fmt_pct(1.23)
    assert "-" in fmt_pct(-1.23)
    # fmt_price(None) returns some placeholder; just confirm it's a string
    assert isinstance(fmt_price(None), str)
