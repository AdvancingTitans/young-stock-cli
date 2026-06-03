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
    report_format: str = "full",
    only: str | None = None,
    order: str | None = None,
    quick: bool = False,
) -> None:
    if report_format == "summary":
        print_daily_summary(core, date_str, watchlist, include_news=include_news, only=only)
        return
    if report_format == "key-points":
        print_daily_key_points(core, date_str, watchlist, include_news=include_news, only=only)
        return

    core.DIAGNOSTICS.clear()
    display_date = core._display_date(date_str)
    print(f"# 每日行情日报（{display_date}）\n")
    core.print_stage_line(date_str)
    print("数据来源: young-stock-cli 核心模块，多源免登录行情与新闻聚合。")
    print("说明: 以下内容仅供复盘参考，不构成投资建议。\n")
    print("=" * 60 + "\n")

    sections = _section_order(order)
    if _include_section("watchlist", only, sections):
        print_daily_watchlist(core, watchlist, date_str, include_news=include_news and not quick)

    if not quick and _include_section("global", only, sections):
        print("## 二、全球指数与大盘概览\n")
        core.run_global_market(date_str)

    if _include_section("a", only, sections):
        print("## 三、A股大盘与市场情绪\n")
        core.run_a_share(date_str, include_news=include_news and not quick)

    print("## 四、投资建议\n")
    print("- 先看交易日与数据源日期是否一致；若出现最新可用数据提示，不把旧行情当成当日信号。")
    print("- 个股/基金优先结合持仓成本、仓位上限和新闻催化验证，不因单日涨跌直接追涨杀跌。")
    print("- 市场情绪偏弱或资金流口径降级时，降低加仓冲动；情绪修复时再观察量能和领涨方向持续性。")
    print("- 基金估值是盘中/收盘估算，正式净值以基金公司晚间披露为准。")
    print()

    if core.DIAGNOSTICS:
        core.print_diagnostic_summary()
    core.print_report_footer()


def print_daily_summary(
    core: Any,
    date_str: str,
    watchlist: dict[str, list[str]] | None,
    include_news: bool = True,
    only: str | None = None,
) -> None:
    display_date = core._display_date(date_str)
    print(f"{display_date} 行情摘要")
    print("-" * 28)
    if _include_only("funds", only):
        print("你的基金: " + _fund_summary(core, watchlist, date_str))
    if _include_only("stocks", only):
        print("关注个股: " + _stock_summary(core, watchlist, date_str))
    if _include_only("a", only):
        print("A股: " + _a_index_summary(core, date_str))
        print("热点/资金: " + _flow_summary(core, date_str))
    if include_news and _include_only("news", only):
        print("新闻: 摘要模式不展开长新闻；需要详情可用 --format full")
    print("风险: 基金持仓按季报披露估算，若距今较久，可能已调仓；避免因单日涨跌追涨杀跌。")


def print_daily_key_points(
    core: Any,
    date_str: str,
    watchlist: dict[str, list[str]] | None,
    include_news: bool = True,
    only: str | None = None,
) -> None:
    print_daily_summary(core, date_str, watchlist, include_news=include_news, only=only)
    print()
    print("关键要点:")
    print(f"- 趋势: {_trend_hint(core, watchlist, date_str)}")
    print("- 风控: 若关注标的集中在同一主题，优先控制单一方向仓位。")
    print("- 操作: 使用 young diagnose 排查数据源；使用 --format full 查看完整复盘。")


def _fund_summary(core: Any, watchlist: dict[str, list[str]] | None, date_str: str) -> str:
    funds = _daily_watchlist_items(watchlist, "funds")
    if not funds:
        return "-"
    parts = []
    for code in funds[:6]:
        data = core.fetch_fund_estimate(code, date_str)
        pct = data.get("estimate_change_pct") if "_error" not in data else None
        parts.append(f"{code}({core.fmt_pct(pct)})")
    return "、".join(parts)


def _stock_summary(core: Any, watchlist: dict[str, list[str]] | None, date_str: str) -> str:
    stocks = _daily_watchlist_items(watchlist, "stocks")
    if not stocks:
        return "-"
    parts = []
    for symbol in stocks[:6]:
        try:
            qd = core.get_single_stock_quote(symbol, date_str)
        except ValueError:
            qd = None
        parts.append(f"{symbol}({core.fmt_pct(qd.change_pct) if qd else '-'})")
    return "、".join(parts)


def _a_index_summary(core: Any, date_str: str) -> str:
    names = {"000001": "上证", "399006": "创业板"}
    try:
        data = core.get_index(date_str)
    except Exception:
        data = []
    parts = []
    for item in data:
        code = str(item.get("f12", ""))
        if code in names:
            parts.append(f"{names[code]}{core.fmt_pct(item.get('f3'))}")
    return "、".join(parts) or "暂未获取到指数快照"


def _flow_summary(core: Any, date_str: str) -> str:
    try:
        flow = core.get_fund_flow(date_str, strict_date=False)
    except Exception:
        return "暂未获取到资金流"
    if flow.get("_fallback_indicator") == "concept_money_flow":
        return _json_top_names(flow.get("_concept_in"), limit=2) or "概念资金流暂无双边数据"
    if flow.get("_fallback_indicator") == "sector_money_flow":
        return _json_top_names(flow.get("_sector_in"), limit=2) or "行业资金流暂无数据"
    if flow.get("主力净流入"):
        return f"主力净流入 {core.fmt_amount(flow.get('主力净流入'))}"
    return "资金流暂无可核验数据"


def _json_top_names(raw: str | None, limit: int) -> str:
    import json

    if not raw:
        return ""
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    parts = []
    for row in rows[:limit]:
        name = row.get("name") or row.get("行业") or "-"
        net = row.get("net")
        parts.append(f"{name}({net:+.1f}亿)" if isinstance(net, (int, float)) else str(name))
    return "、".join(parts)


def _trend_hint(core: Any, watchlist: dict[str, list[str]] | None, date_str: str) -> str:
    stocks = _daily_watchlist_items(watchlist, "stocks")
    if not stocks:
        return "暂无关注个股，建议先设置投资记忆。"
    strong = weak = 0
    for symbol in stocks[:6]:
        try:
            qd = core.get_single_stock_quote(symbol, date_str)
        except ValueError:
            qd = None
        pct = qd.change_pct if qd else None
        if pct is not None and pct > 1:
            strong += 1
        elif pct is not None and pct < -1:
            weak += 1
    if strong > weak:
        return "关注标的偏强，留意放量后是否持续。"
    if weak > strong:
        return "关注标的偏弱，优先观察止跌和仓位风险。"
    return "关注标的分化或震荡，等待更明确方向。"


def _section_order(order: str | None) -> list[str]:
    if not order:
        return ["watchlist", "global", "a"]
    mapping = {"基金": "watchlist", "个股": "watchlist", "关注": "watchlist", "A股": "a", "a": "a", "港股": "global", "美股": "global", "global": "global"}
    return [mapping.get(part.strip(), part.strip()) for part in order.split(",") if part.strip()]


def _include_only(section: str, only: str | None) -> bool:
    if not only:
        return True
    aliases = {
        "funds": {"funds", "基金"},
        "stocks": {"stocks", "stock", "个股", "股票"},
        "a": {"a", "A股", "a股"},
        "news": {"news", "新闻"},
    }
    requested = {part.strip() for part in only.split(",") if part.strip()}
    return bool(aliases.get(section, {section}) & requested)


def _include_section(section: str, only: str | None, sections: list[str]) -> bool:
    if only:
        if section == "watchlist":
            return _include_only("funds", only) or _include_only("stocks", only)
        return _include_only(section, only)
    return section in sections
