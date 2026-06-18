"""Update and cache the stock-analysis reporting specification without executing remote code."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .local_store import young_home

STOCK_ANALYSIS_SKILL_URL = (
    "https://raw.githubusercontent.com/AdvancingTitans/stock-analysis/main/"
    "skills/stock-analysis/SKILL.md"
)
STOCK_ANALYSIS_RAW_BASE = STOCK_ANALYSIS_SKILL_URL.rsplit("/", 1)[0]
REFERENCE_PATHS = (
    "references/output_discipline.md",
    "references/data-source-strategy.md",
    "references/analysis-template.md",
    "references/methodology/m1-index-overview.md",
    "references/methodology/m2-sector-flow.md",
    "references/methodology/m3-upside.md",
    "references/methodology/m4-downside.md",
    "references/methodology/m5-style-buckets.md",
    "references/methodology/m6-resilient.md",
    "references/template/analysis-template.md",
    "references/template/module-template.md",
    "references/template/portfolio-template.md",
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


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:4]) or (0,)


def _cache_path() -> Path:
    return young_home() / "methodologies" / "stock-analysis" / "SKILL.md"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cached_spec(path: Path) -> tuple[str, str]:
    if not path.exists():
        return BUILTIN_VERSION, BUILTIN_GUIDANCE
    skill_text = path.read_text(encoding="utf-8")
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.exists():
        return _version(skill_text), skill_text
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checksums = manifest.get("sha256") or {}
        texts = {}
        for relative, expected in checksums.items():
            candidate = path.parent / relative
            content = candidate.read_text(encoding="utf-8")
            if _sha256(content) != expected:
                raise ValueError("checksum mismatch")
            texts[relative] = content
    except (OSError, ValueError, json.JSONDecodeError):
        return BUILTIN_VERSION, BUILTIN_GUIDANCE
    combined = [texts.get("SKILL.md", skill_text)]
    combined.extend(texts[relative] for relative in REFERENCE_PATHS if relative in texts)
    return str(manifest.get("version") or _version(skill_text)), "\n\n".join(combined)


def _download_text(client: Any, url: str, timeout: float) -> str:
    response = client.get(url, timeout=timeout)
    if response.status_code >= 400 or not str(response.text).strip():
        raise RuntimeError(f"HTTP {response.status_code}")
    return str(response.text).rstrip() + "\n"


def _install_spec(path: Path, version: str, files: dict[str, str]) -> None:
    parent = path.parent.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stock-analysis-", dir=parent) as temp_name:
        temp_root = Path(temp_name)
        for relative, content in files.items():
            target = temp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        manifest = {
            "version": version,
            "sha256": {relative: _sha256(content) for relative, content in files.items()},
        }
        (temp_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        destination = path.parent
        backup = destination.with_name(destination.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        os.replace(temp_root, destination)
        if backup.exists():
            shutil.rmtree(backup)


def sync_stock_analysis_methodology(*, session: Any = None, timeout: float = 5) -> MethodologySpec:
    path = _cache_path()
    current_version, current_text = _cached_spec(path)
    client = session or requests.Session()
    try:
        remote_skill = _download_text(client, STOCK_ANALYSIS_SKILL_URL, timeout)
    except Exception:
        return MethodologySpec(current_version, current_text, path, updated=False)
    remote_version = _version(remote_skill)
    if _version_tuple(remote_version) <= _version_tuple(current_version):
        return MethodologySpec(current_version, current_text, path, updated=False)
    files = {"SKILL.md": remote_skill}
    try:
        for relative in REFERENCE_PATHS:
            files[relative] = _download_text(
                client,
                f"{STOCK_ANALYSIS_RAW_BASE}/{relative}",
                timeout,
            )
        _install_spec(path, remote_version, files)
    except Exception:
        return MethodologySpec(current_version, current_text, path, updated=False)
    combined = [files["SKILL.md"], *(files[relative] for relative in REFERENCE_PATHS)]
    return MethodologySpec(remote_version, "\n\n".join(combined), path, updated=True)
