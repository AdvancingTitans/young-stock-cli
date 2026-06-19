"""Rich interactive chat with Click-backed slash commands."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Callable

from click.testing import CliRunner
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from .config import load_config
from .llm import LLMClient, LLMError
from .local_store import load_store, now_label, save_store

CHAT_MEMORY_STORE = "chat_memory"
CHAT_MEMORY_LABELS = {
    "investment": "投资记忆",
    "persona": "人格/角色设定",
    "preferences": "其他长期偏好",
}
_EXPLICIT_MEMORY_HINTS = ("记住", "记一下", "别忘了", "以后", "下次", "长期", "默认")
_INVESTMENT_HINTS = (
    "持有",
    "仓位",
    "买入",
    "定投",
    "成本",
    "止盈",
    "止损",
    "股票",
    "基金",
    "etf",
    "a股",
    "港股",
    "美股",
    "关注",
)
_PERSONA_HINTS = ("扮演", "角色", "你是", "请叫我", "叫我", "助手", "教练", "顾问", "分析师")
_PREFERENCE_HINTS = (
    "偏好",
    "喜欢",
    "希望",
    "尽量",
    "默认",
    "请用",
    "回答",
    "回复",
    "简洁",
    "中文",
    "不要",
    "别",
    "避免",
    "先给",
)


def _empty_long_term_memory() -> dict[str, list[dict[str, str]]]:
    return {kind: [] for kind in CHAT_MEMORY_LABELS}


def load_long_term_memory() -> dict[str, list[dict[str, str]]]:
    raw = load_store(CHAT_MEMORY_STORE, {})
    data = _empty_long_term_memory()
    for kind in CHAT_MEMORY_LABELS:
        items = raw.get(kind, []) if isinstance(raw, dict) else []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            content = _clean_memory_text(str(item.get("content", "")))
            if not content:
                continue
            data[kind].append(
                {
                    "content": content,
                    "updated_at": str(item.get("updated_at") or ""),
                }
            )
    return data


def save_long_term_memory(data: dict[str, list[dict[str, str]]]) -> None:
    save_store(CHAT_MEMORY_STORE, data)


def clear_long_term_memory_store(kind: str | None = None) -> dict[str, list[dict[str, str]]]:
    data = load_long_term_memory()
    if kind and kind in CHAT_MEMORY_LABELS:
        data[kind] = []
    else:
        data = _empty_long_term_memory()
    save_long_term_memory(data)
    return data


def format_long_term_memory_for_cli(data: dict[str, list[dict[str, str]]]) -> str:
    lines = []
    for kind, label in CHAT_MEMORY_LABELS.items():
        notes = [item["content"] for item in data.get(kind, []) if item.get("content")]
        lines.append(f"{label}: {'; '.join(notes) if notes else '-'}")
    return "\n".join(lines)


def _format_long_term_memory_for_prompt(data: dict[str, list[dict[str, str]]]) -> str:
    lines = []
    for kind, label in CHAT_MEMORY_LABELS.items():
        notes = [item["content"] for item in data.get(kind, []) if item.get("content")]
        if notes:
            lines.append(f"- {label}: {'；'.join(notes[-4:])}")
    if not lines:
        return ""
    return "\n".join(
        [
            "长期用户记忆（仅在相关时使用；这是提炼后的长期信息，不是完整聊天原文）：",
            *lines,
        ]
    )


def _clean_memory_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ，,。；;：:")


def _normalize_memory_key(text: str) -> str:
    return re.sub(r"\s+", "", _clean_memory_text(text)).lower()


def _strip_memory_prefix(text: str) -> str:
    cleaned = _clean_memory_text(text)
    cleaned = re.sub(r"^(请)?(帮我)?(记住|记一下|别忘了)[：:\s]*", "", cleaned)
    if cleaned.startswith("以后请"):
        return _clean_memory_text("请" + cleaned[3:])
    if cleaned.startswith("以后"):
        return _clean_memory_text(cleaned[2:])
    return cleaned


def _classify_memory(text: str, cleaned: str) -> str | None:
    lowered = text.lower()
    explicit = any(hint in text for hint in _EXPLICIT_MEMORY_HINTS)
    if any(hint in text for hint in _PERSONA_HINTS):
        return "persona"
    if any(hint in text for hint in _PREFERENCE_HINTS):
        return "preferences"
    if any(hint in lowered for hint in _INVESTMENT_HINTS) or re.search(r"\b[A-Z]{1,5}\b|\b\d{6}\b", text):
        return "investment"
    if explicit and cleaned:
        return "preferences"
    return None


def _extract_long_term_memories(text: str) -> list[tuple[str, str]]:
    notes: list[tuple[str, str]] = []
    for chunk in re.split(r"[。！？；\n]+", text):
        original = chunk.strip()
        if not original:
            continue
        cleaned = _strip_memory_prefix(original)
        if not cleaned:
            continue
        kind = _classify_memory(original, cleaned)
        if kind:
            notes.append((kind, cleaned))
    return notes


def _upsert_long_term_memory(
    data: dict[str, list[dict[str, str]]],
    kind: str,
    content: str,
) -> bool:
    items = data.setdefault(kind, [])
    key = _normalize_memory_key(content)
    timestamp = now_label()
    for item in items:
        if _normalize_memory_key(item.get("content", "")) == key:
            item["content"] = content
            item["updated_at"] = timestamp
            return False
    items.append({"content": content, "updated_at": timestamp})
    del items[:-12]
    return True


def slash_to_args(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped.startswith("/"):
        raise ValueError("slash command must start with /")
    return shlex.split(stripped[1:])


@dataclass
class ChatSession:
    max_turns: int = 5
    output: Callable[[str], None] | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    long_term_memory: dict[str, list[dict[str, str]]] = field(default_factory=load_long_term_memory)

    def __post_init__(self) -> None:
        self.console = Console()
        if self.output is None:
            self.output = self.console.print
        self.long_term_memory = load_long_term_memory()

    def remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content[-8000:]})
        self.history = self.history[-(self.max_turns * 2):]

    def capture_long_term_memory(self, text: str) -> int:
        updates = 0
        for kind, content in _extract_long_term_memories(text):
            updates += int(_upsert_long_term_memory(self.long_term_memory, kind, content))
        if updates:
            save_long_term_memory(self.long_term_memory)
        return updates

    def _build_messages(self) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": "你是 young-stock-cli 助手。未提供 Evidence Pack 时不要编造实时行情；引导用户使用 slash 命令取数。",
            }
        ]
        long_term = _format_long_term_memory_for_prompt(self.long_term_memory)
        if long_term:
            messages.append({"role": "system", "content": long_term})
        messages.extend(self.history)
        return messages

    def handle_slash(self, text: str) -> bool:
        args = slash_to_args(text)
        if not args:
            return False
        if args[0] in {"exit", "quit"}:
            return True
        if args[0] == "clear":
            self.history.clear()
            self.output("对话上下文已清空。")
            return False
        if args[0] == "help":
            self.output(
                "使用任意现有命令：/a、/stock 600519、/daily、/profile list、/memory show、/memory clear、/report、/send；/exit 退出。"
            )
            return False
        if args[0] == "chat":
            self.output("chat 模式中不能再次启动 /chat。")
            return False
        if args[0] == "daily-llm":
            args = ["replay", *args[1:]]
        self.remember("user", text)
        command_output = self._invoke_click(args)
        if args and args[0] == "memory":
            self.long_term_memory = load_long_term_memory()
        if command_output:
            self.remember("assistant", command_output)
        return False

    def _invoke_click(self, args: list[str]) -> str:
        from .cli import cli

        result = CliRunner().invoke(cli, args, color=False)
        text_output = result.output.rstrip()
        if text_output:
            self.output(text_output)
        if result.exception and not text_output:
            self.output(str(result.exception))
            return str(result.exception)
        return text_output

    def handle_message(self, text: str) -> None:
        self.capture_long_term_memory(text)
        self.remember("user", text)
        config = load_config(strict=False).get("llm", {})
        try:
            response = LLMClient(config).chat(self._build_messages())
        except LLMError as exc:
            self.output(str(exc))
            return
        self.remember("assistant", response.content)
        if self.output == self.console.print:
            self.console.print(Markdown(response.content))
        else:
            self.output(response.content)


def run_chat() -> None:
    console = Console()
    session = ChatSession()
    console.print("[bold #1B365D]young chat[/] — 输入 /help 查看命令，/exit 退出。")
    while True:
        try:
            text = Prompt.ask("[bold cyan]young[/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见。")
            return
        if not text:
            continue
        if text.startswith("/"):
            if session.handle_slash(text):
                return
        else:
            session.handle_message(text)
