"""Read-only MCP stdio server for standardized young Evidence."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any

from . import __version__, _core
from .evidence import build_daily_evidence, build_fund_evidence, build_stock_evidence
from .health import SOURCE_HEALTH, SourceHealthBook
from .profile import load_profile
from .sources import SourcePolicy, resolve_quote
from .sources.registry import DATA_SOURCES

TOOL_NAMES = (
    "get_quote",
    "get_market_indices",
    "get_market_emotion",
    "get_daily_evidence",
    "get_stock_evidence",
    "get_fund_evidence",
    "get_stock_news",
    "get_announcements",
    "get_research_reports",
    "get_fund_flow",
    "get_source_health",
)

_DATE_RE = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")
_SOURCE_KEYS = {"source", "_source"}
_DATE_KEYS = {"as_of", "data_date", "date", "latest_date", "nav_date", "trade_date", "_source_date"}


class MCPToolError(ValueError):
    pass


def _schema(
    properties: dict[str, Any] | None = None,
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def _date_property() -> dict[str, Any]:
    return {"type": "string", "description": "Trade date, YYYYMMDD or YYYY-MM-DD."}


def _symbol_property() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def list_tools() -> list[dict[str, Any]]:
    symbol_date = {"symbol": _symbol_property(), "date": _date_property()}
    return [
        {
            "name": "get_quote",
            "description": "Read a standardized quote through young SourceResolver.",
            "inputSchema": _schema(symbol_date, required=["symbol"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_market_indices",
            "description": "Read market index evidence from young daily Evidence.",
            "inputSchema": _schema({"date": _date_property()}),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_market_emotion",
            "description": "Read short-term market emotion evidence from young daily Evidence.",
            "inputSchema": _schema({"date": _date_property()}),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_daily_evidence",
            "description": "Read the full young daily Evidence bundle.",
            "inputSchema": _schema({"date": _date_property(), "profile": {"type": "object"}}),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_stock_evidence",
            "description": "Read the full young stock Evidence bundle.",
            "inputSchema": _schema(symbol_date, required=["symbol"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_fund_evidence",
            "description": "Read the full young fund Evidence bundle.",
            "inputSchema": _schema({"code": _symbol_property(), "date": _date_property()}, required=["code"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_stock_news",
            "description": "Read the stock news slice from young stock Evidence.",
            "inputSchema": _schema(symbol_date, required=["symbol"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_announcements",
            "description": "Read the announcements slice from young stock Evidence when available.",
            "inputSchema": _schema(symbol_date, required=["symbol"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_research_reports",
            "description": "Read the research-report slice from young stock Evidence when available.",
            "inputSchema": _schema(symbol_date, required=["symbol"]),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_fund_flow",
            "description": "Read market fund-flow evidence from young daily Evidence.",
            "inputSchema": _schema({"date": _date_property()}),
            "annotations": {"readOnlyHint": True},
        },
        {
            "name": "get_source_health",
            "description": "Read young source-health snapshots.",
            "inputSchema": _schema(
                {"date": _date_property(), "sources": {"type": "array", "items": {"type": "string"}}}
            ),
            "annotations": {"readOnlyHint": True},
        },
    ]


def _normalize_date(value: Any, core: Any) -> str:
    if value in (None, ""):
        if hasattr(core, "nearest_trade_date"):
            return str(core.nearest_trade_date()).replace("-", "")
        return datetime.now().strftime("%Y%m%d")
    text = str(value).strip()
    if not _DATE_RE.fullmatch(text):
        raise MCPToolError("date must be YYYYMMDD or YYYY-MM-DD")
    return text.replace("-", "")


def _required_text(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise MCPToolError(f"{key} is required")
    return value


def _compact_date(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("-", "") if _DATE_RE.fullmatch(text) else text


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _sources(value: Any) -> str:
    found: list[str] = []
    for item in _walk(value):
        for key in _SOURCE_KEYS:
            source = item.get(key)
            if isinstance(source, str) and source and source not in found:
                found.append(source)
    return ",".join(found[:8]) or "young"


def _dates(value: Any) -> list[str]:
    result: list[str] = []
    for item in _walk(value):
        for key in _DATE_KEYS:
            date = _compact_date(item.get(key))
            if date and date not in result:
                result.append(date)
    return result


def _has_stale_marker(value: Any) -> bool:
    return any(
        item.get("stale") is True
        or item.get("_stale") is True
        or item.get("_date_note") == "latest_available"
        or item.get("_cache_note") == "last_known_good"
        for item in _walk(value)
    )


def _wrap(
    *,
    requested_date: str,
    evidence: dict[str, Any],
    source: str | None = None,
    as_of: str | None = None,
    missing: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    actual = _compact_date(as_of) or (next(iter(_dates(evidence)), "") or requested_date)
    stale = _has_stale_marker(evidence) or bool(actual and requested_date and actual != requested_date)
    return {
        "requested_date": requested_date,
        "as_of": actual,
        "source": source or _sources(evidence),
        "stale": stale,
        "missing": missing or [],
        "warnings": warnings or [],
        "evidence": evidence,
    }


def _bundle_response(requested_date: str, bundle: Any, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = bundle.to_dict()
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    missing = list(meta.get("missing_modules") or [])
    return _wrap(
        requested_date=requested_date,
        evidence=evidence or payload,
        missing=missing,
        warnings=[] if not missing else [f"missing evidence: {', '.join(missing)}"],
    )


class YoungMCPTools:
    def __init__(self, *, core: Any | None = None, health: SourceHealthBook | None = None) -> None:
        self.core = core or _core
        self.health = health or SOURCE_HEALTH

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise MCPToolError(f"unknown tool: {name}")
        args = arguments or {}
        handlers = {
            "get_quote": self.get_quote,
            "get_market_indices": self.get_market_indices,
            "get_market_emotion": self.get_market_emotion,
            "get_daily_evidence": self.get_daily_evidence,
            "get_stock_evidence": self.get_stock_evidence,
            "get_fund_evidence": self.get_fund_evidence,
            "get_stock_news": self.get_stock_news,
            "get_announcements": self.get_announcements,
            "get_research_reports": self.get_research_reports,
            "get_fund_flow": self.get_fund_flow,
            "get_source_health": self.get_source_health,
        }
        return handlers[name](args)

    def get_quote(self, args: dict[str, Any]) -> dict[str, Any]:
        symbol = _required_text(args, "symbol")
        date = _normalize_date(args.get("date"), self.core)
        result = resolve_quote(
            self.core,
            symbol,
            date,
            policy=SourcePolicy(),
            health=self.health,
        )
        quote = result.data if result.ok and isinstance(result.data, dict) else None
        return _wrap(
            requested_date=date,
            evidence={"quote": quote, "attempts": list(result.attempts)},
            source=result.source or "young_quote_resolver",
            as_of=result.as_of or (quote or {}).get("date"),
            missing=[] if quote else ["quote"],
            warnings=[] if quote else [result.error or "quote unavailable", *result.attempts],
        )

    def get_market_indices(self, args: dict[str, Any]) -> dict[str, Any]:
        date = _normalize_date(args.get("date"), self.core)
        bundle = build_daily_evidence(self.core, date, {}, include_news_radar=False, health=self.health)
        return _bundle_response(date, bundle, {"M1": bundle.modules.get("M1", {})})

    def get_market_emotion(self, args: dict[str, Any]) -> dict[str, Any]:
        date = _normalize_date(args.get("date"), self.core)
        bundle = build_daily_evidence(self.core, date, {}, include_news_radar=False, health=self.health)
        return _bundle_response(
            date,
            bundle,
            {
                "M3": bundle.modules.get("M3", {}),
                "M4": bundle.modules.get("M4", {}),
                "emotion_summary": bundle.meta.get("m7_emotion_summary"),
            },
        )

    def get_daily_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        date = _normalize_date(args.get("date"), self.core)
        profile = args.get("profile") if isinstance(args.get("profile"), dict) else load_profile()
        return _bundle_response(
            date,
            build_daily_evidence(self.core, date, profile, include_news_radar=True, health=self.health),
        )

    def get_stock_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        symbol = _required_text(args, "symbol")
        date = _normalize_date(args.get("date"), self.core)
        return _bundle_response(date, build_stock_evidence(self.core, symbol, date, health=self.health))

    def get_fund_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        code = _required_text(args, "code")
        date = _normalize_date(args.get("date"), self.core)
        return _bundle_response(date, build_fund_evidence(self.core, code, date, health=self.health))

    def _stock_slice(self, args: dict[str, Any], key: str) -> dict[str, Any]:
        symbol = _required_text(args, "symbol")
        date = _normalize_date(args.get("date"), self.core)
        bundle = build_stock_evidence(self.core, symbol, date, health=self.health)
        stock = bundle.modules.get("STOCK", {})
        if key in {"announcements", "research_reports"}:
            evidence = {key: (stock.get("a_share_extensions") or {}).get(key)}
        else:
            evidence = {key: stock.get(key)}
        missing = [] if evidence.get(key) else [key]
        response = _bundle_response(date, bundle, evidence)
        response["missing"] = missing
        response["warnings"] = [] if not missing else [f"{key} unavailable"]
        return response

    def get_stock_news(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._stock_slice(args, "news")

    def get_announcements(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._stock_slice(args, "announcements")

    def get_research_reports(self, args: dict[str, Any]) -> dict[str, Any]:
        return self._stock_slice(args, "research_reports")

    def get_fund_flow(self, args: dict[str, Any]) -> dict[str, Any]:
        date = _normalize_date(args.get("date"), self.core)
        bundle = build_daily_evidence(self.core, date, {}, include_news_radar=False, health=self.health)
        flow = bundle.modules.get("M2", {}).get("fund_flow")
        return _wrap(
            requested_date=date,
            evidence={"fund_flow": flow},
            missing=[] if flow and not flow.get("_unavailable") and not flow.get("_error") else ["fund_flow"],
            warnings=[] if flow and not flow.get("_unavailable") and not flow.get("_error") else ["fund_flow unavailable"],
        )

    def get_source_health(self, args: dict[str, Any]) -> dict[str, Any]:
        sources = args.get("sources")
        names = [str(item) for item in sources] if isinstance(sources, list) else sorted({source.health_key for source in DATA_SOURCES})
        evidence = {"health": {name: asdict(self.health.snapshot(name)) for name in names}}
        return _wrap(
            requested_date=_normalize_date(args.get("date"), self.core),
            evidence=evidence,
            source="young_source_health",
        )


def _read_framed_messages(raw: bytes) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    pos = 0
    while pos < len(raw):
        header_end = raw.find(b"\r\n\r\n", pos)
        if header_end < 0:
            break
        headers = raw[pos:header_end].decode("ascii", errors="replace").split("\r\n")
        length = 0
        for header in headers:
            name, _, value = header.partition(":")
            if name.lower() == "content-length":
                length = int(value.strip())
                break
        body_start = header_end + 4
        body_end = body_start + length
        if length <= 0 or body_end > len(raw):
            break
        messages.append(json.loads(raw[body_start:body_end].decode("utf-8")))
        pos = body_end
    return messages


def _frame(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _success(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def _handle_message(message: dict[str, Any], tools: YoungMCPTools) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    if message_id is None:
        return None
    try:
        if method == "initialize":
            return _success(
                message_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "young-stock-cli", "version": __version__},
                },
            )
        if method == "tools/list":
            return _success(message_id, {"tools": list_tools()})
        if method == "tools/call":
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            payload = tools.call(str(params.get("name") or ""), params.get("arguments") or {})
            return _success(
                message_id,
                {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "isError": False},
            )
        if method == "shutdown":
            return _success(message_id, {})
        return _error(message_id, -32601, f"method not found: {method}")
    except MCPToolError as exc:
        return _error(message_id, -32602, str(exc))
    except Exception as exc:
        return _error(message_id, -32603, str(exc))


def serve_stdio(
    *,
    input_stream: Any | None = None,
    output_stream: Any | None = None,
    tools: YoungMCPTools | None = None,
) -> None:
    in_stream = input_stream or getattr(sys.stdin, "buffer", sys.stdin)
    out_stream = output_stream or getattr(sys.stdout, "buffer", sys.stdout)
    raw = in_stream.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    responses = [
        response
        for message in _read_framed_messages(raw)
        for response in [_handle_message(message, tools or YoungMCPTools())]
        if response is not None
    ]
    for response in responses:
        framed = _frame(response)
        try:
            out_stream.write(framed)
        except TypeError:
            out_stream.write(framed.decode("utf-8"))
    if hasattr(out_stream, "flush"):
        out_stream.flush()


if __name__ == "__main__":
    serve_stdio()
