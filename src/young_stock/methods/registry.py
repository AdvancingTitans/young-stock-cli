"""Lightweight institutional method cards; structure only, never scores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MethodCard:
    id: str
    category: str
    name: str
    purpose: str
    compatible_schools: tuple[str, ...] = ()


METHOD_CARDS = {
    card.id: card
    for card in (
        MethodCard("dcf", "valuation", "DCF-lite", "用现金流情景检查长期价值与关键假设"),
        MethodCard("reverse_dcf", "valuation", "Reverse DCF", "反推当前价格隐含的增长与利润率预期"),
        MethodCard("comps", "valuation", "Comps", "用可比公司和历史区间校验估值舒适度"),
        MethodCard("lbo_lite", "valuation", "LBO-lite", "检查杠杆承受力与现金回收能力", ("价值",)),
        MethodCard("three_statement_lite", "valuation", "3-statement-lite", "联动利润表、资产负债表和现金流"),
        MethodCard("sotp_lite", "valuation", "SOTP-lite", "对多业务公司分部估值并识别折价来源"),
        MethodCard("earnings", "research", "财报解读", "追踪收入、利润、现金流和指引变化"),
        MethodCard("earnings_preview", "research", "业绩前瞻", "列出财报前关键预期与验证点"),
        MethodCard("catalyst", "research", "催化剂日历", "跟踪未来 3/10/30 个交易日事件"),
        MethodCard("thesis_tracker", "research", "投资逻辑追踪", "记录证据增强、削弱与待确认项"),
        MethodCard("industry", "research", "行业综述", "检查竞争格局、周期和行业 beta"),
        MethodCard("news_attribution", "research", "新闻情绪归因", "区分事实事件、情绪与价格反馈"),
        MethodCard("portfolio_risk", "research", "持仓风险复盘", "识别集中度、相关性和暴露"),
        MethodCard("ic_memo", "decision", "IC Memo", "压缩成态度、证据、反方与行动条件"),
        MethodCard("dd", "decision", "Due Diligence checklist", "检查治理、财务、业务与信息缺口"),
        MethodCard("porter", "decision", "Porter Five Forces", "检查行业结构与护城河"),
        MethodCard("unit_economics", "decision", "Unit Economics", "检查单客经济性与规模质量", ("成长",)),
        MethodCard("vcp", "decision", "VCP", "检查波动收缩与量价确认", ("技术/交易",)),
        MethodCard("rebalance", "decision", "Rebalancing Review", "把结论映射到持仓与组合暴露"),
    )
}

_LONG_TERM = {
    "dcf",
    "reverse_dcf",
    "comps",
    "three_statement_lite",
    "sotp_lite",
    "earnings",
    "catalyst",
    "thesis_tracker",
    "industry",
    "portfolio_risk",
    "ic_memo",
    "dd",
    "porter",
    "rebalance",
}
_TRADING = {
    "comps",
    "earnings_preview",
    "catalyst",
    "news_attribution",
    "portfolio_risk",
    "ic_memo",
    "vcp",
    "rebalance",
}

_PREFERRED_METHODS = {
    "buffett": ("dd", "porter", "dcf", "rebalance"),
    "dalio": ("portfolio_risk", "industry", "catalyst", "rebalance"),
    "minervini": ("vcp", "earnings_preview", "catalyst", "rebalance"),
}

_BLOCKED_METHODS = {
    "buffett": ("vcp",),
    "munger": ("vcp",),
    "graham": ("vcp",),
    "klarman": ("vcp",),
}


def select_method_cards(school: str | None = None, *, lens_id: str | None = None) -> tuple[MethodCard, ...]:
    if school == "技术/交易":
        selected = _TRADING
    elif school in {"价值", "中国视角"}:
        selected = _LONG_TERM
    else:
        selected = set(METHOD_CARDS)
    if lens_id:
        selected -= set(_BLOCKED_METHODS.get(lens_id, ()))
        preferred = _PREFERRED_METHODS.get(lens_id, ())
        ordered = [METHOD_CARDS[card_id] for card_id in preferred if card_id in selected]
        ordered.extend(card for card_id, card in METHOD_CARDS.items() if card_id in selected and card_id not in preferred)
        return tuple(ordered)
    return tuple(card for card_id, card in METHOD_CARDS.items() if card_id in selected)
