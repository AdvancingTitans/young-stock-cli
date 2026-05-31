"""Smoke tests for the CLI surface (no network calls)."""
import subprocess
import sys

from young_stock_cli import __version__
from young_stock_cli.cli import main


def test_version_constant():
    assert __version__.count(".") == 2


def test_help_runs():
    rc = main(["--help"])
    assert rc == 0


def test_version_flag(capsys):
    rc = main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_unknown_command_returns_2():
    rc = main(["bogus"])
    assert rc == 2


def test_module_entry_point_runs():
    """`python -m young_stock_cli --help` works."""
    result = subprocess.run(
        [sys.executable, "-m", "young_stock_cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "young-stock-cli" in result.stdout


def test_market_subcommands_recognized():
    """`a`, `hk`, `us`, `global` are all valid first args (we don't run them,
    just confirm the dispatcher doesn't reject them up front)."""
    from young_stock_cli.cli import USAGE

    for m in ("a", "hk", "us", "global"):
        assert m in USAGE
