from young_stock.chat import ChatSession, slash_to_args


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

    assert session.handle_slash("/not-real") is False
    assert any("No such command" in output for output in outputs)


def test_chat_daily_llm_alias_dispatches_replay(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    calls = []
    monkeypatch.setattr(session, "_invoke_click", lambda args: calls.append(args))

    assert session.handle_slash("/daily-llm") is False
    assert calls == [["replay"]]
