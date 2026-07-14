from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    open_seconds: float = 300.0
    opened_at: float | None = None
    reason: str = ""

    def is_open(self, now: float | None = None) -> bool:
        if self.opened_at is None:
            return False
        now = time.monotonic() if now is None else now
        if now - self.opened_at >= self.open_seconds:
            self.opened_at = None
            self.reason = ""
            return False
        return True

    def open(self, reason: str, *, now: float | None = None) -> None:
        self.opened_at = time.monotonic() if now is None else now
        self.reason = reason


@dataclass
class DomainPolicy:
    domain_group: str = ""
    max_concurrency: int = 4
    min_interval: float = 0.0
    jitter_range: tuple[float, float] = (0.0, 0.0)
    backoff_base: float = 1.0
    backoff_factor: float = 2.0
    backoff_jitter: tuple[float, float] = (0.0, 0.0)
    max_backoff: float = 30.0
    proxy_mode: str = "direct"
    proxies: dict[str, str] | None = None
    fallback_domains: tuple[str, ...] = ()
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def group_for(self, host: str) -> str:
        return self.domain_group or host
