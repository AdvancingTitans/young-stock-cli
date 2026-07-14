"""LLM API provider registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    display_name: str
    protocol: str
    default_api_base: str
    default_api_key_env: str
    models_path: str
    models_response_containers: tuple[str, ...]
    chat_path: str
    requires_explicit_base_url: bool = False
    supports_model_probe: bool = True
    requires_api_key: bool = True


_OPENAI_CHAT = "openai-chat"
_ANTHROPIC_MESSAGES = "anthropic-messages"


_PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "openai",
        "OpenAI",
        _OPENAI_CHAT,
        "https://api.openai.com/v1",
        "OPENAI_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "xai",
        "xAI",
        _OPENAI_CHAT,
        "https://api.x.ai/v1",
        "XAI_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "ark",
        "Ark",
        _OPENAI_CHAT,
        "https://ark.cn-beijing.volces.com/api/v3",
        "ARK_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "kimi",
        "Kimi",
        _OPENAI_CHAT,
        "https://api.moonshot.ai/v1",
        "KIMI_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "moonshot",
        "Moonshot",
        _OPENAI_CHAT,
        "https://api.moonshot.ai/v1",
        "MOONSHOT_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "deepseek",
        "DeepSeek",
        _OPENAI_CHAT,
        "https://api.deepseek.com",
        "DEEPSEEK_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "qwen",
        "Qwen",
        _OPENAI_CHAT,
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "DASHSCOPE_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "ollama",
        "Ollama",
        _OPENAI_CHAT,
        "http://localhost:11434/v1",
        "",
        "/models",
        ("data", "models"),
        "/chat/completions",
        requires_api_key=False,
    ),
    ProviderSpec(
        "anthropic",
        "Anthropic",
        _ANTHROPIC_MESSAGES,
        "https://api.anthropic.com/v1",
        "ANTHROPIC_API_KEY",
        "/models",
        ("data", "models"),
        "/messages",
        supports_model_probe=False,
    ),
    ProviderSpec(
        "siliconflow",
        "SiliconFlow",
        _OPENAI_CHAT,
        "https://api.siliconflow.cn/v1",
        "SILICONFLOW_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "minimax",
        "MiniMax",
        _OPENAI_CHAT,
        "https://api.minimax.io/v1",
        "MINIMAX_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "openrouter",
        "OpenRouter",
        _OPENAI_CHAT,
        "https://openrouter.ai/api/v1",
        "OPENROUTER_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "groq",
        "Groq",
        _OPENAI_CHAT,
        "https://api.groq.com/openai/v1",
        "GROQ_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "together",
        "Together AI",
        _OPENAI_CHAT,
        "https://api.together.xyz/v1",
        "TOGETHER_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
    ),
    ProviderSpec(
        "openai-compatible",
        "OpenAI-compatible",
        _OPENAI_CHAT,
        "",
        "OPENAI_COMPATIBLE_API_KEY",
        "/models",
        ("data", "models"),
        "/chat/completions",
        requires_explicit_base_url=True,
    ),
)

_PROVIDER_BY_ID = {spec.provider_id: spec for spec in _PROVIDERS}


def provider_ids() -> tuple[str, ...]:
    return tuple(spec.provider_id for spec in _PROVIDERS)


def provider_specs() -> tuple[ProviderSpec, ...]:
    return _PROVIDERS


def provider_spec(provider_id: object) -> ProviderSpec | None:
    return _PROVIDER_BY_ID.get(str(provider_id or "").strip().lower())


def default_api_base(provider_id: object) -> str:
    spec = provider_spec(provider_id)
    return spec.default_api_base if spec else ""
