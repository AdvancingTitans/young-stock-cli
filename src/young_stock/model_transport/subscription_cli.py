"""Local subscription CLI model transport."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Callable

from ..llm import LLMError, LLMNotConfigured, LLMResponse


@dataclass(frozen=True)
class SubscriptionCliSpec:
    provider_id: str
    display_name: str
    executable_names: tuple[str, ...]
    version_args: tuple[str, ...]
    build_run_args: Callable[[str, str | None], list[str]]
    help_args: tuple[str, ...] = ("--help",)


def _codex_args(executable: str, model: str | None) -> list[str]:
    args = [
        executable,
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--ignore-rules",
        "-",
    ]
    if model:
        args[2:2] = ["--model", model]
    return args


def _claude_args(executable: str, model: str | None) -> list[str]:
    args = [
        executable,
        "--print",
        "--input-format",
        "text",
        "--output-format",
        "text",
        "--no-session-persistence",
        "--safe-mode",
        "--tools",
        "",
    ]
    if model:
        args.extend(["--model", model])
    return args


_SPECS: tuple[SubscriptionCliSpec, ...] = (
    SubscriptionCliSpec("codex", "Codex CLI", ("codex",), ("--version",), _codex_args),
    SubscriptionCliSpec("claude", "Claude Code", ("claude",), ("--version",), _claude_args),
)
_SPEC_BY_ID = {spec.provider_id: spec for spec in _SPECS}

_LOGIN_HINTS = (
    "not logged in",
    "login",
    "log in",
    "auth",
    "unauthorized",
    "authentication",
    "api key",
    "未登录",
    "认证",
)


def subscription_cli_provider_ids() -> tuple[str, ...]:
    return tuple(spec.provider_id for spec in _SPECS)


def subscription_cli_specs() -> tuple[SubscriptionCliSpec, ...]:
    return _SPECS


def subscription_cli_spec(provider_id: object) -> SubscriptionCliSpec | None:
    return _SPEC_BY_ID.get(str(provider_id or "").strip().lower())


class SubscriptionCliTransport:
    transport_id = "subscription-cli"

    def __init__(self, config: dict[str, Any]):
        self.config = dict(config or {})
        self.provider = str(self.config.get("provider") or "").strip().lower()
        self.model = str(self.config.get("model") or "").strip()

    def list_models(self, *, verify_chat: bool = False) -> list[str]:
        del verify_chat
        raise LLMError("subscription-cli transport 不支持远端模型列表查询；请在本机 CLI 中确认可用模型。")

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        spec, executable = self._resolve_cli()
        timeout = self._timeout()
        prompt = self._prompt(messages)
        with tempfile.TemporaryDirectory(prefix="young-model-") as temp_dir:
            args = spec.build_run_args(executable, self.model or None)
            if spec.provider_id == "codex":
                args[-1:-1] = ["-C", temp_dir]
            result = self._run(args, prompt, timeout=timeout, cwd=temp_dir)
            stdout = (result.stdout or "").strip()
            stderr = self._sanitize(result.stderr, temp_dir=temp_dir)
            if result.returncode != 0:
                if self._looks_like_login_error(stderr):
                    raise LLMNotConfigured(
                        f"{spec.display_name} 登录状态不可用；请先在本机完成 CLI 登录。stderr: {stderr}"
                    )
                detail = f" stderr: {stderr}" if stderr else ""
                raise LLMError(f"{spec.display_name} 调用失败（exit code {result.returncode}）。{detail}")
            if not stdout:
                detail = f" stderr: {stderr}" if stderr else ""
                raise LLMError(f"{spec.display_name} 返回内容为空。{detail}")
            return LLMResponse(
                stdout,
                spec.provider_id,
                self.model or spec.provider_id,
                {},
                {"stderr": stderr} if stderr else {},
                self.transport_id,
            )

    def _resolve_cli(self) -> tuple[SubscriptionCliSpec, str]:
        spec = subscription_cli_spec(self.provider)
        if spec is None:
            supported = ", ".join(subscription_cli_provider_ids())
            raise LLMNotConfigured(f"不支持的 subscription-cli provider: {self.provider or '-'}。可用: {supported}")
        executable = str(self.config.get("cli_executable") or "").strip()
        if executable and not os.path.exists(executable):
            raise LLMNotConfigured(f"{spec.display_name} 可执行文件不存在，无法验证。")
        if not executable:
            executable = next((path for name in spec.executable_names if (path := shutil.which(name))), "")
        if not executable:
            raise LLMNotConfigured(f"未安装 {spec.display_name}，或可执行文件不在 PATH 中。")
        self._verify_cli(spec, executable)
        return spec, executable

    def _verify_cli(self, spec: SubscriptionCliSpec, executable: str) -> None:
        for args in (spec.version_args, spec.help_args):
            result = subprocess.run(
                [executable, *args],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
            if result.returncode == 0 and (result.stdout or result.stderr).strip():
                return
        raise LLMNotConfigured(f"{spec.display_name} 可执行文件存在，但版本/help 信息无法验证。")

    def _timeout(self) -> float:
        try:
            timeout = float(self.config.get("timeout") or 120)
        except (TypeError, ValueError):
            timeout = 120.0
        return max(timeout, 1.0)

    def _prompt(self, messages: list[dict[str, str]]) -> str:
        parts = [
            "你是 young-stock-cli 的本机模型传输层，只能根据下方已经构造完成的 Evidence 和 Prompt 输出文本。",
            "不得读取用户项目、修改代码、执行 shell、调用仓库工具、抓取行情、修改 Profile，或请求高权限自动批准。",
        ]
        for item in messages:
            role = str(item.get("role") or "user").strip() or "user"
            content = str(item.get("content") or "")
            parts.append(f"\n[{role}]\n{content}")
        return "\n".join(parts).strip() + "\n"

    def _run(self, args: list[str], prompt: str, *, timeout: float, cwd: str) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_process_group(process)
            stdout, stderr = process.communicate()
            diagnostic = self._sanitize(stderr, temp_dir=cwd)
            detail = f" stderr: {diagnostic}" if diagnostic else ""
            raise LLMError(f"subscription-cli 模型调用超时（{int(timeout)} 秒），已终止进程组。{detail}") from exc
        return subprocess.CompletedProcess(args, process.returncode or 0, stdout, stderr)

    def _terminate_process_group(self, process: subprocess.Popen[str]) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError:
            process.terminate()

    def _sanitize(self, value: object, *, temp_dir: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        for secret_key in ("api_key", "Authorization", "authorization"):
            text = text.replace(secret_key, "[redacted]")
        api_key = str(self.config.get("api_key") or "").strip()
        if api_key:
            text = text.replace(api_key, "[redacted]")
        return text.replace(temp_dir, "<tempdir>")[:600]

    def _looks_like_login_error(self, stderr: str) -> bool:
        normalized = stderr.lower()
        return any(hint in normalized for hint in _LOGIN_HINTS)
