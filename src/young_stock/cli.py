"""young-stock-cli command line interface."""
from __future__ import annotations

import subprocess
import sys

import click

from . import __version__, _core
from .profile import add_profile_item, load_profile, profile_path


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
def daily(date: str | None, refresh: bool, no_news: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    profile = load_profile()
    if not profile.get("stocks") and not profile.get("funds"):
        _print_first_use_guide()
        return
    _core.run_daily_report(date_str, profile, include_news=not no_news)


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


@profile.command("show", help="Show saved daily-report investment memory.")
def profile_show() -> None:
    data = load_profile()
    click.echo(f"Stocks: {', '.join(data.get('stocks', [])) or '-'}")
    click.echo(f"Funds: {', '.join(data.get('funds', [])) or '-'}")


@cli.command(help="Clear cached responses older than N days.")
@click.option("--days", default=7, show_default=True, help="Delete cache files older than this many days.")
def cache_clear(days: int) -> None:
    _core.cache_clear_old(days=days)
    click.echo(f"Cleared cache older than {days} days.")


if __name__ == "__main__":
    cli()
