"""A-share market structure adapters."""

from __future__ import annotations

import time
import urllib.parse
from typing import Callable

from ..contracts import SourceResult
from .eastmoney_base import EastmoneyHttpAdapter, display_date, normalize_code


def classification_adapter(client: EastmoneyHttpAdapter) -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str) -> SourceResult:
        code = normalize_code(symbol)
        params = {"ut": "fa5fd1943c7b386f172d6893dbfba10b", "fltt": 2, "fields": "f12,f14", "_": int(time.time() * 1000)}
        url = "https://push2.eastmoney.com/api/qt/slist/get?" + urllib.parse.urlencode(params)
        payload = client.get_json(
            url,
            capability="classification",
            market="a",
            symbol=code,
            effective_date=trade_date,
            parameters={key: value for key, value in params.items() if key != "_"},
            allow_empty=True,
        )
        boards = (payload.get("data") or {}).get("bklist") or []
        industry = []
        concepts = []
        for item in boards:
            name = item.get("BOARD_NAME") or item.get("name")
            if not name:
                continue
            if str(item.get("BOARD_TYPE") or "").lower() in {"industry", "hy"}:
                industry.append(str(name))
            else:
                concepts.append(str(name))
        return SourceResult(
            data={
                "symbol": code,
                "industry": industry,
                "concepts": concepts,
                "mapping": "stock.M2/M5/M6",
            },
            source="eastmoney.market",
            as_of=display_date(trade_date),
        )

    return fetch
