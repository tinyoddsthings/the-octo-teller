"""T.O.T. Bone Engine 地圖與空間資料模型。"""

from __future__ import annotations

import math
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from tot.models.enums import (
    Ability,
    Condition,
    CoverType,
    DamageType,
    Fragility,
    Material,
    Size,
    SurfaceTrigger,
)
from tot.models.shapes import BoundingShape


class Position(BaseModel):
    """公尺座標（左下為原點，X 向右、Y 向上）。

    單位為公尺，精度到小數第二位（cm）。
    整數輸入由 Pydantic 自動轉為 float，地圖 JSON 格式不用改。
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0  # 高度（公尺），高於地面

    @field_validator("x", "y", "z", mode="before")
    @classmethod
    def _round_to_cm(cls, v: float | int) -> float:
        """四捨五入到小數第二位（cm 精度）。"""
        return round(float(v), 2)

    def distance_to(self, other: Position) -> float:
        """2D Euclidean 距離（公尺）。D&D 水平/垂直分開算。"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def distance_3d(self, other: Position) -> float:
        """3D Euclidean 距離（公尺）。"""
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def height_diff(self, other: Position) -> float:
        """兩點高度差的絕對值（公尺）。"""
        return abs(self.z - other.z)


class Entity(BaseModel):
    """地圖上的實體基底。

    座標單位為公尺（float），整數輸入自動轉 float。
    """

    id: str
    x: float
    y: float
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
    size: Size = Size.MEDIUM
    z: float = 0.0  # 高度（公尺）
    bounds: BoundingShape | None = None

    @model_validator(mode="after")
    def _set_default_bounds(self) -> Self:
        """bounds 未指定時，依 size 自動產生圓形碰撞區。"""
        if self.bounds is None:
            self.bounds = BoundingShape.from_size(self.size)
        return self


class LootEntry(BaseModel):
    """Prop 內的可拾取物品。"""

    item_id: str
    name: str
    description: str = ""
    quantity: int = 1
    value_gp: int = 0
    grants_key: str | None = None  # 拿取後獲得鑰匙（開鎖用）


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
    # ── 可摧毀屬性 ──
    material: Material | None = None  # None = 不可摧毀
    fragility: Fragility = Fragility.RESILIENT
    object_size: Size = Size.MEDIUM
    hp_max: int = 0  # 0 = 不可摧毀
    hp_current: int = 0
    object_ac: int = 15
    damage_immunities: list[DamageType] = Field(default_factory=list)
    damage_resistances: list[DamageType] = Field(default_factory=list)
    damage_threshold: int = 0
    bounds: BoundingShape | None = None  # None = 沿用 _PROP_HALF AABB
    # ── 探索互動屬性 ──
    interactable: bool = False  # 可互動（搜索/開啟）
    investigation_dc: int = 0  # 搜索 DC（0=明顯可見）
    interact_message: str = ""  # 互動時顯示的訊息
    is_searched: bool = False  # 已被搜索過
    is_looted: bool = False  # 已被拾取過
    loot_items: list[LootEntry] = Field(default_factory=list)
    # ── 鎖定屬性（門 Prop 用）──
    is_locked: bool = False  # 上鎖（需要鑰匙或開鎖檢定）
    lock_dc: int = 0  # 開鎖 DC（Thieves' Tools / STR 破門）
    key_item: str | None = None  # 對應鑰匙的 grants_key id
    # ── 地形屬性 ──
    terrain_type: str = ""  # hill / crevice / water / rubble
    elevation_m: float = 0.0  # 地形高度（正=高地，負=低窪）


class Wall(BaseModel):
    """牆壁障礙物（AABB 矩形）。"""

    x: float  # min-x（公尺）
    y: float  # min-y（公尺）
    width: float  # 寬（公尺）
    height: float  # 高（公尺）
    name: str = "wall"


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


class SurfaceEffect(BaseModel):
    """地圖上的持續性區域效果（如油脂術、糾纏術、精靈之火）。"""

    id: str
    name: str
    bounds: BoundingShape
    center_x: float
    center_y: float
    center_z: float = 0.0
    damage_dice: str = ""  # 例如 "2d4"
    damage_type: DamageType | None = None
    save_dc: int = 0
    save_ability: Ability | None = None
    save_half: bool = False  # 豁免成功是否半傷
    applies_condition: Condition | None = None
    is_difficult_terrain: bool = False
    triggers: list[SurfaceTrigger] = Field(default_factory=lambda: [SurfaceTrigger.ENTER])
    expires_at_second: int | None = None  # None = 永久
    remaining_rounds: int | None = None  # 向後相容：尚未接入 GameClock 時使用
    source_id: str | None = None  # 施放者 ID

    def contains_point(self, x: float, y: float) -> bool:
        """判斷點 (x, y) 是否在此效果範圍內。"""
        return self.bounds.contains_point(self.center_x, self.center_y, x, y)


class CoverResult(BaseModel):
    """掩蔽計算結果。"""

    cover_type: CoverType
    cover_objects: list[str] = Field(default_factory=list)
    primary_cover_id: str | None = None


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
    surfaces: list[SurfaceEffect] = Field(default_factory=list)

    def get_actor(self, combatant_id: UUID) -> Actor | None:
        """以 combatant_id 查詢 Actor。"""
        for a in self.actors:
            if a.combatant_id == combatant_id:
                return a
        return None

    def get_actor_position(self, combatant_id: UUID) -> Position | None:
        """以 combatant_id 查詢戰鬥者位置（公尺座標）。"""
        for a in self.actors:
            if a.combatant_id == combatant_id:
                return Position(x=a.x, y=a.y)
        return None

    def alive_actors(self) -> list[Actor]:
        """回傳所有存活的 Actor。"""
        return [a for a in self.actors if a.is_alive]
