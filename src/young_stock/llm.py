"""Small dependency-free LLM provider adapters built on requests."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

PROVIDER_BASES = {
    "openai": "https://api.openai.com/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "kimi": "https://api.moonshot.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


class LLMError(RuntimeError):
    """Provider request failed."""


class LLMNotConfigured(LLMError):
    """No usable provider/model was configured."""


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    def __init__(self, config: dict[str, Any], *, session: Any = None):
        self.config = dict(config or {})
        self.session = session or requests.Session()

    def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        provider = str(self.config.get("provider") or "").lower()
        model = str(self.config.get("model") or "")
        if not provider or not model:
            raise LLMNotConfigured("未配置 LLM，请运行 `young config llm --help`。")
        api_base = str(self.config.get("api_base") or PROVIDER_BASES.get(provider) or "").rstrip("/")
        if not api_base:
            raise LLMNotConfigured(f"provider {provider} 缺少 api_base")
        api_key = self._api_key()
        if provider != "ollama" and not api_key:
            raise LLMNotConfigured("未配置 LLM API key；建议使用 api_key_env。")
        if provider == "anthropic":
            return self._anthropic(api_base, api_key, model, messages)
        return self._openai_compatible(api_base, api_key, provider, model, messages)

    def list_models(self) -> list[str]:
        provider = str(self.config.get("provider") or "").lower()
        if not provider:
            raise LLMNotConfigured("未指定 provider，请使用 `young config models --provider ...`。")
        api_base = str(self.config.get("api_base") or PROVIDER_BASES.get(provider) or "").rstrip("/")
        if not api_base:
            raise LLMNotConfigured(f"provider {provider} 缺少 api_base")
        api_key = self._api_key()
        if provider != "ollama" and not api_key:
            raise LLMNotConfigured("未配置 LLM API key；建议使用 api_key_env。")
        headers = {"Accept": "application/json"}
        if provider == "anthropic":
            headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = self._get(f"{api_base}/models", headers=headers)
        data = response.json()
        rows = data.get("data") or data.get("models") or []
        models = []
        for item in rows:
            model_id = (item.get("id") or item.get("name")) if isinstance(item, dict) else item
            if model_id:
                models.append(str(model_id))
        return sorted(dict.fromkeys(models))

    def _api_key(self) -> str:
        env_name = str(self.config.get("api_key_env") or "")
        if env_name and os.environ.get(env_name):
            return str(os.environ[env_name])
        return str(self.config.get("api_key") or "")

    def _post(self, url: str, **kwargs: Any) -> Any:
        timeout = float(self.config.get("timeout") or 60)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.post(url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise LLMError(f"LLM 网络请求失败: {exc.__class__.__name__}") from exc
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(0.2 * (attempt + 1))
                continue
            if response.status_code in {401, 403}:
                raise LLMError("LLM 认证失败，请检查 API key 和 provider 配置。")
            if response.status_code >= 400:
                raise LLMError(f"LLM 请求失败（HTTP {response.status_code}）")
            return response
        raise LLMError(f"LLM 网络请求失败: {last_error.__class__.__name__ if last_error else 'unknown'}")

    def _get(self, url: str, **kwargs: Any) -> Any:
        timeout = float(self.config.get("timeout") or 60)
        try:
            response = self.session.get(url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise LLMError(f"模型列表请求失败: {exc.__class__.__name__}") from exc
        if response.status_code in {401, 403}:
            raise LLMError("模型列表认证失败，请检查 API key、provider 和 api_base。")
        if response.status_code >= 400:
            raise LLMError(f"模型列表请求失败（HTTP {response.status_code}）")
        return response

    def _openai_compatible(
        self,
        api_base: str,
        api_key: str,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if self.config.get("max_tokens"):
            payload["max_tokens"] = int(self.config["max_tokens"])
        response = self._post(f"{api_base}/chat/completions", headers=headers, json=payload)
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM 返回内容为空或格式异常。") from exc
        if not str(content).strip():
            raise LLMError("LLM 返回内容为空或格式异常。")
        return LLMResponse(str(content), provider, model, dict(data.get("usage") or {}), data)

    def _anthropic(
        self,
        api_base: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        system = "\n\n".join(item["content"] for item in messages if item.get("role") == "system")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [item for item in messages if item.get("role") != "system"],
            "max_tokens": int(self.config.get("max_tokens") or 4000),
        }
        if system:
            payload["system"] = system
        response = self._post(
            f"{api_base}/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
        )
        data = response.json()
        content = "".join(
            str(item.get("text") or "") for item in data.get("content", []) if item.get("type") == "text"
        ).strip()
        if not content:
            raise LLMError("LLM 返回内容为空或格式异常。")
        return LLMResponse(content, "anthropic", model, dict(data.get("usage") or {}), data)
