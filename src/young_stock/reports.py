"""Report composers built on top of the core quote/fund APIs."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from .debate import DebateEngine, build_institutional_prompt
from .lens import build_lens_prompt
from .llm import LLMError
from .research_style import review_research_report, to_research_evidence, to_research_methodology
from .review_gate import review_investment_output

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

LLM_REPORT_PROMPT_VERSION = "young-research-language-v4"
LLM_REPORT_SYSTEM_PROMPT = """请基于用户提供的研报证据，撰写正式 A 股投资研究报告。
你只能使用用户提供的研报证据，不得补写或外推任何缺失数字、日期、来源或持仓。
你必须严格遵循 young-stock-cli 的 M1-M6 框架，并在其后新增 M7；默认 balanced 时不得把 M1-M6 替换、弱化或改写成任何个人投资框架。
按以下顺序输出 Markdown：大盘指数概览、持仓分析、六模块深度复盘、M7 机构化综合判断、综合持仓建议与风险提示。
“六模块深度复盘”下固定使用以下子标题顺序：M1 大盘指数与市场广度、M2 板块强弱与资金流、M3 赚钱效应与涨停结构、M4 下跌风险与炸板结构、M5 持仓与市场风格、M6 抗跌方向。
每个有证据的模块给出关键判断、证据、风险/确认条件；建议必须是条件化触发器，不给无条件买卖指令。
证据完整度不足时，只输出指数、持仓、已验证风险和下一交易日观察清单。
正文只写投资研究语言。不得出现内部字段名、程序结构、工具名称、本地路径、文件扩展名、技术切换过程或机械占位段。
某模块无证据时优先省略该小节；确需说明时使用“相关指标当日未披露”或“历史数据不可得”等自然表述。
正常数据使用“据公开市场数据”或“据交易所及财经终端披露”；回溯数据使用“按惯例回溯至该日”或“历史口径回溯”。
公开版会在标题下统一加入短声明；不要重复免责声明，也不要在结尾追加长免责声明。"""

LLM_REPORT_STRUCTURE_PROMPT = """输出结构必须固定：
# 标题
## 大盘指数概览
## 持仓分析
## 六模块深度复盘
### M1 大盘指数与市场广度
### M2 板块强弱与资金流
### M3 赚钱效应与涨停结构
### M4 下跌风险与炸板结构
### M5 持仓与市场风格
### M6 抗跌方向
## M7 机构化综合判断
## 综合持仓建议与风险提示

只有显式 lens 系统消息可以约束 M7 的专家视角；不得把 M1-M6 改写成人物风格模板。"""

MODULE_TITLES = {
    "M1": "大盘指数与市场广度",
    "M2": "板块强弱与资金流",
    "M3": "赚钱效应与涨停结构",
    "M4": "下跌风险与炸板结构",
    "M5": "持仓与市场风格",
    "M6": "抗跌方向",
    "STOCK": "个股证据",
}

FIELD_TITLES = {
    "a_indices": "A股指数",
    "hk_indices": "港股指数",
    "us_indices": "美股指数",
    "northbound": "北向资金",
    "breadth": "市场广度",
    "industry": "行业板块",
    "concept": "概念板块",
    "fund_flow": "资金流",
    "zt_count": "涨停家数",
    "zt_pool": "涨停明细",
    "early_limit_up_count": "早盘涨停家数",
    "dt_count": "跌停家数",
    "zb_count": "炸板家数",
    "blowup_ratio": "炸板率",
    "dt_pool": "跌停明细",
    "zb_pool": "炸板明细",
    "holdings": "持仓",
    "style_signals": "风格观察",
    "growth_board_count": "科创板与创业板活跃样本数",
    "resilient": "抗跌方向",
    "quote": "行情",
    "block_trades": "大宗交易",
    "news": "公开信息",
    "trade_date": "交易日",
    "quality_score": "证据完整度评分",
    "missing_modules": "证据暂缺模块",
    "degrade_mode": "报告范围",
    "source_events": "数据状态",
    "methodology": "研究框架",
    "analysis_symbol": "分析标的",
    "report_type": "报告类型",
    "source": "数据来源",
}

INTERNAL_FIELD_TITLES = {
    "_source": "数据来源",
    "_source_date": "数据日期",
    "_requested_date": "请求日期",
    "_scope": "统计范围",
    "_date_note": "日期说明",
    "_cache_note": "日期说明",
}

REPAIR_PROMPT = """你上一版输出未通过机械校验。只做约束内修复，不得新增证据外数字或主观评分。
必须保留正式 Markdown，并补齐以下字段语义：总体态度、详细结论、证据、风险、行动建议、观察清单。
如果原文已有内容，只能重写为合规表达；若证据不足，明确写“证据暂缺”。"""


def _public_source(value: Any) -> Any:
    text = str(value or "")
    source_names = []
    for token, label in (
        ("腾讯", "腾讯财经"),
        ("sina", "新浪财经"),
        ("新浪", "新浪财经"),
        ("eastmoney", "东方财富"),
        ("东方财富", "东方财富"),
        ("东财", "东方财富"),
        ("同花顺", "同花顺"),
        ("ths", "同花顺"),
        ("futu", "富途公开资讯"),
        ("富途", "富途公开资讯"),
    ):
        if token.lower() in text.lower() and label not in source_names:
            source_names.append(label)
    return "、".join(source_names) if source_names else "公开市场数据"


def _research_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_research_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "available":
            result["证据状态"] = "据公开市场数据" if item else "本模块证据暂缺"
            continue
        if key in {"source", "_source"}:
            result["数据来源"] = _public_source(item)
            continue
        if key in {"_date_note", "_cache_note"}:
            result["日期说明"] = "历史口径回溯"
            continue
        if key == "missing_modules":
            result["证据暂缺模块"] = [MODULE_TITLES.get(name, name) for name in item]
            continue
        if key == "degrade_mode":
            result["报告范围"] = {
                "full": "完整报告",
                "degraded": "证据受限报告",
                "simplified": "简化报告",
            }.get(str(item), str(item))
            continue
        if key in INTERNAL_FIELD_TITLES:
            result[INTERNAL_FIELD_TITLES[key]] = _research_value(item)
            continue
        if key.startswith("_"):
            continue
        label = FIELD_TITLES.get(key, key)
        result[label] = _research_value(item)
    return result


def _research_context(evidence: dict[str, Any]) -> dict[str, Any]:
    modules = evidence.get("modules") or {}
    context = {
        "研报证据": {
            MODULE_TITLES.get(name, name): _research_value(payload)
            for name, payload in modules.items()
        },
        "报告信息": _research_value(evidence.get("_meta") or {}),
    }
    return context


def _safe_news_url(value: Any) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _news_markdown_label(core: Any, item: dict[str, Any]) -> str:
    title = core._clean_news_title(str(item.get("title") or "")) or "相关资讯"
    safe_title = title.replace("[", r"\[").replace("]", r"\]")
    url = _safe_news_url(item.get("url")) or _safe_news_url(item.get("link"))
    return f"[{safe_title}]({url})" if url else safe_title


def generate_llm_daily_report(
    evidence: dict[str, Any],
    llm_client: Any,
    history: list[dict[str, str]] | None = None,
    methodology: str | None = None,
    lens: str = "balanced",
    debate_rounds: int = 3,
    daily: bool = True,
) -> tuple[str, dict[str, Any]]:
    base_messages = [{"role": "system", "content": LLM_REPORT_SYSTEM_PROMPT}]
    base_messages.append({"role": "system", "content": LLM_REPORT_STRUCTURE_PROMPT})
    lens_prompt = (
        DebateEngine("all", rounds=debate_rounds, daily=daily).prompt()
        if lens == "all"
        else build_institutional_prompt(lens, rounds=debate_rounds, daily=daily)
    )
    if lens not in {"all", "balanced"}:
        lens_prompt += "\n" + build_lens_prompt(lens)
    base_messages.append({"role": "system", "content": lens_prompt})
    messages = list(base_messages)
    if methodology:
        research_methodology = to_research_methodology(methodology)
        messages.append(
            {
                "role": "system",
                "content": "以下是 young 当前内置研究规范，仅用于报告结构和表达纪律：\n"
                + research_methodology,
            }
        )
    messages.extend((history or [])[-10:])
    report_context = to_research_evidence(evidence)
    messages.append(
        {
            "role": "user",
            "content": "请生成证据驱动的深度行情复盘。\n\n研报证据：\n"
            + json.dumps(report_context, ensure_ascii=False, indent=2),
        }
    )
    response = llm_client.chat(messages)
    metadata = {
        "prompt_version": LLM_REPORT_PROMPT_VERSION,
        "provider": response.provider,
        "model": response.model,
        "usage": response.usage,
        "quality_score": evidence.get("_meta", {}).get("quality_score"),
        "missing_modules": evidence.get("_meta", {}).get("missing_modules", []),
        "lens": lens,
        "debate_rounds": debate_rounds if lens == "all" else 0,
    }
    markdown = review_research_report(response.content, evidence)
    checks = review_investment_output(markdown, evidence)
    enforce_checks = checks.pop("structured_candidate")
    if enforce_checks and not all(checks.values()):
        repair_messages = [
            *base_messages,
            {"role": "system", "content": REPAIR_PROMPT},
            messages[-1],
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": f"请修复以下失败检查后重新输出完整 Markdown：{json.dumps(checks, ensure_ascii=False)}"},
        ]
        repair_response = llm_client.chat(repair_messages)
        markdown = review_research_report(repair_response.content, evidence)
        checks = review_investment_output(markdown, evidence)
        checks.pop("structured_candidate")
        if not all(checks.values()):
            raise LLMError(f"LLM 输出未通过机械校验: {json.dumps(checks, ensure_ascii=False)}")
    metadata["mechanical_checks"] = checks
    return markdown, metadata


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
                    print(f"  相关新闻: {_news_markdown_label(core, items[0])}")
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
    order: str | None = None,
) -> None:
    if report_format == "summary":
        print_daily_summary(core, date_str, watchlist, include_news=include_news)
        return
    if report_format == "key-points":
        print_daily_key_points(core, date_str, watchlist, include_news=include_news)
        return

    core.DIAGNOSTICS.clear()
    display_date = core._display_date(date_str)
    print(f"# 每日行情日报（{display_date}）\n")
    core.print_stage_line(date_str)
    print("数据来源: young-stock-cli 核心模块，多源免登录行情与新闻聚合。")
    print("说明: 以下内容仅供复盘参考，不构成投资建议。\n")
    print("=" * 60 + "\n")

    sections = _section_order(order)
    if "watchlist" in sections:
        print_daily_watchlist(core, watchlist, date_str, include_news=include_news)

    if "markets" in sections:
        print_relevant_markets(core, watchlist, date_str, include_news=include_news)

    print("## 三、投资建议\n")
    for note in _portfolio_advice(core, watchlist, date_str, include_news=include_news):
        print(f"- {note}")
    print()

    if core.DIAGNOSTICS:
        core.print_diagnostic_summary()
    core.print_report_footer()


def print_relevant_markets(core: Any, watchlist: dict[str, list[str]] | None, date_str: str, include_news: bool = True) -> None:
    markets = _relevant_markets(core, watchlist, date_str)
    if not markets:
        return
    print("## 二、相关市场概览\n")
    print("说明: 仅展示与用户持仓股票或基金 top10 持仓相关的市场，不再默认展开全球市场。\n")
    if "cn_market" in markets:
        print("### A股相关市场\n")
        core.run_a_share(date_str, include_news=include_news)
    if "hk_market" in markets:
        print("### 港股相关市场\n")
        core.run_hk_market(date_str, include_news=include_news)
    if "us_market" in markets:
        print("### 美股相关市场\n")
        core.run_us_market(date_str, include_news=include_news)


def _relevant_markets(core: Any, watchlist: dict[str, list[str]] | None, date_str: str) -> set[str]:
    markets: set[str] = set()
    for symbol in _daily_watchlist_items(watchlist, "stocks"):
        try:
            _, market = core.normalize_stock_symbol(symbol)
        except ValueError:
            continue
        if market in {"cn_market", "hk_market", "us_market"}:
            markets.add(market)
    for code in _daily_watchlist_items(watchlist, "funds"):
        try:
            holdings = core.fetch_fund_holdings(code, date_str, limit=10)
        except Exception:
            holdings = {}
        for item in holdings.get("holdings", []) if isinstance(holdings, dict) else []:
            raw_code = str(item.get("code") or "")
            try:
                _, market = core.normalize_stock_symbol(raw_code)
            except ValueError:
                continue
            if market in {"cn_market", "hk_market", "us_market"}:
                markets.add(market)
    return markets


def print_daily_summary(
    core: Any,
    date_str: str,
    watchlist: dict[str, list[str]] | None,
    include_news: bool = True,
) -> None:
    display_date = core._display_date(date_str)
    print(f"{display_date} 行情摘要")
    print("-" * 28)
    print("你的基金: " + _fund_summary(core, watchlist, date_str))
    print("关注个股: " + _stock_summary(core, watchlist, date_str))
    print("A股: " + _a_index_summary(core, date_str))
    print("热点/资金: " + _flow_summary(core, date_str))
    if include_news:
        print("新闻: 摘要模式不展开长新闻；需要详情可用 --format full")
    print("持仓建议: " + _portfolio_summary(core, watchlist, date_str, include_news=include_news))


def print_daily_key_points(
    core: Any,
    date_str: str,
    watchlist: dict[str, list[str]] | None,
    include_news: bool = True,
) -> None:
    print_daily_summary(core, date_str, watchlist, include_news=include_news)
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
        name = str(fund.get("name") or code)
        stance, reason = _fund_manager_stance(pct, pnl)
        asof = str(fund.get("holding_asof") or fund.get("asof") or "")
        if compact:
            notes.append(f"{name}({code}) {core.fmt_pct(pct)}，{pnl_text}，建议“{stance}”。")
        else:
            base = f"{name}({code}) 今日估值 {core.fmt_pct(pct)}，{pnl_text}，建议“{stance}”。{reason}"
            if position.get("buy_date"):
                base += f"买入日 {position.get('buy_date')}，买入净值采用 {buy_nav.get('date', '待获取')} 附近可用净值。"
            if asof:
                base += f"重仓股披露截止 {asof}，若距今较久，需把实时估值作为调仓后的补充信号。"
            base += "跟踪重点：基金风格是否仍匹配买入逻辑、top10 持仓是否与自选股重复暴露、回撤是否超过自己的承受阈值。"
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
        pnl = _position_return(qd.price, buy_price.get("close"), position.get("quantity"))
        stance, action_reason = _manager_stance(qd.change_pct, news_score, pnl)
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


def _fund_manager_stance(change_pct: float | None, pnl: dict[str, float] | None) -> tuple[str, str]:
    pct = change_pct or 0
    pnl_pct = pnl["pct"] if pnl else None
    if pnl_pct is not None and pnl_pct >= 15:
        if pct >= 1:
            return "继续持有但分批锁定收益", "买入以来收益较厚且当日估值仍偏强，适合把止盈线从成本转向回撤阈值。"
        return "持有并保护收益", "买入以来收益较厚但短线动能一般，重点看净值回撤和重仓方向是否转弱。"
    if pnl_pct is not None and pnl_pct <= -10:
        if pct <= -1:
            return "降低加仓冲动", "买入以来回撤较大且当日估值偏弱，先确认基金风格是否失效。"
        return "修复观察", "买入以来仍亏损但当日估值修复，可继续观察连续性，暂不因单日反弹追高。"
    if pct <= -2:
        return "谨慎观察", "当日估值明显走弱，优先检查重仓行业是否出现系统性负面信号。"
    if pct >= 2:
        return "持有观察", "当日估值较强，可跟踪上涨是否来自核心持仓贡献而非短线情绪。"
    return "中性持有", "收益和日内估值都未给出强动作信号，适合按原定配置纪律跟踪。"


def _manager_stance(change_pct: float | None, news_score: int, pnl: dict[str, float] | None = None) -> tuple[str, str]:
    pct = change_pct or 0
    pnl_pct = pnl["pct"] if pnl else None
    if pnl_pct is not None and pnl_pct >= 20 and news_score < 0:
        return "保护收益", "买入以来收益较厚但新闻边际转弱，先上移止盈/回撤线，避免好仓位回吐成普通波动。"
    if pnl_pct is not None and pnl_pct >= 20 and pct >= 2:
        return "持有但不追高", "买入以来已有较大安全垫，当日继续走强时更适合让利润奔跑而不是追加风险。"
    if pnl_pct is not None and pnl_pct <= -12 and news_score < 0:
        return "降低仓位观察", "买入以来亏损叠加负面新闻，需重新验证买入逻辑，避免用补仓掩盖判断错误。"
    if pnl_pct is not None and pnl_pct <= -12 and news_score >= 0:
        return "修复观察", "买入以来仍处亏损，但消息面未明显恶化，可等待价格重新站稳后再决定是否补仓。"
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
        return ["watchlist", "markets"]
    mapping = {
        "基金": "watchlist",
        "个股": "watchlist",
        "关注": "watchlist",
        "A股": "markets",
        "a": "markets",
        "港股": "markets",
        "美股": "markets",
        "markets": "markets",
        "相关市场": "markets",
        "global": "markets",
    }
    return [mapping.get(part.strip(), part.strip()) for part in order.split(",") if part.strip()]
