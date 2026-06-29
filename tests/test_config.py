import json
import stat

import pytest

from young_stock.config import (
    ConfigError,
    add_feishu_channel,
    load_effective_config,
    load_config,
    mask_config,
    migrate_legacy_llm_api_key_fallback,
    normalize_api_base,
    save_config,
    update_llm_config,
)


def test_config_round_trip_uses_young_home(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    config = update_llm_config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="secret-value",
        api_base="https://api.deepseek.com",
    )

    assert config["schema_version"] == 1
    assert load_config()["llm"]["model"] == "deepseek-chat"
    assert json.loads((tmp_path / "config.json").read_text())["llm"]["api_key"] == "secret-value"
    assert stat.S_IMODE((tmp_path / "config.json").stat().st_mode) & 0o077 == 0


def test_model_and_api_base_round_trip_without_backend_url_migration(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_config({"llm": {"provider": "deepseek", "model": "old-model", "api_base": "https://old.example/v1"}})

    llm = load_config()["llm"]

    assert llm["model"] == "old-model"
    assert llm["api_base"] == "https://old.example/v1"
    assert "backend_url" not in llm


def test_config_persists_api_key_env_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", '  "env-secret"  ')

    config = update_llm_config(
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="MODEL_KEY",
    )

    assert config["llm"]["api_key_env"] == "MODEL_KEY"
    assert config["llm"]["api_key"] == "env-secret"
    assert load_config()["llm"]["api_key"] == "env-secret"


def test_config_normalizes_direct_api_key_before_persisting(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = update_llm_config(
        provider="deepseek",
        model="deepseek-chat",
        api_key='  "secret-value"  ',
        api_base="https://api.deepseek.com",
    )

    assert config["llm"]["api_key"] == "secret-value"
    assert load_config()["llm"]["api_key"] == "secret-value"


def test_config_normalizes_kimi_coding_vanity_api_base(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = update_llm_config(
        provider="openai",
        model="kimi-k6",
        api_key="secret-value",
        api_base="https://api.kimi.com/coding/",
    )

    assert normalize_api_base("openai", "https://api.kimi.com/coding/") == "https://api.kimi.com/coding/v1"
    assert config["llm"]["model"] == "kimi-for-coding"
    assert config["llm"]["api_base"] == "https://api.kimi.com/coding/v1"
    assert load_config()["llm"]["api_base"] == "https://api.kimi.com/coding/v1"


def test_update_llm_config_preserves_existing_values_when_model_only_changes(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", "env-secret")
    save_config(
        {
            "llm": {
                "provider": "deepseek",
                "model": "old-model",
                "api_key_env": "MODEL_KEY",
                "api_key": "saved-secret",
                "api_base": "https://api.deepseek.com",
                "timeout": 45,
                "max_tokens": 8192,
            }
        }
    )

    config = update_llm_config(model="new-model")

    assert config["llm"]["model"] == "new-model"
    assert config["llm"]["api_key_env"] == "MODEL_KEY"
    assert config["llm"]["api_key"] == "saved-secret"
    assert config["llm"]["api_base"] == "https://api.deepseek.com"
    assert config["llm"]["timeout"] == 45
    assert config["llm"]["max_tokens"] == 8192


def test_update_llm_config_normalizes_and_persists_fallback_models(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = update_llm_config(
        provider="deepseek",
        model="primary-model",
        fallback_models=["fallback-a", " ", "primary-model", "fallback-a", "fallback-b"],
    )

    assert config["llm"]["fallback_models"] == ["fallback-a", "fallback-b"]
    assert load_config()["llm"]["fallback_models"] == ["fallback-a", "fallback-b"]


def test_update_llm_config_preserves_existing_fallback_models_when_model_only_changes(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_config(
        {
            "llm": {
                "provider": "deepseek",
                "model": "old-model",
                "fallback_models": ["fallback-a", "fallback-b"],
            }
        }
    )

    config = update_llm_config(model="new-model")

    assert config["llm"]["model"] == "new-model"
    assert config["llm"]["fallback_models"] == ["fallback-a", "fallback-b"]


def test_migrate_legacy_llm_api_key_fallback_persists_normalized_key(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", '  "env-secret"  ')
    save_config({"llm": {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "MODEL_KEY"}})

    migrated = migrate_legacy_llm_api_key_fallback()

    assert migrated is True
    assert load_config()["llm"]["api_key"] == "env-secret"


def test_migrate_legacy_llm_api_key_fallback_skips_when_env_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_config({"llm": {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "MODEL_KEY"}})

    migrated = migrate_legacy_llm_api_key_fallback()

    assert migrated is False
    assert "api_key" not in load_config()["llm"]


def test_load_effective_config_hydrates_env_secret_without_persisting(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", '  "env-secret"  ')
    save_config({"llm": {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "MODEL_KEY"}})

    effective = load_effective_config(strict=False)

    assert effective["llm"]["api_key"] == "env-secret"
    assert "api_key" not in load_config(strict=False)["llm"]


def test_config_masks_secrets_and_webhook_tokens():
    masked = mask_config(
        {
            "llm": {"api_key": "abcdefghi"},
            "channels": {
                "feishu": {
                    "work": {
                        "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/token-value",
                        "app_secret": "app-secret",
                    }
                }
            },
        }
    )

    assert masked["llm"]["api_key"] != "abcdefghi"
    assert "token-value" not in masked["channels"]["feishu"]["work"]["webhook"]
    assert masked["channels"]["feishu"]["work"]["app_secret"] != "app-secret"


def test_mask_config_keeps_list_structure_for_fallback_models():
    masked = mask_config({"llm": {"fallback_models": ["model-a", "model-b"], "api_key": "abcdefghi"}})

    assert masked["llm"]["fallback_models"] == ["model-a", "model-b"]
    assert masked["llm"]["api_key"] != "abcdefghi"


def test_invalid_config_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(ConfigError, match="config.json"):
        load_config(strict=True)

    assert load_config(strict=False)["schema_version"] == 1


def test_save_config_is_atomic_and_keeps_required_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_config({"channels": {"feishu": {}}})

    stored = load_config()
    assert stored["schema_version"] == 1
    assert stored["llm"] == {}
    assert stored["chat"] == {}
    assert not list(tmp_path.glob("*.tmp"))


def test_chat_config_section_round_trips(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    save_config({"chat": {"style": "buffett"}})

    assert load_config()["chat"]["style"] == "buffett"
    assert load_config()["chat"]["analysis_framework"] == "buffett"


def test_chat_analysis_framework_migrates_to_synchronized_style(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    save_config({"chat": {"analysis_framework": "munger", "style": "buffett"}})

    chat = load_config()["chat"]
    assert chat["style"] == "munger"
    assert chat["analysis_framework"] == "munger"


def test_feishu_channel_accepts_preissued_tenant_token(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = add_feishu_channel(
        "token-app",
        {"tenant_access_token": "token", "receive_id": "chat", "receive_id_type": "chat_id"},
    )

    assert config["channels"]["feishu"]["token-app"]["tenant_access_token"] == "token"


def test_feishu_channel_round_trips_app_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = add_feishu_channel(
        "work",
        {
            "app_id": "cli_a1",
            "app_secret": "secret-123",
            "receive_id": "oc_test_chat",
            "receive_id_type": "chat_id",
        },
    )

    channel = config["channels"]["feishu"]["work"]
    assert channel["app_id"] == "cli_a1"
    assert channel["app_secret"] == "secret-123"
    assert load_config()["channels"]["feishu"]["work"]["receive_id"] == "oc_test_chat"
