"""Braille 點字地圖渲染 Widget。

用 drawille Canvas 繪製高解析度刻度線、牆壁、角色標記，
再用 Rich markup 疊加彩色標籤。每個 Unicode Braille 字元 = 2×4 dots。

座標轉換流程：
  公尺座標 (Position.x, y) → meter_to_px() → drawille pixel (px_x, px_y)
  Widget 尺寸 W×H 字元 → 畫布 W*2 × H*4 dots
  Y 軸翻轉：braille Y=0 在頂部，遊戲 Y=0 在底部
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from drawille import Canvas
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from tot.models import Actor, Character, MapState, Monster

# ---------------------------------------------------------------------------
# AoE 覆蓋資料
# ---------------------------------------------------------------------------

# 呎 → 公尺（5ft = 1.5m）
_FT_TO_M = 1.5 / 5.0


def _char_width(ch: str) -> int:
    """判斷字元的顯示寬度（全形/emoji=2, 半形=1）。"""
    if not ch:
        return 1
    cp = ord(ch[0])
    # emoji 範圍（常見區段）一律視為寬度 2
    if cp >= 0x1F000:
        return 2
    cat = unicodedata.east_asian_width(ch[0])
    return 2 if cat in ("W", "F") else 1


def _display_width(text: str) -> int:
    """計算字串的終端顯示寬度。"""
    return sum(_char_width(ch) for ch in text)


@dataclass
class AoeOverlay:
    """AoE 覆蓋預覽資料。"""

    shape: str  # "sphere", "cone", "line", "cube"
    center_x: float  # AoE 中心 / 瞄準方向（公尺）
    center_y: float
    caster_x: float  # 施法者位置（公尺）
    caster_y: float
    radius_m: float = 0.0  # 球形半徑
    length_m: float = 0.0  # 錐形/線形長度
    width_m: float = 0.0  # 立方/線形寬度


# ---------------------------------------------------------------------------
# 角色標記形狀
# ---------------------------------------------------------------------------

# PC：填滿圓（5×5 dots），怪物：菱形，死亡：X
_CIRCLE_OFFSETS: list[tuple[int, int]] = []
for _dy in range(-2, 3):
    for _dx in range(-2, 3):
        if _dx * _dx + _dy * _dy <= 5:
            _CIRCLE_OFFSETS.append((_dx, _dy))

_DIAMOND_OFFSETS: list[tuple[int, int]] = [
    (0, -2),
    (-1, -1),
    (0, -1),
    (1, -1),
    (-2, 0),
    (-1, 0),
    (0, 0),
    (1, 0),
    (2, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
    (0, 2),
]

_X_OFFSETS: list[tuple[int, int]] = [
    (-2, -2),
    (-1, -1),
    (0, 0),
    (1, 1),
    (2, 2),
    (2, -2),
    (1, -1),
    (-1, 1),
    (-2, 2),
]


class BrailleMapCanvas(Widget):
    """Drawille 點字地圖 Widget。

    透過 reactive 屬性 map_state 驅動重繪——設定 map_state 時自動 render()。
    combatant_map 用於判斷角色陣營和存活狀態。
    """

    # Textual reactive：變更時觸發 render
    map_state: reactive[MapState | None] = reactive(None)
    combatant_map: reactive[dict[UUID, Character | Monster]] = reactive(dict)
    aoe_overlay: reactive[AoeOverlay | None] = reactive(None)

    DEFAULT_CSS = """
    BrailleMapCanvas {
        height: 1fr;
        min-height: 10;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._canvas = Canvas()
        # 快取渲染尺寸
        self._last_width: int = 0
        self._last_height: int = 0

    # ----- 座標轉換 -----

    def _compute_scale(
        self,
        widget_w: int,
        widget_h: int,
        world_w: float,
        world_h: float,
    ) -> float:
        """計算 pixel/meter scale，保持等比。"""
        canvas_w = widget_w * 2  # braille: 2 dots per char width
        canvas_h = widget_h * 4  # braille: 4 dots per char height
        if world_w <= 0 or world_h <= 0:
            return 1.0
        return min(canvas_w / world_w, canvas_h / world_h)

    def _meter_to_px(
        self,
        x: float,
        y: float,
        scale: float,
        canvas_h: int,
    ) -> tuple[int, int]:
        """公尺座標 → drawille pixel 座標（含 Y 翻轉）。

        遊戲 Y=0 在底部，braille Y=0 在頂部。
        """
        px_x = int(x * scale)
        px_y = canvas_h - 1 - int(y * scale)
        return px_x, px_y

    # ----- 繪製方法 -----

    def _draw_scale_lines(
        self,
        canvas: Canvas,
        world_w: float,
        world_h: float,
        scale: float,
        canvas_h: int,
        interval: float = 1.5,
    ) -> None:
        """繪製公尺刻度線（虛線風格：每隔 2 dots 畫 1 dot）。"""
        # 垂直線
        mx = 0.0
        while mx <= world_w + 1e-9:
            for step in range(int(world_h * scale)):
                if step % 3 == 0:  # 虛線
                    my = step / scale
                    px, py = self._meter_to_px(mx, my, scale, canvas_h)
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)
            mx += interval

        # 水平線
        my = 0.0
        while my <= world_h + 1e-9:
            for step in range(int(world_w * scale)):
                if step % 3 == 0:
                    mx_s = step / scale
                    px, py = self._meter_to_px(mx_s, my, scale, canvas_h)
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)
            my += interval

    def _draw_props(
        self,
        canvas: Canvas,
        ms: MapState,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製 Props——blocking 填滿、非 blocking 畫外框（公尺座標）。"""
        all_props = [*ms.manifest.props, *ms.props]
        for prop in all_props:
            if prop.hidden:
                continue
            # prop 佔據以其座標為中心的 1.5×1.5m 區域
            half = 0.75
            x0 = prop.x - half
            y0 = prop.y - half
            x1 = prop.x + half
            y1 = prop.y + half

            if prop.is_blocking:
                self._fill_rect(canvas, x0, y0, x1, y1, scale, canvas_h)
            else:
                self._outline_rect(canvas, x0, y0, x1, y1, scale, canvas_h)

    def _fill_rect(
        self,
        canvas: Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        scale: float,
        canvas_h: int,
    ) -> None:
        """填滿矩形區域（公尺座標，像素密集填充）。"""
        px0, _ = self._meter_to_px(x0, y0, scale, canvas_h)
        px1, _ = self._meter_to_px(x1, y1, scale, canvas_h)
        _, py0 = self._meter_to_px(x0, y1, scale, canvas_h)  # Y 翻轉
        _, py1 = self._meter_to_px(x0, y0, scale, canvas_h)
        for px in range(min(px0, px1), max(px0, px1) + 1):
            for py in range(min(py0, py1), max(py0, py1) + 1):
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

    def _outline_rect(
        self,
        canvas: Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        scale: float,
        canvas_h: int,
    ) -> None:
        """畫矩形外框（公尺座標）。"""
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % 4]
            seg_len = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
            steps = max(2, int(seg_len * scale))
            for s in range(steps + 1):
                t = s / steps
                mx = ax + (bx - ax) * t
                my = ay + (by - ay) * t
                px, py = self._meter_to_px(mx, my, scale, canvas_h)
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

    def _draw_walls(
        self,
        canvas: Canvas,
        ms: MapState,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製牆壁（Wall AABB 填滿）。"""
        all_walls = [*ms.manifest.walls, *ms.walls]
        for wall in all_walls:
            self._fill_rect(
                canvas, wall.x, wall.y, wall.x + wall.width, wall.y + wall.height, scale, canvas_h
            )

    def _draw_actor_shape(
        self,
        canvas: Canvas,
        actor: Actor,
        scale: float,
        canvas_h: int,
        combatant_map: dict[UUID, Character | Monster],
    ) -> None:
        """在 drawille 上畫角色的幾何形狀。"""
        cx, cy = self._meter_to_px(actor.x, actor.y, scale, canvas_h)

        if not actor.is_alive:
            offsets = _X_OFFSETS
        elif actor.combatant_type == "character":
            offsets = _CIRCLE_OFFSETS
        else:
            offsets = _DIAMOND_OFFSETS

        for dx, dy in offsets:
            px, py = cx + dx, cy + dy
            if px >= 0 and py >= 0:
                canvas.set(px, py)

    # ----- AoE 覆蓋繪製 -----

    def _draw_aoe(
        self,
        canvas: Canvas,
        overlay: AoeOverlay,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製 AoE 覆蓋預覽（外框 + 稀疏填充）。"""
        if overlay.shape == "sphere":
            self._draw_aoe_sphere(canvas, overlay, scale, canvas_h)
        elif overlay.shape == "cone":
            self._draw_aoe_cone(canvas, overlay, scale, canvas_h)
        elif overlay.shape == "cube":
            self._draw_aoe_cube(canvas, overlay, scale, canvas_h)
        elif overlay.shape == "line":
            self._draw_aoe_line(canvas, overlay, scale, canvas_h)

    def _draw_aoe_sphere(
        self,
        canvas: Canvas,
        ov: AoeOverlay,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製球形 AoE（圓形外框 + 稀疏填充）。"""
        r = ov.radius_m
        cx, cy = ov.center_x, ov.center_y

        # 外框：圓形輪廓
        steps = max(36, int(r * scale * 2))
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            mx = cx + r * math.cos(angle)
            my = cy + r * math.sin(angle)
            px, py = self._meter_to_px(mx, my, scale, canvas_h)
            if px >= 0 and py >= 0:
                canvas.set(px, py)

        # 稀疏填充
        r_px = int(r * scale)
        center_px, center_py = self._meter_to_px(cx, cy, scale, canvas_h)
        for dx in range(-r_px, r_px + 1):
            for dy in range(-r_px, r_px + 1):
                if dx * dx + dy * dy <= r_px * r_px and (dx + dy) % 4 == 0:
                    px, py = center_px + dx, center_py + dy
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)

    def _draw_aoe_cone(
        self,
        canvas: Canvas,
        ov: AoeOverlay,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製錐形 AoE（三角形外框 + 稀疏填充）。"""
        # 方向向量
        dx = ov.center_x - ov.caster_x
        dy = ov.center_y - ov.caster_y
        d_len = math.sqrt(dx * dx + dy * dy)
        if d_len < 1e-9:
            return
        ux, uy = dx / d_len, dy / d_len
        # 垂直向量
        nx, ny = -uy, ux

        length = ov.length_m
        half_width = length / 2  # 錐形終端寬度 = 長度

        # 三角形三點（公尺座標）
        tip_x, tip_y = ov.caster_x, ov.caster_y
        end_left_x = ov.caster_x + ux * length + nx * half_width
        end_left_y = ov.caster_y + uy * length + ny * half_width
        end_right_x = ov.caster_x + ux * length - nx * half_width
        end_right_y = ov.caster_y + uy * length - ny * half_width

        # 畫三條邊
        triangle = [
            (tip_x, tip_y),
            (end_left_x, end_left_y),
            (end_right_x, end_right_y),
        ]
        for i in range(3):
            ax, ay = triangle[i]
            bx, by = triangle[(i + 1) % 3]
            seg_steps = max(2, int(math.sqrt((bx - ax) ** 2 + (by - ay) ** 2) * scale))
            for s in range(seg_steps + 1):
                t = s / seg_steps
                mx = ax + (bx - ax) * t
                my = ay + (by - ay) * t
                px, py = self._meter_to_px(mx, my, scale, canvas_h)
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

        # 稀疏填充：沿前進方向掃描
        fill_steps = max(4, int(length * scale / 2))
        for fi in range(1, fill_steps):
            t = fi / fill_steps
            fwd = t * length
            half_w = t * half_width  # 隨距離遞增
            lat_steps = max(2, int(half_w * scale / 2))
            for li in range(-lat_steps, lat_steps + 1):
                if (fi + li) % 3 != 0:
                    continue
                lat = li / lat_steps * half_w
                mx = ov.caster_x + ux * fwd + nx * lat
                my = ov.caster_y + uy * fwd + ny * lat
                px, py = self._meter_to_px(mx, my, scale, canvas_h)
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

    def _draw_aoe_cube(
        self,
        canvas: Canvas,
        ov: AoeOverlay,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製立方 AoE（矩形外框 + 稀疏填充）。"""
        dx = ov.center_x - ov.caster_x
        dy = ov.center_y - ov.caster_y
        d_len = math.sqrt(dx * dx + dy * dy)
        if d_len < 1e-9:
            # 方向不明——以施法者為中心畫正方形
            side = ov.width_m
            half = side / 2
            corners_m = [
                (ov.caster_x - half, ov.caster_y - half),
                (ov.caster_x + half, ov.caster_y - half),
                (ov.caster_x + half, ov.caster_y + half),
                (ov.caster_x - half, ov.caster_y + half),
            ]
        else:
            ux, uy = dx / d_len, dy / d_len
            nx, ny = -uy, ux
            side = ov.width_m
            half = side / 2

            # 矩形四角：施法者前方 side 長，左右各 half
            corners_m = [
                (ov.caster_x - nx * half, ov.caster_y - ny * half),
                (ov.caster_x + nx * half, ov.caster_y + ny * half),
                (ov.caster_x + ux * side + nx * half, ov.caster_y + uy * side + ny * half),
                (ov.caster_x + ux * side - nx * half, ov.caster_y + uy * side - ny * half),
            ]

        # 畫四邊外框
        for i in range(4):
            ax, ay = corners_m[i]
            bx, by = corners_m[(i + 1) % 4]
            seg_steps = max(2, int(math.sqrt((bx - ax) ** 2 + (by - ay) ** 2) * scale))
            for s in range(seg_steps + 1):
                t = s / seg_steps
                mx = ax + (bx - ax) * t
                my = ay + (by - ay) * t
                px, py = self._meter_to_px(mx, my, scale, canvas_h)
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

        # 稀疏填充
        self._sparse_fill_polygon(canvas, corners_m, scale, canvas_h)

    def _draw_aoe_line(
        self,
        canvas: Canvas,
        ov: AoeOverlay,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製線形 AoE（窄矩形外框 + 稀疏填充）。"""
        dx = ov.center_x - ov.caster_x
        dy = ov.center_y - ov.caster_y
        d_len = math.sqrt(dx * dx + dy * dy)
        if d_len < 1e-9:
            return
        ux, uy = dx / d_len, dy / d_len
        nx, ny = -uy, ux

        length = ov.length_m
        half_w = ov.width_m / 2

        corners_m = [
            (ov.caster_x - nx * half_w, ov.caster_y - ny * half_w),
            (ov.caster_x + nx * half_w, ov.caster_y + ny * half_w),
            (ov.caster_x + ux * length + nx * half_w, ov.caster_y + uy * length + ny * half_w),
            (ov.caster_x + ux * length - nx * half_w, ov.caster_y + uy * length - ny * half_w),
        ]

        for i in range(4):
            ax, ay = corners_m[i]
            bx, by = corners_m[(i + 1) % 4]
            seg_steps = max(2, int(math.sqrt((bx - ax) ** 2 + (by - ay) ** 2) * scale))
            for s in range(seg_steps + 1):
                t = s / seg_steps
                mx = ax + (bx - ax) * t
                my = ay + (by - ay) * t
                px, py = self._meter_to_px(mx, my, scale, canvas_h)
                if px >= 0 and py >= 0:
                    canvas.set(px, py)

        self._sparse_fill_polygon(canvas, corners_m, scale, canvas_h)

    def _sparse_fill_polygon(
        self,
        canvas: Canvas,
        corners_m: list[tuple[float, float]],
        scale: float,
        canvas_h: int,
    ) -> None:
        """稀疏填充凸多邊形（每 4 pixel 畫 1 dot）。"""
        # 計算 bounding box（像素）
        pxs = []
        pys = []
        for mx, my in corners_m:
            px, py = self._meter_to_px(mx, my, scale, canvas_h)
            pxs.append(px)
            pys.append(py)
        min_px, max_px = min(pxs), max(pxs)
        min_py, max_py = min(pys), max(pys)

        # 掃描每個像素，用射線法判斷是否在多邊形內
        for px in range(max(0, min_px), max_px + 1):
            for py in range(max(0, min_py), max_py + 1):
                if (px + py) % 4 != 0:
                    continue
                if self._point_in_polygon(px, py, pxs, pys):
                    canvas.set(px, py)

    @staticmethod
    def _point_in_polygon(
        px: int,
        py: int,
        poly_x: list[int],
        poly_y: list[int],
    ) -> bool:
        """射線法判斷點是否在凸多邊形內。"""
        n = len(poly_x)
        inside = False
        j = n - 1
        for i in range(n):
            yi, yj = poly_y[i], poly_y[j]
            xi, xj = poly_x[i], poly_x[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside

    # ----- 標籤計算 -----

    def _compute_labels(
        self,
        ms: MapState,
        scale: float,
        canvas_h: int,
        widget_w: int,
        combatant_map: dict[UUID, Character | Monster],
        x_offset: int = 0,
    ) -> list[tuple[int, int, str, str]]:
        """計算角色彩色標籤的字元位置。

        回傳 [(char_x, char_y, label_text, rich_style), ...]
        x_offset: Y 軸標籤的欄位偏移量（座標軸佔用的寬度）
        """
        labels: list[tuple[int, int, str, str]] = []
        for actor in ms.actors:
            combatant = combatant_map.get(actor.combatant_id)
            if not combatant:
                continue

            px, py = self._meter_to_px(actor.x, actor.y, scale, canvas_h)
            # pixel → char 座標
            char_x = px // 2
            char_y = py // 4

            # 標籤放在角色右側 +2 字元，加上 Y 軸偏移
            label_x = char_x + 2 + x_offset

            # 標籤文字：名字首兩字
            if isinstance(combatant, Monster):
                name = (combatant.label or combatant.name)[:2]
            else:
                name = combatant.name[:2]

            if not actor.is_alive:
                style = "dim strike"
                label = f"💀{name}"
            elif actor.combatant_type == "character":
                if isinstance(combatant, Character) and combatant.is_ai_controlled:
                    style = "bold blue"
                else:
                    style = "bold green"
                label = f"{name}"
            else:
                # 怪物：顯示狀態描述
                style = "bold red"
                label = f"{name}"

            # 邊界檢查
            if 0 <= label_x < widget_w and char_y >= 0:
                labels.append((label_x, char_y, label, style))

        return labels

    # ----- Textual render -----

    def render(self) -> Text:
        """渲染 drawille 地圖 + Rich 彩色標籤 + 座標軸。"""
        ms = self.map_state
        if not ms:
            return Text("（等待地圖資料…）")

        # Widget 可用尺寸
        w = self.size.width
        h = self.size.height
        if w <= 0 or h <= 0:
            return Text("")

        world_w = ms.manifest.width
        world_h = ms.manifest.height
        interval = 1.5  # 刻度線間距（公尺）

        # 座標軸 margin
        max_label = f"{world_h:.0f}"
        y_margin = len(max_label) + 1  # Y 標籤寬度 + 空格
        x_margin = 1  # 底部 X 軸一行

        # 繪圖區扣除座標軸空間
        draw_w = max(1, w - y_margin)
        draw_h = max(1, h - x_margin)

        scale = self._compute_scale(draw_w, draw_h, world_w, world_h)
        canvas_h = draw_h * 4

        # 重建 canvas
        canvas = Canvas()

        # 1. 刻度線
        self._draw_scale_lines(canvas, world_w, world_h, scale, canvas_h, interval)

        # 2. 牆壁（Wall AABBs）
        self._draw_walls(canvas, ms, scale, canvas_h)

        # 3. Props（blocking=填滿，non-blocking=外框）
        self._draw_props(canvas, ms, scale, canvas_h)

        # 4. 角色形狀
        cmap = self.combatant_map
        for actor in ms.actors:
            self._draw_actor_shape(canvas, actor, scale, canvas_h, cmap)

        # 5. AoE 覆蓋
        if self.aoe_overlay:
            self._draw_aoe(canvas, self.aoe_overlay, scale, canvas_h)

        # 6. 取得 braille frame
        frame = canvas.frame()
        frame_lines = frame.split("\n") if frame else []

        # 確保行數填滿繪圖區高度
        while len(frame_lines) < draw_h:
            frame_lines.append("")

        # 裁切每行到繪圖區寬度
        for i in range(len(frame_lines)):
            if len(frame_lines[i]) > draw_w:
                frame_lines[i] = frame_lines[i][:draw_w]

        # 7. Y 軸標籤（公尺）
        y_label_width = y_margin - 1

        # 8. 建構 Rich.Text + 疊加彩色標籤 + Y 軸標籤
        labels = self._compute_labels(ms, scale, canvas_h, w, cmap, x_offset=y_margin)

        result = Text()
        for row_idx in range(min(len(frame_lines), draw_h)):
            # Y 軸標籤：計算此 char row 對應的公尺 Y
            pixel_y_center = row_idx * 4 + 2
            meter_y = (canvas_h - 1 - pixel_y_center) / scale

            # 對齊到最近的刻度線
            snapped_y = round(meter_y / interval) * interval
            _, line_pixel_y = self._meter_to_px(0, snapped_y, scale, canvas_h)
            line_char_row = line_pixel_y // 4

            if row_idx == line_char_row and 0 <= snapped_y <= world_h:
                y_label = f"{snapped_y:.0f}".rjust(y_label_width) + " "
            else:
                y_label = " " * y_margin

            line = frame_lines[row_idx]
            padded = y_label + line.ljust(draw_w)
            if len(padded) > w:
                padded = padded[:w]

            # 找此行的標籤
            row_labels = [(lx, lt, ls) for lx, ly, lt, ls in labels if ly == row_idx]

            if not row_labels:
                result.append(padded + "\n", style="bright_white")
            else:
                line_text = Text(padded, style="bright_white")
                for lx, lt, ls in sorted(row_labels, key=lambda x: x[0]):
                    if lx < w:
                        line_text = self._overlay_label(line_text, lx, lt, ls, w)
                result.append(line_text)
                result.append("\n")

        # 9. X 軸標籤行（公尺）
        x_axis = " " * y_margin
        mx = 0.0
        while mx <= world_w + 1e-9:
            line_px_x = int(mx * scale)
            line_char_col = line_px_x // 2
            label = f"{mx:.0f}"
            pos = line_char_col - len(label) // 2
            while len(x_axis) < y_margin + pos + len(label):
                x_axis += " "
            if pos >= 0:
                x_axis = x_axis[: y_margin + pos] + label + x_axis[y_margin + pos + len(label) :]
            mx += interval
        x_axis = x_axis[:w].rstrip()
        result.append(x_axis + "\n", style="dim")

        return result

    def render_to_plain(self, w: int, h: int) -> str:
        """渲染為純文字字串（用於 log 檔快照）。

        不需要 Textual widget context，給定字元寬高即可。
        標籤直接嵌入純文字（無 Rich markup）。
        """
        ms = self.map_state
        if not ms:
            return "（等待地圖資料…）"
        cmap = self.combatant_map
        return render_braille_map(ms, cmap, w, h)

    @staticmethod
    def _overlay_label(base: Text, x: int, label: str, style: str, max_w: int) -> Text:
        """在 Rich.Text 的指定位置覆蓋彩色標籤（CJK/emoji 寬度安全）。"""
        plain = base.plain
        if x >= len(plain):
            return base

        # 按顯示寬度截斷 label
        avail = max_w - x
        actual_label = ""
        used = 0
        for ch in label:
            cw = _char_width(ch)
            if used + cw > avail:
                break
            actual_label += ch
            used += cw

        # 計算 base 中需要覆蓋的字元數（braille 底層全是 1-col 字元）
        actual_end = min(x + used, len(plain))

        result = Text()
        if x > 0:
            result.append_text(base[:x])
        result.append(actual_label, style=style)
        if actual_end < len(plain):
            result.append_text(base[actual_end:])

        return result


# ---------------------------------------------------------------------------
# 獨立渲染函式（不需要 Textual Widget）
# ---------------------------------------------------------------------------


def render_braille_map(
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    w: int = 40,
    h: int = 12,
) -> str:
    """渲染 drawille 地圖為純文字字串（含座標軸）。

    用於 log 檔快照等不需要 Textual 的場景。
    標籤嵌入純文字（無 Rich markup / 顏色）。
    """
    renderer = BrailleMapCanvas()

    world_w = map_state.manifest.width
    world_h = map_state.manifest.height
    interval = 1.5

    # 座標軸 margin
    max_label = f"{world_h:.0f}"
    y_margin = len(max_label) + 1
    x_margin = 1

    draw_w = max(1, w - y_margin)
    draw_h = max(1, h - x_margin)

    scale = renderer._compute_scale(draw_w, draw_h, world_w, world_h)
    canvas_h = draw_h * 4

    canvas = Canvas()

    # 刻度線
    renderer._draw_scale_lines(canvas, world_w, world_h, scale, canvas_h, interval)

    # 牆壁
    renderer._draw_walls(canvas, map_state, scale, canvas_h)

    # Props
    renderer._draw_props(canvas, map_state, scale, canvas_h)

    # 角色形狀
    for actor in map_state.actors:
        renderer._draw_actor_shape(canvas, actor, scale, canvas_h, combatant_map)

    # 取得 braille frame
    frame = canvas.frame()
    frame_lines = frame.split("\n") if frame else []

    while len(frame_lines) < draw_h:
        frame_lines.append("")
    for i in range(len(frame_lines)):
        if len(frame_lines[i]) > draw_w:
            frame_lines[i] = frame_lines[i][:draw_w]

    # 計算標籤（含 Y 軸偏移）
    labels = renderer._compute_labels(
        map_state, scale, canvas_h, w, combatant_map, x_offset=y_margin
    )

    y_label_width = y_margin - 1

    result_lines: list[str] = []
    for row_idx in range(min(len(frame_lines), draw_h)):
        # Y 軸標籤（公尺）
        pixel_y_center = row_idx * 4 + 2
        meter_y = (canvas_h - 1 - pixel_y_center) / scale

        snapped_y = round(meter_y / interval) * interval
        _, line_pixel_y = renderer._meter_to_px(0, snapped_y, scale, canvas_h)
        line_char_row = line_pixel_y // 4

        if row_idx == line_char_row and 0 <= snapped_y <= world_h:
            y_label = f"{snapped_y:.0f}".rjust(y_label_width) + " "
        else:
            y_label = " " * y_margin

        line = frame_lines[row_idx]
        padded = y_label + line.ljust(draw_w)
        if len(padded) > w:
            padded = padded[:w]
        chars = list(padded)

        row_labels = [(lx, lt) for lx, ly, lt, _ls in labels if ly == row_idx]
        for lx, lt in sorted(row_labels, key=lambda x: x[0]):
            col = lx
            for ch in lt:
                if col >= len(chars):
                    break
                chars[col] = ch
                col += 1
                # 全形字（CJK / emoji）佔 2 欄，要吃掉下一格
                if _char_width(ch) == 2 and col < len(chars):
                    chars[col] = ""
                    col += 1

        result_lines.append("".join(chars).rstrip())

    # X 軸標籤行（公尺）
    x_axis = " " * y_margin
    mx = 0.0
    while mx <= world_w + 1e-9:
        line_px_x = int(mx * scale)
        line_char_col = line_px_x // 2
        label = f"{mx:.0f}"
        pos = line_char_col - len(label) // 2
        while len(x_axis) < y_margin + pos + len(label):
            x_axis += " "
        if pos >= 0:
            x_axis = x_axis[: y_margin + pos] + label + x_axis[y_margin + pos + len(label) :]
        mx += interval
    result_lines.append(x_axis[:w].rstrip())

    return "\n".join(result_lines)
