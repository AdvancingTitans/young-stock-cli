import json
import sys
from types import SimpleNamespace

import young_stock.cli as cli_module
from young_stock import __version__
from young_stock.cli import cli


def _patch_profile_validation(monkeypatch):
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(
        cli_module._core,
        "get_single_stock_quote",
        lambda symbol, date: cli_module._core.QuoteData(
            symbol=symbol,
            name="测试股票",
            market="cn_market",
            date=date,
            price=10.0,
            change_pct=1.0,
            source="test",
        ),
    )
    monkeypatch.setattr(
        cli_module._core,
        "fetch_fund_estimate",
        lambda code, date: {
            "fundcode": code,
            "name": "测试基金",
            "estimate_nav": "1.00",
            "estimate_change_pct": "0.10",
            "date": date,
        },
    )


def test_version_string():
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 2


def test_cli_help(capsys):
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "A-share" in result.output


def test_cli_version():
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_subcommands_registered():
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    for sub in [
        "a", "hk", "us", "global", "indices", "zt-pool", "flow", "block-trades", "stock", "fund", "news",
        "daily", "profile", "portfolio", "alert", "note", "diary", "diagnose", "guide", "example", "init",
        "cache-clear", "update", "uninstall", "config", "chat", "replay", "analyze", "report", "send",
    ]:
        assert sub in result.output, f"subcommand `{sub}` missing from help"


def test_cli_top_level_command_help_is_available():
    from click.testing import CliRunner

    runner = CliRunner()
    commands = [
        "a", "hk", "us", "global", "indices", "zt-pool", "flow", "block-trades", "stock", "fund", "news",
        "daily", "profile", "portfolio", "alert", "note", "diary", "diagnose", "guide", "example", "init",
        "cache-clear", "update", "uninstall", "config", "chat", "replay", "analyze", "report", "send",
    ]

    for command in commands:
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, f"{command} --help failed: {result.output}"
        assert "Usage:" in result.output


def test_cli_stock_runs_single_stock_quote(monkeypatch):
    from click.testing import CliRunner

    calls = []

    def fake_run_stock(symbol, date_str, include_news):
        calls.append((symbol, date_str, include_news))

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_stock_quote", fake_run_stock)

    runner = CliRunner()
    result = runner.invoke(cli, ["stock", "600519", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("600519", "20260529", False)]


def test_cli_fund_runs_fund_report(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module._core, "run_fund_report", lambda code, date_str, include_news=True: calls.append((code, date_str, include_news)))

    runner = CliRunner()
    result = runner.invoke(cli, ["fund", "161725", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("161725", "20260529", False)]


def test_cli_a_no_news(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module._core, "run_a_share", lambda date_str, include_news=True: calls.append((date_str, include_news)))

    runner = CliRunner()
    result = runner.invoke(cli, ["a", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("20260529", False)]


def test_cli_us_no_news(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module._core, "run_us_market", lambda date_str, include_news=True: calls.append((date_str, include_news)))

    runner = CliRunner()
    result = runner.invoke(cli, ["us", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("20260529", False)]


def test_cli_news_runs_stock_news(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module._core, "run_stock_news", lambda symbol, date_str, size=8: calls.append((symbol, date_str, size)))

    runner = CliRunner()
    result = runner.invoke(cli, ["news", "0700.HK", "--limit", "6"])

    assert result.exit_code == 0
    assert calls == [("0700.HK", "20260529", 6)]

    calls.clear()
    result = runner.invoke(cli, ["news", "stock", "0700.HK", "--limit", "6"])

    assert result.exit_code == 0
    assert calls == [("0700.HK", "20260529", 6)]


def test_cli_flow_stock_runs_single_stock_flow(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_stock_fund_flow_report", lambda symbol, date_str, limit=20: calls.append((symbol, date_str, limit)))

    runner = CliRunner()
    result = runner.invoke(cli, ["flow", "--stock", "AAPL", "--limit", "3"])

    assert result.exit_code == 0
    assert calls == [("AAPL", "20260529", 3)]


def test_cli_flow_northbound_runs_northbound_flow(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_northbound_flow_report", lambda date_str: calls.append(date_str))

    runner = CliRunner()
    result = runner.invoke(cli, ["flow", "--northbound"])

    assert result.exit_code == 0
    assert calls == ["20260529"]


def test_cli_block_trades_runs_report(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_block_trades_report", lambda symbol, date_str, limit=10: calls.append((symbol, date_str, limit)))

    runner = CliRunner()
    result = runner.invoke(cli, ["block-trades", "600519", "--limit", "5"])

    assert result.exit_code == 0
    assert calls == [("600519", "20260529", 5)]


def test_cli_hk_no_news(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module._core, "run_hk_market", lambda date_str, include_news=True: calls.append((date_str, include_news)))

    runner = CliRunner()
    result = runner.invoke(cli, ["hk", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("20260529", False)]


def test_cli_update_runs_pip_upgrade(monkeypatch):
    from click.testing import CliRunner

    calls = []

    def fake_run(cmd, check):
        calls.append((cmd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--pre", "--user"])

    assert result.exit_code == 0
    assert calls == [(
        [sys.executable, "-m", "pip", "install", "--upgrade", "young-stock-cli", "--pre", "--user"],
        False,
    )]


def test_cli_update_failure_mentions_python_version(monkeypatch):
    from click.testing import CliRunner

    def fake_run(cmd, check):
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["update"])

    assert result.exit_code != 0
    assert "Python 3.9+" in result.output
    assert "python3 -m pip install --upgrade young-stock-cli" in result.output


def test_cli_config_models_lists_provider_models(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(
        cli_module.LLMClient,
        "list_models",
        lambda self: ["moonshot-v1-8k", "kimi-k2-0711-preview"],
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "openai",
            "--api-base",
            "https://api.moonshot.cn/v1",
            "--api-key-env",
            "MOONSHOT_API_KEY",
        ],
    )

    assert result.exit_code == 0
    assert "moonshot-v1-8k" in result.output
    assert "kimi-k2-0711-preview" in result.output


def test_cli_uninstall_runs_pip_uninstall(monkeypatch):
    from click.testing import CliRunner

    calls = []

    def fake_run(cmd, check):
        calls.append((cmd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli, ["uninstall"])

    assert result.exit_code == 0
    assert calls == [([sys.executable, "-m", "pip", "uninstall", "-y", "young-stock-cli"], False)]


def test_cli_daily_guides_first_use_when_profile_empty(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)

    runner = CliRunner()
    result = runner.invoke(cli, ["daily", "--no-news"])

    assert result.exit_code == 0
    assert "尚未设置投资记忆" in result.output
    assert "young profile add-stock 600519 --buy-date" in result.output
    assert "young profile add-fund 161725 --buy-date" in result.output


def test_cli_profile_add_stock_and_fund_then_daily_uses_memory(monkeypatch, tmp_path):
    from click.testing import CliRunner

    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(profile_path))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    _patch_profile_validation(monkeypatch)

    calls = []
    monkeypatch.setattr(
        cli_module._core,
        "run_daily_report",
        lambda date_str, watchlist=None, include_news=True, report_format="full", only=None, order=None, quick=False: calls.append(
            (date_str, watchlist, include_news, report_format, only, order, quick)
        ),
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["profile", "add-stock", "600519", "--buy-date", "2026-01-15", "--quantity", "100"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0

    result = runner.invoke(cli, ["daily", "--no-news", "--format", "summary", "--only", "funds", "--quick"])

    assert result.exit_code == 0
    assert calls == [(
        "20260529",
        {
            "stocks": ["600519"],
            "funds": ["161725"],
            "groups": {},
            "positions": {
                "stocks": {"600519": {"buy_date": "2026-01-15", "quantity": 100.0}},
                "funds": {"161725": {"buy_date": "2026-02-01", "quantity": 1000.0}},
            },
        },
        False,
        "summary",
        "funds",
        None,
        True,
    )]


def test_cli_profile_remove_clear_and_groups(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    _patch_profile_validation(monkeypatch)
    runner = CliRunner()

    assert runner.invoke(cli, ["profile", "add-stock", "600519", "--buy-date", "2026-01-15", "--quantity", "100"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "create", "成长型"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "add", "成长型", "600519"]).exit_code == 0

    listed = runner.invoke(cli, ["profile", "list"])
    assert listed.exit_code == 0
    assert "600519" in listed.output
    assert "成长型" in listed.output

    assert runner.invoke(cli, ["profile", "remove-stock", "600519"]).exit_code == 0
    after_remove = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_remove.output

    assert runner.invoke(cli, ["profile", "add-stock", "000001", "--buy-date", "2026-01-20", "--quantity", "200"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "add", "成长型", "000001"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear-stocks"]).exit_code == 0
    after_clear_stocks = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_clear_stocks.output
    assert "Funds: 161725" in after_clear_stocks.output
    assert "stocks=-" in after_clear_stocks.output

    assert runner.invoke(cli, ["profile", "clear-funds"]).exit_code == 0
    after_clear_funds = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear_funds.output

    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear"]).exit_code == 0
    after_clear = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear.output


def test_cli_profile_add_requires_position_details(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    runner = CliRunner()

    result = runner.invoke(cli, ["profile", "add-stock", "600519"])

    assert result.exit_code != 0
    assert "Missing option '--buy-date'" in result.output
    assert cli_module.load_profile()["stocks"] == []


def test_cli_profile_add_validates_stock_before_writing(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")

    def fake_quote(symbol, date):
        if symbol == "bad-code":
            raise ValueError("invalid")
        return cli_module._core.QuoteData(
            symbol="600519",
            name="贵州茅台",
            market="cn_market",
            date=date,
            price=1600.0,
            change_pct=0.5,
            source="test",
        )

    monkeypatch.setattr(cli_module._core, "get_single_stock_quote", fake_quote)
    runner = CliRunner()

    invalid = runner.invoke(cli, ["profile", "add-stock", "bad-code", "--buy-date", "2026-01-15", "--quantity", "100"])
    assert invalid.exit_code != 0
    assert "bad-code 不是有效的股票代码" in invalid.output
    assert cli_module.load_profile()["stocks"] == []

    valid = runner.invoke(cli, ["profile", "add-stock", "600519", "--buy-date", "2026-01-15", "--quantity", "100"])
    assert valid.exit_code == 0
    assert "您的投资记忆已添加：贵州茅台（600519）" in valid.output
    assert cli_module.load_profile()["stocks"] == ["600519"]


def test_cli_profile_add_validates_fund_before_writing(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(
        cli_module._core,
        "fetch_fund_estimate",
        lambda code, date: {"_error": "not found"} if code == "000000" else {"fundcode": code, "name": "招商中证白酒", "estimate_nav": "1.0"},
    )
    runner = CliRunner()

    invalid = runner.invoke(cli, ["profile", "add-fund", "000000", "--buy-date", "2026-01-15", "--quantity", "1000"])
    assert invalid.exit_code != 0
    assert "000000 不是有效的基金代码" in invalid.output
    assert cli_module.load_profile()["funds"] == []

    valid = runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-01-15", "--quantity", "1000"])
    assert valid.exit_code == 0
    assert "您的投资记忆已添加：招商中证白酒（161725）" in valid.output
    assert cli_module.load_profile()["funds"] == ["161725"]


def test_cli_local_productivity_commands(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    assert runner.invoke(cli, ["portfolio", "create", "我的组合"]).exit_code == 0
    assert runner.invoke(cli, ["portfolio", "add", "我的组合", "600519", "10"]).exit_code == 0
    assert "600519" in runner.invoke(cli, ["portfolio", "show", "我的组合"]).output

    assert runner.invoke(cli, ["alert", "create", "600519", "涨跌幅>5%"]).exit_code == 0
    assert "600519" in runner.invoke(cli, ["alert", "list"]).output

    assert runner.invoke(cli, ["note", "add", "今天减少追高"]).exit_code == 0
    assert "减少追高" in runner.invoke(cli, ["note", "list"]).output

    assert runner.invoke(cli, ["diary", "save", "20260603", "--text", "日报摘要"]).exit_code == 0
    assert "日报摘要" in runner.invoke(cli, ["diary", "show", "20260603"]).output


def test_cli_init_bootstraps_local_state(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path / "young-home"))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr("young_stock.pdf._load_weasyprint", lambda: object())

    result = CliRunner().invoke(cli, ["init"])

    assert result.exit_code == 0
    assert "初始化完成" in result.output
    assert "young daily --format summary" in result.output
    assert "young replay" in result.output
    assert (tmp_path / "young-home" / "config.json").exists()
    assert (tmp_path / "young-home" / "reports").exists()
    assert (tmp_path / "profile.json").exists()


def test_cli_diagnose_outputs_network_guidance(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "SOURCE_HEALTH", SimpleNamespace(snapshot=lambda name: SimpleNamespace(success_rate=0.25, average_latency_ms=1200, should_skip=True)))

    result = CliRunner().invoke(cli, ["diagnose"])

    assert result.exit_code == 0
    assert "网络诊断" in result.output
    assert "建议" in result.output


def test_cli_diagnose_json_outputs_machine_readable_support_info(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        cli_module._core,
        "SOURCE_HEALTH",
        SimpleNamespace(snapshot=lambda name: SimpleNamespace(success_rate=1.0, average_latency_ms=0.0, should_skip=False)),
    )

    result = CliRunner().invoke(cli, ["diagnose", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "young diagnose"
    assert payload["version"] == __version__
    assert payload["python"]["executable"] == sys.executable
    assert payload["paths"]["profile"].endswith("profile.json")
    assert payload["paths"]["home"].endswith("home")
    assert payload["paths"]["cache"]
    assert payload["read_only"] is True
    assert {source["name"] for source in payload["sources"]} >= {"eastmoney", "sina", "tencent", "ths", "futu"}


def test_cli_config_llm_saves_and_masks_secret(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    saved = runner.invoke(
        cli,
        [
            "config",
            "llm",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key",
            "very-secret",
        ],
    )
    shown = runner.invoke(cli, ["config", "show"])

    assert saved.exit_code == 0
    assert "very-secret" not in saved.output
    assert "very-secret" not in shown.output
    assert "deepseek-chat" in shown.output


def test_cli_daily_llm_uses_enhanced_path(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    calls = []
    monkeypatch.setattr(cli_module, "_run_llm_replay", lambda date_str, kind="replay", symbol=None: calls.append((date_str, kind, symbol)))

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert calls == [("20260618", "replay", None)]


def test_cli_report_and_send_render_friendly_errors(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr("young_stock.pdf.export_report_pdf", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("pdf missing")))
    report_result = CliRunner().invoke(cli, ["report", "--date", "20260618"])
    assert report_result.exit_code != 0
    assert "pdf missing" in report_result.output

    monkeypatch.setattr("young_stock.channels.send_report", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("run report first")))
    send_result = CliRunner().invoke(cli, ["send", "--date", "20260618"])
    assert send_result.exit_code != 0
    assert "run report first" in send_result.output
