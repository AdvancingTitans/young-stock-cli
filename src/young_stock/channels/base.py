"""Channel adapter primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeliveryResult:
    channel: str
    target: str
    ok: bool
    detail: str
