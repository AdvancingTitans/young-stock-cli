"""young-stock-cli command line interface."""
from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from typing import Any

import click

from . import __version__, _core


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="A-share & global market after-hours CLI. No login, no scraping tricks.",
)
@click.version_option(__version__, "-V", "--version", message="young-stock-cli %(version)s")
def cli() -> None:
    pass


def _json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _echo_json(payload: Any) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _run(market: str, date: str | None, refresh: bool, as_json: bool = False) -> None:
    if refresh:
        _core.NO_CACHE = True
    _core.cache_clear_old(days=7)
    date_str = date or _core.nearest_trade_date()
    if as_json:
        if market == "a":
            _echo_json(_a_share_payload(date_str))
        elif market == "hk":
            _echo_json(_hk_market_payload(date_str))
        elif market == "us":
            _echo_json(_us_market_payload(date_str))
        elif market == "global":
            _echo_json(_global_market_payload(date_str))
        else:
            click.echo(f"unknown market: {market}", err=True)
            sys.exit(1)
        return
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
_json_opt = click.option("--json", "as_json", is_flag=True, help="Output raw data as JSON.")


def _a_share_payload(date_str: str) -> dict[str, Any]:
    zt = _core.get_zt_pool(date_str)
    dt = _core.get_dt_pool(date_str)
    zb = _core.get_zb_pool(date_str)
    return {
        "date": date_str,
        "indices": _core.get_index(date_str),
        "zt_pool": zt,
        "dt_pool": dt,
        "zb_pool": zb,
        "flow": _core.get_fund_flow(date_str),
    }


def _zt_payload(date_str: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "zt_pool": _core.get_zt_pool(date_str),
        "dt_pool": _core.get_dt_pool(date_str),
        "zb_pool": _core.get_zb_pool(date_str),
    }


def _us_market_payload(date_str: str) -> dict[str, Any]:
    symbols = {"^GSPC": "标普 500", "^IXIC": "纳斯达克"}
    return {"date": date_str, "indices": _core.fetch_us_indices_sina(symbols, date_str)}


def _hk_market_payload(date_str: str) -> dict[str, Any]:
    symbols = {"^HSI": "恒生指数", "^HSCE": "国企指数", "HSTECH.HK": "恒生科技指数"}
    return {"date": date_str, "indices": _core.fetch_hk_indices_tencent(symbols, date_str)}


def _global_market_payload(date_str: str) -> dict[str, Any]:
    return {
        "date": date_str,
        "a": _core.get_index(date_str),
        "hk": _hk_market_payload(date_str)["indices"],
        "us": _us_market_payload(date_str)["indices"],
    }


@cli.command(help="A-share after-hours dashboard: indices, ZT/DT pool, fund flow, boards.")
@_date_opt
@_refresh_opt
@_json_opt
@click.option("--zt", is_flag=True, help="Only show limit-up/down pool data.")
def a(date: str | None, refresh: bool, as_json: bool, zt: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    if zt:
        payload = _zt_payload(date_str)
        if as_json:
            _echo_json(payload)
        else:
            _core.print_zt_analysis(payload["zt_pool"], payload["dt_pool"], payload["zb_pool"])
        return
    _run("a", date, refresh, as_json=as_json)


@cli.command(help="Hong Kong market after-hours snapshot.")
@_date_opt
@_refresh_opt
@_json_opt
def hk(date: str | None, refresh: bool, as_json: bool) -> None:
    _run("hk", date, refresh, as_json=as_json)


@cli.command(help="US market after-hours snapshot.")
@_date_opt
@_refresh_opt
@_json_opt
def us(date: str | None, refresh: bool, as_json: bool) -> None:
    _run("us", date, refresh, as_json=as_json)


@cli.command(name="global", help="Global indices snapshot (A + HK + US).")
@_date_opt
@_refresh_opt
@_json_opt
def global_(date: str | None, refresh: bool, as_json: bool) -> None:
    _run("global", date, refresh, as_json=as_json)


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
@_json_opt
def indices(date: str | None, refresh: bool, as_json: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    data = _core.get_index(date_str)
    if as_json:
        _echo_json({"date": date_str, "indices": data})
        return
    _core.print_index(data)


@cli.command(name="zt-pool", help="Show A-share limit-up (涨停) pool.")
@_date_opt
@_refresh_opt
@_json_opt
def zt_pool(date: str | None, refresh: bool, as_json: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    payload = _zt_payload(date_str)
    if as_json:
        _echo_json(payload)
        return
    _core.print_zt_analysis(payload["zt_pool"], payload["dt_pool"], payload["zb_pool"])


@cli.command(help="Show A-share fund flow (north-bound, main capital).")
@_date_opt
@_refresh_opt
@_json_opt
def flow(date: str | None, refresh: bool, as_json: bool) -> None:
    if refresh:
        _core.NO_CACHE = True
    date_str = date or _core.nearest_trade_date()
    flow_data = _core.get_fund_flow(date_str)
    if as_json:
        _echo_json({"date": date_str, "flow": flow_data})
        return
    _core.print_fund_flow(flow_data)


@cli.command(help="Clear cached responses older than N days.")
@click.option("--days", default=7, show_default=True, help="Delete cache files older than this many days.")
def cache_clear(days: int) -> None:
    _core.cache_clear_old(days=days)
    click.echo(f"Cleared cache older than {days} days.")


if __name__ == "__main__":
    cli()
