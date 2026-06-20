"""Configurable neutral bridge for optional online research."""

from __future__ import annotations

import os
import re
import shlex
import subprocess

RESEARCH_COMMAND_ENV = "YOUNG_STOCK_RESEARCH_COMMAND"


def research_bridge_hint() -> str:
    return (
        "未配置可选联网研究桥。若需在底层补充财报、公告和新闻摘录，"
        f"请设置 {RESEARCH_COMMAND_ENV}。"
    )


def compact_research_output(text: str, max_chars: int = 2200) -> str:
    lines = [line.strip() for line in text.splitlines()]
    interesting = []
    for line in lines:
        if not line or line in {"{", "}", "[", "]"}:
            continue
        lowered = line.lower()
        if "http" in lowered or line.startswith(("title:", "url:", "id:")):
            continue
        if re.search(r"\d", line) or any(token in line for token in ("财报", "公告", "新闻", "营收", "利润", "风险", "指引")):
            interesting.append(line)
    if not interesting:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact[:max_chars]
    chunks: list[str] = []
    total = 0
    for line in interesting:
        snippet = line[:220]
        if total + len(snippet) + 1 > max_chars:
            break
        chunks.append(snippet)
        total += len(snippet) + 1
    return "\n".join(chunks)


def _command_parts(query: str) -> list[str] | None:
    raw = os.environ.get(RESEARCH_COMMAND_ENV, "").strip()
    if not raw:
        return None
    parts = shlex.split(raw)
    if not parts:
        return None
    if any(part == "{query}" for part in parts):
        return [query if part == "{query}" else part for part in parts]
    return [*parts, query]


def run_research_bridge(query: str, *, timeout: float = 20.0) -> dict[str, str]:
    command = _command_parts(query)
    if not command:
        return {"_unavailable": research_bridge_hint()}
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        return {
            "_unavailable": (
                "可选联网研究桥命令不存在。"
                f"请检查 {RESEARCH_COMMAND_ENV} 是否指向当前环境可执行命令。"
            )
        }
    except (subprocess.SubprocessError, ValueError) as exc:
        return {
            "_unavailable": (
                "可选联网研究桥执行失败。"
                f"请检查 {RESEARCH_COMMAND_ENV} 配置。详细信息：{exc}"
            )
        }
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        detail = output or f"exit={result.returncode}"
        return {
            "_unavailable": (
                "可选联网研究桥执行失败。"
                f"请检查 {RESEARCH_COMMAND_ENV} 配置。详细信息：{detail}"
            )
        }
    summary = compact_research_output(output)
    if not summary:
        return {"_unavailable": "可选联网研究桥未返回可提炼内容。请调整查询或桥接命令。"}
    return {"summary_material": summary, "_source": "configured research bridge"}
