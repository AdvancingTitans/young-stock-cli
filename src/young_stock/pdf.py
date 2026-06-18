"""Kami-compatible Markdown to PDF report export."""

from __future__ import annotations

import contextlib
import html
import io
import os
import re
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from .artifacts import ReportArtifacts
from .local_store import load_store


class PDFDependencyError(RuntimeError):
    """The optional PDF renderer is unavailable."""


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"==(.+?)==", r'<strong class="highlight">\1</strong>', escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def markdown_to_html(markdown: str) -> str:
    """Convert the report's Markdown subset while escaping raw HTML."""
    lines = markdown.splitlines()
    output: list[str] = []
    in_list = False
    in_table = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if in_table and (not stripped or "|" not in stripped):
            output.append("</tbody></table>")
            in_table = False
        if in_list and not stripped.startswith(("- ", "* ")):
            output.append("</ul>")
            in_list = False
        if not stripped:
            continue
        if stripped.startswith("#"):
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            output.append(f"<h{level}>{_inline(stripped[level:].strip())}</h{level}>")
            continue
        if stripped.startswith(("- ", "* ")):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{_inline(stripped[2:].strip())}</li>")
            continue
        if "|" in stripped and stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            if not in_table:
                output.append("<table><tbody>")
                in_table = True
            tag = "th" if index + 1 < len(lines) and re.match(r"^\|?[\s:|-]+\|?$", lines[index + 1]) else "td"
            output.append("<tr>" + "".join(f"<{tag}>{_inline(cell)}</{tag}>" for cell in cells) + "</tr>")
            continue
        if stripped.startswith(">"):
            output.append(f"<blockquote>{_inline(stripped[1:].strip())}</blockquote>")
            continue
        output.append(f"<p>{_inline(stripped)}</p>")
    if in_list:
        output.append("</ul>")
    if in_table:
        output.append("</tbody></table>")
    return "\n".join(output)


def _template_text() -> str:
    override = os.environ.get("YOUNG_STOCK_KAMI_TEMPLATE")
    if override and Path(override).expanduser().exists():
        return Path(override).expanduser().read_text(encoding="utf-8")
    kami_home = os.environ.get("YOUNG_STOCK_KAMI_HOME")
    if kami_home:
        candidate = Path(kami_home).expanduser() / "assets" / "templates" / "equity-report.html"
        if candidate.exists():
            external = candidate.read_text(encoding="utf-8")
            if all(placeholder in external for placeholder in ("{{TITLE}}", "{{DATE}}", "{{BODY}}")):
                return external
    return (
        resources.files("young_stock")
        .joinpath("templates/equity-report.html")
        .read_text(encoding="utf-8")
    )


def _load_weasyprint() -> Any:
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "young-stock-weasy-cache"))
    if sys.platform == "darwin":
        for prefix in (Path("/opt/homebrew"), Path("/usr/local")):
            library = prefix / "lib" / "libgobject-2.0.dylib"
            if not library.exists():
                continue
            existing = [item for item in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(":") if item]
            if str(library.parent) not in existing:
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join([str(library.parent), *existing])
            break
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    return HTML


def _default_render(html_path: Path, pdf_path: Path) -> None:
    renderer = _load_weasyprint()
    if renderer is None:
        raise PDFDependencyError(
            "未安装 PDF 可选依赖。uv tool 用户请运行 "
            "`uv tool install --force 'young-stock-cli[pdf]'`；"
            "普通 Python 环境请运行 `python3 -m pip install \"young-stock-cli[pdf]\"`。"
        )
    renderer(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))


def _capture_daily(core: Any, trade_date: str, profile: dict[str, Any] | None) -> str:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        core.run_daily_report(
            trade_date,
            profile or {},
            include_news=True,
            report_format="full",
            only=None,
            order=None,
            quick=False,
        )
    return stream.getvalue()


def export_report_pdf(
    trade_date: str,
    *,
    core: Any = None,
    profile: dict[str, Any] | None = None,
    daily_markdown_factory: Callable[[], str] | None = None,
    render: Callable[[Path, Path], None] | None = None,
) -> tuple[Path, Path]:
    artifacts = ReportArtifacts(trade_date)
    markdown_path = ReportArtifacts.latest_markdown(trade_date)
    if markdown_path is None:
        diary = load_store("diaries", {}).get(trade_date, {})
        diary_text = str(diary.get("text") or "") if isinstance(diary, dict) else ""
        if diary_text.strip():
            markdown = diary_text
        elif daily_markdown_factory:
            markdown = daily_markdown_factory()
        elif core is not None:
            markdown = _capture_daily(core, trade_date, profile)
        else:
            raise ValueError("没有可用报告；请先运行 `young daily` 或提供日报生成器。")
        markdown_path = artifacts.write_markdown("daily", markdown)
    markdown = markdown_path.read_text(encoding="utf-8")
    body = markdown_to_html(markdown)
    title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else f"{trade_date} 投资复盘报告"
    document = (
        _template_text()
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{DATE}}", trade_date)
        .replace("{{BODY}}", body)
    )
    html_path = artifacts.path("report", "html")
    html_path.write_text(document, encoding="utf-8")
    pdf_path = artifacts.path("report", "pdf")
    (render or _default_render)(html_path, pdf_path)
    return markdown_path, pdf_path
