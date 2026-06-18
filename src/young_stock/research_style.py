"""Convert internal market evidence into publication-safe research language."""

from __future__ import annotations

import copy
import re
from typing import Any

MODULE_TITLES = {
    "M1": "大盘指数与市场广度",
    "M2": "板块强弱与资金流",
    "M3": "赚钱效应与涨停结构",
    "M4": "下跌风险与炸板结构",
    "M5": "持仓与市场风格",
    "M6": "抗跌方向",
    "STOCK": "个股证据",
}

FIELD_TITLES = {
    "a_indices": "A股指数",
    "hk_indices": "港股指数",
    "us_indices": "美股指数",
    "northbound": "北向资金",
    "breadth": "市场广度",
    "industry": "行业板块",
    "concept": "概念板块",
    "fund_flow": "资金流",
    "zt_count": "涨停家数",
    "zt_pool": "涨停明细",
    "early_limit_up_count": "早盘涨停家数",
    "dt_count": "跌停家数",
    "zb_count": "炸板家数",
    "blowup_ratio": "炸板率",
    "dt_pool": "跌停明细",
    "zb_pool": "炸板明细",
    "holdings": "持仓",
    "style_signals": "风格观察",
    "growth_board_count": "科创板与创业板活跃样本数",
    "resilient": "抗跌方向",
    "quote": "行情",
    "block_trades": "大宗交易",
    "news": "公开信息",
    "trade_date": "交易日",
    "quality_score": "证据完整度评分",
    "missing_modules": "证据暂缺模块",
    "degrade_mode": "报告范围",
    "analysis_symbol": "分析标的",
    "report_type": "报告类型",
}

FORBIDDEN_PATTERNS = (
    r"\bmodules\.[A-Za-z0-9_.]+",
    r"\b(?:available|growth_board_count|degrade_mode|missing_modules)\b",
    r"\b(?:fallback)\b",
    r"脚本|采集|推测|不确定性|猜测",
    r"(?:[A-Za-z]:)?[/~][^\s，。；：)）`]+",
    r"\b[\w-]+\.(?:py|js|sh)\b",
    r"\bM[1-6]\s*(?:降级|缺失|不可用)",
)


class ResearchStyleError(RuntimeError):
    """Report still contains publication-unsafe internal language."""


def _public_source(value: Any) -> str:
    text = str(value or "")
    labels = []
    for token, label in (
        ("腾讯", "腾讯财经"),
        ("sina", "新浪财经"),
        ("新浪", "新浪财经"),
        ("eastmoney", "东方财富"),
        ("东财", "东方财富"),
        ("同花顺", "同花顺"),
        ("ths", "同花顺"),
        ("futu", "富途公开资讯"),
        ("富途", "富途公开资讯"),
    ):
        if token.lower() in text.lower() and label not in labels:
            labels.append(label)
    return "、".join(labels) if labels else "公开市场数据"


def _convert(value: Any) -> Any:
    if isinstance(value, list):
        return [_convert(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "available":
            result["证据状态"] = "据公开市场数据" if item else "本模块证据暂缺"
        elif key in {"source", "_source"}:
            result["数据来源"] = _public_source(item)
        elif key in {"_date_note", "_cache_note"}:
            result["日期说明"] = "历史口径回溯"
        elif key == "missing_modules":
            result["证据暂缺模块"] = [MODULE_TITLES.get(name, name) for name in item]
        elif key == "degrade_mode":
            result["报告范围"] = {
                "full": "完整报告",
                "degraded": "证据受限报告",
                "simplified": "简化报告",
            }.get(str(item), str(item))
        elif key.startswith("_"):
            continue
        else:
            result[FIELD_TITLES.get(key, key)] = _convert(item)
    return result


def to_research_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Return a publication-oriented copy without exposing internal field names."""
    source = copy.deepcopy(evidence)
    return {
        "研报证据": {
            MODULE_TITLES.get(name, name): _convert(payload)
            for name, payload in (source.get("modules") or {}).items()
        },
        "报告信息": _convert(source.get("_meta") or {}),
    }


def to_research_methodology(text: str) -> str:
    """Keep report structure and investment discipline, remove implementation guidance."""
    safe_lines = []
    in_code_block = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or _unsafe(line):
            continue
        if re.search(r"\b(?:API|HTTP|Session|Camofox|Playwright|JSON|evidence)\b", line, re.IGNORECASE):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _replacement_lines(evidence: dict[str, Any]) -> list[str]:
    modules = evidence.get("modules") or {}
    lines = []
    if not (modules.get("M2") or {}).get("available"):
        lines.append("- 本模块证据暂缺。")
    growth = ((modules.get("M5") or {}).get("style_signals") or {}).get("growth_board_count")
    if isinstance(growth, (int, float)):
        lines.append(f"- 据公开市场数据，科创板与创业板活跃样本数为 {growth:g} 家。")
    lines.append("- 据公开市场数据，相关指标以已披露口径为准。")
    return lines


def _unsafe(line: str) -> bool:
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in FORBIDDEN_PATTERNS)


def review_research_report(markdown: str, evidence: dict[str, Any]) -> str:
    """Remove unsafe sentences, add evidence-backed research wording, and validate."""
    internal_fields = re.findall(r"\bmodules\.([A-Za-z0-9_]+)\.([A-Za-z0-9_.]+)", markdown)
    known_modules = set((evidence.get("modules") or {}).keys())
    if any(module not in known_modules for module, _field in internal_fields):
        raise ResearchStyleError("正式研报包含无法转换的内部字段。")
    safe_lines = []
    removed = False
    for line in markdown.splitlines():
        if _unsafe(line):
            removed = True
            continue
        safe_lines.append(line)
    if removed:
        insert_at = 1 if safe_lines and safe_lines[0].startswith("#") else 0
        safe_lines[insert_at:insert_at] = ["", *_replacement_lines(evidence), ""]
    reviewed = "\n".join(safe_lines).strip()
    if _unsafe(reviewed):
        raise ResearchStyleError("正式研报未通过研究语言审校。")
    return reviewed
