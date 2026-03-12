"""BrailleMapCanvas 單元測試——座標轉換、AoE overlay 資料結構。"""

from __future__ import annotations

import pytest

from tot.tui.canvas import AoeOverlay, BrailleMapCanvas


@pytest.fixture
def canvas_widget():
    """建立一個 BrailleMapCanvas 實例（不需要 Textual app）。"""
    return BrailleMapCanvas()


class TestMeterToPx:
    """meter_to_px 座標轉換。"""

    def test_origin_maps_to_bottom_left(self, canvas_widget):
        """遊戲原點 (0,0) 應對應到 drawille 畫布左下角。"""
        scale = 10.0
        canvas_h = 80  # 20 rows * 4 dots
        px, py = canvas_widget._meter_to_px(0, 0, scale, canvas_h)
        assert px == 0
        assert py == canvas_h - 1  # Y 翻轉：底部

    def test_y_flip(self, canvas_widget):
        """遊戲 Y 增大時，braille Y 應減小（往頂部移動）。"""
        scale = 10.0
        canvas_h = 80
        _, py_low = canvas_widget._meter_to_px(0, 0, scale, canvas_h)
        _, py_high = canvas_widget._meter_to_px(0, 5, scale, canvas_h)
        assert py_high < py_low

    def test_scale_multiplication(self, canvas_widget):
        """x 座標應乘以 scale。"""
        scale = 6.67
        canvas_h = 80
        px, _ = canvas_widget._meter_to_px(3.0, 0, scale, canvas_h)
        assert px == int(3.0 * scale)

    def test_large_world_coordinate(self, canvas_widget):
        """大座標應正確轉換。"""
        scale = 5.0
        canvas_h = 200
        px, py = canvas_widget._meter_to_px(10.0, 20.0, scale, canvas_h)
        assert px == 50
        assert py == 200 - 1 - 100  # canvas_h - 1 - int(20 * 5)


class TestComputeScale:
    """_compute_scale 等比計算。"""

    def test_square_world_square_widget(self, canvas_widget):
        """正方形世界 + 正方形 widget → scale 一致。"""
        # widget 20x10 chars → 40x40 dots
        scale = canvas_widget._compute_scale(20, 10, 10.0, 10.0)
        # canvas_w=40, canvas_h=40, world=10x10 → min(4, 4) = 4
        assert scale == pytest.approx(4.0)

    def test_wide_world_constrained_by_width(self, canvas_widget):
        """寬世界被 widget 寬度限制。"""
        scale = canvas_widget._compute_scale(40, 10, 20.0, 5.0)
        # canvas_w=80, canvas_h=40 → min(80/20, 40/5) = min(4, 8) = 4
        assert scale == pytest.approx(4.0)

    def test_tall_world_constrained_by_height(self, canvas_widget):
        """高世界被 widget 高度限制。"""
        scale = canvas_widget._compute_scale(40, 10, 5.0, 20.0)
        # canvas_w=80, canvas_h=40 → min(80/5, 40/20) = min(16, 2) = 2
        assert scale == pytest.approx(2.0)

    def test_zero_world_returns_one(self, canvas_widget):
        """零尺寸世界回傳 1.0。"""
        assert canvas_widget._compute_scale(20, 10, 0, 0) == 1.0
        assert canvas_widget._compute_scale(20, 10, 0, 10) == 1.0


class TestAoeOverlay:
    """AoeOverlay 資料結構。"""

    def test_sphere_overlay(self):
        ov = AoeOverlay(
            shape="sphere",
            center_x=5.0,
            center_y=5.0,
            caster_x=3.0,
            caster_y=3.0,
            radius_m=6.0,
        )
        assert ov.shape == "sphere"
        assert ov.radius_m == 6.0
        assert ov.length_m == 0.0

    def test_cone_overlay(self):
        ov = AoeOverlay(
            shape="cone",
            center_x=5.0,
            center_y=5.0,
            caster_x=3.0,
            caster_y=3.0,
            length_m=4.5,
        )
        assert ov.shape == "cone"
        assert ov.length_m == 4.5

    def test_cube_overlay(self):
        ov = AoeOverlay(
            shape="cube",
            center_x=5.0,
            center_y=5.0,
            caster_x=3.0,
            caster_y=3.0,
            width_m=4.5,
        )
        assert ov.shape == "cube"
        assert ov.width_m == 4.5

    def test_line_overlay(self):
        ov = AoeOverlay(
            shape="line",
            center_x=5.0,
            center_y=5.0,
            caster_x=3.0,
            caster_y=3.0,
            length_m=18.0,
            width_m=1.5,
        )
        assert ov.shape == "line"
        assert ov.length_m == 18.0
        assert ov.width_m == 1.5


class TestPointInPolygon:
    """射線法多邊形判定。"""

    def test_point_inside_square(self):
        # 正方形 (0,0) → (10,0) → (10,10) → (0,10)
        poly_x = [0, 10, 10, 0]
        poly_y = [0, 0, 10, 10]
        assert BrailleMapCanvas._point_in_polygon(5, 5, poly_x, poly_y) is True

    def test_point_outside_square(self):
        poly_x = [0, 10, 10, 0]
        poly_y = [0, 0, 10, 10]
        assert BrailleMapCanvas._point_in_polygon(15, 5, poly_x, poly_y) is False

    def test_point_inside_triangle(self):
        poly_x = [0, 10, 5]
        poly_y = [0, 0, 10]
        assert BrailleMapCanvas._point_in_polygon(5, 3, poly_x, poly_y) is True

    def test_point_outside_triangle(self):
        poly_x = [0, 10, 5]
        poly_y = [0, 0, 10]
        assert BrailleMapCanvas._point_in_polygon(0, 10, poly_x, poly_y) is False
