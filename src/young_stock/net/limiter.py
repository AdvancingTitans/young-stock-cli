from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class _LimitState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    semaphore: threading.BoundedSemaphore | None = None
    max_concurrency: int = 0
    next_allowed_at: float = 0.0


class DomainRateLimiter:
    def __init__(self, *, clock=time, jitter: Callable[[float, float], float] | None = None):
        self._clock = clock
        self._jitter = jitter or random.uniform
        self._states: dict[str, _LimitState] = {}
        self._states_lock = threading.Lock()

    def _state_for(self, group: str, max_concurrency: int) -> _LimitState:
        max_concurrency = max(1, int(max_concurrency or 1))
        with self._states_lock:
            state = self._states.setdefault(group, _LimitState())
            if state.semaphore is None or state.max_concurrency != max_concurrency:
                state.semaphore = threading.BoundedSemaphore(max_concurrency)
                state.max_concurrency = max_concurrency
            return state

    @contextmanager
    def acquire(
        self,
        group: str,
        *,
        max_concurrency: int,
        min_interval: float = 0.0,
        jitter_range: tuple[float, float] = (0.0, 0.0),
    ) -> Iterator[None]:
        state = self._state_for(group, max_concurrency)
        assert state.semaphore is not None
        state.semaphore.acquire()
        try:
            with state.lock:
                now = self._clock.monotonic()
                wait = max(0.0, state.next_allowed_at - now)
                if wait > 0:
                    self._clock.sleep(wait)
                    now = self._clock.monotonic()
                low, high = jitter_range
                jitter = self._jitter(low, high) if high or low else 0.0
                # ponytail: one timestamp per domain group is enough here; upgrade to token buckets if CLI adds bulk crawling.
                state.next_allowed_at = now + max(0.0, float(min_interval or 0.0)) + max(0.0, jitter)
            yield
        finally:
            state.semaphore.release()
