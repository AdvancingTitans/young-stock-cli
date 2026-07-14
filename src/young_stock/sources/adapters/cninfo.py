"""CNInfo official-source placeholders.

The default stage uses Eastmoney HTTP summaries; CNInfo can be wired as an
official fallback without changing report contracts.
"""

from __future__ import annotations

from typing import Callable

from ..contracts import SourceResult


def announcements_adapter() -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str) -> SourceResult:
        del symbol, trade_date
        return SourceResult(source="cninfo", error="cninfo adapter not enabled in this stage")

    return fetch
