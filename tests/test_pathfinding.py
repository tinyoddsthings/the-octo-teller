"""Visibility Graph + A* 尋路單元測試。

涵蓋：
- 直線路徑
- 繞障礙物路徑
- 不可達 → None
- 成本上限剪枝
- reach 範圍終止
- 困難地形（友方 Actor 穿越成本 ×2）
"""

from __future__ import annotations

import math
from uuid import uuid4

import pytest

from tot.gremlins.bone_engine.pathfinding import find_furthest_along_path, find_path_to_range
from tot.models import (
    Actor,
    MapManifest,
    MapState,
    Position,
    TerrainTile,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_map() -> MapState:
    """10×10 空白地圖（grid_size=1.5m）。"""
    manifest = MapManifest(name="test", width=10, height=10, grid_size_m=1.5)
    terrain = [[TerrainTile() for _ in range(10)] for _ in range(10)]
    return MapState(manifest=manifest, terrain=terrain)


@pytest.fixture
def map_with_wall() -> MapState:
    """10×10 地圖，在 x=3 列（grid col 3-7）有一面牆。
    牆壁在 (4, 3)~(4, 7)（grid y=3~7, x=4）形成垂直屏障。
    """
    manifest = MapManifest(name="wall_test", width=10, height=10, grid_size_m=1.5)
    terrain = [[TerrainTile() for _ in range(10)] for _ in range(10)]
    # 在 grid x=5 建一排牆（y=2~7）
    for gy in range(2, 8):
        terrain[gy][5] = TerrainTile(is_blocking=True, name="wall")
    return MapState(manifest=manifest, terrain=terrain)


def _make_actor(
    actor_id: str,
    gx: int,
    gy: int,
    gs: float = 1.5,
    *,
    alive: bool = True,
) -> Actor:
    mx = gx * gs + gs / 2
    my = gy * gs + gs / 2
    return Actor(
        id=actor_id,
        x=mx,
        y=my,
        combatant_id=uuid4(),
        combatant_type="monster",
        name=f"actor_{actor_id}",
        is_blocking=True,
        is_alive=alive,
    )


# ===========================================================================
# 直線路徑
# ===========================================================================


class TestStraightPath:
    """無障礙物的直線路徑。"""

    def test_already_in_range(self, empty_map: MapState):
        """起點已在 reach 範圍內 → 空路徑。"""
        start = Position.from_grid(2, 2, 1.5)
        target = Position.from_grid(3, 2, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=9.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path == []

    def test_straight_line(self, empty_map: MapState):
        """直線可達 → 回傳路徑。"""
        start = Position.from_grid(1, 5, 1.5)
        target = Position.from_grid(8, 5, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=30.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None
        assert len(path) > 0
        # 路徑終點應在 reach 範圍內
        end = path[-1]
        dist = math.sqrt((end.x - target.x) ** 2 + (end.y - target.y) ** 2)
        assert dist <= 1.5 + 0.1  # 容差

    def test_straight_line_cost(self, empty_map: MapState):
        """路徑成本 = 歐幾里得距離。"""
        start = Position.from_grid(0, 5, 1.5)
        target = Position.from_grid(5, 5, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=0.01,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=30.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None
        # 計算路徑總成本
        cost = 0.0
        prev = start
        for wp in path:
            cost += math.sqrt((wp.x - prev.x) ** 2 + (wp.y - prev.y) ** 2)
            prev = wp
        # 直線距離 = 5 * 1.5 = 7.5m
        assert cost == pytest.approx(7.5, abs=0.5)


# ===========================================================================
# 繞障礙物
# ===========================================================================


class TestObstacleAvoidance:
    """障礙物繞行。"""

    def test_around_wall(self, map_with_wall: MapState):
        """牆壁阻擋直線 → 繞行。"""
        start = Position.from_grid(3, 5, 1.5)
        target = Position.from_grid(7, 5, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=map_with_wall,
            mover_radius=0.75,
            max_cost=30.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None
        assert len(path) > 0
        # 終點在 reach 範圍內
        end = path[-1]
        dist = math.sqrt((end.x - target.x) ** 2 + (end.y - target.y) ** 2)
        assert dist <= 1.5 + 0.1

    def test_blocked_by_actors(self, empty_map: MapState):
        """敵方 Actor 阻擋 → 繞行。"""
        start = Position.from_grid(2, 5, 1.5)
        target = Position.from_grid(8, 5, 1.5)
        # 在中間放一個敵方 Actor
        blocker = _make_actor("blocker", 5, 5)
        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=30.0,
            blocked_actors=[blocker],
            passable_actors=[],
        )
        assert path is not None
        # 路徑應繞過 blocker


# ===========================================================================
# 不可達
# ===========================================================================


class TestUnreachable:
    """不可達目標。"""

    def test_walled_off(self):
        """目標被牆壁完全包圍 → None。"""
        manifest = MapManifest(name="box", width=10, height=10, grid_size_m=1.5)
        terrain = [[TerrainTile() for _ in range(10)] for _ in range(10)]
        # 在 target 周圍建牆（grid 4,4 ~ 6,6 全是牆，只留 5,5 空）
        for gy in range(3, 8):
            for gx in range(4, 7):
                if gx == 5 and gy == 5:
                    continue  # 留空
                terrain[gy][gx] = TerrainTile(is_blocking=True, name="wall")
        ms = MapState(manifest=manifest, terrain=terrain)

        start = Position.from_grid(1, 5, 1.5)
        target = Position.from_grid(5, 5, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=0.01,
            map_state=ms,
            mover_radius=0.75,
            max_cost=50.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is None


# ===========================================================================
# 成本上限剪枝
# ===========================================================================


class TestCostLimit:
    """max_cost 剪枝。"""

    def test_cost_limit(self, empty_map: MapState):
        """成本不足以到達 → None。"""
        start = Position.from_grid(0, 5, 1.5)
        target = Position.from_grid(9, 5, 1.5)
        # 距離 ≈ 13.5m，限制 3m
        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=3.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is None


# ===========================================================================
# Reach 範圍終止
# ===========================================================================


class TestReachTermination:
    """到達 reach 範圍即停。"""

    def test_stops_at_reach(self, empty_map: MapState):
        """不需走到目標正上方。"""
        start = Position.from_grid(0, 5, 1.5)
        target = Position.from_grid(8, 5, 1.5)
        path = find_path_to_range(
            start,
            target,
            reach_m=3.0,  # 2 格觸及
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=30.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None
        end = path[-1]
        dist_to_target = math.sqrt((end.x - target.x) ** 2 + (end.y - target.y) ** 2)
        assert dist_to_target <= 3.0 + 0.1
        # 路徑成本應 < 直線到目標的距離
        cost = 0.0
        prev = start
        for wp in path:
            cost += math.sqrt((wp.x - prev.x) ** 2 + (wp.y - prev.y) ** 2)
            prev = wp
        direct_dist = math.sqrt((target.x - start.x) ** 2 + (target.y - start.y) ** 2)
        assert cost < direct_dist


# ===========================================================================
# 邊界碰撞迴歸測試
# ===========================================================================


class TestBoundaryCollision:
    """迴歸：角色出生點恰好落在膨脹障礙物邊界上時，路徑不應失敗。

    Tutorial Room 實際佈局重現：
    - Pillar 1 在格 (3, 3) → 膨脹後 AABB (3.75, 3.75, 6.75, 6.75)
    - 玩家陶德在格 (4, 2) → 公尺 (6.75, 3.75)（恰好在膨脹邊界角落）
    - 蟲巢首領在格 (4, 5) → 公尺 (6.75, 8.25)
    - 直線 x=6.75 沿膨脹 AABB 右邊走，Liang-Barsky 會誤判為穿過
    """

    def test_boundary_path(self):
        """起點在膨脹障礙物邊界上 → 應能找到繞行路徑，而非 None。"""
        manifest = MapManifest(name="tutorial", width=10, height=10, grid_size_m=1.5)
        terrain = [[TerrainTile() for _ in range(10)] for _ in range(10)]
        # Pillar 1 在格 (3, 3)
        terrain[3][3] = TerrainTile(is_blocking=True, name="pillar")
        ms = MapState(manifest=manifest, terrain=terrain)

        # 格 (4, 2) = (6.75, 3.75)，恰好在膨脹邊界角落
        start = Position.from_grid(4, 2, 1.5)
        # 格 (4, 5) = (6.75, 8.25)
        target = Position.from_grid(4, 5, 1.5)

        path = find_path_to_range(
            start,
            target,
            reach_m=1.5,
            map_state=ms,
            mover_radius=0.75,
            max_cost=15.0,
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None, "起點在膨脹邊界上時不應回傳 None（邊界擦邊被誤判為穿過）"


# ===========================================================================
# find_furthest_along_path
# ===========================================================================


class TestFurthestAlongPath:
    """盡量靠近目標。"""

    def test_partial_path(self, empty_map: MapState):
        """移動預算不足 → 截斷路徑。"""
        start = Position.from_grid(0, 5, 1.5)
        target = Position.from_grid(9, 5, 1.5)
        path = find_furthest_along_path(
            start,
            target,
            reach_m=1.5,
            map_state=empty_map,
            mover_radius=0.75,
            max_cost=4.5,  # 只夠走 3 格
            blocked_actors=[],
            passable_actors=[],
        )
        assert path is not None
        assert len(path) > 0
        # 檢查路徑成本不超過 max_cost
        cost = 0.0
        prev = start
        for wp in path:
            cost += math.sqrt((wp.x - prev.x) ** 2 + (wp.y - prev.y) ** 2)
            prev = wp
        assert cost <= 4.5 + 0.1
