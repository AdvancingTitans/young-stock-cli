"""Local investment-memory profile for personalized daily reports."""

from __future__ import annotations

import json
import os
from pathlib import Path

EMPTY_PROFILE = {"stocks": [], "funds": [], "groups": {}}


def profile_path() -> Path:
    override = os.environ.get("YOUNG_STOCK_PROFILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".young_stock" / "profile.json"


def load_profile() -> dict[str, list[str]]:
    path = profile_path()
    if not path.exists():
        return {k: list(v) for k, v in EMPTY_PROFILE.items()}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {k: list(v) for k, v in EMPTY_PROFILE.items()}
    return {
        "stocks": [str(v) for v in data.get("stocks", []) if str(v).strip()],
        "funds": [str(v) for v in data.get("funds", []) if str(v).strip()],
        "groups": _normalize_groups(data.get("groups", {})),
    }


def save_profile(profile: dict[str, list[str]]) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_profile_item(kind: str, value: str) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    items = profile.setdefault(kind, [])
    normalized = value.strip()
    if normalized and normalized not in items:
        items.append(normalized)
    save_profile(profile)
    return profile


def remove_profile_item(kind: str, value: str) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    normalized = value.strip()
    profile[kind] = [item for item in profile.get(kind, []) if item != normalized]
    save_profile(profile)
    return profile


def clear_profile() -> dict[str, list[str]]:
    profile = {k: ({} if k == "groups" else []) for k in EMPTY_PROFILE}
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
