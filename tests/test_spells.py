"""spells.py 單元測試——法術載入、施法檢查、效果執行、專注管理。"""

from __future__ import annotations

import random

import pytest

from tot.gremlins.bone_engine.spells import (
    CastError,
    can_cast,
    cast_spell,
    get_spell_by_name,
    is_concentrating,
    list_spells,
    load_spell_db,
    start_concentration,
)
from tot.models import (
    AbilityScores,
    Character,
    Condition,
    Monster,
    SpellSlots,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def wizard():
    """有法術欄位的法師角色。"""
    return Character(
        name="TestWizard",
        char_class="Wizard",
        hp_max=8,
        hp_current=8,
        spell_dc=13,
        spell_attack=5,
        proficiency_bonus=2,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3},
            current_slots={1: 4, 2: 3},
        ),
        spells_known=["火焰箭", "魔法飛彈", "燃燒之手", "護盾術", "睡眠術"],
    )


@pytest.fixture
def cleric():
    """有治療法術的牧師角色。"""
    return Character(
        name="TestCleric",
        char_class="Cleric",
        hp_max=10,
        hp_current=10,
        spell_dc=14,
        spell_attack=6,
        proficiency_bonus=2,
        spell_slots=SpellSlots(
            max_slots={1: 4},
            current_slots={1: 4},
        ),
        spells_known=["療傷術", "治療之言", "指引之箭", "神聖火焰"],
    )


@pytest.fixture
def goblin():
    """測試用哥布林。"""
    return Monster(
        name="Goblin",
        size="Small",
        creature_type="Humanoid",
        ac=15,
        hp_current=7,
        hp_max=7,
        speed=9,
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=10,
            intelligence=10,
            wisdom=8,
            charisma=8,
        ),
        challenge_rating=0.25,
    )


@pytest.fixture
def wounded_wizard():
    """受傷的法師（用於測試治療）。"""
    return Character(
        name="WoundedWizard",
        char_class="Wizard",
        hp_max=20,
        hp_current=5,
        spell_dc=13,
        spell_attack=5,
        proficiency_bonus=2,
        spell_slots=SpellSlots(
            max_slots={1: 4},
            current_slots={1: 4},
        ),
        spells_known=["療傷術"],
    )


@pytest.fixture
def seeded_rng():
    """固定種子的 RNG，確保測試可重複。"""
    return random.Random(42)


# ---------------------------------------------------------------------------
# TestLoadSpellDB
# ---------------------------------------------------------------------------


class TestLoadSpellDB:
    """法術資料庫載入。"""

    def test_load_returns_dict(self):
        db = load_spell_db()
        assert isinstance(db, dict)
        assert len(db) >= 20

    def test_spell_has_chinese_name(self):
        db = load_spell_db()
        assert "火焰箭" in db

    def test_spell_has_en_name(self):
        db = load_spell_db()
        spell = db["火焰箭"]
        assert spell.en_name == "Fire Bolt"

    def test_cantrips_level_zero(self):
        cantrips = list_spells(level=0)
        assert all(s.level == 0 for s in cantrips)
        assert len(cantrips) >= 10

    def test_list_by_class(self):
        cleric_spells = list_spells(char_class="Cleric")
        assert any(s.name == "神聖火焰" for s in cleric_spells)
        assert all("Cleric" in s.classes for s in cleric_spells)


class TestGetSpellByName:
    """法術名稱查詢。"""

    def test_chinese_name(self):
        spell = get_spell_by_name("火焰箭")
        assert spell is not None
        assert spell.en_name == "Fire Bolt"

    def test_english_name(self):
        spell = get_spell_by_name("Fire Bolt")
        assert spell is not None
        assert spell.name == "火焰箭"

    def test_case_insensitive(self):
        spell = get_spell_by_name("fire bolt")
        assert spell is not None

    def test_not_found(self):
        assert get_spell_by_name("不存在的法術") is None


# ---------------------------------------------------------------------------
# TestCanCast
# ---------------------------------------------------------------------------


class TestCanCast:
    """施法前置檢查。"""

    def test_cantrip_always_castable(self, wizard):
        spell = get_spell_by_name("火焰箭")
        assert can_cast(wizard, spell) is None

    def test_has_slot(self, wizard):
        spell = get_spell_by_name("魔法飛彈")
        assert can_cast(wizard, spell, slot_level=1) is None

    def test_no_slot(self, wizard):
        wizard.spell_slots.current_slots[1] = 0
        spell = get_spell_by_name("魔法飛彈")
        error = can_cast(wizard, spell, slot_level=1)
        assert isinstance(error, CastError)
        assert "欄位" in error.reason

    def test_slot_too_low(self, wizard):
        spell = get_spell_by_name("魔法飛彈")
        # 不存在的 0 環位（非戲法不能用 0 環位）
        error = can_cast(wizard, spell, slot_level=0)
        assert isinstance(error, CastError)

    def test_unknown_spell(self, wizard):
        spell = get_spell_by_name("療傷術")
        # wizard 的 spells_known 裡沒有療傷術
        error = can_cast(wizard, spell, slot_level=1)
        assert isinstance(error, CastError)
        assert "未在已知" in error.reason


# ---------------------------------------------------------------------------
# TestCastDamageSpell
# ---------------------------------------------------------------------------


class TestCastDamageSpell:
    """傷害法術效果執行。"""

    def test_cantrip_attack_hit(self, wizard, goblin, seeded_rng):
        spell = get_spell_by_name("火焰箭")
        result = cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert result.success
        assert result.slot_used == 0  # 戲法不消耗欄位
        assert result.message  # 有訊息

    def test_cantrip_no_slot_consumed(self, wizard, goblin, seeded_rng):
        spell = get_spell_by_name("火焰箭")
        slots_before = wizard.spell_slots.current_slots.get(1, 0)
        cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert wizard.spell_slots.current_slots.get(1, 0) == slots_before

    def test_level1_consumes_slot(self, wizard, goblin, seeded_rng):
        spell = get_spell_by_name("魔法飛彈")
        slots_before = wizard.spell_slots.current_slots[1]
        cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert wizard.spell_slots.current_slots[1] == slots_before - 1

    def test_magic_missile_auto_hit(self, wizard, goblin, seeded_rng):
        """魔法飛彈自動命中，一定造成傷害。"""
        spell = get_spell_by_name("魔法飛彈")
        hp_before = goblin.hp_current
        result = cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert result.success
        assert result.damage_dealt > 0
        assert goblin.hp_current < hp_before

    def test_save_spell_damage(self, wizard, goblin, seeded_rng):
        """豁免型傷害法術（燃燒之手）。"""
        spell = get_spell_by_name("燃燒之手")
        result = cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert result.success
        assert result.slot_used == 1

    def test_no_target_returns_error(self, wizard, seeded_rng):
        spell = get_spell_by_name("火焰箭")
        result = cast_spell(wizard, spell, None, rng=seeded_rng)
        assert not result.success
        assert "目標" in result.message

    def test_attack_spell_with_condition(self, wizard, goblin, seeded_rng):
        """疫病射線命中時附加中毒狀態。"""
        spell = get_spell_by_name("疫病射線")
        wizard.spells_known.append("疫病射線")
        # 用多個種子嘗試直到命中
        for seed in range(100):
            rng = random.Random(seed)
            goblin.hp_current = goblin.hp_max
            goblin.conditions = []
            result = cast_spell(wizard, spell, goblin, rng=rng)
            if result.damage_dealt > 0:
                assert result.condition_applied is not None
                assert goblin.has_condition(Condition.POISONED)
                break


# ---------------------------------------------------------------------------
# TestCastHealingSpell
# ---------------------------------------------------------------------------


class TestCastHealingSpell:
    """治療法術效果執行。"""

    def test_cure_wounds(self, cleric, wounded_wizard, seeded_rng):
        spell = get_spell_by_name("療傷術")
        hp_before = wounded_wizard.hp_current
        result = cast_spell(cleric, spell, wounded_wizard, rng=seeded_rng)
        assert result.success
        assert result.healing_done > 0
        assert wounded_wizard.hp_current > hp_before
        assert wounded_wizard.hp_current <= wounded_wizard.hp_max

    def test_healing_word(self, cleric, wounded_wizard, seeded_rng):
        spell = get_spell_by_name("治療之言")
        result = cast_spell(cleric, spell, wounded_wizard, rng=seeded_rng)
        assert result.success
        assert result.healing_done > 0

    def test_heal_capped_at_max(self, cleric, seeded_rng):
        """治療不超過最大 HP。"""
        target = Character(
            name="AlmostFull",
            hp_max=20,
            hp_current=19,
            spell_slots=SpellSlots(max_slots={1: 1}, current_slots={1: 1}),
        )
        spell = get_spell_by_name("療傷術")
        result = cast_spell(cleric, spell, target, rng=seeded_rng)
        assert target.hp_current == 20
        assert result.healing_done == 1


# ---------------------------------------------------------------------------
# TestCastConditionSpell
# ---------------------------------------------------------------------------


class TestCastConditionSpell:
    """狀態法術效果執行。"""

    def test_sleep_applies_unconscious(self, wizard, goblin):
        """睡眠術——豁免失敗時施加昏迷。"""
        spell = get_spell_by_name("睡眠術")
        # 用低骰子確保哥布林豁免失敗（WIS -1）
        for seed in range(100):
            rng = random.Random(seed)
            goblin.conditions = []
            result = cast_spell(wizard, spell, goblin, rng=rng)
            if not result.save_passed:
                assert result.condition_applied is not None
                assert goblin.has_condition(Condition.UNCONSCIOUS)
                break

    def test_condition_spell_needs_target(self, wizard, seeded_rng):
        spell = get_spell_by_name("睡眠術")
        result = cast_spell(wizard, spell, None, rng=seeded_rng)
        assert not result.success


# ---------------------------------------------------------------------------
# TestConcentration
# ---------------------------------------------------------------------------


class TestConcentration:
    """專注管理。"""

    def test_concentration_spell_sets_field(self, wizard, goblin, seeded_rng):
        spell = get_spell_by_name("睡眠術")
        assert not is_concentrating(wizard)
        cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert is_concentrating(wizard)
        assert wizard.concentration_spell == "睡眠術"

    def test_new_concentration_breaks_old(self, wizard, goblin, seeded_rng):
        """施放新專注法術會中斷舊的。"""
        sleep = get_spell_by_name("睡眠術")
        cast_spell(wizard, spell=sleep, target=goblin, rng=seeded_rng)
        assert wizard.concentration_spell == "睡眠術"

        # 施放另一個專注法術（劍刃護身）
        wizard.spells_known.append("劍刃護身")
        blade_ward = get_spell_by_name("劍刃護身")
        result = cast_spell(wizard, blade_ward, rng=seeded_rng)
        assert wizard.concentration_spell == "劍刃護身"
        assert result.concentration_broken == "睡眠術"

    def test_non_concentration_doesnt_break(self, wizard, goblin, seeded_rng):
        """非專注法術不影響現有專注。"""
        sleep = get_spell_by_name("睡眠術")
        cast_spell(wizard, spell=sleep, target=goblin, rng=seeded_rng)

        mm = get_spell_by_name("魔法飛彈")
        cast_spell(wizard, mm, goblin, rng=seeded_rng)
        assert wizard.concentration_spell == "睡眠術"

    def test_start_concentration_api(self, wizard):
        old = start_concentration(wizard, "祝福術")
        assert old is None
        assert wizard.concentration_spell == "祝福術"

        old = start_concentration(wizard, "睡眠術")
        assert old == "祝福術"
        assert wizard.concentration_spell == "睡眠術"


# ---------------------------------------------------------------------------
# TestUpcast
# ---------------------------------------------------------------------------


class TestUpcast:
    """升環施法。"""

    def test_upcast_consumes_higher_slot(self, wizard, goblin, seeded_rng):
        """用 2 環位施放 1 環法術，消耗 2 環欄位。"""
        spell = get_spell_by_name("魔法飛彈")
        slots_1_before = wizard.spell_slots.current_slots[1]
        slots_2_before = wizard.spell_slots.current_slots[2]
        cast_spell(wizard, spell, goblin, slot_level=2, rng=seeded_rng)
        assert wizard.spell_slots.current_slots[1] == slots_1_before
        assert wizard.spell_slots.current_slots[2] == slots_2_before - 1

    def test_upcast_healing_stronger(self, cleric, seeded_rng):
        """升環治療骰數更多。"""
        spell = get_spell_by_name("療傷術")
        target1 = Character(name="T1", hp_max=50, hp_current=1)
        target2 = Character(name="T2", hp_max=50, hp_current=1)
        # 用相同種子比較 1 環 vs 2 環
        cleric.spell_slots.max_slots[2] = 3
        cleric.spell_slots.current_slots[2] = 3
        r1 = cast_spell(cleric, spell, target1, slot_level=1, rng=random.Random(42))
        r2 = cast_spell(cleric, spell, target2, slot_level=2, rng=random.Random(42))
        # 2 環應該治療更多（2d8 vs 4d8）
        assert r2.healing_done >= r1.healing_done


# ---------------------------------------------------------------------------
# TestCastFailure
# ---------------------------------------------------------------------------


class TestCastFailure:
    """施法失敗場景。"""

    def test_no_slots_left(self, wizard, goblin, seeded_rng):
        wizard.spell_slots.current_slots[1] = 0
        spell = get_spell_by_name("魔法飛彈")
        result = cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert not result.success
        assert "欄位" in result.message

    def test_spell_not_known(self, wizard, goblin, seeded_rng):
        spell = get_spell_by_name("療傷術")
        result = cast_spell(wizard, spell, goblin, rng=seeded_rng)
        assert not result.success
        assert "未在已知" in result.message
