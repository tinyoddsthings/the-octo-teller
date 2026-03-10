"""spells.py 單元測試——法術載入、施法檢查、效果執行、專注管理。"""

from __future__ import annotations

import random

import pytest

from tot.gremlins.bone_engine.conditions import apply_condition
from tot.gremlins.bone_engine.spells import (
    CastError,
    can_cast,
    cast_spell,
    get_max_targets,
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
    Item,
    Monster,
    Spell,
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
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_known=[
            "火焰箭",
            "魔法飛彈",
            "燃燒之手",
            "護盾術",
            "睡眠術",
            "定身術",
            "粉碎音波",
            "目盲/耳聾術",
            "迷蹤步",
            "反制法術",
            "火球術",
        ],
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


# ---------------------------------------------------------------------------
# TestComponents（成分檢查）
# ---------------------------------------------------------------------------


class TestComponents:
    """法術成分系統。"""

    def test_spell_has_components(self):
        """確認 JSON 載入後法術有 components。"""
        db = load_spell_db()
        fire_bolt = db["火焰箭"]
        assert fire_bolt.components == ["V", "S"]
        bless = db["祝福術"]
        assert "M" in bless.components

    def test_silenced_blocks_verbal(self, wizard, goblin):
        """被沉默 → V 法術不可施放。"""
        apply_condition(wizard, Condition.SILENCED, source="Silence")
        spell = get_spell_by_name("火焰箭")  # V, S
        error = can_cast(wizard, spell)
        assert isinstance(error, CastError)
        assert "沉默" in error.reason

    def test_silenced_allows_no_verbal(self, wizard):
        """被沉默 → 無 V 成分法術仍可施放。"""
        apply_condition(wizard, Condition.SILENCED, source="Silence")
        # 冰刃術只有 S, M（無 V）
        spell = get_spell_by_name("冰刃術")
        wizard.spells_known.append("冰刃術")
        error = can_cast(wizard, spell, slot_level=1)
        assert error is None

    def test_incapacitated_blocks_somatic(self, wizard):
        """被無力化 → S 法術不可施放。"""
        apply_condition(wizard, Condition.STUNNED, source="Hold Person")
        spell = get_spell_by_name("火焰箭")  # V, S
        error = can_cast(wizard, spell)
        assert isinstance(error, CastError)
        assert "無力化" in error.reason

    def test_material_cost_check(self, wizard):
        """有金額材料但背包沒有 → 不可施放。"""
        spell = get_spell_by_name("繽紛寶珠")  # M: 價值 50gp 的鑽石
        wizard.spells_known.append("繽紛寶珠")
        error = can_cast(wizard, spell, slot_level=1)
        assert isinstance(error, CastError)
        assert "材料" in error.reason

    def test_material_cost_with_item(self, wizard, goblin, seeded_rng):
        """有金額材料且背包有 → 可施放。"""
        spell = get_spell_by_name("繽紛寶珠")
        wizard.spells_known.append("繽紛寶珠")
        wizard.inventory.append(Item(name="價值 50gp 的鑽石"))
        error = can_cast(wizard, spell, slot_level=1)
        assert error is None

    def test_material_no_cost_always_ok(self, wizard):
        """無金額材料 → 不檢查背包。"""
        spell = get_spell_by_name("祝福術")  # M: 一滴聖水（cost=0）
        wizard.spells_known.append("祝福術")
        # 背包空的也可以（0 cost 可用法器替代）
        error = can_cast(wizard, spell, slot_level=1)
        assert error is None


# ---------------------------------------------------------------------------
# TestUpcastAdvanced（進階升環）
# ---------------------------------------------------------------------------


class TestUpcastAdvanced:
    """進階升環機制。"""

    def test_upcast_no_concentration(self, wizard, goblin, seeded_rng):
        """達到指定環數後不觸發專注。"""
        # 建立一個有 upcast_no_concentration_at 的測試法術
        spell = Spell(
            name="測試專注法術",
            level=1,
            school="Enchantment",
            concentration=True,
            effect_type="buff",
            components=["V", "S"],
            upcast_no_concentration_at=3,
        )
        wizard.spells_known.append("測試專注法術")
        wizard.spell_slots.max_slots[3] = 2
        wizard.spell_slots.current_slots[3] = 2

        # 用 3 環施放 → 不需專注
        result = cast_spell(wizard, spell, slot_level=3, rng=seeded_rng)
        assert result.success
        assert not result.concentration_started
        assert wizard.concentration_spell is None

    def test_upcast_below_threshold_still_concentrates(self, wizard, goblin, seeded_rng):
        """低於閾值仍需專注。"""
        spell = Spell(
            name="測試專注法術2",
            level=1,
            school="Enchantment",
            concentration=True,
            effect_type="buff",
            components=["V", "S"],
            upcast_no_concentration_at=3,
        )
        wizard.spells_known.append("測試專注法術2")

        # 用 1 環施放 → 仍需專注
        result = cast_spell(wizard, spell, slot_level=1, rng=seeded_rng)
        assert result.success
        assert result.concentration_started
        assert wizard.concentration_spell == "測試專注法術2"

    def test_get_max_targets_base(self):
        """無升環時回傳基本目標數。"""
        spell = get_spell_by_name("祝福術")
        assert get_max_targets(spell, 1) == 3

    def test_get_max_targets_upcast(self):
        """升環增加目標數。"""
        spell = get_spell_by_name("祝福術")  # base 3, +1 per level
        assert get_max_targets(spell, 2) == 4
        assert get_max_targets(spell, 3) == 5

    def test_get_max_targets_cantrip_no_upcast(self):
        """戲法不會因升環增加目標。"""
        spell = Spell(
            name="測試戲法",
            level=0,
            school="Evocation",
            max_targets=2,
            upcast_additional_targets=1,
        )
        # 戲法 level=0，不適用升環目標增加
        assert get_max_targets(spell, 0) == 2


# ---------------------------------------------------------------------------
# TestHighLevelSpells（高環法術）
# ---------------------------------------------------------------------------


class TestHighLevelSpells:
    """2-3 環法術載入、施放與升環。"""

    def test_new_spells_loaded(self):
        """確認新增的高環法術都載入成功。"""
        db = load_spell_db()
        for name in ["定身術", "粉碎音波", "目盲/耳聾術", "迷蹤步", "反制法術", "火球術"]:
            assert name in db, f"{name} 未載入"
        assert len(db) >= 36  # 30 + 6

    def test_fireball_base_damage(self, wizard, goblin, seeded_rng):
        """火球術 3 環 8d6 傷害。"""
        spell = get_spell_by_name("火球術")
        assert spell.level == 3
        assert spell.damage_dice == "8d6"
        result = cast_spell(wizard, spell, goblin, slot_level=3, rng=seeded_rng)
        assert result.success
        assert result.slot_used == 3

    def test_fireball_upcast_damage(self, wizard, seeded_rng):
        """火球術升環：用 3 環 vs 用更高環的骰子數比較。"""
        spell = get_spell_by_name("火球術")
        # 建一個大 HP 目標，避免死亡影響結果
        target_3 = Monster(name="T1", hp_max=200, hp_current=200, ac=1)
        target_4 = Monster(name="T2", hp_max=200, hp_current=200, ac=1)

        wizard.spell_slots.max_slots[4] = 1
        wizard.spell_slots.current_slots[4] = 1

        r3 = cast_spell(wizard, spell, target_3, slot_level=3, rng=random.Random(99))
        r4 = cast_spell(wizard, spell, target_4, slot_level=4, rng=random.Random(99))
        # 4 環應該傷害 >= 3 環（8d6 vs 9d6，同 seed）
        assert r4.damage_dealt >= r3.damage_dealt

    def test_hold_person_paralyzed(self, wizard, goblin):
        """定身術豁免失敗時施加麻痺。"""
        spell = get_spell_by_name("定身術")
        for seed in range(100):
            rng = random.Random(seed)
            goblin.conditions = []
            goblin.hp_current = goblin.hp_max
            result = cast_spell(wizard, spell, goblin, slot_level=2, rng=rng)
            if not result.save_passed:
                assert goblin.has_condition(Condition.PARALYZED)
                break

    def test_hold_person_upcast_targets(self):
        """定身術升環增加目標數：2環=1, 3環=2, 4環=3。"""
        spell = get_spell_by_name("定身術")
        assert get_max_targets(spell, 2) == 1
        assert get_max_targets(spell, 3) == 2
        assert get_max_targets(spell, 4) == 3

    def test_shatter_save_half(self, wizard, seeded_rng):
        """粉碎音波豁免成功時半傷。"""
        spell = get_spell_by_name("粉碎音波")
        # 用高 CON 目標確保有機會通過豁免
        tough = Monster(
            name="Iron Golem",
            hp_max=100,
            hp_current=100,
            ac=20,
            ability_scores=AbilityScores(CON=20),
        )
        for seed in range(100):
            rng = random.Random(seed)
            tough.hp_current = tough.hp_max
            result = cast_spell(wizard, spell, tough, slot_level=2, rng=rng)
            if result.save_passed:
                assert result.damage_dealt > 0  # 半傷仍造成傷害
                assert "半傷" in result.message
                break

    def test_blindness_deafness_no_concentration(self, wizard, goblin):
        """目盲/耳聾術不需專注。"""
        spell = get_spell_by_name("目盲/耳聾術")
        assert not spell.concentration
        # 先維持一個專注法術
        wizard.concentration_spell = "睡眠術"
        for seed in range(100):
            rng = random.Random(seed)
            goblin.conditions = []
            result = cast_spell(wizard, spell, goblin, slot_level=2, rng=rng)
            if not result.save_passed:
                # 專注法術應該沒有被中斷
                assert wizard.concentration_spell == "睡眠術"
                assert not result.concentration_started
                break

    def test_blindness_deafness_upcast_targets(self):
        """目盲/耳聾術升環增加目標數。"""
        spell = get_spell_by_name("目盲/耳聾術")
        assert get_max_targets(spell, 2) == 1
        assert get_max_targets(spell, 3) == 2

    def test_misty_step_v_only(self, wizard, seeded_rng):
        """迷蹤步只需 V，被沉默時不可用。"""
        spell = get_spell_by_name("迷蹤步")
        assert spell.components == ["V"]

        # 正常施放 OK
        result = cast_spell(wizard, spell, slot_level=2, rng=seeded_rng)
        assert result.success

        # 被沉默後不可用
        from tot.gremlins.bone_engine.conditions import apply_condition

        apply_condition(wizard, Condition.SILENCED, source="Silence")
        error = can_cast(wizard, spell, slot_level=2)
        assert isinstance(error, CastError)
        assert "沉默" in error.reason

    def test_counterspell_s_only_immune_to_silence(self, wizard, seeded_rng):
        """反制法術只需 S，被沉默時仍可施放。"""
        spell = get_spell_by_name("反制法術")
        assert spell.components == ["S"]

        from tot.gremlins.bone_engine.conditions import apply_condition

        apply_condition(wizard, Condition.SILENCED, source="Silence")
        # S-only 法術不受沉默影響
        error = can_cast(wizard, spell, slot_level=3)
        assert error is None

    def test_counterspell_blocked_by_incapacitated(self, wizard):
        """反制法術有 S，被無力化時不可施放。"""
        spell = get_spell_by_name("反制法術")
        from tot.gremlins.bone_engine.conditions import apply_condition

        apply_condition(wizard, Condition.STUNNED, source="Stun")
        error = can_cast(wizard, spell, slot_level=3)
        assert isinstance(error, CastError)
        assert "無力化" in error.reason
