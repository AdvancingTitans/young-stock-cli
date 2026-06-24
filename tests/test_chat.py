import pytest

import young_stock.chat as chat_module
from young_stock.chat import ChatSession, run_chat, slash_to_args
from young_stock.config import load_config
from young_stock.local_store import load_store, save_store


def test_slash_commands_map_to_click_arguments():
    assert slash_to_args("/a --no-news") == ["a", "--no-news"]
    assert slash_to_args("/profile list") == ["profile", "list"]
    assert slash_to_args("/daily --llm") == ["daily", "--llm"]


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
    assert "groups" not in session.history[-1]["content"]


def test_chat_allows_stock_slash(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    calls = []
    monkeypatch.setattr(session, "_invoke_click", lambda args, echo=True: calls.append((args, echo)) or "")

    assert session.handle_slash("/stock 600519 --llm") is False
    assert calls == [(["stock", "600519", "--llm"], True)]


def test_chat_allows_send_slash(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    calls = []
    monkeypatch.setattr(session, "_invoke_click", lambda args, echo=True: calls.append((args, echo)) or "")

    assert session.handle_slash("/send --channel feishu") is False
    assert calls == [(["send", "--channel", "feishu"], True)]


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
        ("/config", "禁止 /config"),
        ("/update", "禁止 /update"),
        ("/uninstall", "禁止 /uninstall"),
        ("/profile add-stock 600519", "仅支持只读的 /profile list"),
        ("/profile group add 成长型 600519", "仅支持只读的 /profile list"),
        ("/memory reset", "仅支持 /memory show 和 /memory clear"),
        ("/reach 贵州茅台", "不支持 /reach"),
    ],
)
def test_chat_blocks_write_or_mutating_slash_without_invoking_click(command, message):
    outputs = []
    session = ChatSession(output=outputs.append)
    session._invoke_click = lambda args: (_ for _ in ()).throw(AssertionError(f"unexpected click call: {args}"))

    assert session.handle_slash(command) is False
    assert any(message in output for output in outputs)


def test_chat_help_and_prompt_do_not_advertise_profile_group():
    assert "/profile group" not in chat_module.READ_ONLY_SLASH_HELP
    assert "/profile group" not in chat_module.SUPPORTED_SLASH_FOR_PROMPT
    assert "/analyze" not in chat_module.READ_ONLY_SLASH_HELP
    assert "/stock <symbol> [--llm] [--lens ...]" in chat_module.READ_ONLY_SLASH_HELP
    assert "/daily [--llm] [--lens ...]" in chat_module.READ_ONLY_SLASH_HELP
    assert "/analyze" not in chat_module.SUPPORTED_SLASH_FOR_PROMPT
    assert "/stock <symbol> [--llm] [--lens ...]" in chat_module.SUPPORTED_SLASH_FOR_PROMPT
    assert "/daily [--llm] [--lens ...]" in chat_module.SUPPORTED_SLASH_FOR_PROMPT


def test_chat_rejects_removed_daily_llm_aliases(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    monkeypatch.setattr(
        session,
        "_invoke_click",
        lambda args, echo=True: (_ for _ in ()).throw(AssertionError(f"unexpected click call: {args}")),
    )

    assert session.handle_slash("/daily-llm") is False
    assert session.handle_slash("/replay --refresh") is False
    assert any("不支持 /daily-llm" in output for output in outputs)
    assert any("不支持 /replay" in output for output in outputs)


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
    assert load_config(strict=False)["chat"]["analysis_framework"] == "buffett"
    assert any("已同步设置对话风格和分析框架" in output for output in outputs)

    reloaded = ChatSession(output=lambda _: None)
    assert reloaded.style_name == "buffett"

    assert reloaded.handle_slash("/style clear") is False
    assert "style" not in load_config(strict=False)["chat"]
    assert "analysis_framework" not in load_config(strict=False)["chat"]
    assert ChatSession(output=lambda _: None).style_name == "balanced"


def test_style_supports_every_registered_investor_lens(monkeypatch, tmp_path):
    from young_stock.lens.registry import lens_ids

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    session = ChatSession(output=lambda _: None)

    for lens_id in lens_ids():
        assert session.handle_slash(f"/style set {lens_id}") is False
        assert session.style_name == lens_id
        assert load_config(strict=False)["chat"]["analysis_framework"] == lens_id


def test_style_set_replaces_conflicting_style_memory(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    outputs = []
    session = ChatSession(output=outputs.append)
    session.capture_long_term_memory("以后请扮演查理芒格式的投资教练。")

    assert session.handle_slash("/style set buffett") is False

    combined = "\n".join(
        item["content"]
        for notes in session.long_term_memory.values()
        for item in notes
    )
    assert "查理芒格" not in combined
    assert "buffett" in combined
    assert any("同步设置对话风格和分析框架" in output for output in outputs)


def test_style_set_affects_llm_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    captured_messages = []

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def chat(self, messages):
            captured_messages.append(messages)
            return type("Response", (), {"content": "收到"})()

    monkeypatch.setattr(chat_module, "LLMClient", DummyClient)
    session = ChatSession(output=lambda _: None)

    assert session.handle_slash("/style set buffett") is False
    session.handle_message("怎么看护城河？")

    safety_prompt = captured_messages[0][0]["content"]
    time_prompt = captured_messages[0][1]["content"]
    style_prompt = captured_messages[0][2]["content"]
    assert "young-stock-cli 助手" not in safety_prompt
    assert "当前系统时间（北京时间，UTC+8）是" in time_prompt
    assert "当前对话风格与分析框架：buffett" in style_prompt
    assert "股东通信" in style_prompt
    assert "我是 Buffett" in style_prompt
    assert "按这个风格对话" not in style_prompt
    assert "不要声称自己真的是历史上的该人物" in style_prompt
    assert "/stock <symbol>" in safety_prompt
    assert "/analyze" not in safety_prompt
    assert "/send" in safety_prompt
    assert "/reach <query>" not in safety_prompt
    assert "不要直接拒绝" in safety_prompt


def test_chat_allowed_query_slashes_exist_in_click_registry():
    from young_stock.cli import cli

    allowed_click_roots = {"a", "stock", "fund", "news", "daily", "report", "diagnose", "send", "profile", "memory"}

    assert allowed_click_roots <= set(cli.commands)


def test_style_set_uses_selected_persona_name_in_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    captured_messages = []

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def chat(self, messages):
            captured_messages.append(messages)
            return type("Response", (), {"content": "收到"})()

    monkeypatch.setattr(chat_module, "LLMClient", DummyClient)
    session = ChatSession(output=lambda _: None)

    assert session.handle_slash("/style set graham") is False
    session.handle_message("先自我介绍一下。")

    style_prompt = captured_messages[0][2]["content"]
    assert "我是 Graham" in style_prompt
    assert "young-stock-cli 助手" not in style_prompt


def test_chat_time_query_uses_beijing_system_time(monkeypatch):
    outputs = []
    session = ChatSession(output=outputs.append)
    fixed_now = chat_module.datetime(2026, 6, 19, 15, 30, 45, tzinfo=chat_module._BEIJING_TZ)
    monkeypatch.setattr(
        chat_module,
        "current_time_snapshot",
        lambda: {
            "current": fixed_now,
            "source": "network+local",
            "local": fixed_now,
            "network": fixed_now,
            "diff_seconds": 0,
        },
    )
    monkeypatch.setattr(
        chat_module,
        "LLMClient",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called for time query")),
    )

    session.handle_message("现在北京时间几点？今天几号？")

    assert outputs == ["当前北京时间是 2026 年 6 月 19 日 15:30:45，星期五（已用联网时钟与本地时钟交叉校验）。"]
    assert session.history[-1]["content"] == outputs[0]


def test_chat_injects_current_time_and_auto_research_context(monkeypatch):
    captured_messages = []

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def chat(self, messages):
            captured_messages.append(messages)
            return type("Response", (), {"content": "已分析"})()

    monkeypatch.setattr(chat_module, "LLMClient", DummyClient)
    monkeypatch.setattr(
        chat_module,
        "current_time_snapshot",
        lambda: {
            "current": chat_module.datetime(2026, 6, 19, 16, 8, 9, tzinfo=chat_module._BEIJING_TZ),
            "source": "network+local",
            "local": chat_module.datetime(2026, 6, 19, 16, 8, 7, tzinfo=chat_module._BEIJING_TZ),
            "network": chat_module.datetime(2026, 6, 19, 16, 8, 9, tzinfo=chat_module._BEIJING_TZ),
            "diff_seconds": 2,
        },
    )
    session = ChatSession(output=lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        chat_module,
        "run_research_bridge",
        lambda query: {"summary_material": """
title: Tesla Q1 2026 earnings
营收 120 亿美元，同比增长 12%
毛利率 18.4%
净利润 21 亿美元
现金流改善
https://example.com/raw
""".strip()},
    )

    session.handle_message("帮我搜索一下贵州茅台最新新闻和盈利情况")

    system_contents = [item["content"] for item in captured_messages[0] if item["role"] == "system"]
    assert any("当前系统时间（北京时间，UTC+8）是 2026-06-19 16:08:09" in content for content in system_contents)
    assert any("联网时钟与本地时钟交叉校验" in content for content in system_contents)
    assert any("本轮已自动完成外部研究补充" in content for content in system_contents)
    assert any("营收 120 亿美元" in content for content in system_contents)
    assert all("https://example.com/raw" not in content for content in system_contents)
    assert all("title:" not in content for content in system_contents)


def test_chat_auto_research_never_echoes_raw_capture(monkeypatch):
    outputs: list[str] = []

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def chat(self, messages):
            return type("Response", (), {"content": "已总结"})()

    monkeypatch.setattr(chat_module, "LLMClient", DummyClient)
    monkeypatch.setattr(
        chat_module,
        "current_time_snapshot",
        lambda: {
            "current": chat_module.datetime(2026, 6, 19, 16, 8, 9, tzinfo=chat_module._BEIJING_TZ),
            "source": "network+local",
            "local": chat_module.datetime(2026, 6, 19, 16, 8, 7, tzinfo=chat_module._BEIJING_TZ),
            "network": chat_module.datetime(2026, 6, 19, 16, 8, 9, tzinfo=chat_module._BEIJING_TZ),
            "diff_seconds": 2,
        },
    )
    session = ChatSession(output=outputs.append)
    monkeypatch.setattr(
        chat_module,
        "run_research_bridge",
        lambda query: {"summary_material": "营收 120 亿美元\n毛利率 18.4%"},
    )

    session.handle_message("搜索特斯拉 2026 年第一季度财报")

    assert outputs == ["已总结"]


def test_hidden_research_uses_bridge_with_raw_query(monkeypatch):
    session = ChatSession(output=lambda _: None)
    calls = []
    monkeypatch.setattr(
        chat_module,
        "run_research_bridge",
        lambda query: calls.append(query) or {"summary_material": "ok"},
    )

    assert session._hidden_research('Tesla "Q1" \\ guidance') == "ok"
    assert calls == ['Tesla "Q1" \\ guidance']


def test_current_time_snapshot_falls_back_to_local_when_network_unavailable(monkeypatch):
    local_now = chat_module.datetime(2026, 6, 19, 9, 0, 0, tzinfo=chat_module._BEIJING_TZ)
    monkeypatch.setattr(chat_module, "_local_beijing_now", lambda: local_now)
    monkeypatch.setattr(chat_module, "_median_network_time", lambda: None)
    chat_module._TIME_VERIFICATION_CACHE["verified_at"] = None
    chat_module._TIME_VERIFICATION_CACHE["local_now"] = None
    chat_module._TIME_VERIFICATION_CACHE["network_now"] = None

    snapshot = chat_module.current_time_snapshot()

    assert snapshot["current"] == local_now
    assert snapshot["source"] == "local-only"
    assert snapshot["network"] is None


def test_run_chat_banner_shows_style_options(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    def raise_eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(chat_module, "_prompt_toolkit_prompt", None)
    monkeypatch.setattr("builtins.input", raise_eof)

    run_chat()

    captured = capsys.readouterr().out
    assert "可选风格" in captured
    assert "balanced" in captured
    assert "当前风格" in captured
    assert "/style set <name>" in captured
    assert "对话风格、自称口吻和分析框架" in captured


def test_run_chat_uses_prompt_toolkit_with_fixed_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    prompts = []

    def fake_prompt(prompt):
        prompts.append(prompt)
        raise EOFError

    monkeypatch.setattr(chat_module, "_prompt_toolkit_prompt", fake_prompt)

    run_chat()

    assert prompts == ["young "]


def test_run_chat_falls_back_to_builtins_input_when_prompt_toolkit_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        raise EOFError

    monkeypatch.setattr(chat_module, "_prompt_toolkit_prompt", None)
    monkeypatch.setattr("builtins.input", fake_input)

    run_chat()

    assert prompts == ["young "]
