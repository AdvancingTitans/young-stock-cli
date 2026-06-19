from pathlib import Path

from click.testing import CliRunner

import young_stock.cli as cli_module
from young_stock.cli import cli


def test_replay_and_report_default_to_current_calendar_date(monkeypatch, tmp_path):
    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "_current_report_date", lambda: "20260619")

    replay_calls = []
    monkeypatch.setattr(cli_module, "_run_llm_replay", lambda date_str, kind="replay", symbol=None: replay_calls.append((date_str, kind, symbol)))
    monkeypatch.setattr(
        "young_stock.pdf.export_report_pdf",
        lambda trade_date, **kwargs: (Path(f"/tmp/{trade_date}.md"), Path(f"/tmp/{trade_date}.pdf")),
    )

    runner = CliRunner()
    replay_result = runner.invoke(cli, ["replay"])
    report_result = runner.invoke(cli, ["report"])

    assert replay_result.exit_code == 0
    assert report_result.exit_code == 0
    assert replay_calls == [("20260619", "replay", None)]
    assert "/tmp/20260619.pdf" in report_result.output
