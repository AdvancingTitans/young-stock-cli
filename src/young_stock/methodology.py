"""young-stock-cli built-in report methodology."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .local_store import young_home

BUILTIN_VERSION = "young-1.0"
BUILTIN_GUIDANCE = """young-stock-cli 内置研究框架
version: young-1.0

- 固定顺序：大盘指数概览、持仓分析、六模块深度复盘、M7 机构化综合判断、综合持仓建议与风险提示。
- M1-M6 只围绕公开市场数据、确认条件、风险触发器和下一步观察点展开。
- 缺失字段留空或使用“相关指标当日未披露”“本模块证据暂缺”等自然表述，不把空值写成零。
- 正式输出不暴露内部字段名、实现细节、本地路径、脚本名或技术切换过程。
- 允许在已配置时追加可选联网研究摘录，但只能作为辅助公开资料，不替代已验证市场证据。
"""


@dataclass
class MethodologySpec:
    version: str
    text: str
    path: Path
    updated: bool = False


def _cache_path() -> Path:
    return young_home() / "methodologies" / "young-stock-cli" / "SKILL.md"


def _legacy_roots() -> tuple[Path, ...]:
    legacy_name = "stock" + "-analysis"
    return (
        young_home() / "methodologies" / legacy_name,
    )


def _cleanup_legacy_roots() -> None:
    for legacy in _legacy_roots():
        if legacy.exists():
            shutil.rmtree(legacy, ignore_errors=True)


def _write_builtin(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current != BUILTIN_GUIDANCE:
        path.write_text(BUILTIN_GUIDANCE, encoding="utf-8")


def load_builtin_methodology(*, session: Any = None, timeout: float = 5) -> MethodologySpec:
    del session, timeout
    path = _cache_path()
    _cleanup_legacy_roots()
    _write_builtin(path)
    return MethodologySpec(BUILTIN_VERSION, BUILTIN_GUIDANCE, path, updated=False)
