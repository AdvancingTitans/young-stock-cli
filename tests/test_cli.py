import json
import sys
from types import SimpleNamespace

import click

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
    registered = set(cli.commands)
    for sub in [
        "a", "hk", "us", "global", "indices", "zt-pool", "flow", "stock", "fund", "news",
        "daily", "profile", "portfolio", "diary", "diagnose", "guide", "example", "init",
        "cache-clear", "update", "uninstall", "config", "chat", "style", "analyze", "report", "send", "lhb",
    ]:
        assert sub in registered, f"subcommand `{sub}` missing from command registry"
    for removed in ["block-trades", "alert", "note", "reach"]:
        assert removed not in registered, f"removed subcommand `{removed}` unexpectedly present in registry"


def test_cli_top_level_command_help_is_available():
    from click.testing import CliRunner

    runner = CliRunner()
    commands = [
        "a", "hk", "us", "global", "indices", "zt-pool", "flow", "stock", "fund", "news",
        "daily", "profile", "portfolio", "diary", "diagnose", "guide", "example", "init",
        "cache-clear", "update", "uninstall", "config", "chat", "style", "analyze", "report", "send", "lhb",
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
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda *args, **kwargs: type(
            "Extras",
            (),
            {
                "to_dict": staticmethod(
                    lambda: {
                        "lhb": {"rows": [{"date": "20260529", "net_buy": 123}]},
                        "financial_trends": {"rows": []},
                        "social_heat": {"_unavailable": "optional"},
                        "events": {},
                        "technical_fallback": {"_unavailable": "configure"},
                    }
                )
            },
        )(),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["stock", "600519", "--no-news"])

    assert result.exit_code == 0
    assert calls == [("600519", "20260529", False)]
    assert "## 增强证据" in result.output
    assert "### 龙虎榜" in result.output
    assert "| 20260529 | 123 |" in result.output
    assert "optional" not in result.output
    assert "configure" not in result.output


def test_cli_analyze_defaults_to_plain_stock_evidence_without_llm(monkeypatch):
    from click.testing import CliRunner

    run_calls = []
    extras_calls = []
    render_calls = []

    monkeypatch.setattr(cli_module, "_default_report_trade_date", lambda: "20260529")
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
    monkeypatch.setattr(
        cli_module._core,
        "run_stock_quote",
        lambda symbol, date_str, include_news=True: run_calls.append((symbol, date_str, include_news)),
    )
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda core, symbol, date_str, rich_source=False: extras_calls.append((symbol, date_str, rich_source)) or type(
            "Extras",
            (),
            {"to_dict": staticmethod(lambda: {"lhb": {"rows": [{"date": "20260529", "net_buy": 1}]}})},
        )(),
    )
    monkeypatch.setattr(
        cli_module,
        "_print_stock_extras",
        lambda extras, **kwargs: render_calls.append((extras, kwargs)),
    )
    llm_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_llm_replay",
        lambda *args, **kwargs: llm_calls.append((args, kwargs)),
    )

    result = CliRunner().invoke(cli, ["analyze", "600519"])

    assert result.exit_code == 0
    assert run_calls == [("600519", "20260529", True)]
    assert extras_calls == [("600519", "20260529", False)]
    assert len(render_calls) == 1
    assert llm_calls == []


def test_cli_analyze_llm_without_explicit_lens_does_not_pass_lens_layer(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module, "_default_report_trade_date", lambda: "20260529")
    replay_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_llm_replay",
        lambda date_str, **kwargs: replay_calls.append((date_str, kwargs)),
    )

    result = CliRunner().invoke(cli, ["analyze", "600519", "--llm"])

    assert result.exit_code == 0
    assert replay_calls == [("20260529", {"kind": "analyze", "symbol": "600519"})]


def test_cli_daily_llm_without_explicit_lens_does_not_pass_lens_layer(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_daily_llm",
        lambda date_str, **kwargs: calls.append((date_str, kwargs)),
    )

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert calls == [("20260619", {"refresh": False, "no_news": False, "report_format": "full", "order": None})]


def test_cli_explicit_lens_requires_llm(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    runner = CliRunner()

    daily_result = runner.invoke(cli, ["daily", "--lens", "all"])
    analyze_result = runner.invoke(cli, ["analyze", "600519", "--lens", "all"])

    assert daily_result.exit_code != 0
    assert analyze_result.exit_code != 0
    assert "--lens requires --llm" in daily_result.output
    assert "--lens requires --llm" in analyze_result.output


def test_cli_debate_rounds_require_llm_and_lens_all(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260619")
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    runner = CliRunner()

    no_llm = runner.invoke(cli, ["daily", "--debate-rounds", "4"])
    wrong_lens = runner.invoke(cli, ["analyze", "600519", "--llm", "--lens", "balanced", "--debate-rounds", "4"])

    assert no_llm.exit_code != 0
    assert wrong_lens.exit_code != 0
    assert "--debate-rounds requires --llm and --lens all" in no_llm.output
    assert "--debate-rounds requires --llm and --lens all" in wrong_lens.output


def test_cli_analyze_accepts_source_flags_without_llm(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module, "_default_report_trade_date", lambda: "20260529")
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
    monkeypatch.setattr(cli_module._core, "run_stock_quote", lambda *args, **kwargs: None)
    source_flags = []
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda core, symbol, date_str, rich_source=False: source_flags.append((symbol, date_str, rich_source, core.BROWSER_FALLBACK)) or type(
            "Extras",
            (),
            {"to_dict": staticmethod(lambda: {})},
        )(),
    )
    monkeypatch.setattr(cli_module, "_print_stock_extras", lambda *args, **kwargs: None)

    result = CliRunner().invoke(cli, ["analyze", "600519", "--rich-source", "--browser-fallback"])

    assert result.exit_code == 0
    assert source_flags == [("600519", "20260529", True, True)]


def test_cli_analyze_rejects_invalid_symbol_before_rendering(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "get_single_stock_quote", lambda symbol, date: (_ for _ in ()).throw(ValueError("invalid")))
    called = []
    monkeypatch.setattr(cli_module._core, "run_stock_quote", lambda *args, **kwargs: called.append("run"))

    result = CliRunner().invoke(cli, ["analyze", "bad-code"])

    assert result.exit_code != 0
    assert "bad-code 不是有效的股票代码" in result.output
    assert called == []


def test_cli_stock_shows_short_hint_when_no_enhanced_evidence(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_stock_quote", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda *args, **kwargs: type(
            "Extras",
            (),
            {
                "to_dict": staticmethod(
                    lambda: {
                        "lhb": {},
                        "financial_trends": {"_unavailable": "blocked"},
                        "social_heat": {},
                        "events": {"_unavailable": "blocked"},
                        "technical_fallback": {"_unavailable": "blocked"},
                    }
                )
            },
        )(),
    )

    result = CliRunner().invoke(cli, ["stock", "600519", "--browser-fallback"])

    assert result.exit_code == 0
    assert "未返回可展示的增强证据" in result.output
    assert "YOUNG_STOCK_RESEARCH_COMMAND" in result.output
    assert "当前增强项没有需要启动浏览器的失败源" not in result.output
    assert "已允许浏览器回退" in result.output


def test_cli_stock_renders_human_readable_enhanced_evidence(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "run_stock_quote", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli_module,
        "collect_stock_extras",
        lambda *args, **kwargs: type(
            "Extras",
            (),
            {
                "to_dict": staticmethod(
                    lambda: {
                        "lhb": {
                            "requested_date": "20260529",
                            "rows": [
                                {"date": "2007-01-01", "name": "A", "reason": "历史异常记录", "buy": 1, "sell": 2, "net_buy": -1},
                                {"date": "2013-01-01", "name": "B", "reason": "历史异常记录", "buy": 3, "sell": 4, "net_buy": -1},
                                {"date": "20260529", "name": "贵州茅台", "reason": "日涨幅偏离值达到7%", "buy": 1000, "sell": 300, "net_buy": 700},
                            ],
                            "_source": "东方财富龙虎榜",
                        },
                        "financial_trends": {
                            "ratio_trends": [{"period": "2024", "revenue": 100, "net_profit": 20}],
                            "_source": "akshare 财务摘要 + 三张表",
                        },
                        "social_heat": {
                            "keyword": "600519",
                            "count": 1,
                            "rows": [{"platform": "微博", "title": "贵州茅台"}],
                            "_source": "公开社交热榜 JSON",
                        },
                        "events": {
                            "rows": [{"date": "20260529", "title": "发布年度报告"}],
                            "_source": "akshare 公告",
                        },
                        "technical_fallback": {
                            "last_close": 1712.34,
                            "ma20": 1688.1,
                            "ma60": 1650.8,
                            "_source": "yfinance",
                        },
                    }
                )
            },
        )(),
    )

    result = CliRunner().invoke(cli, ["stock", "600519", "--rich-source", "--no-news"])

    assert result.exit_code == 0
    assert "## 增强证据" in result.output
    assert "### 龙虎榜" in result.output
    assert "### 五年财务趋势" in result.output
    assert "### 社交热度" in result.output
    assert "### 公告与事件" in result.output
    assert "### 技术指标补充" in result.output
    assert "#### 财务指标趋势" in result.output
    assert "| 报告期 | 营业收入 | 净利润 |" in result.output
    assert "- 关键词: 600519" in result.output
    assert "- 记录数: 1" in result.output
    assert "- 最新收盘价: 1712.34" in result.output
    assert "2007-01-01" not in result.output
    assert "2013-01-01" not in result.output
    assert "{\n" not in result.output
    assert '"rows"' not in result.output
    assert "_source" not in result.output
    assert "_unavailable" not in result.output
    for internal_key in (
        "requested_date",
        "ratio_trends",
        "period",
        "revenue",
        "net_profit",
        "keyword",
        "count",
        "platform",
        "title",
        "date",
        "last_close",
        "ma20",
        "ma60",
    ):
        assert internal_key not in result.output


def test_render_nested_mapping_keeps_first_nested_item():
    lines = cli_module._render_nested_mapping("财务报表", {"资产负债表": {"流动资产": 1, "非流动资产": 2}})

    assert "#### 资产负债表" in lines
    assert "- 流动资产: 1" in lines
    assert "- 非流动资产: 2" in lines


def test_cli_lhb_prints_natural_empty_hint(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(
        cli_module,
        "fetch_lhb",
        lambda core, symbol, date, limit: {
            "symbol": symbol,
            "requested_date": date,
            "rows": [
                {"date": "2007-01-01", "name": "A", "reason": "历史异常记录", "buy": 1, "sell": 2, "net_buy": -1},
                {"date": "2013-01-01", "name": "B", "reason": "历史异常记录", "buy": 3, "sell": 4, "net_buy": -1},
            ],
            "_source": "东方财富龙虎榜",
        },
    )

    result = CliRunner().invoke(cli, ["lhb", "600519"])

    assert result.exit_code == 0
    assert "暂无可展示的龙虎榜证据" in result.output or "未找到可展示的龙虎榜记录" in result.output
    assert "{\n" not in result.output
    assert '"rows"' not in result.output
    assert "_source" not in result.output
    assert "_unavailable" not in result.output


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


def test_cli_removed_commands_are_rejected():
    from click.testing import CliRunner

    runner = CliRunner()
    for command in ("block-trades", "alert", "note", "reach"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code != 0
        assert "No such command" in result.output


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


def test_cli_update_uses_uv_tool_install_when_running_from_uv_environment(monkeypatch):
    from click.testing import CliRunner

    calls = []

    monkeypatch.setattr(cli_module.sys, "executable", "/tmp/uv/tools/young-stock-cli/bin/python")
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/opt/homebrew/bin/uv" if name == "uv" else None)

    def fake_run(cmd, check=False, capture_output=False, text=False, encoding=None, errors=None):
        calls.append((cmd, check, capture_output, text, encoding, errors))
        if cmd[1:] == ["tool", "list"]:
            return SimpleNamespace(returncode=0, stdout="young-stock-cli\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(cli, ["update", "--pre"])

    assert result.exit_code == 0
    assert calls[0][0] == ["/opt/homebrew/bin/uv", "tool", "list"]
    assert calls[1][0] == [
        "/opt/homebrew/bin/uv",
        "tool",
        "install",
        "--upgrade",
        "--prerelease",
        "allow",
        "young-stock-cli",
    ]


def test_cli_update_falls_back_to_pip_when_uv_probe_fails(monkeypatch):
    from click.testing import CliRunner

    calls = []

    monkeypatch.setattr(cli_module.sys, "executable", "/tmp/uv/tools/young-stock-cli/bin/python")
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/opt/homebrew/bin/uv" if name == "uv" else None)

    def fake_run(cmd, check=False, capture_output=False, text=False, encoding=None, errors=None):
        calls.append((cmd, check, capture_output, text, encoding, errors))
        if cmd[1:] == ["tool", "list"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="boom")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(cli, ["update"])

    assert result.exit_code == 0
    assert calls[0][0] == ["/opt/homebrew/bin/uv", "tool", "list"]
    assert calls[1][0] == [cli_module.sys.executable, "-m", "pip", "install", "--upgrade", "young-stock-cli"]


def test_cli_uninstall_uses_uv_tool_uninstall_when_running_from_uv_environment(monkeypatch):
    from click.testing import CliRunner

    calls = []

    monkeypatch.setattr(cli_module.sys, "executable", "/tmp/uv/tools/young-stock-cli/bin/python")
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/opt/homebrew/bin/uv" if name == "uv" else None)

    def fake_run(cmd, check=False, capture_output=False, text=False, encoding=None, errors=None):
        calls.append((cmd, check, capture_output, text, encoding, errors))
        if cmd[1:] == ["tool", "list"]:
            return SimpleNamespace(returncode=0, stdout="young-stock-cli\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(cli, ["uninstall"])

    assert result.exit_code == 0
    assert calls[0][0] == ["/opt/homebrew/bin/uv", "tool", "list"]
    assert calls[1][0] == ["/opt/homebrew/bin/uv", "tool", "uninstall", "young-stock-cli"]


def test_cli_update_does_not_treat_an_unrelated_tools_directory_as_uv(monkeypatch):
    from click.testing import CliRunner

    calls = []

    monkeypatch.setattr(cli_module.sys, "executable", "/opt/tools/project/.venv/bin/python")
    monkeypatch.setattr(cli_module.shutil, "which", lambda name: "/opt/homebrew/bin/uv" if name == "uv" else None)

    def fake_run(cmd, check=False, capture_output=False, text=False, encoding=None, errors=None):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="young-stock-cli v0.1.17\n", stderr="")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    result = CliRunner().invoke(cli, ["update"])

    assert result.exit_code == 0
    assert calls == [[cli_module.sys.executable, "-m", "pip", "install", "--upgrade", "young-stock-cli"]]


def test_cli_report_help_says_pdf_only():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["report", "--help"])

    assert result.exit_code == 0
    assert "PDF only" in result.output


def test_cli_daily_removed_only_and_quick_options_are_rejected():
    from click.testing import CliRunner

    runner = CliRunner()

    result = runner.invoke(cli, ["daily", "--only", "基金,A股"])
    assert result.exit_code != 0
    assert "No such option" in result.output
    assert "--only" in result.output

    result = runner.invoke(cli, ["daily", "--quick"])
    assert result.exit_code != 0
    assert "No such option" in result.output
    assert "--quick" in result.output


def test_cli_replay_command_is_removed():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["replay"])

    assert result.exit_code != 0
    assert "No such command 'replay'" in result.output


def test_cli_send_help_mentions_optional_pdf():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["send", "--help"])

    assert result.exit_code == 0
    assert "latest Markdown report and summary" in result.output
    assert "same-name PDF only" in result.output
    assert "when it exists" in result.output


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
            "--list",
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
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260529")
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
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260529")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    _patch_profile_validation(monkeypatch)

    calls = []
    monkeypatch.setattr(
        cli_module._core,
        "run_daily_report",
        lambda date_str, watchlist=None, include_news=True, report_format="full", order=None: calls.append(
            (date_str, watchlist, include_news, report_format, order)
        ),
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["profile", "add-stock", "600519", "--buy-date", "2026-01-15", "--quantity", "100"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0

    result = runner.invoke(cli, ["daily", "--no-news", "--format", "summary"])

    assert result.exit_code == 0
    assert calls == [(
        "20260529",
        {
            "stocks": ["600519"],
            "funds": ["161725"],
            "groups": {},
            "classifications": {
                "stocks": {
                    "600519": {
                        "market": "A股",
                        "asset_type": "股票",
                        "category": "待观察",
                        "style": "待观察",
                        "evidence": ["market=cn_market", "symbol=600519"],
                    }
                }
            },
            "positions": {
                "stocks": {"600519": {"buy_date": "2026-01-15", "quantity": 100.0}},
                "funds": {"161725": {"buy_date": "2026-02-01", "quantity": 1000.0}},
            },
        },
        False,
        "summary",
        None,
    )]


def test_cli_profile_group_commands_are_removed(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    runner = CliRunner()

    help_result = runner.invoke(cli, ["profile", "--help"])
    removed_result = runner.invoke(cli, ["profile", "group", "create", "成长型"])

    assert help_result.exit_code == 0
    assert "group" not in help_result.output
    assert removed_result.exit_code != 0
    assert "No such command 'group'" in removed_result.output


def test_cli_profile_remove_and_clear_clean_classifications(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    _patch_profile_validation(monkeypatch)
    runner = CliRunner()

    assert runner.invoke(cli, ["profile", "add-stock", "600519", "--buy-date", "2026-01-15", "--quantity", "100"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0

    listed = runner.invoke(cli, ["profile", "list"])
    assert listed.exit_code == 0
    assert "600519" in listed.output
    assert "自动分类" in listed.output
    assert "classifications" not in listed.output
    assert "groups" not in listed.output

    assert runner.invoke(cli, ["profile", "remove-stock", "600519"]).exit_code == 0
    after_remove = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_remove.output
    assert "600519" not in cli_module.load_profile()["classifications"]["stocks"]

    assert runner.invoke(cli, ["profile", "add-stock", "000001", "--buy-date", "2026-01-20", "--quantity", "200"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear-stocks"]).exit_code == 0
    after_clear_stocks = runner.invoke(cli, ["profile", "list"])
    assert "Stocks: -" in after_clear_stocks.output
    assert "Funds: 161725" in after_clear_stocks.output
    assert cli_module.load_profile()["classifications"]["stocks"] == {}

    assert runner.invoke(cli, ["profile", "clear-funds"]).exit_code == 0
    after_clear_funds = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear_funds.output

    assert runner.invoke(cli, ["profile", "add-fund", "161725", "--buy-date", "2026-02-01", "--quantity", "1000"]).exit_code == 0
    assert runner.invoke(cli, ["profile", "clear"]).exit_code == 0
    after_clear = runner.invoke(cli, ["profile", "list"])
    assert "Funds: -" in after_clear.output


def test_cli_profile_remove_stock_also_cleans_legacy_groups(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    cli_module.profile_path().write_text(
        json.dumps(
            {
                "stocks": ["600519"],
                "funds": [],
                "groups": {"旧分组": {"stocks": ["600519", "000001"], "funds": []}},
                "classifications": {"stocks": {"600519": {"market": "A股", "asset_type": "股票", "style": "消费", "evidence": ["name=贵州茅台"]}}},
                "positions": {"stocks": {"600519": {"buy_date": "2026-01-15", "quantity": 100}}, "funds": {}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["profile", "remove-stock", "600519"])

    assert result.exit_code == 0
    assert cli_module.load_profile()["groups"] == {"旧分组": {"stocks": ["000001"], "funds": []}}


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
    assert "自动分类" in valid.output
    assert cli_module.load_profile()["stocks"] == ["600519"]
    assert cli_module.load_profile()["classifications"]["stocks"]["600519"] == {
        "market": "A股",
        "asset_type": "股票",
        "category": "消费",
        "style": "消费",
        "evidence": ["market=cn_market", "name=贵州茅台", "keyword=茅台"],
    }


def test_cli_profile_add_stock_uses_evidence_based_category_tags(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    quotes = {
        "0700.HK": cli_module._core.QuoteData(
            symbol="0700.HK",
            name="腾讯控股 ETF",
            market="hk_market",
            date="20260529",
            price=500.0,
            change_pct=1.2,
            source="test",
        ),
        "300750": cli_module._core.QuoteData(
            symbol="300750",
            name="宁德时代",
            market="cn_market",
            date="20260529",
            price=220.0,
            change_pct=1.2,
            source="test",
        ),
    }
    monkeypatch.setattr(cli_module._core, "get_single_stock_quote", lambda symbol, date: quotes[symbol])

    etf = CliRunner().invoke(cli, ["profile", "add-stock", "0700.HK", "--buy-date", "2026-01-15", "--quantity", "200"])
    growth = CliRunner().invoke(cli, ["profile", "add-stock", "300750", "--buy-date", "2026-01-15", "--quantity", "50"])

    assert etf.exit_code == 0
    assert "主题ETF" in etf.output
    assert cli_module.load_profile()["classifications"]["stocks"]["0700.HK"] == {
        "market": "港股",
        "asset_type": "ETF",
        "category": "主题ETF",
        "style": "主题ETF",
        "evidence": ["market=hk_market", "name=腾讯控股 ETF", "symbol=0700.HK", "asset_type=ETF"],
    }

    assert growth.exit_code == 0
    assert "创业板" in growth.output
    assert cli_module.load_profile()["classifications"]["stocks"]["300750"] == {
        "market": "A股",
        "asset_type": "股票",
        "category": "创业板",
        "style": "创业板",
        "evidence": ["market=cn_market", "symbol=300750", "board=创业板"],
    }


def test_cli_profile_add_stock_does_not_call_research_bridge(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setenv(cli_module.RESEARCH_COMMAND_ENV, "dummy-bridge")
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260529")
    monkeypatch.setattr(
        cli_module._core,
        "get_single_stock_quote",
        lambda symbol, date: cli_module._core.QuoteData(
            symbol="688111",
            name="金山办公",
            market="cn_market",
            date=date,
            price=300.0,
            change_pct=1.0,
            source="test",
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "run_research_bridge",
        lambda query: (_ for _ in ()).throw(AssertionError("profile add-stock 不应触发 research bridge")),
    )

    result = CliRunner().invoke(cli, ["profile", "add-stock", "688111", "--buy-date", "2026-01-15", "--quantity", "20"])

    assert result.exit_code == 0
    assert "深度分析可补充" in result.output
    assert cli_module.load_profile()["classifications"]["stocks"]["688111"]["category"] == "科创板"


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

    assert runner.invoke(cli, ["alert", "list"]).exit_code != 0
    assert runner.invoke(cli, ["note", "list"]).exit_code != 0

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
    assert "young config show" in result.output
    assert "young config models --help" in result.output
    assert "可选：完成配置后再运行 young daily --format summary / young daily --llm / young report" in result.output
    assert (tmp_path / "young-home" / "config.json").exists()
    assert (tmp_path / "young-home" / "reports").exists()
    assert (tmp_path / "profile.json").exists()


def test_cli_diagnose_outputs_network_guidance(monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setattr(cli_module._core, "SOURCE_HEALTH", SimpleNamespace(snapshot=lambda name: SimpleNamespace(success_rate=0.25, average_latency_ms=1200, should_skip=True)))
    monkeypatch.delenv("YOUNG_STOCK_RESEARCH_COMMAND", raising=False)

    result = CliRunner().invoke(cli, ["diagnose"])

    assert result.exit_code == 0
    assert "网络诊断" in result.output
    assert "建议" in result.output
    assert "YOUNG_STOCK_RESEARCH_COMMAND" in result.output


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


def test_cli_config_models_saves_and_masks_secret(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    saved = runner.invoke(
        cli,
        [
            "config",
            "models",
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


def test_cli_config_show_is_human_readable_and_masks_secrets(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()
    assert runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key",
            "very-secret",
            "--api-base",
            "https://api.deepseek.com",
        ],
    ).exit_code == 0

    shown = runner.invoke(cli, ["config", "show"])

    assert shown.exit_code == 0
    assert "{" not in shown.output
    assert "}" not in shown.output
    assert "provider: deepseek" in shown.output
    assert "model: deepseek-chat" in shown.output
    assert "api_key" not in shown.output
    assert "very-secret" not in shown.output


def test_cli_config_channel_list_is_human_readable_and_masks_secrets(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()
    assert runner.invoke(
        cli,
        [
            "config",
            "channel",
            "add",
            "feishu",
            "work",
            "--webhook",
            "https://example.test/hook/secret-token",
        ],
    ).exit_code == 0

    listed = runner.invoke(cli, ["config", "channel", "list"])

    assert listed.exit_code == 0
    assert "{" not in listed.output
    assert "}" not in listed.output
    assert "work" in listed.output
    assert "feishu" in listed.output
    assert "secret-token" not in listed.output
    assert "webhook" in listed.output


def test_cli_config_models_persists_all_core_fields(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", "env-secret")
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key-env",
            "MODEL_KEY",
            "--api-base",
            "https://api.deepseek.com",
            "--timeout",
            "45",
            "--max-tokens",
            "8192",
        ],
    )

    assert result.exit_code == 0
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    llm = config["llm"]
    assert llm["provider"] == "deepseek"
    assert llm["model"] == "deepseek-chat"
    assert llm["api_key_env"] == "MODEL_KEY"
    assert llm["api_key"] == "env-secret"
    assert llm["api_base"] == "https://api.deepseek.com"
    assert llm["timeout"] == 45
    assert llm["max_tokens"] == 8192


def test_cli_config_models_preserves_saved_fields_when_only_model_changes(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    initial = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key",
            "saved-secret",
            "--api-key-env",
            "MODEL_KEY",
            "--api-base",
            "https://api.deepseek.com",
            "--timeout",
            "45",
            "--max-tokens",
            "8192",
        ],
    )
    assert initial.exit_code == 0

    result = runner.invoke(cli, ["config", "models", "--model", "deepseek-reasoner"])

    assert result.exit_code == 0
    llm = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["llm"]
    assert llm["provider"] == "deepseek"
    assert llm["model"] == "deepseek-reasoner"
    assert llm["api_key"] == "saved-secret"
    assert llm["api_key_env"] == "MODEL_KEY"
    assert llm["api_base"] == "https://api.deepseek.com"
    assert llm["timeout"] == 45
    assert llm["max_tokens"] == 8192


def test_cli_config_models_with_api_key_env_persists_fallback(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", "env-secret")
    runner = CliRunner()

    saved = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key-env",
            "MODEL_KEY",
        ],
    )

    assert saved.exit_code == 0
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["api_key_env"] == "MODEL_KEY"
    assert config["llm"]["api_key"] == "env-secret"


def test_cli_config_models_uses_saved_key_after_env_changes(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from young_stock.llm import LLMClient

    class FakeSession:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return self.responses.pop(0)

    def response(status, payload):
        return SimpleNamespace(status_code=status, json=lambda: payload, text=str(payload), headers={})

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", "  'saved-secret'  ")
    runner = CliRunner()

    saved = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--api-key-env",
            "MODEL_KEY",
        ],
    )
    assert saved.exit_code == 0

    monkeypatch.setenv("MODEL_KEY", "wrong-secret")
    client = LLMClient(
        json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["llm"],
        session=FakeSession([response(200, {"choices": [{"message": {"content": "ok"}}]})]),
    )

    client.chat([{"role": "user", "content": "hi"}])

    assert client.session.calls[0][1]["headers"]["Authorization"] == "Bearer saved-secret"


def test_cli_config_show_migrates_legacy_api_key_env_fallback(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("MODEL_KEY", "  'env-secret'  ")
    (tmp_path / "config.json").write_text(
        json.dumps({"schema_version": 1, "llm": {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "MODEL_KEY"}}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["llm"]["api_key"] == "env-secret"


def test_cli_config_llm_command_redirects_to_models():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["config", "llm", "--help"])

    assert result.exit_code != 0
    assert "young config models" in result.output


def test_cli_config_models_lists_endpoint_model_ids_only_with_list(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    cli_module.update_llm_config(provider="ark", model="seed", api_key="secret")

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def list_models(self):
            return ["model-a", "model-b"]

    monkeypatch.setattr(cli_module, "LLMClient", DummyClient)

    result = CliRunner().invoke(cli, ["config", "models", "--list"])

    assert result.exit_code == 0
    assert result.output.strip().splitlines() == ["model-a", "model-b"]


def test_cli_config_models_list_surfaces_clean_llm_error(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    cli_module.update_llm_config(provider="ark", model="seed", api_key="secret")

    class DummyClient:
        def __init__(self, config):
            self.config = config

        def list_models(self):
            raise cli_module.LLMError("模型列表返回了非 JSON 响应，无法解析。")

    monkeypatch.setattr(cli_module, "LLMClient", DummyClient)

    result = CliRunner().invoke(cli, ["config", "models", "--list"])

    assert result.exit_code != 0
    assert "模型列表返回了非 JSON 响应，无法解析。" in result.output
    assert "secret" not in result.output


def test_cli_config_models_requires_model_or_list():
    from click.testing import CliRunner

    result = CliRunner().invoke(cli, ["config", "models", "--provider", "ark"])

    assert result.exit_code != 0
    assert "请提供 --model" in result.output


def test_cli_config_models_accepts_repeatable_fallback_model(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "config",
            "models",
            "--provider",
            "deepseek",
            "--model",
            "primary-model",
            "--fallback-model",
            "fallback-a",
            "--fallback-model",
            "primary-model",
            "--fallback-model",
            "fallback-a",
            "--fallback-model",
            "fallback-b",
        ],
    )

    assert result.exit_code == 0
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert config["llm"]["fallback_models"] == ["fallback-a", "fallback-b"]


def test_cli_config_show_keeps_fallback_model_list(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    cli_module.save_config(
        {
            "llm": {
                "provider": "deepseek",
                "model": "primary-model",
                "fallback_models": ["fallback-a", "fallback-b"],
                "api_key": "secret-value",
            }
        }
    )

    result = CliRunner().invoke(cli, ["config", "show"])

    assert result.exit_code == 0
    assert "fallback models: fallback-a, fallback-b" in result.output


def test_cli_config_channel_add_persists_app_delivery_fields(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "config",
            "channel",
            "add",
            "feishu",
            "work",
            "--app-id",
            "cli_a1",
            "--app-secret",
            "secret-123",
            "--receive-id",
            "oc_test_chat",
            "--receive-id-type",
            "chat_id",
        ],
    )

    assert result.exit_code == 0
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    channel = config["channels"]["feishu"]["work"]
    assert channel["app_id"] == "cli_a1"
    assert channel["app_secret"] == "secret-123"
    assert channel["receive_id"] == "oc_test_chat"
    assert channel["receive_id_type"] == "chat_id"


def test_cli_daily_llm_uses_enhanced_path(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_daily_llm",
        lambda date_str, **kwargs: calls.append((date_str, kwargs)),
    )

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert calls == [
        (
            "20260618",
            {"refresh": False, "no_news": False, "report_format": "full", "order": None},
        )
    ]


def test_cli_daily_llm_passes_lens_and_debate_rounds(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    calls = []
    monkeypatch.setattr(cli_module, "_run_daily_llm", lambda date_str, **kwargs: calls.append((date_str, kwargs)))

    result = CliRunner().invoke(cli, ["daily", "--llm", "--lens", "all", "--debate-rounds", "4"])

    assert result.exit_code == 0
    assert calls[0][1]["lens"] == "all"
    assert calls[0][1]["debate_rounds"] == 4


def test_cli_analyze_accepts_every_lens_and_configurable_debate(monkeypatch):
    from click.testing import CliRunner

    calls = []
    monkeypatch.setattr(cli_module, "_default_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "_run_llm_replay", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = CliRunner().invoke(
        cli,
        ["analyze", "600519", "--llm", "--lens", "feng_liu"],
    )

    assert result.exit_code == 0
    assert calls[0][1] == {
        "kind": "analyze",
        "symbol": "600519",
        "lens": "feng_liu",
    }


def test_cli_style_set_uses_the_same_registered_lenses_as_slash_style(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))

    result = CliRunner().invoke(cli, ["style", "set", "zhang_kun"])

    assert result.exit_code == 0
    assert cli_module.load_config(strict=False)["chat"]["analysis_framework"] == "zhang_kun"


def test_cli_daily_without_llm_stays_on_deterministic_path(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    daily_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_plain_daily",
        lambda date_str, profile, **kwargs: daily_calls.append((date_str, profile, kwargs)),
    )
    monkeypatch.setattr(
        cli_module,
        "_run_daily_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("plain daily must not invoke LLM path")),
    )

    result = CliRunner().invoke(cli, ["daily", "--format", "summary"])

    assert result.exit_code == 0
    assert daily_calls == [
        (
            "20260618",
            {"stocks": ["600519"], "funds": []},
            {"no_news": False, "report_format": "summary", "order": None},
        )
    ]


def test_cli_daily_llm_reuses_existing_markdown(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    report_dir = tmp_path / "reports" / "20260618"
    report_dir.mkdir(parents=True)
    markdown = report_dir / "20260618-盘后-A股深度复盘.md"
    markdown.write_text("# deep replay\n", encoding="utf-8")

    llm_calls = []
    monkeypatch.setattr(cli_module, "_run_llm_replay", lambda *args, **kwargs: llm_calls.append((args, kwargs)))

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert llm_calls == []
    assert "deep replay" in result.output
    assert str(markdown) in result.output


def test_cli_daily_llm_existing_markdown_does_not_export_pdf(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    report_dir = tmp_path / "reports" / "20260618"
    report_dir.mkdir(parents=True)
    markdown = report_dir / "20260618-盘后-A股深度复盘.md"
    markdown.write_text("# deep replay\n", encoding="utf-8")

    llm_calls = []
    monkeypatch.setattr(cli_module, "_run_llm_replay", lambda *args, **kwargs: llm_calls.append((args, kwargs)))

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code == 0
    assert llm_calls == []
    assert "PDF:" not in result.output


def test_cli_daily_llm_refresh_rebuilds_markdown_only(monkeypatch, tmp_path):
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    report_dir = tmp_path / "reports" / "20260618"
    report_dir.mkdir(parents=True)
    markdown = report_dir / "20260618-盘后-A股深度复盘.md"
    markdown.write_text("# old replay\n", encoding="utf-8")

    llm_calls = []
    def fake_run_llm_replay(date_str, kind="replay", symbol=None):
        llm_calls.append((date_str, kind, symbol))
        click.echo("# fresh replay")
        return markdown

    monkeypatch.setattr(cli_module, "_run_llm_replay", fake_run_llm_replay)

    result = CliRunner().invoke(cli, ["daily", "--llm", "--refresh"])

    assert result.exit_code == 0
    assert llm_calls == [("20260618", "replay", None)]
    assert "fresh replay" in result.output
    assert "PDF:" not in result.output


def test_cli_daily_llm_falls_back_without_configuration(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from young_stock.llm import LLMNotConfigured

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})

    daily_calls = []
    monkeypatch.setattr(
        cli_module,
        "_run_llm_replay",
        lambda *args, **kwargs: (_ for _ in ()).throw(LLMNotConfigured("未配置 LLM，请运行 `young config models --help`。")),
    )
    monkeypatch.setattr(
        cli_module._core,
        "run_daily_report",
        lambda date_str, profile, include_news=True, report_format="full", order=None: daily_calls.append(
            (date_str, profile, include_news, report_format, order)
        ),
    )

    result = CliRunner().invoke(cli, ["daily", "--llm", "--no-news", "--format", "summary"])

    assert result.exit_code == 0
    assert "已回退到普通 daily" in result.output
    assert "young config models --help" in result.output
    assert daily_calls == [("20260618", {"stocks": ["600519"], "funds": []}, False, "summary", None)]


def test_cli_daily_llm_does_not_swallow_other_llm_errors(monkeypatch, tmp_path):
    import click
    from click.testing import CliRunner

    monkeypatch.setenv("YOUNG_STOCK_HOME", str(tmp_path))
    monkeypatch.setenv("YOUNG_STOCK_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setattr(cli_module._core, "nearest_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module, "latest_report_trade_date", lambda: "20260618")
    monkeypatch.setattr(cli_module._core, "cache_clear_old", lambda days: None)
    monkeypatch.setattr(cli_module, "load_profile", lambda: {"stocks": ["600519"], "funds": []})
    monkeypatch.setattr(
        cli_module,
        "_run_llm_replay",
        lambda *args, **kwargs: (_ for _ in ()).throw(click.ClickException("认证失败")),
    )

    result = CliRunner().invoke(cli, ["daily", "--llm"])

    assert result.exit_code != 0
    assert "认证失败" in result.output
    assert "已回退到普通 daily" not in result.output


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
