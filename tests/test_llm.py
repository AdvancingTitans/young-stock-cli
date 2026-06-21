from types import SimpleNamespace

import pytest
import requests

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

    def get(self, url, **kwargs):
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


def non_json_response(status, text):
    def raise_json():
        raise ValueError("not json")

    return SimpleNamespace(
        status_code=status,
        json=raise_json,
        text=text,
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
    assert kwargs["timeout"] == (10.0, 60.0)
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


def test_saved_api_key_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("MODEL_KEY", "env-secret")
    session = FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": '  "saved-secret"  ',
            "api_key_env": "MODEL_KEY",
        },
        session=session,
    )

    client.chat([{"role": "user", "content": "hi"}])

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer saved-secret"


def test_api_key_falls_back_to_saved_secret_when_env_missing(monkeypatch):
    monkeypatch.delenv("MODEL_KEY", raising=False)
    session = FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "saved-secret",
            "api_key_env": "MODEL_KEY",
        },
        session=session,
    )

    client.chat([{"role": "user", "content": "hi"}])

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer saved-secret"


def test_api_key_env_falls_back_when_saved_secret_missing(monkeypatch):
    monkeypatch.setenv("MODEL_KEY", "  'env-secret'  ")
    session = FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key_env": "MODEL_KEY",
        },
        session=session,
    )

    client.chat([{"role": "user", "content": "hi"}])

    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer env-secret"


def test_openai_compatible_model_discovery():
    session = FakeSession(
        [
            response(
                200,
                {
                    "data": [
                        {"id": "doubao-seed-1-6-250615"},
                        {"id": "kimi-k2-0711-preview"},
                    ]
                },
            )
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "placeholder",
            "api_key": "secret",
            "api_base": "https://example.test/v1",
        },
        session=session,
    )

    models = client.list_models()

    assert models == ["doubao-seed-1-6-250615", "kimi-k2-0711-preview"]
    assert session.calls[0][0] == "https://example.test/v1/models"


def test_list_models_http_200_non_json_is_safely_wrapped():
    session = FakeSession([non_json_response(200, "prompt=不要泄露这个 prompt api_key=secret")])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "placeholder",
            "api_key": "secret",
            "api_base": "https://example.test/v1",
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.list_models()

    text = str(exc.value)
    assert "非 JSON" in text
    assert "prompt" not in text
    assert "secret" not in text


@pytest.mark.parametrize("payload", [["model-a"], {"data": {"id": "model-a"}}, {"items": ["model-a"]}])
def test_list_models_malformed_shape_is_safely_wrapped(payload):
    session = FakeSession([response(200, payload)])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "placeholder",
            "api_key": "secret",
            "api_base": "https://example.test/v1",
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.list_models()

    assert "格式异常" in str(exc.value)


def test_missing_configuration_and_auth_errors_are_clear():
    with pytest.raises(LLMNotConfigured, match="young config models --help"):
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


def test_auth_error_points_to_unified_models_help_without_leaking_secret():
    session = FakeSession(
        [response(401, {"error": {"message": "The API key format is incorrect.", "type": "Unauthorized"}})]
    )
    client = LLMClient(
        {
            "provider": "ark",
            "model": "doubao-seed-1-6",
            "api_key": "ark-secret",
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.list_models()

    text = str(exc.value)
    assert "API key format is incorrect" in text
    assert "young config models --help" in text
    assert "young config models --provider" not in text
    assert "ark-secret" not in text


def test_chat_uses_split_connect_and_read_timeouts_and_retries_read_timeout(monkeypatch):
    sleeps = []
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: sleeps.append(seconds))
    session = FakeSession(
        [
            requests.ReadTimeout("slow response"),
            response(200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "secret",
            "timeout": 30,
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "分析"}])

    assert result.content == "ok"
    assert len(session.calls) == 2
    timeout = session.calls[0][1]["timeout"]
    assert isinstance(timeout, tuple)
    assert len(timeout) == 2
    assert timeout[0] < timeout[1]
    assert timeout[1] >= 30
    assert sleeps == [0.2]


def test_read_timeout_error_is_actionable_and_sanitized(monkeypatch):
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: None)
    session = FakeSession([requests.ReadTimeout("slow response")] * 3)
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "super-secret",
            "timeout": 30,
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.chat([{"role": "user", "content": "不要泄露这个 prompt"}])

    text = str(exc.value)
    assert "super-secret" not in text
    assert "不要泄露这个 prompt" not in text
    assert "timeout" in text.lower()
    assert "young config path" in text


def test_non_transient_request_errors_fail_without_retry():
    session = FakeSession([requests.exceptions.InvalidSchema("bad schema")])
    client = LLMClient(
        {
            "provider": "openai",
            "model": "gpt-test",
            "api_key": "secret",
        },
        session=session,
    )

    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])

    assert len(session.calls) == 1


def test_rate_limit_exhausts_primary_retries_then_falls_back(monkeypatch):
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: None)
    session = FakeSession(
        [
            response(429, {"error": {"message": "rate limit exceeded"}}),
            response(429, {"error": {"message": "rate limit exceeded"}}),
            response(429, {"error": {"message": "rate limit exceeded"}}),
            response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "hi"}])

    assert result.content == "fallback ok"
    assert result.model == "fallback-model"
    assert result.provider == "openai"
    assert [call[1]["json"]["model"] for call in session.calls] == [
        "primary-model",
        "primary-model",
        "primary-model",
        "fallback-model",
    ]


def test_timeout_exhausts_primary_retries_then_falls_back(monkeypatch):
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: None)
    session = FakeSession(
        [
            requests.ReadTimeout("slow response"),
            requests.ReadTimeout("slow response"),
            requests.ReadTimeout("slow response"),
            response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "hi"}])

    assert result.content == "fallback ok"
    assert result.model == "fallback-model"
    assert [call[1]["json"]["model"] for call in session.calls] == [
        "primary-model",
        "primary-model",
        "primary-model",
        "fallback-model",
    ]


def test_auth_error_does_not_fallback():
    session = FakeSession(
        [
            response(401, {"error": {"message": "bad secret"}}),
            response(200, {"choices": [{"message": {"content": "should not happen"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    with pytest.raises(LLMError, match="认证"):
        client.chat([{"role": "user", "content": "hi"}])

    assert [call[1]["json"]["model"] for call in session.calls] == ["primary-model"]


def test_ark_generic_404_fails_with_actionable_hint_and_no_fallback():
    session = FakeSession(
        [
            response(404, {"message": "Not Found"}),
            response(200, {"choices": [{"message": {"content": "should not happen"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "ark",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.chat([{"role": "user", "content": "hi"}])

    text = str(exc.value)
    assert "api_base" in text
    assert "young config models --list" in text
    assert [call[1]["json"]["model"] for call in session.calls] == ["primary-model"]


def test_model_not_found_404_uses_fallback(monkeypatch):
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: None)
    session = FakeSession(
        [
            response(404, {"error": {"message": "The model `primary-model` does not exist"}}),
            response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "ark",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "hi"}])

    assert result.content == "fallback ok"
    assert result.model == "fallback-model"
    assert [call[1]["json"]["model"] for call in session.calls] == ["primary-model", "fallback-model"]


@pytest.mark.parametrize("status_code", [400, 422])
def test_model_not_found_detail_on_non_auth_4xx_uses_fallback(monkeypatch, status_code):
    monkeypatch.setattr("young_stock.llm.time.sleep", lambda seconds: None)
    session = FakeSession(
        [
            response(status_code, {"error": {"message": "deployment not found"}}),
            response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "openai",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "hi"}])

    assert result.content == "fallback ok"
    assert result.model == "fallback-model"
    assert [call[1]["json"]["model"] for call in session.calls] == ["primary-model", "fallback-model"]


@pytest.mark.parametrize("provider,url", [("openai", "https://api.deepseek.com/chat/completions"), ("anthropic", "https://api.anthropic.com/v1/messages")])
def test_http_200_non_json_is_safely_wrapped_and_does_not_fallback(provider, url):
    session = FakeSession(
        [
            non_json_response(200, "prompt=不要泄露这个 prompt api_key=secret"),
            response(200, {"choices": [{"message": {"content": "fallback ok"}}]}),
        ]
    )
    client = LLMClient(
        {
            "provider": "deepseek" if provider == "openai" else "anthropic",
            "model": "primary-model",
            "fallback_models": ["fallback-model"],
            "api_key": "secret",
        },
        session=session,
    )

    with pytest.raises(LLMError) as exc:
        client.chat([{"role": "user", "content": "hi"}])

    text = str(exc.value)
    assert "secret" not in text
    assert "不要泄露这个 prompt" not in text
    assert "fallback-model" not in text
    assert len(session.calls) == 1
    assert session.calls[0][0] == url
