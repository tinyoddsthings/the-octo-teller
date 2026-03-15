"""TileMapCanvas — Drawille-Tile 混合地圖 Widget（探索模式專用）。

保留 _build_grid() 語意（tile 類型判斷），但用 drawille Canvas
繪製紋理。牆壁從 RenderBuffer AABB 直接投影到 dot 級精度，
門洞（wall gap）自然可見。

與 BrailleMapCanvas（戰鬥用）完全獨立。
"""

from __future__ import annotations

import math
import unicodedata

from drawille import Canvas
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from tot.models.map import MapState, Prop
from tot.tui.render_buffer import RenderBuffer, RenderItem, RenderLayer, TextureType
from tot.tui.tiles import (
    CELL_SIZE_M,
    FLOOR_TILE,
    PROP_TILES,
    TERRAIN_TILES,
    WALL_TILE,
    TileVisual,
    build_legend_lines,
    stamp_tile_texture,
)

# ---------------------------------------------------------------------------
# 圖例定義（疊加到地圖右上角）
# ---------------------------------------------------------------------------


def _display_width(s: str) -> int:
    """終端顯示寬度（CJK/全形=2, 其他=1）。"""
    w = 0
    for ch in s:
        cat = unicodedata.east_asian_width(ch)
        w += 2 if cat in ("W", "F") else 1
    return w


def _pad_to_width(s: str, width: int) -> str:
    """用空格填充到指定終端顯示寬度。"""
    dw = _display_width(s)
    if dw < width:
        return s + " " * (width - dw)
    return s


_FALLBACK_LEGEND = build_legend_lines()
_LEGEND_WIDTH_MIN = max(sum(_display_width(s) for s, _ in segs) for segs in _FALLBACK_LEGEND) + 2


class TileMapCanvas(Widget):
    """Drawille-Tile 混合地圖 Widget。

    reactive 屬性變更時自動 refresh（同 BrailleMapCanvas 模式）。
    用 drawille Canvas 繪製 tile 紋理，牆壁在 dot 級精度渲染。
    """

    DEFAULT_CSS = """
    TileMapCanvas {
        height: 1fr;
        min-height: 10;
    }
    """

    map_state: reactive[MapState | None] = reactive(None)
    render_buffer: reactive[RenderBuffer | None] = reactive(None)

    def watch_map_state(self, _old: MapState | None, _new: MapState | None) -> None:
        self.refresh()

    def watch_render_buffer(self, _old: RenderBuffer | None, _new: RenderBuffer | None) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # 網格建構（語意不變）
    # ------------------------------------------------------------------

    def _build_grid(self) -> list[list[TileVisual]]:
        """將 RenderBuffer 轉為 2D tile 網格。

        回傳 grid[gy][gx]，Y=0 對應世界最底部。
        """
        buf = self.render_buffer
        ms = self.map_state
        if buf is None or ms is None:
            return []

        grid_w = math.ceil(buf.world_w / CELL_SIZE_M)
        grid_h = math.ceil(buf.world_h / CELL_SIZE_M)

        # 初始化為全地板
        grid: list[list[TileVisual]] = [[FLOOR_TILE for _ in range(grid_w)] for _ in range(grid_h)]

        # 建立 prop id → Prop 查找表（manifest + runtime）
        prop_lookup: dict[str, Prop] = {}
        for p in ms.manifest.props:
            prop_lookup[p.id] = p
        for p in ms.props:
            prop_lookup[p.id] = p

        # 依 layer 由低到高填入（後者覆蓋前者）
        # Actor 不進 grid：step 7c 已用 RenderBuffer 座標獨立繪製圓圈，
        # 避免覆蓋地形紋理造成黑色空洞
        for item in buf.items:
            if item.layer == RenderLayer.WALL:
                self._fill_wall(grid, item, grid_w, grid_h)
            elif item.layer == RenderLayer.TERRAIN:
                self._fill_terrain(grid, item, prop_lookup, grid_w, grid_h)
            elif item.layer == RenderLayer.PROP:
                self._fill_prop(grid, item, prop_lookup, grid_w, grid_h)

        return grid

    @staticmethod
    def _aabb_to_grid_range(
        item: RenderItem, grid_w: int, grid_h: int
    ) -> tuple[int, int, int, int]:
        """RenderItem 的 AABB → grid 座標範圍（含邊界裁剪）。"""
        min_x, min_y, max_x, max_y = item.bounds.to_aabb(item.center_x, item.center_y)
        eps = 0.01
        return (
            max(0, int(min_x / CELL_SIZE_M)),
            max(0, int(min_y / CELL_SIZE_M)),
            min(grid_w - 1, int((max_x - eps) / CELL_SIZE_M)),
            min(grid_h - 1, int((max_y - eps) / CELL_SIZE_M)),
        )

    @staticmethod
    def _fill_wall(
        grid: list[list[TileVisual]],
        item: RenderItem,
        grid_w: int,
        grid_h: int,
    ) -> None:
        """牆壁：AABB 覆蓋所有重疊的 cell。"""
        min_gx, min_gy, max_gx, max_gy = TileMapCanvas._aabb_to_grid_range(item, grid_w, grid_h)
        for gy in range(min_gy, max_gy + 1):
            for gx in range(min_gx, max_gx + 1):
                grid[gy][gx] = WALL_TILE

    @staticmethod
    def _fill_terrain(
        grid: list[list[TileVisual]],
        item: RenderItem,
        prop_lookup: dict[str, Prop],
        grid_w: int,
        grid_h: int,
    ) -> None:
        """地形：反查 terrain_type，AABB 覆蓋。"""
        prop = prop_lookup.get(item.entity_id)
        terrain_type = prop.terrain_type if prop else ""
        tile = TERRAIN_TILES.get(terrain_type, FLOOR_TILE)

        min_gx, min_gy, max_gx, max_gy = TileMapCanvas._aabb_to_grid_range(item, grid_w, grid_h)
        for gy in range(min_gy, max_gy + 1):
            for gx in range(min_gx, max_gx + 1):
                grid[gy][gx] = tile

    @staticmethod
    def _fill_prop(
        grid: list[list[TileVisual]],
        item: RenderItem,
        prop_lookup: dict[str, Prop],
        grid_w: int,
        grid_h: int,
    ) -> None:
        """Prop：全部跳過 grid tile，改由 step 7b 碰撞體積渲染。"""

    # ------------------------------------------------------------------
    # 動態圖例
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dynamic_legend(
        grid: list[list[TileVisual]], buf: RenderBuffer | None
    ) -> list[list[tuple[str, str]]]:
        """掃描 grid + RenderBuffer，只顯示畫面上存在的項目。"""
        present: set[TileVisual] = set()
        for row in grid:
            for tile in row:
                present.add(tile)

        # Prop 從 RenderBuffer 掃描（不再出現在 grid 中）
        present_props: set[TileVisual] = set()
        has_party = False
        has_monsters = False
        if buf:
            for item in buf.items:
                if item.layer == RenderLayer.PROP and item.label:
                    tile = PROP_TILES.get(item.label)
                    if tile:
                        present_props.add(tile)
                elif item.layer == RenderLayer.ACTOR:
                    if item.style and "green" in item.style:
                        has_party = True
                    else:
                        has_monsters = True

        return build_legend_lines(
            present_tiles=present,
            present_props=present_props,
            has_party=has_party,
            has_monsters=has_monsters,
        )

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def render(self) -> Text:
        """產生 Rich Text 輸出（Drawille-Tile 混合渲染）。

        1. _build_grid() 取得 tile 語意網格
        2. 非牆壁 tile → stamp braille 紋理
        3. 牆壁 → 從 RenderBuffer WALL 層 AABB 直接 dot 級填充
        4. Actor → 用實際座標畫 circle/diamond 形狀
        5. 逐字元比對顏色 → 套用 Rich style
        6. 右上角疊加圖例
        """
        grid = self._build_grid()
        if not grid:
            return Text("（無地圖資料）")

        buf = self.render_buffer

        grid_h = len(grid)
        grid_w = len(grid[0]) if grid else 0

        # 1. widget 可用尺寸
        w = self.size.width
        h = self.size.height

        # 2. 座標軸 margin
        max_y_label = f"{(grid_h - 1) * CELL_SIZE_M:.0f}"
        y_gutter = len(max_y_label) + 1
        x_margin = 1

        draw_w = max(1, w - y_gutter)
        draw_h = max(1, h - x_margin)

        # 3. 每個 tile 的字元寬高
        tile_w_chars = max(1, draw_w // grid_w)
        tile_h_chars = max(1, draw_h // grid_h)

        # dot 尺寸
        tile_w_dots = tile_w_chars * 2  # 每字元 2 dots 寬
        tile_h_dots = tile_h_chars * 4  # 每字元 4 dots 高

        # 4. 置中偏移
        used_w_chars = tile_w_chars * grid_w
        used_h_chars = tile_h_chars * grid_h
        pad_left = (draw_w - used_w_chars) // 2
        pad_top = (draw_h - used_h_chars) // 2

        # 5. 為每個顏色建立獨立 Canvas（含圖層優先級）
        color_canvases: dict[str, tuple[Canvas, int]] = {}  # color → (Canvas, max_priority)

        def _get_canvas(color: str, priority: int = 0) -> Canvas:
            if color not in color_canvases:
                color_canvases[color] = (Canvas(), priority)
            else:
                cvs, old_p = color_canvases[color]
                color_canvases[color] = (cvs, max(old_p, priority))
            return color_canvases[color][0]

        # 6. 非牆壁 tile：stamp 紋理
        for gy in range(grid_h):
            for gx in range(grid_w):
                tile = grid[gy][gx]
                if tile is WALL_TILE:
                    continue  # 牆壁由 RenderBuffer 精確繪製
                if tile is FLOOR_TILE:
                    continue  # 地板空白

                # Y 翻轉：grid gy=0 在底部 → canvas 頂部
                flipped_gy = grid_h - 1 - gy
                px0 = gx * tile_w_dots
                py0 = flipped_gy * tile_h_dots

                cvs = _get_canvas(tile.fg, priority=1)  # TERRAIN 層
                stamp_tile_texture(cvs, tile, px0, py0, tile_w_dots, tile_h_dots)

        # 7~8. 牆壁 + Actor：統一 dots-per-meter 計算
        if buf:
            total_dots_w = tile_w_dots * grid_w
            total_dots_h = tile_h_dots * grid_h
            # 統一用 grid 覆蓋的世界尺寸（= grid_w * CELL_SIZE_M），
            # 避免 ceil() 擴張後 world_w 與 grid 實際範圍不一致
            grid_world_w = grid_w * CELL_SIZE_M
            grid_world_h = grid_h * CELL_SIZE_M
            dpm_x = total_dots_w / grid_world_w if grid_world_w > 0 else 1.0
            dpm_y = total_dots_h / grid_world_h if grid_world_h > 0 else 1.0

            # 7a. 牆壁
            wall_canvas = _get_canvas("bright_white", priority=2)  # WALL 層
            for item in buf.items:
                if item.layer != RenderLayer.WALL:
                    continue
                min_x, min_y, max_x, max_y = item.bounds.to_aabb(item.center_x, item.center_y)
                # 公尺 → dot 座標（Y 翻轉）
                dx0 = int(min_x * dpm_x)
                dx1 = int(max_x * dpm_x)
                dy0 = int((grid_world_h - max_y) * dpm_y)  # Y 翻轉
                dy1 = int((grid_world_h - min_y) * dpm_y)
                for py in range(max(0, dy0), min(total_dots_h, dy1)):
                    for px in range(max(0, dx0), min(total_dots_w, dx1)):
                        wall_canvas.set(px, py)

            # 7b. Prop：用實際碰撞體積繪製（dot 級精度）
            for item in buf.items:
                if item.layer != RenderLayer.PROP:
                    continue
                color = item.style or "cyan"
                cvs = _get_canvas(color, priority=3)  # PROP 層

                tex = item.texture

                # 無碰撞標記：中心 4 dots（2×2）
                if tex == "marker":
                    cx_dot = int(item.center_x * dpm_x)
                    cy_dot = int((grid_world_h - item.center_y) * dpm_y)
                    for ddx, ddy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                        px, py = cx_dot + ddx, cy_dot + ddy
                        if 0 <= px < total_dots_w and 0 <= py < total_dots_h:
                            cvs.set(px, py)
                    continue

                min_x, min_y, max_x, max_y = item.bounds.to_aabb(
                    item.center_x,
                    item.center_y,
                )
                dx0 = int(min_x * dpm_x)
                dx1 = int(max_x * dpm_x)
                dy0 = int((grid_world_h - max_y) * dpm_y)
                dy1 = int((grid_world_h - min_y) * dpm_y)

                if tex in ("circle_fill", "circle_outline"):
                    # 圓形：用橢圓方程式
                    cx = (dx0 + dx1) / 2
                    cy = (dy0 + dy1) / 2
                    rx = (dx1 - dx0) / 2
                    ry = (dy1 - dy0) / 2
                    if rx < 1 or ry < 1:
                        continue
                    for py in range(max(0, dy0), min(total_dots_h, dy1)):
                        for px in range(max(0, dx0), min(total_dots_w, dx1)):
                            dist = ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2
                            is_inside = dist <= 1.0
                            is_edge = abs(dist - 1.0) < 0.5
                            hit = tex == "circle_fill" and is_inside
                            hit = hit or (tex == "circle_outline" and is_edge)
                            if hit:
                                cvs.set(px, py)
                else:
                    # 矩形：fill = 填滿，outline = 外框
                    is_fill = tex == "fill"
                    for py in range(max(0, dy0), min(total_dots_h, dy1)):
                        for px in range(max(0, dx0), min(total_dots_w, dx1)):
                            if is_fill or py == dy0 or py == dy1 - 1 or px == dx0 or px == dx1 - 1:
                                cvs.set(px, py)

            # 7d. 掩體標記：收集 cover_label 位置（字元座標）
            cover_annotations: dict[tuple[int, int], tuple[str, str]] = {}
            for item in buf.items:
                if item.layer != RenderLayer.PROP or not item.cover_label:
                    continue
                # 標記位置：prop 中心偏右上 1 字元
                cx_dot = int(item.center_x * dpm_x)
                cy_dot = int((grid_world_h - item.center_y) * dpm_y)
                # dot → 字元座標（braille 每字元 2 dots 寬, 4 dots 高）
                char_col = cx_dot // 2 + 1  # 偏右 1 字元
                char_row = cy_dot // 4 - 1  # 偏上 1 字元
                if 0 <= char_col < used_w_chars and 0 <= char_row < used_h_chars:
                    color = "bold bright_yellow" if item.cover_label == "½" else "bold bright_cyan"
                    cover_annotations[(char_col, char_row)] = (item.cover_label, color)

            # 7c. Actor — 視覺大小 = 碰撞半徑
            for item in buf.items:
                if item.layer != RenderLayer.ACTOR:
                    continue
                color = item.style or "bold green"
                cvs = _get_canvas(color, priority=4)  # ACTOR 層
                # 公尺 → dot（Y 翻轉）
                cx_dot = int(item.center_x * dpm_x)
                cy_dot = int((grid_world_h - item.center_y) * dpm_y)

                # 碰撞半徑 → dot 半徑（最低 2 dots 確保可見）
                radius_m = item.bounds.radius_m
                rx_dot = max(2.0, radius_m * dpm_x)
                ry_dot = max(2.0, radius_m * dpm_y)
                ix_r = int(math.ceil(rx_dot))
                iy_r = int(math.ceil(ry_dot))

                tex = item.texture
                for dy in range(-iy_r, iy_r + 1):
                    py = cy_dot + dy
                    if py < 0 or py >= total_dots_h:
                        continue
                    for dx in range(-ix_r, ix_r + 1):
                        px = cx_dot + dx
                        if px < 0 or px >= total_dots_w:
                            continue
                        nx = dx / rx_dot  # 正規化座標
                        ny = dy / ry_dot
                        hit = False
                        if tex == TextureType.ACTOR_CIRCLE:
                            # 填滿橢圓
                            hit = nx * nx + ny * ny <= 1.0
                        elif tex == TextureType.ACTOR_DIAMOND:
                            # 菱形外框（曼哈頓距離 ≈ 1.0）
                            md = abs(nx) + abs(ny)
                            hit = 0.7 <= md <= 1.0
                        elif tex == TextureType.ACTOR_X and nx * nx + ny * ny <= 1.0:
                            # X 形：兩條對角線，限橢圓範圍內
                            hit = abs(abs(nx) - abs(ny)) < 0.3
                        if hit:
                            cvs.set(px, py)

        # 9. 取各 Canvas 的 braille frame，統一對齊（保留優先級）
        color_frames: dict[str, tuple[list[str], int]] = {}  # color → (lines, priority)
        for color, (cvs, pri) in color_canvases.items():
            f = cvs.frame(min_x=0, min_y=0)
            color_frames[color] = (f.split("\n") if f else [], pri)

        blank_chars = {" ", "\u2800"}

        # 10. 逐行組裝 Rich Text
        result = Text()
        for row_idx in range(draw_h):
            if row_idx > 0:
                result.append("\n")

            adj_row = row_idx - pad_top

            # 上方 padding 或超出範圍
            if adj_row < 0 or adj_row >= used_h_chars:
                result.append(" " * w)
                continue

            # Y 翻轉的 grid 行
            gy = grid_h - 1 - adj_row // tile_h_chars
            sub_row = adj_row % tile_h_chars

            # Y 軸標籤
            if sub_row == 0:
                y_val = f"{gy * CELL_SIZE_M:.0f}"
                y_label = y_val.rjust(y_gutter - 1) + " "
            else:
                y_label = " " * y_gutter

            result.append(y_label, style="dim")

            # 左側 padding
            if pad_left > 0:
                result.append(" " * pad_left)

            # braille 區域逐字元套色（winner-take-all：最高優先級整個字元取代）
            # cover_annotations 可能在此行覆蓋 braille 字元為掩體標記
            frame_row = adj_row  # frame 行 = adj_row（因為 frame 從 0 開始，對齊 tile 區域）
            for col_idx in range(used_w_chars):
                # 掩體標記覆蓋（½ / ¾）
                ann = cover_annotations.get((col_idx, frame_row)) if buf else None
                if ann is not None:
                    result.append(ann[0], style=ann[1])
                    continue

                best_dots = 0
                best_color = ""
                best_pri = -1
                for color, (frames, pri) in color_frames.items():
                    if frame_row < len(frames) and col_idx < len(frames[frame_row]):
                        ch = frames[frame_row][col_idx]
                        if ch not in blank_chars and "\u2800" <= ch <= "\u28ff":
                            dots = ord(ch) - 0x2800
                            if dots > 0 and pri > best_pri:
                                best_dots = dots
                                best_color = color
                                best_pri = pri
                if best_dots > 0 and best_color:
                    result.append(chr(0x2800 + best_dots), style=best_color)
                else:
                    result.append("\u2800")

            # 右側 padding
            right_pad = w - y_gutter - pad_left - used_w_chars
            if right_pad > 0:
                result.append(" " * right_pad)

        # 11. X 軸標籤行
        result.append("\n")
        x_axis = [" "] * w
        last_end = -1
        for gx in range(grid_w):
            label = f"{gx * CELL_SIZE_M:.0f}"
            tile_center = y_gutter + pad_left + gx * tile_w_chars + tile_w_chars // 2
            pos = tile_center - len(label) // 2
            if pos >= y_gutter and pos >= last_end and pos + len(label) <= w:
                for ci, ch in enumerate(label):
                    x_axis[pos + ci] = ch
                last_end = pos + len(label) + 1
        result.append("".join(x_axis).rstrip(), style="dim")

        # 12. 圖例疊加到右上角（動態：只顯示畫面上存在的項目）
        legend = self._build_dynamic_legend(grid, buf)
        result = self._overlay_legend(result, w, legend)

        return result

    @staticmethod
    def _overlay_legend(
        text: Text, widget_w: int, legend_lines: list[list[tuple[str, str]]]
    ) -> Text:
        """在 Rich Text 的右上角疊加圖例。"""
        lines = text.plain.split("\n")
        if len(lines) < len(legend_lines) + 1:
            return text

        legend_width = (
            max(
                (sum(_display_width(s) for s, _ in segs) for segs in legend_lines),
                default=_LEGEND_WIDTH_MIN,
            )
            + 2
        )

        # 重建 Text，在前幾行右側覆寫圖例
        result = Text()
        split_texts = text.split("\n")

        for i, line_text in enumerate(split_texts):
            if i > 0:
                result.append("\n")

            legend_idx = i - 1  # 從第 2 行開始疊加（跳過第一行座標）
            if 0 <= legend_idx < len(legend_lines):
                plain = line_text.plain
                # 圖例放在行尾——用終端顯示寬度計算起始位置
                legend_start = widget_w - legend_width
                if legend_start > 0 and _display_width(plain) >= legend_start:
                    # 依顯示寬度截斷行的前半部分
                    cut = 0
                    dw = 0
                    for ch in plain:
                        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
                        if dw + cw > legend_start:
                            break
                        dw += cw
                        cut += 1
                    result.append_text(line_text[:cut])
                    # 補齊到 legend_start 寬度
                    if dw < legend_start:
                        result.append(" " * (legend_start - dw))
                    # 疊加圖例：逐段 append，每段用自己的顏色 + 深色背景
                    legend_segs = legend_lines[legend_idx]
                    for seg_text, seg_style in legend_segs:
                        bg_style = f"{seg_style} on #1a1a2e" if seg_style else "on #1a1a2e"
                        result.append(seg_text, style=bg_style)
                    # 補齊到 legend_width
                    seg_total = sum(_display_width(s) for s, _ in legend_segs)
                    if seg_total < legend_width:
                        result.append(" " * (legend_width - seg_total), style="on #1a1a2e")
                else:
                    result.append_text(line_text)
            else:
                result.append_text(line_text)

        return result
