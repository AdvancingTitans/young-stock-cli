"""Hidden investment-committee prompt constraints for young reports."""

from __future__ import annotations

ALLOWED_FINAL_ATTITUDES = ("看涨", "偏看涨", "中性", "偏看空", "看空", "回避", "证据不足")

FORBIDDEN_PUBLIC_HEADINGS = (
    "Analyst Team",
    "Research Team",
    "Trader Agent",
    "Risk Management",
    "Portfolio Management",
)


def committee_prompt(*, asset_kind: str = "daily", lens: str | None = None) -> str:
    final_title = "综合持仓建议与风险提示"
    if lens and lens not in {"balanced", "all"}:
        final_title = "指定专家视角持仓建议与风险提示"
    asset_note = ""
    if asset_kind == "fund":
        asset_note = (
            "本次是基金投研结构。不要把基金写成普通公司或个股；"
            "指数基金、ETF、LOF 关注跟踪指数、跟踪误差、溢价折价和流动性；"
            "主动权益基金关注基金经理、风格漂移、重仓股变化和行业集中度；"
            "债券基金和货币基金关注久期、信用风险、利率环境、收益稳定性和回撤风险。"
        )
    elif asset_kind == "stock":
        asset_note = "本次是个股投研结构，重点围绕标的概览、行情趋势与资金、估值基本面与事件、新闻公告与情绪。"
    else:
        asset_note = "本次是 Daily M1-M7 复盘结构，M1-M6 强化证据表达，M7 只呈现研究委员会判断。"
    forbidden = "、".join(FORBIDDEN_PUBLIC_HEADINGS)
    attitudes = "、".join(ALLOWED_FINAL_ATTITUDES)
    if lens and lens not in {"balanced", "all"}:
        return (
            "本次是单专家视角，不触发多专家辩论，也不输出 M7 机构化综合判断。"
            f"报告中不得出现这些标题：{forbidden}。"
            f"{asset_note}"
            f"最后一章“{final_title}”只承载该专家框架下的态度、持仓建议和风险提示；"
            f"最终态度只能使用：{attitudes}。"
            "不要输出交易计划草案、风险管理意见、组合经理最终意见等委员会小节。"
            "所有动作建议必须是条件化触发器；证据不足时写“维持观察，不生成新增动作”或“证据不足，暂不提高风险暴露”。"
            "不得写真实交易执行、券商连接、自动下单或保证收益语义。"
        )
    return (
        "内部采用轻量投资委员会推理，但不得把内部角色作为一级标题暴露给用户。"
        f"报告中不得出现这些标题：{forbidden}。"
        f"{asset_note}"
        "M7 机构化综合判断只输出核心共识、主要分歧、看多证据、看空证据、待验证问题；"
        "不要输出逐轮辩论记录。"
        f"最后一章“{final_title}”必须整合交易计划、风险管理和组合经理最终意见，并包含五个小节："
        "最终态度、交易计划草案、风险管理意见、组合经理最终意见、下一交易日观察清单。"
        f"最终态度只能使用：{attitudes}。"
        "交易计划草案必须包含触发条件、失效条件、持仓动作草案、不行动条件。"
        "风险管理意见必须包含市场风险、标的或基金风险、组合集中度风险、流动性与波动风险、证据缺口风险、风险约束建议。"
        "组合经理最终意见必须包含最终态度、具体意见、组合层优先级、暂不行动理由、下一交易日观察清单。"
        "所有动作建议必须是条件化触发器；证据不足时写“维持观察，不生成新增动作”或“证据不足，暂不提高风险暴露”。"
        "不得写真实交易执行、券商连接、自动下单或保证收益语义。"
    )


def asset_kind_from_evidence(evidence: dict[str, object]) -> str:
    meta = evidence.get("_meta") if isinstance(evidence, dict) else {}
    if isinstance(meta, dict) and meta.get("asset_kind") == "fund":
        return "fund"
    modules = evidence.get("modules") if isinstance(evidence, dict) else {}
    if isinstance(modules, dict) and "FUND" in modules:
        return "fund"
    if isinstance(meta, dict) and meta.get("report_type") == "single-stock":
        return "stock"
    if isinstance(modules, dict) and "STOCK" in modules:
        return "stock"
    return "daily"
