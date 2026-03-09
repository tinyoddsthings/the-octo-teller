"""T.O.T. Bone Engine 核心 Pydantic 資料模型。

所有跨模組的資料結構都定義在這裡。Bone Engine 是純確定性的
——不呼叫 LLM、除了骰子以外沒有隨機性。
基於 D&D 2024 (5.5e) 規則。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# 列舉型別
# ---------------------------------------------------------------------------

class Ability(StrEnum):
    STR = "STR"
    DEX = "DEX"
    CON = "CON"
    INT = "INT"
    WIS = "WIS"
    CHA = "CHA"


class Skill(StrEnum):
    # 力量系
    ATHLETICS = "Athletics"
    # 敏捷系
    ACROBATICS = "Acrobatics"
    SLEIGHT_OF_HAND = "Sleight of Hand"
    STEALTH = "Stealth"
    # 智力系
    ARCANA = "Arcana"
    HISTORY = "History"
    INVESTIGATION = "Investigation"
    NATURE = "Nature"
    RELIGION = "Religion"
    # 感知系
    ANIMAL_HANDLING = "Animal Handling"
    INSIGHT = "Insight"
    MEDICINE = "Medicine"
    PERCEPTION = "Perception"
    SURVIVAL = "Survival"
    # 魅力系
    DECEPTION = "Deception"
    INTIMIDATION = "Intimidation"
    PERFORMANCE = "Performance"
    PERSUASION = "Persuasion"


# 技能 → 對應屬性的對照表
SKILL_ABILITY_MAP: dict[Skill, Ability] = {
    Skill.ATHLETICS: Ability.STR,
    Skill.ACROBATICS: Ability.DEX,
    Skill.SLEIGHT_OF_HAND: Ability.DEX,
    Skill.STEALTH: Ability.DEX,
    Skill.ARCANA: Ability.INT,
    Skill.HISTORY: Ability.INT,
    Skill.INVESTIGATION: Ability.INT,
    Skill.NATURE: Ability.INT,
    Skill.RELIGION: Ability.INT,
    Skill.ANIMAL_HANDLING: Ability.WIS,
    Skill.INSIGHT: Ability.WIS,
    Skill.MEDICINE: Ability.WIS,
    Skill.PERCEPTION: Ability.WIS,
    Skill.SURVIVAL: Ability.WIS,
    Skill.DECEPTION: Ability.CHA,
    Skill.INTIMIDATION: Ability.CHA,
    Skill.PERFORMANCE: Ability.CHA,
    Skill.PERSUASION: Ability.CHA,
}


class DamageType(StrEnum):
    ACID = "Acid"
    BLUDGEONING = "Bludgeoning"
    COLD = "Cold"
    FIRE = "Fire"
    FORCE = "Force"
    LIGHTNING = "Lightning"
    NECROTIC = "Necrotic"
    PIERCING = "Piercing"
    POISON = "Poison"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    SLASHING = "Slashing"
    THUNDER = "Thunder"


class Condition(StrEnum):
    BLINDED = "Blinded"
    CHARMED = "Charmed"
    DEAFENED = "Deafened"
    DODGING = "Dodging"  # 非官方狀態，追蹤閃避動作效果（1 輪）
    EXHAUSTION = "Exhaustion"
    FRIGHTENED = "Frightened"
    GRAPPLED = "Grappled"
    INCAPACITATED = "Incapacitated"
    INVISIBLE = "Invisible"
    PARALYZED = "Paralyzed"
    PETRIFIED = "Petrified"
    POISONED = "Poisoned"
    PRONE = "Prone"
    RESTRAINED = "Restrained"
    STUNNED = "Stunned"
    UNCONSCIOUS = "Unconscious"
    WEAKENED = "Weakened"  # 2024 新增，傷害減半


class Size(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


class CreatureType(StrEnum):
    ABERRATION = "Aberration"
    BEAST = "Beast"
    CELESTIAL = "Celestial"
    CONSTRUCT = "Construct"
    DRAGON = "Dragon"
    ELEMENTAL = "Elemental"
    FEY = "Fey"
    FIEND = "Fiend"
    GIANT = "Giant"
    HUMANOID = "Humanoid"
    MONSTROSITY = "Monstrosity"
    OOZE = "Ooze"
    PLANT = "Plant"
    UNDEAD = "Undead"


class SpellSchool(StrEnum):
    ABJURATION = "Abjuration"
    CONJURATION = "Conjuration"
    DIVINATION = "Divination"
    ENCHANTMENT = "Enchantment"
    EVOCATION = "Evocation"
    ILLUSION = "Illusion"
    NECROMANCY = "Necromancy"
    TRANSMUTATION = "Transmutation"


class CoverType(StrEnum):
    """掩蔽類型。"""
    NONE = "None"
    HALF = "Half"                  # +2 AC 與 DEX 豁免
    THREE_QUARTERS = "Three-Quarters"  # +5 AC 與 DEX 豁免
    TOTAL = "Total"                # 無法被直接攻擊


class WeaponMastery(StrEnum):
    """2024 武器專精效果。"""
    CLEAVE = "Cleave"    # 命中後對相鄰另一目標造成屬性修正傷害
    GRAZE = "Graze"      # 未命中仍造成屬性修正傷害
    NICK = "Nick"         # 額外附贈動作攻擊
    PUSH = "Push"         # 命中後推開目標 3m
    SAP = "Sap"           # 命中後目標下次攻擊劣勢
    SLOW = "Slow"         # 命中後減速 3m
    TOPPLE = "Topple"     # 命中後目標 CON 豁免，失敗倒地
    VEX = "Vex"           # 命中後下次攻擊同目標優勢


# ---------------------------------------------------------------------------
# 屬性值
# ---------------------------------------------------------------------------

class AbilityScores(BaseModel):
    """六大屬性值，自動計算修正值。"""

    STR: int = 10
    DEX: int = 10
    CON: int = 10
    INT: int = 10
    WIS: int = 10
    CHA: int = 10

    def score(self, ability: Ability) -> int:
        return getattr(self, ability.value)

    def modifier(self, ability: Ability) -> int:
        """修正值公式：(屬性值 - 10) // 2，依據 PHB。"""
        return (self.score(ability) - 10) // 2


# ---------------------------------------------------------------------------
# 生效中的狀態（執行時狀態）
# ---------------------------------------------------------------------------

class ActiveCondition(BaseModel):
    """目前影響生物的狀態效果。"""

    condition: Condition
    source: str = ""
    remaining_rounds: int | None = None  # None = 無限期 / 直到被移除
    exhaustion_level: int = 0  # 僅用於力竭（1-6 級）


# ---------------------------------------------------------------------------
# 法術
# ---------------------------------------------------------------------------

class Spell(BaseModel):
    name: str
    level: int = Field(ge=0, le=9)  # 0 = 戲法
    school: SpellSchool
    casting_time: str = "1 action"
    range: str = "Self"
    duration: str = "Instantaneous"
    concentration: bool = False
    ritual: bool = False
    description: str = ""
    damage_dice: str = ""  # 例如 "1d10"，無傷害則為空字串
    damage_type: DamageType | None = None
    save_ability: Ability | None = None  # 需要豁免的法術
    classes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 物品與武器
# ---------------------------------------------------------------------------

class WeaponProperty(StrEnum):
    AMMUNITION = "Ammunition"
    FINESSE = "Finesse"
    HEAVY = "Heavy"
    LIGHT = "Light"
    LOADING = "Loading"
    REACH = "Reach"
    THROWN = "Thrown"
    TWO_HANDED = "Two-Handed"
    VERSATILE = "Versatile"


class Weapon(BaseModel):
    name: str
    damage_dice: str  # 例如 "1d8"
    damage_type: DamageType
    properties: list[WeaponProperty] = Field(default_factory=list)
    range_normal: int = 1  # 公尺；1 = 近戰
    range_long: int | None = None  # 遠程/投擲武器的長射程
    is_martial: bool = False
    mastery: WeaponMastery | None = None  # 2024 武器專精

    @computed_field
    @property
    def is_ranged(self) -> bool:
        return self.range_normal > 1

    @computed_field
    @property
    def is_finesse(self) -> bool:
        return WeaponProperty.FINESSE in self.properties


class Item(BaseModel):
    name: str
    description: str = ""
    weight: float = 0.0  # 公斤
    quantity: int = 1
    is_magic: bool = False
    requires_attunement: bool = False


# ---------------------------------------------------------------------------
# 角色
# ---------------------------------------------------------------------------

class SpellSlots(BaseModel):
    """追蹤每個環級的法術欄位（目前值 / 最大值）。"""

    max_slots: dict[int, int] = Field(default_factory=dict)  # {1: 4, 2: 3, ...}
    current_slots: dict[int, int] = Field(default_factory=dict)

    def use(self, level: int) -> bool:
        current = self.current_slots.get(level, 0)
        if current <= 0:
            return False
        self.current_slots[level] = current - 1
        return True

    def recover_all(self) -> None:
        self.current_slots = dict(self.max_slots)


class DeathSaves(BaseModel):
    successes: int = Field(default=0, ge=0, le=3)
    failures: int = Field(default=0, ge=0, le=3)

    def reset(self) -> None:
        self.successes = 0
        self.failures = 0

    @computed_field
    @property
    def is_stable(self) -> bool:
        return self.successes >= 3

    @computed_field
    @property
    def is_dead(self) -> bool:
        return self.failures >= 3


class Character(BaseModel):
    """玩家角色或 NPC 隊友。"""

    id: UUID = Field(default_factory=uuid4)
    name: str
    species: str = ""  # 2024 PHB 用「species」而非「race」
    char_class: str = ""
    subclass: str = ""
    level: int = Field(default=1, ge=1, le=20)
    background: str = ""

    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    proficiency_bonus: int = 2  # 由等級推導，但儲存方便使用
    size: Size = Size.MEDIUM

    hp_max: int = 10
    hp_current: int = 10
    hp_temp: int = 0
    hit_dice_total: int = 1
    hit_dice_remaining: int = 1
    hit_die_size: int = 8  # d6/d8/d10/d12

    ac: int = 10
    speed: int = 9  # 公尺（30ft ≈ 9m）
    initiative_bonus: int = 0

    skill_proficiencies: list[Skill] = Field(default_factory=list)
    skill_expertise: list[Skill] = Field(default_factory=list)
    saving_throw_proficiencies: list[Ability] = Field(default_factory=list)

    spell_slots: SpellSlots = Field(default_factory=SpellSlots)
    spells_known: list[str] = Field(default_factory=list)
    spells_prepared: list[str] = Field(default_factory=list)
    concentration_spell: str | None = None

    weapons: list[Weapon] = Field(default_factory=list)
    inventory: list[Item] = Field(default_factory=list)

    damage_resistances: list[DamageType] = Field(default_factory=list)
    damage_immunities: list[DamageType] = Field(default_factory=list)

    conditions: list[ActiveCondition] = Field(default_factory=list)
    death_saves: DeathSaves = Field(default_factory=DeathSaves)
    exhaustion_level: int = Field(default=0, ge=0, le=6)
    heroic_inspiration: bool = False

    xp: int = 0

    def ability_modifier(self, ability: Ability) -> int:
        return self.ability_scores.modifier(ability)

    def skill_bonus(self, skill: Skill) -> int:
        ability = SKILL_ABILITY_MAP[skill]
        bonus = self.ability_modifier(ability)
        if skill in self.skill_expertise:
            bonus += self.proficiency_bonus * 2
        elif skill in self.skill_proficiencies:
            bonus += self.proficiency_bonus
        return bonus

    def saving_throw(self, ability: Ability) -> int:
        bonus = self.ability_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            bonus += self.proficiency_bonus
        return bonus

    @computed_field
    @property
    def passive_perception(self) -> int:
        return 10 + self.skill_bonus(Skill.PERCEPTION)

    @computed_field
    @property
    def is_alive(self) -> bool:
        return not self.death_saves.is_dead and self.exhaustion_level < 6

    @computed_field
    @property
    def is_conscious(self) -> bool:
        return self.hp_current > 0

    def has_condition(self, condition: Condition) -> bool:
        return any(c.condition == condition for c in self.conditions)


# ---------------------------------------------------------------------------
# 怪物
# ---------------------------------------------------------------------------

class MonsterAction(BaseModel):
    name: str
    attack_bonus: int | None = None  # None = 無攻擊骰（豁免制法術）
    damage_dice: str = ""
    damage_type: DamageType | None = None
    reach: int = 1  # 公尺
    description: str = ""
    save_dc: int | None = None
    save_ability: Ability | None = None


class Monster(BaseModel):
    """怪物資料區塊。"""

    id: UUID = Field(default_factory=uuid4)
    name: str
    size: Size = Size.MEDIUM
    creature_type: CreatureType = CreatureType.HUMANOID
    alignment: str = ""

    ac: int = 10
    hp_max: int = 10
    hp_current: int = 10
    speed: int = 9

    ability_scores: AbilityScores = Field(default_factory=AbilityScores)
    challenge_rating: float = 0
    xp_reward: int = 0
    proficiency_bonus: int = 2

    damage_resistances: list[DamageType] = Field(default_factory=list)
    damage_immunities: list[DamageType] = Field(default_factory=list)
    condition_immunities: list[Condition] = Field(default_factory=list)

    actions: list[MonsterAction] = Field(default_factory=list)
    conditions: list[ActiveCondition] = Field(default_factory=list)

    label: str = ""  # 戰鬥中的顯示標籤（例如「哥布林 A」）

    def ability_modifier(self, ability: Ability) -> int:
        return self.ability_scores.modifier(ability)

    @computed_field
    @property
    def is_alive(self) -> bool:
        return self.hp_current > 0

    @computed_field
    @property
    def hp_description(self) -> str:
        """給玩家看的 HP 描述（不顯示精確數字）。"""
        if self.hp_max == 0:
            return "N/A"
        ratio = self.hp_current / self.hp_max
        if ratio >= 1.0:
            return "無傷"
        if ratio >= 0.75:
            return "輕微受傷"
        if ratio >= 0.50:
            return "明顯受傷"
        if ratio >= 0.25:
            return "重傷"
        if ratio > 0:
            return "瀕死"
        return "倒下"

    def has_condition(self, condition: Condition) -> bool:
        if condition in self.condition_immunities:
            return False
        return any(c.condition == condition for c in self.conditions)


# ---------------------------------------------------------------------------
# 戰鬥狀態
# ---------------------------------------------------------------------------

CombatantRef = tuple[Literal["character", "monster"], UUID]


# ---------------------------------------------------------------------------
# 地圖座標系統
# ---------------------------------------------------------------------------

class Position(BaseModel):
    """格子座標（左下為原點，X 向右、Y 向上）。"""
    x: int = 0
    y: int = 0


class Entity(BaseModel):
    """地圖上的實體基底。"""
    id: str
    x: int
    y: int
    symbol: str = "?"       # ASCII 單字元
    is_blocking: bool = False
    name: str = ""


class Actor(Entity):
    """地圖上的戰鬥者（參照 Character/Monster，不繼承）。"""
    combatant_id: UUID
    combatant_type: Literal["character", "monster"]
    is_blocking: bool = True  # 生物預設阻擋通行
    is_alive: bool = True


class Prop(Entity):
    """靜態物件（牆壁、門、陷阱、掉落物）。"""
    prop_type: str = "decoration"  # wall / door / trap / item / decoration
    hidden: bool = False           # 隱藏物件（陷阱等）


class TerrainTile(BaseModel):
    """地形格。"""
    symbol: str = "."
    is_blocking: bool = False
    name: str = "floor"
    is_difficult: bool = False     # 困難地形（移動加倍消耗）


class TurnState(BaseModel):
    """單一回合內的動作經濟追蹤。"""
    action_used: bool = False
    bonus_action_used: bool = False
    mastery_used: bool = False  # 武器專精每回合一次


class InitiativeEntry(BaseModel):
    combatant_type: Literal["character", "monster"]
    combatant_id: UUID
    initiative: int
    is_surprised: bool = False
    reaction_used: bool = False  # 反應跨回合追蹤（每輪重置）


class CombatState(BaseModel):
    """追蹤進行中的戰鬥遭遇狀態。"""

    round_number: int = 1
    current_turn_index: int = 0
    initiative_order: list[InitiativeEntry] = Field(default_factory=list)
    is_active: bool = False
    turn_state: TurnState = Field(default_factory=TurnState)
