"""young-stock-cli command line interface."""
from __future__ import annotations

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


def _run(market: str, date: str | None, refresh: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    if market == "a":
        _core.run_a_share(date_str)
    elif market == "hk":
        _core.run_hk_market(date_str)
    elif market == "us":
        _core.run_us_market(date_str)
    elif market == "global":
        _core.run_global_market(date_str)
    else:
        click.echo(f"unknown market: {market}", err=True)
        sys.exit(1)


_date_opt = click.option("--date", "-d", default=None, help="Trade date YYYYMMDD (default: nearest trade day).")
_refresh_opt = click.option("--refresh", is_flag=True, help="Skip cache and force re-fetch.")


@cli.command(help="A-share after-hours dashboard: indices, ZT/DT pool, fund flow, boards.")
@_date_opt
@_refresh_opt
def a(date: str | None, refresh: bool) -> None:
    _run("a", date, refresh)


@cli.command(help="Hong Kong market after-hours snapshot.")
@_date_opt
@_refresh_opt
def hk(date: str | None, refresh: bool) -> None:
    _run("hk", date, refresh)


@cli.command(help="US market after-hours snapshot.")
@_date_opt
@_refresh_opt
def us(date: str | None, refresh: bool) -> None:
    _run("us", date, refresh)


@cli.command(name="global", help="Global indices snapshot (A + HK + US).")
@_date_opt
@_refresh_opt
def global_(date: str | None, refresh: bool) -> None:
    _run("global", date, refresh)


@cli.command(help="Show A-share major indices only.")
@_date_opt
def indices(date: str | None) -> None:
    date_str = date or _core.nearest_trade_date()
    data = _core.get_index(date_str)
    _core.print_index(data)


@cli.command(name="zt-pool", help="Show A-share limit-up (涨停) pool.")
@_date_opt
def zt_pool(date: str | None) -> None:
    date_str = date or _core.nearest_trade_date()
    zt = _core.get_zt_pool(date_str)
    dt = _core.get_dt_pool(date_str)
    zb = _core.get_zb_pool(date_str)
    _core.print_zt_analysis(zt, dt, zb)


@cli.command(help="Show A-share fund flow (north-bound, main capital).")
@_date_opt
def flow(date: str | None) -> None:
    date_str = date or _core.nearest_trade_date()
    flow_data = _core.get_fund_flow(date_str)
    _core.print_fund_flow(flow_data)


@cli.command(help="Clear cached responses older than N days.")
@click.option("--days", default=7, show_default=True, help="Delete cache files older than this many days.")
def cache_clear(days: int) -> None:
    _core.cache_clear_old(days=days)
    click.echo(f"Cleared cache older than {days} days.")


if __name__ == "__main__":
    cli()
