"""Local investment-memory profile for personalized daily reports."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .local_store import young_home

EMPTY_PROFILE = {"stocks": [], "funds": [], "groups": {}, "positions": {"stocks": {}, "funds": {}}}


def profile_path() -> Path:
    override = os.environ.get("YOUNG_STOCK_PROFILE")
    if override:
        return Path(override).expanduser()
    return young_home() / "profile.json"


def load_profile() -> dict[str, list[str]]:
    path = profile_path()
    if not path.exists():
        return _empty_profile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_profile()
    return {
        "stocks": [str(v) for v in data.get("stocks", []) if str(v).strip()],
        "funds": [str(v) for v in data.get("funds", []) if str(v).strip()],
        "groups": _normalize_groups(data.get("groups", {})),
        "positions": _normalize_positions(data.get("positions", {})),
    }


def save_profile(profile: dict[str, list[str]]) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_profile_item(
    kind: str,
    value: str,
    buy_date: str | None = None,
    quantity: float | None = None,
) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    items = profile.setdefault(kind, [])
    normalized = value.strip()
    if normalized and normalized not in items:
        items.append(normalized)
    if normalized and (buy_date or quantity is not None):
        position = profile.setdefault("positions", {}).setdefault(kind, {}).setdefault(normalized, {})
        if buy_date:
            position["buy_date"] = buy_date.strip()
        if quantity is not None:
            position["quantity"] = quantity
    save_profile(profile)
    return profile


def remove_profile_item(kind: str, value: str) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    normalized = value.strip()
    profile[kind] = [item for item in profile.get(kind, []) if item != normalized]
    profile.setdefault("positions", {}).setdefault(kind, {}).pop(normalized, None)
    save_profile(profile)
    return profile


def clear_profile() -> dict[str, list[str]]:
    profile = _empty_profile()
    save_profile(profile)
    return profile


def clear_profile_kind(kind: str) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    profile[kind] = []
    profile.setdefault("positions", {})[kind] = {}
    for group in profile.get("groups", {}).values():
        if isinstance(group, dict):
            group[kind] = []
    save_profile(profile)
    return profile


def add_group(name: str) -> dict[str, list[str]]:
    profile = load_profile()
    group_name = name.strip()
    if group_name:
        profile.setdefault("groups", {}).setdefault(group_name, {"stocks": [], "funds": []})
    save_profile(profile)
    return profile


def add_group_item(name: str, value: str) -> dict[str, list[str]]:
    profile = add_group(name)
    group_name = name.strip()
    normalized = value.strip()
    kind = "stocks" if normalized.isdigit() and len(normalized) == 6 and normalized.startswith(("3", "6", "8")) else "funds"
    items = profile["groups"][group_name].setdefault(kind, [])
    if normalized and normalized not in items:
        items.append(normalized)
    save_profile(profile)
    return profile


def _normalize_groups(groups) -> dict[str, dict[str, list[str]]]:
    if not isinstance(groups, dict):
        return {}
    result = {}
    for name, data in groups.items():
        if isinstance(data, dict):
            result[str(name)] = {
                "stocks": [str(v) for v in data.get("stocks", []) if str(v).strip()],
                "funds": [str(v) for v in data.get("funds", []) if str(v).strip()],
            }
    return result


def _normalize_positions(positions) -> dict[str, dict[str, dict[str, float | str]]]:
    result: dict[str, dict[str, dict[str, float | str]]] = {"stocks": {}, "funds": {}}
    if not isinstance(positions, dict):
        return result
    for kind in ("stocks", "funds"):
        raw_items = positions.get(kind, {})
        if not isinstance(raw_items, dict):
            continue
        for code, raw_position in raw_items.items():
            if not isinstance(raw_position, dict):
                continue
            position: dict[str, float | str] = {}
            buy_date = str(raw_position.get("buy_date") or "").strip()
            if buy_date:
                position["buy_date"] = buy_date
            try:
                position["quantity"] = float(raw_position["quantity"])
            except (KeyError, TypeError, ValueError):
                pass
            if position:
                result[kind][str(code)] = position
    return result


def _empty_profile() -> dict[str, list[str]]:
    return {"stocks": [], "funds": [], "groups": {}, "positions": {"stocks": {}, "funds": {}}}
