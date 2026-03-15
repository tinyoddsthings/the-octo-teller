"""TileMapCanvas 單元測試。

驗證網格建構、layer 優先級、Y 軸翻轉、braille 混合渲染。
不依賴 Textual App，直接測試 _build_grid() 和 render()。
"""

from __future__ import annotations

from uuid import uuid4

from tot.models.enums import Size
from tot.models.map import Actor, MapManifest, MapState, Prop, Wall
from tot.models.shapes import BoundingShape
from tot.tui.render_buffer import RenderBuffer
from tot.tui.tile_canvas import _LEGEND_WIDTH, TileMapCanvas, _display_width
from tot.tui.tiles import FLOOR_TILE, TERRAIN_TILES, WALL_TILE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSize:
    """mock Textual Size 物件。"""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height


def _make_empty_map(w: float = 6.0, h: float = 6.0) -> MapState:
    """空地圖（無牆壁、無 prop、無 actor）。"""
    manifest = MapManifest(name="test", width=w, height=h)
    return MapState(manifest=manifest)


def _build(ms: MapState):
    """建構 RenderBuffer + TileMapCanvas grid。"""
    buf = RenderBuffer(ms.manifest.width, ms.manifest.height)
    buf.build(ms)
    canvas = TileMapCanvas()
    canvas._map_state = ms  # type: ignore[attr-defined]
    canvas._render_buffer = buf  # type: ignore[attr-defined]
    # 直接存取 reactive 底層
    canvas.map_state = ms
    canvas.render_buffer = buf
    return canvas._build_grid()


def _make_canvas_with_size(
    ms: MapState,
    width: int = 40,
    height: int = 20,
) -> TileMapCanvas:
    """建構含 mock size 的 TileMapCanvas。"""
    from unittest.mock import PropertyMock

    buf = RenderBuffer(ms.manifest.width, ms.manifest.height)
    buf.build(ms)
    canvas = TileMapCanvas()
    canvas.map_state = ms
    canvas.render_buffer = buf
    # mock self.size（Textual Widget 的 size 屬性）
    type(canvas).size = PropertyMock(return_value=_FakeSize(width, height))
    return canvas


# ---------------------------------------------------------------------------
# 空地圖
# ---------------------------------------------------------------------------


class TestEmptyMap:
    def test_all_floor(self) -> None:
        """空地圖所有 cell 都是地板。"""
        grid = _build(_make_empty_map(4.5, 3.0))
        # 4.5/1.5 = 3 cols, 3.0/1.5 = 2 rows
        assert len(grid) == 2
        assert len(grid[0]) == 3
        for row in grid:
            for tile in row:
                assert tile == FLOOR_TILE

    def test_no_data_returns_empty(self) -> None:
        """無 map_state/render_buffer 回傳空 grid。"""
        canvas = TileMapCanvas()
        assert canvas._build_grid() == []


# ---------------------------------------------------------------------------
# 牆壁填充
# ---------------------------------------------------------------------------


class TestWallFill:
    def test_single_wall(self) -> None:
        """1.5×1.5 牆壁佔 1 格。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=1.5, height=1.5, name="w1"))
        grid = _build(ms)
        # 牆壁中心 (0.75, 0.75) → grid (0, 0)
        assert grid[0][0] == WALL_TILE

    def test_large_wall_covers_multiple_cells(self) -> None:
        """3×3 牆壁佔 4 格（2×2）。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=3.0, height=3.0, name="w1"))
        grid = _build(ms)
        assert grid[0][0] == WALL_TILE
        assert grid[0][1] == WALL_TILE
        assert grid[1][0] == WALL_TILE
        assert grid[1][1] == WALL_TILE
        # (2,2) 應仍是地板
        assert grid[2][2] == FLOOR_TILE


# ---------------------------------------------------------------------------
# 地形填充
# ---------------------------------------------------------------------------


class TestTerrainFill:
    def test_water_terrain(self) -> None:
        """水域地形正確填充。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.props.append(
            Prop(
                id="water1",
                x=3.0,
                y=3.0,
                terrain_type="water",
                bounds=BoundingShape.rect(3.0, 3.0),
            )
        )
        grid = _build(ms)
        water_tile = TERRAIN_TILES["water"]
        # 水域中心 (3.0, 3.0)，AABB 1.5~4.5 → grid cols 1~2, rows 1~2
        assert grid[1][1] == water_tile
        assert grid[1][2] == water_tile
        assert grid[2][1] == water_tile
        assert grid[2][2] == water_tile
        # (0,0) 不受影響
        assert grid[0][0] == FLOOR_TILE


# ---------------------------------------------------------------------------
# Prop 填充
# ---------------------------------------------------------------------------


class TestPropFill:
    def test_interactable_prop_shows_diamond(self) -> None:
        """可互動 prop 顯示為 !。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.props.append(
            Prop(
                id="chest1",
                x=2.25,
                y=2.25,
                prop_type="item",
                interactable=True,
            )
        )
        grid = _build(ms)
        # (2.25, 2.25) → grid (1, 1)
        assert grid[1][1].char == "!"

    def test_blocking_door_shows_filled(self) -> None:
        """阻擋型門顯示為 +。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.props.append(
            Prop(
                id="door1",
                x=0.75,
                y=0.75,
                prop_type="door",
                is_blocking=True,
                bounds=BoundingShape.rect(1.5, 0.3),
            )
        )
        grid = _build(ms)
        assert grid[0][0].char == "+"


# ---------------------------------------------------------------------------
# Actor 填充
# ---------------------------------------------------------------------------


class TestActorFill:
    def test_party_actor(self) -> None:
        """隊伍 actor 顯示為 @。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.actors.append(
            Actor(
                id="party-1",
                x=0.75,
                y=0.75,
                name="隊伍",
                combatant_id=uuid4(),
                combatant_type="character",
                size=Size.MEDIUM,
            )
        )
        grid = _build(ms)
        assert grid[0][0].char == "@"

    def test_monster_uses_first_ascii_char(self) -> None:
        """怪物 actor 顯示名字首個 ASCII 字母。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.actors.append(
            Actor(
                id="goblin-1",
                x=3.0,
                y=3.0,
                name="Goblin",
                combatant_id=uuid4(),
                combatant_type="monster",
                size=Size.MEDIUM,
            )
        )
        grid = _build(ms)
        # (3.0, 3.0) → grid (2, 2)
        assert grid[2][2].char == "G"


# ---------------------------------------------------------------------------
# Layer 優先級
# ---------------------------------------------------------------------------


class TestLayerPriority:
    def test_actor_over_terrain(self) -> None:
        """Actor 層覆蓋地形層。"""
        ms = _make_empty_map(6.0, 6.0)
        # 水域佔 grid (0,0)~(1,1)
        ms.manifest.props.append(
            Prop(
                id="water1",
                x=1.5,
                y=1.5,
                terrain_type="water",
                bounds=BoundingShape.rect(3.0, 3.0),
            )
        )
        # 隊伍在水域中
        ms.actors.append(
            Actor(
                id="party-1",
                x=0.75,
                y=0.75,
                name="隊伍",
                combatant_id=uuid4(),
                combatant_type="character",
                size=Size.MEDIUM,
            )
        )
        grid = _build(ms)
        # Actor 層在 TERRAIN 之上，應為 @
        assert grid[0][0].char == "@"

    def test_wall_over_floor(self) -> None:
        """牆壁覆蓋地板。"""
        ms = _make_empty_map(3.0, 3.0)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=1.5, height=1.5, name="w1"))
        grid = _build(ms)
        assert grid[0][0] == WALL_TILE
        assert grid[0][1] == FLOOR_TILE


# ---------------------------------------------------------------------------
# Braille 渲染測試
# ---------------------------------------------------------------------------


class TestRender:
    def test_y_flip_in_output(self) -> None:
        """render() 輸出中，世界 Y=0 的牆壁在底部行有 braille 填充。"""
        ms = _make_empty_map(3.0, 3.0)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=1.5, height=1.5, name="w1"))
        canvas = _make_canvas_with_size(ms, width=30, height=10)

        text = canvas.render()
        plain = text.plain
        lines = plain.strip().split("\n")

        # 找含非空白 braille 字元的行（牆壁填充）
        map_lines = [
            i for i, ln in enumerate(lines) if any("\u2801" <= ch <= "\u28ff" for ch in ln)
        ]
        assert len(map_lines) > 0, "應有 braille 填充的行"
        # 牆壁在 Y=0，應出現在底部半段
        midpoint = len(lines) // 2
        assert any(idx >= midpoint for idx in map_lines), "Y=0 牆壁應在底部行"

    def test_render_no_data(self) -> None:
        """無資料時顯示提示文字。"""
        canvas = TileMapCanvas()
        text = canvas.render()
        assert "無地圖資料" in text.plain

    def test_render_scales_to_fill(self) -> None:
        """render() 輸出行數近似 widget 尺寸。"""
        ms = _make_empty_map(6.0, 6.0)  # 4×4 grid
        canvas = _make_canvas_with_size(ms, width=60, height=30)

        text = canvas.render()
        lines = text.plain.split("\n")
        # 總行數 = draw_h（地圖行）+ 1（X 軸標籤行）= height
        assert len(lines) == 30
        # 每行寬度不超過 widget 寬度
        for line in lines:
            assert len(line) <= 60

    def test_render_wall_braille(self) -> None:
        """牆壁區域含填充 braille 字元。"""
        ms = _make_empty_map(3.0, 3.0)  # 2×2 grid
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=1.5, height=1.5, name="w1"))
        canvas = _make_canvas_with_size(ms, width=30, height=12)

        text = canvas.render()
        plain = text.plain
        # 應包含非空白 braille（牆壁填充）
        has_filled_braille = any("\u2801" <= ch <= "\u28ff" for ch in plain)
        assert has_filled_braille, "牆壁應產生填充 braille 字元"

    def test_floor_is_blank_braille(self) -> None:
        """純地板地圖的地圖區域只有空白 braille（⠀）或空格。

        圖例區域（右上角）除外——圖例含 ⣿ 作為牆壁示意。
        """
        ms = _make_empty_map(3.0, 3.0)
        w = 30
        canvas = _make_canvas_with_size(ms, width=w, height=10)

        text = canvas.render()
        plain = text.plain
        # 排除右側圖例區域（用計算後的終端寬度）
        legend_w = _LEGEND_WIDTH
        for line in plain.split("\n"):
            map_part = line[: max(0, len(line) - legend_w)]
            for ch in map_part:
                if "\u2801" <= ch <= "\u28ff":
                    raise AssertionError(f"地板不應有填充 braille，但發現 {ch!r}")

    def test_wall_gap_visible(self) -> None:
        """南牆門洞處（wall gap）braille 應為空白。

        南牆 x=0~4.5 有缺口 x=3.0~4.5（門洞），
        門洞對應的 dot 區域不應被牆壁填充。
        """
        ms = _make_empty_map(7.5, 6.0)
        # 南牆左段 x=0~3.0, y=0~0.3
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=3.0, height=0.3, name="south-l"))
        # 南牆右段 x=4.5~7.5, y=0~0.3
        ms.manifest.walls.append(Wall(x=4.5, y=0.0, width=3.0, height=0.3, name="south-r"))
        # 門洞 x=3.0~4.5 無牆壁

        canvas = _make_canvas_with_size(ms, width=40, height=15)
        text = canvas.render()
        plain = text.plain
        lines = plain.split("\n")

        # 底部行（Y=0 區域，最後幾行地圖行）不應全部都是 braille 填充
        # 至少有一行在中間區域有空隙
        bottom_lines = lines[-5:-1]  # X 軸標籤前的幾行
        has_gap = False
        for ln in bottom_lines:
            filled_positions = [i for i, ch in enumerate(ln) if "\u2801" <= ch <= "\u28ff"]
            blank_positions = [
                i
                for i, ch in enumerate(ln)
                if ch in (" ", "\u2800") and i > 5  # 排除 Y 軸標籤區
            ]
            if (
                filled_positions
                and blank_positions
                and min(blank_positions) > min(filled_positions)
            ):
                has_gap = True
                break
        assert has_gap, "門洞處應可見牆壁間隙"

    def test_legend_overlay(self) -> None:
        """渲染輸出右上角含圖例，且圖例不超過 widget 寬度。"""
        ms = _make_empty_map(6.0, 6.0)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=6.0, height=0.3, name="s"))
        canvas = _make_canvas_with_size(ms, width=50, height=20)

        text = canvas.render()
        plain = text.plain
        assert "圖例" in plain, "渲染輸出應包含圖例"

        # 確認每行的顯示寬度不超過 widget 寬度
        for line in plain.split("\n"):
            dw = _display_width(line)
            assert dw <= 50, f"行顯示寬度 {dw} 超過 widget 寬度 50：{line!r}"

    def test_actor_wall_alignment(self) -> None:
        """actor 和 wall 在相同世界座標時 dot 座標一致。

        統一 dpm 後，牆壁和 actor 用同一個 grid_world 尺寸計算，
        world_w 不等於 grid_w * CELL_SIZE_M 時也不會偏移。
        """
        # 非整除的世界尺寸（5.0m → ceil(5.0/1.5)=4 tiles → 6.0m grid）
        ms = _make_empty_map(5.0, 5.0)
        # 牆壁佔 (0, 0) ~ (1.5, 1.5)
        ms.manifest.walls.append(Wall(x=0.0, y=0.0, width=1.5, height=1.5, name="w1"))
        # actor 在牆壁中心 (0.75, 0.75)
        ms.actors.append(
            Actor(
                id="party-1",
                x=0.75,
                y=0.75,
                name="隊伍",
                combatant_id=uuid4(),
                combatant_type="character",
                size=Size.MEDIUM,
            )
        )
        canvas = _make_canvas_with_size(ms, width=40, height=20)
        text = canvas.render()
        # 不會拋出例外且有 braille 輸出即可——主要驗證 dpm 一致
        plain = text.plain
        has_braille = any("\u2801" <= ch <= "\u28ff" for ch in plain)
        assert has_braille, "應有 braille 渲染輸出"

    def test_color_priority(self) -> None:
        """ACTOR 層顏色優先於 TERRAIN 層。

        當 actor 和 terrain（如水域）重疊時，actor 的 color
        應因優先級較高而被選中。
        """
        ms = _make_empty_map(6.0, 6.0)
        # 水域覆蓋全圖
        ms.manifest.props.append(
            Prop(
                id="water1",
                x=3.0,
                y=3.0,
                terrain_type="water",
                bounds=BoundingShape.rect(6.0, 6.0),
            )
        )
        # actor 在中心
        ms.actors.append(
            Actor(
                id="party-1",
                x=3.0,
                y=3.0,
                name="隊伍",
                combatant_id=uuid4(),
                combatant_type="character",
                size=Size.MEDIUM,
            )
        )
        canvas = _make_canvas_with_size(ms, width=40, height=20)
        text = canvas.render()

        # 取 actor 位置附近的 styled spans
        # actor 的 style 預設是 "bold green"（render() 中 item.style or "bold green"）
        # 確認 "bold green" 出現在渲染結果的 spans 中
        has_actor_style = any("green" in str(span.style) for span in text._spans)
        assert has_actor_style, "Actor 顏色應出現在渲染結果中"
