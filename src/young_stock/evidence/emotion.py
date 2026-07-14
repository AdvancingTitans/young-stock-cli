"""Standardized short-term market emotion evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from young_stock.calendar import previous_trade_day


def normalize_stock_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and len(text) >= 8:
            text = text[2:]
    for suffix in (".SH", ".SZ", ".BJ"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    digits = "".join(char for char in text if char.isdigit())
    return digits[-6:] if len(digits) >= 6 else digits


@dataclass
class MarketEmotionEvidence:
    data_date: str
    as_of: str
    zt_count: int | None
    dt_count: int | None
    zb_count: int | None
    seal_ratio: float | None
    blowup_ratio: float | None
    max_board: int | None
    lianban_count: int | None
    ladder: dict[int, list[dict[str, Any]]]
    previous_zt_count: int | None
    promotion_numerator: int | None
    promotion_denominator: int | None
    promotion_rate: float | None
    early_limit_up_count: int | None
    turnover_top: list[dict[str, Any]]
    source: str
    missing_fields: list[str] = field(default_factory=list)
    stale: bool = False
    high_break_count: int | None = None
    limit_up_industries: list[dict[str, Any]] = field(default_factory=list)
    current_limit_up_codes: list[str] = field(default_factory=list)
    current_limit_down_codes: list[str] = field(default_factory=list)
    current_blowup_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _PoolState:
    count: int | None
    rows: list[dict[str, Any]]
    as_of: str | None
    source: str | None
    missing: list[str]
    stale: bool


def _safe_call(default: Any, function: Any, *args: Any) -> Any:
    try:
        return function(*args)
    except Exception as exc:
        if isinstance(default, dict):
            return {"_error": str(exc)}
        return default


def _pool_state(raw: Any, label: str) -> _PoolState:
    missing: list[str] = []
    if not isinstance(raw, dict) or raw.get("_error") or raw.get("_unavailable"):
        return _PoolState(None, [], None, None, [label], False)
    payload = raw.get("data")
    if not isinstance(payload, dict):
        return _PoolState(None, [], _as_of(raw), _source(raw), [label], _stale(raw, None))
    pool_value = payload.get("pool")
    if isinstance(pool_value, list):
        rows = [row for row in pool_value if isinstance(row, dict)]
    else:
        rows = []
        missing.append(f"{label}_pool")
    count = _int_or_none(payload.get("tc"))
    if count is None:
        if isinstance(pool_value, list):
            count = len(rows)
        else:
            missing.append(f"{label}_count")
    as_of = _as_of(raw) or _as_of(payload)
    return _PoolState(count, rows, as_of, _source(raw) or _source(payload), missing, _stale(raw, as_of))


def _as_of(raw: dict[str, Any]) -> str | None:
    for key in ("as_of", "_source_date", "date", "_latest_date", "_requested_date"):
        value = raw.get(key)
        if value:
            return str(value).replace("-", "")
    return None


def _source(raw: dict[str, Any]) -> str | None:
    return str(raw.get("_source") or raw.get("source") or "") or None


def _stale(raw: dict[str, Any], as_of: str | None) -> bool:
    return bool(raw.get("stale") or raw.get("_stale") or raw.get("_date_note") == "latest_available")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _board_days(row: dict[str, Any]) -> int:
    zttj = row.get("zttj") if isinstance(row.get("zttj"), dict) else {}
    for key in ("days", "ct", "lbc"):
        value = _int_or_none(zttj.get(key) if key in zttj else row.get(key))
        if value is not None:
            return max(value, 1)
    return 1


def _stock_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": normalize_stock_code(row.get("c") or row.get("code") or row.get("symbol")),
        "name": row.get("n") or row.get("name"),
        "industry": row.get("hybk") or row.get("industry"),
    }


def _codes(rows: list[dict[str, Any]]) -> set[str]:
    return {code for code in (normalize_stock_code(row.get("c") or row.get("code") or row.get("symbol")) for row in rows) if code}


def _high_board_codes(rows: list[dict[str, Any]]) -> set[str]:
    return {code for row in rows if _board_days(row) >= 2 for code in [normalize_stock_code(row.get("c") or row.get("code") or row.get("symbol"))] if code}


def _ladder(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        days = _board_days(row)
        if days >= 2:
            result.setdefault(days, []).append(_stock_item(row))
    return dict(sorted(result.items(), reverse=True))


def _industry_spread(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        industry = str(row.get("hybk") or row.get("industry") or "未知")
        counts[industry] = counts.get(industry, 0) + 1
    return [{"name": name, "limit_up_count": count} for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]]


def _amount(row: dict[str, Any]) -> float | None:
    for key in ("amount", "f6", "成交额", "turnover"):
        amount = _float_or_none(row.get(key))
        if amount is not None:
            return amount
    return None


def _turnover_top(*pools: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    ranked = []
    for rows in pools:
        for row in rows:
            amount = _amount(row)
            if amount is None:
                continue
            item = _stock_item(row)
            item["amount"] = amount
            ranked.append(item)
    ranked.sort(key=lambda item: item["amount"], reverse=True)
    return ranked[:limit]


def _ratio(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def build_market_emotion(
    core: Any,
    trade_date: str,
    *,
    zt_data: dict[str, Any] | None = None,
    dt_data: dict[str, Any] | None = None,
    zb_data: dict[str, Any] | None = None,
    previous_zt_data: dict[str, Any] | None = None,
) -> MarketEmotionEvidence:
    zt_raw = zt_data if zt_data is not None else _safe_call({}, core.get_zt_pool, trade_date)
    dt_raw = dt_data if dt_data is not None else _safe_call({}, core.get_dt_pool, trade_date)
    zb_raw = zb_data if zb_data is not None else _safe_call({}, core.get_zb_pool, trade_date)
    previous_date = previous_trade_day(trade_date, "a")
    previous_raw = previous_zt_data if previous_zt_data is not None else _safe_call({}, core.get_zt_pool, previous_date)

    zt = _pool_state(zt_raw, "zt")
    dt = _pool_state(dt_raw, "dt")
    zb = _pool_state(zb_raw, "zb")
    previous = _pool_state(previous_raw, "previous_limit_up")

    denominator = zt.count + zb.count if zt.count is not None and zb.count is not None else None
    current_high_codes = _high_board_codes(zt.rows)
    previous_codes = _codes(previous.rows) if previous.count is not None else None
    previous_high_codes = _high_board_codes(previous.rows) if previous.count is not None else None
    promotion_numerator = len(previous_codes & current_high_codes) if previous_codes is not None else None
    promotion_denominator = len(previous_codes) if previous_codes is not None else None
    high_break_count = len(previous_high_codes - current_high_codes) if previous_high_codes is not None else None

    max_board = None
    lianban_count = None
    early_count = None
    if zt.count is not None:
        if zt.count == 0:
            max_board = 0
        elif zt.rows:
            max_board = max(_board_days(row) for row in zt.rows)
        lianban_count = len(current_high_codes)
        early_count = sum(1 for row in zt.rows if _int_or_none(row.get("fbt")) is not None and int(row["fbt"]) <= 100000)

    as_of = zt.as_of or dt.as_of or zb.as_of or trade_date
    sources = sorted({source for source in (zt.source, dt.source, zb.source, previous.source) if source})
    missing = [field for state in (zt, dt, zb, previous) for field in state.missing]

    return MarketEmotionEvidence(
        data_date=as_of,
        as_of=as_of,
        zt_count=zt.count,
        dt_count=dt.count,
        zb_count=zb.count,
        seal_ratio=_ratio(zt.count, denominator),
        blowup_ratio=_ratio(zb.count, denominator),
        max_board=max_board,
        lianban_count=lianban_count,
        ladder=_ladder(zt.rows),
        previous_zt_count=previous.count,
        promotion_numerator=promotion_numerator,
        promotion_denominator=promotion_denominator,
        promotion_rate=_ratio(promotion_numerator, promotion_denominator),
        early_limit_up_count=early_count,
        turnover_top=_turnover_top(zt.rows, dt.rows, zb.rows),
        source=",".join(sources) if sources else "eastmoney",
        missing_fields=sorted(set(missing)),
        stale=any((zt.stale, dt.stale, zb.stale)) or any(
            state.as_of is not None and state.as_of != str(trade_date).replace("-", "") for state in (zt, dt, zb)
        ),
        high_break_count=high_break_count,
        limit_up_industries=_industry_spread(zt.rows),
        current_limit_up_codes=sorted(_codes(zt.rows)),
        current_limit_down_codes=sorted(_codes(dt.rows)),
        current_blowup_codes=sorted(_codes(zb.rows)),
    )


def map_emotion_to_modules(emotion: MarketEmotionEvidence, holdings: list[Any] | None = None) -> dict[str, dict[str, Any]]:
    holding_codes = sorted({code for code in (normalize_stock_code(item) for item in holdings or []) if code})
    holding_set = set(holding_codes)
    return {
        "M1": {
            "emotion_market": {
                "zt_count": emotion.zt_count,
                "dt_count": emotion.dt_count,
                "zb_count": emotion.zb_count,
                "turnover_top": emotion.turnover_top,
            }
        },
        "M2": {"limit_up_diffusion": emotion.limit_up_industries},
        "M3": {
            "emotion": {
                "zt_count": emotion.zt_count,
                "seal_ratio": emotion.seal_ratio,
                "max_board": emotion.max_board,
                "lianban_count": emotion.lianban_count,
                "ladder": emotion.ladder,
                "previous_zt_count": emotion.previous_zt_count,
                "promotion_numerator": emotion.promotion_numerator,
                "promotion_denominator": emotion.promotion_denominator,
                "promotion_rate": emotion.promotion_rate,
                "early_limit_up_count": emotion.early_limit_up_count,
                "source": emotion.source,
                "as_of": emotion.as_of,
                "missing_fields": emotion.missing_fields,
                "stale": emotion.stale,
            }
        },
        "M4": {
            "emotion": {
                "dt_count": emotion.dt_count,
                "zb_count": emotion.zb_count,
                "blowup_ratio": emotion.blowup_ratio,
                "high_break_count": emotion.high_break_count,
                "source": emotion.source,
                "as_of": emotion.as_of,
                "missing_fields": emotion.missing_fields,
                "stale": emotion.stale,
            }
        },
        "M5": {
            "emotion_alignment": {
                "holding_codes": holding_codes,
                "limit_up_holdings": sorted(holding_set & set(emotion.current_limit_up_codes)),
                "limit_down_holdings": sorted(holding_set & set(emotion.current_limit_down_codes)),
                "blowup_holdings": sorted(holding_set & set(emotion.current_blowup_codes)),
                "active_industries": emotion.limit_up_industries,
            }
        },
        "M6": {
            "emotion_persistence": {
                "promotion_rate": emotion.promotion_rate,
                "promotion_numerator": emotion.promotion_numerator,
                "promotion_denominator": emotion.promotion_denominator,
                "max_board": emotion.max_board,
                "lianban_count": emotion.lianban_count,
            }
        },
    }


def compress_emotion_for_m7(emotion: MarketEmotionEvidence) -> dict[str, Any]:
    return {
        "data_date": emotion.data_date,
        "as_of": emotion.as_of,
        "zt_count": emotion.zt_count,
        "dt_count": emotion.dt_count,
        "zb_count": emotion.zb_count,
        "seal_ratio": emotion.seal_ratio,
        "blowup_ratio": emotion.blowup_ratio,
        "max_board": emotion.max_board,
        "lianban_count": emotion.lianban_count,
        "promotion": {
            "numerator": emotion.promotion_numerator,
            "denominator": emotion.promotion_denominator,
            "rate": emotion.promotion_rate,
        },
        "early_limit_up_count": emotion.early_limit_up_count,
        "high_break_count": emotion.high_break_count,
        "source": emotion.source,
        "missing_fields": emotion.missing_fields,
        "stale": emotion.stale,
    }
