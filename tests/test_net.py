import threading

import pytest

from young_stock.net.client import CircuitOpenError, ManagedHttpClient
from young_stock.net.limiter import DomainRateLimiter
from young_stock.net.policy import DomainPolicy


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Response:
    def __init__(self, status_code=200, text="{}", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.content = text.encode()


class MockSession:
    def __init__(self, responses=None, delay=0.0):
        self.responses = list(responses or [Response()])
        self.calls = []
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def request(self, method, url, **kwargs):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                threading.Event().wait(self.delay)
            self.calls.append((method, url, kwargs))
            item = self.responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        finally:
            with self.lock:
                self.active -= 1


def test_domain_limiter_enforces_concurrency_limit():
    session = MockSession([Response(), Response()], delay=0.05)
    policy = DomainPolicy(domain_group="eastmoney", max_concurrency=1)
    client = ManagedHttpClient(session=session, policies={"push2.eastmoney.com": policy})

    threads = [
        threading.Thread(target=client.request, args=("GET", "https://push2.eastmoney.com/a")),
        threading.Thread(target=client.request, args=("GET", "https://push2.eastmoney.com/b")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert session.max_active == 1


def test_limiter_applies_min_interval_and_jitter():
    clock = FakeClock()
    limiter = DomainRateLimiter(clock=clock, jitter=lambda lo, hi: 0.25)

    with limiter.acquire("eastmoney", max_concurrency=1, min_interval=1.0, jitter_range=(0.2, 0.4)):
        pass
    with limiter.acquire("eastmoney", max_concurrency=1, min_interval=1.0, jitter_range=(0.2, 0.4)):
        pass

    assert clock.sleeps == [1.25]


def test_429_retry_after_takes_precedence_over_backoff():
    clock = FakeClock()
    session = MockSession([Response(429, headers={"Retry-After": "7"}), Response(200, "ok")])
    client = ManagedHttpClient(session=session, clock=clock, max_attempts=2)

    response = client.request("GET", "https://example.com/data")

    assert response.text == "ok"
    assert clock.sleeps == [7.0]


def test_403_opens_circuit():
    clock = FakeClock()
    session = MockSession([Response(403, "forbidden")])
    client = ManagedHttpClient(session=session, clock=clock, max_attempts=1)

    response = client.request("GET", "https://example.com/data")
    assert response.status_code == 403
    with pytest.raises(CircuitOpenError):
        client.request("GET", "https://example.com/data")


def test_5xx_uses_exponential_backoff_with_jitter():
    clock = FakeClock()
    session = MockSession([Response(500), Response(502), Response(200, "ok")])
    policy = DomainPolicy(backoff_base=2.0, backoff_jitter=(0.5, 0.5))
    client = ManagedHttpClient(
        session=session,
        policies={"example.com": policy},
        clock=clock,
        max_attempts=3,
    )

    client.request("GET", "https://example.com/data")

    assert clock.sleeps == [2.5, 4.5]


def test_primary_domain_falls_back_to_configured_backup():
    session = MockSession([Response(500), Response(200, "ok")])
    policy = DomainPolicy(fallback_domains=("backup.example.com",))
    client = ManagedHttpClient(session=session, policies={"api.example.com": policy}, max_attempts=2)

    response = client.request("GET", "https://api.example.com/path?q=1")

    assert response.text == "ok"
    assert session.calls[0][1] == "https://api.example.com/path?q=1"
    assert session.calls[1][1] == "https://backup.example.com/path?q=1"
    assert client.traces[-1].fallback_domain == "backup.example.com"


def test_proxy_modes_and_timeout_classification():
    class ReadTimeout(Exception):
        pass

    session = MockSession([ReadTimeout("slow")])
    policy = DomainPolicy(proxy_mode="proxy", proxies={"https": "http://proxy"})
    client = ManagedHttpClient(
        session=session,
        policies={"example.com": policy},
        timeout_exceptions={"read_timeout": (ReadTimeout,)},
        max_attempts=1,
    )

    with pytest.raises(ReadTimeout):
        client.request("GET", "https://example.com/data?token=secret")

    assert session.calls[0][2]["proxies"] == {"https": "http://proxy"}
    assert client.traces[-1].error_type == "read_timeout"
    assert "secret" not in client.traces[-1].safe_url


def test_auto_proxy_tries_direct_before_proxy():
    class NetworkError(Exception):
        pass

    session = MockSession([NetworkError("direct failed"), Response(200, "ok")])
    policy = DomainPolicy(proxy_mode="auto", proxies={"https": "http://proxy"})
    client = ManagedHttpClient(
        session=session,
        policies={"example.com": policy},
        max_attempts=2,
    )

    response = client.request("GET", "https://example.com/data")

    assert response.text == "ok"
    assert session.calls[0][2]["proxies"] == {}
    assert session.calls[1][2]["proxies"] == {"https": "http://proxy"}


def test_eastmoney_subdomains_share_default_domain_group():
    client = ManagedHttpClient()

    assert client.policy_for("push2.eastmoney.com").group_for("push2.eastmoney.com") == "eastmoney"
    assert client.policy_for("push2his.eastmoney.com").group_for("push2his.eastmoney.com") == "eastmoney"
