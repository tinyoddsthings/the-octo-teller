"""Bone Engine 空間邏輯。

格子距離、Bresenham 視線、移動驗證、掩蔽偵測、區域查詢。
純確定性，無 LLM、無隨機性。座標系為左下原點（X 向右、Y 向上）。
"""

from __future__ import annotations

import re
from uuid import UUID

from tot.models import (
    Actor,
    Character,
    CoverType,
    Entity,
    MapState,
    Monster,
    Position,
    Spell,
    Zone,
    ZoneConnection,
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
    x0: int,
    y0: int,
    x1: int,
    y1: int,
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
    return any(a.x == x and a.y == y and a.is_alive and a.is_blocking for a in map_state.actors)


def has_line_of_sight(
    origin: Position,
    target: Position,
    map_state: MapState,
) -> bool:
    """視線判定：Bresenham 路徑上（不含起終點）若有 is_blocking 則遮擋。"""
    path = bresenham_line(origin.x, origin.y, target.x, target.y)
    # 跳過起點和終點
    return all(not _is_blocking_at(x, y, map_state) for x, y in path[1:-1])


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
    if (
        map_state.terrain
        and 0 <= new_y < len(map_state.terrain)
        and 0 <= new_x < len(map_state.terrain[new_y])
        and map_state.terrain[new_y][new_x].is_difficult
    ):
        cost *= 2

    if speed_remaining < cost:
        return False, speed_remaining

    actor.x = new_x
    actor.y = new_y
    return True, speed_remaining - cost


# ---------------------------------------------------------------------------
# 掩蔽偵測
# ---------------------------------------------------------------------------


def determine_cover_from_grid(
    attacker: Position,
    target: Position,
    map_state: MapState,
) -> CoverType:
    """根據 Bresenham 路徑上的阻擋物判定掩蔽。

    不含起終點。1 個阻擋 = 半掩蔽(+2 AC)，2+ 個 = 3/4 掩蔽(+5 AC)。
    完全掩蔽（Total）需由上層判定（如完全在牆後、無視線）。
    """
    path = bresenham_line(attacker.x, attacker.y, target.x, target.y)
    blocking_count = 0
    for x, y in path[1:-1]:
        if _is_blocking_at(x, y, map_state):
            blocking_count += 1
    if blocking_count >= 2:
        return CoverType.THREE_QUARTERS
    if blocking_count == 1:
        return CoverType.HALF
    return CoverType.NONE


# ---------------------------------------------------------------------------
# 區域查詢
# ---------------------------------------------------------------------------


def zone_for_position(x: int, y: int, zones: list[Zone]) -> Zone | None:
    """座標 → 所屬區域。多區域重疊時回傳第一個符合的。"""
    for z in zones:
        if z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max:
            return z
    return None


def build_zone_adjacency(
    connections: list[ZoneConnection],
) -> dict[str, list[str]]:
    """從 ZoneConnection 建立雙向鄰接圖。"""
    adj: dict[str, list[str]] = {}
    for conn in connections:
        adj.setdefault(conn.from_zone, []).append(conn.to_zone)
        adj.setdefault(conn.to_zone, []).append(conn.from_zone)
    return adj


# ---------------------------------------------------------------------------
# 生成位置
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 法術射程驗證
# ---------------------------------------------------------------------------


def parse_spell_range_meters(range_str: str, grid_size: float = 1.5) -> float | None:
    """解析法術射程字串 → 公尺。"Self"/"Touch" → None。"""
    s = range_str.strip().lower()
    if s in ("self", "touch") or s.startswith("self"):
        return None
    # "120ft" → 120 / 5 * 1.5 = 36.0m
    m = re.match(r"(\d+)\s*ft", s)
    if m:
        return int(m.group(1)) / 5.0 * grid_size
    return None


def validate_spell_range(
    spell: Spell, distance: float, grid_size: float = 1.5
) -> str | None:
    """驗證法術射程。回傳錯誤訊息或 None。"""
    range_str = spell.range.strip().lower()
    if range_str == "self" or range_str.startswith("self"):
        return None
    if range_str == "touch":
        if distance / grid_size > 1:
            return f"觸碰法術需要在鄰接格（當前 {distance:.1f}m）"
        return None
    range_m = parse_spell_range_meters(spell.range, grid_size)
    if range_m is not None and distance > range_m:
        return f"超出法術射程（{spell.range}≈{range_m:.0f}m，當前 {distance:.1f}m）"
    return None


# ---------------------------------------------------------------------------
# 生成位置
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# BFS 尋路
# ---------------------------------------------------------------------------


def _is_passable_for_bfs(
    x: int,
    y: int,
    map_state: MapState,
    mover_id: UUID,
    friendly_ids: set[UUID],
) -> bool:
    """BFS 用可通行判定。友方 actor 視為可穿越（D&D 5e 規則）。"""
    m = map_state.manifest
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return False
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return False
    for p in m.props:
        if p.x == x and p.y == y and p.is_blocking:
            return False
    for p in map_state.props:
        if p.x == x and p.y == y and p.is_blocking:
            return False
    for a in map_state.actors:
        if a.x == x and a.y == y and a.is_alive and a.is_blocking:
            # 自身不阻擋
            if a.combatant_id == mover_id:
                continue
            # 友方可穿越
            if a.combatant_id in friendly_ids:
                continue
            return False
    return True


def bfs_path_to_range(
    start: Position,
    target: Position,
    reach_grids: int,
    map_state: MapState,
    max_steps: int,
    mover_id: UUID,
    friendly_ids: set[UUID],
) -> list[Position] | None:
    """BFS 尋路，找到 Chebyshev 距離 target ≤ reach_grids 的可通行格。

    友方 actor 視為可穿越但不可停留（D&D 5e 規則）。
    回傳路徑 list[Position]（不含起點），或 None。
    """
    from collections import deque

    # 起點已在範圍內
    if max(abs(start.x - target.x), abs(start.y - target.y)) <= reach_grids:
        return []

    # 不可停留的格子：友方佔據的格（穿越可以，停留不行）
    friendly_occupied: set[tuple[int, int]] = set()
    for a in map_state.actors:
        if a.is_alive and a.is_blocking and a.combatant_id in friendly_ids and a.combatant_id != mover_id:
            friendly_occupied.add((a.x, a.y))

    queue: deque[tuple[int, int, int]] = deque()  # (x, y, depth)
    visited: dict[tuple[int, int], tuple[int, int] | None] = {(start.x, start.y): None}
    queue.append((start.x, start.y, 0))

    dirs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    while queue:
        cx, cy, depth = queue.popleft()
        if depth >= max_steps:
            continue

        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in visited:
                continue
            if not _is_passable_for_bfs(nx, ny, map_state, mover_id, friendly_ids):
                continue

            visited[(nx, ny)] = (cx, cy)

            # 可以停留？（不能停在友方佔據格）
            can_stop = (nx, ny) not in friendly_occupied
            if can_stop and max(abs(nx - target.x), abs(ny - target.y)) <= reach_grids:
                # 回溯路徑
                path: list[Position] = []
                cur: tuple[int, int] | None = (nx, ny)
                while cur is not None and cur != (start.x, start.y):
                    path.append(Position(x=cur[0], y=cur[1]))
                    cur = visited.get(cur)
                path.reverse()
                return path

            queue.append((nx, ny, depth + 1))

    return None


def place_actors_at_spawn(
    characters: list[Character],
    monsters: list[Monster],
    map_state: MapState,
) -> None:
    """依 spawn_points 將戰鬥者放上地圖，建立 Actor 加入 map_state.actors。

    spawn_points 的 key 對應：'players' → characters、'enemies' → monsters。
    若 spawn_points 不足，多出的戰鬥者不會被放置。
    """
    spawns = map_state.manifest.spawn_points

    player_spawns = spawns.get("players", [])
    for i, char in enumerate(characters):
        if i >= len(player_spawns):
            break
        sp = player_spawns[i]
        actor = Actor(
            id=f"pc_{i}",
            x=sp.x,
            y=sp.y,
            symbol="🧙",
            combatant_id=char.id,
            combatant_type="character",
            name=char.name,
            is_blocking=True,
            is_alive=char.is_alive,
        )
        map_state.actors.append(actor)

    enemy_spawns = spawns.get("enemies", [])
    for i, mon in enumerate(monsters):
        if i >= len(enemy_spawns):
            break
        sp = enemy_spawns[i]
        symbol = "👹"
        actor = Actor(
            id=f"mob_{i}",
            x=sp.x,
            y=sp.y,
            symbol=symbol,
            combatant_id=mon.id,
            combatant_type="monster",
            name=mon.label or mon.name,
            is_blocking=True,
            is_alive=mon.is_alive,
        )
        map_state.actors.append(actor)
