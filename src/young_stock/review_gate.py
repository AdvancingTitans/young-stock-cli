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


def review_investment_output(markdown: str, evidence: dict[str, Any]) -> dict[str, bool]:
    text = str(markdown or "")
    evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
    allowed_numeric_signatures = _allowed_numeric_signatures(evidence_text)
    grounded_date_spans = [
        match.span()
        for match in HYPHENATED_DATE_RE.finditer(text)
        if (f"{match.group(1)}{int(match.group(2)):02d}{int(match.group(3)):02d}", False)
        in allowed_numeric_signatures
    ]
    numeric_claims = [
        match.group()
        for match in CLAIM_NUMBER_RE.finditer(text)
        if not (
            match.group() in {"1", "2", "3", "4", "5", "6", "7"}
            and text[match.end() :].startswith((". ", "、"))
            and (match.start() == 0 or text[match.start() - 1] in "\n:：")
        )
        and not any(start <= match.start() and match.end() <= end for start, end in grounded_date_spans)
    ]
    structured_candidate = any(token in text for token in ("行动建议", "观察清单", "详细结论", "核心理由", "风险"))
    return {
        "attitude_present": any(attitude in text for attitude in ATTITUDES),
        "conclusion_present": any(token in text for token in ("详细结论", "辩论后结论", "总体结论", "核心理由", "conclusion")),
        "evidence_present": any(token in text for token in ("证据", "核心理由", "据公开")),
        "risk_present": "风险" in text,
        "action_present": any(token in text for token in ("行动建议", "持有", "观察", "回避", "降低暴露")),
        "watchlist_present": any(token in text for token in ("观察清单", "action_watchlist")) or "持有观察" in text,
        "no_subjective_score": not re.search(r"(?:评分|score)\s*[:：]?\s*\d+", text, re.IGNORECASE),
        "no_internal_jargon": not any(token in text for token in ("modules.", "fallback", "source_trace")),
        "numbers_grounded": all(
            (_normalize_number_token(token), token.endswith("%")) in allowed_numeric_signatures for token in numeric_claims
        ),
        "structured_candidate": structured_candidate,
    }
