"""conditions.py 單元測試——狀態套用、移除、堆疊、回合計時。"""

from __future__ import annotations

import pytest

from tot.gremlins.bone_engine.conditions import (
    apply_condition,
    can_take_action,
    exhaustion_penalty,
    get_conditions,
    has_condition_effect,
    is_incapacitated,
    remove_condition,
    tick_conditions_end_of_turn,
    tick_conditions_start_of_turn,
)
from tot.models import Character, Condition, Monster

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fighter():
    """建立一個基礎角色（直接用 model，不經 build_character）。"""
    return Character(name="TestFighter", char_class="Fighter", hp_max=12, hp_current=12)


@pytest.fixture
def goblin():
    """建立一個哥布林怪物。"""
    return Monster(
        name="Goblin",
        size="Small",
        monster_type="humanoid",
        alignment="neutral evil",
        armor_class=15,
        hit_points=7,
        max_hit_points=7,
        speed=30,
        ability_scores={
            "strength": 8,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 8,
            "charisma": 8,
        },
        challenge_rating=0.25,
    )


@pytest.fixture
def immune_monster():
    """建立一個對毒免疫的怪物（如不死族）。"""
    return Monster(
        name="Skeleton",
        size="Medium",
        monster_type="undead",
        alignment="lawful evil",
        armor_class=13,
        hit_points=13,
        max_hit_points=13,
        speed=30,
        ability_scores={
            "strength": 10,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 6,
            "wisdom": 8,
            "charisma": 5,
        },
        challenge_rating=0.25,
        condition_immunities=[Condition.POISONED, Condition.EXHAUSTION],
    )


# ---------------------------------------------------------------------------
# TestApplyCondition
# ---------------------------------------------------------------------------


class TestApplyCondition:
    """apply_condition 基礎功能。"""

    def test_apply_basic(self, fighter):
        ac = apply_condition(fighter, Condition.PRONE)
        assert ac is not None
        assert ac.condition == Condition.PRONE
        assert fighter.has_condition(Condition.PRONE)

    def test_apply_with_duration(self, fighter):
        ac = apply_condition(fighter, Condition.BLINDED, remaining_rounds=3)
        assert ac is not None
        assert ac.remaining_rounds == 3

    def test_apply_with_source(self, fighter):
        ac = apply_condition(
            fighter, Condition.FRIGHTENED, source="dragon_fear", remaining_rounds=2
        )
        assert ac is not None
        assert ac.source == "dragon_fear"

    def test_immune_monster_returns_none(self, immune_monster):
        ac = apply_condition(immune_monster, Condition.POISONED)
        assert ac is None
        assert not immune_monster.has_condition(Condition.POISONED)


# ---------------------------------------------------------------------------
# TestRemoveCondition
# ---------------------------------------------------------------------------


class TestRemoveCondition:
    """remove_condition 移除邏輯。"""

    def test_remove_all(self, fighter):
        apply_condition(fighter, Condition.BLINDED, source="spell_a")
        apply_condition(fighter, Condition.PRONE)
        removed = remove_condition(fighter, Condition.BLINDED)
        assert len(removed) == 1
        assert not fighter.has_condition(Condition.BLINDED)
        assert fighter.has_condition(Condition.PRONE)

    def test_remove_by_source(self, goblin):
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_a")
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_b")
        removed = remove_condition(goblin, Condition.GRAPPLED, source="fighter_a")
        assert len(removed) == 1
        grapples = [ac for ac in goblin.conditions if ac.condition == Condition.GRAPPLED]
        assert len(grapples) == 1
        assert grapples[0].source == "fighter_b"

    def test_remove_nonexistent(self, fighter):
        removed = remove_condition(fighter, Condition.STUNNED)
        assert removed == []


# ---------------------------------------------------------------------------
# TestHasConditionEffect
# ---------------------------------------------------------------------------


class TestHasConditionEffect:
    """has_condition_effect 查詢。"""

    def test_has_condition(self, fighter):
        apply_condition(fighter, Condition.POISONED)
        assert has_condition_effect(fighter, Condition.POISONED)

    def test_not_has_condition(self, fighter):
        assert not has_condition_effect(fighter, Condition.POISONED)

    def test_immune_monster(self, immune_monster):
        apply_condition(immune_monster, Condition.POISONED)
        assert not has_condition_effect(immune_monster, Condition.POISONED)


# ---------------------------------------------------------------------------
# TestGetConditions
# ---------------------------------------------------------------------------


class TestGetConditions:
    """get_conditions 集合查詢。"""

    def test_empty(self, fighter):
        assert get_conditions(fighter) == set()

    def test_multiple(self, fighter):
        apply_condition(fighter, Condition.PRONE)
        apply_condition(fighter, Condition.POISONED)
        conds = get_conditions(fighter)
        assert conds == {Condition.PRONE, Condition.POISONED}


# ---------------------------------------------------------------------------
# TestIncapacitated
# ---------------------------------------------------------------------------


class TestIncapacitated:
    """is_incapacitated / can_take_action 判定。"""

    def test_not_incapacitated(self, fighter):
        assert not is_incapacitated(fighter)
        assert can_take_action(fighter)

    def test_stunned_is_incapacitated(self, fighter):
        apply_condition(fighter, Condition.STUNNED)
        assert is_incapacitated(fighter)
        assert not can_take_action(fighter)

    def test_paralyzed_is_incapacitated(self, fighter):
        apply_condition(fighter, Condition.PARALYZED)
        assert is_incapacitated(fighter)

    def test_prone_not_incapacitated(self, fighter):
        apply_condition(fighter, Condition.PRONE)
        assert not is_incapacitated(fighter)
        assert can_take_action(fighter)


# ---------------------------------------------------------------------------
# TestExhaustionPenalty
# ---------------------------------------------------------------------------


class TestExhaustionPenalty:
    """2024 版力竭懲罰計算。"""

    def test_zero(self):
        assert exhaustion_penalty(0) == 0

    def test_level_3(self):
        assert exhaustion_penalty(3) == -6

    def test_level_6(self):
        assert exhaustion_penalty(6) == -12


# ---------------------------------------------------------------------------
# TestTickConditions
# ---------------------------------------------------------------------------


class TestTickConditions:
    """回合計時器測試。"""

    def test_start_of_turn_no_op(self, fighter):
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=2)
        expired = tick_conditions_start_of_turn(fighter)
        assert expired == []
        assert fighter.has_condition(Condition.BLINDED)

    def test_end_of_turn_decrement(self, fighter):
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=3)
        expired = tick_conditions_end_of_turn(fighter)
        assert expired == []
        ac = fighter.conditions[0]
        assert ac.remaining_rounds == 2

    def test_end_of_turn_expire(self, fighter):
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=1)
        expired = tick_conditions_end_of_turn(fighter)
        assert len(expired) == 1
        assert expired[0].condition == Condition.BLINDED
        assert not fighter.has_condition(Condition.BLINDED)

    def test_permanent_not_expired(self, fighter):
        apply_condition(fighter, Condition.PRONE)
        expired = tick_conditions_end_of_turn(fighter)
        assert expired == []
        assert fighter.has_condition(Condition.PRONE)

    def test_multiple_conditions_tick(self, fighter):
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=1)
        apply_condition(fighter, Condition.POISONED, remaining_rounds=3)
        apply_condition(fighter, Condition.PRONE)
        expired = tick_conditions_end_of_turn(fighter)
        assert len(expired) == 1
        assert expired[0].condition == Condition.BLINDED
        assert not fighter.has_condition(Condition.BLINDED)
        assert fighter.has_condition(Condition.POISONED)
        assert fighter.has_condition(Condition.PRONE)


# ---------------------------------------------------------------------------
# TestStackingRules
# ---------------------------------------------------------------------------


class TestStackingRules:
    """堆疊規則：不堆疊、同源堆疊、力竭累加。"""

    def test_non_stackable_overwrites(self, fighter):
        """不堆疊狀態：新的覆蓋舊的，取較長持續時間。"""
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=2)
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=5)
        blinds = [ac for ac in fighter.conditions if ac.condition == Condition.BLINDED]
        assert len(blinds) == 1
        assert blinds[0].remaining_rounds == 5

    def test_non_stackable_keeps_longer(self, fighter):
        """不堆疊：新的較短時，保留較長的持續時間。"""
        apply_condition(fighter, Condition.POISONED, remaining_rounds=5)
        apply_condition(fighter, Condition.POISONED, remaining_rounds=2)
        poisons = [ac for ac in fighter.conditions if ac.condition == Condition.POISONED]
        assert len(poisons) == 1
        assert poisons[0].remaining_rounds == 5

    def test_non_stackable_permanent_wins(self, fighter):
        """不堆疊：None（永久）永遠最長。"""
        apply_condition(fighter, Condition.BLINDED, remaining_rounds=10)
        apply_condition(fighter, Condition.BLINDED)
        blinds = [ac for ac in fighter.conditions if ac.condition == Condition.BLINDED]
        assert len(blinds) == 1
        assert blinds[0].remaining_rounds is None

    def test_source_stacking_different_sources(self, goblin):
        """同源堆疊：不同來源可並存。"""
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_a")
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_b")
        grapples = [ac for ac in goblin.conditions if ac.condition == Condition.GRAPPLED]
        assert len(grapples) == 2

    def test_source_stacking_same_source_overwrites(self, goblin):
        """同源堆疊：相同來源覆蓋（取較長持續時間）。"""
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_a", remaining_rounds=2)
        apply_condition(goblin, Condition.GRAPPLED, source="fighter_a", remaining_rounds=5)
        grapples = [ac for ac in goblin.conditions if ac.condition == Condition.GRAPPLED]
        assert len(grapples) == 1
        assert grapples[0].remaining_rounds == 5

    def test_exhaustion_accumulates(self, fighter):
        """力竭累加等級。"""
        apply_condition(fighter, Condition.EXHAUSTION, exhaustion_level=1)
        apply_condition(fighter, Condition.EXHAUSTION, exhaustion_level=2)
        assert fighter.exhaustion_level == 3
        exh = [ac for ac in fighter.conditions if ac.condition == Condition.EXHAUSTION]
        assert len(exh) == 1
        assert exh[0].exhaustion_level == 3

    def test_exhaustion_cap_at_6(self, fighter):
        """力竭上限 6 級。"""
        apply_condition(fighter, Condition.EXHAUSTION, exhaustion_level=4)
        apply_condition(fighter, Condition.EXHAUSTION, exhaustion_level=4)
        assert fighter.exhaustion_level == 6


# ---------------------------------------------------------------------------
# TestCombatIntegration
# ---------------------------------------------------------------------------


class TestCombatIntegration:
    """確認 combat.py 匯入 conditions.py 的函式仍正常。"""

    def test_combat_imports(self):
        """combat.py 應能成功匯入 can_take_action 和 exhaustion_penalty。"""
        from tot.gremlins.bone_engine.combat import check_incapacitated_effects

        assert callable(check_incapacitated_effects)

    def test_combat_can_take_action(self, fighter):
        """combat.py 使用 conditions.can_take_action 應正常運作。"""
        from tot.gremlins.bone_engine.combat import (
            can_take_action as combat_cta,
        )

        assert combat_cta(fighter)
        apply_condition(fighter, Condition.STUNNED)
        assert not combat_cta(fighter)
