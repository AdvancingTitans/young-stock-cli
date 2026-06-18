"""Update and cache the stock-analysis reporting specification without executing remote code."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .local_store import young_home

STOCK_ANALYSIS_SKILL_URL = (
    "https://raw.githubusercontent.com/AdvancingTitans/stock-analysis/main/"
    "skills/stock-analysis/SKILL.md"
)
BUILTIN_VERSION = "4.2.0"
BUILTIN_GUIDANCE = """stock-analysis 4.2.0:
- 固定顺序：大盘指数概览、持仓分析、六模块深度复盘、综合持仓建议与风险提示。
- 行情优先腾讯与新浪；A股独有数据使用东财，失败后尝试浏览器页面。
- 正式研报只写市场数据、判断、风险和确认条件，不展示技术过程。
- 缺失字段留空或使用“本模块证据暂缺”，不得把空值写成零。
"""


@dataclass
class MethodologySpec:
    version: str
    text: str
    path: Path
    updated: bool = False


def _version(text: str) -> str:
    match = re.search(r'(?m)^\s*version:\s*["\']?([^"\'\s]+)', text)
    return match.group(1) if match else BUILTIN_VERSION


def _cache_path() -> Path:
    return young_home() / "methodologies" / "stock-analysis" / "SKILL.md"


def sync_stock_analysis_methodology(*, session: Any = None, timeout: float = 5) -> MethodologySpec:
    path = _cache_path()
    current_text = path.read_text(encoding="utf-8") if path.exists() else BUILTIN_GUIDANCE
    current_version = _version(current_text)
    client = session or requests.Session()
    try:
        response = client.get(STOCK_ANALYSIS_SKILL_URL, timeout=timeout)
        if response.status_code >= 400 or not str(response.text).strip():
            raise RuntimeError(f"HTTP {response.status_code}")
        remote_text = str(response.text)
    except Exception:
        return MethodologySpec(current_version, current_text, path, updated=False)
    remote_version = _version(remote_text)
    updated = remote_text != current_text
    if updated:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(remote_text.rstrip() + "\n", encoding="utf-8")
    return MethodologySpec(remote_version, remote_text, path, updated=updated)
