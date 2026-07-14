"""A-share capital/event adapters backed by Eastmoney HTTP endpoints."""

from __future__ import annotations

import time
import urllib.parse
from typing import Any, Callable

from ..contracts import SourceResult
from .eastmoney_base import EastmoneyHttpAdapter, display_date, normalize_code, number

SOURCE = "eastmoney.capital"

A_SHARE_EVIDENCE_MAP = {
    "stock_fund_flow": "stock.M2",
    "industry_fund_flow": "daily.M2",
    "concept_fund_flow": "daily.M2",
    "margin": "stock.M4",
    "lhb": "stock.M3",
    "lockup": "risk_calendar",
    "holder_count": "stock.M5",
    "block_trades": "stock.M5",
    "dividend": "risk_calendar",
    "announcements": "risk_calendar",
    "research_reports": "stock.supplemental",
    "classification": "stock.M2/M5/M6",
}


def _ok(capability: str, symbol: str, rows: list[dict[str, Any]], trade_date: str, *, as_of: str = "") -> SourceResult:
    return SourceResult(
        data={
            "symbol": normalize_code(symbol) or symbol,
            "rows": rows,
            "count": len(rows),
            "mapping": A_SHARE_EVIDENCE_MAP[capability],
        },
        source=SOURCE,
        as_of=as_of or (rows[0].get("date") if rows else display_date(trade_date)),
    )


def stock_fund_flow_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 20) -> SourceResult:
        code = normalize_code(symbol)
        params = {
            "secid": f"{'1' if code.startswith(('6', '9')) else '0'}.{code}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": 101,
            "lmt": max(1, min(int(limit or 20), 120)),
            "_": int(time.time() * 1000),
        }
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?" + urllib.parse.urlencode(params)
        payload = client.get_json(
            url,
            capability="stock_fund_flow",
            market="a",
            symbol=code,
            effective_date=trade_date,
            parameters={key: value for key, value in params.items() if key != "_"},
        )
        if payload.get("_error"):
            return SourceResult(source=SOURCE, error=payload["_error"])
        rows = []
        for line in (payload.get("data") or {}).get("klines") or []:
            parts = str(line).split(",")
            if len(parts) < 6:
                continue
            rows.append(
                {
                    "date": display_date(parts[0]),
                    "main_net_yuan": number(parts[1]),
                    "small_net_yuan": number(parts[2]),
                    "mid_net_yuan": number(parts[3]),
                    "big_net_yuan": number(parts[4]),
                    "super_big_net_yuan": number(parts[5]),
                    "main_net_pct": number(parts[6]) if len(parts) > 6 else None,
                }
            )
        if not rows:
            return SourceResult(source=SOURCE, error="empty stock fund flow")
        return _ok("stock_fund_flow", code, rows, trade_date, as_of=rows[-1]["date"])

    return fetch


def board_fund_flow_adapter(client: EastmoneyHttpAdapter, board_type: str) -> Callable[[str, str], SourceResult]:
    normalized_type = "concept" if board_type == "concept" else "industry"

    def fetch(symbol: str, trade_date: str, limit: int = 50) -> SourceResult:
        fs = "m:90+t:3" if normalized_type == "concept" else "m:90+t:2"
        params = {
            "pn": 1,
            "pz": max(1, min(int(limit or 50), 200)),
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f62",
            "fs": fs,
            "fields": "f12,f14,f62,f184",
            "_": int(time.time() * 1000),
        }
        url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
        payload = client.get_json(
            url,
            capability=f"{normalized_type}_fund_flow",
            market="a",
            symbol=normalized_type,
            effective_date=trade_date,
            parameters={key: value for key, value in params.items() if key != "_"},
        )
        items = ((payload.get("data") or {}).get("diff") or [])
        if isinstance(items, dict):
            items = list(items.values())
        rows = [
            {
                "code": str(item.get("f12") or ""),
                "name": str(item.get("f14") or ""),
                "main_net_yuan": number(item.get("f62")),
                "main_net_pct": number(item.get("f184")),
            }
            for item in items
            if isinstance(item, dict)
        ]
        mapping = "concept_fund_flow" if normalized_type == "concept" else "industry_fund_flow"
        return _ok(mapping, symbol, rows, trade_date)

    return fetch


def margin_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 10) -> SourceResult:
        rows = client.datacenter(
            "RPTA_WEB_RZRQ_GGMX",
            symbol=symbol,
            trade_date=trade_date,
            capability="margin",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="TRADE_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("TRADE_DATE")),
                "fin_balance_yuan": number(row.get("FIN_BALANCE")),
                "sec_balance_yuan": number(row.get("SEC_BALANCE")),
                "margin_balance_yuan": number(row.get("RZYE") or row.get("RZRQYE")),
            }
            for row in rows
        ]
        return _ok("margin", symbol, parsed, trade_date)

    return fetch


def lhb_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 20) -> SourceResult:
        rows = client.datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            symbol=symbol,
            trade_date=trade_date,
            capability="lhb",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="TRADE_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("TRADE_DATE")),
                "reason": row.get("EXPLANATION") or row.get("EXPLANATION_TYPE"),
                "buy_yuan": number(row.get("BUY_AMT")),
                "sell_yuan": number(row.get("SELL_AMT")),
                "net_buy_yuan": number(row.get("NET_BUY_AMT") or row.get("NET_BUY")),
            }
            for row in rows
        ]
        return _ok("lhb", symbol, parsed, trade_date)

    return fetch


def lockup_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 20) -> SourceResult:
        rows = client.datacenter(
            "RPT_LIFT_STAGE",
            symbol=symbol,
            trade_date=trade_date,
            capability="lockup",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="FREE_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("FREE_DATE") or row.get("LIFT_DATE")),
                "lift_shares": number(row.get("LIFT_NUM") or row.get("FREE_SHARES")),
                "lift_market_cap_yuan": number(row.get("LIFT_MARKET_CAP")),
            }
            for row in rows
        ]
        return _ok("lockup", symbol, parsed, trade_date)

    return fetch


def holder_count_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 8) -> SourceResult:
        rows = client.datacenter(
            "RPT_HOLDERNUMLATEST",
            symbol=symbol,
            trade_date=trade_date,
            capability="holder_count",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="END_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("END_DATE")),
                "holder_count": int(number(row.get("HOLDER_TOTAL_NUM")) or 0) if number(row.get("HOLDER_TOTAL_NUM")) is not None else None,
                "change_pct": number(row.get("HOLDER_NUM_RATIO")),
            }
            for row in rows
        ]
        return _ok("holder_count", symbol, parsed, trade_date)

    return fetch


def block_trade_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 10) -> SourceResult:
        rows = client.datacenter(
            "RPT_DATA_BLOCKTRADE",
            symbol=symbol,
            trade_date=trade_date,
            capability="block_trades",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="TRADE_DATE",
        )
        parsed = []
        for row in rows:
            close = number(row.get("CLOSE_PRICE"))
            price = number(row.get("DEAL_PRICE"))
            parsed.append(
                {
                    "date": display_date(row.get("TRADE_DATE")),
                    "price": price,
                    "close": close,
                    "premium_pct": round((price / close - 1) * 100, 2) if price is not None and close else None,
                    "amount_yuan": number(row.get("DEAL_AMT")),
                    "buyer": row.get("BUYER_NAME") or "",
                    "seller": row.get("SELLER_NAME") or "",
                }
            )
        return _ok("block_trades", symbol, parsed, trade_date)

    return fetch


def dividend_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 10) -> SourceResult:
        rows = client.datacenter(
            "RPT_SHAREBONUS_DET",
            symbol=symbol,
            trade_date=trade_date,
            capability="dividend",
            filter_str=f'(SECURITY_CODE="{normalize_code(symbol)}")',
            page_size=limit,
            sort_columns="EX_DIVIDEND_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("EX_DIVIDEND_DATE") or row.get("EQUITY_RECORD_DATE")),
                "cash_dividend_per_10": number(row.get("CASH_DIVIDEND_RATIO")),
                "bonus_share_per_10": number(row.get("BONUS_RATIO")),
                "transfer_share_per_10": number(row.get("TRANSFER_RATIO")),
            }
            for row in rows
        ]
        return _ok("dividend", symbol, parsed, trade_date)

    return fetch
