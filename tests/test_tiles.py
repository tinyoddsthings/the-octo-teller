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
    braille_wide_sample,
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
        """所有有 legend_label 的 tile（含 prop）都出現在圖例文字中。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        for tile in [WALL_TILE, FLOOR_TILE, PARTY_TILE]:
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"
        for tile in TERRAIN_TILES.values():
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"
        for tile in PROP_TILES.values():
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"

    def test_legend_sample_matches_texture(self) -> None:
        """圖例中的 wide braille 取樣 = braille_wide_sample() 回傳值（防漂移）。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        for tile in [WALL_TILE, FLOOR_TILE, *TERRAIN_TILES.values()]:
            if not tile.legend_label:
                continue
            icon_lines = braille_wide_sample(tile)
            for icon_line in icon_lines:
                assert icon_line in combined, (
                    f"{tile.legend_label} 的 wide braille 取樣未出現在圖例"
                )

    def test_legend_uses_tile_colors(self) -> None:
        """每個 tile 的圖例段落使用對應的 tile.fg 顏色。"""
        lines = build_legend_lines()
        # 展平所有 segments
        all_segs = [(text, style) for segs in lines for text, style in segs]
        # 牆壁 wide braille 上半行應用 bright_white
        wall_icon = braille_wide_sample(WALL_TILE)
        wall_seg = [(t, s) for t, s in all_segs if t == wall_icon[0]]
        assert any(s == WALL_TILE.fg for _, s in wall_seg)
        # 隊伍段落應該用 bold bright_green
        party_seg = [(t, s) for t, s in all_segs if s == PARTY_TILE.fg]
        assert len(party_seg) > 0

    def test_dynamic_filters_by_present_tiles(self) -> None:
        """present_tiles 參數只顯示畫面上存在的 tile。"""
        lines = build_legend_lines(present_tiles={WALL_TILE, FLOOR_TILE})
        combined = "".join(text for segs in lines for text, _ in segs)
        assert "牆壁" in combined
        assert "地板" in combined
        assert "碎石" not in combined
        assert "水域" not in combined

    def test_no_monsters_when_absent(self) -> None:
        """has_monsters=False 時不顯示怪物。"""
        lines = build_legend_lines(has_monsters=False)
        combined = "".join(text for segs in lines for text, _ in segs)
        assert "怪物" not in combined

    def test_monsters_shown_when_present(self) -> None:
        """has_monsters=True 時顯示怪物。"""
        lines = build_legend_lines(has_monsters=True)
        combined = "".join(text for segs in lines for text, _ in segs)
        assert "怪物" in combined

    def test_party_uses_wide_braille_icon(self) -> None:
        """隊伍圖例用 4×2 wide braille 圓圈，不是 @ 或單字元。"""
        lines = build_legend_lines(has_party=True)
        all_segs = [(text, style) for segs in lines for text, style in segs]
        # 不應有 @ 字元
        assert not any(t == "@" for t, _ in all_segs)
        # 應有多字元 braille 段落且 style 是 party 顏色
        party_icons = [
            t
            for t, s in all_segs
            if s == PARTY_TILE.fg and len(t) > 1 and any("\u2800" <= ch <= "\u28ff" for ch in t)
        ]
        assert len(party_icons) > 0, "隊伍圖例應有 wide braille icon"

    def test_wide_sample_returns_correct_dimensions(self) -> None:
        """braille_wide_sample 回傳正確的行數和寬度。"""
        all_tiles = [WALL_TILE, FLOOR_TILE, *TERRAIN_TILES.values(), *PROP_TILES.values()]
        for tile in all_tiles:
            icon_lines = braille_wide_sample(tile)
            assert len(icon_lines) == 2, f"{tile.legend_label} wide sample 應有 2 行"
            for line in icon_lines:
                assert len(line) == 4, f"{tile.legend_label} wide sample 每行應 4 字元"

    def test_prop_wide_icons_use_two_lines_in_legend(self) -> None:
        """Prop 圖例佔 2 行（icon 上半 + 下半）。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        # 每個 prop 標籤只出現在第 1 行（不在第 2 行重複）
        for tile in PROP_TILES.values():
            if tile.legend_label:
                assert combined.count(tile.legend_label) == 1

    def test_all_props_have_legend_label(self) -> None:
        """所有 PROP_TILES 都有 legend_label。"""
        for key, tile in PROP_TILES.items():
            assert tile.legend_label, f"PROP_TILES[{key!r}] 缺少 legend_label"

    def test_prop_colors_distinct_from_walls(self) -> None:
        """門顏色不應與牆壁相同。"""
        wall_fg = WALL_TILE.fg
        assert PROP_TILES["door_open"].fg != wall_fg
        assert PROP_TILES["door_blocked"].fg != wall_fg

    def test_legend_contains_props(self) -> None:
        """全圖例（無過濾）包含所有 prop 標籤。"""
        lines = build_legend_lines()
        combined = "".join(text for segs in lines for text, _ in segs)
        for tile in PROP_TILES.values():
            if tile.legend_label:
                assert tile.legend_label in combined, f"{tile.legend_label} 未出現在圖例"

    def test_dynamic_legend_filters_props(self) -> None:
        """present_props 過濾正確：只顯示傳入的 prop tile。"""
        door_open = PROP_TILES["door_open"]
        lines = build_legend_lines(
            present_tiles={WALL_TILE},
            present_props={door_open},
        )
        combined = "".join(text for segs in lines for text, _ in segs)
        assert "門（開）" in combined
        assert "門（鎖）" not in combined
        assert "物品" not in combined


# ---------------------------------------------------------------------------
# legend_shape 機制
# ---------------------------------------------------------------------------


class TestLegendShape:
    """legend_shape 統一圖例形狀測試。"""

    def test_all_props_have_legend_shape(self) -> None:
        """所有 PROP_TILES 都有 legend_shape。"""
        for key, tile in PROP_TILES.items():
            assert tile.legend_shape, f"PROP_TILES[{key!r}] 缺少 legend_shape"

    def test_door_legend_is_narrow(self) -> None:
        """門圖例 = 扁矩形（6 dots 寬 × 3 dots 高，非全填滿）。"""
        tile = PROP_TILES["door_open"]
        icon_lines = braille_wide_sample(tile)
        all_chars = "".join(icon_lines)
        total_dots = sum(bin(ord(ch) - 0x2800).count("1") for ch in all_chars)
        # 6×3 = 18 dots，遠少於全填滿的 64 dots
        assert 10 < total_dots < 30, f"門圖例 dot 數應在 10~30（實際 {total_dots}）"

    def test_item_legend_is_marker(self) -> None:
        """物品圖例 = 中心 2×2 dots（4 個點）。"""
        tile = PROP_TILES["item"]
        icon_lines = braille_wide_sample(tile)
        all_chars = "".join(icon_lines)
        has_dots = any(ch != "\u2800" for ch in all_chars)
        has_blanks = any(ch == "\u2800" for ch in all_chars)
        assert has_dots, "物品圖例應有 dot（marker）"
        assert has_blanks, "物品圖例不應全填滿（應為小標記）"

    def test_terrain_tiles_no_legend_shape(self) -> None:
        """地形 tile 不設 legend_shape（繼續用 BRAILLE_TEXTURES）。"""
        assert WALL_TILE.legend_shape == ""
        assert FLOOR_TILE.legend_shape == ""
        for tile in TERRAIN_TILES.values():
            assert tile.legend_shape == ""
