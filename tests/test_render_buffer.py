"""RenderBuffer 測試。

驗證圖層排序、紋理決定、牆壁/Props/角色的正確建構。
"""

from __future__ import annotations

from uuid import uuid4

from tot.models.map import Actor, MapManifest, MapState, Prop, Wall
from tot.models.shapes import BoundingShape
from tot.tui.render_buffer import (
    RenderBuffer,
    RenderLayer,
    TextureType,
    _actor_texture,
    _prop_texture,
    _size_to_render_bounds,
)

# ---------------------------------------------------------------------------
# 紋理決定邏輯
# ---------------------------------------------------------------------------


class TestTextureDecision:
    """_prop_texture / _actor_texture 單元測試。"""

    def test_blocking_circle_prop(self) -> None:
        """阻擋型圓形 prop → CIRCLE_FILL。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=True, bounds=BoundingShape.circle(0.5))
        assert _prop_texture(prop) == TextureType.CIRCLE_FILL

    def test_nonblocking_circle_prop(self) -> None:
        """非阻擋型圓形 prop → CIRCLE_OUTLINE。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=False, bounds=BoundingShape.circle(2.0))
        assert _prop_texture(prop) == TextureType.CIRCLE_OUTLINE

    def test_blocking_rect_prop(self) -> None:
        """阻擋型矩形 prop → FILL。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=True, bounds=BoundingShape.rect(1.5, 0.3))
        assert _prop_texture(prop) == TextureType.FILL

    def test_nonblocking_rect_prop(self) -> None:
        """非阻擋型矩形 prop → OUTLINE。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=False, bounds=BoundingShape.rect(3, 2))
        assert _prop_texture(prop) == TextureType.OUTLINE

    def test_no_bounds_decoration_outline(self) -> None:
        """無 bounds 的裝飾 prop → OUTLINE（外框渲染）。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=False, prop_type="decoration")
        assert _prop_texture(prop) == TextureType.OUTLINE

    def test_no_bounds_item_marker(self) -> None:
        """無 bounds 的物品 prop → MARKER（小標記，不是大外框）。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=False, prop_type="item")
        assert _prop_texture(prop) == TextureType.MARKER

    def test_no_bounds_interactable_marker(self) -> None:
        """無 bounds 的可互動 prop → MARKER。"""
        prop = Prop(id="p", x=0, y=0, is_blocking=False, interactable=True)
        assert _prop_texture(prop) == TextureType.MARKER

    def test_alive_pc(self) -> None:
        cid = uuid4()
        actor = Actor(id="a", x=0, y=0, combatant_id=cid, combatant_type="character")
        assert _actor_texture(actor) == TextureType.ACTOR_CIRCLE

    def test_alive_monster(self) -> None:
        cid = uuid4()
        actor = Actor(id="a", x=0, y=0, combatant_id=cid, combatant_type="monster")
        assert _actor_texture(actor) == TextureType.ACTOR_DIAMOND

    def test_dead_actor(self) -> None:
        cid = uuid4()
        actor = Actor(
            id="a", x=0, y=0, combatant_id=cid, combatant_type="character", is_alive=False
        )
        assert _actor_texture(actor) == TextureType.ACTOR_X


# ---------------------------------------------------------------------------
# RenderBuffer 建構
# ---------------------------------------------------------------------------


def _make_map_state(
    walls: list[Wall] | None = None,
    props: list[Prop] | None = None,
    actors: list[Actor] | None = None,
) -> MapState:
    """建立測試用 MapState。"""
    manifest = MapManifest(
        name="test",
        width=10.0,
        height=10.0,
        walls=walls or [],
        props=props or [],
    )
    return MapState(
        manifest=manifest,
        walls=[],  # manifest.walls 已含牆壁，不重複
        actors=actors or [],
    )


class TestRenderBufferBuild:
    """RenderBuffer.build() 測試。"""

    def test_empty_map(self) -> None:
        """空地圖 → 空 items。"""
        ms = _make_map_state()
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        assert buf.items == []

    def test_walls_as_fill(self) -> None:
        """牆壁轉為 WALL 層 FILL 紋理。"""
        ms = _make_map_state(walls=[Wall(x=0, y=0, width=2, height=1)])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        wall_items = [i for i in buf.items if i.layer == RenderLayer.WALL]
        assert len(wall_items) == 1
        assert wall_items[0].texture == TextureType.FILL
        assert wall_items[0].center_x == 1.0  # x + width/2
        assert wall_items[0].center_y == 0.5  # y + height/2

    def test_prop_with_bounds(self) -> None:
        """有 bounds 的 prop 使用真實形狀。"""
        prop = Prop(
            id="pillar",
            x=5.0,
            y=5.0,
            is_blocking=True,
            bounds=BoundingShape.circle(0.5),
        )
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)

        prop_items = [i for i in buf.items if i.layer == RenderLayer.PROP]
        assert len(prop_items) == 1
        assert prop_items[0].texture == TextureType.CIRCLE_FILL
        assert prop_items[0].bounds.radius_m == 0.5

    def test_terrain_on_terrain_layer(self) -> None:
        """有 terrain_type 的 prop 分到 TERRAIN 層。"""
        prop = Prop(
            id="pool",
            x=5.0,
            y=5.0,
            terrain_type="water",
            bounds=BoundingShape.circle(2.5),
        )
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)

        terrain_items = [i for i in buf.items if i.layer == RenderLayer.TERRAIN]
        assert len(terrain_items) == 1
        assert terrain_items[0].texture == TextureType.CIRCLE_OUTLINE

    def test_hidden_props_excluded(self) -> None:
        """隱藏 prop 不加入 buffer。"""
        prop = Prop(id="hidden", x=5.0, y=5.0, hidden=True)
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        assert len(buf.items) == 0

    def test_actor_items(self) -> None:
        """角色正確轉為 ACTOR 層。"""
        cid = uuid4()
        actor = Actor(id="hero", x=3.0, y=4.0, combatant_id=cid, combatant_type="character")
        ms = _make_map_state(actors=[actor])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)

        actor_items = [i for i in buf.items if i.layer == RenderLayer.ACTOR]
        assert len(actor_items) == 1
        assert actor_items[0].texture == TextureType.ACTOR_CIRCLE
        assert actor_items[0].center_x == 3.0

    def test_layer_ordering(self) -> None:
        """items 按圖層由下到上排序。"""
        wall = Wall(x=0, y=0, width=1, height=1)
        prop = Prop(id="p", x=5, y=5, is_blocking=True, bounds=BoundingShape.circle(0.5))
        terrain = Prop(id="t", x=3, y=3, terrain_type="rubble", bounds=BoundingShape.rect(2, 2))
        cid = uuid4()
        actor = Actor(id="a", x=7, y=7, combatant_id=cid, combatant_type="monster")
        ms = _make_map_state(walls=[wall], props=[prop, terrain], actors=[actor])

        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)

        layers = [i.layer for i in buf.items]
        assert layers == sorted(layers), f"圖層未按順序：{layers}"
        # 確認包含所有圖層
        layer_set = set(layers)
        assert RenderLayer.WALL in layer_set
        assert RenderLayer.TERRAIN in layer_set
        assert RenderLayer.PROP in layer_set
        assert RenderLayer.ACTOR in layer_set

    def test_viewport_defaults(self) -> None:
        """預設視口 = 全地圖。"""
        buf = RenderBuffer(15.0, 20.0)
        assert buf.viewport_w == 15.0
        assert buf.viewport_h == 20.0
        assert buf.camera_x == 7.5
        assert buf.camera_y == 10.0


# ---------------------------------------------------------------------------
# 無碰撞 prop 外框 + size-based bounds
# ---------------------------------------------------------------------------


class TestSizeToRenderBounds:
    """_size_to_render_bounds 測試。"""

    def test_tiny_bounds(self) -> None:
        from tot.models.enums import Size

        b = _size_to_render_bounds(Size.TINY)
        assert b.half_width_m == 0.75 / 2
        assert b.half_height_m == 0.75 / 2

    def test_medium_bounds(self) -> None:
        from tot.models.enums import Size

        b = _size_to_render_bounds(Size.MEDIUM)
        assert b.half_width_m == 1.5 / 2
        assert b.half_height_m == 1.5 / 2

    def test_large_bounds(self) -> None:
        from tot.models.enums import Size

        b = _size_to_render_bounds(Size.LARGE)
        assert b.half_width_m == 3.0 / 2
        assert b.half_height_m == 3.0 / 2


# ---------------------------------------------------------------------------
# 掩體標記 cover_label
# ---------------------------------------------------------------------------


class TestCoverLabel:
    """cover_bonus → cover_label 映射測試。"""

    def test_cover_half(self) -> None:
        """cover_bonus=2 → ½。"""
        prop = Prop(
            id="box",
            x=5.0,
            y=5.0,
            is_blocking=True,
            cover_bonus=2,
            bounds=BoundingShape.rect(1.0, 1.0),
        )
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        prop_items = [i for i in buf.items if i.layer == RenderLayer.PROP]
        assert len(prop_items) == 1
        assert prop_items[0].cover_label == "½"

    def test_cover_three_quarter(self) -> None:
        """cover_bonus=5 → ¾。"""
        prop = Prop(
            id="pillar",
            x=5.0,
            y=5.0,
            is_blocking=True,
            cover_bonus=5,
            bounds=BoundingShape.circle(0.5),
        )
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        prop_items = [i for i in buf.items if i.layer == RenderLayer.PROP]
        assert len(prop_items) == 1
        assert prop_items[0].cover_label == "¾"

    def test_cover_none(self) -> None:
        """cover_bonus=0 → 空字串。"""
        prop = Prop(
            id="item",
            x=5.0,
            y=5.0,
            is_blocking=False,
            cover_bonus=0,
            bounds=BoundingShape.rect(1.0, 1.0),
        )
        ms = _make_map_state(props=[prop])
        buf = RenderBuffer(10.0, 10.0)
        buf.build(ms)
        prop_items = [i for i in buf.items if i.layer == RenderLayer.PROP]
        assert len(prop_items) == 1
        assert prop_items[0].cover_label == ""
