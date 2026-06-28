"""Mechanical checks for LLM investment output; no subjective scoring."""

from __future__ import annotations

import json
import re
from typing import Any

from .debate import ATTITUDES

CLAIM_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[+-]?\d+(?:\.\d+)?%?(?![A-Za-z0-9])")
EVIDENCE_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?%?")
DATE_TOKEN_RE = re.compile(r"^\d{8}$")
HYPHENATED_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
SLASHED_DATE_RE = re.compile(r"(?<!\d)(\d{4})/(\d{1,2})/(\d{1,2})(?!\d)")
LOCALIZED_DATE_RE = re.compile(r"(?<!\d)(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日(?!\d)")
MARKET_INDEX_NAME_RE = re.compile(
    r"(?:沪深|中证|上证|深证|科创|创业板|北证|国证|恒生|标普|纳斯达克|道琼斯|罗素)\s*\d+(?:\.\d+)?"
)
ATTITUDE_CONTEXT_RE = re.compile(
    r"(?:总体态度|投资评级|操作建议|综合判断|核心结论|倾向|结论|建议)\s*[:：为]?\s*"
    r"(?:持有观察|等待确认|不追高|谨慎|中性|震荡观察|偏强|偏弱|看多|看空|回避|增持|减持|观望)"
)
FINAL_ATTITUDES = ("看涨", "偏看涨", "中性", "偏看空", "看空", "回避", "证据不足", "偏看多")
FORBIDDEN_TERMS = (
    "立即买入", "立即卖出", "满仓", "梭哈", "稳赚", "必涨", "保证收益", "已下单", "自动执行", "连接券商", "实盘自动",
)
FUND_FORBIDDEN_TERMS = ("立即申购", "立即赎回", "自动扣款", "已申购", "已赎回", "保本保收益")
CONDITIONAL_TERMS = ("如果", "若", "当", "除非", "触发", "确认", "失效", "维持观察", "暂不", "证据不足", "不行动", "观察", "等待")


def _normalize_number_token(token: str) -> str:
    value = str(token or "").strip()
    sign = ""
    if value[:1] in {"+", "-"}:
        sign, value = value[:1], value[1:]
    if value.endswith("%"):
        value = value[:-1]
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    if value.startswith("0") and value not in {"0", ""} and not value.startswith("0."):
        value = value.lstrip("0") or "0"
    return f"{sign}{value}" if sign else value


def _allowed_numeric_signatures(evidence_text: str) -> set[tuple[str, bool]]:
    allowed: set[tuple[str, bool]] = set()
    for token in EVIDENCE_NUMBER_RE.findall(evidence_text):
        normalized = _normalize_number_token(token)
        allowed.add((normalized, token.endswith("%")))
        if token.endswith("%"):
            allowed.add((normalized, False))
        if DATE_TOKEN_RE.fullmatch(normalized):
            # ponytail: keep 8-digit dates atomic; do not derive year/month/day shortcuts.
            continue
    return allowed


def _date_spans_grounded_by_evidence(text: str, allowed_numeric_signatures: set[tuple[str, bool]]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (HYPHENATED_DATE_RE, SLASHED_DATE_RE, LOCALIZED_DATE_RE):
        for match in pattern.finditer(text):
            atomic_date = f"{match.group(1)}{int(match.group(2)):02d}{int(match.group(3)):02d}"
            if (atomic_date, False) in allowed_numeric_signatures:
                spans.append(match.span())
    return spans


def _market_index_name_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in MARKET_INDEX_NAME_RE.finditer(text)]


def _inside_any_span(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(span_start <= start and end <= span_end for span_start, span_end in spans)


def _has_attitude(text: str) -> bool:
    return any(attitude in text for attitude in (*ATTITUDES, *FINAL_ATTITUDES)) or bool(ATTITUDE_CONTEXT_RE.search(text))


def _is_fund_evidence(evidence: dict[str, Any]) -> bool:
    evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
    return '"asset_kind": "fund"' in evidence_text or '"report_type": "single-fund"' in evidence_text or '"FUND"' in evidence_text


def _has_single_lens_final_title(text: str) -> bool:
    return bool(re.search(r"(?m)^##\s+(?!综合)[^\n#]{1,24}持仓建议与风险提示\s*$", text))


def _requires_final_advice_sections(text: str, evidence: dict[str, Any]) -> bool:
    meta = evidence.get("_meta") if isinstance(evidence, dict) else {}
    if _has_single_lens_final_title(text):
        return False
    return (
        "交易计划草案" in text
        or "风险管理意见" in text
        or "组合经理最终意见" in text
        or (isinstance(meta, dict) and bool(meta.get("report_type")))
    )


def review_investment_output(markdown: str, evidence: dict[str, Any]) -> dict[str, bool]:
    text = str(markdown or "")
    evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
    allowed_numeric_signatures = _allowed_numeric_signatures(evidence_text)
    grounded_date_spans = _date_spans_grounded_by_evidence(text, allowed_numeric_signatures)
    market_index_spans = _market_index_name_spans(text)
    numeric_claims = [
        match.group()
        for match in CLAIM_NUMBER_RE.finditer(text)
        if not (
            match.group() in {"1", "2", "3", "4", "5", "6", "7"}
            and text[match.end() :].startswith((". ", "、"))
            and (match.start() == 0 or text[match.start() - 1] in "\n:：")
        )
        and not _inside_any_span(match.start(), match.end(), grounded_date_spans)
        and not _inside_any_span(match.start(), match.end(), market_index_spans)
    ]
    structured_candidate = any(token in text for token in ("行动建议", "综合持仓建议", "观察清单", "详细结论", "核心理由", "风险"))
    requires_final = _requires_final_advice_sections(text, evidence)
    single_lens_final = _has_single_lens_final_title(text)
    final_advice_present = "综合持仓建议与风险提示" in text or "持仓建议与风险提示" in text
    no_forbidden = not any(token in text for token in (FORBIDDEN_TERMS + (FUND_FORBIDDEN_TERMS if _is_fund_evidence(evidence) else ())))
    return {
        "attitude_present": _has_attitude(text),
        "conclusion_present": any(token in text for token in ("详细结论", "辩论后结论", "总体结论", "综合判断", "核心理由", "conclusion")),
        "evidence_present": any(token in text for token in ("证据", "核心理由", "据公开", "数据显示", "披露")),
        "risk_present": "风险" in text,
        "action_present": any(token in text for token in ("行动建议", "综合持仓建议", "持有", "观察", "回避", "等待确认", "不追高", "降低暴露")),
        "watchlist_present": any(token in text for token in ("观察清单", "下一交易日", "跟踪", "确认条件", "action_watchlist")) or "持有观察" in text,
        "no_subjective_score": not re.search(r"(?:评分|score)\s*[:：]?\s*\d+", text, re.IGNORECASE),
        "no_internal_jargon": not any(token in text for token in ("modules.", "fallback", "source_trace")),
        "final_advice_present": (not requires_final) or final_advice_present,
        "final_attitude_section": (not requires_final) or "最终态度" in text,
        "trading_plan_section": (not requires_final) or "交易计划草案" in text,
        "risk_management_section": (not requires_final) or "风险管理意见" in text,
        "portfolio_opinion_section": (not requires_final) or "组合经理最终意见" in text,
        "next_watchlist_section": (not requires_final) or "下一交易日观察清单" in text,
        "single_lens_no_committee_sections": (not single_lens_final)
        or not any(token in text for token in ("交易计划草案", "风险管理意见", "组合经理最终意见")),
        "no_forbidden_trading_language": no_forbidden,
        "conditional_language": no_forbidden and any(token in text for token in CONDITIONAL_TERMS),
        "numbers_grounded": all(
            (_normalize_number_token(token), token.endswith("%")) in allowed_numeric_signatures for token in numeric_claims
        ),
        "structured_candidate": structured_candidate,
    }
