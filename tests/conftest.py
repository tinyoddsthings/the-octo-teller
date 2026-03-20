"""共用測試 fixtures——標準角色、怪物、地圖。

各測試檔案仍可定義自己的 fixture 覆蓋這裡的。
名稱加 `std_` 前綴，避免與既有的本地 fixture 衝突。
"""

from __future__ import annotations

import random

import pytest

from tot.models import (
    Ability,
    AbilityScores,
    Character,
    Condition,
    DamageType,
    Monster,
    Size,
    Skill,
    SpellSlots,
    Weapon,
    WeaponProperty,
)

# ---------------------------------------------------------------------------
# 隨機數產生器
# ---------------------------------------------------------------------------


@pytest.fixture
def rng42():
    """固定種子 42 的 RNG。"""
    return random.Random(42)


# ---------------------------------------------------------------------------
# 標準角色
# ---------------------------------------------------------------------------


@pytest.fixture
def std_fighter():
    """5 級戰士——高 HP、重甲、長劍+盾。"""
    return Character(
        name="Aldric",
        class_levels={"Fighter": 5},
        background="Soldier",
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        hit_dice_remaining={10: 5},
        ac=18,  # 鏈甲(16) + 盾(2)
        speed=9,
        skill_proficiencies=[Skill.ATHLETICS, Skill.PERCEPTION],
        saving_throw_proficiencies=[Ability.STR, Ability.CON],
        weapons=[
            Weapon(
                name="長劍",
                damage_dice="1d8",
                damage_type=DamageType.SLASHING,
                properties=[WeaponProperty.VERSATILE],
                is_martial=True,
            ),
        ],
    )


@pytest.fixture
def std_wizard():
    """5 級法師——法術欄位 1~3 環、已知法術。"""
    return Character(
        name="Elara",
        class_levels={"Wizard": 5},
        ability_scores=AbilityScores(STR=8, DEX=14, CON=12, INT=18, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=27,
        hp_current=27,
        hit_dice_remaining={6: 5},
        ac=15,  # 法師護甲(13) + DEX(2)
        speed=9,
        spell_dc=15,
        spell_attack=7,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_known=[
            "火焰箭",
            "魔法飛彈",
            "護盾術",
            "燃燒之手",
            "迷蹤步",
            "粉碎音波",
            "火球術",
            "反制法術",
        ],
        skill_proficiencies=[Skill.ARCANA, Skill.INVESTIGATION],
        saving_throw_proficiencies=[Ability.INT, Ability.WIS],
    )


@pytest.fixture
def std_cleric():
    """5 級牧師——治療 + 法術、中甲+盾。"""
    return Character(
        name="Branwen",
        class_levels={"Cleric": 5},
        ability_scores=AbilityScores(STR=14, DEX=10, CON=14, INT=10, WIS=18, CHA=12),
        proficiency_bonus=3,
        hp_max=38,
        hp_current=38,
        hit_dice_remaining={8: 5},
        ac=18,  # 半身甲(15+0) + 盾(2) + ... 近似
        speed=9,
        spell_dc=15,
        spell_attack=7,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 3, 3: 2},
            current_slots={1: 4, 2: 3, 3: 2},
        ),
        spells_known=[
            "神聖火焰",
            "療傷術",
            "治療之言",
            "指引之箭",
            "祝福術",
            "定身術",
        ],
        skill_proficiencies=[Skill.MEDICINE, Skill.RELIGION],
        saving_throw_proficiencies=[Ability.WIS, Ability.CHA],
    )


# ---------------------------------------------------------------------------
# 標準怪物
# ---------------------------------------------------------------------------


@pytest.fixture
def std_goblin():
    """CR 1/4 哥布林。"""
    return Monster(
        name="哥布林",
        size=Size.SMALL,
        creature_type="Humanoid",
        ac=15,
        hp_max=7,
        hp_current=7,
        speed=9,
        ability_scores=AbilityScores(STR=8, DEX=14, CON=10, INT=10, WIS=8, CHA=8),
        proficiency_bonus=2,
        challenge_rating=0.25,
        xp_reward=50,
    )


@pytest.fixture
def std_skeleton():
    """CR 1/4 骷髏——免疫毒素和力竭。"""
    return Monster(
        name="骷髏",
        size=Size.MEDIUM,
        creature_type="Undead",
        ac=13,
        hp_max=13,
        hp_current=13,
        speed=9,
        ability_scores=AbilityScores(STR=10, DEX=14, CON=15, INT=6, WIS=8, CHA=5),
        proficiency_bonus=2,
        challenge_rating=0.25,
        xp_reward=50,
        damage_immunities=[DamageType.POISON],
        condition_immunities=[Condition.POISONED, Condition.EXHAUSTION],
    )


@pytest.fixture
def std_ogre():
    """CR 2 食人魔——大型、高 HP。"""
    return Monster(
        name="食人魔",
        size=Size.LARGE,
        creature_type="Giant",
        ac=11,
        hp_max=59,
        hp_current=59,
        speed=12,
        ability_scores=AbilityScores(STR=19, DEX=8, CON=16, INT=5, WIS=7, CHA=7),
        proficiency_bonus=2,
        challenge_rating=2,
        xp_reward=450,
    )
