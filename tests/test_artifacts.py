import json
from datetime import datetime

from young_stock.artifacts import DeliveryArtifacts, ReportArtifacts, ReportIdentity, market_session, report_session
from young_stock.reports import generate_llm_daily_report


class FakeLLM:
    def chat(self, messages):
        assert '"证据完整度评分": 85' in messages[-1]["content"]
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


def test_market_session_labels():
    assert market_session(datetime(2026, 6, 18, 8, 50)) == "盘前"
    assert market_session(datetime(2026, 6, 18, 9, 10)) == "早盘"
    assert market_session(datetime(2026, 6, 18, 9, 41)) == "早盘"
    assert market_session(datetime(2026, 6, 18, 10, 30)) == "早盘"
    assert market_session(datetime(2026, 6, 18, 12, 0)) == "午间"
    assert market_session(datetime(2026, 6, 18, 14, 10)) == "盘中"
    assert market_session(datetime(2026, 6, 18, 15, 10)) == "盘后"


def test_report_session_uses_after_close_for_historical_trade_date():
    assert report_session("20260618", datetime(2026, 6, 19, 9, 41)) == "盘后"
    assert report_session("20260619", datetime(2026, 6, 19, 8, 50)) == "盘后"
    assert report_session("20260618", datetime(2026, 6, 18, 9, 41)) == "早盘"


def test_report_identity_uses_date_session_and_topic():
    identity = ReportIdentity("20260618", "盘后", "A股深度复盘")
    assert identity.prefix == "20260618-盘后-A股深度复盘"


def test_same_session_topic_overwrites_and_cross_session_is_retained(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    artifacts = ReportArtifacts("20260618")
    after_close = ReportIdentity("20260618", "盘后", "A股深度复盘")
    midday = ReportIdentity("20260618", "午间", "A股深度复盘")

    first = artifacts.write_report_markdown(after_close, "# old")
    second = artifacts.write_report_markdown(after_close, "# new")
    other = artifacts.write_report_markdown(midday, "# midday")

    assert first == second
    assert second.read_text(encoding="utf-8") == "# new\n"
    assert other.exists()


def test_latest_markdown_prefers_identity_path_over_newer_legacy_file(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    artifacts = ReportArtifacts("20260619")
    legacy = artifacts.write_markdown("replay", "# legacy\n")
    identified = artifacts.write_report_markdown(ReportIdentity("20260619", "早盘", "A股深度复盘"), "# identity\n")

    legacy.touch()

    assert ReportArtifacts.latest_markdown("20260619") == identified


def test_latest_delivery_artifacts_uses_same_name_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    identity = ReportIdentity("20260619", "盘后", "A股深度复盘")
    artifacts = ReportArtifacts("20260619")
    markdown = artifacts.write_report_markdown(identity, "# identity\n")
    pdf = artifacts.path(identity.prefix, "pdf")
    pdf.write_bytes(b"%PDF")

    bundle = ReportArtifacts.latest_delivery_artifacts("20260619")

    assert bundle == DeliveryArtifacts(markdown=markdown, pdf=pdf)
