"""T.O.T. Bone Engine 法術資料模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from tot.models.enums import (
    Ability,
    AoeShape,
    Condition,
    DamageType,
    SpellAttackType,
    SpellEffectType,
    SpellSchool,
)


class SpellComponents(BaseModel):
    """法術成分子模型。"""

    required: list[str] = Field(default_factory=list)  # ["V", "S", "M"]
    material_description: str = ""  # 材料描述（如「價值 50gp 的鑽石粉」）
    material_cost_gp: float = 0.0  # 材料金額（gp），0 = 可用法器替代
    material_consumed: bool = False  # 施法後材料是否消耗


class SpellAoe(BaseModel):
    """AoE 區域子模型。"""

    shape: AoeShape | None = None  # None = 非 AoE 法術
    radius_ft: int = 0  # 球形/圓形半徑（呎）
    length_ft: int = 0  # 線形長度 / 錐形長度（呎）
    width_ft: int = 0  # 線形寬度 / 立方邊長（呎）


class SpellUpcast(BaseModel):
    """升環子模型。"""

    dice: str = ""  # 升環時每環增加的骰子（如 "1d6"）
    additional_targets: int = 0  # 每升一環多幾個目標


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

    # 子模型
    components: SpellComponents = Field(default_factory=SpellComponents)
    aoe: SpellAoe = Field(default_factory=SpellAoe)
    upcast: SpellUpcast = Field(default_factory=SpellUpcast)

    # 目標
    max_targets: int = 1

    classes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _flat_to_nested(cls, data: Any) -> Any:
        """支援舊版 flat JSON 格式 → nested 子模型映射。"""
        if not isinstance(data, dict):
            return data

        # --- components ---
        if "components" in data and isinstance(data["components"], list):
            comp: dict[str, Any] = {"required": data.pop("components")}
            for key, nested_key in [
                ("material_description", "material_description"),
                ("material_cost", "material_cost_gp"),
                ("material_consumed", "material_consumed"),
            ]:
                if key in data:
                    comp[nested_key] = data.pop(key)
            data["components"] = comp

        # --- aoe ---
        if "aoe_shape" in data or "aoe_radius_ft" in data:
            aoe: dict[str, Any] = {}
            for key, nested_key in [
                ("aoe_shape", "shape"),
                ("aoe_radius_ft", "radius_ft"),
                ("aoe_length_ft", "length_ft"),
                ("aoe_width_ft", "width_ft"),
            ]:
                if key in data:
                    aoe[nested_key] = data.pop(key)
            data["aoe"] = aoe

        # --- upcast ---
        if "upcast_dice" in data or "upcast_additional_targets" in data:
            up: dict[str, Any] = {}
            for key, nested_key in [
                ("upcast_dice", "dice"),
                ("upcast_additional_targets", "additional_targets"),
            ]:
                if key in data:
                    up[nested_key] = data.pop(key)
            data["upcast"] = up

        # 移除已刪除的死欄位（向前相容）
        for dead_key in ("upcast_duration_map", "upcast_no_concentration_at", "upcast_aoe_bonus"):
            data.pop(dead_key, None)

        return data
