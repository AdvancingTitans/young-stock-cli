"""Common model transport protocol."""

from __future__ import annotations

from typing import Any, Protocol


class ModelTransport(Protocol):
    transport_id: str

    def chat(self, messages: list[dict[str, str]]) -> Any:
        """Return a response object with content/provider/model metadata."""

    def list_models(self, *, verify_chat: bool = False) -> list[str]:
        """Return model IDs when the transport supports model discovery."""
