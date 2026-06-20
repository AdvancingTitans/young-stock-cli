from young_stock.review_gate import review_investment_output


def test_review_gate_checks_attitude_evidence_risk_action_and_numbers():
    result = review_investment_output(
        "总体态度：中性\n核心理由：据公开数据，ROE 为 20%。\n风险：增长放缓。\n行动建议：持有观察。",
        {"roe": "20%"},
    )

    assert all(result.values())


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
