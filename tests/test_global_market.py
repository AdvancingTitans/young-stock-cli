from types import SimpleNamespace

from young_stock import _core
from young_stock.evidence import build_stock_evidence
from young_stock.global_market import (
    collect_global_indices,
    collect_rich_source_bundle,
    lightweight_source_plan,
    normalize_global_symbol,
    parse_eastmoney_kline_close,
    parse_sec_filing_fixture,
    select_exact_eastmoney_match,
)


def test_hk_symbol_normalization_pads_to_five_digits():
    assert normalize_global_symbol("700").symbol == "00700.HK"
    assert normalize_global_symbol("0700.hk").source_codes["eastmoney"] == "00700"
    assert normalize_global_symbol("00700.HK").market == "hk_market"


def test_us_exact_match_beats_similar_symbols_and_warrants():
    rows = [
        {"f12": "AAP", "f14": "Advance Auto Parts Inc"},
        {"f12": "AAPLW", "f14": "Apple Warrant"},
        {"f12": "AAPL", "f14": "Apple Inc"},
        {"f12": "AAPU", "f14": "Direxion Daily AAPL Bull 2X Shares"},
    ]

    selected = select_exact_eastmoney_match(rows, "aapl", "us_market")

    assert selected == {"f12": "AAPL", "f14": "Apple Inc"}


def test_hk_exact_match_avoids_notes_leveraged_etfs_and_similar_codes():
    rows = [
        {"f12": "0070", "f14": "金粤控股"},
        {"f12": "0700", "f14": "腾讯控股票据"},
        {"f12": "00700", "f14": "腾讯控股"},
        {"f12": "07200", "f14": "腾讯法兴二五购A"},
        {"f12": "7500", "f14": "FI二南方恒指"},
    ]

    selected = select_exact_eastmoney_match(rows, "700.HK", "hk_market")

    assert selected == {"f12": "00700", "f14": "腾讯控股"}


def test_lightweight_source_plan_documents_quote_history_and_index_fallbacks():
    assert lightweight_source_plan("hk_market", "quote") == ("sina", "tencent", "eastmoney")
    assert lightweight_source_plan("us_market", "history") == ("eastmoney", "yahoo")
    assert lightweight_source_plan("hk_market", "indices") == ("tencent", "sina", "eastmoney")
    assert lightweight_source_plan("us_market", "indices") == ("sina", "tencent", "eastmoney")


def test_history_kline_never_returns_rows_after_today():
    row = parse_eastmoney_kline_close(
        "AAPL",
        "us_market",
        ["2026-07-09,10,11,12,9,100,1000", "2026-07-10,11,12,13,10,100,1000"],
        requested_date="20260709",
        today="20260708",
    )

    assert row == {"_error": "历史K线不能返回未来数据", "requested_date": "2026-07-09", "today": "2026-07-08"}


def test_history_kline_returns_first_trading_row_on_or_after_request_with_source_date():
    row = parse_eastmoney_kline_close(
        "00700.HK",
        "hk_market",
        ["2026-07-06,10,11,12,9,100,1000", "2026-07-08,11,12,13,10,100,1000"],
        requested_date="20260707",
        today="20260708",
    )

    assert row == {
        "symbol": "00700.HK",
        "market": "hk_market",
        "date": "2026-07-08",
        "close": 12.0,
        "_source": "东方财富历史K线",
        "_requested_date": "2026-07-07",
    }


def test_collect_global_indices_tracks_source_and_date_across_fallbacks():
    class Core:
        def fetch_us_indices_sina(self, symbols, date):
            return []

        def fetch_us_indices_tencent(self, symbols, date):
            return [_core.QuoteData(symbol="^GSPC", name="标普 500", date="2026-07-07", price=6000, source="tencent")]

        def fetch_hk_indices_tencent(self, symbols, date):
            return []

        def fetch_hk_indices_sina(self, symbols, date):
            return [_core.QuoteData(symbol="^HSI", name="恒生指数", date="2026-07-08", price=24000, source="sina")]

        def fetch_indices_direct(self, symbols, date, secids):
            return []

        def get_index(self, date):
            return [{"f12": "000001", "f14": "上证指数", "f2": 3200, "f3": 0.1, "f6": 100, "_source": "eastmoney", "_source_date": "2026-07-08"}]

    bundle = collect_global_indices(Core(), "20260708")

    assert bundle["us_indices"][0]["source"] == "tencent"
    assert bundle["hk_indices"][0]["trade_date"] == "2026-07-08"
    assert bundle["a_indices"][0]["source"] == "eastmoney"


def test_sec_fixture_extracts_structured_facts_without_full_text():
    filing = {
        "form": "10-K",
        "filed": "2026-02-01",
        "accessionNumber": "0000320193-26-000001",
        "items": {"Item 1A": "Risk factors summary", "Item 7": "MD&A summary"},
        "full_text": "Very long SEC filing body that must not be passed to the model.",
    }

    facts = parse_sec_filing_fixture(filing)

    assert facts == {
        "form": "10-K",
        "filed": "2026-02-01",
        "accession_number": "0000320193-26-000001",
        "key_sections": [
            {"item": "Item 1A", "snippet": "Risk factors summary"},
            {"item": "Item 7", "snippet": "MD&A summary"},
        ],
        "source": "sec",
    }
    assert "full_text" not in facts


def test_rich_source_bundle_reports_missing_optional_dependencies():
    bundle = collect_rich_source_bundle("AAPL", "20260708", rich_source=True, installed_dependencies=set())

    assert bundle["sec_filings"]["_unavailable"] == "SEC 10-K/10-Q/8-K 需要安装 rich-source SEC adapter"
    assert bundle["xbrl_financials"]["_unavailable"] == "XBRL 财务需要安装 rich-source SEC adapter"
    assert bundle["analyst_estimates"]["_unavailable"] == "分析师预期需要安装 rich-source 数据 adapter"
    assert bundle["us_options"]["_unavailable"] == "美股期权需要安装 rich-source 期权 adapter"


def test_global_market_extensions_flow_into_stock_evidence_bundle():
    quote = SimpleNamespace(
        symbol="AAPL",
        name="Apple",
        market="us_market",
        date="20260708",
        price=210.0,
        change_pct=1.0,
        turnover=1000,
        source="sina",
        currency="USD",
    )
    core = SimpleNamespace(
        normalize_stock_symbol=lambda symbol: ("AAPL", "us_market"),
        get_index=lambda date: [],
        fetch_hk_indices_sina=lambda symbols, date: [],
        fetch_us_indices_sina=lambda symbols, date: [],
        fetch_northbound_flow_snapshot=lambda date: {},
        get_fund_flow=lambda date, strict_date=False: {"_unavailable": "not a-share"},
        fetch_eastmoney_board_list=lambda kind, date, limit=100: {"rows": []},
        get_zt_pool=lambda date: {"_error": "not a-share"},
        get_dt_pool=lambda date: {"_error": "not a-share"},
        get_zb_pool=lambda date: {"_error": "not a-share"},
        fetch_us_stocks_sina=lambda symbols, date: [quote],
        fetch_us_stocks_tencent=lambda symbols, date: [],
        fetch_us_stocks_direct=lambda symbols, date: [],
        fetch_stock_fund_flow_daily=lambda symbol, date, limit=20: {"rows": []},
        fetch_block_trades=lambda symbol, date, limit=10: {"rows": []},
        eastmoney_fast_news=lambda *args, **kwargs: {"data": []},
        sina_roll_news=lambda *args, **kwargs: {"data": []},
        futu_news_search=lambda *args, **kwargs: {"data": []},
        _news_aliases=lambda symbol, name="": [symbol, name],
        fetch_global_market_extensions=lambda symbol, date, rich_source=False: {
            "symbol": symbol,
            "quote_source_plan": ["sina", "tencent", "eastmoney"],
            "history": {"rows": [{"date": date, "close": 210.0}], "source": "eastmoney"},
            "rich_source_skipped": ["sec_filings", "xbrl_financials", "analyst_estimates", "institutional_holdings", "us_options", "full_financials"],
        },
    )

    evidence = build_stock_evidence(core, "AAPL", "20260708")

    stock = evidence.modules["STOCK"]
    assert stock["global_market"]["history"]["source"] == "eastmoney"
    assert "global_market" in evidence.meta["source_events"][0]
