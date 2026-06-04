"""Report composers built on top of the core quote/fund APIs."""
from __future__ import annotations

from typing import Any

THEME_KEYWORDS = {
    "科技成长/AI": ("AI", "人工智能", "芯片", "半导体", "算力", "CPO", "光通信", "NVDA", "英伟达", "服务器"),
    "消费品牌": ("白酒", "消费", "茅台", "五粮液", "苹果", "Apple", "品牌"),
    "金融地产": ("银行", "保险", "券商", "地产", "房地产"),
    "新能源": ("新能源", "电池", "光伏", "储能", "汽车", "特斯拉", "Tesla"),
}

POSITIVE_NEWS_KEYWORDS = (
    "增长", "新高", "超预期", "回购", "增持", "获批", "中标", "订单", "需求", "盈利", "现金流", "韧性", "突破", "上调"
)
NEGATIVE_NEWS_KEYWORDS = (
    "下滑", "亏损", "减持", "调查", "处罚", "诉讼", "裁员", "降级", "放缓", "跌破", "风险", "监管", "召回", "违约"
)


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
    for note in _portfolio_advice(core, watchlist, date_str, include_news=include_news and not quick):
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
    print("持仓建议: " + _portfolio_summary(core, watchlist, date_str, include_news=include_news))


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
    key_points = _portfolio_key_points(core, watchlist, date_str, include_news=include_news)
    for title, notes in key_points:
        print(f"{title}:")
        for note in notes:
            print(f"- {note}")
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


def _portfolio_advice(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> list[str]:
    sections = _portfolio_key_points(core, watchlist, date_str, include_news=include_news)
    notes = [note for _, values in sections for note in values]
    if not notes:
        return ["先设置关注股票/基金后再生成个性化建议；没有标的时只适合做市场复盘，不适合给仓位动作。"]
    return notes[:8]


def _portfolio_summary(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> str:
    context = _portfolio_context(core, watchlist, date_str, include_news=include_news)
    fund_notes = _fund_position_notes(core, context, compact=True)
    stock_notes = _stock_position_notes(core, context, compact=True)
    overall = _overall_position_notes(core, context, compact=True)
    parts = []
    if fund_notes:
        parts.append("基金: " + fund_notes[0].rstrip("。"))
    if stock_notes:
        parts.append("个股: " + stock_notes[0].rstrip("。"))
    if overall:
        parts.append("综合: " + overall[0].rstrip("。"))
    return "；".join(parts) if parts else "暂无关注标的，先设置投资记忆后再输出持仓建议。"


def _portfolio_key_points(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> list[tuple[str, list[str]]]:
    context = _portfolio_context(core, watchlist, date_str, include_news=include_news)
    sections = [
        ("基金分析", _fund_position_notes(core, context)),
        ("个股分析", _stock_position_notes(core, context)),
        ("综合持仓", _overall_position_notes(core, context)),
    ]
    return [(title, notes) for title, notes in sections if notes]


def _portfolio_context(
    core: Any,
    watchlist: dict[str, list[str]] | None,
    date_str: str,
    include_news: bool = True,
) -> dict[str, Any]:
    quotes = []
    news_titles: dict[str, list[str]] = {}
    positions = watchlist.get("positions", {}) if watchlist else {}
    stock_positions = positions.get("stocks", {}) if isinstance(positions, dict) else {}
    fund_positions = positions.get("funds", {}) if isinstance(positions, dict) else {}
    stock_buy_prices: dict[str, dict[str, Any]] = {}
    fund_buy_navs: dict[str, dict[str, Any]] = {}
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
        position = stock_positions.get(symbol) or stock_positions.get(getattr(qd, "symbol", ""))
        if isinstance(position, dict) and position.get("buy_date"):
            stock_buy_prices[symbol] = core.fetch_stock_close_on_or_after(symbol, str(position["buy_date"]))

    funds = []
    for code in _daily_watchlist_items(watchlist, "funds")[:6]:
        data = core.fetch_fund_estimate(code, date_str)
        if "_error" not in data:
            funds.append(data)
        else:
            funds.append({"fundcode": code, "_error": data.get("_error")})
        position = fund_positions.get(code)
        if isinstance(position, dict) and position.get("buy_date"):
            fund_buy_navs[code] = core.fetch_fund_nav_on_or_after(code, str(position["buy_date"]))
    return {
        "quotes": quotes,
        "funds": funds,
        "news_titles": news_titles,
        "positions": {"stocks": stock_positions, "funds": fund_positions},
        "stock_buy_prices": stock_buy_prices,
        "fund_buy_navs": fund_buy_navs,
    }


def _fund_position_notes(core: Any, context: dict[str, Any], compact: bool = False) -> list[str]:
    funds = context.get("funds", [])
    positions = context.get("positions", {}).get("funds", {})
    buy_navs = context.get("fund_buy_navs", {})
    notes = []
    for fund in funds:
        code = str(fund.get("fundcode") or fund.get("code") or "")
        if not code:
            continue
        pct = _to_float(fund.get("estimate_change_pct"))
        position = positions.get(code, {}) if isinstance(positions, dict) else {}
        buy_nav = buy_navs.get(code, {}) if isinstance(buy_navs, dict) else {}
        current_nav = _to_float(fund.get("estimate_nav")) or _to_float(fund.get("nav"))
        pnl = _position_return(current_nav, buy_nav.get("nav"), position.get("quantity"))
        pnl_text = _pnl_text(core, pnl)
        stance = "持有观察" if pct is None or pct >= -2 else "谨慎观察"
        if compact:
            notes.append(f"{code}{core.fmt_pct(pct)}，{pnl_text}，建议“{stance}”。")
        else:
            base = f"{code} 今日估值 {core.fmt_pct(pct)}，{pnl_text}，建议“{stance}”。"
            if position.get("buy_date"):
                base += f"买入日 {position.get('buy_date')}，买入净值采用 {buy_nav.get('date', '待获取')} 附近可用净值。"
            base += "重点跟踪基金持仓时效、基金经理风格漂移，以及与自选个股是否重复暴露。"
            notes.append(base)
    return notes


def _stock_position_notes(core: Any, context: dict[str, Any], compact: bool = False) -> list[str]:
    quotes = context.get("quotes", [])
    positions = context.get("positions", {}).get("stocks", {})
    buy_prices = context.get("stock_buy_prices", {})
    news_titles = context.get("news_titles", {})
    notes = []
    for qd in quotes:
        symbol = qd.symbol
        name = qd.name or symbol
        position = positions.get(symbol) or positions.get(symbol.upper()) or {}
        buy_price = buy_prices.get(symbol) or buy_prices.get(symbol.upper()) or {}
        news_label, news_reason, news_score = _news_signal(news_titles.get(symbol, []))
        stance, action_reason = _manager_stance(qd.change_pct, news_score)
        pnl = _position_return(qd.price, buy_price.get("close"), position.get("quantity"))
        pnl_text = _pnl_text(core, pnl)
        if compact:
            notes.append(f"{name}({symbol}) {core.fmt_pct(qd.change_pct)}，{news_label}，{pnl_text}，建议“{stance}”。")
        else:
            base = (
                f"{name}({symbol}) 今日 {core.fmt_pct(qd.change_pct)}，{news_label}{news_reason}，{pnl_text}，"
                f"建议“{stance}”。{action_reason}"
            )
            if position.get("buy_date"):
                base += f"买入日 {position.get('buy_date')}，买入价采用 {buy_price.get('date', '待获取')} 附近可用收盘价。"
            base += "持有跟踪项：新闻催化是否延续、成交/趋势是否确认、基本面数据是否支持当前估值；减仓条件：新闻转负、趋势跌破或组合单一主题过度集中。"
            notes.append(base)
    return notes


def _overall_position_notes(core: Any, context: dict[str, Any], compact: bool = False) -> list[str]:
    notes = []
    quotes = context.get("quotes", [])
    funds = context.get("funds", [])
    themes = _theme_exposure(quotes, context.get("news_titles", {}))
    total_cost = total_value = 0.0
    for qd in quotes:
        position = context.get("positions", {}).get("stocks", {}).get(qd.symbol, {})
        buy_price = context.get("stock_buy_prices", {}).get(qd.symbol, {})
        pnl = _position_return(qd.price, buy_price.get("close"), position.get("quantity"))
        if pnl:
            total_cost += pnl["cost"]
            total_value += pnl["value"]
    for fund in funds:
        code = str(fund.get("fundcode") or fund.get("code") or "")
        position = context.get("positions", {}).get("funds", {}).get(code, {})
        buy_nav = context.get("fund_buy_navs", {}).get(code, {})
        current_nav = _to_float(fund.get("estimate_nav")) or _to_float(fund.get("nav"))
        pnl = _position_return(current_nav, buy_nav.get("nav"), position.get("quantity"))
        if pnl:
            total_cost += pnl["cost"]
            total_value += pnl["value"]

    if total_cost:
        total_pct = (total_value / total_cost - 1) * 100
        notes.append(f"组合买入以来估算收益 {core.fmt_pct(total_pct)}，成本约 {core.fmt_price(total_cost)}，现值约 {core.fmt_price(total_value)}。")
    elif compact:
        notes.append("组合收益待补买入日期和数量，系统将自动回溯买入日净值/价格。")

    if themes:
        top_theme, names = max(themes.items(), key=lambda item: len(item[1]))
        if len(names) >= 2:
            notes.append(f"主题集中度偏高：{top_theme} 覆盖 {', '.join(names[:4])}，基金与个股需避免重复押注同一景气线。")
    if funds and quotes:
        notes.append("综合建议：先把基金作为底仓/行业暴露工具，把个股作为增强仓；新增资金优先投向低相关、估值和新闻趋势更匹配的方向。")
    elif funds:
        notes.append("综合建议：当前以基金为主，重点看基金风格、持仓时效和回撤承受能力。")
    elif quotes:
        notes.append("综合建议：当前以个股为主，建议设置单票仓位上限，并补充低相关资产降低波动。")
    return notes[:1] if compact and notes else notes


def _position_return(current_price: Any, buy_price: Any, quantity: Any) -> dict[str, float] | None:
    current = _to_float(current_price)
    buy = _to_float(buy_price)
    qty = _to_float(quantity)
    if current is None or buy is None or qty is None or buy <= 0 or qty <= 0:
        return None
    cost = buy * qty
    value = current * qty
    return {"cost": cost, "value": value, "amount": value - cost, "pct": (value / cost - 1) * 100}


def _pnl_text(core: Any, pnl: dict[str, float] | None) -> str:
    if not pnl:
        return "买入以来收益待获取买入日价格/净值后估算"
    return f"买入以来 {core.fmt_pct(pnl['pct'])}（约 {core.fmt_price(pnl['amount'])}）"


def _theme_exposure(quotes: list[Any], news_titles: dict[str, list[str]]) -> dict[str, list[str]]:
    exposure: dict[str, list[str]] = {}
    for qd in quotes:
        blob = " ".join([qd.symbol or "", qd.name or "", *news_titles.get(qd.symbol, [])])
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword.lower() in blob.lower() for keyword in keywords):
                exposure.setdefault(theme, []).append(qd.name or qd.symbol)
                break
    return exposure


def _news_signal(headlines: list[str]) -> tuple[str, str, int]:
    if not headlines:
        return "新闻信号不足", "（未拿到可核验的当天高信号新闻）", 0
    blob = " ".join(headlines)
    positive = sum(1 for word in POSITIVE_NEWS_KEYWORDS if word.lower() in blob.lower())
    negative = sum(1 for word in NEGATIVE_NEWS_KEYWORDS if word.lower() in blob.lower())
    score = positive - negative
    if score > 0:
        return "新闻偏正面", f"（{headlines[0]}）", score
    if score < 0:
        return "新闻偏负面", f"（{headlines[0]}）", score
    return "新闻偏中性", f"（{headlines[0]}）", score


def _manager_stance(change_pct: float | None, news_score: int) -> tuple[str, str]:
    pct = change_pct or 0
    if pct >= 3 and news_score >= 0:
        return "持有观察", "趋势和消息面同向，但上涨后更要防止为好消息支付过高价格。"
    if pct >= 3 and news_score < 0:
        return "冲高谨慎", "价格上涨但新闻质量不配合，优先保护已有收益。"
    if pct <= -3 and news_score < 0:
        return "降低仓位观察", "价格和消息面共振走弱，先控制组合回撤。"
    if pct <= -3:
        return "观察验证", "价格走弱但新闻未确认基本面恶化，不急于把波动等同于价值受损。"
    if news_score > 0:
        return "持有观察", "新闻边际偏正面但价格未充分确认，适合等待趋势延续证据。"
    if news_score < 0:
        return "谨慎观察", "新闻边际偏负面但价格未剧烈反应，适合先收紧风险预算。"
    return "中性观察", "行情和新闻都未给出足够强的方向信号。"


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
