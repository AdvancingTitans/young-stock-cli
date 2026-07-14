from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field

_SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
}
_SECRET_HEADERS = {"authorization", "cookie", "proxy-authorization", "x-api-key"}


def scrub_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_pairs = [(key, "***" if key.lower() in _SECRET_QUERY_KEYS else value) for key, value in pairs]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(safe_pairs), parsed.fragment)
    )


def scrub_headers(headers: dict[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (headers or {}).items():
        out[key] = "***" if key.lower() in _SECRET_HEADERS else value
    return out


@dataclass
class RequestTrace:
    method: str
    safe_url: str
    domain: str
    domain_group: str
    attempts: int = 0
    status_code: int | None = None
    error_type: str = ""
    proxy_mode: str = "direct"
    fallback_domain: str = ""
    elapsed_ms: float = 0.0
    request_headers: dict[str, str] = field(default_factory=dict)
