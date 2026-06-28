"""Prompt-level debate orchestration kept intentionally lightweight."""

from __future__ import annotations

from young_stock.lens.registry import LENSES, get_lens
from young_stock.methods.registry import select_method_cards

from .contracts import DebateConfig, DebateRound


def _methods_text(lens_id: str) -> str:
    school = None if lens_id in {"all", "balanced"} else get_lens(lens_id).school
    return "、".join(card.name for card in select_method_cards(school, lens_id=None if lens_id in {"all", "balanced"} else lens_id))


class DebateEngine:
    def __init__(self, lens_id: str, *, rounds: int = 3, daily: bool = False):
        self.lens_id = lens_id
        self.config = DebateConfig(rounds)
        self.daily = daily

    def rounds(self) -> tuple[DebateRound, ...]:
        goals = [
            "立场陈述，先各自提交 attitude/evidence/risk",
            "交叉质询，挑出最硬证据与最弱假设",
            "收敛分歧，形成最终委员会结论",
        ]
        extra_goal = "继续压缩未解决分歧并更新最终结论"
        items = []
        for index in range(1, self.config.rounds + 1):
            goal = goals[index - 1] if index <= len(goals) else extra_goal
            items.append(DebateRound(index, goal))
        return tuple(items)

    def prompt(self) -> str:
        rounds_text = " ".join(
            f"ROUND {item.round_number}: {item.goal}；字段={','.join(item.required_fields)}。"
            for item in self.rounds()
        )
        final_scope = "## M7 机构化综合判断" if self.daily else "最终投资结论"
        return (
            f"{build_institutional_prompt(self.lens_id, rounds=self.config.rounds, daily=self.daily)}\n"
            f"内部状态机：{rounds_text}"
            f" FINAL_CONTRACT 必须落到 {final_scope}，并包含 attitude、conclusion、evidence、risk、action_watchlist。"
            " 整个委员会流程只调用一次模型，不得拆成多次外部调用。"
        )


def build_institutional_prompt(
    lens_id: str,
    *,
    rounds: int = 3,
    daily: bool = False,
) -> str:
    config = DebateConfig(rounds)
    scope = "今日大盘、市场风格与用户整体持仓" if daily else "单只股票及用户相关持仓"
    if lens_id not in {"all", "balanced"}:
        lens = get_lens(lens_id)
        output_scope = (
            "不新增 M7；在既有结构后只输出该专家视角的持仓建议与风险提示。"
            if daily
            else "最终只输出该专家视角的总体态度、详细结论、证据、风险和针对持仓的行动建议。"
        )
        return (
            f"分析范围：{scope}。{output_scope}"
            "态度只能是：偏看多 / 中性 / 偏看空 / 回避；不得输出主观评分。"
            "所有数字必须来自给定证据；缺失时明确写证据暂缺。"
            "方法卡只提供结构且不得压过所选专家原则："
            f"{_methods_text(lens_id)}。\n"
            f"采用 {lens.name}（{lens.school}）视角。"
            f"原则：{'、'.join(lens.principles)}。"
            f"优先证据：{'、'.join(lens.evidence_priorities)}。"
            "不要触发辩论，不要模仿身份声明；保留明确态度和 3-5 段分析结论。"
        )
    m7 = (
        "在既有 M1-M6 后新增且只新增 `## M7 机构化综合判断`，包含："
        "专家观点或委员会结论、轻量 comps/比率趋势、催化剂与业绩跟踪、"
        "IC memo/DD/rebalance 风格行动建议。"
        if daily
        else "最终只输出总体态度、详细结论、证据、风险和针对持仓的行动建议。"
    )
    common = (
        f"分析范围：{scope}。{m7}"
        "态度只能是：偏看多 / 中性 / 偏看空 / 回避；不得输出主观评分。"
        "所有数字必须来自给定证据；缺失时明确写证据暂缺。"
        "方法卡只提供结构且不得压过所选专家原则："
        f"{_methods_text(lens_id)}。"
    )
    if lens_id == "balanced":
        return (
            f"{common}\n采用 balanced 综合视角，不模拟任何专家人格，也不触发辩论。"
            "平衡基本面、估值、宏观、量价、组合暴露与反方证据。"
        )

    roster = "；".join(
        f"{lens.name}/{lens.school}：{'、'.join(lens.principles[:2])}"
        for lens in LENSES.values()
    )
    return (
        f"{common}\n委员会成员：{roster}。"
        "先让每位专家独立形成 attitude + evidence + risk，再按 bull/neutral/bear/avoid 分组。"
        f"在内部完成 {config.rounds} 轮："
        "第 1 轮立场陈述；第 2 轮价值/成长/宏观/交易/量化交叉质询；"
        "第 3 轮及后续轮收敛最硬证据、致命风险和未解决分歧。"
        "每轮内部发言限制为 1-2 段且必须引用证据；不要向用户展示辩论过程。"
        "最终格式必须包含：总体态度及各态度人数、辩论后结论、核心理由、"
        "主要反方观点、风险、针对持仓的最终行动建议。最终同时整理成 FINAL_CONTRACT。"
    )
