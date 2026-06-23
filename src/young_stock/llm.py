"""Small dependency-free LLM provider adapters built on requests."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from .config import (
    is_kimi_coding_api_base,
    kimi_coding_plan_unsupported_message,
    normalize_api_base,
    normalize_api_key,
    normalize_fallback_models,
    normalize_model_id,
)

PROVIDER_BASES = {
    "openai": "https://api.openai.com/v1",
    "ark": "https://ark.cn-beijing.volces.com/api/v3",
    "kimi": "https://api.moonshot.ai/v1",
    "moonshot": "https://api.moonshot.ai/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


class LLMError(RuntimeError):
    """Provider request failed."""


class LLMNotConfigured(LLMError):
    """No usable provider/model was configured."""


class _LLMRequestFailure(LLMError):
    """Internal request failure with fallback classification."""

    def __init__(self, message: str, *, allow_model_fallback: bool = False):
        super().__init__(message)
        self.allow_model_fallback = allow_model_fallback


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
            raise LLMNotConfigured("未配置 LLM，请运行 `young config models --help`。")
        api_base = normalize_api_base(provider, self.config.get("api_base") or PROVIDER_BASES.get(provider) or "")
        if not api_base:
            raise LLMNotConfigured(f"provider {provider} 缺少 api_base；请运行 `young config models --help`。")
        if is_kimi_coding_api_base(api_base):
            raise LLMError(kimi_coding_plan_unsupported_message())
        model = normalize_model_id(provider, api_base, model)
        api_key = self._api_key()
        if provider != "ollama" and not api_key:
            raise LLMNotConfigured("未配置 LLM API key；请运行 `young config models --help`。")
        attempted_models: list[str] = []
        last_error: _LLMRequestFailure | None = None
        for index, candidate in enumerate(self._model_candidates(model)):
            attempted_models.append(candidate)
            try:
                if provider == "anthropic":
                    return self._anthropic(api_base, api_key, candidate, messages)
                return self._openai_compatible(api_base, api_key, provider, candidate, messages)
            except _LLMRequestFailure as exc:
                last_error = exc
                if exc.allow_model_fallback and index < len(self._model_candidates(model)) - 1:
                    continue
                break
        if last_error is not None:
            raise LLMError(self._final_error_message(str(last_error), attempted_models)) from None
        raise LLMError(self._final_error_message("LLM 请求失败。", attempted_models))

    def list_models(self) -> list[str]:
        provider = str(self.config.get("provider") or "").lower()
        if not provider:
            raise LLMNotConfigured("未指定 provider，请运行 `young config models --help`。")
        api_base = normalize_api_base(provider, self.config.get("api_base") or PROVIDER_BASES.get(provider) or "")
        if not api_base:
            raise LLMNotConfigured(f"provider {provider} 缺少 api_base；请运行 `young config models --help`。")
        api_key = self._api_key()
        if provider != "ollama" and not api_key:
            raise LLMNotConfigured("未配置 LLM API key；请运行 `young config models --help`。")
        headers = {"Accept": "application/json"}
        if provider == "anthropic":
            headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = self._get(f"{api_base}/models", headers=headers)
        try:
            data = response.json()
        except Exception as exc:
            raise LLMError("模型列表返回了非 JSON 响应，无法解析。") from exc
        if not isinstance(data, dict):
            raise LLMError("模型列表返回格式异常，无法解析可用模型 ID。")
        rows = data.get("data")
        if rows is None:
            rows = data.get("models")
        if rows is None or not isinstance(rows, list):
            raise LLMError("模型列表返回格式异常，无法解析可用模型 ID。")
        models = []
        for item in rows:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name")
            elif isinstance(item, str):
                model_id = item
            else:
                raise LLMError("模型列表返回格式异常，无法解析可用模型 ID。")
            if model_id:
                models.append(str(model_id))
        return sorted(dict.fromkeys(models))

    def _api_key(self) -> str:
        saved = normalize_api_key(self.config.get("api_key"))
        if saved:
            return saved
        env_name = str(self.config.get("api_key_env") or "").strip()
        if env_name and os.environ.get(env_name):
            return normalize_api_key(os.environ[env_name])
        return ""

    def _base_timeout(self) -> float:
        try:
            timeout = float(self.config.get("timeout") or 60)
        except (TypeError, ValueError):
            timeout = 60.0
        return max(timeout, 1.0)

    def _request_timeout(self, *, long_read: bool) -> tuple[float, float]:
        base = self._base_timeout()
        connect_timeout = max(1.0, min(base, 10.0))
        read_timeout = max(base * (3.0 if long_read else 1.0), 60.0 if long_read else 30.0)
        return (connect_timeout, read_timeout)

    def _model_candidates(self, primary_model: str) -> list[str]:
        return [primary_model, *normalize_fallback_models(self.config.get("fallback_models"), primary_model)]

    def _is_retryable_exception(self, exc: requests.RequestException) -> bool:
        if isinstance(exc, requests.Timeout):
            return True
        return isinstance(exc, requests.ConnectionError) and not isinstance(exc, requests.exceptions.SSLError)

    def _retry_delay(self, attempt: int) -> float:
        return 0.2 * (attempt + 1)

    def _request_error_message(self, surface: str, exc: requests.RequestException) -> str:
        error_name = exc.__class__.__name__
        if isinstance(exc, requests.ReadTimeout):
            return (
                f"{surface}生成超时（{error_name}）。请稍后重试；"
                "若长文本生成经常超时，可运行 `young config path` 打开配置文件并提高 llm.timeout。"
            )
        if isinstance(exc, requests.ConnectTimeout):
            return f"{surface}连接超时（{error_name}）。请检查网络、代理和 api_base 后重试。"
        if isinstance(exc, requests.ConnectionError):
            return f"{surface}网络连接失败（{error_name}）。请检查网络、代理和 api_base 后重试。"
        return f"{surface}请求配置或网络失败（{error_name}）。请检查 provider 与 api_base。"

    def _final_error_message(self, message: str, attempted_models: list[str]) -> str:
        if not attempted_models:
            return message
        return f"{message} 已尝试模型: {', '.join(attempted_models)}"

    def _is_model_not_found_detail(self, detail: str) -> bool:
        normalized = detail.lower()
        hints = (
            "model not found",
            "deployment not found",
            "unknown model",
            "no such model",
            "does not exist",
            "not available",
            "unavailable model",
        )
        return any(hint in normalized for hint in hints)

    def _is_quota_or_rate_limit_detail(self, detail: str) -> bool:
        normalized = detail.lower()
        hints = ("rate limit", "quota", "too many requests", "insufficient_quota")
        return any(hint in normalized for hint in hints)

    def _not_found_error_message(self, surface: str, provider: str, detail: str) -> str:
        base = f"{surface}请求失败（HTTP 404）。"
        if provider == "ark":
            base = (
                f"{base} 请检查 api_base，并运行 `young config models --list` 核对模型 ID。"
            )
        if detail:
            return f"{base} 服务端提示：{detail.strip()}"
        return base

    def _request(self, method: str, url: str, *, surface: str, long_read: bool, **kwargs: Any) -> Any:
        timeout = self._request_timeout(long_read=long_read)
        provider = str(self.config.get("provider") or "").lower()
        requester = getattr(self.session, method)
        for attempt in range(3):
            try:
                response = requester(url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                if self._is_retryable_exception(exc) and attempt < 2:
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise _LLMRequestFailure(
                    self._request_error_message(surface, exc),
                    allow_model_fallback=self._is_retryable_exception(exc),
                ) from exc
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(self._retry_delay(attempt))
                continue
            detail = self._error_detail(response) if response.status_code >= 400 else ""
            if response.status_code in {401, 403}:
                raise _LLMRequestFailure(self._auth_error_message(surface, provider, detail))
            if self._is_quota_or_rate_limit_detail(detail):
                raise _LLMRequestFailure(
                    f"{surface}服务暂时不可用（HTTP {response.status_code}），请稍后重试。",
                    allow_model_fallback=True,
                )
            if response.status_code in {408, 429, 500, 502, 503, 504}:
                raise _LLMRequestFailure(
                    f"{surface}服务暂时不可用（HTTP {response.status_code}），请稍后重试。",
                    allow_model_fallback=True,
                )
            if response.status_code in {400, 404, 422} and self._is_model_not_found_detail(detail):
                raise _LLMRequestFailure(
                    f"{surface}模型不存在或当前不可用。请运行 `young config models --list` 核对模型 ID。",
                    allow_model_fallback=True,
                )
            if response.status_code == 404:
                raise _LLMRequestFailure(self._not_found_error_message(surface, provider, detail))
            if response.status_code >= 400:
                raise _LLMRequestFailure(f"{surface}请求失败（HTTP {response.status_code}）")
            return response

    def _post(self, url: str, **kwargs: Any) -> Any:
        return self._request("post", url, surface="LLM", long_read=True, **kwargs)

    def _get(self, url: str, **kwargs: Any) -> Any:
        return self._request("get", url, surface="模型列表", long_read=False, **kwargs)

    def _error_detail(self, response: Any) -> str:
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("type") or error.get("code")
                if message:
                    return str(message)
            message = payload.get("message") or payload.get("detail") or payload.get("error_description")
            if message:
                return str(message)
        text = str(getattr(response, "text", "") or "").strip()
        return text[:160]

    def _response_json(self, response: Any, *, surface: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:
            raise LLMError(f"{surface}返回了非 JSON 响应，无法解析。") from exc
        if not isinstance(payload, dict):
            raise LLMError(f"{surface}返回了非 JSON 响应，无法解析。")
        return payload

    def _auth_error_message(self, surface: str, provider: str, detail: str) -> str:
        message = f"{surface}认证失败，请检查 API key、provider 和 api_base。"
        normalized = detail.strip()
        if normalized:
            message = f"{message} 服务端提示：{normalized}"
        if provider in {"ark", "openai"}:
            message = (
                f"{message} 请运行 `young config models --help` 检查配置方式，"
                "并用 README 中的 curl 示例核对可用模型 ID。"
            )
        return message

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
        data = self._response_json(response, surface="LLM")
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
        data = self._response_json(response, surface="LLM")
        content = "".join(
            str(item.get("text") or "") for item in data.get("content", []) if item.get("type") == "text"
        ).strip()
        if not content:
            raise LLMError("LLM 返回内容为空或格式异常。")
        return LLMResponse(content, "anthropic", model, dict(data.get("usage") or {}), data)
