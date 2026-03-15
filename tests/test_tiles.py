"""tiles.py 單元測試——座標轉換 + 映射完整性。"""

from __future__ import annotations

from tot.tui.tiles import (
    CELL_SIZE_M,
    FLOOR_TILE,
    PARTY_TILE,
    PROP_TILES,
    TERRAIN_TILES,
    WALL_TILE,
    braille_sample,
    build_legend_lines,
    grid_to_world,
    resolve_actor_tile,
    resolve_prop_tile,
    world_to_grid,
)

# ---------------------------------------------------------------------------
# 座標轉換
# ---------------------------------------------------------------------------


class TestWorldToGrid:
    """world_to_grid 測試。"""

    def test_origin(self) -> None:
        assert world_to_grid(0.0, 0.0) == (0, 0)

    def test_one_cell(self) -> None:
        assert world_to_grid(1.5, 1.5) == (1, 1)

    def test_fractional_stays_in_cell(self) -> None:
        """1.49m 仍在第 0 格。"""
        assert world_to_grid(1.49, 0.7) == (0, 0)

    def test_large_coord(self) -> None:
        """25m 地圖的最後一格。"""
        gx, gy = world_to_grid(24.0, 19.5)
        assert gx == 16
        assert gy == 13

    def test_negative_coord(self) -> None:
        """負座標（邊界外）不會崩潰，int() 向零截斷。"""
        gx, gy = world_to_grid(-0.1, -0.1)
        # int(-0.066) = 0（向零截斷）
        assert gx == 0
        assert gy == 0


class TestGridToWorld:
    """grid_to_world 測試。"""

    def test_origin_center(self) -> None:
        cx, cy = grid_to_world(0, 0)
        assert cx == CELL_SIZE_M / 2
        assert cy == CELL_SIZE_M / 2

    def test_roundtrip(self) -> None:
        """grid→world→grid 回程應一致。"""
        for gx, gy in [(0, 0), (3, 5), (10, 7)]:
            cx, cy = grid_to_world(gx, gy)
            assert world_to_grid(cx, cy) == (gx, gy)


# ---------------------------------------------------------------------------
# 地形映射完整性
# ---------------------------------------------------------------------------


class TestTerrainTiles:
    """地形映射表覆蓋率。"""

    def test_all_terrain_types_covered(self) -> None:
        expected = {"rubble", "water", "hill", "crevice"}
        assert set(TERRAIN_TILES.keys()) == expected

    def test_floor_tile_exists(self) -> None:
        assert FLOOR_TILE.char == "."

    def test_wall_tile_exists(self) -> None:
        assert WALL_TILE.char == "#"

    def test_water_has_background(self) -> None:
        assert TERRAIN_TILES["water"].bg != ""


# ---------------------------------------------------------------------------
# Prop 映射
# ---------------------------------------------------------------------------


class TestPropTiles:
    def test_door_open(self) -> None:
        tile = resolve_prop_tile("door", is_blocking=False, interactable=False)
        assert tile == PROP_TILES["door_open"]

    def test_door_blocked(self) -> None:
        tile = resolve_prop_tile("door", is_blocking=True, interactable=False)
        assert tile == PROP_TILES["door_blocked"]

    def test_decoration_blocking(self) -> None:
        tile = resolve_prop_tile("decoration", is_blocking=True, interactable=False)
        assert tile == PROP_TILES["decoration_blocking"]

    def test_decoration_nonblocking(self) -> None:
        tile = resolve_prop_tile("decoration", is_blocking=False, interactable=False)
        assert tile == PROP_TILES["decoration_nonblocking"]

    def test_item_interactable(self) -> None:
        tile = resolve_prop_tile("decoration", is_blocking=False, interactable=True)
        assert tile == PROP_TILES["item"]

    def test_item_prop_type(self) -> None:
        tile = resolve_prop_tile("item", is_blocking=False, interactable=False)
        assert tile == PROP_TILES["item"]


# ---------------------------------------------------------------------------
# Actor 映射
# ---------------------------------------------------------------------------


class TestActorTiles:
    def test_party_character(self) -> None:
        tile = resolve_actor_tile("隊伍", "character")
        assert tile.char == "@"
        assert "green" in tile.fg

    def test_monster_uses_first_char(self) -> None:
        tile = resolve_actor_tile("Goblin", "monster")
        assert tile.char == "G"
        assert "red" in tile.fg

    def test_chinese_name_fallback_to_m(self) -> None:
        """CJK 名稱（2 欄寬）→ fallback 'M'，避免 grid 跑版。"""
        tile = resolve_actor_tile("哥布林", "monster")
        assert tile.char == "M"

    def test_empty_name_fallback(self) -> None:
        tile = resolve_actor_tile("", "monster")
        assert tile.char == "M"


# ---------------------------------------------------------------------------
# Braille 取樣 + 自動圖例
# ---------------------------------------------------------------------------


class TestBrailleSample:
    """braille_sample() 從紋理函數實際取樣。"""

    def test_wall_filled(self) -> None:
        """牆壁 = 全填 ⣿（2×4 dots 全亮）。"""
        assert braille_sample(WALL_TILE) == "⣿"

    def test_floor_blank(self) -> None:
        """地板 = 空白 braille（無 dot）。"""
        assert braille_sample(FLOOR_TILE) == "\u2800"

    def test_water_has_dots(self) -> None:
        """水域取樣有 dot（非空白）。"""
        s = braille_sample(TERRAIN_TILES["water"])
        assert s != "\u2800"


class TestBuildLegendLines:
    """build_legend_lines() 自動圖例生成。"""

    def test_contains_all_labeled(self) -> None:
        """所有有 legend_label 的 tile 都出現在圖例文字中。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        for tile in [WALL_TILE, FLOOR_TILE, PARTY_TILE]:
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"
        for tile in TERRAIN_TILES.values():
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"

    def test_legend_sample_matches_texture(self) -> None:
        """圖例中的 braille 字元 = braille_sample() 回傳值（防漂移）。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        for tile in [WALL_TILE, FLOOR_TILE]:
            sample = braille_sample(tile)
            if tile.legend_label:
                assert sample in combined, f"{tile.legend_label} 的 braille 取樣未出現在圖例"
        for tile in TERRAIN_TILES.values():
            sample = braille_sample(tile)
            if tile.legend_label:
                assert sample in combined, f"{tile.legend_label} 的 braille 取樣未出現在圖例"

    def test_legend_uses_tile_colors(self) -> None:
        """每個 tile 的圖例段落使用對應的 tile.fg 顏色。"""
        lines = build_legend_lines()
        # 展平所有 segments
        all_segs = [(text, style) for segs in lines for text, style in segs]
        # 牆壁 braille 應該用 bright_white
        wall_sample = braille_sample(WALL_TILE)
        wall_seg = [(t, s) for t, s in all_segs if t == wall_sample]
        assert any(s == WALL_TILE.fg for _, s in wall_seg)
        # 隊伍 @ 應該用 bold bright_green
        party_seg = [(t, s) for t, s in all_segs if t == PARTY_TILE.char]
        assert any(s == PARTY_TILE.fg for _, s in party_seg)
