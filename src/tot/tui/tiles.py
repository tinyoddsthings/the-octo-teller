"""Tile-based 視覺映射字典 + 座標轉換 + Braille 紋理。

探索 TUI 的 TileMapCanvas 用此模組將 RenderBuffer 語意
轉為 drawille braille 渲染。每個 tile = 1.5m × 1.5m（= 5ft D&D 格）。

Braille 字元（U+2800-U+28FF）EAW = Narrow，不會在 CJK 終端跑版，
且每字元 2×4 dots 提供亞 tile 級解析度，牆壁/門洞可在 dot 級精確繪製。

與 BrailleMapCanvas（戰鬥用）完全獨立，不共用渲染邏輯。
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drawille import Canvas

# ---------------------------------------------------------------------------
# Tile 視覺定義
# ---------------------------------------------------------------------------

CELL_SIZE_M = 1.5  # 1 tile = 5ft ≈ 1.5m


@dataclass(frozen=True)
class TileVisual:
    """單一 tile 的顯示資訊。

    char 必須是 ASCII 字元（保證終端寬度 = 1 欄）。
    legend_label 非空時會自動出現在圖例中。
    legend_shape 非空時圖例用形狀繪製（與地圖視覺一致），
    否則用 BRAILLE_TEXTURES 紋理取樣。
    """

    char: str  # 顯示字元（ASCII，寬度 1 欄）
    fg: str  # Rich 前景色
    bg: str = ""  # Rich 背景色（空 = 無）
    legend_label: str = ""  # 非空 = 出現在圖例
    legend_shape: str = ""  # 非空 = 圖例用形狀繪製（同地圖視覺語言）


# ---------------------------------------------------------------------------
# 地形映射（terrain_type → TileVisual）
# ---------------------------------------------------------------------------

FLOOR_TILE = TileVisual(char=".", fg="dim", legend_label="地板")

TERRAIN_TILES: dict[str, TileVisual] = {
    "rubble": TileVisual(char=":", fg="yellow", legend_label="碎石"),
    "water": TileVisual(char="~", fg="bright_blue", bg="on dark_blue", legend_label="水域"),
    "hill": TileVisual(char="^", fg="green", legend_label="高地"),
    "crevice": TileVisual(char="v", fg="red", legend_label="裂縫"),
}

WALL_TILE = TileVisual(char="#", fg="bright_white", legend_label="牆壁")

# ---------------------------------------------------------------------------
# Prop 映射（prop_type + is_blocking → TileVisual）
# ---------------------------------------------------------------------------

PROP_TILES: dict[str, TileVisual] = {
    "door_open": TileVisual(
        char="□", fg="bright_yellow", legend_label="門（開）", legend_shape="rect_narrow"
    ),
    "door_blocked": TileVisual(
        char="□", fg="bright_red", legend_label="門（鎖）", legend_shape="rect_narrow"
    ),
    "decoration_blocking": TileVisual(
        char="O", fg="cyan", legend_label="障礙物", legend_shape="circle_fill"
    ),
    "decoration_nonblocking": TileVisual(
        char="o", fg="cyan", legend_label="裝飾", legend_shape="rect_outline"
    ),
    "item": TileVisual(char="!", fg="bright_magenta", legend_label="物品", legend_shape="marker"),
}


def resolve_prop_tile(prop_type: str, is_blocking: bool, interactable: bool) -> TileVisual:
    """依 prop 屬性決定 tile 視覺。"""
    if prop_type == "door":
        return PROP_TILES["door_blocked"] if is_blocking else PROP_TILES["door_open"]
    if interactable or prop_type == "item":
        return PROP_TILES["item"]
    if is_blocking:
        return PROP_TILES["decoration_blocking"]
    return PROP_TILES["decoration_nonblocking"]


# ---------------------------------------------------------------------------
# Actor 映射
# ---------------------------------------------------------------------------

PARTY_TILE = TileVisual(char="@", fg="bold bright_green", legend_label="隊伍")


def resolve_actor_tile(name: str, combatant_type: str) -> TileVisual:
    """依 actor 類型決定 tile 視覺。

    隊伍（character）→ @（綠色）
    NPC/monster → 名字首個 ASCII 字母（紅色），CJK 名稱用 M fallback
    """
    if combatant_type == "character":
        return PARTY_TILE
    # 取第一個 ASCII 字母（避免 CJK 2 欄寬字元破壞 grid）
    for ch in name:
        if ch.isascii() and ch.isalpha():
            return TileVisual(char=ch.upper(), fg="bold red")
    # CJK / 空名稱 fallback
    return TileVisual(char="M", fg="bold red")


# ---------------------------------------------------------------------------
# 座標轉換
# ---------------------------------------------------------------------------


def world_to_grid(x: float, y: float) -> tuple[int, int]:
    """世界座標（公尺）→ 網格座標。"""
    return int(x / CELL_SIZE_M), int(y / CELL_SIZE_M)


def grid_to_world(gx: int, gy: int) -> tuple[float, float]:
    """網格座標 → 世界座標（格子中心）。"""
    return (gx + 0.5) * CELL_SIZE_M, (gy + 0.5) * CELL_SIZE_M


# ---------------------------------------------------------------------------
# Braille 紋理函數
# ---------------------------------------------------------------------------
# 每個函數在指定的 pixel 區域 (px0, py0, pw, ph) 內畫 dots。
# px0, py0 = 區域左上角 dot 座標；pw, ph = 區域寬高（dots）。


def _tex_floor(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """地板：空白（不畫任何 dot）。"""


def _tex_wall(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """牆壁：全部填滿。"""
    for dy in range(ph):
        for dx in range(pw):
            canvas.set(px0 + dx, py0 + dy)


def _tex_water(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """水域：水平波浪線（每 3 行畫 1 行）。"""
    for dy in range(ph):
        if dy % 3 == 1:
            for dx in range(pw):
                canvas.set(px0 + dx, py0 + dy)


def _tex_rubble(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """碎石：稀疏散佈 dots（~25% 密度）。"""
    for dy in range(ph):
        for dx in range(pw):
            if (dx + dy * 3) % 4 == 0:
                canvas.set(px0 + dx, py0 + dy)


def _tex_hill(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """高地：底部密、頂部疏。"""
    for dy in range(ph):
        # 越往底部（dy 越大），間距越小
        spacing = max(1, 4 - (dy * 3 // max(1, ph)))
        for dx in range(pw):
            if dx % spacing == 0:
                canvas.set(px0 + dx, py0 + dy)


def _tex_crevice(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """裂縫：頂部密、底部疏。"""
    for dy in range(ph):
        spacing = max(1, 1 + (dy * 3 // max(1, ph)))
        for dx in range(pw):
            if dx % spacing == 0:
                canvas.set(px0 + dx, py0 + dy)


def _tex_obstacle(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """障礙物（阻擋型）：中心大方塊。"""
    cx, cy = pw // 2, ph // 2
    r = max(1, min(pw, ph) // 3)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            x, y = cx + dx, cy + dy
            if 0 <= x < pw and 0 <= y < ph:
                canvas.set(px0 + x, py0 + y)


def _tex_decoration(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """裝飾（非阻擋型）：小空心菱形。"""
    cx, cy = pw / 2 - 0.5, ph / 2 - 0.5
    r = min(pw, ph) / 4
    for dy in range(ph):
        for dx in range(pw):
            dist = abs(dx - cx) + abs(dy - cy)
            if abs(dist - r) < 0.8:
                canvas.set(px0 + dx, py0 + dy)


def _tex_item(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """物品標記：中心 3×3 菱形。"""
    cx, cy = pw // 2, ph // 2
    for dx, dy in [(0, -1), (-1, 0), (0, 0), (1, 0), (0, 1)]:
        x, y = cx + dx, cy + dy
        if 0 <= x < pw and 0 <= y < ph:
            canvas.set(px0 + x, py0 + y)


def _tex_door(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """門：矩形外框（開門/鎖門同一形狀，靠顏色區分）。"""
    for dy in range(ph):
        for dx in range(pw):
            if dy == 0 or dy == ph - 1 or dx == 0 or dx == pw - 1:
                canvas.set(px0 + dx, py0 + dy)


# 紋理名稱 → 函數對照表
BRAILLE_TEXTURES: dict[str, Callable[..., None]] = {
    "floor": _tex_floor,
    "wall": _tex_wall,
    "water": _tex_water,
    "rubble": _tex_rubble,
    "hill": _tex_hill,
    "crevice": _tex_crevice,
    "decoration": _tex_decoration,
    "decoration_blocking": _tex_obstacle,
    "decoration_nonblocking": _tex_decoration,
    "item": _tex_item,
    "door_open": _tex_door,
    "door_blocked": _tex_door,
}


def tile_texture_key(tile: TileVisual) -> str:
    """從 TileVisual 推導 braille 紋理 key。"""
    if tile is FLOOR_TILE:
        return "floor"
    if tile is WALL_TILE:
        return "wall"
    # 地形
    for name, tv in TERRAIN_TILES.items():
        if tile is tv:
            return name
    # Prop
    for name, tv in PROP_TILES.items():
        if tile is tv:
            return name
    # Actor → 不由此函數處理
    return "floor"


def stamp_tile_texture(
    canvas: Canvas, tile: TileVisual, px0: int, py0: int, pw: int, ph: int
) -> None:
    """在 canvas 的指定區域內畫 tile 紋理。"""
    key = tile_texture_key(tile)
    func = BRAILLE_TEXTURES.get(key, _tex_floor)
    func(canvas, px0, py0, pw, ph)


# ---------------------------------------------------------------------------
# Braille 取樣 + 自動圖例
# ---------------------------------------------------------------------------


def braille_sample(tile: TileVisual) -> str:
    """用 2×4 dot canvas 跑紋理函數，回傳 1 個 braille 字元。

    改紋理函數 → 此函數自動回傳新結果 → 圖例連動更新。
    """
    from drawille import Canvas as _Canvas

    key = tile_texture_key(tile)
    func = BRAILLE_TEXTURES.get(key, _tex_floor)
    c = _Canvas()
    func(c, 0, 0, 2, 4)
    frame = c.frame(min_x=0, min_y=0)
    if frame and frame.strip():
        return frame.strip()[0]
    return "\u2800"


# ---------------------------------------------------------------------------
# 圖例形狀函數（legend_shape → drawille 繪製）
# ---------------------------------------------------------------------------
# 與地圖碰撞體積視覺一致：改 legend_shape 就同時改圖例 icon。


def _shape_rect_fill(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """填滿矩形（= 地圖 FILL）。"""
    for dy in range(ph):
        for dx in range(pw):
            canvas.set(px0 + dx, py0 + dy)


def _shape_rect_outline(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """矩形外框（= 地圖 OUTLINE）。"""
    for dy in range(ph):
        for dx in range(pw):
            if dy == 0 or dy == ph - 1 or dx == 0 or dx == pw - 1:
                canvas.set(px0 + dx, py0 + dy)


def _shape_circle_fill(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """填滿橢圓（= 地圖 CIRCLE_FILL）。"""
    cx, cy = pw / 2 - 0.5, ph / 2 - 0.5
    rx, ry = pw / 2, ph / 2
    if rx <= 0 or ry <= 0:
        return
    for dy in range(ph):
        for dx in range(pw):
            if ((dx - cx) / rx) ** 2 + ((dy - cy) / ry) ** 2 <= 1.0:
                canvas.set(px0 + dx, py0 + dy)


def _shape_circle_outline(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """橢圓外框（= 地圖 CIRCLE_OUTLINE）。"""
    cx, cy = pw / 2 - 0.5, ph / 2 - 0.5
    rx, ry = pw / 2, ph / 2
    if rx <= 0 or ry <= 0:
        return
    for dy in range(ph):
        for dx in range(pw):
            dist = ((dx - cx) / rx) ** 2 + ((dy - cy) / ry) ** 2
            if abs(dist - 1.0) < 0.5:
                canvas.set(px0 + dx, py0 + dy)


def _shape_rect_narrow(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """扁填滿矩形（門圖例用，6 dots 寬 × 3 dots 高）。"""
    nw, nh = 6, 3
    sx = px0 + (pw - nw) // 2
    sy = py0 + (ph - nh) // 2
    for dy in range(nh):
        for dx in range(nw):
            canvas.set(sx + dx, sy + dy)


def _shape_cross(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """十字（物品）。"""
    cx, cy = pw // 2, ph // 2
    # 水平線
    for dx in range(pw):
        canvas.set(px0 + dx, py0 + cy)
    # 垂直線
    for dy in range(ph):
        canvas.set(px0 + cx, py0 + dy)


def _shape_marker(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """中心 2×2 dots。"""
    cx, cy = pw // 2, ph // 2
    for ddx, ddy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
        x, y = cx + ddx, cy + ddy
        if 0 <= x < pw and 0 <= y < ph:
            canvas.set(px0 + x, py0 + y)


_LEGEND_SHAPES: dict[str, Callable[..., None]] = {
    "rect_fill": _shape_rect_fill,
    "rect_narrow": _shape_rect_narrow,
    "rect_outline": _shape_rect_outline,
    "circle_fill": _shape_circle_fill,
    "circle_outline": _shape_circle_outline,
    "cross": _shape_cross,
    "marker": _shape_marker,
}


# ---------------------------------------------------------------------------
# Wide braille 取樣（圖例用，4 chars × 2 lines = 8×8 dots）
# ---------------------------------------------------------------------------

_WIDE_W = 4  # 圖例 wide icon 寬度（字元）
_WIDE_H = 2  # 圖例 wide icon 高度（行）


def _frame_to_lines(frame: str, w_chars: int, h_lines: int) -> list[str]:
    """drawille frame → 固定寬高的字串列表。"""
    raw = frame.split("\n") if frame else []
    result: list[str] = []
    for i in range(h_lines):
        line = raw[i] if i < len(raw) else ""
        while len(line) < w_chars:
            line += "\u2800"
        result.append(line[:w_chars])
    return result


def braille_wide_sample(
    tile: TileVisual, w_chars: int = _WIDE_W, h_lines: int = _WIDE_H
) -> list[str]:
    """用 (w_chars×2) × (h_lines×4) dot canvas 跑紋理/形狀函數，回傳多行 braille。

    若 tile.legend_shape 非空，用 _LEGEND_SHAPES 形狀函數（與地圖視覺一致）；
    否則用 BRAILLE_TEXTURES 紋理函數（地形用）。
    """
    from drawille import Canvas as _Canvas

    w_d, h_d = w_chars * 2, h_lines * 4
    if tile.legend_shape:
        func = _LEGEND_SHAPES[tile.legend_shape]
    else:
        key = tile_texture_key(tile)
        func = BRAILLE_TEXTURES.get(key, _tex_floor)
    c = _Canvas()
    func(c, 0, 0, w_d, h_d)
    return _frame_to_lines(c.frame(min_x=0, min_y=0), w_chars, h_lines)


def _braille_circle_wide(w_chars: int = _WIDE_W, h_lines: int = _WIDE_H) -> list[str]:
    """填滿圓形（隊伍圖例用）。"""
    from drawille import Canvas as _Canvas

    w_d, h_d = w_chars * 2, h_lines * 4
    c = _Canvas()
    cx, cy = w_d / 2 - 0.5, h_d / 2 - 0.5
    r = min(w_d, h_d) / 2 - 0.5
    for y in range(h_d):
        for x in range(w_d):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                c.set(x, y)
    return _frame_to_lines(c.frame(min_x=0, min_y=0), w_chars, h_lines)


def _braille_diamond_wide(w_chars: int = _WIDE_W, h_lines: int = _WIDE_H) -> list[str]:
    """外框菱形（怪物圖例用）。"""
    from drawille import Canvas as _Canvas

    w_d, h_d = w_chars * 2, h_lines * 4
    c = _Canvas()
    cx, cy = w_d / 2 - 0.5, h_d / 2 - 0.5
    r = min(w_d, h_d) / 2 - 0.5
    for y in range(h_d):
        for x in range(w_d):
            if abs(abs(x - cx) + abs(y - cy) - r) < 1.0:
                c.set(x, y)
    return _frame_to_lines(c.frame(min_x=0, min_y=0), w_chars, h_lines)


def _cjk_display_width(s: str) -> int:
    """終端顯示寬度（CJK/全形=2, 其他=1）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def build_legend_lines(
    *,
    present_tiles: set[TileVisual] | None = None,
    present_props: set[TileVisual] | None = None,
    has_party: bool = True,
    has_monsters: bool = False,
) -> list[list[tuple[str, str]]]:
    """從 tile 定義自動組裝圖例資料。

    回傳 list[list[(text, style)]]——每行是多段 segments，
    每個 tile 條目用自己的 fg 顏色。

    所有條目統一用 4×2 wide 取樣（8×8 dots），提升形狀辨識度。

    Args:
        present_tiles: 畫面上實際存在的地形 TileVisual 集合。
            None = 顯示所有有 legend_label 的 tile（向後相容）。
        present_props: 畫面上實際存在的 prop TileVisual 集合。
            None = 顯示所有有 legend_label 的 prop（向後相容）。
        has_party: 畫面上有隊伍角色。
        has_monsters: 畫面上有怪物。
    """
    lines: list[list[tuple[str, str]]] = [[("  圖例      ", "bold")]]

    def _append_wide_entries(
        entries: list[tuple[list[str], str, str]],
    ) -> None:
        """每行 2 個 wide 條目（4 chars × 2 lines）。

        第 1 行：icon 上半 + 標籤
        第 2 行：icon 下半
        """
        for i in range(0, len(entries), 2):
            icon1, label1, style1 = entries[i]
            # 第 1 行
            segs_top: list[tuple[str, str]] = [("  ", "")]
            segs_top.append((icon1[0], style1))
            segs_top.append((f" {label1}", style1))
            if i + 1 < len(entries):
                icon2, label2, style2 = entries[i + 1]
                segs_top.append(("  ", ""))
                segs_top.append((icon2[0], style2))
                segs_top.append((f" {label2}", style2))
            lines.append(segs_top)
            # 第 2 行
            segs_bot: list[tuple[str, str]] = [("  ", "")]
            segs_bot.append((icon1[1], style1))
            if i + 1 < len(entries):
                # 對齊：跳過 " label1" + "  " 的寬度
                pad = 1 + _cjk_display_width(label1) + 2
                segs_bot.append((" " * pad, ""))
                segs_bot.append((icon2[1], style2))
            lines.append(segs_bot)
            # 每對條目後空一行，減少視覺擁擠
            lines.append([("", "")])

    # 地形條目（4×2 wide 紋理取樣）
    all_tiles = [WALL_TILE, FLOOR_TILE, *TERRAIN_TILES.values()]
    terrain_wide: list[tuple[list[str], str, str]] = []
    for tile in all_tiles:
        if not tile.legend_label:
            continue
        if present_tiles is not None and tile not in present_tiles:
            continue
        terrain_wide.append((braille_wide_sample(tile), tile.legend_label, tile.fg))
    if terrain_wide:
        _append_wide_entries(terrain_wide)

    # Prop 條目（4×2 wide 取樣）
    prop_wide: list[tuple[list[str], str, str]] = []
    for tile in PROP_TILES.values():
        if not tile.legend_label:
            continue
        if present_props is not None and tile not in present_props:
            continue
        prop_wide.append((braille_wide_sample(tile), tile.legend_label, tile.fg))
    if prop_wide:
        _append_wide_entries(prop_wide)

    # Actor 條目（4×2 wide 取樣）
    actor_wide: list[tuple[list[str], str, str]] = []
    if has_party:
        actor_wide.append((_braille_circle_wide(), PARTY_TILE.legend_label, PARTY_TILE.fg))
    if has_monsters:
        actor_wide.append((_braille_diamond_wide(), "怪物", "bold red"))
    if actor_wide:
        _append_wide_entries(actor_wide)

    return lines
