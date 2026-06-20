"""young-stock-cli Markdown to PDF report export."""

from __future__ import annotations

import contextlib
import html
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .artifacts import ReportArtifacts, ReportIdentity, report_session
from .local_store import load_store
from .research_style import sanitize_public_report


class PDFDependencyError(RuntimeError):
    """The optional PDF renderer is unavailable."""


def _inline_text(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"==(.+?)==", r'<strong class="highlight">\1</strong>', escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def _safe_link_href(raw: str) -> str | None:
    candidate = html.unescape(raw).strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _parse_markdown_link(text: str, start: int) -> tuple[int, str, str] | None:
    if start < 0 or start >= len(text) or text[start] != "[":
        return None
    label_end = text.find("]", start + 1)
    if label_end <= start + 1 or label_end + 1 >= len(text) or text[label_end + 1] != "(":
        return None
    depth = 1
    cursor = label_end + 2
    href_chars: list[str] = []
    while cursor < len(text):
        char = text[cursor]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor + 1, text[start + 1:label_end], "".join(href_chars)
        href_chars.append(char)
        cursor += 1
    return None


def _inline(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        link_start = text.find("[", cursor)
        if link_start < 0:
            parts.append(_inline_text(text[cursor:]))
            break
        parts.append(_inline_text(text[cursor:link_start]))
        parsed = _parse_markdown_link(text, link_start)
        if parsed is None:
            parts.append(_inline_text(text[link_start]))
            cursor = link_start + 1
            continue
        link_end, label, href = parsed
        safe_href = _safe_link_href(href)
        if safe_href:
            parts.append(f'<a href="{html.escape(safe_href, quote=True)}">{_inline_text(label)}</a>')
        else:
            parts.append(_inline_text(text[link_start:link_end]))
        cursor = link_end
    return "".join(parts)


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
    override = os.environ.get("YOUNG_STOCK_REPORT_TEMPLATE")
    if override and Path(override).expanduser().exists():
        return Path(override).expanduser().read_text(encoding="utf-8")
    return (
        resources.files("young_stock")
        .joinpath("templates/equity-report.html")
        .read_text(encoding="utf-8")
    )


def _parse_identity_from_path(path: Path) -> ReportIdentity | None:
    match = re.match(r"^(?P<trade_date>\d{8})-(?P<session>早盘|午间|盘中|盘后)-(?P<topic>.+)\.md$", path.name)
    if not match:
        return None
    return ReportIdentity(match.group("trade_date"), match.group("session"), match.group("topic"))


def _report_title(markdown: str, trade_date: str) -> str:
    title_match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    return title_match.group(1).strip() if title_match else f"{trade_date} 投资复盘报告"


def _report_topic(markdown: str, fallback: str = "A股投资日报") -> str:
    title = re.sub(r"\s+", "", _report_title(markdown, "")).strip("：:-—")
    if title in {"", "复盘", "深度复盘"}:
        return "A股深度复盘"
    if "日报" in title:
        return "A股投资日报"
    return title or fallback


def _load_related_evidence(markdown_path: Path) -> dict[str, Any] | None:
    candidates = []
    if markdown_path.stem in {"replay", "report"}:
        candidates.append(markdown_path.with_name("evidence.json"))
    candidates.append(markdown_path.with_name(f"{markdown_path.stem}-evidence.json"))
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _resolve_requested_markdown_path(artifacts: ReportArtifacts, trade_date: str, markdown_path: Path | str) -> Path:
    candidate = Path(markdown_path).expanduser()
    if candidate.suffix.lower() != ".md":
        raise ValueError("markdown_path 必须指向 .md Markdown 报告文件。")
    if not candidate.exists():
        raise ValueError(f"Markdown 不存在: {candidate}")
    candidate = candidate.resolve()
    report_dir = artifacts.directory.resolve()
    if candidate.parent != report_dir:
        raise ValueError(f"Markdown 必须位于 {trade_date} 报告目录下: {report_dir}")
    return candidate


def _canonicalize_markdown(
    artifacts: ReportArtifacts,
    trade_date: str,
    markdown_path: Path,
    markdown: str,
    *,
    now: datetime | None = None,
) -> tuple[Path, str]:
    identity = _parse_identity_from_path(markdown_path)
    evidence = _load_related_evidence(markdown_path)
    cleaned = sanitize_public_report(markdown, evidence)
    session = identity.session if identity else report_session(trade_date, now)
    topic = identity.topic if identity else _report_topic(cleaned)
    canonical = artifacts.write_report_markdown(ReportIdentity(trade_date, session, topic), cleaned)
    return canonical, cleaned


def _clean_document_html(document: str) -> str:
    return document


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
            "当前环境未检测到 PDF 渲染能力。请先运行 `young init` 检查安装状态；"
            "若仍缺少依赖，uv tool 用户请执行 `uv tool install --force 'young-stock-cli'`，"
            "普通 Python 环境请执行 `python3 -m pip install --upgrade young-stock-cli`。"
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
            order=None,
        )
    return stream.getvalue()


def export_report_pdf(
    trade_date: str,
    *,
    core: Any = None,
    profile: dict[str, Any] | None = None,
    markdown_path: Path | str | None = None,
    daily_markdown_factory: Callable[[], str] | None = None,
    render: Callable[[Path, Path], None] | None = None,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    artifacts = ReportArtifacts(trade_date)
    markdown_path = (
        _resolve_requested_markdown_path(artifacts, trade_date, markdown_path)
        if markdown_path is not None
        else ReportArtifacts.latest_markdown(trade_date)
    )
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
        markdown_path = artifacts.write_report_markdown(
            ReportIdentity(trade_date, report_session(trade_date, now), "A股投资日报"),
            sanitize_public_report(markdown),
        )
    markdown = markdown_path.read_text(encoding="utf-8")
    markdown_path, markdown = _canonicalize_markdown(artifacts, trade_date, markdown_path, markdown, now=now)
    body = markdown_to_html(markdown)
    title = _report_title(markdown, trade_date)
    document = _clean_document_html(
        _template_text()
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{DATE}}", trade_date)
        .replace("{{BODY}}", body)
    )
    output_name = markdown_path.stem
    html_path = artifacts.path(output_name, "html")
    html_path.write_text(document, encoding="utf-8")
    pdf_path = artifacts.path(output_name, "pdf")
    (render or _default_render)(html_path, pdf_path)
    return markdown_path, pdf_path
