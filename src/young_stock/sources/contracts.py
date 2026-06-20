"""Small immutable contracts shared by source metadata and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataSource:
    id: str
    markets: tuple[str, ...]
    capabilities: tuple[str, ...]
    tier: str
    access: str
    health_key: str
    slow: bool = False
    optional_dependency: str | None = None


@dataclass(frozen=True)
class SourcePolicy:
    rich_source: bool = False
    browser_fallback: bool = False


@dataclass(frozen=True)
class SourceResult:
    data: Any = None
    source: str = ""
    as_of: str = ""
    error: str | None = None
    attempts: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.error is None and self.data is not None
