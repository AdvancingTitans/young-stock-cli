import pytest

from young_stock.debate import DebateConfig, DebateEngine, build_institutional_prompt
from young_stock.methods import METHOD_CARDS, select_method_cards


def test_method_registry_covers_requested_institutional_structures_without_scores():
    assert len([card for card in METHOD_CARDS.values() if card.category == "valuation"]) == 6
    assert len([card for card in METHOD_CARDS.values() if card.category == "research"]) == 7
    assert len([card for card in METHOD_CARDS.values() if card.category == "decision"]) == 6
    assert all("score" not in card.__dataclass_fields__ for card in METHOD_CARDS.values())


def test_long_term_lens_does_not_receive_vcp_as_primary_method():
    assert "vcp" not in {card.id for card in select_method_cards("价值")}
    assert "dd" in {card.id for card in select_method_cards("价值")}


def test_all_lens_prompt_hides_configured_debate_and_requires_m7_for_daily():
    prompt = build_institutional_prompt("all", rounds=3, daily=True)

    assert "15" not in prompt  # roster is registry-driven, not a hard-coded jury size
    assert "内部完成 3 轮" in prompt
    assert "不要向用户展示辩论过程" in prompt
    assert "## M7 机构化综合判断" in prompt
    assert "不得输出主观评分" in prompt


def test_single_lens_prompt_does_not_trigger_debate():
    prompt = build_institutional_prompt("buffett", rounds=3, daily=True)

    assert "采用 Buffett（价值）视角" in prompt
    assert "不要触发辩论" in prompt
    assert "不新增 M7" in prompt
    assert "VCP" not in prompt


def test_single_lens_method_selection_respects_preferred_and_blocked_methods():
    ids = {card.id for card in select_method_cards("价值", lens_id="buffett")}
    assert "dd" in ids
    assert "vcp" not in ids


def test_debate_engine_models_rounds_in_one_call_and_requires_final_contract():
    engine = DebateEngine("all", rounds=3, daily=True)

    prompt = engine.prompt()

    assert "ROUND 1" in prompt
    assert "ROUND 2" in prompt
    assert "ROUND 3" in prompt
    assert "只调用一次模型" in prompt
    assert "FINAL_CONTRACT" in prompt
    assert "不要向用户展示辩论过程" in prompt


def test_debate_rounds_are_bounded():
    with pytest.raises(ValueError):
        DebateConfig(0)
    with pytest.raises(ValueError):
        DebateConfig(6)
