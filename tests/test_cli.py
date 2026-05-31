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
    for sub in ["a", "hk", "us", "global", "indices", "zt-pool", "flow", "stock", "cache-clear", "update"]:
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
