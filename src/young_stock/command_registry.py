"""Shared command descriptors for CLI/chat-facing command surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SlashCommandDescriptor:
    name: str
    usage: str
    source: Literal["click", "chat"]
    execution_kind: Literal["local", "interactive", "remote-mutation"]
    prompt_visible: bool = True
    help_visible: bool = True


SLASH_COMMANDS: tuple[SlashCommandDescriptor, ...] = (
    SlashCommandDescriptor("a", "a", "click", "local"),
    SlashCommandDescriptor("stock", "stock <symbol> [--llm] [--lens ...]", "click", "local"),
    SlashCommandDescriptor("fund", "fund <code> [--llm] [--lens ...]", "click", "local"),
    SlashCommandDescriptor("news", "news <query>", "click", "local"),
    SlashCommandDescriptor("daily", "daily [--llm] [--lens ...]", "click", "local"),
    SlashCommandDescriptor("report", "report（仅导出 PDF）", "click", "local", prompt_visible=False),
    SlashCommandDescriptor("report", "report (PDF export only)", "click", "local", help_visible=False),
    SlashCommandDescriptor("send", "send [--dry-run|--yes] [--channel <name>]", "click", "remote-mutation"),
    SlashCommandDescriptor("profile", "profile list", "click", "local"),
    SlashCommandDescriptor("memory", "memory show", "click", "local"),
    SlashCommandDescriptor("memory", "memory clear", "click", "local"),
    SlashCommandDescriptor("style", "style", "chat", "interactive"),
    SlashCommandDescriptor("style", "style list", "chat", "interactive"),
    SlashCommandDescriptor("style", "style set <name>", "chat", "interactive"),
    SlashCommandDescriptor("style", "style show", "chat", "interactive"),
    SlashCommandDescriptor("style", "style clear", "chat", "interactive"),
    SlashCommandDescriptor("diagnose", "diagnose", "click", "local"),
    SlashCommandDescriptor("help", "help", "chat", "interactive"),
    SlashCommandDescriptor("clear", "clear", "chat", "interactive"),
    SlashCommandDescriptor("exit", "exit", "chat", "interactive"),
)


def authoritative_slash_help() -> str:
    visible = [f"/{command.usage}" for command in SLASH_COMMANDS if command.help_visible]
    return "可用命令：" + "、".join(visible) + "。"


def supported_slash_for_prompt() -> str:
    visible = [f"/{command.usage}" for command in SLASH_COMMANDS if command.prompt_visible]
    return ", ".join(visible)


def click_slash_roots() -> set[str]:
    return {command.name for command in SLASH_COMMANDS if command.source == "click"}
