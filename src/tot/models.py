"""T.O.T. Bone Engine 核心 Pydantic 資料模型。

所有跨模組的資料結構都定義在這裡。Bone Engine 是純確定性的
——不呼叫 LLM、除了骰子以外沒有隨機性。
基於 D&D 2024 (5.5e) 規則。
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, field_validator

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
    DISENGAGING = "Disengaging"  # 追蹤撤離動作效果（1 輪）
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
    SILENCED = "Silenced"  # Silence 法術範圍內，無法施放 V 成分法術
    WEAKENED = "Weakened"  # 2024 新增，傷害減半


class Size(StrEnum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"


# 體型 → 碰撞半徑（公尺），D&D 5e 標準空間佔據的一半
SIZE_RADIUS_M: dict[Size, float] = {
    Size.TINY: 0.15,  # 0.3m 直徑
    Size.SMALL: 0.375,  # 0.75m 直徑（半格）
    Size.MEDIUM: 0.75,  # 1.5m 直徑（1 格）
    Size.LARGE: 1.5,  # 3.0m 直徑（2 格）
    Size.HUGE: 2.25,  # 4.5m 直徑（3 格）
    Size.GARGANTUAN: 3.0,  # 6.0m 直徑（4 格）
}

# 體型序號，用於穿越規則比較（差 ≥ 2 級可穿越敵對）
SIZE_ORDER: dict[Size, int] = {
    Size.TINY: 0,
    Size.SMALL: 1,
    Size.MEDIUM: 2,
    Size.LARGE: 3,
    Size.HUGE: 4,
    Size.GARGANTUAN: 5,
}


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
    HALF = "Half"  # +2 AC 與 DEX 豁免
    THREE_QUARTERS = "Three-Quarters"  # +5 AC 與 DEX 豁免
    TOTAL = "Total"  # 無法被直接攻擊


class WeaponMastery(StrEnum):
    """2024 武器專精效果。"""

    CLEAVE = "Cleave"  # 命中後對相鄰另一目標造成屬性修正傷害
    GRAZE = "Graze"  # 未命中仍造成屬性修正傷害
    NICK = "Nick"  # 額外附贈動作攻擊
    PUSH = "Push"  # 命中後推開目標 3m
    SAP = "Sap"  # 命中後目標下次攻擊劣勢
    SLOW = "Slow"  # 命中後減速 3m
    TOPPLE = "Topple"  # 命中後目標 CON 豁免，失敗倒地
    VEX = "Vex"  # 命中後下次攻擊同目標優勢


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


class SpellAttackType(StrEnum):
    """法術攻擊類型。"""

    NONE = "none"  # 無攻擊擲骰（豁免型或自動命中）
    MELEE = "melee"  # 近戰法術攻擊
    RANGED = "ranged"  # 遠程法術攻擊


class SpellEffectType(StrEnum):
    """法術主要效果類型。"""

    DAMAGE = "damage"
    HEALING = "healing"
    CONDITION = "condition"  # 純施加狀態
    BUFF = "buff"  # 增益效果
    UTILITY = "utility"  # 非戰鬥用途


class AoeShape(StrEnum):
    """AoE 形狀。"""

    SPHERE = "sphere"  # 球形（2D 平面 = 圓形），如火球術
    CONE = "cone"  # 錐形，如燃燒之手
    LINE = "line"  # 線形，如閃電束
    CUBE = "cube"  # 方形，如雷鳴波


class Spell(BaseModel):
    name: str  # 中文名
    en_name: str = ""  # 英文名（可選，供查詢用）
    level: int = Field(ge=0, le=9)  # 0 = 戲法
    school: SpellSchool
    casting_time: str = "1 action"
    range: str = "Self"
    duration: str = "Instantaneous"
    concentration: bool = False
    ritual: bool = False
    description: str = ""
    effect_type: SpellEffectType = SpellEffectType.DAMAGE
    attack_type: SpellAttackType = SpellAttackType.NONE
    damage_dice: str = ""  # 例如 "1d10"，無傷害則為空字串
    damage_type: DamageType | None = None
    healing_dice: str = ""  # 例如 "2d8"，無治療則為空字串
    save_ability: Ability | None = None  # 需要豁免的法術
    save_half: bool = False  # 豁免成功時是否半傷
    applies_condition: Condition | None = None  # 法術施加的狀態
    # 成分
    components: list[str] = Field(default_factory=list)  # ["V", "S", "M"]
    material_description: str = ""  # 材料描述（如「價值 50gp 的鑽石粉」）
    material_cost: int = 0  # 材料金額（gp），0 = 可用法器替代
    material_consumed: bool = False  # 施法後材料是否消耗

    # 升環
    upcast_dice: str = ""  # 升環時每環增加的骰子（如 "1d6"）
    upcast_additional_targets: int = 0  # 每升一環多幾個目標
    upcast_duration_map: dict[int, int] = Field(default_factory=dict)  # {環數: 分鐘}
    upcast_no_concentration_at: int | None = None  # 達到此環數時不需專注
    upcast_aoe_bonus: int = 0  # 每升一環增加的半徑（呎）

    # AoE
    aoe_shape: AoeShape | None = None  # None = 非 AoE 法術
    aoe_radius_ft: int = 0  # 球形/圓形半徑（呎）
    aoe_length_ft: int = 0  # 線形長度 / 錐形長度（呎）
    aoe_width_ft: int = 0  # 線形寬度 / 立方邊長（呎）

    # 目標
    max_targets: int = 1

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


# ---------------------------------------------------------------------------
# 怪物
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 戰鬥狀態
# ---------------------------------------------------------------------------

CombatantRef = tuple[Literal["character", "monster"], UUID]


# ---------------------------------------------------------------------------
# 地圖座標系統
# ---------------------------------------------------------------------------


class Position(BaseModel):
    """公尺座標（左下為原點，X 向右、Y 向上）。

    單位為公尺，精度到小數第二位（cm）。
    整數輸入由 Pydantic 自動轉為 float，地圖 JSON 格式不用改。
    """

    x: float = 0.0
    y: float = 0.0

    @field_validator("x", "y", mode="before")
    @classmethod
    def _round_to_cm(cls, v: float | int) -> float:
        """四捨五入到小數第二位（cm 精度）。"""
        return round(float(v), 2)

    def distance_to(self, other: Position) -> float:
        """Euclidean 距離（公尺）。"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


class Entity(BaseModel):
    """地圖上的實體基底。

    座標單位為公尺（float），整數輸入自動轉 float。
    """

    id: str
    x: float
    y: float
    symbol: str = "?"  # ASCII 單字元
    is_blocking: bool = False
    name: str = ""

    @field_validator("x", "y", mode="before")
    @classmethod
    def _round_to_cm(cls, v: float | int) -> float:
        return round(float(v), 2)


class Actor(Entity):
    """地圖上的戰鬥者（參照 Character/Monster，不繼承）。"""

    combatant_id: UUID
    combatant_type: Literal["character", "monster"]
    is_blocking: bool = True  # 生物預設阻擋通行
    is_alive: bool = True


class Prop(Entity):
    """地圖上的靜態物件。

    is_blocking 決定是否阻擋移動與視線：
    - wall (🧱)：is_blocking=True，擋移動、擋視線
    - door (🚪)：關門 is_blocking=True，開門改為 False
    - trap (⚠️)：is_blocking=False，不擋路，踩上去由上層觸發
    - item (💎)：is_blocking=False，可撿取的掉落物
    - decoration：is_blocking 視設計而定（桌椅可擋可不擋）

    cover_bonus 決定作為掩體時提供的 AC 加值：
    - 0：無掩蔽（陷阱、掉落物）
    - 2：半掩蔽（木箱、矮牆、家具）
    - 5：3/4 掩蔽（石柱、厚牆壁）
    - 99：全掩蔽（完整牆壁，完全阻擋攻擊）
    """

    prop_type: str = "decoration"  # wall / door / trap / item / decoration
    hidden: bool = False  # 隱藏物件（未被發現的陷阱等）
    cover_bonus: int = 0  # 作為掩體的 AC 加值


class Wall(BaseModel):
    """牆壁障礙物（AABB 矩形）。"""

    x: float  # min-x（公尺）
    y: float  # min-y（公尺）
    width: float  # 寬（公尺）
    height: float  # 高（公尺）
    name: str = "wall"
    symbol: str = "#"


# ---------------------------------------------------------------------------
# 區域拓樸
# ---------------------------------------------------------------------------


class Zone(BaseModel):
    """命名區域，提供敘事語境給 Narrator。"""

    name: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    description: str = ""


class ZoneConnection(BaseModel):
    """區域間的連接。"""

    from_zone: str
    to_zone: str
    via: str = ""  # 對應 Prop.id（門、通道）


# ---------------------------------------------------------------------------
# 地圖定義與即時狀態
# ---------------------------------------------------------------------------


class MapManifest(BaseModel):
    """地圖靜態定義，從 JSON 載入。"""

    name: str
    width: float  # 地圖寬度（公尺）
    height: float  # 地圖高度（公尺）
    walls: list[Wall] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    zone_connections: list[ZoneConnection] = Field(default_factory=list)
    spawn_points: dict[str, list[Position]] = Field(default_factory=dict)


class MapState(BaseModel):
    """戰鬥中的即時地圖狀態。"""

    manifest: MapManifest
    walls: list[Wall] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)  # 執行期動態追加的物件


class MoveEvent(BaseModel):
    """移動產生的事件（供上層處理）。"""

    event_type: str  # "opportunity_attack" | "difficult_terrain"
    trigger_actor_id: str = ""  # 觸發 OA 的敵方 Actor id
    message: str = ""


class MoveResult(BaseModel):
    """move_entity 的回傳結果。"""

    success: bool
    speed_remaining: float
    events: list[MoveEvent] = Field(default_factory=list)


class AoePreview(BaseModel):
    """AoE 瞄準預覽結果。"""

    center: Position
    hit_enemies: list[str] = Field(default_factory=list)  # Actor.id 列表
    hit_allies: list[str] = Field(default_factory=list)  # 友軍誤傷 Actor.id
    all_hit_names: list[str] = Field(default_factory=list)  # 可讀名稱列表
    message: str = ""  # 預覽摘要


class TurnState(BaseModel):
    """單一回合內的動作經濟追蹤。"""

    action_used: bool = False
    bonus_action_used: bool = False
    mastery_used: bool = False  # 武器專精每回合一次
    movement_remaining: float = 0.0  # 剩餘移動距離（公尺），回合開始時由 TUI 設為 speed


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
    map_state: MapState | None = None  # 有地圖時啟用空間系統


# ---------------------------------------------------------------------------
# Pointcrawl 探索系統
# ---------------------------------------------------------------------------


class NodeType(StrEnum):
    """探索節點類型。"""

    ROOM = "room"  # 地城房間
    CORRIDOR = "corridor"  # 走廊
    POI = "poi"  # 城鎮興趣點
    TOWN = "town"  # 城鎮（世界圖層）
    DUNGEON = "dungeon"  # 地城入口（世界圖層）
    LANDMARK = "landmark"  # 自然地標


class MapScale(StrEnum):
    """探索地圖尺度，決定時間單位。"""

    DUNGEON = "dungeon"  # 分鐘
    TOWN = "town"  # 小時
    WORLD = "world"  # 天


class EncounterType(StrEnum):
    """遭遇類型。"""

    SURPRISE = "surprise"  # 玩家偷襲成功 → 擴大佈陣區 + 敵人劣勢先攻
    NORMAL = "normal"  # 正常遭遇 → 標準佈陣區
    AMBUSH = "ambush"  # 敵人伏擊 → 跳過佈陣，玩家劣勢先攻


class EncounterResult(BaseModel):
    """潛行對抗察覺的判定結果。"""

    encounter_type: EncounterType
    stealth_rolls: dict[str, int] = Field(default_factory=dict)
    enemy_perception: int = 0
    surprised_ids: set[UUID] = Field(default_factory=set)
    message: str = ""


class DeploymentState(BaseModel):
    """佈陣階段狀態——戰鬥開始前的角色放置。"""

    map_state: MapState
    spawn_zone: list[Position] = Field(default_factory=list)
    placements: dict[str, Position] = Field(default_factory=dict)
    encounter: EncounterResult
    is_confirmed: bool = False


class ExplorationNode(BaseModel):
    """Pointcrawl 節點——玩家可到達的地點。"""

    id: str
    name: str
    node_type: NodeType
    description: str = ""  # 給 Narrator 的敘事素材

    # 與戰鬥地圖的銜接
    combat_map: str | None = None  # MapManifest JSON 檔名（遭遇戰鬥時載入）

    # 狀態
    is_discovered: bool = True  # 玩家是否已知此節點
    is_visited: bool = False  # 玩家是否已到過

    # 城鎮專用：內含 POI 子節點
    pois: list[ExplorationNode] = Field(default_factory=list)

    # 敘事用
    ambient: str = ""  # 環境氛圍描述（聲音、氣味…）
    npcs: list[str] = Field(default_factory=list)  # 此處可遇到的 NPC id


class ExplorationEdge(BaseModel):
    """Pointcrawl 路徑——連接兩個節點。"""

    id: str
    from_node_id: str
    to_node_id: str
    name: str = ""  # 例如：「鏽蝕鐵門」「泥濘商道」

    # 通行條件
    is_discovered: bool = True  # 是否對玩家可見
    is_locked: bool = False  # 上鎖（需要盜賊檢定或鑰匙）
    lock_dc: int = 0  # 開鎖 DC
    key_item: str | None = None  # 可用鑰匙物品 id
    hidden_dc: int = 0  # 隱藏通道的偵察 DC（0=不隱藏）
    is_one_way: bool = False  # 單向通道
    break_dc: int = 0  # STR DC 破門（0=不可破壞）
    noise_on_force: bool = True  # 破門時是否產生噪音

    # 世界圖層旅行參數
    distance_days: float = 0  # 旅行天數（世界圖層）
    distance_minutes: int = 0  # 移動分鐘數（地城圖層）
    danger_level: int = 0  # 危險等級 1-10（影響隨機遭遇）
    terrain_type: str = ""  # 地形（swamp/forest/mountain…）

    # 狀態
    is_blocked: bool = False  # 坍塌、封鎖等


class ExplorationMap(BaseModel):
    """Pointcrawl 拓樸地圖（一張地城/一座城鎮/一個世界）。"""

    id: str
    name: str
    scale: MapScale
    nodes: list[ExplorationNode] = Field(default_factory=list)
    edges: list[ExplorationEdge] = Field(default_factory=list)

    # 入口：玩家進入此地圖時的起始節點
    entry_node_id: str = ""


class MapStackEntry(BaseModel):
    """子地圖堆疊中的一層（記住從哪裡進來）。"""

    map_id: str
    node_id: str  # 進入子地圖前所在的節點


class ExplorationState(BaseModel):
    """玩家在 Pointcrawl 系統中的即時位置。"""

    current_map_id: str  # 目前所在的 ExplorationMap
    current_node_id: str  # 目前所在的節點
    elapsed_minutes: int = 0  # 場景經過時間
    discovered_nodes: set[str] = Field(default_factory=set)
    discovered_edges: set[str] = Field(default_factory=set)

    # 子地圖堆疊：從世界→地城→房間，像 call stack
    map_stack: list[MapStackEntry] = Field(default_factory=list)
