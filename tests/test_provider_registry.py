from young_stock.providers import provider_ids, provider_spec


def test_registry_contains_supported_api_providers():
    required = {
        "openai",
        "xai",
        "ark",
        "kimi",
        "moonshot",
        "deepseek",
        "qwen",
        "ollama",
        "anthropic",
        "siliconflow",
        "minimax",
        "openrouter",
        "groq",
        "together",
        "openai-compatible",
    }

    assert required.issubset(set(provider_ids()))


def test_provider_defaults_are_declared_in_one_place():
    deepseek = provider_spec("deepseek")
    anthropic = provider_spec("anthropic")
    compatible = provider_spec("openai-compatible")

    assert deepseek.display_name == "DeepSeek"
    assert deepseek.protocol == "openai-chat"
    assert deepseek.default_api_base == "https://api.deepseek.com"
    assert deepseek.default_api_key_env == "DEEPSEEK_API_KEY"
    assert deepseek.models_path == "/models"
    assert deepseek.models_response_containers == ("data", "models")
    assert deepseek.chat_path == "/chat/completions"
    assert deepseek.supports_model_probe is True
    assert anthropic.protocol == "anthropic-messages"
    assert anthropic.chat_path == "/messages"
    assert compatible.requires_explicit_base_url is True
    assert compatible.default_api_base == ""
