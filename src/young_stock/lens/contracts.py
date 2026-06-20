"""Structured single-lens result contract."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from young_stock.debate.contracts import ATTITUDES


@dataclass(frozen=True)
class LensResult:
    lens: str
    attitude: str
    conclusion: str
    evidence: tuple[str, ...]
    risk: tuple[str, ...]
    action_watchlist: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.lens.strip():
            raise ValueError("lens is required")
        if self.attitude not in ATTITUDES:
            raise ValueError("attitude must use supported labels")
        if not self.conclusion.strip():
            raise ValueError("conclusion is required")
        for field_name in ("evidence", "risk", "action_watchlist"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be tuple[str, ...]")
            if any(not str(item).strip() for item in values):
                raise ValueError(f"{field_name} cannot contain blanks")


def _normalize_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        lines = [line.strip("-* \t") for line in value.splitlines()]
        return tuple(line for line in lines if line)
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, tuple):
        return tuple(str(item).strip() for item in value if str(item).strip())
    raise ValueError("list field must be string or list")


def _parse_json(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    return json.loads(stripped)


def _parse_markdown(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        bullet = re.match(r"^-\s*([a-z_]+)\s*:\s*(.*)$", line, re.IGNORECASE)
        if bullet:
            key = bullet.group(1).lower()
            value = bullet.group(2).strip()
            current_key = key
            if key in {"evidence", "risk", "action_watchlist"}:
                fields[key] = _normalize_list(value) if value else ()
            else:
                fields[key] = value
            continue
        item = re.match(r"^-\s*(.+)$", line)
        if item and current_key in {"evidence", "risk", "action_watchlist"}:
            fields[current_key] = (*fields.get(current_key, ()), item.group(1).strip())
    return fields


def parse_lens_result(text: str) -> LensResult:
    payload = _parse_json(text) or _parse_markdown(text)
    try:
        return LensResult(
            lens=str(payload["lens"]).strip().lower(),
            attitude=str(payload["attitude"]).strip(),
            conclusion=str(payload["conclusion"]).strip(),
            evidence=_normalize_list(payload.get("evidence")),
            risk=_normalize_list(payload.get("risk")),
            action_watchlist=_normalize_list(payload.get("action_watchlist")),
        )
    except KeyError as exc:
        raise ValueError(f"missing field: {exc.args[0]}") from exc


def build_lens_result(expected_lens: str, text: str) -> LensResult:
    result = parse_lens_result(text)
    if result.lens != expected_lens.strip().lower():
        raise ValueError("lens result does not match requested lens")
    return result
