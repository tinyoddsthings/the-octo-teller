"""T.O.T. Bone Engine 地圖與空間資料模型。"""

from __future__ import annotations

import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
