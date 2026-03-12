"""幾何基元與碰撞偵測。

提供 AABB（軸對齊矩形）與圓形的碰撞偵測、線段交叉檢查，
以及從地圖狀態提取靜態障礙物的功能。

用於 pathfinding.py 的 Visibility Graph + A* 和 move_entity 的碰撞驗證。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tot.models import MapState


@dataclass(slots=True)
class AABB:
    """軸對齊矩形（牆壁、Prop 障礙物）。"""

    min_x: float
    min_y: float
    max_x: float
    max_y: float


def circle_aabb_overlap(cx: float, cy: float, r: float, aabb: AABB) -> bool:
    """圓形 (cx, cy, r) 是否與 AABB 重疊。

    找到 AABB 上離圓心最近的點，檢查距離是否 < r。
    """
    # 把圓心 clamp 到 AABB 範圍，得到最近點
    nearest_x = max(aabb.min_x, min(cx, aabb.max_x))
    nearest_y = max(aabb.min_y, min(cy, aabb.max_y))
    dx = cx - nearest_x
    dy = cy - nearest_y
    return dx * dx + dy * dy < r * r


def segment_aabb_intersect(x1: float, y1: float, x2: float, y2: float, aabb: AABB) -> bool:
    """線段 (x1,y1)→(x2,y2) 是否穿過 AABB。

    使用 Liang-Barsky 線段裁剪演算法。
    """
    dx = x2 - x1
    dy = y2 - y1

    # 四條邊的 p, q 值
    checks = [
        (-dx, x1 - aabb.min_x),  # 左
        (dx, aabb.max_x - x1),  # 右
        (-dy, y1 - aabb.min_y),  # 下
        (dy, aabb.max_y - y1),  # 上
    ]

    t_enter = 0.0
    t_exit = 1.0

    for p, q in checks:
        if abs(p) < 1e-12:
            # 線段與該邊平行
            if q < 0:
                return False  # 在邊外側
        else:
            t = q / p
            if p < 0:
                t_enter = max(t_enter, t)
            else:
                t_exit = min(t_exit, t)
            if t_enter > t_exit:
                return False

    return True


def inflate_aabb(aabb: AABB, radius: float) -> AABB:
    """Minkowski 膨脹：將 AABB 各邊向外擴展 radius。

    膨脹後的 AABB 用於 Configuration Space，讓路徑搜索
    從「膨脹體通過」簡化為「點通過」。
    """
    return AABB(
        min_x=aabb.min_x - radius,
        min_y=aabb.min_y - radius,
        max_x=aabb.max_x + radius,
        max_y=aabb.max_y + radius,
    )


def extract_static_obstacles(map_state: MapState) -> list[AABB]:
    """從地圖提取所有靜態障礙物的 AABB 列表。

    包含：
    - Wall AABB（新格式）
    - is_blocking 的 terrain cell（舊格式相容）
    - is_blocking 的 manifest Props（牆壁等靜態物）
    - is_blocking 的 runtime Props（動態放置的物件）
    不含 Actor（Actor 是動態的，由 pathfinding 層另外處理）。
    """
    m = map_state.manifest
    gs = m.grid_size_m
    obstacles: list[AABB] = []

    # Wall AABB（新格式）
    for w in map_state.walls:
        obstacles.append(AABB(w.x, w.y, w.x + w.width, w.y + w.height))
    for w in m.walls:
        obstacles.append(AABB(w.x, w.y, w.x + w.width, w.y + w.height))

    # 地形阻擋（舊格式相容）
    if map_state.terrain:
        for gy, row in enumerate(map_state.terrain):
            for gx, tile in enumerate(row):
                if tile.is_blocking:
                    obstacles.append(AABB(gx * gs, gy * gs, (gx + 1) * gs, (gy + 1) * gs))

    # manifest 靜態 Props
    for p in m.props:
        if p.is_blocking:
            pgx = int(math.floor(p.x / gs))
            pgy = int(math.floor(p.y / gs))
            obstacles.append(AABB(pgx * gs, pgy * gs, (pgx + 1) * gs, (pgy + 1) * gs))

    # runtime 動態 Props
    for p in map_state.props:
        if p.is_blocking:
            pgx = int(math.floor(p.x / gs))
            pgy = int(math.floor(p.y / gs))
            obstacles.append(AABB(pgx * gs, pgy * gs, (pgx + 1) * gs, (pgy + 1) * gs))

    return _deduplicate_aabbs(obstacles)


def _deduplicate_aabbs(obstacles: list[AABB]) -> list[AABB]:
    """去除重複的 AABB（同一格可能被 terrain + prop 重複標記）。"""
    seen: set[tuple[float, float, float, float]] = set()
    result: list[AABB] = []
    for ob in obstacles:
        key = (ob.min_x, ob.min_y, ob.max_x, ob.max_y)
        if key not in seen:
            seen.add(key)
            result.append(ob)
    return result
