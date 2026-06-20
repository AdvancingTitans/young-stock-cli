"""Policy- and health-aware fallback resolution."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from time import monotonic

from young_stock.health import SOURCE_HEALTH, SourceHealthBook

from .contracts import DataSource, SourcePolicy, SourceResult
from .registry import DATA_SOURCES, find_sources

Adapter = Callable[..., SourceResult]
_TIER_ORDER = {"primary": 0, "fallback": 1, "official": 2}


class SourceResolver:
    def __init__(
        self,
        *,
        registry: tuple[DataSource, ...] = DATA_SOURCES,
        health: SourceHealthBook | None = None,
    ) -> None:
        self.registry = registry
        self.health = health or SOURCE_HEALTH

    def resolve(
        self,
        market: str,
        capability: str,
        adapters: Mapping[str, Adapter],
        *args: object,
        policy: SourcePolicy | None = None,
        **kwargs: object,
    ) -> SourceResult:
        candidates = find_sources(market, capability, policy, registry=self.registry)
        candidates.sort(
            key=lambda source: (
                _TIER_ORDER[source.tier],
                self.health.should_skip(source.health_key),
            )
        )
        attempts: list[str] = []

        for source in candidates:
            adapter = adapters.get(source.id)
            if adapter is None:
                continue
            started = monotonic()
            try:
                result = adapter(*args, **kwargs)
                if not isinstance(result, SourceResult):
                    raise TypeError("adapter must return SourceResult")
            except Exception as exc:  # adapters are an external-data trust boundary
                latency_ms = (monotonic() - started) * 1000
                self.health.record(source.health_key, ok=False, latency_ms=latency_ms)
                attempts.append(f"{source.id}: {exc}")
                continue

            latency_ms = (monotonic() - started) * 1000
            self.health.record(source.health_key, ok=result.ok, latency_ms=latency_ms)
            attempts.append(f"{source.id}: {'ok' if result.ok else result.error or 'unavailable'}")
            if result.ok:
                return replace(
                    result,
                    source=result.source or source.id,
                    attempts=tuple(attempts),
                )

        return SourceResult(error="all sources failed", attempts=tuple(attempts))
