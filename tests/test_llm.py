from types import SimpleNamespace

import pytest

from young_stock.llm import LLMClient, LLMError, LLMNotConfigured


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(status, payload):
    return SimpleNamespace(
        status_code=status,
        json=lambda: payload,
        text=str(payload),
        headers={},
    )


def test_openai_compatible_provider_maps_messages(monkeypatch):
    session = FakeSession(
        [
            response(
                200,
                {
                    "choices": [{"message": {"content": "复盘完成"}}],
                    "usage": {"total_tokens": 42},
                },
            )
        ]
    )
    client = LLMClient(
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key": "secret",
            "timeout": 12,
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "分析"}])

    url, kwargs = session.calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert kwargs["json"]["model"] == "deepseek-chat"
    assert kwargs["timeout"] == 12
    assert result.content == "复盘完成"
    assert result.usage["total_tokens"] == 42


def test_anthropic_provider_maps_response():
    session = FakeSession(
        [response(200, {"content": [{"type": "text", "text": "谨慎看多"}], "usage": {"input_tokens": 3}})]
    )
    client = LLMClient(
        {"provider": "anthropic", "model": "claude-test", "api_key": "secret"},
        session=session,
    )

    result = client.chat(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "分析"},
        ]
    )

    url, kwargs = session.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert kwargs["json"]["system"] == "system"
    assert result.content == "谨慎看多"


def test_api_key_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("MODEL_KEY", "env-secret")
    session = FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "inline-secret",
            "api_key_env": "MODEL_KEY",
        },
        session=session,
    )

    client.chat([{"role": "user", "content": "hi"}])

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer env-secret"


def test_missing_configuration_and_auth_errors_are_clear():
    with pytest.raises(LLMNotConfigured, match="未配置 LLM"):
        LLMClient({}).chat([{"role": "user", "content": "hi"}])

    session = FakeSession([response(401, {"error": {"message": "bad secret"}})])
    client = LLMClient(
        {"provider": "openai", "model": "gpt-test", "api_key": "super-secret"},
        session=session,
    )
    with pytest.raises(LLMError) as exc:
        client.chat([{"role": "user", "content": "hi"}])
    assert "super-secret" not in str(exc.value)
    assert "认证" in str(exc.value)
