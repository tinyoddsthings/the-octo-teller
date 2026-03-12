"""幾何基元單元測試。

涵蓋：
- 圓-AABB 碰撞（相交、相切、不相交）
- 線段-AABB 交叉（穿過、擦邊、不相交）
- AABB 膨脹
- 障礙物提取
"""

from __future__ import annotations

import pytest

from tot.gremlins.bone_engine.geometry import (
    AABB,
    circle_aabb_overlap,
    extract_static_obstacles,
    inflate_aabb,
    segment_aabb_intersect,
)
from tot.models import (
    MapManifest,
    MapState,
    Prop,
    Wall,
)

# ===========================================================================
# 圓-AABB 碰撞
# ===========================================================================


class TestCircleAABBOverlap:
    """circle_aabb_overlap 碰撞偵測。"""

    def test_circle_inside_aabb(self):
        """圓心在 AABB 內部 → 重疊。"""
        aabb = AABB(0, 0, 2, 2)
        assert circle_aabb_overlap(1, 1, 0.5, aabb) is True

    def test_circle_outside_aabb(self):
        """圓心遠離 AABB → 不重疊。"""
        aabb = AABB(0, 0, 2, 2)
        assert circle_aabb_overlap(5, 5, 0.5, aabb) is False

    def test_circle_touching_edge(self):
        """圓形剛好觸碰 AABB 邊（不算重疊，用 <）。"""
        aabb = AABB(0, 0, 2, 2)
        # 圓心 (3, 1)，半徑 1 → 最近點 (2, 1)，距離 = 1 = r → 不重疊
        assert circle_aabb_overlap(3, 1, 1.0, aabb) is False

    def test_circle_overlapping_edge(self):
        """圓形超過 AABB 邊 → 重疊。"""
        aabb = AABB(0, 0, 2, 2)
        # 圓心 (2.5, 1)，半徑 1 → 最近點 (2, 1)，距離 = 0.5 < 1 → 重疊
        assert circle_aabb_overlap(2.5, 1, 1.0, aabb) is True

    def test_circle_near_corner(self):
        """圓形靠近 AABB 角落但不重疊。"""
        aabb = AABB(0, 0, 2, 2)
        # 圓心 (3, 3)，半徑 1 → 最近點 (2, 2)，距離 = sqrt(2) ≈ 1.41 > 1
        assert circle_aabb_overlap(3, 3, 1.0, aabb) is False

    def test_circle_overlapping_corner(self):
        """圓形與 AABB 角落重疊。"""
        aabb = AABB(0, 0, 2, 2)
        # 圓心 (2.5, 2.5)，半徑 1 → 最近點 (2, 2)，距離 = sqrt(0.5) ≈ 0.71 < 1
        assert circle_aabb_overlap(2.5, 2.5, 1.0, aabb) is True


# ===========================================================================
# 線段-AABB 交叉
# ===========================================================================


class TestSegmentAABBIntersect:
    """segment_aabb_intersect 線段裁剪。"""

    def test_segment_through_aabb(self):
        """線段穿過 AABB → True。"""
        aabb = AABB(1, 1, 3, 3)
        assert segment_aabb_intersect(0, 2, 4, 2, aabb) is True

    def test_segment_miss_aabb(self):
        """線段完全在 AABB 外 → False。"""
        aabb = AABB(1, 1, 3, 3)
        assert segment_aabb_intersect(0, 0, 4, 0, aabb) is False

    def test_segment_diagonal_through(self):
        """對角線段穿過 AABB → True。"""
        aabb = AABB(1, 1, 3, 3)
        assert segment_aabb_intersect(0, 0, 4, 4, aabb) is True

    def test_segment_inside_aabb(self):
        """線段完全在 AABB 內 → True。"""
        aabb = AABB(0, 0, 4, 4)
        assert segment_aabb_intersect(1, 1, 3, 3, aabb) is True

    def test_segment_parallel_outside(self):
        """線段與 AABB 邊平行但在外側 → False。"""
        aabb = AABB(1, 1, 3, 3)
        assert segment_aabb_intersect(0, 0, 0, 4, aabb) is False

    def test_segment_touching_corner(self):
        """線段經過 AABB 角落 → True。"""
        aabb = AABB(1, 1, 3, 3)
        # 從 (0,0) 到 (1,1) 的線段剛好碰到角落
        assert segment_aabb_intersect(0, 0, 1, 1, aabb) is True

    def test_zero_length_segment_inside(self):
        """零長度線段在 AABB 內 → True。"""
        aabb = AABB(0, 0, 2, 2)
        assert segment_aabb_intersect(1, 1, 1, 1, aabb) is True

    def test_zero_length_segment_outside(self):
        """零長度線段在 AABB 外 → False。"""
        aabb = AABB(0, 0, 2, 2)
        assert segment_aabb_intersect(5, 5, 5, 5, aabb) is False


# ===========================================================================
# AABB 膨脹
# ===========================================================================


class TestInflateAABB:
    """inflate_aabb Minkowski 膨脹。"""

    def test_inflate(self):
        """膨脹後 AABB 各邊擴展 radius。"""
        aabb = AABB(1, 1, 3, 3)
        inflated = inflate_aabb(aabb, 0.5)
        assert inflated.min_x == pytest.approx(0.5)
        assert inflated.min_y == pytest.approx(0.5)
        assert inflated.max_x == pytest.approx(3.5)
        assert inflated.max_y == pytest.approx(3.5)

    def test_inflate_zero(self):
        """膨脹 0 → 不變。"""
        aabb = AABB(1, 2, 3, 4)
        inflated = inflate_aabb(aabb, 0)
        assert inflated.min_x == 1 and inflated.max_x == 3


# ===========================================================================
# 障礙物提取
# ===========================================================================


class TestExtractStaticObstacles:
    """extract_static_obstacles 從地圖提取 AABB。"""

    def test_empty_map(self):
        """空白地圖 → 無障礙物。"""
        manifest = MapManifest(name="test", width=7.5, height=7.5)
        ms = MapState(manifest=manifest)
        assert extract_static_obstacles(ms) == []

    def test_blocking_wall(self):
        """Wall AABB → 產生障礙物。"""
        w = Wall(x=4.5, y=3.0, width=1.5, height=1.5, name="wall")
        manifest = MapManifest(name="test", width=7.5, height=7.5, walls=[w])
        ms = MapState(manifest=manifest, walls=[w])
        obs = extract_static_obstacles(ms)
        # manifest.walls + map_state.walls 各一，去重後 = 1
        assert len(obs) == 1
        assert obs[0].min_x == pytest.approx(4.5)
        assert obs[0].min_y == pytest.approx(3.0)

    def test_blocking_prop(self):
        """阻擋 Prop → 產生 AABB（以 prop 位置為中心的 1.5m × 1.5m）。"""
        prop = Prop(
            id="w1",
            x=3.75,
            y=3.75,
            symbol="🧱",
            is_blocking=True,
            prop_type="wall",
        )
        manifest = MapManifest(name="test", width=7.5, height=7.5, props=[prop])
        ms = MapState(manifest=manifest)
        obs = extract_static_obstacles(ms)
        assert len(obs) == 1
        assert obs[0].min_x == pytest.approx(3.0)
        assert obs[0].min_y == pytest.approx(3.0)

    def test_deduplication(self):
        """manifest.walls 和 map_state.walls 相同位置 → 去重後只有一個。"""
        w = Wall(x=3.0, y=3.0, width=1.5, height=1.5, name="wall")
        manifest = MapManifest(name="test", width=7.5, height=7.5, walls=[w])
        ms = MapState(manifest=manifest, walls=[w])
        obs = extract_static_obstacles(ms)
        assert len(obs) == 1  # 去重後只有一個
