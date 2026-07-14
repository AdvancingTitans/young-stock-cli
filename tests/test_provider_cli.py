from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

from young_stock.cli import cli
from young_stock.llm import LLMClient, LLMError
from young_stock.model_transport.subscription_cli import subscription_cli_provider_ids
from young_stock.providers import provider_ids


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def response(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=str(payload), headers={})


def test_config_models_provider_choice_is_built_from_registry():
    command = cli.commands["config"].commands["models"]
    provider_option = next(param for param in command.params if param.name == "provider")

    assert isinstance(provider_option.type, click.Choice)
    assert tuple(provider_option.type.choices) == tuple(dict.fromkeys((*provider_ids(), *subscription_cli_provider_ids())))


def test_config_providers_lists_registry_without_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret")

    result = CliRunner().invoke(cli, ["config", "providers"])

    assert result.exit_code == 0
    assert "openai-compatible" in result.output
    assert "Anthropic" in result.output
    assert "anthropic-messages" in result.output
    assert "super-secret" not in result.output


def test_llm_errors_include_provider_display_name_without_secret():
    session = FakeSession([response(401, {"error": {"message": "bad key"}})])
    client = LLMClient({"provider": "groq", "model": "llama-test", "api_key": "super-secret"}, session=session)

    with pytest.raises(LLMError) as exc:
        client.chat([{"role": "user", "content": "hi"}])

    text = str(exc.value)
    assert "Groq" in text
    assert "super-secret" not in text
