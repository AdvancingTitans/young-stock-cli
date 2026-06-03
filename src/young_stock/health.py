"""Lightweight data-source health scoring."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass(frozen=True)
class SourceHealthSnapshot:
    name: str
    attempts: int
    failures: int
    success_rate: float
    average_latency_ms: float
    should_skip: bool


@dataclass
class _SourceHealth:
    window_size: int
    events: deque[tuple[bool, float]] = field(init=False)
    last_failure_at: float | None = None

    def __post_init__(self) -> None:
        self.events = deque(maxlen=self.window_size)

    def record(self, ok: bool, latency_ms: float) -> None:
        self.events.append((ok, max(0.0, latency_ms)))
        if not ok:
            self.last_failure_at = monotonic()

    def snapshot(self, name: str) -> SourceHealthSnapshot:
        attempts = len(self.events)
        failures = sum(1 for ok, _ in self.events if not ok)
        success_rate = (attempts - failures) / attempts if attempts else 1.0
        average_latency = sum(latency for _, latency in self.events) / attempts if attempts else 0.0
        should_skip = attempts >= 3 and success_rate < 0.5
        return SourceHealthSnapshot(name, attempts, failures, success_rate, average_latency, should_skip)


class SourceHealthBook:
    def __init__(self, window_size: int = 8) -> None:
        self.window_size = window_size
        self._sources: dict[str, _SourceHealth] = {}

    def _source(self, name: str) -> _SourceHealth:
        if name not in self._sources:
            self._sources[name] = _SourceHealth(self.window_size)
        return self._sources[name]

    def record(self, name: str, ok: bool, latency_ms: float) -> None:
        self._source(name).record(ok, latency_ms)

    def snapshot(self, name: str) -> SourceHealthSnapshot:
        return self._source(name).snapshot(name)

    def should_skip(self, name: str) -> bool:
        return self.snapshot(name).should_skip
