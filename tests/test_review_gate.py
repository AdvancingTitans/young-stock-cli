from young_stock.review_gate import _allowed_numeric_signatures, review_investment_output


def test_review_gate_checks_attitude_evidence_risk_action_and_numbers():
    result = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，ROE 为 21。\n风险：增长放缓。\n行动建议：持有观察。",
        {"roe": "21%"},
    )

    assert all(result.values())


def test_review_gate_does_not_allow_financial_numbers_without_evidence():
    result = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，ROE 为 20。\n风险：增长放缓。\n行动建议：持有观察。",
        {},
    )

    assert result["numbers_grounded"] is False


def test_review_gate_does_not_allow_stock_codes_without_evidence():
    result = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，标的是 000001。\n风险：增长放缓。\n行动建议：持有观察。",
        {},
    )

    assert result["numbers_grounded"] is False


def test_review_gate_rejects_scores_and_unsupported_numbers():
    result = review_investment_output(
        "总体态度：偏看多\n证据：收入增长 99%。\n风险：估值。\n行动建议：观察。\n评分：88",
        {"revenue_growth": "10%"},
    )

    assert result["no_subjective_score"] is False
    assert result["numbers_grounded"] is False


def test_review_gate_requires_contract_fields():
    result = review_investment_output(
        "总体态度：偏看多\n风险：估值。\n行动建议：观察。",
        {"revenue_growth": "10%"},
    )

    assert result["conclusion_present"] is False
    assert result["watchlist_present"] is False


def test_review_gate_allows_grounded_symbol_digits_embedded_in_evidence_identifiers():
    result = review_investment_output(
        "# 贵州茅台（600519）复盘\n"
        "总体态度：偏看多\n"
        "详细结论：据公开数据，600519 的 ROE 为 20%。\n"
        "证据：据公开数据，SH600519 对应标的 ROE 为 20%。\n"
        "风险：估值波动。\n"
        "行动建议：持有观察。\n"
        "观察清单：1. 跟踪批价。",
        {"analysis_symbol": "SH600519", "roe": "20%"},
    )

    assert result["numbers_grounded"] is True


def test_review_gate_date_evidence_does_not_ground_independent_date_parts():
    result = review_investment_output(
        "# 日报\n"
        "总体态度：中性\n"
        "详细结论：2026-05-29 发布，2026 年业绩将改善，05 月跟踪，29 日复盘。\n"
        "证据：报告日期为 20260529。\n"
        "风险：预测可能落空。\n"
        "行动建议：持有观察。\n"
        "观察清单：1. 跟踪后续公告。",
        {"reported_date": "20260529"},
    )

    assert result["numbers_grounded"] is False


def test_review_gate_allows_full_hyphenated_date_when_atomic_date_is_evidence():
    result = review_investment_output(
        "# 2026-05-29 日报\n"
        "总体态度：中性\n"
        "详细结论：据公开数据，当日市场维持震荡。\n"
        "证据：报告日期为 2026-05-29。\n"
        "风险：成交不足。\n"
        "行动建议：持有观察。\n"
        "观察清单：跟踪下一交易日量能。",
        {"reported_date": "20260529"},
    )

    assert result["numbers_grounded"] is True


def test_review_gate_keeps_eight_digit_dates_atomic_in_evidence_signatures():
    allowed = _allowed_numeric_signatures('{"reported_date":"20260529"}')

    assert ("20260529", False) in allowed
    assert ("2026", False) not in allowed
    assert ("05", False) not in allowed
    assert ("29", False) not in allowed


def test_review_gate_allows_business_index_names_and_localized_full_dates():
    result = review_investment_output(
        "# 2026年05月29日 日报\n"
        "总体态度：中性\n"
        "详细结论：据公开市场数据，沪深300与中证500延续分化，科创50需要观察量能。\n"
        "证据：据公开市场数据，报告日期为 2026年05月29日。\n"
        "风险提示：若量能不足，反弹延续性仍需确认。\n"
        "综合持仓建议：持有观察，不追高。\n"
        "下一交易日观察清单：跟踪沪深300、中证500、科创50的量能变化。",
        {"reported_date": "20260529"},
    )

    assert result["numbers_grounded"] is True


def test_review_gate_keeps_unrounded_financial_claims_strict():
    result = review_investment_output(
        "总体态度：中性\n"
        "详细结论：据公开市场数据，收入增长 300%，净流入 50 亿元。\n"
        "证据：证据暂缺。\n"
        "风险提示：波动。\n"
        "综合持仓建议：持有观察。\n"
        "观察清单：跟踪公告。",
        {},
    )

    assert result["numbers_grounded"] is False


def test_review_gate_accepts_formal_daily_report_synonyms():
    result = review_investment_output(
        "# 日报\n"
        "M7 机构化综合判断：总体态度为中性。\n"
        "综合判断：公开市场数据显示，市场仍处震荡整理。\n"
        "风险提示：量能不足可能压制反弹。\n"
        "综合持仓建议：等待确认，不追高。\n"
        "下一交易日跟踪：观察量能与板块持续性。",
        {},
    )

    assert result["conclusion_present"] is True
    assert result["evidence_present"] is True
    assert result["risk_present"] is True
    assert result["action_present"] is True
    assert result["watchlist_present"] is True


def test_review_gate_accepts_stock_report_rating_as_attitude():
    result = review_investment_output(
        "# 贵州茅台个股复盘\n"
        "综合判断：据公开市场数据，公司短线仍以震荡观察为主。\n"
        "投资评级：持有观察。\n"
        "证据：公开行情显示价格波动可控。\n"
        "风险提示：若量能不足，反弹延续性仍需确认。\n"
        "操作建议：等待放量确认，不追高。\n"
        "观察清单：跟踪下一交易日成交额与关键价位。",
        {},
    )

    assert result["attitude_present"] is True


def test_review_gate_opposite_sign_numbers_are_not_grounded():
    negative_percent = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，利润率为 -3%。\n风险：波动。\n行动建议：持有观察。",
        {"margin": "3%"},
    )
    positive_number = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，净流入为 31。\n风险：波动。\n行动建议：持有观察。",
        {"net_inflow": "-31"},
    )

    assert negative_percent["numbers_grounded"] is False
    assert positive_number["numbers_grounded"] is False
