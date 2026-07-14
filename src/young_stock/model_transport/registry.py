"""Model transport registry."""

from __future__ import annotations

from typing import Any

from ..llm import LLMNotConfigured
from .api import ApiTransport
from .base import ModelTransport
from .subscription_cli import SubscriptionCliTransport

_TRANSPORTS = {
    "api": ApiTransport,
    "subscription-cli": SubscriptionCliTransport,
}


def normalize_transport_id(value: object) -> str:
    text = str(value or "").strip().lower()
    return text or "api"


def transport_ids() -> tuple[str, ...]:
    return tuple(_TRANSPORTS)


def model_transport_for_config(config: dict[str, Any], *, session: Any = None) -> ModelTransport:
    normalized = normalize_transport_id((config or {}).get("transport"))
    transport_class = _TRANSPORTS.get(normalized)
    if transport_class is None:
        raise LLMNotConfigured(f"不支持的 model transport: {normalized}")
    if normalized == "api":
        return transport_class(config, session=session)
    if session is not None:
        raise LLMNotConfigured("subscription-cli transport 不支持 HTTP session 注入。")
    return transport_class(config)
