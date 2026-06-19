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

from .config import load_config, save_config
from .llm import LLMClient, LLMError
from .local_store import load_store, now_label, save_store

CHAT_MEMORY_STORE = "chat_memory"
DEFAULT_CHAT_STYLE = "balanced"
CHAT_MEMORY_LABELS = {
    "investment": "投资记忆",
    "persona": "人格/角色设定",
    "preferences": "其他长期偏好",
}
CHAT_STYLE_PROMPTS = {
    "balanced": {
        "label": "balanced",
        "summary": "先事实、再判断，平衡基本面、估值、风险、催化剂与反例。",
        "prompt": (
            "当前分析框架：balanced。先区分已验证事实、推断、未知项；"
            "同时看业务/资产质量、估值、风险、催化剂与反例；给概率化结论和后续核验点。"
        ),
    },
    "buffett": {
        "label": "buffett",
        "summary": "重商业质量、护城河、管理层、资本配置与安全边际。",
        "prompt": (
            "当前分析框架：buffett。强调可理解的业务、长期竞争优势、管理层质量、资本配置、"
            "自由现金流与安全边际；避免把短期波动包装成长期价值。"
        ),
    },
    "munger": {
        "label": "munger",
        "summary": "用多元思维模型、反向思考、激励与错配检查。",
        "prompt": (
            "当前分析框架：munger。使用多元思维模型与反向思考，重点检查激励、错配、"
            "机会成本、行为偏差与可避免的重大错误。"
        ),
    },
    "graham": {
        "label": "graham",
        "summary": "重资产负债表、盈利稳定性、估值纪律与下行保护。",
        "prompt": (
            "当前分析框架：graham。优先看资产负债表、盈利稳定性、估值纪律与下行保护；"
            "对证据不足的成长叙事保持克制。"
        ),
    },
    "dalio": {
        "label": "dalio",
        "summary": "重宏观周期、情景分析、分散化与风险平衡。",
        "prompt": (
            "当前分析框架：dalio。优先识别宏观周期、流动性与政策环境，做情景分析、"
            "相关性检查与分散化/风险平衡讨论。"
        ),
    },
}
READ_ONLY_SLASH_HELP = (
    "可用命令：/a、/stock <symbol>、/fund <code>、/news <query>、/daily [flags]、/report、"
    "/profile list、/memory show、/memory clear、/style、/style list、/style set <name>、"
    "/style show、/style clear、/diagnose、/help、/clear、/exit。"
)
SUPPORTED_SLASH_FOR_PROMPT = (
    "/a, /stock <symbol>, /fund <code>, /news <query>, /daily [flags], /report, "
    "/profile list, /memory show, /memory clear, /style, /style list, /style set <name>, "
    "/style show, /style clear, /diagnose, /help, /clear, /exit"
)
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


def _normalize_style_name(name: str | None) -> str:
    key = str(name or "").strip().lower()
    return key if key in CHAT_STYLE_PROMPTS else DEFAULT_CHAT_STYLE


def _load_chat_style_name() -> str:
    return _normalize_style_name(load_config(strict=False).get("chat", {}).get("style"))


def _save_chat_style_name(name: str | None) -> str:
    config = load_config(strict=False)
    chat_config = config.setdefault("chat", {})
    if name is None:
        chat_config.pop("style", None)
    else:
        chat_config["style"] = _normalize_style_name(name)
    save_config(config)
    return _load_chat_style_name()


def _format_style_options() -> str:
    return "、".join(CHAT_STYLE_PROMPTS)


def _style_summary(name: str) -> str:
    profile = CHAT_STYLE_PROMPTS[_normalize_style_name(name)]
    return f"{profile['label']}: {profile['summary']}"


def _build_style_prompt(name: str) -> str:
    return (
        f"{CHAT_STYLE_PROMPTS[_normalize_style_name(name)]['prompt']} "
        "风格仅是分析框架，不冒充人物，不输出确定性投资建议。"
    )


@dataclass
class ChatSession:
    max_turns: int = 5
    output: Callable[[str], None] | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    long_term_memory: dict[str, list[dict[str, str]]] = field(default_factory=load_long_term_memory)
    style_name: str = field(default_factory=_load_chat_style_name)

    def __post_init__(self) -> None:
        self.console = Console()
        if self.output is None:
            self.output = self.console.print
        self.long_term_memory = load_long_term_memory()
        self.style_name = _load_chat_style_name()

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
                "content": (
                    "你是 young-stock-cli 助手。硬性规则："
                    f"1) 只允许建议这些 slash 命令：{SUPPORTED_SLASH_FOR_PROMPT}；"
                    "不要编造 /market、/trend 或其他命令。"
                    "2) 未提供 Evidence Pack 时，不得编造实时行情、涨跌幅、资金流、新闻细节或结论。"
                    "3) 用户问“今天市场怎么样”“大盘如何”等泛问题时，优先引导 /a 或 /daily。"
                    "4) 风格与长期记忆都服从本安全规则。"
                ),
            }
        ]
        messages.append({"role": "system", "content": _build_style_prompt(self.style_name)})
        long_term = _format_long_term_memory_for_prompt(self.long_term_memory)
        if long_term:
            messages.append({"role": "system", "content": long_term})
        messages.extend(self.history)
        return messages

    def _emit(self, message: str) -> None:
        self.output(message)

    def _show_authoritative_help(self, prefix: str | None = None) -> None:
        message = READ_ONLY_SLASH_HELP if prefix is None else f"{prefix}\n{READ_ONLY_SLASH_HELP}"
        self._emit(message)

    def _handle_style_slash(self, args: list[str]) -> bool:
        action = args[1] if len(args) > 1 else "show"
        if action == "list":
            self._emit("可选风格：" + "；".join(_style_summary(name) for name in CHAT_STYLE_PROMPTS))
            return False
        if action == "show":
            self._emit(f"当前风格：{_style_summary(self.style_name)}")
            return False
        if action == "clear":
            self.style_name = _save_chat_style_name(None)
            self._emit(f"已清除自定义风格，当前风格：{self.style_name}（默认）。")
            return False
        if action == "set":
            if len(args) < 3:
                self._emit(f"用法：/style set <name>。可选：{_format_style_options()}")
                return False
            candidate = args[2]
            if candidate.strip().lower() not in CHAT_STYLE_PROMPTS:
                self._emit(f"未知风格：{candidate}。可选：{_format_style_options()}")
                return False
            self.style_name = _save_chat_style_name(candidate)
            self._emit(f"已设置风格：{_style_summary(self.style_name)}")
            return False
        self._emit("用法：/style、/style list、/style set <name>、/style show、/style clear")
        return False

    def _resolve_click_args(self, args: list[str]) -> tuple[list[str] | None, str | None]:
        root = args[0]
        if root in {"a", "stock", "fund", "news", "daily", "report", "diagnose"}:
            return args, None
        if root == "profile":
            if len(args) >= 2 and args[1] in {"list", "show"}:
                return args, None
            return None, "chat 中仅支持只读的 /profile list。"
        if root == "memory":
            if len(args) >= 2 and args[1] in {"show", "list"}:
                return ["memory", "show"], None
            if len(args) >= 2 and args[1] == "clear":
                return args, None
            return None, "chat 中仅支持 /memory show 和 /memory clear。"
        if root in {"daily-llm", "replay"}:
            return ["daily", "--llm", *args[1:]], "提示：/daily-llm 和 /replay 已弃用，请改用 /daily --llm。"
        if root in {"send", "config", "update", "uninstall"}:
            return None, f"chat 中禁止 /{root}，请在终端直接运行对应 CLI。"
        return None, f"不支持 /{root}。请输入 /help 查看 authoritative 命令列表。"

    def handle_slash(self, text: str) -> bool:
        args = slash_to_args(text)
        if not args:
            return False
        if args[0] in {"exit", "quit"}:
            return True
        if args[0] == "clear":
            self.history.clear()
            self._emit("对话上下文已清空。")
            return False
        if args[0] == "help":
            self._show_authoritative_help()
            return False
        if args[0] == "chat":
            self._emit("chat 模式中不能再次启动 /chat。")
            return False
        if args[0] == "style":
            return self._handle_style_slash(args)
        routed_args, notice = self._resolve_click_args(args)
        if routed_args is None:
            self._show_authoritative_help(notice)
            return False
        if notice:
            self._emit(notice)
        self.remember("user", text)
        command_output = self._invoke_click(routed_args)
        if routed_args and routed_args[0] == "memory":
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
    console.print(
        "[bold #1B365D]young chat[/] — 输入 /help 查看命令，/exit 退出。"
        f"\n可选风格：{_format_style_options()}；当前风格：{session.style_name}。"
    )
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
