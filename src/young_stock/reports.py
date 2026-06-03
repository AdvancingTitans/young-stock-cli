"""Report composers built on top of the core quote/fund APIs."""
from __future__ import annotations

from typing import Any

THEME_KEYWORDS = {
    "科技成长/AI": ("AI", "人工智能", "芯片", "半导体", "算力", "CPO", "光通信", "NVDA", "英伟达", "服务器"),
    "消费品牌": ("白酒", "消费", "茅台", "五粮液", "苹果", "Apple", "品牌"),
    "金融地产": ("银行", "保险", "券商", "地产", "房地产"),
    "新能源": ("新能源", "电池", "光伏", "储能", "汽车", "特斯拉", "Tesla"),
}


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
    for note in _buffett_advice(core, watchlist, date_str, include_news=include_news and not quick):
        print(f"- {note}")
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
    print("风险: " + _buffett_summary_risk(core, watchlist, date_str, include_news=include_news))


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
    for note in _buffett_key_points(core, watchlist, date_str, include_news=include_news):
        print(f"- 风控: {note}")
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


def _buffett_advice(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> list[str]:
    context = _buffett_context(core, watchlist, date_str, include_news=include_news)
    notes = _buffett_key_points_from_context(core, context)
    if not notes:
        return ["先设置关注股票/基金后再生成个性化建议；没有标的时只适合做市场复盘，不适合给仓位动作。"]
    return notes[:6]


def _buffett_summary_risk(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> str:
    context = _buffett_context(core, watchlist, date_str, include_news=include_news)
    notes = _buffett_key_points_from_context(core, context)
    if notes:
        return notes[0]
    funds = _daily_watchlist_items(watchlist, "funds")
    if funds:
        return f"{'、'.join(funds[:3])} 仅能看到净值/估值变化，先核对季报持仓时效，再决定是否调整仓位。"
    return "暂无关注标的，先设置投资记忆后再做能力圈、安全边际和主题集中度检查。"


def _buffett_key_points(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> list[str]:
    context = _buffett_context(core, watchlist, date_str, include_news=include_news)
    notes = _buffett_key_points_from_context(core, context)
    return notes[:3] or ["暂无关注标的，先设置投资记忆后再输出个性化风险。"]


def _buffett_context(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> dict[str, Any]:
    quotes = []
    news_titles: dict[str, list[str]] = {}
    for symbol in _daily_watchlist_items(watchlist, "stocks")[:8]:
        try:
            qd = core.get_single_stock_quote(symbol, date_str)
        except ValueError:
            qd = None
        if qd:
            quotes.append(qd)
            if include_news:
                keyword = qd.name if qd.market in ("cn_market", "hk_market") and qd.name else qd.symbol
                lang = "zh-CN" if qd.market in ("cn_market", "hk_market") else "en"
                news = core.combined_news_search(
                    keyword,
                    size=2,
                    lang=lang,
                    aliases=core._news_aliases(qd.symbol, qd.name),
                    date_str=date_str,
                )
                items = news.get("data", []) if "_error" not in news else []
                news_titles[qd.symbol] = [
                    core._clean_news_title(str(item.get("title") or ""))
                    for item in items
                    if item.get("title")
                ][:2]

    funds = []
    for code in _daily_watchlist_items(watchlist, "funds")[:6]:
        data = core.fetch_fund_estimate(code, date_str)
        if "_error" not in data:
            funds.append(data)
        else:
            funds.append({"fundcode": code, "_error": data.get("_error")})
    return {"quotes": quotes, "funds": funds, "news_titles": news_titles}


def _buffett_key_points_from_context(core: Any, context: dict[str, Any]) -> list[str]:
    quotes = context.get("quotes", [])
    funds = context.get("funds", [])
    news_titles = context.get("news_titles", {})
    notes: list[str] = []

    leaders = sorted(
        [q for q in quotes if q.change_pct is not None],
        key=lambda q: abs(q.change_pct or 0),
        reverse=True,
    )
    if leaders:
        qd = leaders[0]
        name = qd.name or qd.symbol
        headlines = news_titles.get(qd.symbol, [])
        news_hint = f"；新闻线索：{headlines[0]}" if headlines else ""
        if (qd.change_pct or 0) >= 3:
            notes.append(
                f"{name}({qd.symbol}) 今日 {core.fmt_pct(qd.change_pct)}，先用安全边际检查估值和盈利质量，不能把上涨直接当成内在价值提升{news_hint}。"
            )
        elif (qd.change_pct or 0) <= -3:
            notes.append(
                f"{name}({qd.symbol}) 今日 {core.fmt_pct(qd.change_pct)}，按 Buffett 框架区分价格波动和护城河受损；若新闻指向监管、需求或现金流恶化，再考虑降级{news_hint}。"
            )
        else:
            notes.append(
                f"{name}({qd.symbol}) 波动最大但仅 {core.fmt_pct(qd.change_pct)}，更适合观察业务质量与估值位置，不必因日内报价改变长期判断。"
            )

    themes = _theme_exposure(quotes, news_titles)
    if themes:
        top_theme, names = max(themes.items(), key=lambda item: len(item[1]))
        if len(names) >= 2:
            notes.append(
                f"主题集中度偏高：{top_theme} 覆盖 {', '.join(names[:4])}；需要确认这些标的是可理解的能力圈和可持续护城河，而不是同一条景气线的重复押注。"
            )
        else:
            notes.append(
                f"能力圈检查：{names[0]} 暂归入 {top_theme}，后续建议补 PE/PB/ROE、自由现金流和竞争优势证据，再谈加仓。"
            )

    strong_funds = []
    weak_funds = []
    for fund in funds:
        code = str(fund.get("fundcode") or fund.get("code") or "")
        pct = _to_float(fund.get("estimate_change_pct"))
        if pct is not None and pct >= 2:
            strong_funds.append(f"{code}{core.fmt_pct(pct)}")
        elif pct is not None and pct <= -2:
            weak_funds.append(f"{code}{core.fmt_pct(pct)}")
    if strong_funds:
        notes.append(
            f"基金 {', '.join(strong_funds[:3])} 估值偏强，但基金持仓来自季报且可能已调仓；把它当净值线索，不把估算涨幅当买入理由。"
        )
    elif weak_funds:
        notes.append(
            f"基金 {', '.join(weak_funds[:3])} 估值偏弱，先查重仓行业是否发生长期逻辑变化；若只是市场先生报价波动，仓位动作应服从原先配置上限。"
        )
    elif funds:
        codes = [str(fund.get("fundcode") or fund.get("code") or "") for fund in funds if fund.get("fundcode") or fund.get("code")]
        notes.append(
            f"基金 {', '.join(codes[:3])} 暂无极端估值波动；重点看持仓时效、基金经理风格漂移和与已关注个股的重合度。"
        )

    if quotes and not any("安全边际" in note for note in notes):
        names = "、".join((q.name or q.symbol) for q in quotes[:3])
        notes.append(f"{names} 的下一步不是追涨杀跌，而是补一张估值表：合理买入价、可承受回撤、退出条件和机会成本。")

    return notes


def _theme_exposure(quotes: list[Any], news_titles: dict[str, list[str]]) -> dict[str, list[str]]:
    exposure: dict[str, list[str]] = {}
    for qd in quotes:
        blob = " ".join([qd.symbol or "", qd.name or "", *news_titles.get(qd.symbol, [])])
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword.lower() in blob.lower() for keyword in keywords):
                exposure.setdefault(theme, []).append(qd.name or qd.symbol)
                break
    return exposure


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


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
