from types import SimpleNamespace

from young_stock.llm import LLMClient


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def response(status, payload):
    return SimpleNamespace(status_code=status, json=lambda: payload, text=str(payload), headers={})


def test_model_listing_accepts_models_container_and_top_level_modalities():
    session = FakeSession(
        [
            response(
                200,
                {
                    "models": [
                        {"id": "text-a", "input_modalities": ["text"], "output_modalities": ["text"]},
                        {"id": "image-out", "input_modalities": ["text"], "output_modalities": ["image"]},
                        {"id": "audio-only", "modalities": ["audio"]},
                        {"name": "text-b", "modalities": ["text"]},
                    ]
                },
            )
        ]
    )
    client = LLMClient(
        {
            "provider": "openrouter",
            "model": "placeholder",
            "api_key": "secret",
        },
        session=session,
    )

    models = client.list_models()

    assert models == ["text-a", "text-b"]
    assert session.calls[0][0] == "https://openrouter.ai/api/v1/models"


def test_model_listing_uses_provider_default_api_key_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-secret")
    session = FakeSession([response(200, {"data": [{"id": "llama-text"}]})])
    client = LLMClient({"provider": "groq", "model": "placeholder"}, session=session)

    assert client.list_models() == ["llama-text"]
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer env-secret"
