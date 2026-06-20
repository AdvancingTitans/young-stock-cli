from pathlib import Path

from click.testing import CliRunner

import young_stock.cli as cli_module
from young_stock.cli import cli


def test_report_defaults_to_current_calendar_date(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(
        "young_stock.pdf.export_report_pdf",
        lambda trade_date, **kwargs: (Path(f"/tmp/{trade_date}.md"), Path(f"/tmp/{trade_date}.pdf")),
    )

    runner = CliRunner()
    report_result = runner.invoke(cli, ["report"])

    assert report_result.exit_code == 0
    assert "/tmp/20260619.pdf" in report_result.output


def test_daily_analyze_and_send_default_to_latest_report_trade_date(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    daily_calls = []
    replay_calls = []
    send_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_plain_daily",
        lambda date_str, profile, **kwargs: daily_calls.append((date_str, profile, kwargs)),
    )
    monkeypatch.setattr(
        cli_module,
        "_run_llm_replay",
        lambda date_str, kind="replay", symbol=None: replay_calls.append((date_str, kind, symbol)),
    )
    monkeypatch.setattr(
        "young_stock.channels.send_report",
        lambda trade_date, **kwargs: send_calls.append((trade_date, kwargs)) or [],
    )

    runner = CliRunner()
    daily_result = runner.invoke(cli, ["daily"])
    analyze_result = runner.invoke(cli, ["analyze", "600519"])
    send_result = runner.invoke(cli, ["send"])

    assert daily_result.exit_code == 0
    assert analyze_result.exit_code == 0
    assert send_result.exit_code == 0
    assert daily_calls == [("20260619", {"stocks": ["600519"], "funds": []}, {"no_news": False, "report_format": "full", "only": None, "order": None, "quick": False})]
    assert replay_calls == [("20260619", "analyze", "600519")]
    assert send_calls == [(None, {"channel_name": None})]
