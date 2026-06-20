"""Mechanical checks for LLM investment output; no subjective scoring."""

from __future__ import annotations

import json
import re
from typing import Any

from .debate import ATTITUDES


def review_investment_output(markdown: str, evidence: dict[str, Any]) -> dict[str, bool]:
    text = str(markdown or "")
    evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
    numeric_claims = set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", text))
    evidence_numbers = set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", evidence_text))
    structural_numbers = {"1", "2", "3", "4", "5", "6", "7", "10", "20", "30"}
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
        "numbers_grounded": numeric_claims <= evidence_numbers | structural_numbers,
        "structured_candidate": structured_candidate,
    }
