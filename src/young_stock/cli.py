"""young-stock-cli command line interface."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from click.core import ParameterSource

from . import __version__, _core
from .artifacts import ReportArtifacts, ReportIdentity, report_session
from .calendar import latest_report_trade_date
from .config import (
    add_feishu_channel,
    config_path,
    is_kimi_coding_api_base,
    kimi_coding_plan_unsupported_message,
    load_config,
    load_effective_config,
    mask_config,
    migrate_legacy_llm_api_key_fallback,
    normalize_api_base,
    remove_feishu_channel,
    save_config,
    update_llm_config,
)
from .evidence import build_daily_evidence, build_fund_evidence, build_stock_evidence
from .lens.registry import lens_ids
from .llm import LLMClient, LLMError, LLMNotConfigured
from .local_store import load_store, now_label, save_store, young_home
from .mcp_server import serve_stdio
from .methodology import load_builtin_methodology
from .model_transport.registry import model_transport_for_config, transport_ids
from .model_transport.subscription_cli import subscription_cli_provider_ids
from .profile import (
    add_profile_item,
    clear_profile,
    clear_profile_kind,
    load_profile,
    profile_path,
    remove_profile_item,
    save_profile,
)
from .providers import provider_ids, provider_spec, provider_specs
from .reports import generate_llm_daily_report
from .research_bridge import RESEARCH_COMMAND_ENV, run_research_bridge
from .sources.extras import collect_stock_extras, fetch_lhb

MODEL_PROVIDER_IDS = tuple(dict.fromkeys((*provider_ids(), *subscription_cli_provider_ids())))


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="A-share & global market after-hours CLI. No login, no scraping tricks.",
)
@click.version_option(__version__, "-V", "--version", message="young-stock-cli %(version)s")
def cli() -> None:
    pass


@cli.command(name="mcp", help="Run the read-only MCP stdio server.")
def mcp() -> None:
    serve_stdio()


@cli.result_callback()
def _reset_cli_runtime_flags(*_args: object, **_kwargs: object) -> None:
    _core.NO_CACHE = False


def _run(market: str, date: str | None, refresh: bool, include_news: bool = True) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    if market == "a":
        _core.run_a_share(date_str, include_news=include_news)
    elif market == "hk":
        _core.run_hk_market(date_str, include_news=include_news)
    elif market == "us":
        _core.run_us_market(date_str, include_news=include_news)
    elif market == "global":
        _core.run_global_market(date_str)
    else:
        click.echo(f"unknown market: {market}", err=True)
        sys.exit(1)


_date_opt = click.option("--date", "-d", default=None, help="Trade date YYYYMMDD (default: nearest trade day).")
_refresh_opt = click.option("--refresh", is_flag=True, help="Skip cache and force re-fetch.")


def _print_first_use_guide() -> None:
    click.echo("# 每日行情日报")
    click.echo()
    click.echo("尚未设置投资记忆。首次使用请先添加你关注的股票、ETF 或基金，并补充买入日期和数量。系统会基于 quote 自动给出可解释标签：")
    click.echo("  young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("  young profile add-stock 0700.HK --buy-date 2026-01-15 --quantity 200")
    click.echo("  young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000")
    click.echo()
    click.echo(f"配置会保存到: {profile_path()}")


def _mask_for_human(value: object) -> str:
    text = str(value or "").strip()
    return text or "-"


def _render_config_lines(config_data: dict[str, object]) -> list[str]:
    lines = ["- schema_version: " + str(config_data.get("schema_version", "-"))]
    llm = config_data.get("llm", {}) if isinstance(config_data.get("llm", {}), dict) else {}
    lines.extend(
        [
            "- LLM",
            f"  - transport: {_mask_for_human(llm.get('transport') or ('api' if llm else ''))}",
            f"  - provider: {_mask_for_human(llm.get('provider'))}",
            f"  - model: {_mask_for_human(llm.get('model'))}",
            f"  - api_base: {_mask_for_human(llm.get('api_base'))}",
            f"  - credential env: {_mask_for_human(llm.get('api_key_env'))}",
            f"  - credential: {'已配置(已遮蔽)' if llm.get('api_key') else '-'}",
            f"  - fallback models: {', '.join(llm.get('fallback_models', [])) if llm.get('fallback_models') else '-'}",
            f"  - timeout: {_mask_for_human(llm.get('timeout'))}",
            f"  - max_tokens: {_mask_for_human(llm.get('max_tokens'))}",
        ]
    )
    channels = config_data.get("channels", {}) if isinstance(config_data.get("channels", {}), dict) else {}
    feishu = channels.get("feishu", {}) if isinstance(channels.get("feishu", {}), dict) else {}
    lines.append("- Channels")
    if not feishu:
        lines.append("  - feishu: -")
    else:
        for name, channel in sorted(feishu.items()):
            if not isinstance(channel, dict):
                continue
            lines.extend(
                [
                    f"  - {name} (feishu)",
                    f"    - webhook: {_mask_for_human(channel.get('webhook'))}",
                    f"    - app_id: {_mask_for_human(channel.get('app_id'))}",
                    f"    - app_secret: {'已配置(已遮蔽)' if channel.get('app_secret') else '-'}",
                    f"    - tenant_access_token: {'已配置(已遮蔽)' if channel.get('tenant_access_token') else '-'}",
                    f"    - receive_id: {_mask_for_human(channel.get('receive_id'))}",
                    f"    - receive_id_type: {_mask_for_human(channel.get('receive_id_type'))}",
                ]
            )
    return lines


def _render_channel_lines(channels: dict[str, object]) -> list[str]:
    feishu = channels.get("feishu", {}) if isinstance(channels.get("feishu", {}), dict) else {}
    if not feishu:
        return ["- 暂无已配置渠道"]
    lines: list[str] = []
    for name, channel in sorted(feishu.items()):
        if not isinstance(channel, dict):
            continue
        lines.extend(
            [
                f"- {name} | type=feishu",
                f"  - webhook: {_mask_for_human(channel.get('webhook'))}",
                f"  - receive_id: {_mask_for_human(channel.get('receive_id'))}",
                f"  - receive_id_type: {_mask_for_human(channel.get('receive_id_type'))}",
                f"  - app_id: {_mask_for_human(channel.get('app_id'))}",
                f"  - app_secret: {'已配置(已遮蔽)' if channel.get('app_secret') else '-'}",
                f"  - tenant_access_token: {'已配置(已遮蔽)' if channel.get('tenant_access_token') else '-'}",
            ]
        )
    return lines


def _classify_market(market: str) -> str:
    return {
        "cn_market": "A股",
        "hk_market": "港股",
        "us_market": "美股",
    }.get(market, market or "待识别市场")


def _classify_asset_type(symbol: str, name: str) -> tuple[str, list[str]]:
    symbol_upper = symbol.upper()
    name_upper = name.upper()
    if symbol_upper.startswith("^") or "INDEX" in name_upper or "指数" in name:
        return "指数", [f"name={name}" if name else "", f"symbol={symbol}"]
    if "ETF" in symbol_upper or "ETF" in name_upper:
        return "ETF", [f"name={name}" if name else "", f"symbol={symbol}"]
    if symbol.isdigit() and len(symbol) == 6 and symbol.startswith(("15", "16", "18", "50", "51", "56", "58")):
        return "ETF", [f"symbol={symbol}"]
    return "股票", [f"symbol={symbol}"]


_BOARD_PREFIXES = (
    ("688", "科创板"),
    ("689", "科创板"),
    ("300", "创业板"),
    ("301", "创业板"),
    ("8", "北交所"),
    ("4", "北交所"),
)

_CATEGORY_KEYWORDS = (
    ("消费", ("茅台", "白酒", "啤酒", "消费", "乳业", "食品", "饮料", "零售", "家电")),
    ("金融", ("银行", "证券", "券商", "保险", "信托", "金控")),
    ("科技", ("科技", "电子", "芯片", "半导体", "软件", "计算机", "通信", "互联网", "云", "AI")),
    ("周期", ("煤", "煤炭", "有色", "钢铁", "化工", "石油", "天然气", "航运", "建材")),
    ("医药", ("医药", "生物", "制药", "医疗", "医院", "疫苗")),
    ("公用事业", ("电力", "燃气", "水务", "电网", "公用", "环保")),
)

_ETF_INDEX_TERMS = ("沪深300", "中证500", "中证1000", "上证50", "科创50", "创业板指", "恒生", "纳指", "标普")


def _detect_a_share_board(symbol: str, market: str) -> tuple[str | None, str | None]:
    if market != "cn_market" or not symbol.isdigit():
        return None, None
    for prefix, board in _BOARD_PREFIXES:
        if symbol.startswith(prefix):
            return board, f"board={board}"
    return None, None


def _keyword_category(name: str) -> tuple[str | None, str | None]:
    for category, keywords in _CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in name:
                return category, f"keyword={keyword}"
    return None, None


def _classification_hint() -> str | None:
    if os.environ.get(RESEARCH_COMMAND_ENV):
        return "深度分析可补充：已检测到可选 research bridge；add-stock 当前不会主动联网。"
    return None


def _build_stock_classification(symbol: str, name: str, market: str, quote: Any | None = None) -> dict[str, object]:
    asset_type, asset_evidence = _classify_asset_type(symbol, name)
    evidence = [f"market={market}"]
    for item in asset_evidence:
        if item and item not in evidence:
            evidence.append(item)
    category = "待观察"
    board, board_evidence = _detect_a_share_board(symbol, market)
    keyword_category, keyword_evidence = _keyword_category(name)
    # ponytail: 单标签优先级保持可解释且足够便宜；当前只看 symbol/name/quote 基础字段，后续若要更细可接行业元数据表。
    if asset_type == "ETF":
        category = "主题ETF"
        if f"name={name}" not in evidence and name:
            evidence.insert(1, f"name={name}")
        if f"symbol={symbol}" not in evidence:
            evidence.append(f"symbol={symbol}")
        evidence.append("asset_type=ETF")
        if any(term in name for term in _ETF_INDEX_TERMS):
            category = "指数ETF"
    elif asset_type == "指数":
        category = "指数"
    elif keyword_category and keyword_evidence:
        category = keyword_category
        evidence = [f"market={market}", f"name={name}", keyword_evidence]
    elif board and board_evidence:
        category = board
        evidence = [f"market={market}", f"symbol={symbol}", board_evidence]
    return {
        "market": _classify_market(market),
        "asset_type": asset_type,
        "category": category,
        "style": category,
        "evidence": evidence,
    }


def _profile_classification_line(code: str, classification: dict[str, object]) -> str:
    market = classification.get("market") or "待识别市场"
    asset_type = classification.get("asset_type") or "待识别资产"
    category = classification.get("category") or classification.get("style") or "待观察"
    evidence = "；".join(str(item) for item in classification.get("evidence", []) if str(item).strip()) or "证据不足"
    return f"  {code}: {market} / {asset_type} / {category}（依据：{evidence}）"


def _current_report_date() -> str:
    return datetime.now().strftime("%Y%m%d")


def _default_report_trade_date() -> str:
    return latest_report_trade_date()


def _print_query_context(date_str: str) -> None:
    click.echo(f"查询日期: {date_str}")
    click.echo(f"当前阶段: {_core.dated_stage_label(requested_date=date_str)}")
    click.echo()


def _llm_report_identity(
    date_str: str,
    symbol: str | None = None,
    lens: str | None = None,
) -> ReportIdentity:
    topic = f"{symbol}深度分析" if symbol else "A股深度复盘"
    if lens and lens != "balanced":
        topic = f"{topic}-{lens}"
    return ReportIdentity(date_str, report_session(date_str), topic)


def _validate_llm_option_contract(
    *,
    use_llm: bool,
    lens: str | None,
    debate_rounds: int,
    debate_rounds_explicit: bool,
) -> None:
    if lens and not use_llm:
        raise click.ClickException("--lens requires --llm")
    if debate_rounds_explicit and debate_rounds != 3 and (not use_llm or lens != "all"):
        raise click.ClickException("--debate-rounds requires --llm and --lens all")


def _validate_analyze_symbol(symbol: str, date_str: str) -> str:
    try:
        quote = _core.get_single_stock_quote(symbol, date_str)
    except ValueError as exc:
        raise click.ClickException(_stock_invalid_message(symbol)) from exc
    if not quote or quote.price is None or quote.market not in {"cn_market", "hk_market", "us_market"}:
        raise click.ClickException(_stock_invalid_message(symbol))
    return str(quote.symbol or symbol)


def _run_plain_analyze(
    symbol: str,
    date_str: str,
    *,
    no_news: bool,
    rich_source: bool,
    browser_fallback: bool,
) -> None:
    normalized_symbol = _validate_analyze_symbol(symbol, date_str)
    _print_query_context(date_str)
    _core.run_stock_quote(normalized_symbol, date_str, include_news=not no_news)
    extras = collect_stock_extras(_core, normalized_symbol, date_str, rich_source=rich_source, include_news=not no_news)
    _print_stock_extras(extras.to_dict(), requested_date=date_str, browser_fallback=browser_fallback)


def _print_markdown_report(path: Path) -> None:
    from rich.console import Console
    from rich.markdown import Markdown

    Console().print(Markdown(path.read_text(encoding="utf-8")))


def _internal_research_fallback(symbol: str) -> dict[str, str]:
    query = f"{symbol} 最新财报 重大公告 公司新闻 投资风险"
    return run_research_bridge(query)


def _uv_tool_executable(tool_name: str) -> str | None:
    uv = shutil.which("uv")
    executable = Path(sys.executable).as_posix().lower()
    tool_path = tool_name.lower()
    if not uv or (
        f"/uv/tools/{tool_path}/" not in executable
        and f"/uv-tools/{tool_path}/" not in executable
    ):
        return None

    result = subprocess.run([uv, "tool", "list"], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return None

    for line in (result.stdout or "").splitlines():
        if line.strip().split()[0:1] == [tool_name]:
            return uv
    return None


def _run_plain_daily(
    date_str: str,
    profile: dict[str, object],
    *,
    no_news: bool,
    report_format: str,
    order: str | None,
) -> None:
    _core.run_daily_report(
        date_str,
        profile,
        include_news=not no_news,
        report_format=report_format,
        order=order,
    )


def _fallback_daily_without_llm(
    date_str: str,
    profile: dict[str, object],
    *,
    no_news: bool,
    report_format: str,
    order: str | None,
) -> None:
    click.echo("未配置可用 LLM，已回退到普通 daily。", err=True)
    click.echo("可先运行 `young config models --help` 完成 provider/model 配置或列出可用模型。", err=True)
    _run_plain_daily(
        date_str,
        profile,
        no_news=no_news,
        report_format=report_format,
        order=order,
    )


def _run_daily_llm(
    date_str: str,
    *,
    refresh: bool,
    no_news: bool,
    report_format: str,
    order: str | None,
    lens: str | None = None,
    debate_rounds: int = 3,
    rich_source: bool = False,
    browser_fallback: bool = False,
) -> None:
    profile = load_profile()
    if not profile.get("stocks") and not profile.get("funds"):
        _print_first_use_guide()
        return

    identity = _llm_report_identity(date_str, lens=lens)
    artifacts = ReportArtifacts(date_str)
    markdown_path = artifacts.path(identity.prefix, "md")

    if not refresh and markdown_path.exists():
        _print_markdown_report(markdown_path)
        click.echo(f"Markdown: {markdown_path}")
        return

    try:
        if refresh or not markdown_path.exists():
            replay_options = {}
            if lens:
                replay_options["lens"] = lens
            if lens == "all":
                replay_options["debate_rounds"] = debate_rounds
            if rich_source or browser_fallback:
                replay_options.update(
                    rich_source=rich_source,
                    browser_fallback=browser_fallback,
                )
            markdown_path = _run_llm_replay(date_str, **replay_options)
    except LLMNotConfigured:
        _fallback_daily_without_llm(
            date_str,
            profile,
            no_news=no_news,
            report_format=report_format,
            order=order,
        )
        return

    click.echo(f"Markdown: {markdown_path}")


@cli.command(help="A-share dashboard: indices, ZT/DT pool, verified A-share fund flow, boards.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
@click.option("--browser-fallback", is_flag=True, help="Allow browser fallback if a supporting capability decides it is needed.")
def a(date: str | None, refresh: bool, no_news: bool, browser_fallback: bool) -> None:
    _core.BROWSER_FALLBACK = browser_fallback
    _run("a", date, refresh, include_news=not no_news)


@cli.command(help="Hong Kong market after-hours snapshot.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
def hk(date: str | None, refresh: bool, no_news: bool) -> None:
    _run("hk", date, refresh, include_news=not no_news)


@cli.command(help="US market after-hours snapshot.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
def us(date: str | None, refresh: bool, no_news: bool) -> None:
    _run("us", date, refresh, include_news=not no_news)


@cli.command(name="global", help="Global indices snapshot (A + HK + US).")
@_date_opt
@_refresh_opt
def global_(date: str | None, refresh: bool) -> None:
    _run("global", date, refresh)


@cli.command(help="Update young-stock-cli with the current Python environment.")
@click.option("--pre", is_flag=True, help="Allow pre-release versions.")
@click.option("--user", "user_install", is_flag=True, help="Install to the user site-packages directory.")
def update(pre: bool, user_install: bool) -> None:
    uv = _uv_tool_executable("young-stock-cli")
    if uv:
        if user_install:
            raise click.ClickException("--user is a pip-only option; omit it when updating a uv tool install.")

        cmd = [uv, "tool", "install", "--upgrade"]
        if pre:
            cmd.extend(["--prerelease", "allow"])
        cmd.append("young-stock-cli")
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "young-stock-cli"]
        if pre:
            cmd.append("--pre")
        if user_install:
            cmd.append("--user")

    click.echo("Running: " + " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(
            "update failed with exit code "
            f"{result.returncode}. young-stock-cli requires Python 3.9+. "
            "Check `python3 --version`, then retry with "
            "`python3 -m pip install --upgrade young-stock-cli`；"
            "如果 `which young` 指向 uv tool 环境，请运行 "
            "`uv tool install --upgrade young-stock-cli`。"
        )


@cli.command(help="Uninstall young-stock-cli from the current Python environment.")
def uninstall() -> None:
    uv = _uv_tool_executable("young-stock-cli")
    if uv:
        cmd = [uv, "tool", "uninstall", "young-stock-cli"]
    else:
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y", "young-stock-cli"]
    click.echo("Running: " + " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise click.ClickException(f"uninstall failed with exit code {result.returncode}")


@cli.command(help="Show A-share major indices only.")
@_date_opt
@_refresh_opt
def indices(date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    data = _core.get_index(date_str)
    _core.print_stage_line(date_str)
    _core.print_index(data)


@cli.command(name="zt-pool", help="Show A-share limit-up (涨停) pool.")
@_date_opt
@_refresh_opt
def zt_pool(date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    zt = _core.get_zt_pool(date_str)
    dt = _core.get_dt_pool(date_str)
    zb = _core.get_zb_pool(date_str)
    _core.print_stage_line(date_str)
    _core.print_zt_analysis(zt, dt, zb)


@cli.command(help="Show market fund flow, northbound flow, or one-stock daily fund flow.")
@_date_opt
@_refresh_opt
@click.option("--stock", "symbol", default=None, help="Show one-stock daily fund flow, e.g. 600519, 0700.HK, AAPL.")
@click.option("--northbound", is_flag=True, help="Show A-share northbound intraday flow from THS.")
@click.option("--limit", default=20, show_default=True, type=int, help="Rows for --stock daily fund flow.")
def flow(date: str | None, refresh: bool, symbol: str | None, northbound: bool, limit: int) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    if northbound:
        _core.run_northbound_flow_report(date_str)
    elif symbol:
        _core.run_stock_fund_flow_report(symbol, date_str, limit=limit)
    else:
        flow_data = _core.get_fund_flow(date_str, strict_date=False)
        _core.print_fund_flow(flow_data)


_DISPLAY_LABELS = {
    "symbol": "股票代码",
    "date": "日期",
    "name": "名称",
    "reason": "上榜原因",
    "buy": "买入金额",
    "sell": "卖出金额",
    "net_buy": "净买入额",
    "ratio_trends": "财务指标趋势",
    "statements": "财务报表",
    "periods": "报告期数",
    "period": "报告期",
    "revenue": "营业收入",
    "net_profit": "净利润",
    "keyword": "关键词",
    "count": "记录数",
    "platform": "平台",
    "title": "标题",
    "content": "内容",
    "last_close": "最新收盘价",
    "ma20": "20日均线",
    "ma60": "60日均线",
}


def _display_label(key: object) -> str | None:
    text = str(key)
    if text.startswith("_"):
        return None
    if text in _DISPLAY_LABELS:
        return _DISPLAY_LABELS[text]
    return text if any("\u4e00" <= char <= "\u9fff" for char in text) else None


def _is_visible_value(value: object) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(not str(key).startswith("_") and _is_visible_value(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_is_visible_value(item) for item in value)
    return True


def _visible_items(payload: dict[str, object]) -> list[tuple[str, object]]:
    return [(key, value) for key, value in payload.items() if _display_label(key) and _is_visible_value(value)]


def _format_cell(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float):
        text = f"{value:.2f}"
        return text.rstrip("0").rstrip(".")
    return str(value)


def _table_lines(rows: list[dict[str, object]], preferred_columns: list[str] | tuple[str, ...] = ()) -> list[str]:
    if not rows:
        return []
    columns: list[str] = [
        column
        for column in preferred_columns
        if _display_label(column) and any(_is_visible_value(row.get(column)) for row in rows)
    ]
    for row in rows:
        for key in row:
            if key not in columns and _display_label(key) and any(_is_visible_value(r.get(key)) for r in rows):
                columns.append(key)
    if not columns:
        return []
    header = "| " + " | ".join(_display_label(column) or "" for column in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, divider]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(column)) for column in columns) + " |")
    return lines


def _render_nested_mapping(title: str, payload: dict[str, object], *, title_indent: str = "#### ") -> list[str]:
    lines: list[str] = []
    for key, value in _visible_items(payload):
        label = _display_label(key)
        if not label:
            continue
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            table = _table_lines([item for item in value if _is_visible_value(item)], ())
            if table:
                lines.extend(["", f"{title_indent}{label}", *table])
        elif isinstance(value, dict):
            nested_lines = _render_nested_mapping(label, value, title_indent="##### ")
            if nested_lines:
                lines.extend(["", f"{title_indent}{label}", *nested_lines])
        else:
            lines.append(f"- {label}: {_format_cell(value)}")
    return lines


def _normalized_date(value: object) -> str:
    return "".join(char for char in str(value or "") if char.isdigit())[:8]


def _render_section(title: str, payload: object, *, requested_date: str | None = None) -> list[str]:
    if not isinstance(payload, dict) or not _is_visible_value(payload):
        return []
    if title == "龙虎榜":
        target_date = _normalized_date(requested_date or payload.get("requested_date"))
        rows = [
            row for row in payload.get("rows") or []
            if (
                isinstance(row, dict)
                and (not target_date or not _normalized_date(row.get("date")) or _normalized_date(row.get("date")) == target_date)
                and any(_is_visible_value(row.get(field)) for field in ("reason", "buy", "sell", "net_buy"))
            )
        ]
        if not rows:
            return []
        return [f"### {title}", *_table_lines(rows, ("date", "name", "reason", "buy", "sell", "net_buy"))]
    if title == "社交热度":
        rows = [
            row for row in payload.get("rows") or []
            if isinstance(row, dict) and _is_visible_value(row)
        ]
        if not rows:
            return []
        lines = [f"### {title}"]
        for key in ("keyword", "count"):
            if _is_visible_value(payload.get(key)):
                lines.append(f"- {_display_label(key)}: {_format_cell(payload.get(key))}")
        table = _table_lines(rows, ("platform", "title"))
        return [*lines, "", *table] if table else []
    if title == "公告与事件":
        rows = [
            row for row in payload.get("rows") or []
            if isinstance(row, dict) and _is_visible_value(row)
        ]
        if not rows:
            return []
        table = _table_lines(rows, ("date", "title", "content"))
        return [f"### {title}", *table] if table else []
    if title == "五年财务趋势":
        lines: list[str] = []
        tables: list[str] = []
        for key, value in _visible_items(payload):
            if key == "ratio_trends" and isinstance(value, list):
                table = _table_lines([row for row in value if isinstance(row, dict) and _is_visible_value(row)])
                if table:
                    tables.extend(["", f"#### {_display_label(key)}", *table])
            elif key == "statements" and isinstance(value, dict):
                for statement_name, statement_rows in _visible_items(value):
                    if isinstance(statement_rows, list):
                        table = _table_lines([row for row in statement_rows if isinstance(row, dict) and _is_visible_value(row)])
                        if table:
                            tables.extend(["", f"#### {_display_label(statement_name)}", *table])
            elif not isinstance(value, (list, dict)):
                lines.append(f"- {_display_label(key)}: {_format_cell(value)}")
        if not tables:
            return []
        return [f"### {title}", *lines, *tables]

    lines: list[str] = []
    for key, value in _visible_items(payload):
        label = _display_label(key)
        if not label:
            continue
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            table = _table_lines([item for item in value if _is_visible_value(item)])
            if table:
                lines.extend(["", f"#### {label}", *table])
        elif isinstance(value, dict):
            nested = [line for line in _render_nested_mapping(label, value) if line]
            if nested:
                lines.extend(["", f"#### {label}", *nested])
        else:
            lines.append(f"- {label}: {_format_cell(value)}")
    return [f"### {title}", *lines] if lines else []


def _print_stock_extras(
    extras: dict[str, object],
    *,
    requested_date: str | None = None,
    browser_fallback: bool = False,
) -> None:
    click.echo("\n## 增强证据")
    shown = 0
    for key, title in (
        ("lhb", "龙虎榜"),
        ("financial_trends", "五年财务趋势"),
        ("social_heat", "社交热度"),
        ("events", "公告与事件"),
        ("technical_fallback", "技术指标补充"),
    ):
        section = _render_section(title, extras.get(key) or {}, requested_date=requested_date)
        if not section:
            continue
        shown += 1
        click.echo("")
        for line in section:
            click.echo(line)
    if shown == 0:
        click.echo("\n未返回可展示的增强证据。")
    if browser_fallback:
        click.echo("\n已允许浏览器回退；仅当某项数据能力判断确有必要时才会尝试。")


@cli.command(help="Show A-share Dragon-Tiger List (龙虎榜) evidence for one stock.")
@click.argument("symbol")
@_date_opt
@click.option("--limit", default=20, show_default=True, type=click.IntRange(1, 100))
def lhb(symbol: str, date: str | None, limit: int) -> None:
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    section = _render_section(
        "龙虎榜",
        fetch_lhb(_core, symbol, date_str, limit=limit),
        requested_date=date_str,
    )
    if not section:
        click.echo("暂无可展示的龙虎榜证据。")
        return
    for line in section:
        click.echo(line)


@cli.command(help="Show fund evidence; add --llm for deep fund analysis.")
@click.argument("code")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show fund and holding quote data, skip news lookup.")
@click.option("--llm", "use_llm", is_flag=True, help="Use the configured LLM for deep fund analysis.")
@click.option("--lens", type=click.Choice(("balanced", "all", *lens_ids())), default=None, help="Explicit LLM lens. Requires --llm.")
@click.option("--debate-rounds", default=3, show_default=True, type=click.IntRange(1, 5))
@click.option("--rich-source", is_flag=True, help="Allow slower optional sources where available.")
@click.option("--browser-fallback", is_flag=True, help="Allow browser fallback if a supporting capability decides it is needed.")
@click.pass_context
def fund(
    ctx: click.Context,
    code: str,
    date: str | None,
    refresh: bool,
    no_news: bool,
    use_llm: bool,
    lens: str | None,
    debate_rounds: int,
    rich_source: bool,
    browser_fallback: bool,
) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.BROWSER_FALLBACK = browser_fallback
    _core.cache_clear_old(days=7)
    date_str = date or (_default_report_trade_date() if use_llm else _core.nearest_trade_date())
    _validate_llm_option_contract(
        use_llm=use_llm,
        lens=lens,
        debate_rounds=debate_rounds,
        debate_rounds_explicit=ctx.get_parameter_source("debate_rounds") is ParameterSource.COMMANDLINE,
    )
    if use_llm:
        replay_options = {"kind": "fund", "symbol": code, "asset_kind": "fund"}
        if lens:
            replay_options["lens"] = lens
        if lens == "all":
            replay_options["debate_rounds"] = debate_rounds
        if rich_source or browser_fallback:
            replay_options.update(
                rich_source=rich_source,
                browser_fallback=browser_fallback,
            )
        _run_llm_replay(date_str, **replay_options)
        return
    _print_query_context(date_str)
    _core.run_fund_report(code, date_str, include_news=not no_news)


@cli.command(help="Show multi-source news for one stock, e.g. 600519, 0700.HK, AAPL.")
@click.argument("parts", nargs=-1, required=True)
@_date_opt
@_refresh_opt
@click.option("--limit", default=8, show_default=True, help="Maximum news items to show.")
def news(parts: tuple[str, ...], date: str | None, refresh: bool, limit: int) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    _print_query_context(date_str)
    symbol = parts[-1] if len(parts) > 1 and parts[0].lower() == "stock" else parts[0]
    _core.run_stock_news(symbol, date_str, size=limit)


@cli.command(help="Personal watchlist daily report. Deterministic by default; add `--llm` for the only deep replay entry.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
@click.option("--format", "report_format", type=click.Choice(["full", "summary", "key-points"]), default="full", show_default=True, help="Output style.")
@click.option("--order", default=None, help="Custom full-report order, e.g. 基金,A股,港股,美股.")
@click.option("--llm", "use_llm", is_flag=True, help="Use the configured LLM for the evidence-driven deep replay; plain daily does not require LLM.")
@click.option("--lens", type=click.Choice(("balanced", "all", *lens_ids())), default=None, help="Explicit LLM lens. Requires --llm.")
@click.option("--debate-rounds", default=3, show_default=True, type=click.IntRange(1, 5))
@click.option("--rich-source", is_flag=True, help="Allow slower optional sources for portfolio evidence.")
@click.option("--browser-fallback", is_flag=True, help="Allow browser fallback if a supporting capability decides it is needed.")
@click.pass_context
def daily(
    ctx: click.Context,
    date: str | None,
    refresh: bool,
    no_news: bool,
    report_format: str,
    order: str | None,
    use_llm: bool,
    lens: str | None,
    debate_rounds: int,
    rich_source: bool,
    browser_fallback: bool,
) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.BROWSER_FALLBACK = browser_fallback
    _core.cache_clear_old(days=7)
    date_str = date or _default_report_trade_date()
    profile = load_profile()
    if not profile.get("stocks") and not profile.get("funds"):
        _print_first_use_guide()
        return
    _validate_llm_option_contract(
        use_llm=use_llm,
        lens=lens,
        debate_rounds=debate_rounds,
        debate_rounds_explicit=ctx.get_parameter_source("debate_rounds") is ParameterSource.COMMANDLINE,
    )
    if use_llm:
        llm_options = {}
        if lens:
            llm_options["lens"] = lens
        if lens == "all":
            llm_options["debate_rounds"] = debate_rounds
        if rich_source or browser_fallback:
            llm_options.update(
                rich_source=rich_source,
                browser_fallback=browser_fallback,
            )
        _run_daily_llm(
            date_str,
            refresh=refresh,
            no_news=no_news,
            report_format=report_format,
            order=order,
            **llm_options,
        )
        return
    _run_plain_daily(
        date_str,
        profile,
        no_news=no_news,
        report_format=report_format,
        order=order,
    )


def _run_llm_replay(
    date_str: str,
    kind: str = "replay",
    symbol: str | None = None,
    asset_kind: str = "stock",
    lens: str | None = None,
    debate_rounds: int = 3,
    rich_source: bool = False,
    browser_fallback: bool = False,
):
    profile = load_profile()
    if symbol and asset_kind == "fund":
        evidence = build_fund_evidence(_core, symbol, date_str, rich_source=rich_source)
    elif symbol:
        evidence = build_stock_evidence(_core, symbol, date_str, rich_source=rich_source)
    else:
        evidence = build_daily_evidence(_core, date_str, profile, rich_source=rich_source)
    if symbol and asset_kind != "fund" and rich_source:
        evidence.modules["STOCK"]["external_research"] = _internal_research_fallback(symbol)
    artifacts = ReportArtifacts(date_str)
    identity = _llm_report_identity(date_str, symbol, lens)
    artifacts.write_json(f"{identity.prefix}-evidence", evidence.to_dict())
    migrate_legacy_llm_api_key_fallback()
    config = load_config(strict=False).get("llm", {})
    methodology = load_builtin_methodology()
    try:
        markdown, metadata = generate_llm_daily_report(
            evidence.to_dict(),
            model_transport_for_config(config),
            methodology=methodology.text,
            lens=lens,
            debate_rounds=debate_rounds,
            daily=symbol is None,
        )
    except LLMNotConfigured:
        raise
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    metadata["methodology_version"] = methodology.version
    metadata["methodology_updated"] = methodology.updated
    metadata["browser_fallback"] = browser_fallback
    path = artifacts.write_report_markdown(identity, markdown)
    artifacts.write_json(
        f"{identity.prefix}-metadata",
        {"kind": kind, "session": identity.session, "topic": identity.topic, **metadata},
    )
    _print_markdown_report(path)
    click.echo(f"\nSaved: {path}")
    return path

@cli.command(name="stock", help="Show verified stock evidence; add --llm for deep analysis.")
@click.argument("symbol")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show quote/evidence data, skip news lookup where supported.")
@click.option("--llm", "use_llm", is_flag=True, help="Use the configured LLM for deep replay; default stock is deterministic evidence only.")
@click.option("--lens", type=click.Choice(("balanced", "all", *lens_ids())), default=None, help="Explicit LLM lens. Requires --llm.")
@click.option("--debate-rounds", default=3, show_default=True, type=click.IntRange(1, 5))
@click.option("--rich-source", is_flag=True, help="Allow slower optional financial/social sources.")
@click.option("--browser-fallback", is_flag=True, help="Allow browser fallback if a supporting capability decides it is needed.")
@click.pass_context
def stock(
    ctx: click.Context,
    symbol: str,
    date: str | None,
    refresh: bool,
    no_news: bool,
    use_llm: bool,
    lens: str | None,
    debate_rounds: int,
    rich_source: bool,
    browser_fallback: bool,
) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.BROWSER_FALLBACK = browser_fallback
    date_str = date or _default_report_trade_date()
    _validate_llm_option_contract(
        use_llm=use_llm,
        lens=lens,
        debate_rounds=debate_rounds,
        debate_rounds_explicit=ctx.get_parameter_source("debate_rounds") is ParameterSource.COMMANDLINE,
    )
    if not use_llm:
        _run_plain_analyze(
            symbol,
            date_str,
            no_news=no_news,
            rich_source=rich_source,
            browser_fallback=browser_fallback,
        )
        return
    replay_options = {}
    if lens:
        replay_options["lens"] = lens
    if lens == "all":
        replay_options["debate_rounds"] = debate_rounds
    if rich_source or browser_fallback:
        replay_options.update(
            rich_source=rich_source,
            browser_fallback=browser_fallback,
        )
    _run_llm_replay(
        date_str,
        kind="stock",
        symbol=symbol,
        **replay_options,
    )


@cli.command(help="Enter Rich interactive chat with slash commands.")
def chat() -> None:
    from .chat import run_chat

    run_chat()


@cli.group(help="Show or set the shared chat/investor lens style.")
def style() -> None:
    pass


@style.command("list", help="List balanced and all registered investor lens styles.")
def style_list() -> None:
    from .chat import CHAT_STYLE_PROMPTS, _style_summary

    for name in CHAT_STYLE_PROMPTS:
        click.echo(_style_summary(name))


@style.command("show", help="Show the current shared chat/investor lens style.")
def style_show() -> None:
    from .chat import _load_chat_style_name, _style_summary

    click.echo(_style_summary(_load_chat_style_name()))


@style.command("set", help="Set the shared chat/investor lens style.")
@click.argument("name", type=click.Choice(("balanced", *lens_ids())))
def style_set(name: str) -> None:
    from .chat import _save_chat_style_name, _style_summary

    click.echo("已设置：" + _style_summary(_save_chat_style_name(name)))


@style.command("clear", help="Reset the shared style to balanced.")
def style_clear() -> None:
    from .chat import _save_chat_style_name

    _save_chat_style_name(None)
    click.echo("已清除自定义风格，当前风格：balanced")


@cli.group(help="Manage persistent long-term memory for young chat.")
def memory() -> None:
    pass


@memory.command("show", help="Show saved young chat long-term memory.")
def memory_show() -> None:
    from .chat import format_long_term_memory_for_cli, load_long_term_memory

    click.echo(format_long_term_memory_for_cli(load_long_term_memory()))


memory.add_command(memory_show, name="list")


@memory.command("clear", help="Clear one kind of young chat memory, or all kinds.")
@click.option(
    "--kind",
    type=click.Choice(["investment", "persona", "preferences", "all"]),
    default="all",
    show_default=True,
)
def memory_clear(kind: str) -> None:
    from .chat import clear_long_term_memory_store

    clear_long_term_memory_store(None if kind == "all" else kind)
    click.echo(f"已清空 chat memory: {kind}")


@memory.command("reset", help="Reset all persistent young chat memory.")
def memory_reset() -> None:
    from .chat import clear_long_term_memory_store

    clear_long_term_memory_store()
    click.echo("已重置全部 chat memory。")


@cli.group(help="Manage LLM and delivery-channel configuration.")
def config() -> None:
    pass


@config.command("path", help="Show the configuration file path.")
def config_path_command() -> None:
    click.echo(str(config_path()))


@config.command("show", help="Show effective configuration with secrets masked.")
def config_show() -> None:
    for line in _render_config_lines(mask_config(load_effective_config())):
        click.echo(line)


@config.command("providers", help="List supported LLM API providers.")
def config_providers() -> None:
    for spec in provider_specs():
        base = spec.default_api_base or "(required)"
        key_env = spec.default_api_key_env or "-"
        explicit_base = "yes" if spec.requires_explicit_base_url else "no"
        probe = "yes" if spec.supports_model_probe else "no"
        click.echo(
            f"{spec.provider_id}\t{spec.display_name}\t"
            f"protocol={spec.protocol}\tbase={base}\tkey_env={key_env}\t"
            f"explicit_base={explicit_base}\tmodel_probe={probe}"
        )


@config.command("models", help="Configure the LLM provider/model, or list model IDs from the resolved endpoint.")
@click.option(
    "--provider",
    default=None,
    type=click.Choice(MODEL_PROVIDER_IDS),
)
@click.option("--transport", default=None, type=click.Choice(transport_ids()), help="Model transport: api or subscription-cli.")
@click.option("--model", default=None, help="Model ID used by chat and LLM reports.")
@click.option("--api-key", default=None, hide_input=True)
@click.option("--api-key-env", default=None, help="Environment variable containing the API key.")
@click.option("--api-base", default=None, help="Override provider API base URL.")
@click.option(
    "--fallback-model",
    "fallback_models",
    multiple=True,
    help="Optional fallback model ID. Repeat this option to configure multiple fallback models.",
)
@click.option("--timeout", default=30, show_default=True, type=float)
@click.option("--max-tokens", default=4000, show_default=True, type=int)
@click.option("--list", "list_models", is_flag=True, help="List model IDs exposed by the resolved endpoint.")
@click.pass_context
def config_models(
    ctx: click.Context,
    provider: str | None,
    transport: str | None,
    model: str | None,
    api_key: str | None,
    api_key_env: str | None,
    api_base: str | None,
    fallback_models: tuple[str, ...],
    timeout: float,
    max_tokens: int,
    list_models: bool,
) -> None:
    saved = dict(load_config(strict=False).get("llm") or {})
    effective_saved = dict(load_effective_config(strict=False).get("llm") or {})
    resolved_transport = transport or saved.get("transport") or "api"
    resolved_provider = provider or saved.get("provider")
    explicit_timeout = ctx.get_parameter_source("timeout") is ParameterSource.COMMANDLINE
    explicit_max_tokens = ctx.get_parameter_source("max_tokens") is ParameterSource.COMMANDLINE
    explicit_api_key = ctx.get_parameter_source("api_key") is ParameterSource.COMMANDLINE
    explicit_api_key_env = ctx.get_parameter_source("api_key_env") is ParameterSource.COMMANDLINE
    explicit_api_base = ctx.get_parameter_source("api_base") is ParameterSource.COMMANDLINE
    explicit_fallback_models = ctx.get_parameter_source("fallback_models") is ParameterSource.COMMANDLINE

    if model:
        if not resolved_provider:
            raise click.ClickException("请提供 --provider，或先保存 provider 后再只更新 --model。")
        spec = provider_spec(resolved_provider) if resolved_transport == "api" else None
        if resolved_transport == "api" and spec is None:
            raise click.ClickException(f"{resolved_provider} 不是 API provider；如需本机 CLI，请添加 --transport subscription-cli。")
        if resolved_transport == "subscription-cli" and resolved_provider not in subscription_cli_provider_ids():
            raise click.ClickException(f"{resolved_provider} 不是已支持的 subscription-cli provider。")
        candidate_api_base = normalize_api_base(
            resolved_provider,
            api_base if explicit_api_base else saved.get("api_base", ""),
        )
        if spec and spec.requires_explicit_base_url and not candidate_api_base:
            raise click.ClickException(f"{spec.display_name} 需要显式提供 Base URL：请添加 --api-base。")
        if is_kimi_coding_api_base(candidate_api_base):
            raise click.ClickException(kimi_coding_plan_unsupported_message())
        updated = update_llm_config(
            transport=resolved_transport,
            provider=resolved_provider,
            model=model,
            api_key=api_key if explicit_api_key else None,
            api_key_env=api_key_env if explicit_api_key_env else None,
            api_base=api_base if explicit_api_base else None,
            fallback_models=list(fallback_models) if explicit_fallback_models else None,
            timeout=timeout if explicit_timeout else None,
            max_tokens=max_tokens if explicit_max_tokens else None,
        )
        llm = updated.get("llm") or {}
        click.echo(
            "LLM configured: "
            f"transport={llm.get('transport')}; "
            f"provider={llm.get('provider')}; "
            f"model={llm.get('model')}; "
            f"config={config_path()}"
        )
        return

    if not list_models:
        raise click.ClickException("请提供 --model 保存配置，或使用 --list 查询可用模型 ID。")
    if resolved_transport != "api":
        raise click.ClickException("subscription-cli transport 不支持 --list；请在本机 CLI 中确认可用模型。")

    query = {
        **effective_saved,
        "transport": "api",
        "provider": resolved_provider,
        "api_key": api_key if explicit_api_key else effective_saved.get("api_key"),
        "api_key_env": api_key_env if explicit_api_key_env else effective_saved.get("api_key_env"),
        "api_base": api_base if explicit_api_base else effective_saved.get("api_base"),
        "timeout": timeout if explicit_timeout else effective_saved.get("timeout", timeout),
    }
    try:
        models = LLMClient(query).list_models(verify_chat=True)
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    if not models:
        click.echo("该服务当前未返回可用模型 ID。")
        return
    for model_id in models:
        click.echo(model_id)


@config.command(
    "llm",
    hidden=True,
    add_help_option=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
def config_llm_compat() -> None:
    raise click.ClickException("`young config llm` 已弃用，请改用 `young config models`。")


@config.group("channel", help="Manage notification channels.")
def config_channel() -> None:
    pass


@config_channel.command("add", help="Add a Feishu channel.")
@click.argument("channel_type", type=click.Choice(["feishu"]))
@click.argument("name")
@click.option("--webhook", default=None)
@click.option("--app-id", default=None)
@click.option("--app-secret", default=None, hide_input=True)
@click.option("--tenant-access-token", default=None, hide_input=True)
@click.option("--receive-id", default=None)
@click.option("--receive-id-type", default="chat_id", show_default=True)
def config_channel_add(
    channel_type: str,
    name: str,
    webhook: str | None,
    app_id: str | None,
    app_secret: str | None,
    tenant_access_token: str | None,
    receive_id: str | None,
    receive_id_type: str,
) -> None:
    app_ready = receive_id and (tenant_access_token or (app_id and app_secret))
    if not webhook and not app_ready:
        raise click.ClickException(
            "Feishu 需要 --webhook，或 --receive-id 配合 tenant token / app credentials。"
        )
    add_feishu_channel(
        name,
        {
            "type": channel_type,
            "webhook": webhook,
            "app_id": app_id,
            "app_secret": app_secret,
            "tenant_access_token": tenant_access_token,
            "receive_id": receive_id,
            "receive_id_type": receive_id_type,
        },
    )
    click.echo(f"Added feishu channel: {name}")


@config_channel.command("list", help="List channels with secrets masked.")
def config_channel_list() -> None:
    channels = mask_config(load_config().get("channels", {}))
    for line in _render_channel_lines(channels):
        click.echo(line)


@config_channel.command("remove", help="Remove a channel.")
@click.argument("channel_type", type=click.Choice(["feishu"]))
@click.argument("name")
def config_channel_remove(channel_type: str, name: str) -> None:
    removed = remove_feishu_channel(name)
    click.echo(f"Removed {channel_type} channel: {name}" if removed else f"Channel not found: {name}")


@cli.command(help="Export the latest saved Markdown report to PDF only; it does not generate a new LLM replay.")
@_date_opt
def report(date: str | None) -> None:
    from .pdf import export_report_pdf

    try:
        markdown_path, pdf_path = export_report_pdf(
            date or latest_report_trade_date(),
            core=_core,
            profile=load_profile(),
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Markdown: {markdown_path}")
    click.echo(f"PDF: {pdf_path}")


def _preview_send_bundle(date: str | None, channel_name: str | None) -> None:
    bundle = ReportArtifacts.latest_delivery_artifacts(date)
    if bundle is None:
        if date:
            raise click.ClickException(f"{date} 缺少可发送的 Markdown；请先生成对应日报或 LLM Markdown。")
        raise click.ClickException("未找到可发送的 Markdown；请先生成日报或 LLM Markdown。")
    click.echo("Dry run only; no remote message sent.")
    click.echo(f"Markdown: {bundle.markdown}")
    click.echo(f"PDF: {bundle.pdf if bundle.pdf is not None else '-'}")
    click.echo(f"Channel: {channel_name or 'all configured channels'}")


@cli.command(help="Send the latest Markdown report and summary; attach the same-name PDF only when it exists.")
@_date_opt
@click.option("--channel", "channel_name", default=None, help="Send only one configured channel.")
@click.option("--dry-run", is_flag=True, help="Preview the resolved Markdown/PDF bundle and target channel.")
@click.option("--yes", is_flag=True, help="Actually send to the configured remote channel(s).")
def send(date: str | None, channel_name: str | None, dry_run: bool, yes: bool) -> None:
    from .channels import send_report

    if dry_run and yes:
        raise click.ClickException("`young send` 不能同时使用 --dry-run 和 --yes。")
    if dry_run:
        _preview_send_bundle(date, channel_name)
        return
    if not yes:
        raise click.ClickException("`young send` 会向远端渠道发消息；请先运行 `young send --dry-run` 预览，确认后再加 `--yes`。")
    try:
        results = send_report(date, channel_name=channel_name)
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    for result in results:
        state = "OK" if result.ok else "FAILED"
        click.echo(f"{state} {result.channel}/{result.target}: {result.detail}")
    if results and not all(result.ok for result in results):
        raise click.ClickException("部分渠道发送失败。")


@cli.group(help="Manage local investment memory for daily reports.")
def profile() -> None:
    pass


def _normalize_buy_date(value: str) -> str:
    compact = _core._compact_date(value.strip())
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise click.ClickException("buy-date 必须是 YYYYMMDD 或 YYYY-MM-DD") from exc
    return parsed.strftime("%Y-%m-%d")


def _validate_quantity(value: float) -> float:
    if value <= 0:
        raise click.ClickException("quantity 必须大于 0")
    return value


def _stock_invalid_message(symbol: str) -> str:
    return f"{symbol} 不是有效的股票代码，请删除重新输入"


def _fund_invalid_message(code: str) -> str:
    return f"{code} 不是有效的基金代码，请删除重新输入"


@profile.command("add-stock", help="Add a stock/ETF symbol to your daily watchlist.")
@click.argument("symbol")
@click.option("--buy-date", required=True, help="Buy date YYYYMMDD or YYYY-MM-DD for return analysis.")
@click.option("--quantity", required=True, type=float, help="Holding quantity/shares.")
def profile_add_stock(symbol: str, buy_date: str, quantity: float) -> None:
    normalized_date = _normalize_buy_date(buy_date)
    normalized_quantity = _validate_quantity(quantity)
    date_str = _core.nearest_trade_date()
    try:
        quote = _core.get_single_stock_quote(symbol, date_str)
    except ValueError as exc:
        raise click.ClickException(_stock_invalid_message(symbol)) from exc
    if not quote or quote.price is None or quote.market not in {"cn_market", "hk_market", "us_market"}:
        raise click.ClickException(_stock_invalid_message(symbol))
    classification = _build_stock_classification(str(quote.symbol or symbol), str(quote.name or ""), str(quote.market or ""), quote)
    add_profile_item(
        "stocks",
        quote.symbol,
        buy_date=normalized_date,
        quantity=normalized_quantity,
        classification=classification,
    )
    click.echo(f"您的投资记忆已添加：{quote.name or quote.symbol}（{quote.symbol}）")
    click.echo(f"Position: buy_date={normalized_date}; quantity={normalized_quantity:g}")
    click.echo(
        "自动分类: "
        f"{classification['market']} / {classification['asset_type']} / {classification['category']}"
    )
    if hint := _classification_hint():
        click.echo(hint)


@profile.command("add-fund", help="Add a fund code to your daily watchlist.")
@click.argument("code")
@click.option("--buy-date", required=True, help="Buy date YYYYMMDD or YYYY-MM-DD for return analysis.")
@click.option("--quantity", required=True, type=float, help="Holding shares/units.")
def profile_add_fund(code: str, buy_date: str, quantity: float) -> None:
    normalized_date = _normalize_buy_date(buy_date)
    normalized_quantity = _validate_quantity(quantity)
    try:
        fund_code = _core.normalize_fund_code(code)
    except ValueError as exc:
        raise click.ClickException(_fund_invalid_message(code)) from exc
    data = _core.fetch_fund_estimate(fund_code, _core.nearest_trade_date())
    if "_error" in data or not data.get("name"):
        raise click.ClickException(_fund_invalid_message(code))
    saved_code = str(data.get("fundcode") or fund_code)
    add_profile_item("funds", saved_code, buy_date=normalized_date, quantity=normalized_quantity)
    click.echo(f"您的投资记忆已添加：{data.get('name')}（{saved_code}）")
    click.echo(f"Position: buy_date={normalized_date}; quantity={normalized_quantity:g}")


@profile.command("list", help="Show saved daily-report investment memory.")
def profile_show() -> None:
    data = load_profile()
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")
    positions = data.get("positions", {})
    if positions.get("stocks") or positions.get("funds"):
        click.echo("Positions:")
        for kind, label in (("stocks", "stock"), ("funds", "fund")):
            for code, position in positions.get(kind, {}).items():
                buy_date = position.get("buy_date", "-")
                quantity = position.get("quantity", "-")
                click.echo(f"  {label} {code}: buy_date={buy_date}; quantity={quantity}")
    stock_classifications = data.get("classifications", {}).get("stocks", {})
    if stock_classifications:
        click.echo("自动分类:")
        for code, classification in stock_classifications.items():
            click.echo(_profile_classification_line(code, classification))
    groups = data.get("groups", {})
    if groups:
        click.echo("Legacy groups:")
        for name, group in groups.items():
            stocks = ", ".join(group.get("stocks", [])) or "-"
            funds = ", ".join(group.get("funds", [])) or "-"
            click.echo(f"  {name}: stocks={stocks}; funds={funds}")


profile.add_command(profile_show, name="show")


@profile.command("remove-stock", help="Remove a stock/ETF symbol from your watchlist.")
@click.argument("symbol")
def profile_remove_stock(symbol: str) -> None:
    data = remove_profile_item("stocks", symbol)
    click.echo(f"Removed stock: {symbol.strip()}")
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")


@profile.command("remove-fund", help="Remove a fund code from your watchlist.")
@click.argument("code")
def profile_remove_fund(code: str) -> None:
    data = remove_profile_item("funds", code)
    click.echo(f"Removed fund: {code.strip()}")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")


@profile.command("clear", help="Clear stocks, funds, legacy entries, and auto classifications from investment memory.")
def profile_clear() -> None:
    clear_profile()
    click.echo("Cleared investment memory.")


@profile.command("clear-stocks", help="Clear all saved stocks/ETFs from investment memory.")
def profile_clear_stocks() -> None:
    data = clear_profile_kind("stocks")
    click.echo("Cleared all saved stocks/ETFs.")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")


@profile.command("clear-funds", help="Clear all saved funds from investment memory.")
def profile_clear_funds() -> None:
    data = clear_profile_kind("funds")
    click.echo("Cleared all saved funds.")
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")


def _diagnostic_payload() -> dict:
    sources = []
    for name in ["eastmoney", "sina", "tencent", "ths", "futu"]:
        snap = _core.SOURCE_HEALTH.snapshot(name)
        sources.append({
            "name": name,
            "success_rate": snap.success_rate,
            "average_latency_ms": snap.average_latency_ms,
            "should_skip": snap.should_skip,
        })
    config_data = load_config(strict=False)
    llm_config = config_data.get("llm", {})
    try:
        import importlib.util

        pdf_ready = importlib.util.find_spec("weasyprint") is not None
    except (ImportError, ValueError):
        pdf_ready = False
    return {
        "command": "young diagnose",
        "version": __version__,
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "paths": {
            "profile": str(profile_path()),
            "home": str(young_home()),
            "cache": str(_core.CACHE_DIR),
        },
        "sources": sources,
        "llm": {
            "configured": bool(llm_config.get("provider") and llm_config.get("model")),
            "provider": llm_config.get("provider"),
            "model": llm_config.get("model"),
        },
        "research_bridge": {
            "configured": bool(os.environ.get(RESEARCH_COMMAND_ENV)),
            "env": RESEARCH_COMMAND_ENV,
        },
        "pdf": {"weasyprint": pdf_ready},
        "channels": sorted(config_data.get("channels", {}).get("feishu", {}).keys()),
        "read_only": True,
    }


@cli.command(help="Run a lightweight network/source diagnostic.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable diagnostics.")
def diagnose(as_json: bool) -> None:
    payload = _diagnostic_payload()
    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo("# 网络诊断")
    for source in payload["sources"]:
        name = source["name"]
        snap = _core.SOURCE_HEALTH.snapshot(name)
        state = "建议暂缓使用" if snap.should_skip else "可用/未发现近期异常"
        click.echo(f"{name}: 成功率 {snap.success_rate:.0%}, 平均延迟 {snap.average_latency_ms:.0f}ms, {state}")
    if payload["research_bridge"]["configured"]:
        click.echo(f"Research bridge: 已配置 {RESEARCH_COMMAND_ENV}；对话与分析可按需补充公开资料。")
    else:
        click.echo("Research bridge: 未配置可选桥；当前版本优先使用内置数据源。")
    click.echo("建议: 若接口失败，可先使用缓存、改用 --format summary，或稍后运行 --refresh 重试。")


@cli.command(help="New-user guide.")
def guide() -> None:
    click.echo("1. young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("2. young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000")
    click.echo("3. young daily --format summary（profile stock 会自动生成可解释分类标签）")
    click.echo("4. young profile list / young diagnose")


@cli.command(help="Initialize local state, verify installed capabilities, and print next steps.")
def init() -> None:
    from .pdf import _load_weasyprint

    home = young_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "reports").mkdir(parents=True, exist_ok=True)
    save_config(load_config(strict=False))
    save_profile(load_profile())
    for name, default in (
        ("diaries", {}),
        ("portfolios", {}),
    ):
        save_store(name, load_store(name, default))

    pdf_ready = _load_weasyprint() is not None
    click.echo("初始化完成。")
    click.echo(f"Home: {home}")
    click.echo(f"Profile: {profile_path()}")
    click.echo(f"Config: {config_path()}")
    click.echo(f"PDF: {'已就绪' if pdf_ready else '当前环境未检测到 PDF 渲染能力'}")
    if not pdf_ready:
        click.echo("若你是从仓库根目录执行 `uv tool install --force .` 安装的，请改用 `uv tool install --force '.[pdf]'`。")
        click.echo("若你是从 PyPI 安装的，请执行 `uv tool install --upgrade 'young-stock-cli[pdf]'`。")
    click.echo("下一步建议：")
    click.echo("1. young config show")
    click.echo("2. young config models --help")
    click.echo("3. young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("   或 young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000")
    click.echo("4. 可选：完成配置后再运行 young daily --format summary / young daily --llm / young report")


@cli.command(help="Show common examples.")
def example() -> None:
    click.echo("young daily --format summary")
    click.echo("young daily --format key-points --order 基金,A股,港股,美股")
    click.echo("young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("young send --dry-run")
    click.echo("young send --yes --channel <name>")


@cli.group(help="Manage local portfolios.")
def portfolio() -> None:
    pass


@portfolio.command("create")
@click.argument("name")
def portfolio_create(name: str) -> None:
    data = load_store("portfolios", {})
    data.setdefault(name, [])
    save_store("portfolios", data)
    click.echo(f"Created portfolio: {name}")


@portfolio.command("add")
@click.argument("name")
@click.argument("code")
@click.argument("shares", type=float)
def portfolio_add(name: str, code: str, shares: float) -> None:
    data = load_store("portfolios", {})
    items = data.setdefault(name, [])
    items.append({"code": code, "shares": shares})
    save_store("portfolios", data)
    click.echo(f"Added {code} x {shares:g} to {name}")


@portfolio.command("show")
@click.argument("name")
def portfolio_show(name: str) -> None:
    data = load_store("portfolios", {})
    items = data.get(name, [])
    click.echo(f"# Portfolio: {name}")
    if not items:
        click.echo("  empty")
    for item in items:
        click.echo(f"  {item.get('code')} x {item.get('shares')}")


@portfolio.command("compare")
@click.argument("code1")
@click.argument("code2")
def portfolio_compare(code1: str, code2: str) -> None:
    click.echo(f"{code1} vs {code2}: use young stock <code> for detail; historical comparison is on the roadmap.")


@cli.group(help="Save and read local daily-report snapshots.")
def diary() -> None:
    pass


@diary.command("save")
@click.argument("date")
@click.option("--text", default="", help="Diary text to save.")
def diary_save(date: str, text: str) -> None:
    data = load_store("diaries", {})
    data[date] = {"text": text, "saved_at": now_label()}
    save_store("diaries", data)
    click.echo(f"Saved diary: {date}")


@diary.command("show")
@click.argument("date")
def diary_show(date: str) -> None:
    data = load_store("diaries", {})
    item = data.get(date)
    if not item:
        click.echo("Diary not found.")
        return
    click.echo(item.get("text") or "")


@cli.command(help="Clear cached responses older than N days.")
@click.option("--days", default=7, show_default=True, help="Delete cache files older than this many days.")
def cache_clear(days: int) -> None:
    _core.cache_clear_old(days=days)
    click.echo(f"Cleared cache older than {days} days.")


if __name__ == "__main__":
    cli()
