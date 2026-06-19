from types import SimpleNamespace

from young_stock.reports import generate_llm_daily_report


class RecordingClient:
    def __init__(self, content: str):
        self.content = content
        self.messages = []

    def chat(self, messages):
        self.messages = messages
        return SimpleNamespace(content=self.content, provider="test", model="test-model", usage={})


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
    assert "本模块证据暂缺" in prompt
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
    assert "本模块证据暂缺" in markdown
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
        methodology="报告固定顺序。\nfallback 写入 evidence。\n运行 tools/a.py 脚本采集。",
    )

    system_text = "\n".join(message["content"] for message in client.messages if message["role"] == "system")
    assert "资深A股交易员" not in system_text
    assert "报告固定顺序" in system_text
    assert "fallback" not in system_text
    assert "脚本" not in system_text
    assert ".py" not in system_text
