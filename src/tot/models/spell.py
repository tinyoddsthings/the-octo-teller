"""T.O.T. Bone Engine 法術資料模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tot.models.enums import (
    Ability,
    AoeShape,
    Condition,
    DamageType,
    SpellAttackType,
    SpellEffectType,
    SpellSchool,
)


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
