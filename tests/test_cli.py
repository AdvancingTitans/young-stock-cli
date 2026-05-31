import json
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
    for sub in ["a", "hk", "us", "global", "indices", "zt-pool", "flow", "cache-clear", "update"]:
        assert sub in result.output, f"subcommand `{sub}` missing from help"


def test_indices_json_outputs_parseable_payload(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(
        cli_module._core,
        "get_index",
        lambda date: [{"f12": "000001", "f14": "上证指数", "f2": 3000.12}],
    )

    result = CliRunner().invoke(cli, ["indices", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["date"] == "20260529"
    assert payload["indices"][0]["f12"] == "000001"


def test_a_zt_json_outputs_pool_payload(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "get_zt_pool", lambda date: {"data": {"tc": 2}})
    monkeypatch.setattr(cli_module._core, "get_dt_pool", lambda date: {"data": {"tc": 1}})
    monkeypatch.setattr(cli_module._core, "get_zb_pool", lambda date: {"data": {"tc": 3}})

    result = CliRunner().invoke(cli, ["a", "--zt", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["zt_pool"]["data"]["tc"] == 2
    assert payload["dt_pool"]["data"]["tc"] == 1
    assert payload["zb_pool"]["data"]["tc"] == 3


def test_flow_json_outputs_parseable_payload(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(
        cli_module._core,
        "get_fund_flow",
        lambda date: {"主力净流入": "-42899849216.0", "_source": "东财历史日线资金流"},
    )

    result = CliRunner().invoke(cli, ["flow", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["flow"]["主力净流入"] == "-42899849216.0"


def test_global_json_serializes_quote_data(monkeypatch):
    from click.testing import CliRunner

    quote = cli_module._core.QuoteData(
        symbol="^HSI",
        name="恒生指数",
        market="hk_market",
        date="20260529",
        price=18000.0,
    )

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "get_index", lambda date: [{"f12": "000001"}])
    monkeypatch.setattr(cli_module._core, "fetch_hk_indices_tencent", lambda symbols, date: [quote])
    monkeypatch.setattr(cli_module._core, "fetch_us_indices_sina", lambda symbols, date: [])

    result = CliRunner().invoke(cli, ["global", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["a"][0]["f12"] == "000001"
    assert payload["hk"][0]["symbol"] == "^HSI"


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
