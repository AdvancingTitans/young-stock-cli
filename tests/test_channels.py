from types import SimpleNamespace

import pytest

from young_stock.channels import send_report
from young_stock.channels.feishu import FeishuChannel


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        status, payload = self.responses.pop(0)
        return SimpleNamespace(status_code=status, json=lambda: payload, text=str(payload), headers={})


def test_feishu_webhook_sends_preview_without_claiming_attachment(tmp_path):
    markdown = tmp_path / "report.md"
    pdf = tmp_path / "report.pdf"
    markdown.write_text("# 标题\n\n摘要")
    pdf.write_bytes(b"%PDF")
    session = FakeSession([(200, {"code": 0})])
    channel = FeishuChannel("work", {"webhook": "https://example/hook/token"}, session=session)

    result = channel.send(markdown, pdf)

    assert result.ok
    payload = session.calls[0][1]["json"]
    assert "PDF 本地路径" in payload["content"]["text"]
    assert "已附加" not in payload["content"]["text"]


def test_feishu_app_uploads_and_sends_both_files(tmp_path):
    markdown = tmp_path / "report.md"
    pdf = tmp_path / "report.pdf"
    markdown.write_text("# 标题\n\n摘要")
    pdf.write_bytes(b"%PDF")
    session = FakeSession(
        [
            (200, {"code": 0, "tenant_access_token": "token"}),
            (200, {"code": 0}),
            (200, {"code": 0, "data": {"file_key": "md-key"}}),
            (200, {"code": 0}),
            (200, {"code": 0, "data": {"file_key": "pdf-key"}}),
            (200, {"code": 0}),
        ]
    )
    channel = FeishuChannel(
        "app",
        {"app_id": "id", "app_secret": "secret", "receive_id": "chat", "receive_id_type": "chat_id"},
        session=session,
    )

    result = channel.send(markdown, pdf)

    assert result.ok
    assert len(session.calls) == 6


def test_send_report_requires_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr("young_stock.channels.load_config", lambda strict=False: {"channels": {"feishu": {"work": {"webhook": "x"}}}})

    with pytest.raises(ValueError, match="young report"):
        send_report("20260618")


def test_feishu_retries_transient_http_failure(monkeypatch, tmp_path):
    markdown = tmp_path / "report.md"
    pdf = tmp_path / "report.pdf"
    markdown.write_text("# 标题")
    pdf.write_bytes(b"%PDF")
    session = FakeSession([(500, {}), (200, {"code": 0})])
    monkeypatch.setattr("young_stock.channels.feishu.time.sleep", lambda seconds: None)

    result = FeishuChannel("work", {"webhook": "https://example/hook/token"}, session=session).send(markdown, pdf)

    assert result.ok
    assert len(session.calls) == 2
