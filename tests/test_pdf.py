from pathlib import Path

import pytest

from young_stock.artifacts import ReportArtifacts
from young_stock.pdf import PDFDependencyError, export_report_pdf, markdown_to_html


def test_markdown_to_html_escapes_raw_html():
    html = markdown_to_html("# 标题\n\n<script>alert(1)</script>\n\n- 风险")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<h1>" in html


def test_export_report_uses_existing_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    source = ReportArtifacts("20260618").write_markdown("replay", "# 复盘\n\n正文")
    calls = []

    def fake_render(html_path: Path, pdf_path: Path):
        calls.append((html_path, pdf_path))
        pdf_path.write_bytes(b"%PDF-test")

    markdown_path, pdf_path = export_report_pdf("20260618", render=fake_render)

    assert markdown_path == source
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert calls[0][0].name == "report.html"


def test_export_report_auto_generates_daily_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    markdown_path, pdf_path = export_report_pdf(
        "20260618",
        daily_markdown_factory=lambda: "# 自动日报\n\n真实数据",
        render=lambda html, pdf: pdf.write_bytes(b"%PDF-auto"),
    )

    assert markdown_path.name == "daily.md"
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

    assert markdown_path.name == "daily.md"
    assert "Diary report" in markdown_path.read_text()


def test_default_renderer_has_clear_optional_dependency_error(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    ReportArtifacts("20260618").write_markdown("daily", "# 日报")
    monkeypatch.setattr("young_stock.pdf._load_weasyprint", lambda: None)

    with pytest.raises(PDFDependencyError, match=r"uv tool install --force"):
        export_report_pdf("20260618")
