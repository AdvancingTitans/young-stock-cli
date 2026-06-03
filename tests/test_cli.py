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
    for sub in ["a", "hk", "us", "global", "indices", "zt-pool", "flow", "stock", "fund", "news", "daily", "profile", "cache-clear", "update"]:
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
        lambda date_str, watchlist=None, include_news=True: calls.append((date_str, watchlist, include_news)),
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["profile", "add-stock", "600519"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725"]).exit_code == 0

    result = runner.invoke(cli, ["daily", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("20260529", {"stocks": ["600519"], "funds": ["161725"]}, False)]
