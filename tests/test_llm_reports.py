from types import SimpleNamespace

import pytest

from young_stock.llm import LLMError
from young_stock.reports import generate_llm_daily_report


class RecordingClient:
    def __init__(self, content: str):
        self.content = content
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return SimpleNamespace(content=self.content, provider="test", model="test-model", usage={})


class SequencedClient:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.contents.pop(0), provider="test", model="test-model", usage={})


def test_llm_report_context_translates_internal_fields_for_research_writing():
    client = RecordingClient("# 复盘\n\n据公开市场数据，板块表现偏强。")
    evidence = {
        "modules": {
            "M2": {"available": False, "industry": [], "concept": [], "fund_flow": {}},
            "M5": {"available": True, "style_signals": {"growth_board_count": 14}},
        },
        "_meta": {
            "trade_date": "20260618",
            "quality_score": 40,
            "missing_modules": ["M2"],
            "degrade_mode": "simplified",
        },
    }

    generate_llm_daily_report(evidence, client)

    prompt = client.messages[-1]["content"]
    assert "modules.M2.available" not in prompt
    assert "growth_board_count" not in prompt
    assert '"available"' not in prompt
    assert "missing_modules" not in prompt
    assert "degrade_mode" not in prompt
    assert "科创板与创业板活跃样本数" in prompt
    assert "相关指标当日未披露" in prompt
    assert "板块强弱与资金流" in prompt


def test_llm_report_output_removes_engineering_language():
    client = RecordingClient(
        "# 复盘\n\n证据: modules.M2.available 为 false。\n"
        "风格信号: growth_board_count 为 14。\n"
        "数据通过 fallback 脚本采集，存在不确定性。"
    )

    markdown, _ = generate_llm_daily_report(
        {
            "modules": {
                "M2": {"available": False, "industry": [], "concept": [], "fund_flow": {}},
                "M5": {"available": True, "style_signals": {"growth_board_count": 14}},
            },
            "_meta": {"trade_date": "20260618", "quality_score": 40, "missing_modules": ["M2"]},
        },
        client,
    )

    for forbidden in (
        "modules.M2.available",
        "growth_board_count",
        "fallback",
        "脚本",
        "采集",
        "不确定性",
    ):
        assert forbidden not in markdown
    assert "相关指标当日未披露" in markdown
    assert "科创板与创业板活跃样本数为 14 家" in markdown
    assert "相关指标以已披露口径为准" in markdown
    assert "备用路径" not in markdown


def test_llm_report_output_strips_fixed_preamble():
    client = RecordingClient(
        "# 复盘\n\n"
        "好的，作为资深A股交易员，以下是今天的复盘。\n"
        "据公开市场数据，板块轮动加快。\n"
    )

    markdown, _ = generate_llm_daily_report({"modules": {}, "_meta": {}}, client)

    assert "资深A股交易员" not in markdown
    assert "板块轮动加快" in markdown


def test_llm_methodology_context_is_research_only():
    client = RecordingClient("# 复盘\n\n据公开市场数据，市场震荡。")

    generate_llm_daily_report(
        {"modules": {}, "_meta": {}},
        client,
        methodology="young-stock-cli 内置研究框架。\n报告固定顺序。\nfallback 写入 evidence。\n运行 tools/a.py 脚本采集。",
    )

    system_text = "\n".join(message["content"] for message in client.messages if message["role"] == "system")
    assert "资深A股交易员" not in system_text
    assert "young-stock-cli 内置研究框架" in system_text
    assert "报告固定顺序" in system_text
    assert "fallback" not in system_text
    assert "脚本" not in system_text
    assert ".py" not in system_text


def test_llm_report_system_prompt_uses_short_public_disclaimer_contract():
    client = RecordingClient("# 复盘\n\n据公开市场数据，市场震荡。")

    generate_llm_daily_report({"modules": {}, "_meta": {}}, client)

    system_text = "\n".join(message["content"] for message in client.messages if message["role"] == "system")
    assert "结尾必须原样包含" not in system_text
    assert "不构成任何投资建议。股市有风险，投资需谨慎。" not in system_text
    assert "不要重复免责声明" in system_text


def test_llm_report_system_prompt_rejects_persona_framework_drift():
    client = RecordingClient("# 复盘\n\n据公开市场数据，市场震荡。")

    generate_llm_daily_report({"modules": {}, "_meta": {}}, client)

    system_text = "\n".join(message["content"] for message in client.messages if message["role"] == "system")
    assert "young-stock-cli 的 M1-M6 框架" in system_text
    assert "### M1 大盘指数与市场广度" in system_text
    assert "### M6 抗跌方向" in system_text


def test_llm_report_without_explicit_lens_does_not_load_lens_layer(monkeypatch):
    client = RecordingClient("# 复盘\n\n据公开市场数据，市场震荡。")
    seen = []

    monkeypatch.setattr("young_stock.reports.build_institutional_prompt", lambda *args, **kwargs: seen.append("institutional") or "institutional")
    monkeypatch.setattr("young_stock.reports.build_lens_prompt", lambda *args, **kwargs: seen.append("lens") or "lens")
    monkeypatch.setattr("young_stock.reports.DebateEngine", lambda *args, **kwargs: SimpleNamespace(prompt=lambda: seen.append("debate") or "debate"))

    _, metadata = generate_llm_daily_report({"modules": {}, "_meta": {}}, client, lens=None)

    assert seen == []
    assert metadata["lens"] is None
    assert metadata["debate_rounds"] == 0


def test_llm_report_with_explicit_balanced_lens_uses_institutional_prompt(monkeypatch):
    client = RecordingClient("# 复盘\n\n据公开市场数据，市场震荡。")
    seen = []

    monkeypatch.setattr("young_stock.reports.build_institutional_prompt", lambda lens, **kwargs: seen.append(("institutional", lens, kwargs)) or "balanced prompt")
    monkeypatch.setattr("young_stock.reports.build_lens_prompt", lambda *args, **kwargs: seen.append(("lens", args, kwargs)) or "lens prompt")
    monkeypatch.setattr("young_stock.reports.DebateEngine", lambda *args, **kwargs: SimpleNamespace(prompt=lambda: seen.append(("debate", args, kwargs)) or "debate"))

    _, metadata = generate_llm_daily_report({"modules": {}, "_meta": {}}, client, lens="balanced")

    assert seen == [("institutional", "balanced", {"rounds": 3, "daily": True})]
    assert metadata["lens"] == "balanced"
    assert metadata["debate_rounds"] == 0


def test_llm_report_adds_m7_and_hidden_committee_when_lens_all():
    client = RecordingClient("# 复盘\n\n## M7 机构化综合判断\n\n总体态度：中性。")

    _, metadata = generate_llm_daily_report(
        {"modules": {}, "_meta": {}},
        client,
        lens="all",
        debate_rounds=3,
    )

    system_text = "\n".join(message["content"] for message in client.messages if message["role"] == "system")
    assert "## M7 机构化综合判断" in system_text
    assert "内部完成 3 轮" in system_text
    assert "不要向用户展示辩论过程" in system_text
    assert metadata["lens"] == "all"
    assert metadata["debate_rounds"] == 3


def test_llm_report_repairs_once_when_gate_fails_then_returns_valid_output():
    client = SequencedClient(
        [
            "# 复盘\n\n总体态度：偏看多\n风险：估值。\n行动建议：持有。",
            "# 复盘\n\n总体态度：偏看多\n详细结论：景气延续但估值抬升。\n证据：据公开数据，ROE 为 20%。\n风险：估值波动。\n行动建议：持有观察。\n观察清单：跟踪下一季订单。",
        ]
    )

    markdown, metadata = generate_llm_daily_report(
        {"modules": {"STOCK": {"roe": "20%"}}, "_meta": {}},
        client,
    )

    assert len(client.calls) == 2
    assert "观察清单" in markdown
    assert all(metadata["mechanical_checks"].values())


def test_llm_report_raises_llm_error_after_failed_repair_and_does_not_save_invalid_output():
    client = SequencedClient(
        [
            "# 复盘\n\n总体态度：偏看多\n风险：估值。\n行动建议：持有。",
            "# 复盘\n\n总体态度：偏看多\n风险：估值。\n行动建议：持有。",
        ]
    )

    with pytest.raises(LLMError):
        generate_llm_daily_report({"modules": {}, "_meta": {}}, client)


def test_llm_report_accepts_grounded_symbol_digits_without_repair():
    client = SequencedClient(
        [
            "# 贵州茅台（600519）复盘\n\n"
            "总体态度：偏看多\n"
            "详细结论：据公开数据，600519 的 ROE 为 20%。\n"
            "证据：据公开数据，SH600519 对应标的 ROE 为 20%。\n"
            "风险：估值波动。\n"
            "行动建议：持有观察。\n"
            "观察清单：1. 跟踪批价。"
        ]
    )

    markdown, metadata = generate_llm_daily_report(
        {"analysis_symbol": "SH600519", "modules": {"STOCK": {"roe": "20%"}}, "_meta": {}},
        client,
    )

    assert "600519" in markdown
    assert len(client.calls) == 1
    assert all(metadata["mechanical_checks"].values())


def test_llm_report_repairs_date_fragment_claims_against_atomic_date_evidence():
    client = SequencedClient(
        [
            "# 日报\n\n"
            "总体态度：中性\n"
            "详细结论：2026-05-29 发布后，2026 年业绩将改善，05 月跟踪，29 日复盘。\n"
            "证据：报告日期为 20260529。\n"
            "风险：预测可能落空。\n"
            "行动建议：持有观察。\n"
            "观察清单：1. 跟踪后续公告。",
            "# 日报\n\n"
            "总体态度：中性\n"
            "详细结论：据公开数据，业绩改善有待验证。\n"
            "证据：据公开数据，ROE 为 20%。\n"
            "风险：预测可能落空。\n"
            "行动建议：持有观察。\n"
            "观察清单：1. 跟踪后续公告。",
        ]
    )

    markdown, metadata = generate_llm_daily_report(
        {"modules": {"STOCK": {"roe": "20%"}}, "_meta": {"reported_date": "20260529"}},
        client,
    )

    assert len(client.calls) == 2
    assert "2026-05-29" not in markdown
    assert all(metadata["mechanical_checks"].values())
