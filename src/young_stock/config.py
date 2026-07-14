"""Versioned configuration for LLMs and delivery channels."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .local_store import young_home

DEFAULT_CONFIG: dict[str, Any] = {"schema_version": 2, "llm": {}, "channels": {"feishu": {}}, "chat": {}}
SECRET_KEYS = {"api_key", "app_secret", "tenant_access_token"}


class ConfigError(ValueError):
    """Raised when the user configuration is invalid."""


def config_path() -> Path:
    return young_home() / "config.json"


def normalize_api_key(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    return text


def normalize_api_base(provider: Any, value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    parsed = urlsplit(text)
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    # ponytail: hard-code only Kimi Coding Plan's documented third-party-agent
    # endpoint; if Kimi adds more vanity paths, replace this with a provider map.
    if host == "api.kimi.com" and path == "/coding":
        return "https://api.kimi.com/coding/v1"
    return text


def is_kimi_coding_api_base(value: Any) -> bool:
    parsed = urlsplit(str(value or "").strip().rstrip("/"))
    return parsed.netloc.lower() == "api.kimi.com" and parsed.path.rstrip("/") == "/coding/v1"


def normalize_model_id(provider: Any, api_base: Any, value: Any) -> str:
    model = str(value or "").strip()
    if is_kimi_coding_api_base(api_base):
        return "kimi-for-coding"
    return model


def kimi_coding_plan_unsupported_message() -> str:
    return (
        "Kimi Coding Plan 仅支持 Kimi Code CLI、Claude Code、Roo Code 等 Coding Agents；"
        "young daily / young chat / young analyze 属于投研与问答工作流，不能使用该 endpoint。"
        "请改用 Kimi OpenPlatform 通用 API 或其他 OpenAI-compatible 模型。"
    )


def normalize_fallback_models(value: Any, primary_model: Any = None) -> list[str]:
    primary = str(primary_model or "").strip()
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        items = [value]
    else:
        items = list(value)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        model_id = str(item or "").strip()
        if not model_id or model_id == primary or model_id in seen:
            continue
        seen.add(model_id)
        normalized.append(model_id)
    return normalized


def _with_defaults(data: dict[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(data, dict):
        return result
    result.update({key: value for key, value in data.items() if key not in {"llm", "channels", "chat"}})
    result["schema_version"] = 2
    result["llm"] = dict(data.get("llm") or {})
    if result["llm"]:
        result["llm"].setdefault("transport", "api")
    channels = data.get("channels") or {}
    result["channels"] = dict(channels) if isinstance(channels, dict) else {}
    result["channels"].setdefault("feishu", {})
    chat = data.get("chat") or {}
    result["chat"] = dict(chat) if isinstance(chat, dict) else {}
    chat_style = result["chat"].get("style")
    framework = result["chat"].get("analysis_framework")
    if framework is not None:
        result["chat"]["style"] = framework
    elif chat_style is not None:
        result["chat"]["analysis_framework"] = chat_style
    return result


def load_config(*, strict: bool = True) -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise ConfigError(f"无法读取 {path}: {exc}") from exc
        return copy.deepcopy(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        if strict:
            raise ConfigError(f"{path} 顶层必须是 JSON object")
        return copy.deepcopy(DEFAULT_CONFIG)
    return _with_defaults(raw)


def load_effective_config(*, strict: bool = True) -> dict[str, Any]:
    config = load_config(strict=strict)
    llm = config.setdefault("llm", {})
    env_name = str(llm.get("api_key_env") or "").strip()
    if env_name and not normalize_api_key(llm.get("api_key")):
        resolved = normalize_api_key(os.environ.get(env_name))
        if resolved:
            llm["api_key"] = resolved
    return config


def save_config(data: dict[str, Any]) -> dict[str, Any]:
    normalized = _with_defaults(data)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temp_name, 0o600)
        Path(temp_name).replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()
    return normalized


def update_llm_config(**values: Any) -> dict[str, Any]:
    config = load_config(strict=False)
    llm = config.setdefault("llm", {})
    env_name = str(values.get("api_key_env") or "").strip()
    if env_name and values.get("api_key") is None:
        resolved = os.environ.get(env_name)
        if resolved:
            values["api_key"] = normalize_api_key(resolved)
    explicit_fallback_models = "fallback_models" in values and values.get("fallback_models") is not None
    for key, value in values.items():
        if value is not None:
            if key == "api_key":
                normalized = normalize_api_key(value)
                if normalized:
                    llm[key] = normalized
            elif key == "model":
                normalized = normalize_model_id(
                    values.get("provider") or llm.get("provider"),
                    values.get("api_base") or llm.get("api_base"),
                    value,
                )
                if normalized:
                    llm[key] = normalized
            elif key == "fallback_models":
                llm[key] = normalize_fallback_models(value, values.get("model") or llm.get("model"))
            elif key == "api_key_env":
                env_value = str(value).strip()
                if env_value:
                    llm[key] = env_value
            elif key == "api_base":
                normalized = normalize_api_base(values.get("provider") or llm.get("provider"), value)
                if normalized:
                    llm[key] = normalized
            else:
                llm[key] = value
    if explicit_fallback_models and not llm.get("fallback_models"):
        llm.pop("fallback_models", None)
    if is_kimi_coding_api_base(llm.get("api_base")) and llm.get("model"):
        llm["model"] = "kimi-for-coding"
    return save_config(config)


def migrate_legacy_llm_api_key_fallback() -> bool:
    config = load_config(strict=False)
    llm = config.get("llm") or {}
    env_name = str(llm.get("api_key_env") or "").strip()
    if not env_name or normalize_api_key(llm.get("api_key")):
        return False
    resolved = normalize_api_key(os.environ.get(env_name))
    if not resolved:
        return False
    config.setdefault("llm", {})["api_key"] = resolved
    save_config(config)
    return True


def mask_secret(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 4:
        return "****"
    return f"{text[:2]}***{text[-2:]}"


def _mask_webhook(value: str) -> str:
    parsed = urlsplit(value)
    path_parts = parsed.path.rstrip("/").split("/")
    if path_parts:
        path_parts[-1] = "***"
    return urlunsplit((parsed.scheme, parsed.netloc, "/".join(path_parts), "", ""))


def mask_config(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {item_key: mask_config(item, item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [mask_config(item, key) for item in value]
    if key in SECRET_KEYS:
        return mask_secret(value)
    if key == "webhook" and value:
        return _mask_webhook(str(value))
    return value


def add_feishu_channel(name: str, channel: dict[str, Any]) -> dict[str, Any]:
    config = load_config(strict=False)
    config.setdefault("channels", {}).setdefault("feishu", {})[name] = {
        key: value for key, value in channel.items() if value not in (None, "")
    }
    return save_config(config)


def remove_feishu_channel(name: str) -> bool:
    config = load_config(strict=False)
    channels = config.setdefault("channels", {}).setdefault("feishu", {})
    existed = name in channels
    channels.pop(name, None)
    save_config(config)
    return existed
