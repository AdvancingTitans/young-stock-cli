"""Rich interactive chat with Click-backed slash commands."""

from __future__ import annotations

import builtins
import re
import shlex
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from statistics import median
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from click.testing import CliRunner
from rich.console import Console
from rich.markdown import Markdown

try:  # pragma: no cover - optional dependency may be absent in some envs.
    from prompt_toolkit import prompt as _prompt_toolkit_prompt
except Exception:  # pragma: no cover - dependency missing or broken
    _prompt_toolkit_prompt = None

try:  # pragma: no cover - import path differs across Python builds
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback safety
    ZoneInfo = None  # type: ignore[assignment]

from .config import load_config, save_config
from .lens.registry import chat_style_profiles
from .llm import LLMClient, LLMError
from .local_store import load_store, now_label, save_store
from .research_bridge import compact_research_output, run_research_bridge

CHAT_MEMORY_STORE = "chat_memory"
DEFAULT_CHAT_STYLE = "balanced"
CHAT_MEMORY_LABELS = {
    "investment": "投资记忆",
    "persona": "人格/角色设定",
    "preferences": "其他长期偏好",
}
CHAT_STYLE_PROMPTS = {
    "balanced": {
        "label": "balanced",
        "summary": "先事实、再判断，平衡基本面、估值、风险、催化剂与反例。",
        "prompt": (
            "当前对话风格与分析框架：balanced。使用冷静、克制、专业的第一人称口吻，避免刻意模仿名人腔调；"
            "如需自我介绍，可直接说“我是 Young”；"
            "先区分已验证事实、推断、未知项；"
            "同时看业务/资产质量、估值、风险、催化剂与反例；给概率化结论和后续核验点。"
        ),
    },
    **chat_style_profiles(),
}
READ_ONLY_SLASH_HELP = (
    "可用命令：/a、/stock <symbol> [--llm] [--lens ...]、/fund <code>、/news <query>、/daily [--llm] [--lens ...]、/report（仅导出 PDF）、/send、"
    "/profile list、/memory show、/memory clear、/style、/style list、/style set <name>、"
    "/style show、/style clear、/diagnose、/help、/clear、/exit。"
)
SUPPORTED_SLASH_FOR_PROMPT = (
    "/a, /stock <symbol> [--llm] [--lens ...], /fund <code>, /news <query>, /daily [--llm] [--lens ...], /report (PDF export only), /send, "
    "/profile list, /memory show, /memory clear, /style, /style list, /style set <name>, "
    "/style show, /style clear, /diagnose, /help, /clear, /exit"
)
_EXPLICIT_MEMORY_HINTS = ("记住", "记一下", "别忘了", "以后", "下次", "长期", "默认")
_INVESTMENT_HINTS = (
    "持有",
    "仓位",
    "买入",
    "定投",
    "成本",
    "止盈",
    "止损",
    "股票",
    "基金",
    "etf",
    "a股",
    "港股",
    "美股",
    "关注",
)
_PERSONA_HINTS = ("扮演", "角色", "你是", "请叫我", "叫我", "助手", "教练", "顾问", "分析师")
_PREFERENCE_HINTS = (
    "偏好",
    "喜欢",
    "希望",
    "尽量",
    "默认",
    "请用",
    "回答",
    "回复",
    "简洁",
    "中文",
    "不要",
    "别",
    "避免",
    "先给",
)
_STYLE_MEMORY_HINTS = (
    *CHAT_STYLE_PROMPTS,
    "巴菲特",
    "芒格",
    "查理",
    "格雷厄姆",
    "达利欧",
)
_BEIJING_TZ = ZoneInfo("Asia/Shanghai") if ZoneInfo else timezone(timedelta(hours=8))
_TIME_QUERY_HINTS = (
    "现在几点",
    "现在几号",
    "今天几号",
    "今天几月几号",
    "当前时间",
    "当前日期",
    "北京时间",
    "日期",
    "时间",
    "星期几",
)
_SEARCH_INTENT_HINTS = (
    "搜索",
    "搜一下",
    "搜搜",
    "查一下",
    "查查",
    "查一查",
    "帮我查",
    "帮我搜",
    "lookup",
    "search",
)
_SEARCH_TOPIC_HINTS = (
    "新闻",
    "资讯",
    "公告",
    "财报",
    "盈利",
    "业绩",
    "研报",
    "公司情况",
    "公司信息",
    "最新",
)
_RESEARCH_SUMMARY_HINTS = (
    "营收",
    "收入",
    "利润",
    "净利润",
    "毛利率",
    "指引",
    "现金流",
    "财报",
    "季度",
    "年度",
    "估值",
)
_NETWORK_TIME_URLS = (
    "https://www.baidu.com",
    "https://www.qq.com",
    "https://www.gov.cn",
)
_TIME_VERIFICATION_CACHE: dict[str, object] = {
    "verified_at": None,
    "network_now": None,
    "local_now": None,
}
_TIME_VERIFICATION_TTL = timedelta(minutes=5)


def beijing_now() -> datetime:
    return current_time_snapshot()["current"]


def _local_beijing_now() -> datetime:
    return datetime.now(_BEIJING_TZ)


def _http_date_now(url: str, timeout: float = 2.0) -> datetime | None:
    try:
        request = Request(url, method="HEAD", headers={"User-Agent": "young-stock-cli/0.2"})
        with urlopen(request, timeout=timeout) as response:
            date_header = response.headers.get("Date")
    except (URLError, TimeoutError, ValueError):
        return None
    if not date_header:
        return None
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_BEIJING_TZ)


def _median_network_time() -> datetime | None:
    samples = [sample for sample in (_http_date_now(url) for url in _NETWORK_TIME_URLS) if sample is not None]
    if not samples:
        return None
    if len(samples) == 1:
        return samples[0]
    timestamps = [sample.timestamp() for sample in samples]
    return datetime.fromtimestamp(median(timestamps), tz=_BEIJING_TZ)


def current_time_snapshot() -> dict[str, object]:
    local_now = _local_beijing_now()
    verified_at = _TIME_VERIFICATION_CACHE.get("verified_at")
    if isinstance(verified_at, datetime) and local_now - verified_at <= _TIME_VERIFICATION_TTL:
        network_now = _TIME_VERIFICATION_CACHE.get("network_now")
        cached_local = _TIME_VERIFICATION_CACHE.get("local_now")
        if isinstance(network_now, datetime) and isinstance(cached_local, datetime):
            adjusted = network_now + (local_now - cached_local)
            diff_seconds = int(abs((adjusted - local_now).total_seconds()))
            return {
                "current": adjusted,
                "source": "network+local",
                "local": local_now,
                "network": adjusted,
                "diff_seconds": diff_seconds,
            }
    network_now = _median_network_time()
    _TIME_VERIFICATION_CACHE["verified_at"] = local_now
    _TIME_VERIFICATION_CACHE["local_now"] = local_now
    _TIME_VERIFICATION_CACHE["network_now"] = network_now
    if network_now is None:
        return {
            "current": local_now,
            "source": "local-only",
            "local": local_now,
            "network": None,
            "diff_seconds": None,
        }
    diff_seconds = int(abs((network_now - local_now).total_seconds()))
    return {
        "current": network_now,
        "source": "network+local",
        "local": local_now,
        "network": network_now,
        "diff_seconds": diff_seconds,
    }


def _weekday_label(dt: datetime) -> str:
    return "一二三四五六日"[dt.weekday()]


def _current_time_system_note() -> str:
    snapshot = current_time_snapshot()
    now = snapshot["current"]
    assert isinstance(now, datetime)
    source = "已用联网时钟与本地时钟交叉校验" if snapshot["source"] == "network+local" else "当前仅使用本地时钟"
    diff_seconds = snapshot.get("diff_seconds")
    verification = f"{source}。" if diff_seconds in (None, 0) else f"{source} 两者偏差约 {diff_seconds} 秒。"
    return (
        f"当前系统时间（北京时间，UTC+8）是 {now:%Y-%m-%d %H:%M:%S}，星期{_weekday_label(now)}。"
        f"{verification}"
        "涉及“今天”“当前”“最近”“最新”这类相对时间时，必须以这个北京时间为准，不要自行猜测日期。"
    )


def _read_chat_input(prompt_text: str = "young ") -> str:
    if callable(_prompt_toolkit_prompt):
        try:
            return _prompt_toolkit_prompt(prompt_text)
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            pass
    return builtins.input(prompt_text)


def _is_time_query(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return False
    if any(hint in stripped for hint in _INVESTMENT_HINTS):
        return False
    return any(hint in stripped.lower() for hint in _TIME_QUERY_HINTS)


def _format_time_answer(text: str) -> str:
    snapshot = current_time_snapshot()
    now = snapshot["current"]
    assert isinstance(now, datetime)
    compact = re.sub(r"\s+", "", text)
    date_label = f"{now.year} 年 {now.month} 月 {now.day} 日"
    wants_weekday = "星期" in compact or "周几" in compact
    wants_time = any(token in compact for token in ("几点", "时间", "几点了", "现在"))
    wants_date = any(token in compact for token in ("几号", "日期", "几月几号", "哪天", "今天"))
    if wants_date and not wants_time:
        base = f"当前北京时间日期是 {date_label}"
    elif wants_time and not wants_date:
        base = f"当前北京时间是 {date_label} {now:%H:%M:%S}"
    else:
        base = f"当前北京时间是 {date_label} {now:%H:%M:%S}"
    if wants_weekday or wants_date:
        base += f"，星期{_weekday_label(now)}"
    if snapshot["source"] == "network+local":
        diff_seconds = snapshot.get("diff_seconds")
        suffix = "（已用联网时钟与本地时钟交叉校验）"
        if isinstance(diff_seconds, int) and diff_seconds > 0:
            suffix = f"（已用联网时钟与本地时钟交叉校验，偏差约 {diff_seconds} 秒）"
        return base + suffix + "。"
    return base + "（当前仅使用本地时钟）。"


def _should_auto_research(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("/"):
        return False
    lowered = stripped.lower()
    explicit_search = any(hint in lowered for hint in _SEARCH_INTENT_HINTS)
    topical_latest = any(hint in stripped for hint in _SEARCH_TOPIC_HINTS) and any(
        token in stripped for token in ("最新", "今天", "近期", "公司", "新闻", "公告", "盈利", "财报", "业绩")
    )
    return explicit_search or topical_latest


def _empty_long_term_memory() -> dict[str, list[dict[str, str]]]:
    return {kind: [] for kind in CHAT_MEMORY_LABELS}


def load_long_term_memory() -> dict[str, list[dict[str, str]]]:
    raw = load_store(CHAT_MEMORY_STORE, {})
    data = _empty_long_term_memory()
    for kind in CHAT_MEMORY_LABELS:
        items = raw.get(kind, []) if isinstance(raw, dict) else []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            content = _clean_memory_text(str(item.get("content", "")))
            if not content:
                continue
            data[kind].append(
                {
                    "content": content,
                    "updated_at": str(item.get("updated_at") or ""),
                }
            )
    return data


def save_long_term_memory(data: dict[str, list[dict[str, str]]]) -> None:
    save_store(CHAT_MEMORY_STORE, data)


def clear_long_term_memory_store(kind: str | None = None) -> dict[str, list[dict[str, str]]]:
    data = load_long_term_memory()
    if kind and kind in CHAT_MEMORY_LABELS:
        data[kind] = []
    else:
        data = _empty_long_term_memory()
    save_long_term_memory(data)
    return data


def format_long_term_memory_for_cli(data: dict[str, list[dict[str, str]]]) -> str:
    lines = []
    for kind, label in CHAT_MEMORY_LABELS.items():
        notes = [item["content"] for item in data.get(kind, []) if item.get("content")]
        lines.append(f"{label}: {'; '.join(notes) if notes else '-'}")
    return "\n".join(lines)


def _format_long_term_memory_for_prompt(data: dict[str, list[dict[str, str]]]) -> str:
    lines = []
    for kind, label in CHAT_MEMORY_LABELS.items():
        notes = [item["content"] for item in data.get(kind, []) if item.get("content")]
        if notes:
            lines.append(f"- {label}: {'；'.join(notes[-4:])}")
    if not lines:
        return ""
    return "\n".join(
        [
            "长期用户记忆（仅在相关时使用；这是提炼后的长期信息，不是完整聊天原文）：",
            *lines,
        ]
    )


def _clean_memory_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ，,。；;：:")


def _normalize_memory_key(text: str) -> str:
    return re.sub(r"\s+", "", _clean_memory_text(text)).lower()


def _strip_memory_prefix(text: str) -> str:
    cleaned = _clean_memory_text(text)
    cleaned = re.sub(r"^(请)?(帮我)?(记住|记一下|别忘了)[：:\s]*", "", cleaned)
    if cleaned.startswith("以后请"):
        return _clean_memory_text("请" + cleaned[3:])
    if cleaned.startswith("以后"):
        return _clean_memory_text(cleaned[2:])
    return cleaned


def _classify_memory(text: str, cleaned: str) -> str | None:
    lowered = text.lower()
    explicit = any(hint in text for hint in _EXPLICIT_MEMORY_HINTS)
    if any(hint in text for hint in _PERSONA_HINTS):
        return "persona"
    if any(hint in text for hint in _PREFERENCE_HINTS):
        return "preferences"
    if any(hint in lowered for hint in _INVESTMENT_HINTS) or re.search(r"\b[A-Z]{1,5}\b|\b\d{6}\b", text):
        return "investment"
    if explicit and cleaned:
        return "preferences"
    return None


def _extract_long_term_memories(text: str) -> list[tuple[str, str]]:
    notes: list[tuple[str, str]] = []
    for chunk in re.split(r"[。！？；\n]+", text):
        original = chunk.strip()
        if not original:
            continue
        cleaned = _strip_memory_prefix(original)
        if not cleaned:
            continue
        kind = _classify_memory(original, cleaned)
        if kind:
            notes.append((kind, cleaned))
    return notes


def _upsert_long_term_memory(
    data: dict[str, list[dict[str, str]]],
    kind: str,
    content: str,
) -> bool:
    items = data.setdefault(kind, [])
    key = _normalize_memory_key(content)
    timestamp = now_label()
    for item in items:
        if _normalize_memory_key(item.get("content", "")) == key:
            item["content"] = content
            item["updated_at"] = timestamp
            return False
    items.append({"content": content, "updated_at": timestamp})
    del items[:-12]
    return True


def slash_to_args(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped.startswith("/"):
        raise ValueError("slash command must start with /")
    return shlex.split(stripped[1:])


def _normalize_style_name(name: str | None) -> str:
    key = str(name or "").strip().lower()
    return key if key in CHAT_STYLE_PROMPTS else DEFAULT_CHAT_STYLE


def _load_chat_style_name() -> str:
    chat_config = load_config(strict=False).get("chat", {})
    return _normalize_style_name(chat_config.get("analysis_framework") or chat_config.get("style"))


def _save_chat_style_name(name: str | None) -> str:
    config = load_config(strict=False)
    chat_config = config.setdefault("chat", {})
    if name is None:
        chat_config.pop("style", None)
        chat_config.pop("analysis_framework", None)
        chat_config.pop("analysis_style", None)
    else:
        normalized = _normalize_style_name(name)
        chat_config["style"] = normalized
        chat_config["analysis_framework"] = normalized
        chat_config.pop("analysis_style", None)
    save_config(config)
    return _load_chat_style_name()


def _format_style_options() -> str:
    return "、".join(CHAT_STYLE_PROMPTS)


def _style_summary(name: str) -> str:
    profile = CHAT_STYLE_PROMPTS[_normalize_style_name(name)]
    return f"{profile['label']}: {profile['summary']}"


def _build_style_prompt(name: str) -> str:
    profile = CHAT_STYLE_PROMPTS[_normalize_style_name(name)]
    return (
        f"{profile['prompt']} "
        "这里的风格同时约束自称、口吻和分析框架；不要声称自己真的是历史上的该人物，"
        "把这些名字当作当前对话 persona，直接自然表达，不要写风格说明或元解释；"
        "也不要输出确定性投资建议。"
    )


def _style_memory_note(name: str) -> str:
    normalized = _normalize_style_name(name)
    return (
        f"默认对话风格和分析框架保持同步：{normalized}。"
        "除非我再次使用 /style set 修改，否则始终按这个风格执行。"
    )


def _is_style_related_memory(content: str) -> bool:
    normalized = _normalize_memory_key(content)
    return any(_normalize_memory_key(hint) in normalized for hint in _STYLE_MEMORY_HINTS)


def _sync_style_memory(
    data: dict[str, list[dict[str, str]]],
    name: str | None,
) -> dict[str, list[dict[str, str]]]:
    for kind in ("persona", "preferences"):
        data[kind] = [
            item
            for item in data.get(kind, [])
            if not _is_style_related_memory(item.get("content", ""))
        ]
    if name is not None:
        _upsert_long_term_memory(data, "preferences", _style_memory_note(name))
    return data


@dataclass
class ChatSession:
    max_turns: int = 5
    output: Callable[[str], None] | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    long_term_memory: dict[str, list[dict[str, str]]] = field(default_factory=load_long_term_memory)
    style_name: str = field(default_factory=_load_chat_style_name)

    def __post_init__(self) -> None:
        self.console = Console()
        if self.output is None:
            self.output = self.console.print
        self.long_term_memory = load_long_term_memory()
        self.style_name = _load_chat_style_name()

    def remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content[-8000:]})
        self.history = self.history[-(self.max_turns * 2):]

    def capture_long_term_memory(self, text: str) -> int:
        updates = 0
        for kind, content in _extract_long_term_memories(text):
            updates += int(_upsert_long_term_memory(self.long_term_memory, kind, content))
        if updates:
            save_long_term_memory(self.long_term_memory)
        return updates

    def _build_messages(self, extra_system_messages: list[str] | None = None) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "硬性规则："
                    f"1) 只允许建议这些 slash 命令：{SUPPORTED_SLASH_FOR_PROMPT}；"
                    "不要编造 /market、/trend 或其他命令。"
                    "2) 未提供 Evidence Pack 时，不得编造实时行情、涨跌幅、资金流、新闻细节或结论。"
                    "3) 用户问“今天市场怎么样”“大盘如何”等泛问题时，优先引导 /a 或 /daily。"
                    "4) 用户要做单只股票深入分析、但你缺少足够证据时，不要直接拒绝；"
                    "优先使用已有的 /stock <symbol> 或已注入的外部检索证据继续分析。"
                    "5) 如果本轮已经完成外部检索，就直接总结结果，不要要求用户自己再执行额外检索命令。"
                    "6) /daily --llm 的深度复盘必须严格遵循 young 的 M1-M7 框架；专家视角只约束 M7，不得改写 M1-M6。"
                    "7) 风格与长期记忆都服从本安全规则。"
                ),
            }
        ]
        messages.append({"role": "system", "content": _current_time_system_note()})
        messages.append({"role": "system", "content": _build_style_prompt(self.style_name)})
        for item in extra_system_messages or []:
            if item.strip():
                messages.append({"role": "system", "content": item})
        long_term = _format_long_term_memory_for_prompt(self.long_term_memory)
        if long_term:
            messages.append({"role": "system", "content": long_term})
        messages.extend(self.history)
        return messages

    def _emit(self, message: str) -> None:
        self.output(message)

    def _show_authoritative_help(self, prefix: str | None = None) -> None:
        message = READ_ONLY_SLASH_HELP if prefix is None else f"{prefix}\n{READ_ONLY_SLASH_HELP}"
        self._emit(message)

    def _handle_style_slash(self, args: list[str]) -> bool:
        action = args[1] if len(args) > 1 else "show"
        if action == "list":
            self._emit("可选风格：" + "；".join(_style_summary(name) for name in CHAT_STYLE_PROMPTS))
            return False
        if action == "show":
            self._emit(f"当前风格：{_style_summary(self.style_name)}")
            return False
        if action == "clear":
            self.style_name = _save_chat_style_name(None)
            self.long_term_memory = _sync_style_memory(self.long_term_memory, None)
            save_long_term_memory(self.long_term_memory)
            self._emit(f"已清除自定义风格，当前风格：{self.style_name}（默认）。")
            return False
        if action == "set":
            if len(args) < 3:
                self._emit(f"用法：/style set <name>。可选：{_format_style_options()}")
                return False
            candidate = args[2]
            if candidate.strip().lower() not in CHAT_STYLE_PROMPTS:
                self._emit(f"未知风格：{candidate}。可选：{_format_style_options()}")
                return False
            self.style_name = _save_chat_style_name(candidate)
            self.long_term_memory = _sync_style_memory(self.long_term_memory, self.style_name)
            save_long_term_memory(self.long_term_memory)
            self._emit(f"已同步设置对话风格和分析框架：{_style_summary(self.style_name)}")
            return False
        self._emit("用法：/style、/style list、/style set <name>、/style show、/style clear")
        return False

    def _resolve_click_args(self, args: list[str]) -> tuple[list[str] | None, str | None]:
        root = args[0]
        if root in {"a", "stock", "fund", "news", "daily", "report", "diagnose", "send"}:
            return args, None
        if root == "profile":
            if len(args) >= 2 and args[1] in {"list", "show"}:
                return args, None
            return None, "chat 中仅支持只读的 /profile list。"
        if root == "memory":
            if len(args) >= 2 and args[1] in {"show", "list"}:
                return ["memory", "show"], None
            if len(args) >= 2 and args[1] == "clear":
                return args, None
            return None, "chat 中仅支持 /memory show 和 /memory clear。"
        if root in {"config", "update", "uninstall"}:
            return None, f"chat 中禁止 /{root}，请在终端直接运行对应 CLI。"
        return None, f"不支持 /{root}。请输入 /help 查看 authoritative 命令列表。"

    def handle_slash(self, text: str) -> bool:
        args = slash_to_args(text)
        if not args:
            return False
        if args[0] in {"exit", "quit"}:
            return True
        if args[0] == "clear":
            self.history.clear()
            self._emit("对话上下文已清空。")
            return False
        if args[0] == "help":
            self._show_authoritative_help()
            return False
        if args[0] == "chat":
            self._emit("chat 模式中不能再次启动 /chat。")
            return False
        if args[0] == "style":
            return self._handle_style_slash(args)
        routed_args, notice = self._resolve_click_args(args)
        if routed_args is None:
            self._show_authoritative_help(notice)
            return False
        if notice:
            self._emit(notice)
        self.remember("user", text)
        command_output = self._invoke_click(routed_args)
        if routed_args and routed_args[0] == "memory":
            self.long_term_memory = load_long_term_memory()
        if command_output:
            self.remember("assistant", command_output)
        return False

    def _invoke_click(self, args: list[str], *, echo: bool = True) -> str:
        from .cli import cli

        result = CliRunner().invoke(cli, args, color=False)
        text_output = result.output.rstrip()
        if text_output and echo:
            self.output(text_output)
        if result.exception and not text_output and echo:
            self.output(str(result.exception))
        if result.exception and not text_output:
            return str(result.exception)
        return text_output

    def _hidden_research(self, query: str, limit: int = 5) -> str:
        del limit
        normalized = query.strip()
        if not normalized:
            return ""
        result = run_research_bridge(normalized)
        return result.get("summary_material") or result.get("_unavailable") or ""

    def _maybe_collect_research_context(self, text: str) -> str | None:
        if not _should_auto_research(text):
            return None
        research_output = self._hidden_research(text).strip()
        if not research_output:
            return None
        if "未配置可选联网研究桥" in research_output or "执行失败" in research_output:
            return None
        summary_material = compact_research_output(research_output)
        if not summary_material:
            return None
        return (
            "本轮已自动完成外部研究补充。下面是供你提炼的公开资料摘录，不要展示原始执行过程，也不要要求用户执行额外命令。"
            "你需要直接输出最终总结，并给出基于这些摘录的分析；若证据不足请明确说明。\n"
            f"{summary_material}"
        )

    def handle_message(self, text: str) -> None:
        self.capture_long_term_memory(text)
        self.remember("user", text)
        if _is_time_query(text):
            answer = _format_time_answer(text)
            self.remember("assistant", answer)
            self.output(answer)
            return
        config = load_config(strict=False).get("llm", {})
        extra_system_messages = []
        research_context = self._maybe_collect_research_context(text)
        if research_context:
            extra_system_messages.append(research_context)
        try:
            response = LLMClient(config).chat(self._build_messages(extra_system_messages))
        except LLMError as exc:
            self.output(str(exc))
            return
        self.remember("assistant", response.content)
        if self.output == self.console.print:
            self.console.print(Markdown(response.content))
        else:
            self.output(response.content)


def run_chat() -> None:
    console = Console()
    session = ChatSession()
    console.print(
        "[bold #1B365D]young chat[/] — 输入 /help 查看命令，/exit 退出。"
        f"\n可选风格：{_format_style_options()}。"
    )
    console.print(f"当前风格：{session.style_name}。")
    console.print("可用 `/style set <name>` 同步设置对话风格、自称口吻和分析框架，例如 `/style set buffett`。")
    while True:
        try:
            text = _read_chat_input().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见。")
            return
        if not text:
            continue
        if text.startswith("/"):
            if session.handle_slash(text):
                return
        else:
            session.handle_message(text)
