"""Local investment-memory profile for personalized daily reports."""

from __future__ import annotations

import json
import os
from pathlib import Path

EMPTY_PROFILE = {"stocks": [], "funds": []}


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
    }


def save_profile(profile: dict[str, list[str]]) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_profile_item(kind: str, value: str) -> dict[str, list[str]]:
    if kind not in EMPTY_PROFILE:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    items = profile.setdefault(kind, [])
    normalized = value.strip()
    if normalized and normalized not in items:
        items.append(normalized)
    save_profile(profile)
    return profile
