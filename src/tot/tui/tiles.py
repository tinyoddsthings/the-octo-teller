"""Tile-based 視覺映射字典 + 座標轉換 + Braille 紋理。

探索 TUI 的 TileMapCanvas 用此模組將 RenderBuffer 語意
轉為 drawille braille 渲染。每個 tile = 1.5m × 1.5m（= 5ft D&D 格）。

Braille 字元（U+2800-U+28FF）EAW = Narrow，不會在 CJK 終端跑版，
且每字元 2×4 dots 提供亞 tile 級解析度，牆壁/門洞可在 dot 級精確繪製。

與 BrailleMapCanvas（戰鬥用）完全獨立，不共用渲染邏輯。
"""

from __future__ import annotations

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
    """

    char: str  # 顯示字元（ASCII，寬度 1 欄）
    fg: str  # Rich 前景色
    bg: str = ""  # Rich 背景色（空 = 無）
    legend_label: str = ""  # 非空 = 出現在圖例


# ---------------------------------------------------------------------------
# 地形映射（terrain_type → TileVisual）
# ---------------------------------------------------------------------------

FLOOR_TILE = TileVisual(char=".", fg="dim", legend_label="地板")

TERRAIN_TILES: dict[str, TileVisual] = {
    "rubble": TileVisual(char=":", fg="yellow", legend_label="碎石"),
    "water": TileVisual(char="~", fg="bright_blue", bg="on dark_blue", legend_label="水域"),
    "hill": TileVisual(char="^", fg="green"),
    "crevice": TileVisual(char="v", fg="red"),
}

WALL_TILE = TileVisual(char="#", fg="bright_white", legend_label="牆壁")

# ---------------------------------------------------------------------------
# Prop 映射（prop_type + is_blocking → TileVisual）
# ---------------------------------------------------------------------------

PROP_TILES: dict[str, TileVisual] = {
    "door_open": TileVisual(char="/", fg="bright_white"),
    "door_blocked": TileVisual(char="+", fg="bright_white"),
    "decoration_blocking": TileVisual(char="O", fg="cyan"),
    "decoration_nonblocking": TileVisual(char="o", fg="cyan"),
    "item": TileVisual(char="!", fg="yellow"),
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


def _tex_decoration(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """裝飾物：中心小方塊。"""
    cx, cy = pw // 2, ph // 2
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            x, y = cx + dx, cy + dy
            if 0 <= x < pw and 0 <= y < ph:
                canvas.set(px0 + x, py0 + y)


def _tex_item(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """物品標記：中心 3×3 菱形。"""
    cx, cy = pw // 2, ph // 2
    for dx, dy in [(0, -1), (-1, 0), (0, 0), (1, 0), (0, 1)]:
        x, y = cx + dx, cy + dy
        if 0 <= x < pw and 0 <= y < ph:
            canvas.set(px0 + x, py0 + y)


def _tex_door_open(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """開門：左右邊 1 dot 寬的薄線。"""
    for dy in range(ph):
        canvas.set(px0, py0 + dy)
        if pw > 1:
            canvas.set(px0 + pw - 1, py0 + dy)


def _tex_door_blocked(canvas: Canvas, px0: int, py0: int, pw: int, ph: int) -> None:
    """鎖門：十字交叉。"""
    cx, cy = pw // 2, ph // 2
    for dx in range(pw):
        canvas.set(px0 + dx, py0 + cy)
    for dy in range(ph):
        canvas.set(px0 + cx, py0 + dy)


# 紋理名稱 → 函數對照表
BRAILLE_TEXTURES: dict[str, Callable[..., None]] = {
    "floor": _tex_floor,
    "wall": _tex_wall,
    "water": _tex_water,
    "rubble": _tex_rubble,
    "hill": _tex_hill,
    "crevice": _tex_crevice,
    "decoration": _tex_decoration,
    "item": _tex_item,
    "door_open": _tex_door_open,
    "door_blocked": _tex_door_blocked,
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


def build_legend_lines() -> list[list[tuple[str, str]]]:
    """從 tile 定義自動組裝圖例資料。

    回傳 list[list[(text, style)]]——每行是多段 segments，
    每個 tile 條目用自己的 fg 顏色。
    """
    lines: list[list[tuple[str, str]]] = [[("  圖例      ", "bold")]]

    # 收集 (braille_char, label, fg_style)
    entries: list[tuple[str, str, str]] = [
        (braille_sample(WALL_TILE), WALL_TILE.legend_label, WALL_TILE.fg),
        (braille_sample(FLOOR_TILE), FLOOR_TILE.legend_label, FLOOR_TILE.fg),
    ]
    for tile in TERRAIN_TILES.values():
        if tile.legend_label:
            entries.append((braille_sample(tile), tile.legend_label, tile.fg))

    # 每行 2 個，每個用自己的顏色
    for i in range(0, len(entries), 2):
        segs: list[tuple[str, str]] = [("  ", "")]
        ch, label, style = entries[i]
        segs.append((ch, style))
        segs.append((f" {label}", style))
        if i + 1 < len(entries):
            segs.append(("  ", ""))
            ch, label, style = entries[i + 1]
            segs.append((ch, style))
            segs.append((f" {label}", style))
        lines.append(segs)

    # Actor 行
    lines.append(
        [
            ("  ", ""),
            (PARTY_TILE.char, PARTY_TILE.fg),
            (f" {PARTY_TILE.legend_label}", PARTY_TILE.fg),
            ("  ", ""),
            ("◇", "bold red"),
            (" 怪物", "bold red"),
        ]
    )
    return lines
