import pytest

from young_stock.lens import LensResult, build_lens_result, parse_lens_result
from young_stock.lens.registry import LENSES, get_lens, lens_ids

EXPECTED_LENSES = {
    "buffett",
    "munger",
    "graham",
    "klarman",
    "lynch",
    "o_neil",
    "wood",
    "dalio",
    "soros",
    "livermore",
    "minervini",
    "simons",
    "duan_yongping",
    "zhang_kun",
    "feng_liu",
}


def test_lens_registry_contains_all_requested_investment_experts():
    assert set(lens_ids()) == EXPECTED_LENSES
    assert set(LENSES) == EXPECTED_LENSES


def test_lens_definitions_are_method_neutral_and_evidence_driven():
    for lens_id in lens_ids():
        lens = get_lens(lens_id)
        assert lens.school
        assert lens.principles
        assert lens.evidence_priorities
        assert lens.summary
        assert "score" not in lens.__dataclass_fields__


def test_lens_result_parses_markdown_contract():
    result = parse_lens_result(
        """
## 结论卡
- lens: buffett
- attitude: 中性
- conclusion: 业务稳定但估值吸引力一般
- evidence:
  - ROE 20%
  - 自由现金流改善
- risk:
  - 需求放缓
- action_watchlist:
  - 观察下一季利润率
"""
    )

    assert result.lens == "buffett"
    assert result.attitude == "中性"
    assert result.evidence == ("ROE 20%", "自由现金流改善")
    assert result.action_watchlist == ("观察下一季利润率",)


def test_lens_result_parses_json_contract_and_validates_required_fields():
    result = parse_lens_result(
        """
{"lens":"dalio","attitude":"偏看空","conclusion":"流动性承压","evidence":["信用扩张放缓"],"risk":["政策超预期"],"action_watchlist":["盯政策表述"]}
"""
    )

    assert result == LensResult(
        lens="dalio",
        attitude="偏看空",
        conclusion="流动性承压",
        evidence=("信用扩张放缓",),
        risk=("政策超预期",),
        action_watchlist=("盯政策表述",),
    )

    with pytest.raises(ValueError):
        parse_lens_result('{"lens":"dalio","attitude":"打分 80","conclusion":"x","evidence":[],"risk":[],"action_watchlist":[]}')


def test_build_lens_result_rejects_wrong_lens_output():
    with pytest.raises(ValueError):
        build_lens_result("buffett", '{"lens":"munger","attitude":"中性","conclusion":"x","evidence":["a"],"risk":["b"],"action_watchlist":["c"]}')
