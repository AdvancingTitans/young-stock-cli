"""Report composers built on top of the core quote/fund APIs."""
from __future__ import annotations

from typing import Any


def _daily_watchlist_items(watchlist: dict[str, list[str]] | None, key: str) -> list[str]:
    if not watchlist:
        return []
    values = watchlist.get(key) or []
    return [str(v).strip() for v in values if str(v).strip()]


def _quote_trend_label(change_pct: float | None) -> str:
    if change_pct is None:
        return "趋势待确认"
    if change_pct >= 2:
        return "强势上行"
    if change_pct >= 0.3:
        return "偏强"
    if change_pct <= -2:
        return "明显走弱"
    if change_pct <= -0.3:
        return "偏弱"
    return "震荡"


def print_daily_watchlist(core: Any, watchlist: dict[str, list[str]] | None, date_str: str, include_news: bool = True) -> None:
    stocks = _daily_watchlist_items(watchlist, "stocks")
    funds = _daily_watchlist_items(watchlist, "funds")
    print("## 一、关注标的\n")
    if not stocks and not funds:
        print("  尚未设置关注股票或基金。")
        print()
        return

    if stocks:
        print("### 个股/ETF行情与趋势\n")
        for symbol in stocks:
            try:
                qd = core.get_single_stock_quote(symbol, date_str)
            except ValueError as e:
                print(f"- {symbol}: 暂未拿到可核验行情（{e}）")
                continue
            if not qd:
                print(f"- {symbol}: 暂未拿到可核验行情")
                continue
            name = qd.name or qd.symbol
            print(
                f"- {name} ({qd.symbol}): 最新 {core.fmt_price(qd.price)} {qd.currency}, "
                f"涨跌幅 {core.fmt_pct(qd.change_pct)}, {_quote_trend_label(qd.change_pct)}；"
                f"来源 {core._source_label(qd.source)}，数据日 {qd.date or '-'}。"
            )
            if include_news:
                keyword = qd.name if qd.market in ("cn_market", "hk_market") and qd.name else qd.symbol
                lang = "zh-CN" if qd.market in ("cn_market", "hk_market") else "en"
                news = core.combined_news_search(
                    keyword,
                    size=3,
                    lang=lang,
                    aliases=core._news_aliases(qd.symbol, qd.name),
                    date_str=date_str,
                )
                items = news.get("data", []) if "_error" not in news else []
                if items:
                    title = core._clean_news_title(str(items[0].get("title") or ""))
                    print(f"  相关新闻: {title}")
        print()

    if funds:
        print("### 基金估值与持仓\n")
        for code in funds:
            core.run_fund_report(code, date_str, include_news=include_news)


def run_daily_report(
    core: Any,
    date_str: str,
    watchlist: dict[str, list[str]] | None = None,
    include_news: bool = True,
) -> None:
    core.DIAGNOSTICS.clear()
    display_date = core._display_date(date_str)
    print(f"# 每日行情日报（{display_date}）\n")
    core.print_stage_line(date_str)
    print("数据来源: young-stock-cli 核心模块，多源免登录行情与新闻聚合。")
    print("说明: 以下内容仅供复盘参考，不构成投资建议。\n")
    print("=" * 60 + "\n")

    print_daily_watchlist(core, watchlist, date_str, include_news=include_news)

    print("## 二、全球指数与大盘概览\n")
    core.run_global_market(date_str)

    print("## 三、A股大盘与市场情绪\n")
    core.run_a_share(date_str, include_news=include_news)

    print("## 四、投资建议\n")
    print("- 先看交易日与数据源日期是否一致；若出现最新可用数据提示，不把旧行情当成当日信号。")
    print("- 个股/基金优先结合持仓成本、仓位上限和新闻催化验证，不因单日涨跌直接追涨杀跌。")
    print("- 市场情绪偏弱或资金流口径降级时，降低加仓冲动；情绪修复时再观察量能和领涨方向持续性。")
    print("- 基金估值是盘中/收盘估算，正式净值以基金公司晚间披露为准。")
    print()

    if core.DIAGNOSTICS:
        core.print_diagnostic_summary()
    core.print_report_footer()
