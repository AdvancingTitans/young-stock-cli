import pytest

import young_stock.chat as chat_module
from young_stock.chat import ChatSession, run_chat, slash_to_args
from young_stock.config import load_config
from young_stock.local_store import load_store, save_store


def test_slash_commands_map_to_click_arguments():
    assert slash_to_args("/a --no-news") == ["a", "--no-news"]
    assert slash_to_args('/profile group create "成长 型"') == ["profile", "group", "create", "成长 型"]
    assert slash_to_args("/daily --llm") == ["daily", "--llm"]
    assert slash_to_args("/daily-llm") == ["daily-llm"]


def test_chat_history_keeps_last_five_turns():
    session = ChatSession(max_turns=5)
    for index in range(7):
        session.remember("user", f"u{index}")
        session.remember("assistant", f"a{index}")

    assert len(session.history) == 10
    assert session.history[0]["content"] == "u2"


def test_chat_executes_existing_click_command():
    outputs = []
    session = ChatSession(output=outputs.append)
    exit_requested = session.handle_slash("/profile list")

    assert exit_requested is False
    assert any("Stocks:" in output for output in outputs)
    assert session.history[-2]["content"] == "/profile list"
    assert "Stocks:" in session.history[-1]["content"]


def test_chat_unknown_command_does_not_exit():
    outputs = []
    session = ChatSession(output=outputs.append)
    session._invoke_click = lambda args: (_ for _ in ()).throw(AssertionError(f"unexpected click call: {args}"))

    assert session.handle_slash("/not-real") is False
    assert any("/help" in output for output in outputs)
    assert any("authoritative" in output for output in outputs)


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("/send", "禁止 /send"),
        ("/config", "禁止 /config"),
        ("/update", "禁止 /update"),
        ("/uninstall", "禁止 /uninstall"),
        ("/profile add-stock 600519", "仅支持只读的 /profile list"),
        ("/memory reset", "仅支持 /memory show 和 /memory clear"),
    ],
)
def test_chat_blocks_write_or_mutating_slash_without_invoking_click(command, message):
    outputs = []
    session = ChatSession(output=outputs.append)
    session._invoke_click = lambda args: (_ for _ in ()).throw(AssertionError(f"unexpected click call: {args}"))

    assert session.handle_slash(command) is False
    assert any(message in output for output in outputs)


def test_chat_deprecated_aliases_route_to_daily_llm(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    calls = []
    monkeypatch.setattr(session, "_invoke_click", lambda args: calls.append(args) or "")

    assert session.handle_slash("/daily-llm") is False
    assert session.handle_slash("/replay --refresh") is False
    assert calls == [["daily", "--llm"], ["daily", "--llm", "--refresh"]]
    assert any("已弃用" in output for output in outputs)


def test_chat_memory_clear_slash_resets_persisted_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    save_store(
        "chat_memory",
        {
            "investment": [{"content": "我持有 600519"}],
            "persona": [{"content": "你是我的投研助手"}],
            "preferences": [{"content": "默认中文，回答简洁"}],
        },
    )
    outputs = []
    session = ChatSession(output=outputs.append)

    assert session.handle_slash("/memory clear") is False

    data = load_store("chat_memory", {})
    assert data["investment"] == []
    assert data["persona"] == []
    assert data["preferences"] == []
    assert any("已清空" in output for output in outputs)


def test_chat_style_slash_persists_across_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    outputs = []
    session = ChatSession(output=outputs.append)

    assert session.handle_slash("/style set buffett") is False
    assert load_config(strict=False)["chat"]["style"] == "buffett"
    assert any("已设置风格" in output for output in outputs)

    reloaded = ChatSession(output=lambda _: None)
    assert reloaded.style_name == "buffett"

    assert reloaded.handle_slash("/style clear") is False
    assert "style" not in load_config(strict=False)["chat"]
    assert ChatSession(output=lambda _: None).style_name == "balanced"


def test_run_chat_banner_shows_style_options(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    def raise_eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(chat_module.Prompt, "ask", raise_eof)

    run_chat()

    captured = capsys.readouterr().out
    assert "可选风格" in captured
    assert "balanced" in captured
    assert "当前风格" in captured
