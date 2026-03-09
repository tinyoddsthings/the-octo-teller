"""Bone Engine 角色建立與衍生數值計算。

處理屬性值生成、職業/種族資料查詢，以及所有確定性角色計算
（HP、AC、法術 DC 等）。基於 D&D 2024 (5.5e) 規則。
"""

from __future__ import annotations

from tot.gremlins.bone_engine.dice import roll_ability_scores
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
            Skill.ANIMAL_HANDLING, Skill.ATHLETICS, Skill.INTIMIDATION,
            Skill.NATURE, Skill.PERCEPTION, Skill.SURVIVAL,
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
            Skill.HISTORY, Skill.INSIGHT, Skill.MEDICINE,
            Skill.PERSUASION, Skill.RELIGION,
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
            Skill.ARCANA, Skill.ANIMAL_HANDLING, Skill.INSIGHT,
            Skill.MEDICINE, Skill.NATURE, Skill.PERCEPTION,
            Skill.RELIGION, Skill.SURVIVAL,
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
            Skill.ACROBATICS, Skill.ANIMAL_HANDLING, Skill.ATHLETICS,
            Skill.HISTORY, Skill.INSIGHT, Skill.INTIMIDATION,
            Skill.PERSUASION, Skill.PERCEPTION, Skill.SURVIVAL,
        ],
        num_skills=2,
    ),
    "Monk": ClassData(
        name="Monk",
        hit_die=8,
        primary_ability=Ability.DEX,
        saving_throws=[Ability.STR, Ability.DEX],
        skill_choices=[
            Skill.ACROBATICS, Skill.ATHLETICS, Skill.HISTORY,
            Skill.INSIGHT, Skill.RELIGION, Skill.STEALTH,
        ],
        num_skills=2,
    ),
    "Paladin": ClassData(
        name="Paladin",
        hit_die=10,
        primary_ability=Ability.STR,
        saving_throws=[Ability.WIS, Ability.CHA],
        skill_choices=[
            Skill.ATHLETICS, Skill.INSIGHT, Skill.INTIMIDATION,
            Skill.MEDICINE, Skill.PERSUASION, Skill.RELIGION,
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
            Skill.ANIMAL_HANDLING, Skill.ATHLETICS, Skill.INSIGHT,
            Skill.INVESTIGATION, Skill.NATURE, Skill.PERCEPTION,
            Skill.STEALTH, Skill.SURVIVAL,
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
            Skill.ACROBATICS, Skill.ATHLETICS, Skill.DECEPTION,
            Skill.INSIGHT, Skill.INTIMIDATION, Skill.INVESTIGATION,
            Skill.PERCEPTION, Skill.PERSUASION, Skill.SLEIGHT_OF_HAND,
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
            Skill.ARCANA, Skill.DECEPTION, Skill.INSIGHT,
            Skill.INTIMIDATION, Skill.PERSUASION, Skill.RELIGION,
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
            Skill.ARCANA, Skill.DECEPTION, Skill.HISTORY,
            Skill.INTIMIDATION, Skill.INVESTIGATION, Skill.NATURE,
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
            Skill.ARCANA, Skill.HISTORY, Skill.INSIGHT,
            Skill.INVESTIGATION, Skill.MEDICINE, Skill.NATURE,
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
    8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9,
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
            raise ValueError(
                f"{ability} 會變成 {new_val}（上限 20）"
            )
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
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
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
    1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2), 5: (2, 3),
    6: (2, 3), 7: (2, 4), 8: (2, 4), 9: (2, 5), 10: (2, 5),
    11: (3, 5), 12: (3, 5), 13: (3, 5), 14: (3, 5), 15: (3, 5),
    16: (3, 5), 17: (4, 5), 18: (4, 5), 19: (4, 5), 20: (4, 5),
}

FULL_CASTERS = {"Bard", "Cleric", "Druid", "Sorcerer", "Wizard"}
HALF_CASTERS = {"Paladin", "Ranger"}


def get_spell_slots(char_class: str, level: int) -> SpellSlots:
    """依職業與等級取得法術欄位。"""
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
# 經驗值升級門檻（PHB）
# ---------------------------------------------------------------------------

XP_THRESHOLDS: dict[int, int] = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000,
    7: 23000, 8: 34000, 9: 48000, 10: 64000, 11: 85000,
    12: 100000, 13: 120000, 14: 140000, 15: 165000, 16: 195000,
    17: 225000, 18: 265000, 19: 305000, 20: 355000,
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
    char_class: str,
    level: int = 1,
    ability_scores: AbilityScores | None = None,
    species: str = "",
    subclass: str = "",
    background: str = "",
    skill_proficiencies: list[Skill] | None = None,
    armor_type: str = "none",
    has_shield: bool = False,
) -> Character:
    """建構角色並計算所有衍生數值。

    這是角色建立的主要進入點。接收玩家的選擇後，
    計算 Bone Engine 所需的一切數值。
    """
    if char_class not in CLASS_REGISTRY:
        raise ValueError(f"未知職業: {char_class!r}")

    cls = CLASS_REGISTRY[char_class]
    scores = ability_scores or AbilityScores()
    prof_bonus = proficiency_bonus_for_level(level)
    con_mod = scores.modifier(Ability.CON)
    dex_mod = scores.modifier(Ability.DEX)

    # 無甲防禦
    if char_class == "Barbarian" and armor_type == "none":
        armor_type = "unarmored_barbarian"
        unarmored_bonus = scores.modifier(Ability.CON)
    elif char_class == "Monk" and armor_type == "none":
        armor_type = "unarmored_monk"
        unarmored_bonus = scores.modifier(Ability.WIS)
    else:
        unarmored_bonus = 0

    ac = compute_ac(dex_mod, armor_type, has_shield, unarmored_bonus)
    hp = compute_hp_at_level(cls.hit_die, con_mod, level)
    spell_slots = get_spell_slots(char_class, level)

    return Character(
        name=name,
        species=species,
        char_class=char_class,
        subclass=subclass,
        level=level,
        background=background,
        ability_scores=scores,
        proficiency_bonus=prof_bonus,
        hp_max=hp,
        hp_current=hp,
        hit_dice_total=level,
        hit_dice_remaining=level,
        hit_die_size=cls.hit_die,
        ac=ac,
        speed=9,  # 預設 30ft = 9m，種族可能覆寫
        initiative_bonus=dex_mod,
        skill_proficiencies=skill_proficiencies or [],
        saving_throw_proficiencies=cls.saving_throws,
        spell_slots=spell_slots,
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
        self._char_class: str = ""
        self._ability_scores: AbilityScores | None = None
        self._skill_proficiencies: list[Skill] = []
        self._armor_type: str = "none"
        self._has_shield: bool = False
        self._level: int = 1
        self._subclass: str = ""

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
        """Step 4: 選擇職業。"""
        if self._step < 3:
            raise ValueError("請先選擇種族")
        if self._step > 3:
            raise ValueError("職業必須在第四步設定")
        if char_class not in CLASS_REGISTRY:
            raise ValueError(f"未知職業: {char_class!r}")
        self._char_class = char_class
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
            self._ability_scores = AbilityScores(
                **{a.value: v for a, v in scores.items()}
            )
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
                raise ValueError(
                    f"{self._char_class} 無法選擇技能 {s.value}"
                )
        if len(skills) != cls.num_skills:
            raise ValueError(
                f"{self._char_class} 應選 {cls.num_skills} 項技能，收到 {len(skills)}"
            )

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
        """設定子職業（可選）。可在任何步驟呼叫。"""
        self._subclass = subclass

    # -- 建構 --

    def build(self) -> Character:
        """呼叫 build_character() 產出完整角色。所有必要步驟必須完成。"""
        if self._step < len(_BUILD_STEPS):
            raise ValueError(
                f"建角尚未完成，目前在步驟: {self.current_step}"
            )

        return build_character(
            name=self._name,
            char_class=self._char_class,
            level=self._level,
            ability_scores=self._ability_scores,
            species=self._species,
            subclass=self._subclass,
            background=self._background,
            skill_proficiencies=self._skill_proficiencies,
            armor_type=self._armor_type,
            has_shield=self._has_shield,
        )
