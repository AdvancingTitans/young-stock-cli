"""Lens engine keeps the single-lens contract explicit and validated."""

from __future__ import annotations

from .contracts import LensResult, build_lens_result
from .registry import get_lens


def build_lens_prompt(lens_id: str) -> str:
    lens = get_lens(lens_id)
    return (
        f"采用 {lens.name}（{lens.school}）视角，只输出单个 FINAL_CONTRACT。"
        "FINAL_CONTRACT 必须包含 lens, attitude, conclusion, evidence, risk, action_watchlist。"
        f"lens 固定为 {lens.id}；attitude 只能是：偏看多 / 中性 / 偏看空 / 回避。"
        f"原则：{'、'.join(lens.principles)}。"
        f"优先证据：{'、'.join(lens.evidence_priorities)}。"
        "允许输出 Markdown 或 JSON，但字段必须完整。"
    )


def run_lens_engine(lens_id: str, content: str) -> LensResult:
    return build_lens_result(lens_id, content)
