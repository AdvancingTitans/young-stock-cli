from copy import deepcopy

import pytest

from young_stock.research_style import (
    ResearchStyleError,
    normalize_report_markdown,
    review_research_report,
    to_research_evidence,
    to_research_methodology,
)


def sample_evidence():
    return {
        "modules": {
            "M2": {
                "available": False,
                "industry": [],
                "fund_flow": {"_error": "request failed in /tmp/get_flow.py"},
            },
            "M5": {
                "available": True,
                "style_signals": {"growth_board_count": 14},
            },
        },
        "_meta": {
            "trade_date": "20260618",
            "quality_score": 35,
            "missing_modules": ["M2"],
            "degrade_mode": "simplified",
        },
    }


def test_to_research_evidence_is_pure_and_contains_no_internal_names():
    evidence = sample_evidence()
    original = deepcopy(evidence)

    converted = to_research_evidence(evidence)
    text = str(converted)

    assert evidence == original
    assert "modules" not in text
    assert "available" not in text
    assert "growth_board_count" not in text
    assert "degrade_mode" not in text
    assert "科创板与创业板活跃样本数" in text
    assert "相关指标当日未披露" in text


def test_to_research_evidence_handles_numeric_ladder_keys():
    evidence = {
        "modules": {
            "M3": {
                "emotion": {
                    "ladder": {
                        3: [{"code": "600002", "name": "B"}],
                    }
                }
            }
        },
        "_meta": {},
    }

    converted = to_research_evidence(evidence)

    ladder = converted["研报证据"]["赚钱效应与涨停结构"]["短线情绪证据"]["连板梯队"]
    assert ladder["3"] == [{"code": "600002", "name": "B"}]


def test_review_research_report_handles_markdown_wrapped_engineering_phrases():
    markdown = (
        "# 复盘\n\n"
        "* **证据**: `modules.M2.available` 为 `false`。\n"
        "* **风格信号**: `growth_board_count` 为 14。\n"
        "* 数据通过 fallback 脚本采集，位置 `/tmp/a.py`，存在不确定性。\n"
    )

    reviewed = review_research_report(markdown, sample_evidence())

    forbidden = (
        "modules.M2.available",
        "growth_board_count",
        "fallback",
        "脚本",
        "采集",
        "不确定性",
        "/tmp/",
        ".py",
    )
    assert all(word not in reviewed for word in forbidden)
    assert "相关指标当日未披露" in reviewed
    assert "科创板与创业板活跃样本数为 14 家" in reviewed


def test_review_research_report_strips_fixed_preamble_and_layout_noise():
    markdown = (
        "# 复盘\n\n"
        "好的，作为资深A股交易员，以下是今天的正式报告。\n"
        "据公开市场数据，市场震荡整理。\n"
        "young-stock-cli publication layout · 内容仅供复盘参考\n"
    )

    reviewed = review_research_report(markdown, sample_evidence())

    assert "资深A股交易员" not in reviewed
    assert "young-stock-cli publication layout" not in reviewed
    assert reviewed.count("本文来自公开市场数据。仅供复盘参考，不构成投资建议。") == 1
    assert "市场震荡整理" in reviewed


def test_review_research_report_removes_placeholder_only_line_but_keeps_context_sentence():
    reviewed = review_research_report(
        "# 复盘\n\n- 本模块证据暂缺。\n这句话只是提示本模块证据暂缺导致样本不足。\n",
        sample_evidence(),
    )

    assert "- 本模块证据暂缺。" not in reviewed
    assert "这句话只是提示本模块证据暂缺导致样本不足。" in reviewed


def test_review_research_report_normalizes_markdown_spacing_and_percent_signs():
    markdown = (
        "# 复盘\n\n"
        "## 综合持仓建议与风险提示\n"
        "### 交易计划草案\n"
        "- **触发条件**：若指数   跌超2 %，则维持观察。\n"
        "    - 若半导体设备板块涨幅   超5 %，再提高观察优先级。\n"
        "   - 若基金估算净值跌超3 %，暂不提高风险暴露。\n"
        "- **不行动条件**：证据    不足时维持观察。\n"
    )

    reviewed = review_research_report(markdown, sample_evidence())

    assert "跌超2%" in reviewed
    assert "超5%" in reviewed
    assert "跌超3%" in reviewed
    assert "指数   跌" not in reviewed
    assert "证据    不足" not in reviewed
    assert "  - 若半导体设备板块" in reviewed
    assert "  - 若基金估算净值" in reviewed
    assert "    - 若半导体设备板块" not in reviewed
    assert "   - 若基金估算净值" not in reviewed


def test_normalize_report_markdown_keeps_code_blocks_untouched():
    markdown = "```text\n跌超2 %\n    - raw   spacing\n```\n\n- 正文  跌超2 %"

    normalized = normalize_report_markdown(markdown)

    assert "跌超2 %\n    - raw   spacing" in normalized
    assert "- 正文 跌超2%" in normalized


def test_review_research_report_rejects_unrecognized_internal_field():
    with pytest.raises(ResearchStyleError):
        review_research_report("# 复盘\n\n`modules.UNKNOWN.secret` 为 true。", sample_evidence())


def test_to_research_methodology_removes_technical_instructions():
    text = (
        "# 输出纪律\n"
        "- 报告固定顺序：大盘指数概览 → 持仓分析 → 六模块深度复盘。\n"
        "- fallback、浏览器降级写入 evidence。\n"
        "- 执行 `sources/a.py` 脚本采集数据。\n"
        "- 建议必须使用条件化表达。\n"
    )

    converted = to_research_methodology(text)

    assert "报告固定顺序" in converted
    assert "建议必须使用条件化表达" in converted
    assert "fallback" not in converted
    assert "脚本" not in converted
    assert ".py" not in converted
