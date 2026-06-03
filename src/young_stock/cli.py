"""young-stock-cli command line interface."""
from __future__ import annotations

import subprocess
import sys

import click

from . import __version__, _core
from .local_store import load_store, now_label, save_store
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
    click.echo("尚未设置投资记忆。首次使用请先添加你关注的股票、ETF 或基金：")
    click.echo("  young profile add-stock 600519")
    click.echo("  young profile add-stock 0700.HK")
    click.echo("  young profile add-fund 161725")
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
        raise click.ClickException(f"update failed with exit code {result.returncode}")


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


@cli.command(help="Show latest verified A-share fund flow.")
@_date_opt
@_refresh_opt
def flow(date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    flow_data = _core.get_fund_flow(date_str, strict_date=False)
    _core.print_fund_flow(flow_data)


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
def daily(date: str | None, refresh: bool, no_news: bool, report_format: str, only: str | None, order: str | None, quick: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    profile = load_profile()
    if not profile.get("stocks") and not profile.get("funds"):
        _print_first_use_guide()
        return
    _core.run_daily_report(date_str, profile, include_news=not no_news, report_format=report_format, only=only, order=order, quick=quick)


@cli.group(help="Manage local investment memory for daily reports.")
def profile() -> None:
    pass


@profile.command("add-stock", help="Add a stock/ETF symbol to your daily watchlist.")
@click.argument("symbol")
def profile_add_stock(symbol: str) -> None:
    data = add_profile_item("stocks", symbol)
    click.echo(f"Added stock: {symbol.strip()}")
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")


@profile.command("add-fund", help="Add a fund code to your daily watchlist.")
@click.argument("code")
def profile_add_fund(code: str) -> None:
    data = add_profile_item("funds", code)
    click.echo(f"Added fund: {code.strip()}")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")


@profile.command("list", help="Show saved daily-report investment memory.")
def profile_show() -> None:
    data = load_profile()
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")
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


@cli.command(help="Run a lightweight network/source diagnostic.")
def diagnose() -> None:
    click.echo("# 网络诊断")
    for name in ["eastmoney", "sina", "tencent", "ths", "futu"]:
        snap = _core.SOURCE_HEALTH.snapshot(name)
        state = "建议暂缓使用" if snap.should_skip else "可用/未发现近期异常"
        click.echo(f"{name}: 成功率 {snap.success_rate:.0%}, 平均延迟 {snap.average_latency_ms:.0f}ms, {state}")
    click.echo("建议: 若接口失败，可先使用缓存、加 --quick/--format summary，或稍后运行 --refresh 重试。")


@cli.command(help="New-user guide.")
def guide() -> None:
    click.echo("1. young profile add-stock 600519")
    click.echo("2. young profile add-fund 161725")
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
