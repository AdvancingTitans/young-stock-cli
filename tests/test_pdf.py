from pathlib import Path

import pytest

from young_stock.artifacts import ReportArtifacts
from young_stock.pdf import PDFDependencyError, export_report_pdf, markdown_to_html


def test_markdown_to_html_escapes_raw_html():
    html = markdown_to_html("# 标题\n\n<script>alert(1)</script>\n\n- 风险")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<h1>" in html


def test_markdown_to_html_renders_only_safe_http_links():
    html = markdown_to_html(
        "# 标题\n\n"
        "[公开新闻](https://example.com/a?x=1&y=2)\n\n"
        "[带括号链接](https://example.com/path_(v2)/q(test))\n\n"
        "[恶意链接](javascript:alert(1))\n\n"
        "[本地文件](file:///tmp/demo)\n"
    )

    assert '<a href="https://example.com/a?x=1&amp;y=2">公开新闻</a>' in html
    assert '<a href="https://example.com/path_(v2)/q(test)">带括号链接</a>' in html
    assert 'href="javascript:alert(1)"' not in html
    assert 'href="file:///tmp/demo"' not in html
    assert "[恶意链接](javascript:alert(1))" in html
    assert "[本地文件](file:///tmp/demo)" in html


def test_export_report_uses_existing_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    source = ReportArtifacts("20260618").write_markdown("replay", "# 复盘\n\n正文")
    calls = []

    def fake_render(html_path: Path, pdf_path: Path):
        calls.append((html_path, pdf_path))
        pdf_path.write_bytes(b"%PDF-test")

    markdown_path, pdf_path = export_report_pdf("20260618", render=fake_render)

    assert markdown_path != source
    assert markdown_path.name.startswith("20260618-")
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert calls[0][0].name.startswith("20260618-")


def test_export_report_prefers_explicit_markdown_path_over_newer_same_day_report(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    artifacts = ReportArtifacts("20260618")
    chosen = artifacts.directory / "20260618-盘后-A股深度复盘.md"
    newer = artifacts.directory / "20260618-盘后-A股投资日报.md"
    chosen.write_text("# 深度复盘\n\n正文 A\n", encoding="utf-8")
    newer.write_text("# 投资日报\n\n正文 B\n", encoding="utf-8")
    chosen.touch()
    newer.touch()
    chosen.touch()
    newer.touch()

    markdown_path, pdf_path = export_report_pdf(
        "20260618",
        markdown_path=chosen,
        render=lambda html, pdf: pdf.write_bytes(b"%PDF-explicit"),
    )

    assert markdown_path == chosen
    assert pdf_path.name == "20260618-盘后-A股深度复盘.pdf"
    assert "深度复盘" in pdf_path.with_suffix(".html").read_text(encoding="utf-8")


def test_export_report_auto_generates_daily_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    markdown_path, pdf_path = export_report_pdf(
        "20260618",
        daily_markdown_factory=lambda: "# 自动日报\n\n真实数据",
        render=lambda html, pdf: pdf.write_bytes(b"%PDF-auto"),
    )

    assert markdown_path.name.endswith("-A股投资日报.md")
    assert "自动日报" in markdown_path.read_text()
    assert pdf_path.exists()


def test_export_report_reuses_saved_diary_text(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    (tmp_path / "diaries.json").write_text(
        '{"20260618": {"text": "# Diary report\\n\\nSaved text"}}',
        encoding="utf-8",
    )

    markdown_path, _ = export_report_pdf(
        "20260618",
        daily_markdown_factory=lambda: (_ for _ in ()).throw(AssertionError("must not regenerate")),
        render=lambda html, pdf: pdf.write_bytes(b"%PDF-diary"),
    )

    assert markdown_path.name.endswith("-A股投资日报.md")
    assert "Diary report" in markdown_path.read_text()


def test_export_report_strips_layout_noise_and_fixed_preamble(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    ReportArtifacts("20260618").write_markdown(
        "replay",
        "# 复盘\n\n"
        "数据来源: young-stock-cli 核心模块，多源免登录行情与新闻聚合。\n"
        "说明: 以下内容仅供复盘参考，不构成投资建议。\n"
        "好的，作为资深A股交易员，以下是今天的报告。\n"
        "Kami-compatible editorial layout · 内容仅供复盘参考\n"
        "正文\n",
    )

    markdown_path, pdf_path = export_report_pdf(
        "20260618",
        render=lambda html, pdf: pdf.write_bytes(b"%PDF-clean"),
    )

    cleaned = markdown_path.read_text(encoding="utf-8")
    assert "资深A股交易员" not in cleaned
    assert cleaned.count("本文来自公开市场数据。仅供复盘参考，不构成投资建议。") == 1
    assert "说明: 以下内容仅供复盘参考，不构成投资建议。" not in cleaned
    assert "数据来源: young-stock-cli 核心模块，多源免登录行情与新闻聚合。" not in cleaned
    html_text = pdf_path.with_suffix(".html").read_text(encoding="utf-8")
    assert "Kami-compatible editorial layout" not in html_text
    assert "本文来自公开市场数据。仅供复盘参考，不构成投资建议。" in html_text


def test_default_renderer_has_clear_optional_dependency_error(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    ReportArtifacts("20260618").write_markdown("daily", "# 日报")
    monkeypatch.setattr("young_stock.pdf._load_weasyprint", lambda: None)

    with pytest.raises(PDFDependencyError, match=r"young init"):
        export_report_pdf("20260618")


def test_export_report_rejects_explicit_markdown_path_outside_trade_date_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    outside = tmp_path / "outside.md"
    outside.write_text("# 外部报告\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"20260618"):
        export_report_pdf(
            "20260618",
            markdown_path=outside,
            render=lambda html, pdf: pdf.write_bytes(b"%PDF-nope"),
        )


def test_export_report_rejects_missing_explicit_markdown_path(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    with pytest.raises(ValueError, match=r"不存在"):
        export_report_pdf(
            "20260618",
            markdown_path=tmp_path / "reports" / "20260618" / "missing.md",
            render=lambda html, pdf: pdf.write_bytes(b"%PDF-missing"),
        )
