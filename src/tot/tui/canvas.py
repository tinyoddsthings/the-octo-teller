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

from tot.models import Actor, Character, Combatant, MapState, Monster
from tot.tui.render_buffer import RenderBuffer, RenderItem, TextureType

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
    combatant_map: reactive[dict[UUID, Combatant]] = reactive(dict)
    aoe_overlay: reactive[AoeOverlay | None] = reactive(None)
    render_buffer: reactive[RenderBuffer | None] = reactive(None)

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
        # 置中偏移量（像素）
        self._px_offset_x: int = 0
        self._px_offset_y: int = 0

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
        px_x = int(x * scale) + self._px_offset_x
        px_y = canvas_h - 1 - int(y * scale) - self._px_offset_y
        return px_x, px_y

    # ----- 繪製方法 -----

    def _draw_props(
        self,
        canvas: Canvas,
        ms: MapState,
        scale: float,
        canvas_h: int,
    ) -> None:
        """繪製 Props——依 bounds 形狀決定繪製方式（公尺座標）。"""
        from tot.models.enums import ShapeType

        all_props = [*ms.manifest.props, *ms.props]
        for prop in all_props:
            if prop.hidden:
                continue

            bounds = prop.bounds
            if bounds is not None and bounds.shape_type == ShapeType.CIRCLE:
                # 圓形 bounds
                if prop.is_blocking:
                    self._fill_circle(canvas, prop.x, prop.y, bounds.radius_m, scale, canvas_h)
                else:
                    self._outline_circle(canvas, prop.x, prop.y, bounds.radius_m, scale, canvas_h)
            else:
                # 矩形 bounds 或 fallback
                if bounds is not None and bounds.shape_type == ShapeType.RECTANGLE:
                    hw, hh = bounds.half_width_m, bounds.half_height_m
                else:
                    hw, hh = 0.75, 0.75  # 無 bounds 時 fallback 1.5×1.5m
                x0 = prop.x - hw
                y0 = prop.y - hh
                x1 = prop.x + hw
                y1 = prop.y + hh

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

    def _fill_circle(
        self,
        canvas: Canvas,
        cx: float,
        cy: float,
        radius_m: float,
        scale: float,
        canvas_h: int,
    ) -> None:
        """填滿圓形區域（公尺座標）。"""
        r_px = int(radius_m * scale)
        center_px, center_py = self._meter_to_px(cx, cy, scale, canvas_h)
        for dx in range(-r_px, r_px + 1):
            for dy in range(-r_px, r_px + 1):
                if dx * dx + dy * dy <= r_px * r_px:
                    px, py = center_px + dx, center_py + dy
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)

    def _outline_circle(
        self,
        canvas: Canvas,
        cx: float,
        cy: float,
        radius_m: float,
        scale: float,
        canvas_h: int,
    ) -> None:
        """畫圓形外框（公尺座標）。"""
        steps = max(24, int(radius_m * scale * 2 * math.pi))
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            mx = cx + radius_m * math.cos(angle)
            my = cy + radius_m * math.sin(angle)
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
        combatant_map: dict[UUID, Combatant],
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

    # ----- RenderBuffer 驅動繪製 -----

    def _draw_render_item(
        self,
        canvas: Canvas,
        item: RenderItem,
        scale: float,
        canvas_h: int,
    ) -> None:
        """依 RenderItem 的 texture 分派到對應繪製方法。"""
        from tot.models.enums import ShapeType

        cx, cy = item.center_x, item.center_y
        b = item.bounds

        match item.texture:
            case TextureType.FILL:
                hw = b.half_width_m if b.shape_type == ShapeType.RECTANGLE else 0.75
                hh = b.half_height_m if b.shape_type == ShapeType.RECTANGLE else 0.75
                self._fill_rect(canvas, cx - hw, cy - hh, cx + hw, cy + hh, scale, canvas_h)
            case TextureType.OUTLINE:
                hw = b.half_width_m if b.shape_type == ShapeType.RECTANGLE else 0.75
                hh = b.half_height_m if b.shape_type == ShapeType.RECTANGLE else 0.75
                self._outline_rect(canvas, cx - hw, cy - hh, cx + hw, cy + hh, scale, canvas_h)
            case TextureType.CIRCLE_FILL:
                self._fill_circle(canvas, cx, cy, b.radius_m, scale, canvas_h)
            case TextureType.CIRCLE_OUTLINE:
                self._outline_circle(canvas, cx, cy, b.radius_m, scale, canvas_h)
            case TextureType.ACTOR_CIRCLE:
                pcx, pcy = self._meter_to_px(cx, cy, scale, canvas_h)
                for dx, dy in _CIRCLE_OFFSETS:
                    px, py = pcx + dx, pcy + dy
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)
            case TextureType.ACTOR_DIAMOND:
                pcx, pcy = self._meter_to_px(cx, cy, scale, canvas_h)
                for dx, dy in _DIAMOND_OFFSETS:
                    px, py = pcx + dx, pcy + dy
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)
            case TextureType.ACTOR_X:
                pcx, pcy = self._meter_to_px(cx, cy, scale, canvas_h)
                for dx, dy in _X_OFFSETS:
                    px, py = pcx + dx, pcy + dy
                    if px >= 0 and py >= 0:
                        canvas.set(px, py)
            case TextureType.SPARSE:
                pass  # AoE 由既有 _draw_aoe 處理

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
        combatant_map: dict[UUID, Combatant],
        x_offset: int = 0,
    ) -> list[tuple[int, int, str, str]]:
        """計算角色彩色標籤的字元位置。

        回傳 [(char_x, char_y, label_text, rich_style), ...]
        x_offset: Y 軸標籤的欄位偏移量（座標軸佔用的寬度）
        """
        labels: list[tuple[int, int, str, str]] = []
        for actor in ms.actors:
            combatant = combatant_map.get(actor.combatant_id)

            px, py = self._meter_to_px(actor.x, actor.y, scale, canvas_h)
            # pixel → char 座標
            char_x = px // 2
            char_y = py // 4

            # 標籤放在角色右側 +1 字元，加上 Y 軸偏移
            label_x = char_x + 1 + x_offset

            if combatant:
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
                    style = "bold red"
                    label = f"{name}"
            elif actor.name:
                # Fallback：無 combatant 對照的 actor（如探索模式隊伍 token）
                name = actor.name[:2]
                if not actor.is_alive:
                    style = "dim strike"
                    label = f"💀{name}"
                elif actor.combatant_type == "character":
                    style = "bold green"
                    label = f"{name}"
                else:
                    style = "bold red"
                    label = f"{name}"
            else:
                continue

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

        # 置中偏移量（像素級）
        used_px_w = int(world_w * scale)
        used_px_h = int(world_h * scale)
        self._px_offset_x = max(0, (draw_w * 2 - used_px_w) // 2)
        self._px_offset_y = max(0, (draw_h * 4 - used_px_h) // 2)

        # 重建 canvas + 多色渲染
        cmap = self.combatant_map
        buf = self.render_buffer
        color_frames: dict[str, tuple[list[str], int]] = {}

        if buf and buf.items:
            # 多色路徑：merged canvas + 每個色彩群組一個 canvas
            canvas = Canvas()
            color_canvases: dict[str, tuple[Canvas, int]] = {}
            for item in buf.items:
                color = item.style or "bright_white"
                priority = item.layer.value
                if color not in color_canvases:
                    color_canvases[color] = (Canvas(), priority)
                else:
                    old_cvs, old_p = color_canvases[color]
                    color_canvases[color] = (old_cvs, max(old_p, priority))
                self._draw_render_item(canvas, item, scale, canvas_h)
                self._draw_render_item(color_canvases[color][0], item, scale, canvas_h)
            # AoE 覆蓋畫到 merged（白色）
            if self.aoe_overlay:
                self._draw_aoe(canvas, self.aoe_overlay, scale, canvas_h)
            # 取各色 frame lines（min_x/min_y=0 確保所有 canvas 從同一起點開始，避免色彩錯位）
            for color, (cvs, pri) in color_canvases.items():
                cf = cvs.frame(min_x=0, min_y=0)
                color_frames[color] = (cf.split("\n") if cf else [], pri)
        else:
            # Legacy fallback（無 RenderBuffer）
            canvas = Canvas()
            self._draw_walls(canvas, ms, scale, canvas_h)
            self._draw_props(canvas, ms, scale, canvas_h)
            for actor in ms.actors:
                self._draw_actor_shape(canvas, actor, scale, canvas_h, cmap)
            if self.aoe_overlay:
                self._draw_aoe(canvas, self.aoe_overlay, scale, canvas_h)

        # 取得 merged braille frame（min_x/min_y=0 與 color frames 對齊）
        frame = canvas.frame(min_x=0, min_y=0)
        frame_lines = frame.split("\n") if frame else []

        while len(frame_lines) < draw_h:
            frame_lines.append("")
        for i in range(len(frame_lines)):
            if len(frame_lines[i]) > draw_w:
                frame_lines[i] = frame_lines[i][:draw_w]

        # Y 軸標籤（公尺）
        y_label_width = y_margin - 1

        # 建構 Rich.Text + 多色 braille + 彩色標籤 + Y 軸標籤
        labels = self._compute_labels(ms, scale, canvas_h, w, cmap, x_offset=y_margin)
        blank_chars = {" ", "\u2800"}

        result = Text()
        for row_idx in range(min(len(frame_lines), draw_h)):
            pixel_y_center = row_idx * 4 + 2
            meter_y = (canvas_h - 1 - pixel_y_center) / scale

            snapped_y = round(meter_y / interval) * interval
            _, line_pixel_y = self._meter_to_px(0, snapped_y, scale, canvas_h)
            line_char_row = line_pixel_y // 4

            if row_idx == line_char_row and 0 <= snapped_y <= world_h:
                y_label = f"{snapped_y:.0f}".rjust(y_label_width) + " "
            else:
                y_label = " " * y_margin

            line = frame_lines[row_idx]

            # 找此行的標籤
            row_labels = [(lx, lt, ls) for lx, ly, lt, ls in labels if ly == row_idx]

            if color_frames:
                # 多色逐字元建構
                line_text = Text()
                # Y 軸標籤（dim）
                line_text.append(y_label, style="dim")
                # braille 區域逐字元套色
                padded_line = line.ljust(draw_w)[:draw_w]
                for col_idx, ch in enumerate(padded_line):
                    if ch in blank_chars:
                        line_text.append(ch)
                        continue
                    # 找此位置最高優先的色彩
                    best_color = "bright_white"
                    best_pri = -1
                    for color, (frames, pri) in color_frames.items():
                        if (
                            row_idx < len(frames)
                            and col_idx < len(frames[row_idx])
                            and frames[row_idx][col_idx] not in blank_chars
                            and pri > best_pri
                        ):
                            best_pri = pri
                            best_color = color
                    line_text.append(ch, style=best_color)
                # 疊加角色標籤
                for lx, lt, ls in sorted(row_labels, key=lambda x: x[0]):
                    if lx < w:
                        line_text = self._overlay_label(line_text, lx, lt, ls, w)
                # 裁切到 widget 寬度
                if len(line_text.plain) > w:
                    line_text = line_text[:w]
                result.append(line_text)
                result.append("\n")
            else:
                # Legacy 全白路徑
                padded = y_label + line.ljust(draw_w)
                if len(padded) > w:
                    padded = padded[:w]
                if not row_labels:
                    result.append(padded + "\n", style="bright_white")
                else:
                    line_text = Text(padded, style="bright_white")
                    for lx, lt, ls in sorted(row_labels, key=lambda x: x[0]):
                        if lx < w:
                            line_text = self._overlay_label(line_text, lx, lt, ls, w)
                    result.append(line_text)
                    result.append("\n")

        # 9. X 軸標籤行（公尺）——含碰撞檢測 + 置中偏移
        h_char_offset = self._px_offset_x // 2  # pixel → char
        x_axis = " " * y_margin
        last_end = -1
        mx = 0.0
        while mx <= world_w + 1e-9:
            line_px_x = int(mx * scale)
            line_char_col = line_px_x // 2 + h_char_offset
            label = f"{mx:.0f}"
            pos = line_char_col - len(label) // 2
            if pos >= 0 and y_margin + pos >= last_end:
                while len(x_axis) < y_margin + pos + len(label):
                    x_axis += " "
                x_axis = x_axis[: y_margin + pos] + label + x_axis[y_margin + pos + len(label) :]
                last_end = y_margin + pos + len(label) + 1
            mx += interval
        x_axis = x_axis[:w].rstrip()
        result.append(x_axis + "\n", style="dim")

        # 重置偏移量（避免影響其他呼叫者）
        self._px_offset_x = 0
        self._px_offset_y = 0

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
    combatant_map: dict[UUID, Combatant],
    w: int = 40,
    h: int = 12,
) -> str:
    """渲染 drawille 地圖為純文字字串（含座標軸）。

    透過 RenderBuffer 統一牆壁/Props/角色的繪製路徑。
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

    # 牆壁 / Props / 角色：透過 RenderBuffer 統一繪製
    buf = RenderBuffer(world_w, world_h)
    buf.build(map_state, combatant_map)
    for item in buf.items:
        renderer._draw_render_item(canvas, item, scale, canvas_h)

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

    # X 軸標籤行（公尺）——含碰撞檢測
    x_axis = " " * y_margin
    last_end = -1
    mx = 0.0
    while mx <= world_w + 1e-9:
        line_px_x = int(mx * scale)
        line_char_col = line_px_x // 2
        label = f"{mx:.0f}"
        pos = line_char_col - len(label) // 2
        if pos >= 0 and y_margin + pos >= last_end:
            while len(x_axis) < y_margin + pos + len(label):
                x_axis += " "
            x_axis = x_axis[: y_margin + pos] + label + x_axis[y_margin + pos + len(label) :]
            last_end = y_margin + pos + len(label) + 1
        mx += interval
    result_lines.append(x_axis[:w].rstrip())

    return "\n".join(result_lines)
