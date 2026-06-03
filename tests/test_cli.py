import sys
from types import SimpleNamespace

import young_stock.cli as cli_module
from young_stock import __version__
from young_stock.cli import cli


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
        "a", "hk", "us", "global", "indices", "zt-pool", "flow", "stock", "fund", "news",
        "daily", "profile", "portfolio", "alert", "note", "diary", "diagnose", "guide", "example",
        "cache-clear", "update", "uninstall",
    ]:
        assert sub in result.output, f"subcommand `{sub}` missing from help"


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
    assert "young profile add-stock 600519" in result.output
    assert "young profile add-fund 161725" in result.output


def test_cli_profile_add_stock_and_fund_then_daily_uses_memory(monkeypatch, tmp_path):
    from click.testing import CliRunner

    profile_path = tmp_path / "profile.json"
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(profile_path))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)

    calls = []
    monkeypatch.setattr(
        cli_module._core,
        "run_daily_report",
        lambda date_str, watchlist=None, include_news=True, report_format="full", only=None, order=None, quick=False: calls.append(
            (date_str, watchlist, include_news, report_format, only, order, quick)
        ),
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["profile", "add-stock", "600519"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725"]).exit_code == 0

    result = runner.invoke(cli, ["daily", "--no-news", "--format", "summary", "--only", "funds", "--quick"])

    assert result.exit_code == 0
    assert calls == [("20260529", {"stocks": ["600519"], "funds": ["161725"], "groups": {}}, False, "summary", "funds", None, True)]


def test_cli_profile_remove_clear_and_groups(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    runner = CliRunner()

    assert runner.invoke(cli, ["profile", "add-stock", "600519"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "create", "成长型"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "add", "成长型", "600519"]).exit_code == 0

    listed = runner.invoke(cli, ["profile", "list"])
    assert listed.exit_code == 0
    assert "600519" in listed.output
    assert "成长型" in listed.output

    assert runner.invoke(cli, ["profile", "remove-stock", "600519"]).exit_code == 0
    after_remove = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_remove.output

    assert runner.invoke(cli, ["profile", "add-stock", "000001"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "group", "add", "成长型", "000001"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear-stocks"]).exit_code == 0
    after_clear_stocks = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_clear_stocks.output
    assert "Funds: 161725" in after_clear_stocks.output
    assert "stocks=-" in after_clear_stocks.output

    assert runner.invoke(cli, ["profile", "clear-funds"]).exit_code == 0
    after_clear_funds = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear_funds.output

    assert runner.invoke(cli, ["profile", "add-fund", "161725"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear"]).exit_code == 0
    after_clear = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear.output


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


def test_cli_diagnose_outputs_network_guidance(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "SOURCE_HEALTH", SimpleNamespace(snapshot=lambda name: SimpleNamespace(success_rate=0.25, average_latency_ms=1200, should_skip=True)))

    result = CliRunner().invoke(cli, ["diagnose"])

    assert result.exit_code == 0
    assert "网络诊断" in result.output
    assert "建议" in result.output
