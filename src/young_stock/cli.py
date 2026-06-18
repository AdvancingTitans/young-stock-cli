"""young-stock-cli command line interface."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime

import click

from . import __version__, _core
from .artifacts import ReportArtifacts
from .config import (
    add_feishu_channel,
    config_path,
    load_config,
    mask_config,
    remove_feishu_channel,
    update_llm_config,
)
from .evidence import build_daily_evidence, build_stock_evidence
from .llm import LLMClient, LLMError
from .local_store import load_store, now_label, save_store, young_home
from .methodology import sync_stock_analysis_methodology
from .profile import (
    add_group,
    add_group_item,
    add_profile_item,
    clear_profile,
    clear_profile_kind,
    load_profile,
    profile_path,
    remove_profile_item,
)
from .reports import generate_llm_daily_report


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="A-share & global market after-hours CLI. No login, no scraping tricks.",
)
@click.version_option(__version__, "-V", "--version", message="young-stock-cli %(version)s")
def cli() -> None:
    pass


def _run(market: str, date: str | None, refresh: bool, include_news: bool = True) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
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
    click.echo("尚未设置投资记忆。首次使用请先添加你关注的股票、ETF 或基金，并补充买入日期和数量：")
    click.echo("  young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("  young profile add-stock 0700.HK --buy-date 2026-01-15 --quantity 200")
    click.echo("  young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000")
    click.echo()
    click.echo(f"配置会保存到: {profile_path()}")


@cli.command(help="A-share dashboard: indices, ZT/DT pool, verified A-share fund flow, boards.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
def a(date: str | None, refresh: bool, no_news: bool) -> None:
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
    if northbound:
        _core.run_northbound_flow_report(date_str)
    elif symbol:
        _core.run_stock_fund_flow_report(symbol, date_str, limit=limit)
    else:
        flow_data = _core.get_fund_flow(date_str, strict_date=False)
        _core.print_fund_flow(flow_data)


@cli.command(name="block-trades", help="Show A-share block trade records for one stock.")
@click.argument("symbol")
@_date_opt
@_refresh_opt
@click.option("--limit", default=10, show_default=True, type=int, help="Maximum records to show.")
def block_trades(symbol: str, date: str | None, refresh: bool, limit: int) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    _core.run_block_trades_report(symbol, date_str, limit=limit)


@cli.command(help="Show one stock by code, e.g. 600519, 0700.HK, AAPL.")
@click.argument("symbol")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show quote data, skip news lookup.")
def stock(symbol: str, date: str | None, refresh: bool, no_news: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    _core.run_stock_quote(symbol, date_str, include_news=not no_news)


@cli.command(help="Show one fund estimate, top holdings quotes, and holding-stock news.")
@click.argument("code")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show fund and holding quote data, skip news lookup.")
def fund(code: str, date: str | None, refresh: bool, no_news: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
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
    symbol = parts[-1] if len(parts) > 1 and parts[0].lower() == "stock" else parts[0]
    _core.run_stock_news(symbol, date_str, size=limit)


@cli.command(help="Personal daily report from your saved watchlist.")
@_date_opt
@_refresh_opt
@click.option("--no-news", is_flag=True, help="Only show market data, skip news lookup.")
@click.option("--format", "report_format", type=click.Choice(["full", "summary", "key-points"]), default="full", show_default=True, help="Output style.")
@click.option("--only", default=None, help="Only show selected parts, e.g. funds,stocks,a or 基金,A股.")
@click.option("--order", default=None, help="Custom full-report order, e.g. 基金,A股,港股,美股.")
@click.option("--quick", is_flag=True, help="Fast mode: skip slower global/news sections.")
@click.option("--llm", "use_llm", is_flag=True, help="Generate an evidence-driven deep replay with the configured LLM.")
def daily(
    date: str | None,
    refresh: bool,
    no_news: bool,
    report_format: str,
    only: str | None,
    order: str | None,
    quick: bool,
    use_llm: bool,
) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    profile = load_profile()
    if not profile.get("stocks") and not profile.get("funds"):
        _print_first_use_guide()
        return
    if use_llm:
        _run_llm_replay(date_str)
        return
    _core.run_daily_report(date_str, profile, include_news=not no_news, report_format=report_format, only=only, order=order, quick=quick)


def _run_llm_replay(date_str: str, kind: str = "replay", symbol: str | None = None) -> None:
    profile = load_profile()
    evidence = (
        build_stock_evidence(_core, symbol, date_str)
        if symbol
        else build_daily_evidence(_core, date_str, profile)
    )
    artifacts = ReportArtifacts(date_str)
    artifacts.write_json("evidence" if not symbol else f"{symbol}-evidence", evidence.to_dict())
    config = load_config(strict=False).get("llm", {})
    methodology = sync_stock_analysis_methodology()
    try:
        markdown, metadata = generate_llm_daily_report(
            evidence.to_dict(),
            LLMClient(config),
            methodology=methodology.text,
        )
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    metadata["stock_analysis_version"] = methodology.version
    metadata["stock_analysis_updated"] = methodology.updated
    name = f"analyze-{symbol}" if symbol else kind
    path = artifacts.write_markdown(name, markdown)
    artifacts.write_metadata({"kind": name, **metadata})
    from rich.console import Console
    from rich.markdown import Markdown

    Console().print(Markdown(markdown))
    click.echo(f"\nSaved: {path}")


@cli.command(help="Generate an evidence-driven deep market replay with the configured LLM.")
@_date_opt
@_refresh_opt
def replay(date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _run_llm_replay(date or _core.nearest_trade_date())


@cli.command(help="Generate deep analysis for one stock using verified young-stock data.")
@click.argument("symbol")
@_date_opt
@_refresh_opt
def analyze(symbol: str, date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _run_llm_replay(date or _core.nearest_trade_date(), kind="analyze", symbol=symbol)


@cli.command(help="Enter Rich interactive chat with slash commands.")
def chat() -> None:
    from .chat import run_chat

    run_chat()


@cli.group(help="Manage LLM and delivery-channel configuration.")
def config() -> None:
    pass


@config.command("path", help="Show the configuration file path.")
def config_path_command() -> None:
    click.echo(str(config_path()))


@config.command("show", help="Show effective configuration with secrets masked.")
def config_show() -> None:
    click.echo(json.dumps(mask_config(load_config()), ensure_ascii=False, indent=2))


@config.command("llm", help="Configure the LLM provider and model.")
@click.option(
    "--provider",
    required=True,
    type=click.Choice(["openai", "ark", "kimi", "moonshot", "deepseek", "qwen", "ollama", "anthropic"]),
)
@click.option("--model", required=True)
@click.option("--api-key", default=None, hide_input=True)
@click.option("--api-key-env", default=None, help="Environment variable containing the API key.")
@click.option("--api-base", default=None)
@click.option("--timeout", default=60, show_default=True, type=float)
@click.option("--max-tokens", default=4000, show_default=True, type=int)
def config_llm(
    provider: str,
    model: str,
    api_key: str | None,
    api_key_env: str | None,
    api_base: str | None,
    timeout: float,
    max_tokens: int,
) -> None:
    update_llm_config(
        provider=provider,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        api_base=api_base,
        timeout=timeout,
        max_tokens=max_tokens,
    )
    click.echo(f"LLM configured: provider={provider}; model={model}; config={config_path()}")


@config.command("models", help="List model IDs exposed by an OpenAI-compatible, Anthropic, or Ollama endpoint.")
@click.option(
    "--provider",
    default=None,
    type=click.Choice(["openai", "ark", "kimi", "moonshot", "deepseek", "qwen", "ollama", "anthropic"]),
)
@click.option("--api-key", default=None, hide_input=True)
@click.option("--api-key-env", default=None, help="Environment variable containing the API key.")
@click.option("--api-base", default=None, help="Provider API base, for example https://api.moonshot.cn/v1.")
@click.option("--timeout", default=30, show_default=True, type=float)
def config_models(
    provider: str | None,
    api_key: str | None,
    api_key_env: str | None,
    api_base: str | None,
    timeout: float,
) -> None:
    saved = dict(load_config(strict=False).get("llm") or {})
    query = {
        **saved,
        "provider": provider or saved.get("provider"),
        "api_key": api_key if api_key is not None else saved.get("api_key"),
        "api_key_env": api_key_env if api_key_env is not None else saved.get("api_key_env"),
        "api_base": api_base or saved.get("api_base"),
        "timeout": timeout,
    }
    try:
        models = LLMClient(query).list_models()
    except LLMError as exc:
        raise click.ClickException(str(exc)) from exc
    if not models:
        click.echo("该服务当前未返回可用模型 ID。")
        return
    for model_id in models:
        click.echo(model_id)


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
    click.echo(json.dumps(channels, ensure_ascii=False, indent=2))


@config_channel.command("remove", help="Remove a channel.")
@click.argument("channel_type", type=click.Choice(["feishu"]))
@click.argument("name")
def config_channel_remove(channel_type: str, name: str) -> None:
    removed = remove_feishu_channel(name)
    click.echo(f"Removed {channel_type} channel: {name}" if removed else f"Channel not found: {name}")


@cli.command(help="Export the latest Markdown report to a professional PDF.")
@_date_opt
def report(date: str | None) -> None:
    from .pdf import export_report_pdf

    try:
        markdown_path, pdf_path = export_report_pdf(
            date or _core.nearest_trade_date(),
            core=_core,
            profile=load_profile(),
        )
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Markdown: {markdown_path}")
    click.echo(f"PDF: {pdf_path}")


@cli.command(help="Send the latest Markdown and PDF report to configured channels.")
@_date_opt
@click.option("--channel", "channel_name", default=None, help="Send only one configured channel.")
def send(date: str | None, channel_name: str | None) -> None:
    from .channels import send_report

    try:
        results = send_report(date or ReportArtifacts.latest_date(), channel_name=channel_name)
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
    add_profile_item("stocks", quote.symbol, buy_date=normalized_date, quantity=normalized_quantity)
    click.echo(f"您的投资记忆已添加：{quote.name or quote.symbol}（{quote.symbol}）")
    click.echo(f"Position: buy_date={normalized_date}; quantity={normalized_quantity:g}")


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
    groups = data.get("groups", {})
    if groups:
        click.echo("Groups:")
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


@profile.command("clear", help="Clear stocks, funds, and groups from investment memory.")
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


@profile.group("group", help="Manage investment-memory groups.")
def profile_group() -> None:
    pass


@profile_group.command("create", help="Create a named watchlist group.")
@click.argument("name")
def profile_group_create(name: str) -> None:
    add_group(name)
    click.echo(f"Created group: {name}")


@profile_group.command("add", help="Add a symbol/code to a group.")
@click.argument("name")
@click.argument("code")
def profile_group_add(name: str, code: str) -> None:
    add_group_item(name, code)
    click.echo(f"Added {code} to group: {name}")


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
        "pdf": {"weasyprint": pdf_ready},
        "channels": sorted(config_data.get("channels", {}).get("feishu", {}).keys()),
        "read_only": True,
    }


@cli.command(help="Run a lightweight network/source diagnostic.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable diagnostics.")
def diagnose(as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(_diagnostic_payload(), ensure_ascii=False, indent=2))
        return
    click.echo("# 网络诊断")
    for source in _diagnostic_payload()["sources"]:
        name = source["name"]
        snap = _core.SOURCE_HEALTH.snapshot(name)
        state = "建议暂缓使用" if snap.should_skip else "可用/未发现近期异常"
        click.echo(f"{name}: 成功率 {snap.success_rate:.0%}, 平均延迟 {snap.average_latency_ms:.0f}ms, {state}")
    click.echo("建议: 若接口失败，可先使用缓存、加 --quick/--format summary，或稍后运行 --refresh 重试。")


@cli.command(help="New-user guide.")
def guide() -> None:
    click.echo("1. young profile add-stock 600519 --buy-date 2026-01-15 --quantity 100")
    click.echo("2. young profile add-fund 161725 --buy-date 2026-01-10 --quantity 1000")
    click.echo("3. young daily --format summary")
    click.echo("4. young profile list / young diagnose")


@cli.command(help="Show common examples.")
def example() -> None:
    click.echo("young daily --format summary --quick")
    click.echo("young daily --format key-points --only 基金,A股")
    click.echo("young profile group create 稳健型")
    click.echo("young alert create 600519 '涨跌幅>5%'")


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


@cli.group(help="Manage local price/change alerts.")
def alert() -> None:
    pass


@alert.command("create")
@click.argument("code")
@click.argument("condition")
def alert_create(code: str, condition: str) -> None:
    data = load_store("alerts", [])
    data.append({"code": code, "condition": condition, "created_at": now_label()})
    save_store("alerts", data)
    click.echo(f"Created alert: {code} {condition}")


@alert.command("list")
def alert_list() -> None:
    data = load_store("alerts", [])
    if not data:
        click.echo("No alerts.")
    for item in data:
        click.echo(f"{item.get('code')}: {item.get('condition')} ({item.get('created_at')})")


@alert.command("check")
def alert_check() -> None:
    data = load_store("alerts", [])
    click.echo(f"Checked {len(data)} alerts. Realtime trigger evaluation is best-effort and will expand in a later release.")


@cli.group(help="Manage investment notes.")
def note() -> None:
    pass


@note.command("add")
@click.argument("content", nargs=-1, required=True)
def note_add(content: tuple[str, ...]) -> None:
    data = load_store("notes", [])
    text = " ".join(content)
    data.append({"content": text, "created_at": now_label()})
    save_store("notes", data)
    click.echo("Added note.")


@note.command("list")
def note_list() -> None:
    data = load_store("notes", [])
    if not data:
        click.echo("No notes.")
    for item in data:
        click.echo(f"{item.get('created_at')}: {item.get('content')}")


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
