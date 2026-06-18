import json
import stat

import pytest

from young_stock.config import (
    ConfigError,
    add_feishu_channel,
    load_config,
    mask_config,
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
    assert not list(tmp_path.glob("*.tmp"))


def test_feishu_channel_accepts_preissued_tenant_token(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    config = add_feishu_channel(
        "token-app",
        {"tenant_access_token": "token", "receive_id": "chat", "receive_id_type": "chat_id"},
    )

    assert config["channels"]["feishu"]["token-app"]["tenant_access_token"] == "token"
