"""Convert internal market evidence into publication-safe research language."""

from __future__ import annotations

import copy
import re
from typing import Any

PUBLIC_DISCLAIMER = "本文来自公开市场数据。仅供复盘参考，不构成投资建议。"

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

EDITORIAL_NOISE_PATTERNS = (
    r"^\s*(?:好的[，,、]?)?.*资深A股交易员.*$",
    r"young-stock-cli publication layout",
    r"young-stock-cli editorial layout",
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
            result["证据状态"] = "据公开市场数据" if item else "相关指标当日未披露"
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
        if re.search(r"\b(?:API|HTTP|Session|browser|Playwright|JSON|evidence)\b", line, re.IGNORECASE):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines).strip()


def _replacement_lines(evidence: dict[str, Any]) -> list[str]:
    modules = evidence.get("modules") or {}
    lines = []
    unavailable = any(payload.get("available") is False for payload in modules.values() if isinstance(payload, dict))
    missing_modules = bool((evidence.get("_meta") or {}).get("missing_modules"))
    if unavailable or missing_modules:
        lines.append("- 相关指标当日未披露。")
    growth = ((modules.get("M5") or {}).get("style_signals") or {}).get("growth_board_count")
    if isinstance(growth, (int, float)):
        lines.append(f"- 据公开市场数据，科创板与创业板活跃样本数为 {growth:g} 家。")
    lines.append("- 据公开市场数据，相关指标以已披露口径为准。")
    return lines


def _unsafe(line: str) -> bool:
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in FORBIDDEN_PATTERNS)


def _editorial_noise(line: str) -> bool:
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in EDITORIAL_NOISE_PATTERNS)


def _normalized_line(line: str) -> str:
    return line.replace("`", "")


def _placeholder_only(line: str) -> bool:
    return bool(re.fullmatch(r"\s*(?:[-*+]\s*)?本模块证据暂缺[。.]?\s*", line))


def _boilerplate(line: str) -> bool:
    stripped = line.strip()
    return bool(
        stripped == PUBLIC_DISCLAIMER
        or stripped == "说明: 以下内容仅供复盘参考，不构成投资建议。"
        or stripped == "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"
        or re.fullmatch(r"=+", stripped)
        or re.fullmatch(r"数据来源:\s*young-stock-cli\s+核心模块，多源免登录行情与新闻聚合。", stripped)
    )


def _strip_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _compose_public_report(title: str | None, body_lines: list[str], disclaimer: str) -> str:
    body = _strip_blank_edges(body_lines)
    if title:
        lines = [title, "", disclaimer]
        if body:
            lines.extend(["", *body])
        return "\n".join(lines).strip()
    if body:
        return "\n".join([disclaimer, "", *body]).strip()
    return disclaimer


_LIST_MARKER_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+•]|\d+[.)])(?P<gap>[ \t]+)(?P<body>.*)$")


def _normalize_report_spacing(line: str) -> str:
    line = re.sub(r"(?<=\d)[ \t\u3000]+%", "%", line)
    indent = re.match(r"^[ \t]*", line).group(0)
    body = line[len(indent):]
    body = re.sub(r"[ \t\u3000]{2,}", " ", body)
    return f"{indent}{body}".rstrip()


def _normalize_markdown_list_line(line: str) -> str:
    match = _LIST_MARKER_RE.match(line)
    if not match:
        return _normalize_report_spacing(line)
    raw_indent = match.group("indent").replace("\t", "  ")
    # ponytail: generated reports only need shallow Markdown lists; cap noisy 3-4 space
    # child indents to 2. Upgrade path: a real Markdown AST formatter.
    indent_len = len(raw_indent)
    if 0 < indent_len <= 4:
        indent_len = 2
    else:
        indent_len = (indent_len // 2) * 2
    body = re.sub(r"[ \t\u3000]{2,}", " ", match.group("body")).strip()
    body = re.sub(r"(?<=\d)[ \t\u3000]+%", "%", body)
    return f"{' ' * indent_len}{match.group('marker')} {body}".rstrip()


def normalize_report_markdown(markdown: str) -> str:
    """Normalize generated Markdown spacing without changing report content."""
    lines: list[str] = []
    in_code_block = False
    for raw_line in str(markdown or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            lines.append(raw_line.rstrip())
            continue
        if in_code_block or not stripped:
            lines.append(raw_line.rstrip())
            continue
        lines.append(_normalize_markdown_list_line(raw_line))
    return "\n".join(lines).strip()


def sanitize_public_report(markdown: str, evidence: dict[str, Any] | None = None, *, strict: bool = False) -> str:
    evidence = evidence or {}
    normalized_markdown = _normalized_line(markdown)
    if strict:
        internal_fields = re.findall(r"\bmodules\.([A-Za-z0-9_]+)\.([A-Za-z0-9_.]+)", normalized_markdown)
        known_modules = set((evidence.get("modules") or {}).keys())
        if any(module not in known_modules for module, _field in internal_fields):
            raise ResearchStyleError("正式研报包含无法转换的内部字段。")

    safe_body: list[str] = []
    title_line: str | None = None
    removed_unsafe = False
    in_code_block = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        normalized = _normalized_line(line)
        if in_code_block or _editorial_noise(normalized) or _boilerplate(normalized) or _placeholder_only(normalized):
            continue
        if _unsafe(normalized):
            removed_unsafe = True
            continue
        if title_line is None and stripped.startswith("#"):
            title_line = line.strip()
            continue
        safe_body.append(line)
    if removed_unsafe:
        replacement_lines = _replacement_lines(evidence)
        if replacement_lines:
            safe_body = [*replacement_lines, "", *safe_body] if safe_body else replacement_lines
    reviewed = _compose_public_report(title_line, safe_body, PUBLIC_DISCLAIMER)
    validation_lines = [_normalized_line(line) for line in reviewed.splitlines()]
    if any(_unsafe(line) or _editorial_noise(line) for line in validation_lines):
        raise ResearchStyleError("正式研报未通过研究语言审校。")
    return normalize_report_markdown(reviewed)


def review_research_report(markdown: str, evidence: dict[str, Any]) -> str:
    """Remove unsafe sentences, add evidence-backed research wording, and validate."""
    return sanitize_public_report(markdown, evidence, strict=True)
