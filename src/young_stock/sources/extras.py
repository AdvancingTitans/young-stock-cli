"""Optional stock evidence kept small, lazy, and failure-tolerant."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Callable

import requests

SOCIAL_CACHE_TTL_SECONDS = 300
_SOCIAL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
SOCIAL_ENDPOINTS = (
    ("微博", "https://weibo.com/ajax/side/hotSearch"),
    ("知乎", "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50"),
    ("百度", "https://top.baidu.com/api/board?platform=wise&tab=realtime"),
    ("抖音", "https://www.douyin.com/aweme/v1/web/hot/search/list/"),
    ("头条", "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"),
    ("B站", "https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1"),
)


@dataclass
class StockExtras:
    financial_trends: dict[str, Any] = field(default_factory=dict)
    lhb: dict[str, Any] = field(default_factory=dict)
    social_heat: dict[str, Any] = field(default_factory=dict)
    events: dict[str, Any] = field(default_factory=dict)
    technical_fallback: dict[str, Any] = field(default_factory=dict)
    source_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _titles(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"title", "word", "query", "name", "display_name"} and isinstance(item, str):
                found.append(item)
            else:
                found.extend(_titles(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_titles(item))
    return found


def _fetch_social_json(session: Any = None) -> list[dict[str, str]]:
    client = session or requests.Session()
    rows: list[dict[str, str]] = []
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"}
    for platform, url in SOCIAL_ENDPOINTS:
        try:
            response = client.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            rows.extend({"platform": platform, "title": title} for title in _titles(response.json())[:50])
        except Exception:
            continue
    return rows


def social_heat(
    keyword: str,
    *,
    fetcher: Callable[[], list[dict[str, str]]] = _fetch_social_json,
    clock: Callable[[], float] = monotonic,
) -> dict[str, Any]:
    key = keyword.strip().lower()
    now = clock()
    cached = _SOCIAL_CACHE.get(key)
    if cached and now - cached[0] < SOCIAL_CACHE_TTL_SECONDS:
        return cached[1]
    matches = [
        row for row in fetcher()
        if key and key in str(row.get("title") or "").lower()
    ]
    result = {"keyword": keyword, "count": len(matches), "rows": matches[:20], "_source": "公开社交热榜 JSON"}
    _SOCIAL_CACHE[key] = (now, result)
    return result


def fetch_lhb(core: Any, symbol: str, trade_date: str, limit: int = 20) -> dict[str, Any]:
    normalized, market = core.normalize_stock_symbol(symbol)
    if market != "cn_market":
        return {"symbol": normalized, "rows": [], "_unavailable": "龙虎榜仅适用于 A 股"}
    rows = core.eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f'(SECURITY_CODE="{normalized}")',
        page_size=limit,
        sort_columns="TRADE_DATE",
        sort_types="-1",
    )
    parsed = [
        {
            "date": str(row.get("TRADE_DATE") or "")[:10],
            "name": row.get("SECURITY_NAME_ABBR"),
            "reason": row.get("EXPLANATION") or row.get("EXPLANATION_TYPE"),
            "buy": row.get("BUY_AMT"),
            "sell": row.get("SELL_AMT"),
            "net_buy": row.get("NET_BUY_AMT") or row.get("NET_BUY"),
        }
        for row in rows
    ]
    return {
        "symbol": normalized,
        "requested_date": trade_date,
        "rows": parsed,
        "_source": "东方财富龙虎榜",
    }


def _akshare_extras(symbol: str, trade_date: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import akshare as ak
    except ImportError:
        unavailable = {"_unavailable": "optional dependency unavailable: akshare"}
        return unavailable, unavailable.copy()
    try:
        frame = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
        ratios = frame.to_dict("records")[-5:]
        statements = {}
        for statement in ("利润表", "资产负债表", "现金流量表"):
            try:
                report = ak.stock_financial_report_sina(stock=symbol, symbol=statement)
                statements[statement] = report.to_dict("records")[-5:]
            except Exception as exc:
                statements[statement] = {"_unavailable": str(exc)}
        financials = {
            "ratio_trends": ratios,
            "statements": statements,
            "periods": 5,
            "_source": "akshare 财务摘要 + 三张表",
        }
    except Exception as exc:
        financials = {"_unavailable": f"akshare financials: {exc}"}
    try:
        frame = ak.stock_notice_report(symbol="全部", date=trade_date)
        records = frame.to_dict("records")
        events = {
            "rows": [row for row in records if symbol in str(row)][:20],
            "_source": "akshare 公告",
        }
    except Exception as exc:
        events = {"_unavailable": f"akshare notices: {exc}"}
    return financials, events


def _yfinance_technical(symbol: str) -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError:
        return {"_unavailable": "optional dependency unavailable: yfinance"}
    try:
        history = yf.Ticker(symbol).history(period="3mo", interval="1d")
        closes = [float(value) for value in history["Close"].dropna().tolist()]
        if not closes:
            return {"_unavailable": "yfinance returned no history"}
        return {
            "last_close": closes[-1],
            "ma20": sum(closes[-20:]) / min(20, len(closes)),
            "ma60": sum(closes[-60:]) / min(60, len(closes)),
            "_source": "yfinance",
        }
    except Exception as exc:
        return {"_unavailable": f"yfinance: {exc}"}


def collect_stock_extras(
    core: Any,
    symbol: str,
    trade_date: str,
    *,
    rich_source: bool = False,
) -> StockExtras:
    normalized, _ = core.normalize_stock_symbol(symbol)
    lhb = fetch_lhb(core, normalized, trade_date)
    if not rich_source:
        return StockExtras(
            financial_trends={"_unavailable": "启用 --rich-source 后可尝试 akshare"},
            lhb=lhb,
            social_heat={"_unavailable": "启用 --rich-source 后采集社交热榜"},
            events={"_unavailable": "启用 --rich-source 后可尝试公告增强"},
            technical_fallback={"_unavailable": "启用 --rich-source 后可尝试 yfinance"},
            source_trace=["eastmoney:lhb"],
        )
    financials, events = _akshare_extras(normalized, trade_date)
    social = social_heat(normalized)
    technical = _yfinance_technical(normalized)
    return StockExtras(
        financial_trends=financials,
        lhb=lhb,
        social_heat=social,
        events=events,
        technical_fallback=technical,
        source_trace=["eastmoney:lhb", "akshare:financials/events", "social:json", "yfinance:technical"],
    )
