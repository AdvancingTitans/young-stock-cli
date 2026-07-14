"""Local investment-memory profile for personalized daily reports."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .local_store import young_home

EMPTY_PROFILE = {
    "stocks": [],
    "funds": [],
    "groups": {},
    "classifications": {"stocks": {}},
    "positions": {"stocks": {}, "funds": {}},
}


class ProfileCorruptError(RuntimeError):
    """Raised when profile state cannot be decoded and no good backup exists."""


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
        data = _read_profile_json(path)
    except (OSError, json.JSONDecodeError):
        backup = _profile_backup_path(path)
        try:
            data = _read_profile_json(backup)
        except (OSError, json.JSONDecodeError) as backup_exc:
            raise ProfileCorruptError(
                f"投资记忆文件损坏且没有可用备份: {path}"
            ) from backup_exc
        _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return {
        "stocks": [str(v) for v in data.get("stocks", []) if str(v).strip()],
        "funds": [str(v) for v in data.get("funds", []) if str(v).strip()],
        "groups": _normalize_groups(data.get("groups", {})),
        "classifications": _normalize_classifications(data.get("classifications", {})),
        "positions": _normalize_positions(data.get("positions", {})),
    }


def save_profile(profile: dict[str, list[str]]) -> None:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            current = path.read_text(encoding="utf-8")
            json.loads(current)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileCorruptError(f"拒绝覆盖损坏的投资记忆文件: {path}") from exc
        _atomic_write_text(_profile_backup_path(path), current)
    _atomic_write_text(path, json.dumps(profile, ensure_ascii=False, indent=2) + "\n")


def _profile_backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bak")


def _read_profile_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise json.JSONDecodeError("profile root must be an object", str(data), 0)
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def add_profile_item(
    kind: str,
    value: str,
    buy_date: str | None = None,
    quantity: float | None = None,
    classification: dict[str, Any] | None = None,
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
    if normalized and kind == "stocks" and classification:
        profile.setdefault("classifications", {}).setdefault("stocks", {})[normalized] = dict(classification)
    save_profile(profile)
    return profile


def remove_profile_item(kind: str, value: str) -> dict[str, list[str]]:
    if kind not in {"stocks", "funds"}:
        raise ValueError(f"unknown profile item kind: {kind}")
    profile = load_profile()
    normalized = value.strip()
    profile[kind] = [item for item in profile.get(kind, []) if item != normalized]
    profile.setdefault("positions", {}).setdefault(kind, {}).pop(normalized, None)
    if kind == "stocks":
        profile.setdefault("classifications", {}).setdefault("stocks", {}).pop(normalized, None)
    for group in profile.get("groups", {}).values():
        if isinstance(group, dict):
            group[kind] = [item for item in group.get(kind, []) if item != normalized]
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
    if kind == "stocks":
        profile.setdefault("classifications", {})["stocks"] = {}
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


def _normalize_classifications(classifications) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {"stocks": {}}
    if not isinstance(classifications, dict):
        return result
    raw_stocks = classifications.get("stocks", {})
    if not isinstance(raw_stocks, dict):
        return result
    for code, raw in raw_stocks.items():
        if not isinstance(raw, dict):
            continue
        market = str(raw.get("market") or "").strip()
        asset_type = str(raw.get("asset_type") or "").strip()
        category = str(raw.get("category") or raw.get("style") or "").strip() or "待观察"
        evidence = [str(item).strip() for item in raw.get("evidence", []) if str(item).strip()]
        result["stocks"][str(code)] = {
            "market": market,
            "asset_type": asset_type,
            "category": category,
            "style": category,
            "evidence": evidence,
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
    return {
        "stocks": [],
        "funds": [],
        "groups": {},
        "classifications": {"stocks": {}},
        "positions": {"stocks": {}, "funds": {}},
    }
