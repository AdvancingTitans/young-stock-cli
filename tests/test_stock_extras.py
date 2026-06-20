from young_stock.sources.extras import StockExtras, collect_stock_extras, social_heat


class FakeCore:
    @staticmethod
    def normalize_stock_symbol(symbol):
        return symbol, "cn_market"

    @staticmethod
    def eastmoney_datacenter(report_name, **kwargs):
        assert report_name == "RPT_DAILYBILLBOARD_DETAILSNEW"
        return [
            {
                "SECURITY_CODE": "600519",
                "SECURITY_NAME_ABBR": "贵州茅台",
                "TRADE_DATE": "2026-06-18 00:00:00",
                "NET_BUY_AMT": 123,
                "BUY_AMT": 500,
                "SELL_AMT": 377,
                "EXPLANATION": "日涨幅偏离值达7%",
            }
        ]


def test_stock_extras_has_fixed_evidence_fields():
    extras = StockExtras()

    assert set(extras.to_dict()) == {
        "financial_trends",
        "lhb",
        "social_heat",
        "events",
        "technical_fallback",
        "source_trace",
    }


def test_collect_stock_extras_uses_http_lhb_without_rich_sources():
    extras = collect_stock_extras(FakeCore(), "600519", "20260618")

    assert extras.lhb["rows"][0]["net_buy"] == 123
    assert extras.lhb["_source"] == "东方财富龙虎榜"
    assert extras.financial_trends["_unavailable"] == "启用 --rich-source 后可尝试 akshare"


def test_social_heat_caches_for_five_minutes():
    calls = []
    now = [1000.0]

    def fetcher():
        calls.append(1)
        return [{"platform": "微博", "title": "贵州茅台 热点"}]

    first = social_heat("贵州茅台", fetcher=fetcher, clock=lambda: now[0])
    now[0] += 299
    second = social_heat("贵州茅台", fetcher=fetcher, clock=lambda: now[0])
    now[0] += 2
    third = social_heat("贵州茅台", fetcher=fetcher, clock=lambda: now[0])

    assert first == second
    assert third == first
    assert len(calls) == 2
