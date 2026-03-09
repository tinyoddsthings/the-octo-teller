"""Bone Engine 空間邏輯。

格子距離、Bresenham 視線、移動驗證、掩蔽偵測、區域查詢。
純確定性，無 LLM、無隨機性。座標系為左下原點（X 向右、Y 向上）。
"""

from __future__ import annotations

from uuid import UUID

from tot.models import (
    Actor,
    Entity,
    MapState,
    Position,
)


# ---------------------------------------------------------------------------
# 距離計算
# ---------------------------------------------------------------------------

def grid_distance(a: Position, b: Position, grid_size: float = 1.5) -> float:
    """Chebyshev 距離 × 格子大小（公尺）。

    D&D 2024 對角線移動 = 1 格（非 1.5 格交替規則）。
    """
    dx = abs(a.x - b.x)
    dy = abs(a.y - b.y)
    return max(dx, dy) * grid_size


def positions_in_radius(
    center: Position,
    radius_m: float,
    grid_size: float = 1.5,
) -> list[Position]:
    """半徑內所有格子座標（AoE 用）。

    以 Chebyshev 距離判定，結果包含中心點。
    """
    radius_grids = int(radius_m / grid_size)
    result: list[Position] = []
    for dx in range(-radius_grids, radius_grids + 1):
        for dy in range(-radius_grids, radius_grids + 1):
            if max(abs(dx), abs(dy)) <= radius_grids:
                result.append(Position(x=center.x + dx, y=center.y + dy))
    return result


# ---------------------------------------------------------------------------
# Bresenham 視線
# ---------------------------------------------------------------------------

def bresenham_line(
    x0: int, y0: int, x1: int, y1: int,
) -> list[tuple[int, int]]:
    """Bresenham 直線演算法，回傳路徑上的所有座標（含起終點）。"""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy

    return points


def _is_blocking_at(x: int, y: int, map_state: MapState) -> bool:
    """檢查指定格子是否有阻擋物（地形、活著的 Actor、阻擋型 Prop）。"""
    m = map_state.manifest
    # 邊界外視為阻擋
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return True
    # 地形阻擋
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return True
    # manifest 中的靜態 Prop
    for p in m.props:
        if p.x == x and p.y == y and p.is_blocking:
            return True
    # 執行期動態 Prop
    for p in map_state.props:
        if p.x == x and p.y == y and p.is_blocking:
            return True
    # 活著的 Actor 視為阻擋（死亡降級後不阻擋）
    for a in map_state.actors:
        if a.x == x and a.y == y and a.is_alive and a.is_blocking:
            return True
    return False


def has_line_of_sight(
    origin: Position,
    target: Position,
    map_state: MapState,
) -> bool:
    """視線判定：Bresenham 路徑上（不含起終點）若有 is_blocking 則遮擋。"""
    path = bresenham_line(origin.x, origin.y, target.x, target.y)
    # 跳過起點和終點
    for x, y in path[1:-1]:
        if _is_blocking_at(x, y, map_state):
            return False
    return True


# ---------------------------------------------------------------------------
# 位置驗證
# ---------------------------------------------------------------------------

def is_valid_position(x: int, y: int, map_state: MapState) -> bool:
    """檢查座標是否在地圖內且非阻擋（可通行）。"""
    m = map_state.manifest
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return False
    # 地形阻擋
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return False
    # 靜態 Prop 阻擋
    for p in m.props:
        if p.x == x and p.y == y and p.is_blocking:
            return False
    # 動態 Prop 阻擋
    for p in map_state.props:
        if p.x == x and p.y == y and p.is_blocking:
            return False
    # 活著的 Actor 佔據
    for a in map_state.actors:
        if a.x == x and a.y == y and a.is_alive and a.is_blocking:
            return False
    return True


# ---------------------------------------------------------------------------
# 實體查詢
# ---------------------------------------------------------------------------

def get_entities_at(x: int, y: int, map_state: MapState) -> list[Entity]:
    """取得指定格子上的所有實體（Actor + Prop，含 manifest 靜態與動態）。"""
    result: list[Entity] = []
    for a in map_state.actors:
        if a.x == x and a.y == y:
            result.append(a)
    for p in map_state.manifest.props:
        if p.x == x and p.y == y:
            result.append(p)
    for p in map_state.props:
        if p.x == x and p.y == y:
            result.append(p)
    return result


def get_actor_position(combatant_id: UUID, map_state: MapState) -> Position | None:
    """以 UUID 查詢戰鬥者位置。找不到回傳 None。"""
    for a in map_state.actors:
        if a.combatant_id == combatant_id:
            return Position(x=a.x, y=a.y)
    return None


def has_hostile_within_melee(
    actor: Actor,
    map_state: MapState,
    allies: set[UUID],
) -> bool:
    """1.5m（1 格）內是否有非無力化的敵方 Actor。

    用於遠程攻擊劣勢判定：近戰範圍內有敵人時遠程攻擊劣勢。
    allies 包含所有友方的 combatant_id（含自己）。
    """
    for other in map_state.actors:
        if other.combatant_id == actor.combatant_id:
            continue
        if not other.is_alive:
            continue
        if other.combatant_id in allies:
            continue
        # Chebyshev 1 格 = 鄰接（含對角線）
        if max(abs(other.x - actor.x), abs(other.y - actor.y)) <= 1:
            return True
    return False


# ---------------------------------------------------------------------------
# 移動
# ---------------------------------------------------------------------------

def move_entity(
    actor: Actor,
    dx: int,
    dy: int,
    map_state: MapState,
    speed_remaining: float,
) -> tuple[bool, float]:
    """嘗試移動 Actor，檢查邊界、阻擋與速度。

    困難地形消耗加倍。回傳 (成功, 剩餘速度)。
    移動成功時直接修改 actor.x/y。
    """
    new_x = actor.x + dx
    new_y = actor.y + dy
    grid_size = map_state.manifest.grid_size_m

    # 目標格必須可通行（排除自己的阻擋：先暫時標記）
    old_blocking = actor.is_blocking
    actor.is_blocking = False
    valid = is_valid_position(new_x, new_y, map_state)
    actor.is_blocking = old_blocking

    if not valid:
        return False, speed_remaining

    # 移動消耗：Chebyshev 1 格（含對角線）
    cost = grid_size
    # 困難地形加倍
    if (map_state.terrain
            and 0 <= new_y < len(map_state.terrain)
            and 0 <= new_x < len(map_state.terrain[new_y])
            and map_state.terrain[new_y][new_x].is_difficult):
        cost *= 2

    if speed_remaining < cost:
        return False, speed_remaining

    actor.x = new_x
    actor.y = new_y
    return True, speed_remaining - cost
