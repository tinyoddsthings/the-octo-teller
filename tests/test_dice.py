"""dice.py 單元測試——表達式解析、擲骰、優劣勢、保留最高/最低。"""

from __future__ import annotations

import random

import pytest

from tot.gremlins.bone_engine.dice import (
    DiceResult,
    RollType,
    parse_expression,
    roll,
    roll_ability_scores,
    roll_d20,
    roll_damage,
)

# ---------------------------------------------------------------------------
# TestParseExpression
# ---------------------------------------------------------------------------


class TestParseExpression:
    """骰子表達式解析。"""

    def test_simple_d20(self):
        count, sides, kh, kl, mod = parse_expression("d20")
        assert (count, sides, kh, kl, mod) == (1, 20, None, None, 0)

    def test_2d6(self):
        count, sides, kh, kl, mod = parse_expression("2d6")
        assert (count, sides) == (2, 6)

    def test_with_positive_modifier(self):
        count, sides, kh, kl, mod = parse_expression("1d8+3")
        assert (count, sides, mod) == (1, 8, 3)

    def test_with_negative_modifier(self):
        count, sides, kh, kl, mod = parse_expression("d20-1")
        assert (count, sides, mod) == (1, 20, -1)

    def test_keep_highest(self):
        count, sides, kh, kl, mod = parse_expression("4d6kh3")
        assert (count, sides, kh, kl) == (4, 6, 3, None)

    def test_keep_lowest(self):
        count, sides, kh, kl, mod = parse_expression("2d20kl1")
        assert (count, sides, kh, kl) == (2, 20, None, 1)

    def test_whitespace_stripped(self):
        count, sides, kh, kl, mod = parse_expression(" 2d6 + 3 ")
        assert (count, sides, mod) == (2, 6, 3)

    def test_case_insensitive(self):
        count, sides, kh, kl, mod = parse_expression("2D8+1")
        assert (count, sides, mod) == (2, 8, 1)

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="無效"):
            parse_expression("not_a_dice")

    def test_zero_sides(self):
        with pytest.raises(ValueError, match="至少"):
            parse_expression("1d0")


# ---------------------------------------------------------------------------
# TestDiceResult
# ---------------------------------------------------------------------------


class TestDiceResult:
    """DiceResult 資料結構屬性。"""

    def test_total_sum_plus_modifier(self):
        r = DiceResult(expression="2d6+3", rolls=[4, 5], modifier=3)
        assert r.total == 12

    def test_total_no_modifier(self):
        r = DiceResult(expression="2d6", rolls=[3, 4])
        assert r.total == 7

    def test_natural_single_die(self):
        r = DiceResult(expression="d20", rolls=[15])
        assert r.natural == 15

    def test_natural_multi_dice_is_none(self):
        r = DiceResult(expression="2d6", rolls=[3, 4])
        assert r.natural is None

    def test_is_nat20(self):
        r = DiceResult(expression="d20", rolls=[20])
        assert r.is_nat20
        assert not r.is_nat1

    def test_is_nat1(self):
        r = DiceResult(expression="d20", rolls=[1])
        assert r.is_nat1
        assert not r.is_nat20

    def test_not_nat20_multi_dice(self):
        """多顆骰子即使總和高也不算 nat20。"""
        r = DiceResult(expression="2d6", rolls=[6, 6])
        assert not r.is_nat20


# ---------------------------------------------------------------------------
# TestRoll
# ---------------------------------------------------------------------------


class TestRoll:
    """roll() 主函式。"""

    def test_basic_roll_range(self):
        """d6 結果在 1~6 之間。"""
        rng = random.Random(0)
        for _ in range(50):
            result = roll("1d6", rng=rng)
            assert 1 <= result.total <= 6

    def test_modifier_applied(self):
        rng = random.Random(42)
        result = roll("d20+5", rng=rng)
        # 骰子 1~20，加 5 → 6~25
        assert 6 <= result.total <= 25

    def test_negative_modifier(self):
        rng = random.Random(42)
        result = roll("d20-2", rng=rng)
        assert result.modifier == -2

    def test_multi_dice_count(self):
        rng = random.Random(42)
        result = roll("3d6", rng=rng)
        assert len(result.rolls) == 3
        assert all(1 <= r <= 6 for r in result.rolls)

    def test_deterministic_with_seed(self):
        """同 seed 產生相同結果。"""
        r1 = roll("2d8+3", rng=random.Random(99))
        r2 = roll("2d8+3", rng=random.Random(99))
        assert r1.total == r2.total
        assert r1.rolls == r2.rolls

    def test_expression_stored(self):
        result = roll("2d6+1", rng=random.Random(0))
        assert result.expression == "2d6+1"


# ---------------------------------------------------------------------------
# TestAdvantageDisadvantage
# ---------------------------------------------------------------------------


class TestAdvantageDisadvantage:
    """優勢/劣勢擲骰。"""

    def test_advantage_takes_higher(self):
        """優勢：取兩顆中較高的。"""
        rng = random.Random(42)
        result = roll("d20", roll_type=RollType.ADVANTAGE, rng=rng)
        assert len(result.advantage_rolls) == 2
        assert result.rolls[0] == max(result.advantage_rolls)

    def test_disadvantage_takes_lower(self):
        """劣勢：取兩顆中較低的。"""
        rng = random.Random(42)
        result = roll("d20", roll_type=RollType.DISADVANTAGE, rng=rng)
        assert len(result.advantage_rolls) == 2
        assert result.rolls[0] == min(result.advantage_rolls)

    def test_advantage_only_on_single_d20(self):
        """多骰（如 2d6）不適用優勢。"""
        rng = random.Random(42)
        result = roll("2d6", roll_type=RollType.ADVANTAGE, rng=rng)
        assert result.advantage_rolls == []

    def test_normal_no_advantage_rolls(self):
        rng = random.Random(42)
        result = roll("d20", roll_type=RollType.NORMAL, rng=rng)
        assert result.advantage_rolls == []

    def test_advantage_statistical_tendency(self):
        """優勢統計上應比正常高。"""
        rng_adv = random.Random(1)
        rng_norm = random.Random(1)
        adv_totals = [
            roll("d20", roll_type=RollType.ADVANTAGE, rng=rng_adv).total for _ in range(200)
        ]
        norm_totals = [
            roll("d20", roll_type=RollType.NORMAL, rng=rng_norm).total for _ in range(200)
        ]
        # 優勢平均應明顯高於普通（d20 平均 10.5，優勢約 13.8）
        assert sum(adv_totals) / len(adv_totals) > sum(norm_totals) / len(norm_totals)


# ---------------------------------------------------------------------------
# TestKeepHighLow
# ---------------------------------------------------------------------------


class TestKeepHighLow:
    """保留最高/保留最低。"""

    def test_keep_highest_3_of_4(self):
        """4d6kh3：保留最高 3 顆，丟棄 1 顆。"""
        rng = random.Random(42)
        result = roll("4d6kh3", rng=rng)
        assert len(result.rolls) == 3
        assert len(result.dropped) == 1
        # 被丟棄的應 <= 所有保留的
        assert result.dropped[0] <= min(result.rolls)

    def test_keep_lowest(self):
        """2d20kl1：保留最低 1 顆。"""
        rng = random.Random(42)
        result = roll("2d20kl1", rng=rng)
        assert len(result.rolls) == 1
        assert len(result.dropped) == 1
        assert result.rolls[0] <= result.dropped[0]

    def test_keep_high_total_range(self):
        """4d6kh3 的結果在 3~18 之間。"""
        rng = random.Random(0)
        for _ in range(50):
            result = roll("4d6kh3", rng=rng)
            assert 3 <= result.total <= 18


# ---------------------------------------------------------------------------
# TestConvenienceFunctions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """便利函式：roll_d20, roll_damage, roll_ability_scores。"""

    def test_roll_d20_basic(self):
        rng = random.Random(42)
        result = roll_d20(rng=rng)
        assert 1 <= result.total <= 20
        assert result.expression.startswith("d20")

    def test_roll_d20_with_modifier(self):
        rng = random.Random(42)
        result = roll_d20(modifier=5, rng=rng)
        assert result.modifier == 5
        assert "d20+5" in result.expression

    def test_roll_d20_negative_modifier(self):
        rng = random.Random(42)
        result = roll_d20(modifier=-3, rng=rng)
        assert result.modifier == -3
        assert "d20-3" in result.expression

    def test_roll_d20_advantage(self):
        rng = random.Random(42)
        result = roll_d20(modifier=3, roll_type=RollType.ADVANTAGE, rng=rng)
        assert result.roll_type == RollType.ADVANTAGE
        assert len(result.advantage_rolls) == 2

    def test_roll_damage_always_normal(self):
        rng = random.Random(42)
        result = roll_damage("2d6+3", rng=rng)
        assert result.roll_type == RollType.NORMAL
        assert result.modifier == 3

    def test_roll_ability_scores_count(self):
        """產生 6 個屬性值。"""
        scores = roll_ability_scores(rng=random.Random(42))
        assert len(scores) == 6

    def test_roll_ability_scores_range(self):
        """每個屬性值在 3~18 之間（4d6kh3）。"""
        scores = roll_ability_scores(rng=random.Random(42))
        for s in scores:
            assert 3 <= s <= 18

    def test_roll_ability_scores_deterministic(self):
        s1 = roll_ability_scores(rng=random.Random(99))
        s2 = roll_ability_scores(rng=random.Random(99))
        assert s1 == s2
