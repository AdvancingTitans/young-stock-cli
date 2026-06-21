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
    monkeypatch.setattr(
        cli_module._core,
        "get_single_stock_quote",
        lambda symbol, date: cli_module._core.QuoteData(
            symbol="600519",
            name="贵州茅台",
            market="cn_market",
            date=date,
            price=1600.0,
            change_pct=0.5,
            source="test",
        ),
    )

    daily_calls = []
    replay_calls = []
    analyze_calls = []
    send_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_plain_daily",
        lambda date_str, profile, **kwargs: daily_calls.append((date_str, profile, kwargs)),
    )
    monkeypatch.setattr(
        cli_module._core,
        "run_stock_quote",
        lambda symbol, date_str, include_news=True: analyze_calls.append((symbol, date_str, include_news)),
    )
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda *args, **kwargs: type("Extras", (), {"to_dict": staticmethod(lambda: {})})(),
    )
    monkeypatch.setattr(cli_module, "_print_stock_extras", lambda *args, **kwargs: None)
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
    assert daily_calls == [("20260619", {"stocks": ["600519"], "funds": []}, {"no_news": False, "report_format": "full", "order": None})]
    assert analyze_calls == [("600519", "20260619", True)]
    assert replay_calls == []
    assert send_calls == [(None, {"channel_name": None})]


def test_daily_llm_defaults_to_latest_report_trade_date(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    replay_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_daily_llm",
        lambda date_str, **kwargs: replay_calls.append((date_str, kwargs)),
    )

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert replay_calls == [("20260619", {"refresh": False, "no_news": False, "report_format": "full", "order": None})]
