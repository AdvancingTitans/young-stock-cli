from types import SimpleNamespace

from young_stock.evidence import build_daily_evidence
from young_stock.evidence.emotion import (
    build_market_emotion,
    compress_emotion_for_m7,
    map_emotion_to_modules,
    normalize_stock_code,
)
from young_stock.review_gate import review_investment_output


def pool(rows, *, tc=None, date="20260622", source="eastmoney", stale=False):
    data = {"pool": rows}
    if tc is not None:
        data["tc"] = tc
    return {"data": data, "_source_date": date, "_source": source, "stale": stale}


def row(code, name=None, days=1, first_time=93000, industry="AI", amount=None):
    payload = {
        "c": code,
        "n": name or code,
        "zttj": {"days": days},
        "fbt": first_time,
        "hybk": industry,
    }
    if amount is not None:
        payload["amount"] = amount
    return payload


class EmotionCore:
    def __init__(self, today, previous):
        self.today = today
        self.previous = previous
        self.zt_calls = []

    def get_zt_pool(self, date):
        self.zt_calls.append(date)
        return self.previous if len(self.zt_calls) == 2 else self.today["zt"]

    def get_dt_pool(self, date):
        return self.today["dt"]

    def get_zb_pool(self, date):
        return self.today["zb"]


def test_promotion_rate_uses_code_set_intersection_not_board_count_ratio():
    today = {
        "zt": pool(
            [
                row("000001.SZ", "A", days=2, amount=30),
                row("SH600002", "B", days=3, amount=20),
                row("300003", "C", days=1, amount=40),
            ],
            tc=3,
        ),
        "dt": pool([row("000004", "D")], tc=1),
        "zb": pool([row("000005", "E")], tc=1),
    }
    previous = pool([row("000001", "A"), row("600002.SH", "B"), row("000006", "F")], tc=3, date="20260619")

    emotion = build_market_emotion(EmotionCore(today, previous), "20260622")

    assert emotion.previous_zt_count == 3
    assert emotion.promotion_numerator == 2
    assert emotion.promotion_denominator == 3
    assert emotion.promotion_rate == 2 / 3
    assert emotion.max_board == 3
    assert emotion.lianban_count == 2
    assert emotion.ladder[3][0]["code"] == "600002"


def test_holiday_previous_trade_day_is_used_and_as_of_stays_source_date():
    today = {
        "zt": pool([row("000001", days=2)], tc=1, date="20260622", stale=True),
        "dt": pool([], tc=0, date="20260622"),
        "zb": pool([], tc=0, date="20260622"),
    }
    previous = pool([row("000001")], tc=1, date="20260618")
    core = EmotionCore(today, previous)

    emotion = build_market_emotion(core, "20260622")

    assert core.zt_calls == ["20260622", "20260618"]
    assert emotion.as_of == "20260622"
    assert emotion.stale is True


def test_missing_previous_pool_keeps_promotion_fields_none():
    today = {"zt": pool([row("000001", days=2)], tc=1), "dt": pool([], tc=0), "zb": pool([], tc=0)}

    emotion = build_market_emotion(EmotionCore(today, {"_error": "closed"}), "20260622")

    assert emotion.previous_zt_count is None
    assert emotion.promotion_numerator is None
    assert emotion.promotion_denominator is None
    assert emotion.promotion_rate is None
    assert "previous_limit_up" in emotion.missing_fields


def test_stock_code_normalization_handles_common_a_share_forms():
    assert normalize_stock_code("000001.SZ") == "000001"
    assert normalize_stock_code("SH600519") == "600519"
    assert normalize_stock_code("  sz300750 ") == "300750"
    assert normalize_stock_code("688111.SH") == "688111"


def test_empty_pools_do_not_invent_undefined_ratios():
    today = {"zt": pool([], tc=0), "dt": pool([], tc=0), "zb": pool([], tc=0)}

    emotion = build_market_emotion(EmotionCore(today, pool([], tc=0, date="20260619")), "20260622")

    assert emotion.zt_count == 0
    assert emotion.dt_count == 0
    assert emotion.zb_count == 0
    assert emotion.seal_ratio is None
    assert emotion.blowup_ratio is None
    assert emotion.max_board == 0
    assert emotion.turnover_top == []


def test_partial_missing_fields_remain_none_and_are_marked_missing():
    today = {"zt": {"data": {}}, "dt": pool([], tc=0), "zb": pool([], tc=0)}

    emotion = build_market_emotion(EmotionCore(today, pool([], tc=0, date="20260619")), "20260622")

    assert emotion.zt_count is None
    assert emotion.early_limit_up_count is None
    assert "zt_count" in emotion.missing_fields
    assert "zt_pool" in emotion.missing_fields


def test_emotion_maps_into_m3_m4_without_trade_signals():
    emotion = build_market_emotion(
        EmotionCore(
            {
                "zt": pool([row("000001", days=2), row("000002", days=1)], tc=2),
                "dt": pool([row("000003")], tc=1),
                "zb": pool([row("000004")], tc=1),
            },
            pool([row("000001"), row("000005", days=2)], tc=2, date="20260619"),
        ),
        "20260622",
    )

    modules = map_emotion_to_modules(emotion, holdings=["000003"])

    assert modules["M3"]["emotion"]["promotion_numerator"] == 1
    assert modules["M3"]["emotion"]["seal_ratio"] == 2 / 3
    assert modules["M4"]["emotion"]["high_break_count"] == 1
    assert modules["M5"]["emotion_alignment"]["limit_down_holdings"] == ["000003"]
    assert "buy" not in str(modules).lower()
    assert "sell" not in str(modules).lower()


def test_daily_evidence_includes_mapped_emotion_sections():
    core = SimpleNamespace(
        get_index=lambda date: [],
        fetch_hk_indices_sina=lambda symbols, date: [],
        fetch_us_indices_sina=lambda symbols, date: [],
        fetch_northbound_flow_snapshot=lambda date: {},
        get_fund_flow=lambda date, strict_date=False: {},
        fetch_eastmoney_board_list=lambda kind, date, limit=100: {"rows": []},
        get_zt_pool=lambda date: pool([row("000001", days=2)] if date == "20260622" else [row("000001")], tc=1, date=date),
        get_dt_pool=lambda date: pool([], tc=0, date=date),
        get_zb_pool=lambda date: pool([], tc=0, date=date),
    )

    evidence = build_daily_evidence(core, "20260622", {"stocks": []})

    assert evidence.modules["M3"]["emotion"]["promotion_rate"] == 1
    assert evidence.modules["M4"]["emotion"]["dt_count"] == 0
    assert evidence.modules["M6"]["emotion_persistence"]["promotion_rate"] == 1
    assert evidence.meta["m7_emotion_summary"]["promotion"] == {"numerator": 1, "denominator": 1, "rate": 1}


def test_m7_compression_keeps_summary_only():
    emotion = build_market_emotion(
        EmotionCore(
            {"zt": pool([row("000001", days=2, amount=10)], tc=1), "dt": pool([], tc=0), "zb": pool([], tc=0)},
            pool([row("000001")], tc=1, date="20260619"),
        ),
        "20260622",
    )

    summary = compress_emotion_for_m7(emotion)

    assert summary["data_date"] == "20260622"
    assert summary["promotion"] == {"numerator": 1, "denominator": 1, "rate": 1}
    assert "zt_pool" not in summary
    assert "ladder" not in summary
    assert "turnover_top" not in summary


def test_review_gate_rejects_emotion_as_direct_trade_or_position_signal():
    result = review_investment_output(
        "总体态度：偏看多\n详细结论：据公开市场数据，涨停扩散。\n证据：涨停家数为 12。\n风险：炸板扩大。\n行动建议：短线情绪触发买入信号并提高仓位。\n观察清单：跟踪明日封板率。",
        {"zt_count": 12},
    )

    assert result["no_forbidden_trading_language"] is False
