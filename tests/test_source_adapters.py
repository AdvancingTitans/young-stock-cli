from dataclasses import dataclass

from young_stock.health import SourceHealthBook
from young_stock.sources import DataSource, SourceResolver
from young_stock.sources.adapters import build_core_adapters, yahoo_chart_adapter


@dataclass
class Quote:
    symbol: str
    date: str
    price: float

    def to_dict(self):
        return {"symbol": self.symbol, "date": self.date, "price": self.price}


class FakeCore:
    @staticmethod
    def normalize_stock_symbol(symbol):
        if symbol == "600519":
            return symbol, "cn_market"
        if symbol.endswith(".HK"):
            return symbol, "hk_market"
        return symbol, "us_market"

    @staticmethod
    def fetch_cn_stocks_sina(symbols, date):
        return []

    @staticmethod
    def fetch_hk_stocks_sina(symbols, date):
        return []

    @staticmethod
    def fetch_us_stocks_sina(symbols, date):
        return []

    @staticmethod
    def fetch_cn_stocks_tencent(symbols, date):
        return [Quote(symbols[0], date, 1)]

    fetch_hk_stocks_tencent = fetch_cn_stocks_tencent
    fetch_us_stocks_tencent = fetch_cn_stocks_tencent
    fetch_cn_stocks_direct = fetch_cn_stocks_tencent
    fetch_hk_stocks_direct = fetch_cn_stocks_tencent
    fetch_us_stocks_direct = fetch_cn_stocks_tencent


def test_core_quote_adapters_support_a_hk_us_fallback():
    registry = (
        DataSource("sina", ("a", "hk", "us"), ("quote",), "primary", "http", "sina"),
        DataSource("tencent", ("a", "hk", "us"), ("quote",), "primary", "http", "tencent"),
    )
    resolver = SourceResolver(registry=registry, health=SourceHealthBook())
    adapters = build_core_adapters(FakeCore())

    for market, symbol in (("a", "600519"), ("hk", "0700.HK"), ("us", "AAPL")):
        result = resolver.resolve(market, "quote", adapters, symbol, "20260618")
        assert result.source == "tencent"
        assert result.data["symbol"] == symbol


def test_yahoo_chart_adapter_parses_v8_response():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [{
                        "meta": {"currency": "USD"},
                        "timestamp": [1, 2],
                        "indicators": {"quote": [{"close": [10.0, 11.0]}]},
                    }]
                }
            }

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    result = yahoo_chart_adapter(Session())("AAPL", "20260618")

    assert result.source == "yahoo"
    assert result.data["rows"][-1]["close"] == 11.0
