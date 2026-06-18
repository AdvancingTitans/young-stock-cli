import json

from young_stock.artifacts import ReportArtifacts
from young_stock.reports import generate_llm_daily_report


class FakeLLM:
    def chat(self, messages):
        assert '"quality_score": 85' in messages[-1]["content"]
        return type(
            "Result",
            (),
            {
                "content": "# 深度复盘\n\n==结构性偏强==\n\n以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。",
                "provider": "test",
                "model": "model",
                "usage": {"total_tokens": 12},
            },
        )()


def test_report_artifacts_write_and_find_latest(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    artifacts = ReportArtifacts("20260618")

    markdown = artifacts.write_markdown("replay", "# report")
    evidence = artifacts.write_json("evidence", {"ok": True})

    assert markdown == tmp_path / "reports" / "20260618" / "replay.md"
    assert json.loads(evidence.read_text())["ok"] is True
    assert ReportArtifacts.latest_markdown("20260618") == markdown


def test_generate_llm_daily_report_uses_evidence_and_returns_metadata():
    evidence = {
        "_meta": {"trade_date": "20260618", "quality_score": 85, "missing_modules": []},
        "modules": {"M1": {"available": True}},
    }

    markdown, metadata = generate_llm_daily_report(evidence, FakeLLM())

    assert "深度复盘" in markdown
    assert metadata["provider"] == "test"
    assert metadata["usage"]["total_tokens"] == 12
