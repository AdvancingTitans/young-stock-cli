"""Small JSON stores for local portfolio, alerts, notes, and saved diaries."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def young_home() -> Path:
    override = os.environ.get("YOUNG_STOCK_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".young_stock"


def load_store(name: str, default: Any) -> Any:
    path = young_home() / f"{name}.json"
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_store(name: str, data: Any) -> None:
    path = young_home() / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
