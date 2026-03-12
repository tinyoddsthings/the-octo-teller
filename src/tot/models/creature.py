"""T.O.T. Bone Engine 生物資料模型（角色、怪物、武器、物品）。"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from tot.models.enums import (
    SKILL_ABILITY_MAP,
    Ability,
    Condition,
    CreatureType,
    DamageType,
    Size,
    Skill,
    WeaponMastery,
    WeaponProperty,
)


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


class ActiveCondition(BaseModel):
    """目前影響生物的狀態效果。"""

    condition: Condition
    source: str = ""
    remaining_rounds: int | None = None  # None = 無限期 / 直到被移除
    exhaustion_level: int = 0  # 僅用於力竭（1-6 級）


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


class Weapon(BaseModel):
    name: str
    damage_dice: str  # 例如 "1d8"
    damage_type: DamageType
    properties: list[WeaponProperty] = Field(default_factory=list)
    range_normal: float = 1.5  # 公尺；1.5 = 近戰、3.0 = 長觸及
    range_long: float | None = None  # 遠程/投擲武器的長射程（公尺）
    is_martial: bool = False
    mastery: WeaponMastery | None = None  # 2024 武器專精

    @computed_field
    @property
    def is_ranged(self) -> bool:
        return self.range_normal > 1.5

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
    spell_dc: int = 0  # 法術豁免 DC（8 + 熟練 + 施法屬性修正）
    spell_attack: int = 0  # 法術攻擊加值（熟練 + 施法屬性修正）
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

    is_ai_controlled: bool = False

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


class MonsterAction(BaseModel):
    name: str
    attack_bonus: int | None = None  # None = 無攻擊骰（豁免制法術）
    damage_dice: str = ""
    damage_type: DamageType | None = None
    reach: float = 1.5  # 觸及距離（公尺）
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
