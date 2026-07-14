import subprocess

import young_stock.research_bridge as bridge_module


def test_run_research_bridge_explains_missing_configuration(monkeypatch):
    monkeypatch.delenv("YOUNG_STOCK_RESEARCH_COMMAND", raising=False)

    result = bridge_module.run_research_bridge("600519 最新财报")

    assert "YOUNG_STOCK_RESEARCH_COMMAND" in result["_unavailable"]
    assert "可选联网研究桥" in result["_unavailable"]


def test_run_research_bridge_uses_placeholder_and_compacts_output(monkeypatch):
    monkeypatch.setenv("YOUNG_STOCK_RESEARCH_COMMAND", "research-helper fetch --query {query} --limit 5")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="title: 财报增长\n营收增长 10%\nhttps://example.com/raw\n",
            stderr="",
        )

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)

    result = bridge_module.run_research_bridge('Tesla "Q1" guidance')

    assert calls[0][0] == ["research-helper", "fetch", "--query", 'Tesla "Q1" guidance', "--limit", "5"]
    assert calls[0][1]["shell"] is False
    assert result["_source"] == "configured research bridge"
    assert "营收增长 10%" in result["summary_material"]
    assert "https://example.com/raw" not in result["summary_material"]
    assert "title: 财报增长" in result["source_material"]
    assert "https://example.com/raw" in result["source_material"]


def test_run_research_bridge_appends_query_when_placeholder_absent(monkeypatch):
    monkeypatch.setenv("YOUNG_STOCK_RESEARCH_COMMAND", "research-helper fetch --limit 3")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="净利润 21 亿美元\n", stderr="")

    monkeypatch.setattr(bridge_module.subprocess, "run", fake_run)

    result = bridge_module.run_research_bridge("贵州茅台 最新公告")

    assert calls[0][-1] == "贵州茅台 最新公告"
    assert result["summary_material"] == "净利润 21 亿美元"
