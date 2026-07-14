import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from young_stock.cli import cli
from young_stock.llm import LLMClient, LLMNotConfigured


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def response(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=str(payload), headers={})


def test_openai_compatible_chat_requires_explicit_base_url():
    client = LLMClient({"provider": "openai-compatible", "model": "custom-model", "api_key": "secret"})

    with pytest.raises(LLMNotConfigured, match="Base URL"):
        client.chat([{"role": "user", "content": "hi"}])


def test_openai_compatible_chat_uses_custom_base_without_relabeling_provider():
    session = FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})])
    client = LLMClient(
        {
            "provider": "openai-compatible",
            "model": "custom-model",
            "api_base": "https://compat.example/v1",
            "api_key": "secret",
        },
        session=session,
    )

    result = client.chat([{"role": "user", "content": "hi"}])

    assert result.provider == "openai-compatible"
    assert session.calls[0][0] == "https://compat.example/v1/chat/completions"


def test_cli_openai_compatible_requires_base_url_and_model(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    missing_base = runner.invoke(cli, ["config", "models", "--provider", "openai-compatible", "--model", "custom-model"])
    missing_model = runner.invoke(cli, ["config", "models", "--provider", "openai-compatible", "--api-base", "https://compat.example/v1"])

    assert missing_base.exit_code != 0
    assert "Base URL" in missing_base.output
    assert missing_model.exit_code != 0
    assert "model" in missing_model.output


def test_cli_openai_compatible_persists_provider_id_and_masks_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    result = CliRunner().invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "openai-compatible",
            "--model",
            "custom-model",
            "--api-base",
            "https://compat.example/v1",
            "--api-key",
            "super-secret",
        ],
    )

    assert result.exit_code == 0
    assert "super-secret" not in result.output
    llm = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["llm"]
    assert llm["provider"] == "openai-compatible"
    assert llm["api_base"] == "https://compat.example/v1"
    assert llm["model"] == "custom-model"
