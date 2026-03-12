"""Visibility Graph + A* 連續空間尋路。

取代 spatial.py 的 bfs_path_to_range（格級 BFS），
在連續座標上搜索歐幾里得最短路徑。

核心概念：
- 提取靜態障礙物 → AABB 列表
- Minkowski 膨脹（障礙物 + 移動者半徑）→ Configuration Space
- Visibility Graph：膨脹後角落 + 起終點，有視線則連邊
- A*：啟發式 = max(0, euclidean_to_target - reach)
"""

from __future__ import annotations

import heapq
import math

from tot.gremlins.bone_engine.geometry import (
    AABB,
    extract_static_obstacles,
    inflate_aabb,
    segment_aabb_intersect,
)
from tot.models import (
    SIZE_RADIUS_M,
    Actor,
    MapState,
    Position,
    Size,
)


def find_path_to_range(
    start: Position,
    target: Position,
    reach_m: float,
    map_state: MapState,
    mover_radius: float,
    max_cost: float,
    blocked_actors: list[Actor],
    passable_actors: list[Actor],
) -> list[Position] | None:
    """連續空間 A* 尋路——找到距 target ≤ reach_m 的最短路。

    Parameters
    ----------
    start : Position
        移動者起始位置（公尺座標）。
    target : Position
        目標位置（公尺座標）。
    reach_m : float
        攻擊/法術觸及距離（公尺）。到達距離 target ≤ reach_m 即可停止。
    map_state : MapState
        地圖狀態（地形 + Props）。
    mover_radius : float
        移動者碰撞半徑（公尺）。
    max_cost : float
        移動預算（公尺），g(n) > max_cost 時剪枝。
    blocked_actors : list[Actor]
        敵對 Actor，視為不可穿越障礙。
    passable_actors : list[Actor]
        友方 Actor，可穿越但穿越成本 ×2。

    Returns
    -------
    list[Position] | None
        路徑點列表（不含起點），None 表示不可達。
        空列表 [] 表示起點已在範圍內。
    """
    # 已在範圍內
    dist_to_target = _euclidean(start.x, start.y, target.x, target.y)
    if dist_to_target <= reach_m:
        return []

    # 1. 提取障礙物
    static_obs = extract_static_obstacles(map_state)

    # 敵對 Actor → 近似為 AABB
    dynamic_obs: list[AABB] = []
    for actor in blocked_actors:
        r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        dynamic_obs.append(AABB(actor.x - r, actor.y - r, actor.x + r, actor.y + r))

    all_obstacles = static_obs + dynamic_obs

    # 2. Minkowski 膨脹
    inflated = [inflate_aabb(ob, mover_radius) for ob in all_obstacles]

    # 友方 Actor 佔據的 AABB（穿越邊成本 ×2，不阻擋）
    passable_aabbs: list[AABB] = []
    for actor in passable_actors:
        r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        passable_aabbs.append(
            inflate_aabb(
                AABB(actor.x - r, actor.y - r, actor.x + r, actor.y + r),
                mover_radius,
            )
        )

    # 3. 建 Visibility Graph 節點
    nodes: list[tuple[float, float]] = [(start.x, start.y)]

    # 計算 goal：如果已經在 reach_m 內用 target，否則沿方向走到 reach_m 邊緣
    # A* 終止條件是「距 target ≤ reach_m」，所以用 target 本身作 goal 引導
    goal = (target.x, target.y)
    nodes.append(goal)

    # 加入 reach 邊界點（沿 start→target 方向，距 target 恰好 reach_m）
    # 讓 A* 可以提早終止，不必走到 target 正上方
    if dist_to_target > reach_m:
        ratio = (dist_to_target - reach_m) / dist_to_target
        reach_x = start.x + (target.x - start.x) * ratio
        reach_y = start.y + (target.y - start.y) * ratio
        in_bounds = _in_map_bounds(reach_x, reach_y, map_state, mover_radius)
        if in_bounds and not _point_in_any_inflated(reach_x, reach_y, inflated):
            nodes.append((reach_x, reach_y))

    # 膨脹後障礙物的 4 個角作為節點
    corner_margin = 0.02  # 2cm 邊距，避免角落卡住
    for ob in inflated:
        corners = [
            (ob.min_x - corner_margin, ob.min_y - corner_margin),
            (ob.min_x - corner_margin, ob.max_y + corner_margin),
            (ob.max_x + corner_margin, ob.min_y - corner_margin),
            (ob.max_x + corner_margin, ob.max_y + corner_margin),
        ]
        for cx, cy in corners:
            in_bounds = _in_map_bounds(cx, cy, map_state, mover_radius)
            if in_bounds and not _point_in_any_inflated(cx, cy, inflated):
                nodes.append((cx, cy))

    # 4. 建邊（Visibility Graph）
    n = len(nodes)
    # 用鄰接表存邊
    adj: dict[int, list[tuple[int, float]]] = {i: [] for i in range(n)}

    for i in range(n):
        for j in range(i + 1, n):
            ix, iy = nodes[i]
            jx, jy = nodes[j]
            # 檢查視線：線段不穿過任何膨脹障礙物
            if not _segment_blocked(ix, iy, jx, jy, inflated):
                dist = _euclidean(ix, iy, jx, jy)
                # 穿越友方區域的成本加倍
                cost_mul = _passable_cost_multiplier(ix, iy, jx, jy, passable_aabbs)
                cost = dist * cost_mul
                adj[i].append((j, cost))
                adj[j].append((i, cost))

    # 5. A* 搜索
    start_idx = 0

    # 啟發式：max(0, 到 target 的距離 - reach_m)（admissible）
    def heuristic(idx: int) -> float:
        nx, ny = nodes[idx]
        return max(0.0, _euclidean(nx, ny, target.x, target.y) - reach_m)

    # (f, g, node_idx, parent_idx)
    open_set: list[tuple[float, float, int, int]] = []
    g_best: dict[int, float] = {start_idx: 0.0}
    parent: dict[int, int] = {}
    heapq.heappush(open_set, (heuristic(start_idx), 0.0, start_idx, -1))

    found_idx: int | None = None

    while open_set:
        f, g, current, prev = heapq.heappop(open_set)

        # 已有更好的路徑到 current
        if g > g_best.get(current, float("inf")):
            continue

        # 記錄 parent
        if prev >= 0 and (current not in parent or g <= g_best[current]):
            parent[current] = prev

        # 終止：到達距 target ≤ reach_m 的節點
        cx, cy = nodes[current]
        if _euclidean(cx, cy, target.x, target.y) <= reach_m:
            found_idx = current
            break

        # 成本上限剪枝
        if g > max_cost:
            continue

        for neighbor, edge_cost in adj[current]:
            new_g = g + edge_cost
            if new_g > max_cost:
                continue
            if new_g < g_best.get(neighbor, float("inf")):
                g_best[neighbor] = new_g
                new_f = new_g + heuristic(neighbor)
                heapq.heappush(open_set, (new_f, new_g, neighbor, current))

    if found_idx is None:
        return None

    # 6. 回溯路徑
    path_indices: list[int] = []
    cur = found_idx
    while cur in parent:
        path_indices.append(cur)
        cur = parent[cur]
    path_indices.reverse()

    # 轉為 Position 列表（不含起點）
    return [Position(x=round(nodes[i][0], 2), y=round(nodes[i][1], 2)) for i in path_indices]


def find_furthest_along_path(
    start: Position,
    target: Position,
    reach_m: float,
    map_state: MapState,
    mover_radius: float,
    max_cost: float,
    blocked_actors: list[Actor],
    passable_actors: list[Actor],
) -> list[Position] | None:
    """盡量靠近 target，即使無法到達 reach_m 範圍內。

    先嘗試完整路徑（無限預算），若成功則截斷到 max_cost。
    用於 NPC AI 在移動預算不足時盡量接近目標。
    """
    # 先試完整路徑
    full_path = find_path_to_range(
        start=start,
        target=target,
        reach_m=reach_m,
        map_state=map_state,
        mover_radius=mover_radius,
        max_cost=999.0,  # 不限預算搜索
        blocked_actors=blocked_actors,
        passable_actors=passable_actors,
    )
    if full_path is None:
        return None  # 完全不可達
    if not full_path:
        return []  # 已在範圍內

    # 截斷到 max_cost，超出時在線段上插值
    truncated: list[Position] = []
    cost = 0.0
    prev = start
    for wp in full_path:
        seg_dist = _euclidean(prev.x, prev.y, wp.x, wp.y)
        if cost + seg_dist > max_cost + 0.01:  # 超出預算
            remaining = max_cost - cost
            if remaining > 0.01 and seg_dist > 0.01:
                ratio = remaining / seg_dist
                interp_x = prev.x + (wp.x - prev.x) * ratio
                interp_y = prev.y + (wp.y - prev.y) * ratio
                truncated.append(Position(x=round(interp_x, 2), y=round(interp_y, 2)))
            break
        cost += seg_dist
        truncated.append(wp)
        prev = wp

    return truncated if truncated else None


# ---------------------------------------------------------------------------
# 內部輔助
# ---------------------------------------------------------------------------


def _euclidean(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def _in_map_bounds(x: float, y: float, map_state: MapState, margin: float = 0.0) -> bool:
    """檢查座標是否在地圖範圍內。"""
    m = map_state.manifest
    gs = m.grid_size_m
    return margin <= x <= m.width * gs - margin and margin <= y <= m.height * gs - margin


def _point_in_any_inflated(x: float, y: float, inflated: list[AABB]) -> bool:
    """檢查點是否在任何膨脹障礙物內部。"""
    return any(ob.min_x < x < ob.max_x and ob.min_y < y < ob.max_y for ob in inflated)


_SEG_EPS = 0.01  # 1cm 容差：讓沿膨脹邊界走的線段不被誤判為穿過障礙物


def _segment_blocked(x1: float, y1: float, x2: float, y2: float, inflated: list[AABB]) -> bool:
    """檢查線段是否穿過任何膨脹障礙物。

    視線檢查時將膨脹障礙物再收縮 _SEG_EPS，使「擦邊而過」的線段不被誤判為阻擋。
    與 _point_in_any_inflated 的嚴格不等式保持一致：邊界上的節點合法，邊界上的邊也不阻擋。
    """
    for ob in inflated:
        shrunk = AABB(
            ob.min_x + _SEG_EPS,
            ob.min_y + _SEG_EPS,
            ob.max_x - _SEG_EPS,
            ob.max_y - _SEG_EPS,
        )
        if segment_aabb_intersect(x1, y1, x2, y2, shrunk):
            return True
    return False


def _passable_cost_multiplier(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    passable_aabbs: list[AABB],
) -> float:
    """計算穿越友方區域的成本倍率。

    如果線段穿過任何友方佔據區域 → ×2（困難地形）。
    """
    for aabb in passable_aabbs:
        if segment_aabb_intersect(x1, y1, x2, y2, aabb):
            return 2.0
    return 1.0
