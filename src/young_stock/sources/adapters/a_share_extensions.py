"""A-share extension evidence collector built from structured adapters."""

from __future__ import annotations

from typing import Any, Callable

from .eastmoney_base import EastmoneyHttpAdapter
from .eastmoney_capital import (
    block_trade_adapter,
    dividend_adapter,
    holder_count_adapter,
    lhb_adapter,
    lockup_adapter,
    margin_adapter,
    stock_fund_flow_adapter,
)
from .eastmoney_market import classification_adapter
from .eastmoney_reports import announcements_adapter, research_reports_adapter

RICH_SOURCE_SKIPPED = [
    "mootdx",
    "level2_orderbook",
    "tick_trades",
    "full_financials",
    "valuation_percentile_history",
    "consensus_expectations",
    "investor_qa",
    "pdf_reports",
]


def source_result_payload(result: Any) -> dict[str, Any]:
    if getattr(result, "ok", False) and isinstance(getattr(result, "data", None), dict):
        return result.data
    return {
        "rows": [],
        "_unavailable": getattr(result, "error", None) or "unavailable",
        "_source": getattr(result, "source", ""),
    }


def safe_fetch(fetcher: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return fetcher(*args, **kwargs)
    except Exception as exc:
        return type("FailedSourceResult", (), {"ok": False, "data": None, "error": str(exc), "source": ""})()


def collect_a_share_extensions(symbol: str, date_str: str, *, rich_source: bool = False) -> dict[str, Any]:
    """Collect default A-share extension evidence through SourceResult adapters."""
    client = EastmoneyHttpAdapter()
    fetchers = {
        "stock_fund_flow": stock_fund_flow_adapter(client),
        "margin": margin_adapter(client),
        "lhb": lhb_adapter(client),
        "lockup": lockup_adapter(client),
        "holder_count": holder_count_adapter(client),
        "block_trades": block_trade_adapter(client),
        "dividend": dividend_adapter(client),
        "announcements": announcements_adapter(client),
        "research_reports": research_reports_adapter(client),
        "classification": classification_adapter(client),
    }
    payload = {
        key: source_result_payload(safe_fetch(fetcher, symbol, date_str))
        for key, fetcher in fetchers.items()
    }
    if not rich_source:
        payload["rich_source_skipped"] = list(RICH_SOURCE_SKIPPED)
    return payload
