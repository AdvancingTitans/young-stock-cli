"""Public source registry and resolver API."""

from .contracts import DataSource, SourcePolicy, SourceResult
from .registry import DATA_SOURCES, find_sources
from .resolver import SourceResolver
from .runtime import resolve_news, resolve_quote

__all__ = [
    "DATA_SOURCES",
    "DataSource",
    "SourcePolicy",
    "SourceResolver",
    "SourceResult",
    "find_sources",
    "resolve_news",
    "resolve_quote",
]
