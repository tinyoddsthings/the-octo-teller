"""T.O.T. Bone Engine 幾何碰撞形狀模型。

BoundingShape 是統一的幾何原語，取代散落各處的 SIZE_RADIUS_M 硬編碼查表。
只依賴 enums.py + math，不 import bone_engine/ 任何模組。
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from tot.models.enums import SIZE_RADIUS_M, ShapeType, Size


class BoundingShape(BaseModel):
    """統一幾何碰撞形狀。

    支援五種形狀：CIRCLE / RECTANGLE / CONE / LINE / CYLINDER。
    每種形狀只使用對應的欄位子集，其餘保持預設值。
    """

    shape_type: ShapeType = ShapeType.CIRCLE
    radius_m: float = 0.0  # 圓/柱半徑
    half_width_m: float = 0.0  # 矩形 X 半寬
    half_height_m: float = 0.0  # 矩形 Y 半高
    direction_deg: float | None = None  # CONE/LINE 朝向（0=+Y 北，順時針）
    angle_deg: float = 53.0  # CONE 全角（D&D 標準）
    length_m: float = 0.0  # CONE/LINE 長度
    height_m: float = 0.0  # CYLINDER 垂直高度（正=上，負=下）

    # ── 工廠方法 ────────────────────────────────

    @classmethod
    def circle(cls, radius_m: float) -> BoundingShape:
        """建立圓形碰撞區。"""
        return cls(shape_type=ShapeType.CIRCLE, radius_m=radius_m)

    @classmethod
    def rect(cls, width_m: float, height_m: float) -> BoundingShape:
        """建立矩形碰撞區。"""
        return cls(
            shape_type=ShapeType.RECTANGLE,
            half_width_m=width_m / 2,
            half_height_m=height_m / 2,
        )

    @classmethod
    def from_size(cls, size: Size) -> BoundingShape:
        """由 D&D 體型建立圓形碰撞區。"""
        return cls.circle(SIZE_RADIUS_M[size])

    @classmethod
    def cone(
        cls,
        length_m: float,
        direction_deg: float,
        angle_deg: float = 53.0,
    ) -> BoundingShape:
        """建立錐形區域。"""
        return cls(
            shape_type=ShapeType.CONE,
            length_m=length_m,
            direction_deg=direction_deg,
            angle_deg=angle_deg,
        )

    @classmethod
    def line(cls, length_m: float, direction_deg: float) -> BoundingShape:
        """建立零寬線段。"""
        return cls(
            shape_type=ShapeType.LINE,
            length_m=length_m,
            direction_deg=direction_deg,
        )

    @classmethod
    def cylinder(cls, radius_m: float, height_m: float) -> BoundingShape:
        """建立柱形區域（水平截面同 CIRCLE，加上垂直高度）。"""
        return cls(
            shape_type=ShapeType.CYLINDER,
            radius_m=radius_m,
            height_m=height_m,
        )

    # ── 幾何方法 ────────────────────────────────

    def contains_point(self, cx: float, cy: float, px: float, py: float) -> bool:
        """判斷點 (px, py) 是否在以 (cx, cy) 為中心的形狀內。"""
        dx = px - cx
        dy = py - cy

        if self.shape_type == ShapeType.CIRCLE or self.shape_type == ShapeType.CYLINDER:
            return dx * dx + dy * dy <= self.radius_m * self.radius_m

        if self.shape_type == ShapeType.RECTANGLE:
            return abs(dx) <= self.half_width_m and abs(dy) <= self.half_height_m

        if self.shape_type == ShapeType.CONE:
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > self.length_m or dist < 1e-9:
                return False
            # direction_deg: 0=+Y 北，順時針 → 轉為數學角度
            dir_rad = math.radians(90.0 - (self.direction_deg or 0.0))
            dir_x = math.cos(dir_rad)
            dir_y = math.sin(dir_rad)
            # dot product 求夾角
            cos_angle = (dx * dir_x + dy * dir_y) / dist
            half_angle_rad = math.radians(self.angle_deg / 2)
            return cos_angle >= math.cos(half_angle_rad)

        if self.shape_type == ShapeType.LINE:
            # 點到線段距離 < ε（零寬線段容差 0.01m = 1cm）
            dir_rad = math.radians(90.0 - (self.direction_deg or 0.0))
            end_x = self.length_m * math.cos(dir_rad)
            end_y = self.length_m * math.sin(dir_rad)
            # 投影到線段上
            seg_len_sq = end_x * end_x + end_y * end_y
            if seg_len_sq < 1e-12:
                return dx * dx + dy * dy <= 0.01 * 0.01
            t = max(0.0, min(1.0, (dx * end_x + dy * end_y) / seg_len_sq))
            closest_x = t * end_x
            closest_y = t * end_y
            dist_sq = (dx - closest_x) ** 2 + (dy - closest_y) ** 2
            return dist_sq <= 0.01 * 0.01

        return False  # pragma: no cover

    def overlaps(self, cx: float, cy: float, other: BoundingShape, ox: float, oy: float) -> bool:
        """判斷兩個形狀是否重疊（僅支援 CIRCLE/RECTANGLE 互碰）。

        CONE/LINE/CYLINDER 抛出 NotImplementedError。
        """
        unsupported = {ShapeType.CONE, ShapeType.LINE}
        if self.shape_type in unsupported or other.shape_type in unsupported:
            msg = f"overlaps() 不支援 {self.shape_type} × {other.shape_type}"
            raise NotImplementedError(msg)

        dx = abs(cx - ox)
        dy = abs(cy - oy)

        s_circle = self.shape_type in (ShapeType.CIRCLE, ShapeType.CYLINDER)
        o_circle = other.shape_type in (ShapeType.CIRCLE, ShapeType.CYLINDER)
        s_rect = self.shape_type == ShapeType.RECTANGLE
        o_rect = other.shape_type == ShapeType.RECTANGLE

        # CIRCLE × CIRCLE（含 CYLINDER）
        if s_circle and o_circle:
            r_sum = self.radius_m + other.radius_m
            return dx * dx + dy * dy < r_sum * r_sum

        # RECT × RECT
        if s_rect and o_rect:
            return (
                dx < self.half_width_m + other.half_width_m
                and dy < self.half_height_m + other.half_height_m
            )

        # CIRCLE × RECT（任一方向）
        if s_circle and o_rect:
            return _circle_rect_overlap(
                dx, dy, self.radius_m, other.half_width_m, other.half_height_m
            )
        if s_rect and o_circle:
            return _circle_rect_overlap(
                dx, dy, other.radius_m, self.half_width_m, self.half_height_m
            )

        return False  # pragma: no cover

    def to_aabb(self, cx: float, cy: float) -> tuple[float, float, float, float]:
        """回傳以 (cx, cy) 為中心的 AABB：(min_x, min_y, max_x, max_y)。"""
        if self.shape_type == ShapeType.CIRCLE or self.shape_type == ShapeType.CYLINDER:
            return (
                cx - self.radius_m,
                cy - self.radius_m,
                cx + self.radius_m,
                cy + self.radius_m,
            )

        if self.shape_type == ShapeType.RECTANGLE:
            return (
                cx - self.half_width_m,
                cy - self.half_height_m,
                cx + self.half_width_m,
                cy + self.half_height_m,
            )

        if self.shape_type == ShapeType.CONE:
            # 保守包圍盒：以長度為半徑的正方形
            return (
                cx - self.length_m,
                cy - self.length_m,
                cx + self.length_m,
                cy + self.length_m,
            )

        if self.shape_type == ShapeType.LINE:
            dir_rad = math.radians(90.0 - (self.direction_deg or 0.0))
            end_x = cx + self.length_m * math.cos(dir_rad)
            end_y = cy + self.length_m * math.sin(dir_rad)
            return (
                min(cx, end_x),
                min(cy, end_y),
                max(cx, end_x),
                max(cy, end_y),
            )

        return (cx, cy, cx, cy)  # pragma: no cover

    def intersects_line(
        self,
        cx: float,
        cy: float,
        target_bounds: BoundingShape,
        tx: float,
        ty: float,
    ) -> bool:
        """判斷此 LINE 是否穿過 target 的碰撞圓（line-circle intersection）。

        僅支援 self 為 LINE、target 為 CIRCLE/CYLINDER。
        """
        if self.shape_type != ShapeType.LINE:
            msg = f"intersects_line() 僅支援 LINE，收到 {self.shape_type}"
            raise TypeError(msg)

        target_r = target_bounds.radius_m
        dir_rad = math.radians(90.0 - (self.direction_deg or 0.0))
        end_x = cx + self.length_m * math.cos(dir_rad)
        end_y = cy + self.length_m * math.sin(dir_rad)

        # 線段 P0→P1 與圓心 C 的最近距離
        seg_dx = end_x - cx
        seg_dy = end_y - cy
        seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy

        if seg_len_sq < 1e-12:
            # 退化為點
            return (cx - tx) ** 2 + (cy - ty) ** 2 <= target_r * target_r

        t = max(0.0, min(1.0, ((tx - cx) * seg_dx + (ty - cy) * seg_dy) / seg_len_sq))
        closest_x = cx + t * seg_dx
        closest_y = cy + t * seg_dy
        dist_sq = (closest_x - tx) ** 2 + (closest_y - ty) ** 2
        return dist_sq <= target_r * target_r


def _circle_rect_overlap(dx: float, dy: float, r: float, hw: float, hh: float) -> bool:
    """圓與矩形重疊檢測（dx/dy 為中心距離的絕對值）。

    找矩形邊上離圓心最近的點，判斷距離是否 < r。
    """
    closest_x = min(dx, hw)
    closest_y = min(dy, hh)
    return closest_x * closest_x + closest_y * closest_y < r * r
