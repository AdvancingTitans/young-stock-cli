from copy import deepcopy

import pytest

from young_stock.research_style import (
    ResearchStyleError,
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
    assert "本模块证据暂缺" in text


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
    assert "本模块证据暂缺" in reviewed
    assert "科创板与创业板活跃样本数为 14 家" in reviewed


def test_review_research_report_strips_fixed_preamble_and_layout_noise():
    markdown = (
        "# 复盘\n\n"
        "好的，作为资深A股交易员，以下是今天的正式报告。\n"
        "据公开市场数据，市场震荡整理。\n"
        "Kami-compatible editorial layout · 内容仅供复盘参考\n"
    )

    reviewed = review_research_report(markdown, sample_evidence())

    assert "资深A股交易员" not in reviewed
    assert "Kami-compatible editorial layout" not in reviewed
    assert "市场震荡整理" in reviewed


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
