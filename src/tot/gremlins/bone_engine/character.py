"""Bone Engine 角色建立與衍生數值計算。

處理屬性值生成、職業/種族資料查詢，以及所有確定性角色計算
（HP、AC、法術 DC 等）。基於 D&D 2024 (5.5e) 規則。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tot.models import (
    Ability,
    AbilityScores,
    Character,
    Skill,
    SpellSlots,
)

# ---------------------------------------------------------------------------
# 熟練加值對照表（PHB p.15）
# ---------------------------------------------------------------------------


def proficiency_bonus_for_level(level: int) -> int:
    if level < 1:
        raise ValueError(f"等級必須 >= 1，收到 {level}")
    if level <= 4:
        return 2
    if level <= 8:
        return 3
    if level <= 12:
        return 4
    if level <= 16:
        return 5
    return 6  # 17-20


# ---------------------------------------------------------------------------
# 職業資料登錄
# ---------------------------------------------------------------------------


class ClassData:
    """職業的靜態資料。"""

    def __init__(
        self,
        name: str,
        hit_die: int,
        primary_ability: Ability,
        saving_throws: list[Ability],
        skill_choices: list[Skill],
        num_skills: int,
        spellcasting_ability: Ability | None = None,
    ):
        self.name = name
        self.hit_die = hit_die
        self.primary_ability = primary_ability
        self.saving_throws = saving_throws
        self.skill_choices = skill_choices
        self.num_skills = num_skills
        self.spellcasting_ability = spellcasting_ability


CLASS_REGISTRY: dict[str, ClassData] = {
    "Barbarian": ClassData(
        name="Barbarian",
        hit_die=12,
        primary_ability=Ability.STR,
        saving_throws=[Ability.STR, Ability.CON],
        skill_choices=[
            Skill.ANIMAL_HANDLING,
            Skill.ATHLETICS,
            Skill.INTIMIDATION,
            Skill.NATURE,
            Skill.PERCEPTION,
            Skill.SURVIVAL,
        ],
        num_skills=2,
    ),
    "Bard": ClassData(
        name="Bard",
        hit_die=8,
        primary_ability=Ability.CHA,
        saving_throws=[Ability.DEX, Ability.CHA],
        skill_choices=list(Skill),  # 吟遊詩人可選任何技能
        num_skills=3,
        spellcasting_ability=Ability.CHA,
    ),
    "Cleric": ClassData(
        name="Cleric",
        hit_die=8,
        primary_ability=Ability.WIS,
        saving_throws=[Ability.WIS, Ability.CHA],
        skill_choices=[
            Skill.HISTORY,
            Skill.INSIGHT,
            Skill.MEDICINE,
            Skill.PERSUASION,
            Skill.RELIGION,
        ],
        num_skills=2,
        spellcasting_ability=Ability.WIS,
    ),
    "Druid": ClassData(
        name="Druid",
        hit_die=8,
        primary_ability=Ability.WIS,
        saving_throws=[Ability.INT, Ability.WIS],
        skill_choices=[
            Skill.ARCANA,
            Skill.ANIMAL_HANDLING,
            Skill.INSIGHT,
            Skill.MEDICINE,
            Skill.NATURE,
            Skill.PERCEPTION,
            Skill.RELIGION,
            Skill.SURVIVAL,
        ],
        num_skills=2,
        spellcasting_ability=Ability.WIS,
    ),
    "Fighter": ClassData(
        name="Fighter",
        hit_die=10,
        primary_ability=Ability.STR,
        saving_throws=[Ability.STR, Ability.CON],
        skill_choices=[
            Skill.ACROBATICS,
            Skill.ANIMAL_HANDLING,
            Skill.ATHLETICS,
            Skill.HISTORY,
            Skill.INSIGHT,
            Skill.INTIMIDATION,
            Skill.PERSUASION,
            Skill.PERCEPTION,
            Skill.SURVIVAL,
        ],
        num_skills=2,
    ),
    "Monk": ClassData(
        name="Monk",
        hit_die=8,
        primary_ability=Ability.DEX,
        saving_throws=[Ability.STR, Ability.DEX],
        skill_choices=[
            Skill.ACROBATICS,
            Skill.ATHLETICS,
            Skill.HISTORY,
            Skill.INSIGHT,
            Skill.RELIGION,
            Skill.STEALTH,
        ],
        num_skills=2,
    ),
    "Paladin": ClassData(
        name="Paladin",
        hit_die=10,
        primary_ability=Ability.STR,
        saving_throws=[Ability.WIS, Ability.CHA],
        skill_choices=[
            Skill.ATHLETICS,
            Skill.INSIGHT,
            Skill.INTIMIDATION,
            Skill.MEDICINE,
            Skill.PERSUASION,
            Skill.RELIGION,
        ],
        num_skills=2,
        spellcasting_ability=Ability.CHA,
    ),
    "Ranger": ClassData(
        name="Ranger",
        hit_die=10,
        primary_ability=Ability.DEX,
        saving_throws=[Ability.STR, Ability.DEX],
        skill_choices=[
            Skill.ANIMAL_HANDLING,
            Skill.ATHLETICS,
            Skill.INSIGHT,
            Skill.INVESTIGATION,
            Skill.NATURE,
            Skill.PERCEPTION,
            Skill.STEALTH,
            Skill.SURVIVAL,
        ],
        num_skills=3,
        spellcasting_ability=Ability.WIS,
    ),
    "Rogue": ClassData(
        name="Rogue",
        hit_die=8,
        primary_ability=Ability.DEX,
        saving_throws=[Ability.DEX, Ability.INT],
        skill_choices=[
            Skill.ACROBATICS,
            Skill.ATHLETICS,
            Skill.DECEPTION,
            Skill.INSIGHT,
            Skill.INTIMIDATION,
            Skill.INVESTIGATION,
            Skill.PERCEPTION,
            Skill.PERSUASION,
            Skill.SLEIGHT_OF_HAND,
            Skill.STEALTH,
        ],
        num_skills=4,
    ),
    "Sorcerer": ClassData(
        name="Sorcerer",
        hit_die=6,
        primary_ability=Ability.CHA,
        saving_throws=[Ability.CON, Ability.CHA],
        skill_choices=[
            Skill.ARCANA,
            Skill.DECEPTION,
            Skill.INSIGHT,
            Skill.INTIMIDATION,
            Skill.PERSUASION,
            Skill.RELIGION,
        ],
        num_skills=2,
        spellcasting_ability=Ability.CHA,
    ),
    "Warlock": ClassData(
        name="Warlock",
        hit_die=8,
        primary_ability=Ability.CHA,
        saving_throws=[Ability.WIS, Ability.CHA],
        skill_choices=[
            Skill.ARCANA,
            Skill.DECEPTION,
            Skill.HISTORY,
            Skill.INTIMIDATION,
            Skill.INVESTIGATION,
            Skill.NATURE,
            Skill.RELIGION,
        ],
        num_skills=2,
        spellcasting_ability=Ability.CHA,
    ),
    "Wizard": ClassData(
        name="Wizard",
        hit_die=6,
        primary_ability=Ability.INT,
        saving_throws=[Ability.INT, Ability.WIS],
        skill_choices=[
            Skill.ARCANA,
            Skill.HISTORY,
            Skill.INSIGHT,
            Skill.INVESTIGATION,
            Skill.MEDICINE,
            Skill.NATURE,
            Skill.RELIGION,
        ],
        num_skills=2,
        spellcasting_ability=Ability.INT,
    ),
}


# ---------------------------------------------------------------------------
# 屬性值生成
# ---------------------------------------------------------------------------

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

POINT_BUY_COSTS: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}

POINT_BUY_BUDGET = 27


def validate_point_buy(scores: dict[Ability, int]) -> tuple[bool, str]:
    """驗證購點法配置。回傳 (是否合法, 訊息)。"""
    if len(scores) != 6:
        return False, f"必須分配全部 6 項屬性，收到 {len(scores)}"

    total_cost = 0
    for ability, value in scores.items():
        if value not in POINT_BUY_COSTS:
            return False, f"{ability}: {value} 超出購點範圍（8-15）"
        total_cost += POINT_BUY_COSTS[value]

    if total_cost != POINT_BUY_BUDGET:
        return False, f"總點數 {total_cost} != 預算 {POINT_BUY_BUDGET}"

    return True, "OK"


def validate_standard_array(scores: dict[Ability, int]) -> tuple[bool, str]:
    """驗證是否使用標準陣列值。"""
    if len(scores) != 6:
        return False, f"必須分配全部 6 項屬性，收到 {len(scores)}"

    if sorted(scores.values()) != sorted(STANDARD_ARRAY):
        return False, f"數值必須是 {STANDARD_ARRAY}"

    return True, "OK"


def validate_skill_selection(
    selected: list[Skill],
    char_class: str,
    bg_skills: list[Skill] | None = None,
) -> tuple[bool, str]:
    """驗證技能選擇的數量與合法性。

    檢查：
    1. 選擇數量是否等於該職業可選技能數
    2. 每個技能是否在職業可選列表中
    3. 是否與背景技能重複
    """
    if char_class not in CLASS_REGISTRY:
        return False, f"未知職業: {char_class!r}"

    cls = CLASS_REGISTRY[char_class]
    bg_set = set(bg_skills) if bg_skills else set()

    for s in selected:
        if s in bg_set:
            return False, f"技能 {s.value} 已由背景提供，不可重複選擇"
        if s not in cls.skill_choices:
            return False, f"{char_class} 無法選擇技能 {s.value}"

    if len(selected) != cls.num_skills:
        return False, f"{char_class} 應選 {cls.num_skills} 項技能，收到 {len(selected)}"

    return True, "OK"


def validate_spell_selection(
    cantrips: list[str],
    spells: list[str],
    num_cantrips: int,
    num_spells: int,
) -> tuple[bool, str]:
    """驗證戲法/法術選擇的數量。

    Args:
        cantrips: 已選戲法名稱列表。
        spells: 已選 1 環法術名稱列表。
        num_cantrips: 該職業 1 級應選戲法數。
        num_spells: 該職業 1 級應選法術數。
    """
    if num_cantrips > 0 and len(cantrips) != num_cantrips:
        return False, f"應選 {num_cantrips} 個戲法，收到 {len(cantrips)}"
    if num_spells > 0 and len(spells) != num_spells:
        return False, f"應選 {num_spells} 個法術，收到 {len(spells)}"
    return True, "OK"


def apply_background_bonus(
    scores: AbilityScores,
    bonuses: dict[Ability, int],
) -> AbilityScores:
    """套用背景屬性加值（+2/+1 或 +1/+1/+1）。

    驗證總加值為 3 且不超過 20 上限。
    """
    total_bonus = sum(bonuses.values())
    if total_bonus != 3:
        raise ValueError(f"背景加值總和必須為 3，收到 {total_bonus}")

    for ability, bonus in bonuses.items():
        if bonus not in (1, 2):
            raise ValueError(f"每項加值必須是 1 或 2，{ability} 收到 {bonus}")

    data = scores.model_dump()
    for ability, bonus in bonuses.items():
        new_val = data[ability.value] + bonus
        if new_val > 20:
            raise ValueError(f"{ability} 會變成 {new_val}（上限 20）")
        data[ability.value] = new_val

    return AbilityScores(**data)


# ---------------------------------------------------------------------------
# 衍生數值計算
# ---------------------------------------------------------------------------


def compute_hp_at_level(hit_die: int, con_modifier: int, level: int) -> int:
    """計算最大 HP。1 級 = 生命骰最大值 + 體質修正；之後每級 = 平均值 + 體質修正。"""
    if level < 1:
        raise ValueError(f"等級必須 >= 1，收到 {level}")
    # 1 級：最大骰面 + 體質修正
    hp = hit_die + con_modifier
    # 2 級以後：平均擲骰（無條件進位）+ 體質修正 × 每級
    avg_roll = hit_die // 2 + 1  # 例：d8 -> 5, d10 -> 6, d12 -> 7
    hp += (level - 1) * (avg_roll + con_modifier)
    return max(hp, 1)  # 最少 1 HP


def compute_ac(
    dex_modifier: int,
    armor_type: str = "none",
    has_shield: bool = False,
    unarmored_bonus: int = 0,
) -> int:
    """根據護甲類型計算 AC。

    armor_type: "none"、"light"、"medium"、"heavy"、"unarmored_barbarian"、"unarmored_monk"
    unarmored_bonus: 野蠻人的體質修正或武僧的感知修正（無甲防禦用）
    """
    match armor_type:
        case "none":
            base = 10 + dex_modifier
        case "light":
            # 皮甲: 11, 鑲嵌皮甲: 12
            base = 12 + dex_modifier  # 預設鑲嵌皮甲
        case "medium":
            # 鏈衫: 13, 鱗甲: 14, 胸甲: 14, 半身甲: 15
            base = 14 + min(dex_modifier, 2)  # 預設鱗甲，敏捷上限 +2
        case "heavy":
            # 環甲: 14, 鏈甲: 16, 鱗片甲: 17, 全身甲: 18
            base = 16  # 預設鏈甲（1 級）；不加敏捷
        case "unarmored_barbarian":
            base = 10 + dex_modifier + unarmored_bonus  # + 體質修正
        case "unarmored_monk":
            base = 10 + dex_modifier + unarmored_bonus  # + 感知修正
        case _:
            base = 10 + dex_modifier

    if has_shield:
        base += 2

    return base


def compute_spell_dc(proficiency_bonus: int, casting_mod: int) -> int:
    """法術豁免 DC = 8 + 熟練加值 + 施法屬性修正值。"""
    return 8 + proficiency_bonus + casting_mod


def compute_spell_attack(proficiency_bonus: int, casting_mod: int) -> int:
    """法術攻擊加值 = 熟練加值 + 施法屬性修正值。"""
    return proficiency_bonus + casting_mod


# ---------------------------------------------------------------------------
# 法術欄位表（完整施法者、半施法者、術士契約魔法）
# ---------------------------------------------------------------------------

# 完整施法者：吟遊詩人、牧師、德魯伊、術師、法師
FULL_CASTER_SLOTS: dict[int, dict[int, int]] = {
    1: {1: 2},
    2: {1: 3},
    3: {1: 4, 2: 2},
    4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2},
    6: {1: 4, 2: 3, 3: 3},
    7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2},
    9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# 半施法者：聖騎士、遊俠
HALF_CASTER_SLOTS: dict[int, dict[int, int]] = {
    1: {},
    2: {1: 2},
    3: {1: 3},
    4: {1: 3},
    5: {1: 4, 2: 2},
    6: {1: 4, 2: 2},
    7: {1: 4, 2: 3},
    8: {1: 4, 2: 3},
    9: {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
    11: {1: 4, 2: 3, 3: 3},
    12: {1: 4, 2: 3, 3: 3},
    13: {1: 4, 2: 3, 3: 3, 4: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 2},
    16: {1: 4, 2: 3, 3: 3, 4: 2},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# 術士契約魔法：欄位較少但全部在最高環級，短休恢復
WARLOCK_SLOTS: dict[int, tuple[int, int]] = {
    # 等級: (欄位數, 欄位環級)
    1: (1, 1),
    2: (2, 1),
    3: (2, 2),
    4: (2, 2),
    5: (2, 3),
    6: (2, 3),
    7: (2, 4),
    8: (2, 4),
    9: (2, 5),
    10: (2, 5),
    11: (3, 5),
    12: (3, 5),
    13: (3, 5),
    14: (3, 5),
    15: (3, 5),
    16: (3, 5),
    17: (4, 5),
    18: (4, 5),
    19: (4, 5),
    20: (4, 5),
}

FULL_CASTERS = {"Bard", "Cleric", "Druid", "Sorcerer", "Wizard"}
HALF_CASTERS = {"Paladin", "Ranger"}


def get_spell_slots(char_class: str, level: int) -> SpellSlots:
    """依職業與等級取得法術欄位（單一職業）。"""
    if char_class == "Warlock":
        num_slots, slot_level = WARLOCK_SLOTS.get(level, (0, 0))
        if num_slots == 0:
            return SpellSlots()
        slots = {slot_level: num_slots}
        return SpellSlots(max_slots=slots, current_slots=dict(slots))

    if char_class in FULL_CASTERS:
        table = FULL_CASTER_SLOTS
    elif char_class in HALF_CASTERS:
        table = HALF_CASTER_SLOTS
    else:
        return SpellSlots()  # 非施法職業

    slots = table.get(level, {})
    return SpellSlots(max_slots=dict(slots), current_slots=dict(slots))


# ---------------------------------------------------------------------------
# 兼職法術欄位計算（PHB multiclassing rules）
# ---------------------------------------------------------------------------

# 施法者權重（用於兼職有效施法者等級計算）
# 完整 = 1.0，半施法 = 0.5，術士 = 0.0（獨立 Pact Magic），非施法 = 0.0
SPELLCASTING_WEIGHT: dict[str, float] = {
    "Bard": 1.0,
    "Cleric": 1.0,
    "Druid": 1.0,
    "Sorcerer": 1.0,
    "Wizard": 1.0,
    "Paladin": 0.5,
    "Ranger": 0.5,
    "Warlock": 0.0,  # 獨立 Pact Magic
    "Barbarian": 0.0,
    "Fighter": 0.0,
    "Monk": 0.0,
    "Rogue": 0.0,
}

# 1/3 施法者子職業（Fighter: Eldritch Knight, Rogue: Arcane Trickster）
_THIRD_CASTER_SUBCLASSES: dict[str, set[str]] = {
    "Fighter": {"Eldritch Knight"},
    "Rogue": {"Arcane Trickster"},
}


def spellcasting_weight(cls: str, subclass: str = "") -> float:
    """回傳職業的施法者權重（1.0 / 0.5 / 0.333 / 0.0）。"""
    if cls in _THIRD_CASTER_SUBCLASSES and subclass in _THIRD_CASTER_SUBCLASSES[cls]:
        return 1 / 3
    return SPELLCASTING_WEIGHT.get(cls, 0.0)


def compute_multiclass_spell_slots(
    class_levels: dict[str, int],
    subclasses: dict[str, str],
) -> tuple[SpellSlots, SpellSlots]:
    """計算兼職法術欄位。

    回傳 (一般法術欄位, 術士契約欄位)。
    一般欄位：依有效施法者等級查 FULL_CASTER_SLOTS（PHB 兼職表）。
    術士欄位：依術士等級查 WARLOCK_SLOTS（獨立，短休恢復）。
    """
    # 計算有效施法者等級（小數加總後 floor 到整數）
    effective_level_float = 0.0
    warlock_level = 0
    for cls, lvl in class_levels.items():
        sub = subclasses.get(cls, "")
        w = spellcasting_weight(cls, sub)
        if cls == "Warlock":
            warlock_level = lvl
        else:
            effective_level_float += lvl * w

    effective_level = int(effective_level_float)

    # 一般法術欄位
    if effective_level > 0:
        slots = FULL_CASTER_SLOTS.get(effective_level, {})
        normal_slots = SpellSlots(max_slots=dict(slots), current_slots=dict(slots))
    else:
        normal_slots = SpellSlots()

    # 術士契約欄位（獨立）
    if warlock_level > 0:
        num, lvl = WARLOCK_SLOTS.get(warlock_level, (0, 0))
        if num > 0:
            pact = {lvl: num}
            pact_slots = SpellSlots(max_slots=pact, current_slots=dict(pact))
        else:
            pact_slots = SpellSlots()
    else:
        pact_slots = SpellSlots()

    return normal_slots, pact_slots


# ---------------------------------------------------------------------------
# 兼職前置條件（PHB 2024 §Creating a Character p.54）
# ---------------------------------------------------------------------------

# 各職業兼職所需最低屬性（新職業 AND 現有所有職業都要滿足）
MULTICLASS_PREREQS: dict[str, list[tuple[Ability, int]]] = {
    "Barbarian": [(Ability.STR, 13)],
    "Bard": [(Ability.CHA, 13)],
    "Cleric": [(Ability.WIS, 13)],
    "Druid": [(Ability.WIS, 13)],
    "Fighter": [(Ability.STR, 13)],  # 或 DEX 13（Fighter 特例，見下方）
    "Monk": [(Ability.DEX, 13), (Ability.WIS, 13)],
    "Paladin": [(Ability.STR, 13), (Ability.CHA, 13)],
    "Ranger": [(Ability.DEX, 13), (Ability.WIS, 13)],
    "Rogue": [(Ability.DEX, 13)],
    "Sorcerer": [(Ability.CHA, 13)],
    "Warlock": [(Ability.CHA, 13)],
    "Wizard": [(Ability.INT, 13)],
}


def validate_multiclass_prereq(char: Character, new_class: str) -> tuple[bool, str]:
    """驗證兼職前置條件（新職業 + 現有所有職業的屬性需求都要滿足）。

    回傳 (是否可兼職, 錯誤訊息)。
    """
    if new_class not in CLASS_REGISTRY:
        return False, f"未知職業: {new_class!r}"

    def _meets(cls: str) -> tuple[bool, str]:
        reqs = MULTICLASS_PREREQS.get(cls, [])
        # Fighter 特例：STR 13 OR DEX 13 即可
        if cls == "Fighter":
            str_ok = char.ability_scores.score(Ability.STR) >= 13
            dex_ok = char.ability_scores.score(Ability.DEX) >= 13
            if not (str_ok or dex_ok):
                return False, f"{cls} 兼職需要 STR 或 DEX >= 13"
            return True, "OK"
        for ability, minimum in reqs:
            if char.ability_scores.score(ability) < minimum:
                return False, f"{cls} 兼職需要 {ability.value} >= {minimum}"
        return True, "OK"

    # 新職業
    ok, msg = _meets(new_class)
    if not ok:
        return False, msg

    # 現有所有職業
    for existing_cls in char.class_levels:
        ok, msg = _meets(existing_cls)
        if not ok:
            return False, f"現有職業 {existing_cls} 的前置條件不滿足：{msg}"

    return True, "OK"


# ---------------------------------------------------------------------------
# 職業特性資料（CLASS_LEVEL_FEATURES）
# ---------------------------------------------------------------------------

# ASI 等級（各職業預設）
DEFAULT_ASI_LEVELS: frozenset[int] = frozenset({4, 8, 12, 16, 19})
ASI_LEVEL_OVERRIDES: dict[str, frozenset[int]] = {
    "Fighter": frozenset({4, 6, 8, 12, 14, 16, 19}),
    "Rogue": frozenset({4, 8, 10, 12, 16, 19}),
}


def get_asi_levels(cls: str) -> frozenset[int]:
    """回傳該職業的 ASI 等級集合。"""
    return ASI_LEVEL_OVERRIDES.get(cls, DEFAULT_ASI_LEVELS)


# 各職業每個等級解鎖的特性（優先實作劇本用到的 Fighter / Cleric / Rogue + Warlock）
CLASS_LEVEL_FEATURES: dict[str, dict[int, list[str]]] = {
    "Fighter": {
        1: ["Fighting Style", "Second Wind", "Weapon Mastery"],
        2: ["Action Surge", "Tactical Mind"],
        3: ["Subclass"],
        4: ["ASI"],
        5: ["Extra Attack"],
        6: ["ASI"],
        7: ["Subclass Feature"],
        8: ["ASI"],
        9: ["Indomitable"],
        10: ["Subclass Feature"],
        11: ["Two Extra Attacks"],
        12: ["ASI"],
        13: ["Indomitable (2)"],
        14: ["ASI"],
        15: ["Subclass Feature"],
        16: ["ASI"],
        17: ["Action Surge (2)", "Indomitable (3)"],
        18: ["Subclass Feature"],
        19: ["ASI"],
        20: ["Three Extra Attacks"],
    },
    "Cleric": {
        1: ["Divine Order", "Spellcasting", "Subclass"],
        2: ["Channel Divinity"],
        3: ["Subclass Feature"],
        4: ["ASI"],
        5: ["Smite Undead"],
        6: ["Subclass Feature", "Channel Divinity (2)"],
        7: ["Blessed Strikes"],
        8: ["ASI"],
        9: ["Subclass Feature"],
        10: ["Divine Intervention"],
        11: ["Channel Divinity (3)"],
        12: ["ASI"],
        13: [],
        14: ["Improved Blessed Strikes"],
        15: [],
        16: ["ASI"],
        17: ["Subclass Feature"],
        18: [],
        19: ["ASI"],
        20: ["Greater Divine Intervention"],
    },
    "Rogue": {
        1: ["Expertise", "Sneak Attack", "Thieves' Cant", "Weapon Mastery"],
        2: ["Cunning Action"],
        3: ["Steady Aim", "Subclass"],
        4: ["ASI"],
        5: ["Cunning Strike", "Uncanny Dodge"],
        6: ["Expertise (2)"],
        7: ["Evasion", "Reliable Talent"],
        8: ["ASI"],
        9: ["Subclass Feature"],
        10: ["ASI"],
        11: ["Improved Cunning Strike"],
        12: ["ASI"],
        13: ["Subclass Feature"],
        14: ["Devious Strikes"],
        15: ["Slippery Mind"],
        16: ["ASI"],
        17: ["Subclass Feature"],
        18: ["Elusive"],
        19: ["ASI"],
        20: ["Stroke of Luck"],
    },
    "Warlock": {
        1: ["Eldritch Invocations", "Pact Magic", "Subclass"],
        2: ["Magical Cunning"],
        3: ["Subclass Feature"],
        4: ["ASI"],
        5: ["Subclass Feature"],
        6: ["Eldritch Invocations (2)"],
        7: ["Subclass Feature"],
        8: ["ASI"],
        9: ["Contact Patron"],
        10: ["Subclass Feature"],
        11: ["Mystic Arcanum (6th)"],
        12: ["ASI"],
        13: ["Mystic Arcanum (7th)"],
        14: ["Subclass Feature"],
        15: ["Mystic Arcanum (8th)"],
        16: ["ASI"],
        17: ["Mystic Arcanum (9th)"],
        18: ["Eldritch Invocations (3)"],
        19: ["ASI"],
        20: ["Eldritch Master"],
    },
    "Barbarian": {
        1: ["Rage", "Unarmored Defense", "Weapon Mastery"],
        2: ["Danger Sense", "Reckless Attack"],
        3: ["Primal Knowledge", "Subclass"],
        4: ["ASI"],
        5: ["Extra Attack", "Fast Movement"],
        6: ["Subclass Feature"],
        7: ["Feral Instinct", "Instinctive Pounce"],
        8: ["ASI"],
        9: ["Brutal Strike"],
        10: ["Subclass Feature"],
        11: ["Relentless Rage"],
        12: ["ASI"],
        13: ["Improved Brutal Strike"],
        14: ["Subclass Feature"],
        15: ["Persistent Rage"],
        16: ["ASI"],
        17: ["Improved Brutal Strike (2)"],
        18: ["Indomitable Might"],
        19: ["ASI"],
        20: ["Primal Champion"],
    },
    "Bard": {
        1: ["Bardic Inspiration", "Spellcasting"],
        2: ["Expertise", "Jack of All Trades"],
        3: ["Subclass"],
        4: ["ASI"],
        5: ["Font of Inspiration"],
        6: ["Subclass Feature"],
        7: ["Countercharm"],
        8: ["ASI"],
        9: ["Subclass Feature"],
        10: ["Magical Secrets"],
        11: [],
        12: ["ASI"],
        13: [],
        14: ["Subclass Feature"],
        15: ["Superior Inspiration"],
        16: ["ASI"],
        17: [],
        18: ["Magical Secrets (2)"],
        19: ["ASI"],
        20: ["Words of Creation"],
    },
    "Druid": {
        1: ["Druidic", "Primal Order", "Spellcasting"],
        2: ["Wild Shape", "Wild Companion"],
        3: ["Subclass"],
        4: ["ASI", "Wild Shape (2)"],
        5: ["Wild Resurgence"],
        6: ["Subclass Feature"],
        7: ["Elemental Fury"],
        8: ["ASI", "Wild Shape (3)"],
        9: ["Subclass Feature"],
        10: ["Subclass Feature"],
        11: [],
        12: ["ASI"],
        13: [],
        14: ["Subclass Feature"],
        15: [],
        16: ["ASI"],
        17: [],
        18: ["Beast Spells"],
        19: ["ASI"],
        20: ["Archdruid"],
    },
    "Monk": {
        1: ["Martial Arts", "Unarmored Defense"],
        2: ["Monk's Discipline", "Unarmored Movement", "Uncanny Metabolism"],
        3: ["Deflect Attacks", "Subclass"],
        4: ["ASI", "Slow Fall"],
        5: ["Extra Attack", "Stunning Strike"],
        6: ["Subclass Feature", "Empowered Strikes"],
        7: ["Evasion"],
        8: ["ASI"],
        9: ["Acrobatic Movement"],
        10: ["Heightened Discipline", "Self-Restoration"],
        11: ["Subclass Feature"],
        12: ["ASI"],
        13: ["Deflect Energy"],
        14: ["Disciplined Survivor"],
        15: ["Perfect Discipline"],
        16: ["ASI"],
        17: ["Subclass Feature"],
        18: ["Superior Defense"],
        19: ["ASI"],
        20: ["Body and Mind"],
    },
    "Paladin": {
        1: ["Divine Sense", "Lay On Hands", "Spellcasting", "Weapon Mastery"],
        2: ["Fighting Style", "Paladin's Smite"],
        3: ["Channel Divinity", "Subclass"],
        4: ["ASI"],
        5: ["Extra Attack", "Faithful Steed"],
        6: ["Aura of Protection"],
        7: ["Subclass Feature"],
        8: ["ASI"],
        9: ["Abjure Foes"],
        10: ["Aura of Courage"],
        11: ["Radiant Strikes"],
        12: ["ASI"],
        13: [],
        14: ["Restoring Touch"],
        15: ["Subclass Feature"],
        16: ["ASI"],
        17: [],
        18: ["Aura Expansion"],
        19: ["ASI"],
        20: ["Subclass Feature"],
    },
    "Ranger": {
        1: ["Deft Explorer", "Favored Enemy", "Spellcasting", "Weapon Mastery"],
        2: ["Fighting Style", "Roving"],
        3: ["Subclass"],
        4: ["ASI"],
        5: ["Extra Attack"],
        6: ["Tireless"],
        7: ["Subclass Feature"],
        8: ["ASI"],
        9: ["Conjure Barrage"],
        10: ["Subclass Feature"],
        11: ["Relentless Hunter"],
        12: ["ASI"],
        13: [],
        14: ["Subclass Feature"],
        15: ["Precise Hunter"],
        16: ["ASI"],
        17: ["Conjure Volley"],
        18: ["Feral Senses"],
        19: ["ASI"],
        20: ["Foe Slayer"],
    },
    "Sorcerer": {
        1: ["Innate Sorcery", "Spellcasting", "Subclass"],
        2: ["Font of Magic", "Metamagic"],
        3: ["Subclass Feature"],
        4: ["ASI"],
        5: ["Subclass Feature", "Sorcerous Restoration"],
        6: ["Subclass Feature"],
        7: [],
        8: ["ASI"],
        9: [],
        10: ["Metamagic (2)"],
        11: [],
        12: ["ASI"],
        13: [],
        14: ["Subclass Feature"],
        15: [],
        16: ["ASI"],
        17: ["Metamagic (3)"],
        18: ["Subclass Feature"],
        19: ["ASI"],
        20: ["Arcane Apotheosis"],
    },
    "Wizard": {
        1: ["Arcane Recovery", "Spellcasting", "Subclass"],
        2: ["Scholar"],
        3: ["Subclass Feature"],
        4: ["ASI"],
        5: [],
        6: ["Subclass Feature"],
        7: [],
        8: ["ASI"],
        9: [],
        10: ["Subclass Feature"],
        11: [],
        12: ["ASI"],
        13: [],
        14: ["Subclass Feature"],
        15: [],
        16: ["ASI"],
        17: [],
        18: ["Spell Mastery"],
        19: ["ASI"],
        20: ["Signature Spells"],
    },
}


# ---------------------------------------------------------------------------
# 經驗值升級門檻（PHB）
# ---------------------------------------------------------------------------

XP_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def level_for_xp(xp: int) -> int:
    """根據總經驗值決定角色等級。"""
    level = 1
    for lvl, threshold in sorted(XP_THRESHOLDS.items()):
        if xp >= threshold:
            level = lvl
    return level


# ---------------------------------------------------------------------------
# 角色建構器
# ---------------------------------------------------------------------------


def build_character(
    name: str,
    class_levels: dict[str, int],
    subclasses: dict[str, str] | None = None,
    ability_scores: AbilityScores | None = None,
    species: str = "",
    background: str = "",
    skill_proficiencies: list[Skill] | None = None,
    armor_type: str = "none",
    has_shield: bool = False,
) -> Character:
    """建構角色並計算所有衍生數值。支援兼職。

    這是角色建立的主要進入點。接收玩家的選擇後，
    計算 Bone Engine 所需的一切數值。

    Args:
        name: 角色名稱。
        class_levels: 每個職業的等級，例如 {"Fighter": 1}。
        subclasses: 子職業對照，例如 {"Fighter": "Champion"}。
        ability_scores: 六大屬性值。
        species: 種族。
        background: 背景。
        skill_proficiencies: 技能熟練項。
        armor_type: 護甲類型。
        has_shield: 是否持盾。
    """
    if not class_levels:
        raise ValueError("class_levels 不能為空")
    for cls_name in class_levels:
        if cls_name not in CLASS_REGISTRY:
            raise ValueError(f"未知職業: {cls_name!r}")

    subclasses = subclasses or {}
    scores = ability_scores or AbilityScores()

    # 主職（等級最高的職業）
    primary_class = max(class_levels, key=class_levels.__getitem__)
    primary_cls = CLASS_REGISTRY[primary_class]
    total_level = sum(class_levels.values())

    prof_bonus = proficiency_bonus_for_level(total_level)
    con_mod = scores.modifier(Ability.CON)
    dex_mod = scores.modifier(Ability.DEX)

    # 無甲防禦（取主職）
    effective_armor = armor_type
    unarmored_bonus = 0
    if primary_class == "Barbarian" and armor_type == "none":
        effective_armor = "unarmored_barbarian"
        unarmored_bonus = scores.modifier(Ability.CON)
    elif primary_class == "Monk" and armor_type == "none":
        effective_armor = "unarmored_monk"
        unarmored_bonus = scores.modifier(Ability.WIS)

    ac = compute_ac(dex_mod, effective_armor, has_shield, unarmored_bonus)

    # HP = 所有職業等級的 HP 加總
    hp = 0
    for cls_name, lvl in class_levels.items():
        cls_data = CLASS_REGISTRY[cls_name]
        hp += compute_hp_at_level(cls_data.hit_die, con_mod, lvl)

    # 兼職法術欄位
    if len(class_levels) == 1:
        # 單一職業：直接查表（包含術士）
        spell_slots_obj = get_spell_slots(primary_class, total_level)
        if primary_class == "Warlock":
            pact_slots = spell_slots_obj
            spell_slots_obj = SpellSlots()
        else:
            pact_slots = SpellSlots()
    else:
        spell_slots_obj, pact_slots = compute_multiclass_spell_slots(class_levels, subclasses)

    # 法術 DC 和攻擊加值（依主職施法屬性）
    casting_mod = 0
    if primary_cls.spellcasting_ability is not None:
        casting_mod = scores.modifier(primary_cls.spellcasting_ability)
    spell_dc = compute_spell_dc(prof_bonus, casting_mod)
    spell_attack = compute_spell_attack(prof_bonus, casting_mod)

    # Hit Dice：依職業分組 {骰面: 顆數}
    hit_dice: dict[int, int] = {}
    for cls_name, lvl in class_levels.items():
        die = CLASS_REGISTRY[cls_name].hit_die
        hit_dice[die] = hit_dice.get(die, 0) + lvl

    return Character(
        name=name,
        species=species,
        background=background,
        class_levels=dict(class_levels),
        subclasses=dict(subclasses),
        ability_scores=scores,
        proficiency_bonus=prof_bonus,
        hp_max=hp,
        hp_current=hp,
        hit_dice_remaining=hit_dice,
        pact_slots=pact_slots,
        ac=ac,
        speed=9,  # 預設 30ft = 9m，種族可能覆寫
        initiative_bonus=dex_mod,
        skill_proficiencies=skill_proficiencies or [],
        saving_throw_proficiencies=primary_cls.saving_throws,
        spell_slots=spell_slots_obj,
        spell_dc=spell_dc,
        spell_attack=spell_attack,
    )


# ---------------------------------------------------------------------------
# 分步驟角色建造器（Builder Pattern）
# ---------------------------------------------------------------------------

# 建角步驟順序：姓名 → 背景 → 種族 → 職業 → 屬性 → 技能
_BUILD_STEPS = ("name", "background", "species", "class", "ability_scores", "skills")


class CharacterBuilder:
    """分步驟角色建造器——包裝 build_character() 供 CLI 互動模式使用。

    建角順序：姓名 → 背景 → 種族 → 職業 → 屬性 → 技能。
    每一步都驗證前置條件，最後呼叫 build_character() 產出 Character。
    護甲、等級、子職業為可選選項，可在任何步驟設定。
    """

    def __init__(self) -> None:
        self._step: int = 0
        self._name: str = ""
        self._background: str = ""
        self._species: str = ""
        self._class_levels: dict[str, int] = {}  # 例如 {"Fighter": 1}
        self._subclasses: dict[str, str] = {}  # 例如 {"Fighter": "Champion"}
        self._pending_subclass: str = ""  # set_subclass 在 set_class 前呼叫時暫存
        self._ability_scores: AbilityScores | None = None
        self._skill_proficiencies: list[Skill] = []
        self._armor_type: str = "none"
        self._has_shield: bool = False
        self._level: int = 1  # 建角用（1 級起始）

    # -- 資訊查詢 --

    @property
    def current_step(self) -> str:
        """回傳下一步該做什麼。"""
        if self._step >= len(_BUILD_STEPS):
            return "ready"
        return _BUILD_STEPS[self._step]

    @property
    def available_classes(self) -> list[str]:
        """可選的職業列表。"""
        return list(CLASS_REGISTRY.keys())

    @property
    def _char_class(self) -> str:
        """主職（建角用，永遠是單一職業）。"""
        if not self._class_levels:
            return ""
        return next(iter(self._class_levels))

    @property
    def available_skills(self) -> list[Skill]:
        """依已選職業回傳可選技能列表。"""
        if not self._char_class or self._char_class not in CLASS_REGISTRY:
            return []
        cls = CLASS_REGISTRY[self._char_class]
        return list(cls.skill_choices)

    @property
    def num_skills(self) -> int:
        """依已選職業回傳應選技能數量。"""
        if not self._char_class or self._char_class not in CLASS_REGISTRY:
            return 0
        return CLASS_REGISTRY[self._char_class].num_skills

    # -- Step 1: 姓名 --

    def set_name(self, name: str) -> None:
        """Step 1: 設定角色名稱。"""
        if self._step > 0:
            raise ValueError("姓名必須在第一步設定")
        if not name.strip():
            raise ValueError("角色名稱不能為空")
        self._name = name.strip()
        self._step = 1

    # -- Step 2: 背景 --

    def set_background(self, background: str) -> None:
        """Step 2: 選擇背景。"""
        if self._step < 1:
            raise ValueError("請先設定角色名稱")
        if self._step > 1:
            raise ValueError("背景必須在第二步設定")
        self._background = background
        self._step = 2

    # -- Step 3: 種族 --

    def set_species(self, species: str) -> None:
        """Step 3: 選擇種族。"""
        if self._step < 2:
            raise ValueError("請先選擇背景")
        if self._step > 2:
            raise ValueError("種族必須在第三步設定")
        self._species = species
        self._step = 3

    # -- Step 4: 職業 --

    def set_class(self, char_class: str) -> None:
        """Step 4: 選擇職業。創角永遠從 1 級單一職業開始。"""
        if self._step < 3:
            raise ValueError("請先選擇種族")
        if self._step > 3:
            raise ValueError("職業必須在第四步設定")
        if char_class not in CLASS_REGISTRY:
            raise ValueError(f"未知職業: {char_class!r}")
        self._class_levels = {char_class: 1}
        # 若有 pending 子職業（在 set_class 之前呼叫 set_subclass），套用之
        if self._pending_subclass:
            self._subclasses[char_class] = self._pending_subclass
            self._pending_subclass = ""
        self._step = 4

    # -- Step 5: 屬性值 --

    def set_ability_scores(
        self,
        scores: AbilityScores | dict[Ability, int],
        *,
        method: str = "manual",
    ) -> None:
        """Step 5: 設定屬性值。

        method: "manual" | "point_buy" | "standard_array"
        """
        if self._step < 4:
            raise ValueError("請先選擇職業")
        if self._step > 4:
            raise ValueError("屬性值必須在第五步設定")

        if isinstance(scores, dict):
            if method == "point_buy":
                ok, msg = validate_point_buy(scores)
                if not ok:
                    raise ValueError(msg)
            elif method == "standard_array":
                ok, msg = validate_standard_array(scores)
                if not ok:
                    raise ValueError(msg)
            self._ability_scores = AbilityScores(**{a.value: v for a, v in scores.items()})
        else:
            self._ability_scores = scores

        self._step = 5

    # -- Step 6: 技能 --

    def set_skills(self, skills: list[Skill]) -> None:
        """Step 6: 選擇技能熟練項。"""
        if self._step < 5:
            raise ValueError("請先設定屬性值")
        if self._step > 5:
            raise ValueError("技能必須在第六步設定")

        cls = CLASS_REGISTRY[self._char_class]
        for s in skills:
            if s not in cls.skill_choices:
                raise ValueError(f"{self._char_class} 無法選擇技能 {s.value}")
        if len(skills) != cls.num_skills:
            raise ValueError(f"{self._char_class} 應選 {cls.num_skills} 項技能，收到 {len(skills)}")

        self._skill_proficiencies = skills
        self._step = 6

    # -- 可選選項（不影響步驟順序，任何時候都可設定）--

    def set_armor(self, armor_type: str, has_shield: bool = False) -> None:
        """設定護甲（可選）。可在任何步驟呼叫。"""
        self._armor_type = armor_type
        self._has_shield = has_shield

    def set_level(self, level: int) -> None:
        """設定等級（可選，預設 1）。可在任何步驟呼叫。"""
        if level < 1 or level > 20:
            raise ValueError(f"等級必須在 1-20 之間，收到 {level}")
        self._level = level

    def set_subclass(self, subclass: str) -> None:
        """設定子職業（可選）。可在任何步驟呼叫（含 set_class 之前）。"""
        if self._char_class:
            self._subclasses[self._char_class] = subclass
        else:
            # 職業尚未設定：暫存，等 set_class 時套用
            self._pending_subclass = subclass

    # -- 建構 --

    def build(self) -> Character:
        """呼叫 build_character() 產出完整角色。所有必要步驟必須完成。"""
        if self._step < len(_BUILD_STEPS):
            raise ValueError(f"建角尚未完成，目前在步驟: {self.current_step}")

        # 建角永遠 1 級起始，set_level() 僅供進階用途（測試、DM 特殊情境）
        class_levels = {self._char_class: self._level}

        return build_character(
            name=self._name,
            class_levels=class_levels,
            subclasses=self._subclasses if self._subclasses else None,
            ability_scores=self._ability_scores,
            species=self._species,
            background=self._background,
            skill_proficiencies=self._skill_proficiencies,
            armor_type=self._armor_type,
            has_shield=self._has_shield,
        )


# ---------------------------------------------------------------------------
# 升級系統
# ---------------------------------------------------------------------------


@dataclass
class LevelUpChoices:
    """升級時的選擇。"""

    target_class: str  # 升哪個職業（可以是新職業，觸發兼職）
    hp_roll: int | None = None  # 擲 HP 骰；None = 使用固定值（die//2+1）
    new_subclass: str | None = None  # 若本次等級解鎖子職業
    new_spells: list[str] = field(default_factory=list)
    asi_ability: tuple[str, str] | None = None  # ASI：(ability1, ability2)，各 +1
    feat_name: str | None = None  # 選 Feat 代替 ASI


def level_up(character: Character, choices: LevelUpChoices) -> Character:
    """執行升級。回傳更新後的 Character（原地修改）。

    流程：
    1. 若升新職業：驗證兼職前置條件
    2. class_levels[target] += 1
    3. 計算並增加 HP
    4. 更新 hit_dice_remaining
    5. 更新熟練加值
    6. 重算法術欄位（含兼職公式）
    7. 套用職業特性標記
    8. 處理 ASI / Feat
    9. 新法術加入 spells_known
    """
    target = choices.target_class
    if target not in CLASS_REGISTRY:
        raise ValueError(f"未知職業: {target!r}")

    # 是否兼職新職業
    is_new_class = target not in character.class_levels
    if is_new_class:
        ok, msg = validate_multiclass_prereq(character, target)
        if not ok:
            raise ValueError(f"無法兼職 {target}：{msg}")

    # 更新職業等級
    new_class_levels = dict(character.class_levels)
    new_class_levels[target] = new_class_levels.get(target, 0) + 1
    new_level_in_class = new_class_levels[target]
    new_total = sum(new_class_levels.values())

    # HP 增加
    cls_data = CLASS_REGISTRY[target]
    con_mod = character.ability_modifier(Ability.CON)
    avg_hp = cls_data.hit_die // 2 + 1
    hp_gain = (choices.hp_roll if choices.hp_roll is not None else avg_hp) + con_mod
    hp_gain = max(1, hp_gain)

    # Hit Dice 增加（依骰面）
    new_hit_dice = dict(character.hit_dice_remaining)
    die = cls_data.hit_die
    new_hit_dice[die] = new_hit_dice.get(die, 0) + 1

    # 熟練加值
    new_prof_bonus = proficiency_bonus_for_level(new_total)

    # 法術欄位
    new_subclasses = dict(character.subclasses)
    if choices.new_subclass:
        new_subclasses[target] = choices.new_subclass
    if len(new_class_levels) == 1:
        spell_slots_obj = get_spell_slots(target, new_level_in_class)
        if target == "Warlock":
            pact_slots = spell_slots_obj
            spell_slots_obj = SpellSlots()
        else:
            pact_slots = character.pact_slots
    else:
        spell_slots_obj, pact_slots = compute_multiclass_spell_slots(
            new_class_levels, new_subclasses
        )

    # ASI
    level_features = CLASS_LEVEL_FEATURES.get(target, {}).get(new_level_in_class, [])
    if choices.asi_ability and "ASI" in level_features:
        a1, a2 = choices.asi_ability
        scores_data = character.ability_scores.model_dump()
        for ability_name in (a1, a2):
            scores_data[ability_name] = min(20, scores_data.get(ability_name, 10) + 1)
        character.ability_scores = character.ability_scores.model_validate(scores_data)

    # 法術
    new_spells_known = list(character.spells_known)
    for spell_name in choices.new_spells:
        if spell_name not in new_spells_known:
            new_spells_known.append(spell_name)

    # 套用所有變更
    character.class_levels = new_class_levels
    character.subclasses = new_subclasses
    character.hp_max += hp_gain
    character.hp_current += hp_gain
    character.hit_dice_remaining = new_hit_dice
    character.proficiency_bonus = new_prof_bonus
    character.spell_slots = spell_slots_obj
    character.pact_slots = pact_slots
    character.spells_known = new_spells_known

    return character
