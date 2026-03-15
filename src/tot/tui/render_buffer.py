"""RenderBuffer — 地圖渲染中介層。

將 MapState 的空間語意轉為按圖層排序的 RenderItem 列表，
解耦「什麼要畫」與「怎麼畫到 drawille」。

圖層由下到上：GRID → TERRAIN → WALL → PROP → ACTOR → AOE。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from uuid import UUID

from tot.models.enums import ShapeType, Size
from tot.models.map import Actor, MapState, Prop
from tot.models.shapes import BoundingShape
from tot.tui.tiles import resolve_prop_tile


class RenderLayer(IntEnum):
    """渲染圖層（由下到上）。"""

    GRID = 0
    TERRAIN = 1
    WALL = 2
    PROP = 3
    ACTOR = 4
    AOE = 5


class TextureType(StrEnum):
    """紋理繪製方式。"""

    FILL = "fill"  # 填滿矩形（阻擋型方形 prop）
    OUTLINE = "outline"  # 矩形外框（非阻擋型方形 prop）
    CIRCLE_FILL = "circle_fill"  # 填滿圓（阻擋型圓形 prop）
    CIRCLE_OUTLINE = "circle_outline"  # 圓形外框（非阻擋型圓形 prop）
    ACTOR_CIRCLE = "actor_circle"  # PC（圓形）
    ACTOR_DIAMOND = "actor_diamond"  # 怪物（菱形）
    ACTOR_X = "actor_x"  # 死亡（X 形）
    SPARSE = "sparse"  # AoE 稀疏填充


@dataclass
class RenderItem:
    """一個待渲染的圖元。"""

    entity_id: str
    layer: RenderLayer
    center_x: float  # 公尺座標
    center_y: float
    bounds: BoundingShape  # 形狀 + 尺寸
    texture: TextureType
    style: str = ""  # Rich color style
    label: str = ""  # 文字標籤


# 預設 prop 碰撞 fallback（1.5×1.5m）
_DEFAULT_PROP_BOUNDS = BoundingShape.rect(1.5, 1.5)


def _prop_texture(prop: Prop) -> TextureType:
    """依 prop 的形狀和阻擋屬性決定紋理。"""
    is_circle = prop.bounds is not None and prop.bounds.shape_type == ShapeType.CIRCLE
    # 門一律用 FILL，確保碰撞外框始終繪製（開門/鎖門只靠顏色區分）
    if prop.prop_type == "door" or prop.is_blocking:
        return TextureType.CIRCLE_FILL if is_circle else TextureType.FILL
    return TextureType.CIRCLE_OUTLINE if is_circle else TextureType.OUTLINE


def _actor_texture(actor: Actor) -> TextureType:
    """依 actor 狀態決定紋理。"""
    if not actor.is_alive:
        return TextureType.ACTOR_X
    if actor.combatant_type == "character":
        return TextureType.ACTOR_CIRCLE
    return TextureType.ACTOR_DIAMOND


@dataclass
class RenderBuffer:
    """地圖渲染中介緩衝區。

    build() 從 MapState 收集所有可見圖元，按圖層排序。
    canvas 層只需遍歷 items 逐項繪製。
    """

    world_w: float
    world_h: float
    items: list[RenderItem] = field(default_factory=list)
    # 視口參數（此次預設全地圖，未來擴充用）
    camera_x: float = 0.0
    camera_y: float = 0.0
    viewport_w: float = 0.0
    viewport_h: float = 0.0

    def __post_init__(self) -> None:
        if self.camera_x == 0.0:
            self.camera_x = self.world_w / 2
        if self.camera_y == 0.0:
            self.camera_y = self.world_h / 2
        if self.viewport_w == 0.0:
            self.viewport_w = self.world_w
        if self.viewport_h == 0.0:
            self.viewport_h = self.world_h

    def build(
        self,
        ms: MapState,
        combatant_map: dict[UUID, object] | None = None,
        aoe: object | None = None,
    ) -> None:
        """從 MapState 建構渲染項目。

        Args:
            ms: 地圖狀態
            combatant_map: UUID → Combatant 對照（用於標籤和樣式）
            aoe: AoeOverlay（暫不處理，由 canvas 直接繪製）
        """
        self.items.clear()
        self._add_walls(ms)
        self._add_props(ms)
        self._add_actors(ms, combatant_map or {})
        self.items.sort(key=lambda i: i.layer)

    def _add_walls(self, ms: MapState) -> None:
        """加入牆壁圖元。"""
        all_walls = [*ms.manifest.walls, *ms.walls]
        for wall in all_walls:
            self.items.append(
                RenderItem(
                    entity_id=wall.name,
                    layer=RenderLayer.WALL,
                    center_x=wall.x + wall.width / 2,
                    center_y=wall.y + wall.height / 2,
                    bounds=BoundingShape.rect(wall.width, wall.height),
                    texture=TextureType.FILL,
                    style="bright_white",
                )
            )

    def _add_props(self, ms: MapState) -> None:
        """加入 prop 圖元（manifest + runtime）。"""
        all_props = [*ms.manifest.props, *ms.props]
        for prop in all_props:
            if prop.hidden:
                continue
            bounds = prop.bounds if prop.bounds is not None else _DEFAULT_PROP_BOUNDS
            is_terrain = bool(prop.terrain_type)
            self.items.append(
                RenderItem(
                    entity_id=prop.id,
                    layer=RenderLayer.TERRAIN if is_terrain else RenderLayer.PROP,
                    center_x=prop.x,
                    center_y=prop.y,
                    bounds=bounds,
                    texture=_prop_texture(prop),
                    style="cyan"
                    if is_terrain
                    else resolve_prop_tile(prop.prop_type, prop.is_blocking, prop.interactable).fg,
                )
            )

    def _add_actors(self, ms: MapState, combatant_map: dict[UUID, object]) -> None:
        """加入角色圖元（含陣營色彩）。"""
        for actor in ms.actors:
            bounds = actor.bounds or BoundingShape.from_size(actor.size or Size.MEDIUM)
            # 依陣營/狀態決定色彩
            if not actor.is_alive:
                style = "dim"
            elif actor.combatant_type == "character":
                combatant = combatant_map.get(actor.combatant_id)
                if combatant and getattr(combatant, "is_ai_controlled", False):
                    style = "bold blue"  # 隊友
                else:
                    style = "bold green"  # 主角
            else:
                style = "bold red"  # 怪物
            self.items.append(
                RenderItem(
                    entity_id=actor.id,
                    layer=RenderLayer.ACTOR,
                    center_x=actor.x,
                    center_y=actor.y,
                    bounds=bounds,
                    texture=_actor_texture(actor),
                    style=style,
                )
            )
