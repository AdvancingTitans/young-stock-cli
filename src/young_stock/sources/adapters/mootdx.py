"""Optional mootdx adapter, intentionally rich-source only."""

from __future__ import annotations

from typing import Callable

from ..contracts import SourcePolicy, SourceResult


def quote_adapter(policy: SourcePolicy | None = None) -> Callable[[str, str], SourceResult]:
    selected = policy or SourcePolicy()

    def fetch(symbol: str, trade_date: str) -> SourceResult:
        del symbol, trade_date
        if not selected.rich_source:
            return SourceResult(source="mootdx", error="mootdx requires --rich-source")
        try:
            import mootdx  # noqa: F401
        except ImportError:
            return SourceResult(source="mootdx", error="optional dependency unavailable: mootdx")
        return SourceResult(source="mootdx", error="mootdx quote not wired for default A-share extensions")

    return fetch
