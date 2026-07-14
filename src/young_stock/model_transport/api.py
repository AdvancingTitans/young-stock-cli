"""API-backed model transport."""

from __future__ import annotations

from typing import Any

from ..llm import LLMClient


class ApiTransport:
    transport_id = "api"

    def __init__(self, config: dict[str, Any], *, session: Any = None):
        self.config = {**dict(config or {}), "transport": "api"}
        self._client = LLMClient(self.config, session=session)

    def chat(self, messages: list[dict[str, str]]) -> Any:
        response = self._client.chat(messages)
        response.transport = self.transport_id
        return response

    def list_models(self, *, verify_chat: bool = False) -> list[str]:
        return self._client.list_models(verify_chat=verify_chat)
