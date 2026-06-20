import os
from types import SimpleNamespace

import pytest

from young_stock.artifacts import ReportArtifacts, ReportIdentity
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
    assert "同名 PDF" in payload["content"]["text"]
    assert "webhook 不支持附件上传" in payload["content"]["text"]


def test_feishu_webhook_preview_mentions_missing_pdf(tmp_path):
    markdown = tmp_path / "report.md"
    markdown.write_text("# 标题\n\n摘要")
    session = FakeSession([(200, {"code": 0})])
    channel = FeishuChannel("work", {"webhook": "https://example/hook/token"}, session=session)

    result = channel.send(markdown, None)

    assert result.ok
    payload = session.calls[0][1]["json"]
    assert "未检测到同名 PDF" in payload["content"]["text"]


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

    with pytest.raises(ValueError, match="缺少可发送的 Markdown"):
        send_report("20260618")


def test_send_report_uses_identity_named_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    artifacts = ReportArtifacts("20260618")
    identity = ReportIdentity("20260618", "盘后", "A股深度复盘")
    markdown = artifacts.write_report_markdown(identity, "# 复盘\n\n正文")
    pdf = artifacts.path(identity.prefix, "pdf")
    pdf.write_bytes(b"%PDF")
    sent = []

    class DummyChannel:
        def __init__(self, name, config):
            self.name = name
            self.config = config

        def send(self, markdown_path, pdf_path):
            sent.append((markdown_path, pdf_path))
            return SimpleNamespace(ok=True, channel=self.name, target="x", detail="ok")

    monkeypatch.setattr("young_stock.channels.load_config", lambda strict=False: {"channels": {"feishu": {"work": {"webhook": "x"}}}})
    monkeypatch.setattr("young_stock.channels.FeishuChannel", DummyChannel)

    results = send_report("20260618")

    assert results[0].ok is True
    assert sent == [(markdown, pdf)]


def test_send_report_without_pdf_uses_latest_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    older = ReportArtifacts("20260618").write_report_markdown(
        ReportIdentity("20260618", "盘后", "A股深度复盘"),
        "# 旧复盘\n\n正文",
    )
    markdown = ReportArtifacts("20260619").write_report_markdown(
        ReportIdentity("20260619", "盘中", "A股深度复盘"),
        "# 新复盘\n\n正文",
    )
    old_stat = older.stat()
    os.utime(older, (old_stat.st_atime, old_stat.st_mtime - 10))
    sent = []

    class DummyChannel:
        def __init__(self, name, config):
            self.name = name
            self.config = config

        def send(self, markdown_path, pdf_path):
            sent.append((markdown_path, pdf_path))
            return SimpleNamespace(ok=True, channel=self.name, target="x", detail="ok")

    monkeypatch.setattr("young_stock.channels.load_config", lambda strict=False: {"channels": {"feishu": {"work": {"webhook": "x"}}}})
    monkeypatch.setattr("young_stock.channels.FeishuChannel", DummyChannel)

    results = send_report(None)

    assert results[0].ok is True
    assert sent == [(markdown, None)]


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
