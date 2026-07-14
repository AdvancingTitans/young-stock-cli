"""THS structured adapter placeholders for A-share boards."""

from __future__ import annotations

from typing import Callable

from ..contracts import SourceResult


def board_adapter() -> Callable[[str, str], SourceResult]:
    def fetch(symbol: str, trade_date: str) -> SourceResult:
        del symbol, trade_date
        return SourceResult(source="ths", error="ths structured adapter not enabled in this stage")

    return fetch
