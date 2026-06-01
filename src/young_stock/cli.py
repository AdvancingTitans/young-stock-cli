"""young-stock-cli command line interface."""
from __future__ import annotations

import subprocess
import sys

import click

from . import __version__, _core


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
        _core.run_a_share(date_str)
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


@cli.command(help="A-share dashboard: indices, ZT/DT pool, verified A-share fund flow, boards.")
@_date_opt
@_refresh_opt
def a(date: str | None, refresh: bool) -> None:
    _run("a", date, refresh)


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


@cli.command(help="Show multi-source news for one stock, e.g. 600519, 0700.HK, AAPL.")
@click.argument("symbol")
@_date_opt
@_refresh_opt
@click.option("--limit", default=8, show_default=True, help="Maximum news items to show.")
def news(symbol: str, date: str | None, refresh: bool, limit: int) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    _core.run_stock_news(symbol, date_str, size=limit)


@cli.command(help="Clear cached responses older than N days.")
@click.option("--days", default=7, show_default=True, help="Delete cache files older than this many days.")
def cache_clear(days: int) -> None:
    _core.cache_clear_old(days=days)
    click.echo(f"Cleared cache older than {days} days.")


if __name__ == "__main__":
    cli()
