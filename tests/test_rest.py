"""休息系統單元測試。"""

from __future__ import annotations

import random

from tot.gremlins.bone_engine.rest import long_rest, short_rest
from tot.models import AbilityScores, Character, SpellSlots


def _fighter(hp_current: int = 20) -> Character:
    """STR 16, CON 14 Fighter, 5 Hit Dice (d10)."""
    return Character(
        name="Aldric",
        class_levels={"Fighter": 5},
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=hp_current,
        hit_dice_remaining={10: 5},
        ac=18,
        speed=9,
    )


def _wizard(hp_current: int = 10) -> Character:
    """INT 18, CON 12 Wizard, 5 Hit Dice (d6)."""
    return Character(
        name="陶德",
        class_levels={"Wizard": 5},
        ability_scores=AbilityScores(STR=8, DEX=14, CON=12, INT=18, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=27,
        hp_current=hp_current,
        hit_dice_remaining={6: 5},
        ac=15,
        speed=9,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 2, 2: 1, 3: 0},  # 部分消耗
        ),
    )


class TestShortRest:
    def test_recovers_hp(self):
        """短休使用 Hit Dice 回復 HP。"""
        fighter = _fighter(hp_current=20)
        rng = random.Random(42)
        result = short_rest([fighter], rng=rng)
        assert result.rest_type == "short"
        assert result.elapsed_seconds == 3600
        assert fighter.hp_current > 20
        assert "Aldric" in result.hp_recovered
        assert fighter.hit_dice_remaining_count < 5

    def test_full_hp_no_dice_used(self):
        """HP 全滿時不消耗 Hit Dice。"""
        fighter = _fighter(hp_current=44)
        result = short_rest([fighter])
        assert result.hp_recovered == {}
        assert result.hit_dice_used == {}
        assert fighter.hit_dice_remaining_count == 5

    def test_no_dice_remaining(self):
        """Hit Dice 用盡時無法回復。"""
        fighter = _fighter(hp_current=20)
        fighter.hit_dice_remaining = {10: 0}
        result = short_rest([fighter])
        assert result.hp_recovered == {}
        assert fighter.hp_current == 20

    def test_stops_at_max_hp(self):
        """HP 回復不超過上限。"""
        fighter = _fighter(hp_current=43)  # 差 1 HP
        rng = random.Random(42)
        result = short_rest([fighter], rng=rng)
        assert fighter.hp_current == 44
        # 只需要 1 顆 Hit Die
        assert result.hit_dice_used.get("Aldric", 0) == 1

    def test_multiple_characters(self):
        """多角色各自回復。"""
        fighter = _fighter(hp_current=20)
        wizard = _wizard(hp_current=10)
        rng = random.Random(42)
        short_rest([fighter, wizard], rng=rng)
        assert fighter.hp_current > 20
        assert wizard.hp_current > 10


class TestLongRest:
    def test_full_hp_recovery(self):
        """長休回復至 HP 全滿。"""
        fighter = _fighter(hp_current=20)
        result = long_rest([fighter])
        assert fighter.hp_current == 44
        assert result.hp_recovered["Aldric"] == 24
        assert result.elapsed_seconds == 28800
        assert result.rest_type == "long"

    def test_spell_slots_recovered(self):
        """長休恢復法術欄位。"""
        wizard = _wizard()
        assert wizard.spell_slots.current_slots[3] == 0
        result = long_rest([wizard])
        assert wizard.spell_slots.current_slots == {1: 4, 2: 3, 3: 2}
        assert result.spell_slots_recovered is True

    def test_hit_dice_recovery(self):
        """長休回復一半 Hit Dice。"""
        fighter = _fighter()
        fighter.hit_dice_remaining = {10: 0}
        long_rest([fighter])
        # 5 // 2 = 2 顆回復
        assert fighter.hit_dice_remaining_count == 2

    def test_hit_dice_min_one(self):
        """1 級角色（1 顆 Hit Die）長休至少回復 1 顆。"""
        char = Character(
            name="Newbie",
            class_levels={"Fighter": 1},
            hp_max=10,
            hp_current=10,
            hit_dice_remaining={10: 0},
        )
        long_rest([char])
        assert char.hit_dice_remaining_count == 1

    def test_hit_dice_cap(self):
        """Hit Dice 不超過上限。"""
        fighter = _fighter()
        fighter.hit_dice_remaining = {10: 4}
        long_rest([fighter])
        # 回復 2 顆，但不超過 5
        assert fighter.hit_dice_remaining_count == 5

    def test_already_full(self):
        """HP 已滿時不出現在 hp_recovered。"""
        fighter = _fighter(hp_current=44)
        result = long_rest([fighter])
        assert "Aldric" not in result.hp_recovered
