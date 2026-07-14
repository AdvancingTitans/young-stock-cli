"""Eastmoney announcement and research-report adapters."""

from __future__ import annotations

from typing import Callable

from ..contracts import SourceResult
from .eastmoney_base import EastmoneyHttpAdapter, display_date, normalize_code, number


def announcements_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 10) -> SourceResult:
        code = normalize_code(symbol)
        rows = client.datacenter(
            "RPT_LICO_FN_CPD",
            symbol=code,
            trade_date=trade_date,
            capability="announcements",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=limit,
            sort_columns="NOTICE_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("NOTICE_DATE")),
                "title": row.get("TITLE") or row.get("NOTICE_TITLE"),
                "category": row.get("ANN_RELCOLUMNS") or row.get("COLUMNS"),
                "url": row.get("Url") or row.get("URL") or row.get("ART_CODE"),
            }
            for row in rows
        ]
        return SourceResult(
            data={"symbol": code, "rows": parsed, "count": len(parsed), "mapping": "risk_calendar"},
            source="eastmoney.reports",
            as_of=parsed[0]["date"] if parsed else display_date(trade_date),
        )

    return fetch


def research_reports_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str, limit: int = 10) -> SourceResult:
        code = normalize_code(symbol)
        rows = client.datacenter(
            "RPT_RESEARCH_REPORT",
            symbol=code,
            trade_date=trade_date,
            capability="research_reports",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=limit,
            sort_columns="REPORT_DATE",
        )
        parsed = [
            {
                "date": display_date(row.get("REPORT_DATE")),
                "title": row.get("TITLE"),
                "org": row.get("ORG_NAME"),
                "analyst": row.get("ANALYST_NAME"),
                "rating": row.get("RATING"),
                "target_price": number(row.get("TARGET_PRICE")),
                "pdf_url": row.get("PDF_URL") or row.get("ATTACH_URL"),
            }
            for row in rows
        ]
        return SourceResult(
            data={"symbol": code, "rows": parsed, "count": len(parsed), "mapping": "stock.supplemental"},
            source="eastmoney.reports",
            as_of=parsed[0]["date"] if parsed else display_date(trade_date),
        )

    return fetch
