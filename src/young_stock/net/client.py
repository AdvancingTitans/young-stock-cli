from __future__ import annotations

import email.utils
import random
import time
import urllib.parse
from typing import Any

import requests

from .limiter import DomainRateLimiter
from .policy import DomainPolicy
from .trace import RequestTrace, scrub_headers, scrub_url


class CircuitOpenError(RuntimeError):
    pass


_EASTMONEY_HOST_PARTS = ("eastmoney.com", "eastmoney.cn")


class ManagedHttpClient:
    def __init__(
        self,
        *,
        session: Any | None = None,
        policies: dict[str, DomainPolicy] | None = None,
        default_policy: DomainPolicy | None = None,
        limiter: DomainRateLimiter | None = None,
        clock=time,
        max_attempts: int = 3,
        timeout: float = 15.0,
        timeout_exceptions: dict[str, tuple[type[BaseException], ...]] | None = None,
    ):
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = False
        self.policies = policies or {}
        self.default_policy = default_policy or DomainPolicy()
        self.limiter = limiter or DomainRateLimiter(clock=clock)
        self.clock = clock
        self.max_attempts = max(1, int(max_attempts or 1))
        self.timeout = timeout
        self.traces: list[RequestTrace] = []
        self.timeout_exceptions = timeout_exceptions or {
            "connect_timeout": (requests.exceptions.ConnectTimeout,),
            "read_timeout": (requests.exceptions.ReadTimeout,),
            "timeout": (requests.exceptions.Timeout,),
        }

    def policy_for(self, host: str) -> DomainPolicy:
        if host in self.policies:
            return self.policies[host]
        for key, policy in self.policies.items():
            if key.startswith("*.") and host.endswith(key[1:]):
                return policy
        if any(part in host for part in _EASTMONEY_HOST_PARTS):
            policy = self.policies.get("eastmoney") or DomainPolicy(domain_group="eastmoney", max_concurrency=1)
            self.policies.setdefault("eastmoney", policy)
            return policy
        return self.default_policy

    def request(self, method: str, url: str, **kwargs: Any):
        method = method.upper()
        headers = kwargs.pop("headers", None)
        timeout = kwargs.pop("timeout", self.timeout)
        urls = self._candidate_urls(url)
        last_exc: BaseException | None = None
        response = None
        started = self.clock.monotonic()
        trace = self._new_trace(method, urls[0], headers)

        for attempt in range(1, self.max_attempts + 1):
            current_url = urls[min(attempt - 1, len(urls) - 1)]
            host = urllib.parse.urlsplit(current_url).netloc.lower()
            policy = self.policy_for(host)
            trace.attempts = attempt
            trace.domain = host
            trace.domain_group = policy.group_for(host)
            trace.proxy_mode = policy.proxy_mode
            if current_url != url:
                trace.fallback_domain = host

            if policy.circuit_breaker.is_open(self.clock.monotonic()):
                trace.error_type = "circuit_open"
                self._finish_trace(trace, started)
                raise CircuitOpenError(policy.circuit_breaker.reason or f"circuit open for {trace.domain_group}")

            try:
                with self.limiter.acquire(
                    policy.group_for(host),
                    max_concurrency=policy.max_concurrency,
                    min_interval=policy.min_interval,
                    jitter_range=policy.jitter_range,
                ):
                    response = self._send(
                        method,
                        current_url,
                        headers,
                        timeout,
                        policy,
                        kwargs,
                        use_proxy=policy.proxy_mode == "proxy"
                        or (policy.proxy_mode == "auto" and attempt > 1 and bool(policy.proxies)),
                    )
            except BaseException as exc:
                trace.error_type = self._classify_exception(exc)
                last_exc = exc
                if attempt >= self.max_attempts:
                    self._finish_trace(trace, started)
                    raise
                self._sleep_backoff(policy, attempt)
                continue

            trace.status_code = response.status_code
            if response.status_code == 403:
                policy.circuit_breaker.open("HTTP 403", now=self.clock.monotonic())
                break
            if response.status_code == 429 and attempt < self.max_attempts:
                self.clock.sleep(self._retry_after_seconds(response.headers.get("Retry-After")) or self._backoff(policy, attempt))
                continue
            if response.status_code == 408 or 500 <= response.status_code <= 599:
                if attempt < self.max_attempts:
                    self._sleep_backoff(policy, attempt)
                    continue
            break

        self._finish_trace(trace, started)
        if response is not None:
            return response
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("request failed without response")

    def _candidate_urls(self, url: str) -> list[str]:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.netloc.lower()
        policy = self.policy_for(host)
        urls = [url]
        for fallback in policy.fallback_domains:
            urls.append(urllib.parse.urlunsplit((parsed.scheme, fallback, parsed.path, parsed.query, parsed.fragment)))
        return urls

    def _new_trace(self, method: str, url: str, headers: dict[str, str] | None) -> RequestTrace:
        host = urllib.parse.urlsplit(url).netloc.lower()
        policy = self.policy_for(host)
        return RequestTrace(
            method=method,
            safe_url=scrub_url(url),
            domain=host,
            domain_group=policy.group_for(host),
            proxy_mode=policy.proxy_mode,
            request_headers=scrub_headers(headers),
        )

    def _finish_trace(self, trace: RequestTrace, started: float) -> None:
        trace.elapsed_ms = (self.clock.monotonic() - started) * 1000
        self.traces.append(trace)

    def _send(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        timeout: float,
        policy: DomainPolicy,
        kwargs: dict[str, Any],
        *,
        use_proxy: bool,
    ):
        request_kwargs = dict(kwargs)
        request_kwargs.update({"headers": headers, "timeout": timeout})
        if use_proxy:
            request_kwargs["proxies"] = policy.proxies or {}
        else:
            request_kwargs["proxies"] = {}
        return self.session.request(method, url, **request_kwargs)

    def _classify_exception(self, exc: BaseException) -> str:
        for name, types in self.timeout_exceptions.items():
            if isinstance(exc, types):
                return name
        return "network_error"

    def _sleep_backoff(self, policy: DomainPolicy, attempt: int) -> None:
        self.clock.sleep(self._backoff(policy, attempt))

    def _backoff(self, policy: DomainPolicy, attempt: int) -> float:
        delay = policy.backoff_base * (policy.backoff_factor ** max(0, attempt - 1))
        low, high = policy.backoff_jitter
        if low or high:
            delay += random.uniform(low, high)
        return min(policy.max_backoff, delay)

    def _retry_after_seconds(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            parsed = email.utils.parsedate_to_datetime(value)
            if parsed is None:
                return None
            return max(0.0, parsed.timestamp() - self.clock.time())
