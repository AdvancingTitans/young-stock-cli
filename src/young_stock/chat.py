"""Rich interactive chat with Click-backed slash commands."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Callable

from click.testing import CliRunner
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from .config import load_config
from .llm import LLMClient, LLMError


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

    def __post_init__(self) -> None:
        self.console = Console()
        if self.output is None:
            self.output = self.console.print

    def remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content[-8000:]})
        self.history = self.history[-(self.max_turns * 2):]

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
            self.output("使用任意现有命令：/a、/stock 600519、/daily、/profile list、/report、/send；/exit 退出。")
            return False
        if args[0] == "chat":
            self.output("chat 模式中不能再次启动 /chat。")
            return False
        if args[0] == "daily-llm":
            args = ["replay", *args[1:]]
        self.remember("user", text)
        command_output = self._invoke_click(args)
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
        self.remember("user", text)
        config = load_config(strict=False).get("llm", {})
        try:
            response = LLMClient(config).chat(
                [
                    {
                        "role": "system",
                        "content": "你是 young-stock-cli 助手。未提供 Evidence Pack 时不要编造实时行情；引导用户使用 slash 命令取数。",
                    },
                    *self.history,
                ]
            )
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
