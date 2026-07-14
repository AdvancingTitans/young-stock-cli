import json

from young_stock.cache_v2 import JsonCacheV2
from young_stock.health import SourceHealthBook
from young_stock.sources import DataSource, SourceResolver
from young_stock.sources.adapters.cninfo import announcements_adapter as cninfo_announcements_adapter
from young_stock.sources.adapters.eastmoney_base import EastmoneyHttpAdapter
from young_stock.sources.adapters.eastmoney_capital import (
    A_SHARE_EVIDENCE_MAP,
    block_trade_adapter,
    board_fund_flow_adapter,
    dividend_adapter,
    holder_count_adapter,
    lhb_adapter,
    lockup_adapter,
    margin_adapter,
    stock_fund_flow_adapter,
)
from young_stock.sources.adapters.eastmoney_market import classification_adapter
from young_stock.sources.adapters.eastmoney_reports import announcements_adapter, research_reports_adapter
from young_stock.sources.adapters.mootdx import quote_adapter as mootdx_quote_adapter
from young_stock.sources.adapters.ths import board_adapter as ths_board_adapter
from young_stock.sources.contracts import SourcePolicy, SourceResult


class Response:
    status_code = 200
    content = b""

    def __init__(self, payload):
        self.content = json.dumps(payload).encode()


class Session:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return Response(self.payloads.pop(0))


def adapter(payloads, tmp_path):
    return EastmoneyHttpAdapter(session=Session(payloads), cache=JsonCacheV2(tmp_path), max_attempts=1)


def datacenter(rows):
    return {"success": True, "result": {"data": rows}}


def test_stock_fund_flow_parser_contract_dates_units_and_missing_values(tmp_path):
    client = adapter(
        [
            {
                "data": {
                    "name": "贵州茅台",
                    "klines": [
                        "2026-07-07,100000000,1,2,3,4,5",
                        "2026-07-08,200000000,,,30000000,40000000,6",
                    ],
                }
            }
        ],
        tmp_path,
    )

    result = stock_fund_flow_adapter(client)("600519", "20260708")

    assert result.ok
    assert result.source == "eastmoney.capital"
    assert result.as_of == "2026-07-08"
    assert result.data["mapping"] == "stock.M2"
    assert result.data["rows"][-1]["main_net_yuan"] == 200000000.0
    assert result.data["rows"][-1]["small_net_yuan"] is None
    assert "f52" not in result.data["rows"][-1]


def test_datacenter_adapters_normalize_units_dates_and_empty_values(tmp_path):
    client = adapter(
        [
            datacenter([{"SECURITY_CODE": "600519", "FIN_BALANCE": 100000000, "TRADE_DATE": "2026-07-08 00:00:00"}]),
            datacenter([{"TRADE_DATE": "2026-07-08", "NET_BUY_AMT": None, "EXPLANATION": "日涨幅偏离值"}]),
            datacenter([{"FREE_DATE": "2026-07-20", "LIFT_MARKET_CAP": 200000000}]),
            datacenter([{"END_DATE": "2026-03-31", "HOLDER_TOTAL_NUM": 12345}]),
            datacenter([{"TRADE_DATE": "2026-07-08", "DEAL_PRICE": 10, "CLOSE_PRICE": 12, "DEAL_AMT": 30000000}]),
            datacenter([{"EX_DIVIDEND_DATE": "2026-07-10", "CASH_DIVIDEND_RATIO": 30}]),
        ],
        tmp_path,
    )

    assert margin_adapter(client)("600519", "20260708").data["rows"][0]["fin_balance_yuan"] == 100000000.0
    assert lhb_adapter(client)("600519", "20260708").data["rows"][0]["net_buy_yuan"] is None
    assert lockup_adapter(client)("600519", "20260708").data["rows"][0]["lift_market_cap_yuan"] == 200000000.0
    assert holder_count_adapter(client)("600519", "20260708").data["rows"][0]["holder_count"] == 12345
    assert block_trade_adapter(client)("600519", "20260708").data["rows"][0]["premium_pct"] == -16.67
    assert dividend_adapter(client)("600519", "20260708").data["rows"][0]["cash_dividend_per_10"] == 30.0


def test_market_report_adapters_and_evidence_map_use_standard_payloads(tmp_path):
    client = adapter(
        [
            {
                "data": {
                    "diff": [
                        {"f12": "BK0475", "f14": "白酒", "f62": 120000000, "f184": 2.5},
                    ]
                }
            },
            {"data": {"bklist": [{"BOARD_CODE": "BK0475", "BOARD_NAME": "白酒", "BOARD_TYPE": "industry"}]}},
            datacenter([{"TITLE": "重大事项公告", "NOTICE_DATE": "2026-07-08", "ART_CODE": "AN1"}]),
            datacenter([{"TITLE": "公司点评", "REPORT_DATE": "2026-07-07", "ORG_NAME": "某证券", "RATING": "买入"}]),
        ],
        tmp_path,
    )

    board = board_fund_flow_adapter(client, "industry")("market", "20260708")
    classification = classification_adapter(client)("600519", "20260708")
    announcements = announcements_adapter(client)("600519", "20260708")
    reports = research_reports_adapter(client)("600519", "20260708")

    assert board.data["rows"][0] == {"code": "BK0475", "name": "白酒", "main_net_yuan": 120000000.0, "main_net_pct": 2.5}
    assert classification.data["industry"] == ["白酒"]
    assert announcements.data["rows"][0]["title"] == "重大事项公告"
    assert reports.data["rows"][0]["rating"] == "买入"
    assert A_SHARE_EVIDENCE_MAP["announcements"] == "risk_calendar"
    assert A_SHARE_EVIDENCE_MAP["research_reports"] == "stock.supplemental"


def test_source_resolver_fallback_and_adapter_cache(tmp_path):
    session = Session([{"data": {"name": "贵州茅台", "klines": ["2026-07-08,1,2,3,4,5,6"]}}])
    client = EastmoneyHttpAdapter(session=session, cache=JsonCacheV2(tmp_path), max_attempts=1)
    fetch = stock_fund_flow_adapter(client)
    resolver = SourceResolver(
        registry=(
            DataSource("broken", ("a",), ("flow",), "primary", "http", "broken"),
            DataSource("eastmoney", ("a",), ("flow",), "fallback", "http", "eastmoney"),
        ),
        health=SourceHealthBook(),
    )

    result = resolver.resolve(
        "a",
        "flow",
        {
            "broken": lambda *_: (_ for _ in ()).throw(RuntimeError("timeout")),
            "eastmoney": fetch,
        },
        "600519",
        "20260708",
    )
    cached = fetch("600519", "20260708")

    assert result.ok
    assert result.attempts == ("broken: timeout", "eastmoney: ok")
    assert cached.ok
    assert len(session.calls) == 1


def test_each_http_adapter_returns_source_result_and_uses_cache(tmp_path):
    cases = [
        (
            stock_fund_flow_adapter,
            [{"data": {"name": "贵州茅台", "klines": ["2026-07-08,1,2,3,4,5,6"]}}],
        ),
        (lambda client: board_fund_flow_adapter(client, "industry"), [{"data": {"diff": [{"f12": "BK1", "f14": "白酒"}]}}]),
        (
            margin_adapter,
            [datacenter([{"TRADE_DATE": "2026-07-08", "FIN_BALANCE": 1}])],
        ),
        (
            lhb_adapter,
            [datacenter([{"TRADE_DATE": "2026-07-08", "NET_BUY_AMT": 1}])],
        ),
        (
            lockup_adapter,
            [datacenter([{"FREE_DATE": "2026-07-08", "LIFT_MARKET_CAP": 1}])],
        ),
        (
            holder_count_adapter,
            [datacenter([{"END_DATE": "2026-07-08", "HOLDER_TOTAL_NUM": 1}])],
        ),
        (
            block_trade_adapter,
            [datacenter([{"TRADE_DATE": "2026-07-08", "DEAL_PRICE": 1, "CLOSE_PRICE": 1}])],
        ),
        (
            dividend_adapter,
            [datacenter([{"EX_DIVIDEND_DATE": "2026-07-08", "CASH_DIVIDEND_RATIO": 1}])],
        ),
        (
            classification_adapter,
            [{"data": {"bklist": [{"BOARD_NAME": "白酒", "BOARD_TYPE": "industry"}]}}],
        ),
        (
            announcements_adapter,
            [datacenter([{"NOTICE_DATE": "2026-07-08", "TITLE": "公告"}])],
        ),
        (
            research_reports_adapter,
            [datacenter([{"REPORT_DATE": "2026-07-08", "TITLE": "研报"}])],
        ),
    ]

    for index, (factory, payloads) in enumerate(cases):
        session = Session(payloads)
        client = EastmoneyHttpAdapter(session=session, cache=JsonCacheV2(tmp_path / str(index)), max_attempts=1)
        fetch = factory(client)
        first = fetch("600519", "20260708")
        second = fetch("600519", "20260708")

        assert isinstance(first, SourceResult)
        assert isinstance(second, SourceResult)
        assert first.ok
        assert second.ok
        assert len(session.calls) == 1


def test_optional_placeholder_adapters_return_source_result_without_required_dependencies():
    for fetch in (
        cninfo_announcements_adapter(),
        ths_board_adapter(),
        mootdx_quote_adapter(SourcePolicy()),
    ):
        result = fetch("600519", "20260708")

        assert isinstance(result, SourceResult)
        assert not result.ok
