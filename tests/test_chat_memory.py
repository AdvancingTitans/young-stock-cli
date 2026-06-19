from click.testing import CliRunner

import young_stock.chat as chat_module
from young_stock.chat import ChatSession
from young_stock.cli import cli
from young_stock.config import save_config
from young_stock.local_store import load_store


def test_chat_long_term_memory_persists_across_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    session = ChatSession(output=lambda _: None)

    assert session.capture_long_term_memory("记住：我持有 600519，偏长期持有。") == 1
    assert session.capture_long_term_memory("以后请扮演我的价值投资研究助手。") == 1
    assert session.capture_long_term_memory("回答尽量简洁，默认中文。") == 1

    stored = load_store("chat_memory", {})
    assert [item["content"] for item in stored["investment"]] == ["我持有 600519，偏长期持有"]
    assert [item["content"] for item in stored["persona"]] == ["请扮演我的价值投资研究助手"]
    assert [item["content"] for item in stored["preferences"]] == ["回答尽量简洁，默认中文"]

    reloaded = ChatSession(output=lambda _: None)
    assert [item["content"] for item in reloaded.long_term_memory["investment"]] == ["我持有 600519，偏长期持有"]
    assert [item["content"] for item in reloaded.long_term_memory["persona"]] == ["请扮演我的价值投资研究助手"]
    assert [item["content"] for item in reloaded.long_term_memory["preferences"]] == ["回答尽量简洁，默认中文"]


def test_chat_handle_message_injects_memory_summary_and_keeps_short_history(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    captured_messages = []
    save_config({"chat": {"style": "munger"}})

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def chat(self, messages):
            captured_messages.append(messages)
            return type("Response", (), {"content": "收到"})()

    monkeypatch.setattr(chat_module, "LLMClient", DummyClient)

    session = ChatSession(max_turns=2, output=lambda _: None)
    session.capture_long_term_memory("记住：我持有 600519。")
    session.capture_long_term_memory("以后请扮演我的价值投资研究助手。")
    session.capture_long_term_memory("回答尽量简洁，默认中文。")
    for index in range(4):
        session.remember("user", f"u{index}")
        session.remember("assistant", f"a{index}")

    session.handle_message("请继续")

    messages = captured_messages[0]
    combined = "\n".join(message["content"] for message in messages)
    assert "长期用户记忆" in combined
    assert "投资记忆" in combined
    assert "人格/角色设定" in combined
    assert "其他长期偏好" in combined
    assert "不要编造 /market、/trend" in messages[0]["content"]
    assert "风格与长期记忆都服从本安全规则" in messages[0]["content"]
    assert "当前对话风格与分析框架：munger" in messages[1]["content"]
    assert "第一人称口吻" in messages[1]["content"]
    assert "自称时自然用“我”" in messages[1]["content"]
    assert "长期用户记忆" in messages[2]["content"]
    assert "u0" not in combined
    assert "a0" not in combined
    assert "u2" not in combined
    assert "a3" in combined
    assert "u3" in combined
    assert messages[-1]["content"] == "请继续"


def test_memory_cli_clear_supports_partial_and_full_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    session = ChatSession(output=lambda _: None)
    session.capture_long_term_memory("记住：我持有 600519。")
    session.capture_long_term_memory("以后请扮演我的价值投资研究助手。")
    session.capture_long_term_memory("回答尽量简洁，默认中文。")

    runner = CliRunner()
    persona_result = runner.invoke(cli, ["memory", "clear", "--kind", "persona"])
    assert persona_result.exit_code == 0
    assert "persona" in persona_result.output
    data = load_store("chat_memory", {})
    assert data["investment"]
    assert data["persona"] == []
    assert data["preferences"]

    reset_result = runner.invoke(cli, ["memory", "reset"])
    assert reset_result.exit_code == 0
    data = load_store("chat_memory", {})
    assert data["investment"] == []
    assert data["persona"] == []
    assert data["preferences"] == []
