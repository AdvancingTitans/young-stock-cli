"""Shared Eastmoney HTTP/cache helpers for structured adapters."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

from young_stock.cache_v2 import CacheKey, JsonCacheV2
from young_stock.net import DomainPolicy, ManagedHttpClient

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://data.eastmoney.com/",
}


class EastmoneyHttpAdapter:
    def __init__(
        self,
        *,
        session: Any | None = None,
        cache: JsonCacheV2 | None = None,
        cache_root: str | Path | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.http = ManagedHttpClient(
            session=session,
            policies={
                "eastmoney": DomainPolicy(
                    domain_group="eastmoney",
                    max_concurrency=1,
                    min_interval=1.0,
                    jitter_range=(0.05, 0.25),
                    proxy_mode="direct",
                )
            },
            max_attempts=max_attempts,
        )
        self.cache = cache or JsonCacheV2(Path(cache_root or Path.home() / ".cache" / "young-stock-cli" / "v2"))

    def get_json(
        self,
        url: str,
        *,
        capability: str,
        market: str,
        symbol: str,
        effective_date: str,
        parameters: dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        key = CacheKey(2, capability, "eastmoney", market, symbol, compact_date(effective_date), parameters or {})
        cached = self.cache.load(key)
        if cached is not None and isinstance(cached.payload, dict):
            return cached.payload
        response = self.http.request("GET", url, headers=DEFAULT_HEADERS)
        status = getattr(response, "status_code", 200)
        if status >= 400:
            return {"_error": f"HTTP {status}"}
        content = getattr(response, "content", b"")
        text = content.decode("utf-8", errors="ignore") if content else str(getattr(response, "text", ""))
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return {"_error": str(exc)}
        as_of = extract_as_of(payload, effective_date)
        self.cache.save_payload(
            key,
            payload,
            source="eastmoney",
            as_of=as_of,
            stale=compact_date(as_of) != compact_date(effective_date),
            allow_empty=allow_empty,
        )
        return payload

    def datacenter(
        self,
        report_name: str,
        *,
        symbol: str,
        trade_date: str,
        capability: str,
        columns: str = "ALL",
        filter_str: str = "",
        page_size: int = 20,
        page_number: int = 1,
        sort_columns: str = "",
        sort_types: str = "-1",
    ) -> list[dict[str, Any]]:
        params = {
            "reportName": report_name,
            "columns": columns,
            "filter": filter_str,
            "pageSize": max(1, min(int(page_size or 20), 500)),
            "pageNumber": max(1, int(page_number or 1)),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
            "_": int(time.time() * 1000),
        }
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get?" + urllib.parse.urlencode(params)
        payload = self.get_json(
            url,
            capability=capability,
            market="a",
            symbol=normalize_code(symbol),
            effective_date=trade_date,
            parameters={key: value for key, value in params.items() if key != "_"},
            allow_empty=True,
        )
        if payload.get("_error"):
            return []
        data = (payload.get("result") or {}).get("data") or []
        return [row for row in data if isinstance(row, dict)]


def compact_date(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:8] if len(digits) >= 8 else str(value or "")


def display_date(value: Any) -> str:
    digits = compact_date(value)
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return str(value or "")


def normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[2:]
    for suffix in (".SH", ".SZ", ".BJ"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    digits = "".join(char for char in text if char.isdigit())
    return digits[-6:] if len(digits) >= 6 else digits


def extract_as_of(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("date", "TRADE_DATE", "NOTICE_DATE", "REPORT_DATE", "FREE_DATE", "END_DATE"):
            value = payload.get(key)
            if value:
                return display_date(value)
        data = payload.get("data")
        if isinstance(data, dict):
            klines = data.get("klines")
            if isinstance(klines, list) and klines:
                return display_date(str(klines[-1]).split(",", 1)[0])
        rows = ((payload.get("result") or {}).get("data") or []) if isinstance(payload.get("result"), dict) else []
        if rows and isinstance(rows[0], dict):
            return extract_as_of(rows[0], fallback)
    return display_date(fallback)


def number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def integer(value: Any) -> int | None:
    parsed = number(value)
    return int(parsed) if parsed is not None else None
