"""Bone Engine 空間邏輯。

距離計算、Bresenham 視線、移動驗證、掩蔽偵測、區域查詢。
純確定性，無 LLM、無隨機性。座標系為左下原點（X 向右、Y 向上）。

座標單位為公尺（float），地形/牆壁/道具仍用整數網格。
內部透過 floor(pos / grid_size) 將公尺座標映射到網格 cell。
"""

from __future__ import annotations

import math
import re
from uuid import UUID

from tot.models import (
    SIZE_ORDER,
    SIZE_RADIUS_M,
    Actor,
    Character,
    CoverType,
    Entity,
    MapState,
    Monster,
    MoveEvent,
    MoveResult,
    Position,
    Size,
    Spell,
    Zone,
    ZoneConnection,
)


def _to_grid(x_m: float, y_m: float, grid_size: float) -> tuple[int, int]:
    """公尺座標 → 網格 cell（內部 helper）。"""
    return int(math.floor(x_m / grid_size)), int(math.floor(y_m / grid_size))


# ---------------------------------------------------------------------------
# 距離計算
# ---------------------------------------------------------------------------


def distance(a: Position, b: Position) -> float:
    """Euclidean 距離（公尺）。"""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def grid_distance(a: Position, b: Position, grid_size: float = 1.5) -> float:
    """Chebyshev 距離 × 格子大小（公尺）。

    D&D 5e 格子戰鬥的標準距離計量：對角線 = 1 格。
    用於近戰觸及範圍、藉機攻擊等格子距離判定。
    遠程攻擊/法術射程可用 distance()（Euclidean）。
    """
    gs = grid_size
    agx, agy = _to_grid(a.x, a.y, gs)
    bgx, bgy = _to_grid(b.x, b.y, gs)
    return max(abs(agx - bgx), abs(agy - bgy)) * gs


def actors_in_radius(
    center: Position,
    radius_m: float,
    map_state: MapState,
    *,
    alive_only: bool = True,
) -> list[Actor]:
    """回傳 center 半徑 radius_m 公尺內的 Actor。

    使用 Euclidean 距離判定（中心到中心）。
    """
    result: list[Actor] = []
    for a in map_state.actors:
        if alive_only and not a.is_alive:
            continue
        d = math.sqrt((a.x - center.x) ** 2 + (a.y - center.y) ** 2)
        if d <= radius_m:
            result.append(a)
    return result


def positions_in_radius(
    center: Position,
    radius_m: float,
    grid_size: float = 1.5,
) -> list[Position]:
    """半徑內所有格子座標（舊版 AoE 用，保留相容）。

    .. deprecated:: 使用 actors_in_radius() 取代。
    """
    radius_grids = int(radius_m / grid_size)
    gs = grid_size
    cgx, cgy = _to_grid(center.x, center.y, gs)
    result: list[Position] = []
    for dx in range(-radius_grids, radius_grids + 1):
        for dy in range(-radius_grids, radius_grids + 1):
            if max(abs(dx), abs(dy)) <= radius_grids:
                result.append(Position.from_grid(cgx + dx, cgy + dy, gs))
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
    """檢查指定網格 cell 是否有阻擋物（地形、活著的 Actor、阻擋型 Prop）。

    x, y 為網格座標（int）。
    """
    m = map_state.manifest
    gs = m.grid_size_m
    # 邊界外視為阻擋
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return True
    # 地形阻擋
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return True
    # manifest 中的靜態 Prop（Prop 座標仍為整數網格）
    for p in m.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return True
    # 執行期動態 Prop
    for p in map_state.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return True
    # 活著的 Actor 視為阻擋（死亡降級後不阻擋）
    for a in map_state.actors:
        agx, agy = _to_grid(a.x, a.y, gs)
        if agx == x and agy == y and a.is_alive and a.is_blocking:
            return True
    return False


def has_line_of_sight(
    origin: Position,
    target: Position,
    map_state: MapState,
) -> bool:
    """視線判定：Bresenham 路徑上（不含起終點）若有 is_blocking 則遮擋。

    接受公尺座標 Position，內部轉為網格座標做 Bresenham。
    """
    gs = map_state.manifest.grid_size_m
    ox, oy = _to_grid(origin.x, origin.y, gs)
    tx, ty = _to_grid(target.x, target.y, gs)
    path = bresenham_line(ox, oy, tx, ty)
    # 跳過起點和終點
    return all(not _is_blocking_at(x, y, map_state) for x, y in path[1:-1])


# ---------------------------------------------------------------------------
# 位置驗證
# ---------------------------------------------------------------------------


def is_valid_position(x: int, y: int, map_state: MapState) -> bool:
    """檢查網格座標是否在地圖內且非阻擋（可通行）。

    x, y 為網格座標（int）。
    """
    m = map_state.manifest
    gs = m.grid_size_m
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return False
    # 地形阻擋
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return False
    # 靜態 Prop 阻擋
    for p in m.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return False
    # 動態 Prop 阻擋
    for p in map_state.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return False
    # 活著的 Actor 佔據
    for a in map_state.actors:
        agx, agy = _to_grid(a.x, a.y, gs)
        if agx == x and agy == y and a.is_alive and a.is_blocking:
            return False
    return True


# ---------------------------------------------------------------------------
# 實體查詢
# ---------------------------------------------------------------------------


def get_entities_at(x: int, y: int, map_state: MapState) -> list[Entity]:
    """取得指定網格 cell 上的所有實體（Actor + Prop）。

    x, y 為網格座標（int）。
    """
    gs = map_state.manifest.grid_size_m
    result: list[Entity] = []
    for a in map_state.actors:
        agx, agy = _to_grid(a.x, a.y, gs)
        if agx == x and agy == y:
            result.append(a)
    for p in map_state.manifest.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y:
            result.append(p)
    for p in map_state.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y:
            result.append(p)
    return result


def get_actor_position(combatant_id: UUID, map_state: MapState) -> Position | None:
    """以 UUID 查詢戰鬥者位置（公尺座標）。找不到回傳 None。"""
    for a in map_state.actors:
        if a.combatant_id == combatant_id:
            return Position(x=a.x, y=a.y)
    return None


def has_hostile_within_melee(
    actor: Actor,
    map_state: MapState,
    allies: set[UUID],
    melee_range_m: float = 1.5,
) -> bool:
    """近戰範圍內是否有非無力化的敵方 Actor。

    使用 Euclidean 距離判定，melee_range_m 預設 1.5m（Medium 觸及範圍）。
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
        dist = math.sqrt((other.x - actor.x) ** 2 + (other.y - actor.y) ** 2)
        if dist <= melee_range_m:
            return True
    return False


# ---------------------------------------------------------------------------
# 碰撞系統（D&D 5e PHB）
# ---------------------------------------------------------------------------


def _size_diff(a: Size, b: Size) -> int:
    """兩個體型的級數差（絕對值）。"""
    return abs(SIZE_ORDER[a] - SIZE_ORDER[b])


def check_collision(
    pos: Position,
    size: Size,
    map_state: MapState,
    exclude_id: str | None = None,
) -> Actor | None:
    """檢查在 pos 放置 size 體型的生物是否與現有 Actor 碰撞。

    碰撞判定：中心距離 < (radius_a + radius_b) → 佔據同一空間。
    回傳第一個碰撞的 Actor，無碰撞回傳 None。
    """
    my_r = SIZE_RADIUS_M[size]
    for a in map_state.actors:
        if not a.is_alive:
            continue
        if exclude_id and a.id == exclude_id:
            continue
        other_r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)  # Actor 無 size，預設 Medium
        center_dist = math.sqrt((a.x - pos.x) ** 2 + (a.y - pos.y) ** 2)
        if center_dist < my_r + other_r:
            return a
    return None


def can_traverse(
    mover_size: Size,
    occupant_size: Size,
    is_hostile: bool,
) -> bool:
    """判斷移動者能否穿越佔據者的空間（D&D 5e PHB）。

    - 非敵對：可穿越（但該空間視為困難地形）
    - 敵對：不可穿越，除非體型差 ≥ 2 級
    """
    if not is_hostile:
        return True
    return _size_diff(mover_size, occupant_size) >= 2


def can_end_move_at(
    pos: Position,
    size: Size,
    map_state: MapState,
    mover_id: str | None = None,
) -> bool:
    """判斷是否可在 pos 停留（D&D 5e PHB）。

    任何生物（敵友皆然）都不可自願在其空間內結束移動。
    """
    my_r = SIZE_RADIUS_M[size]
    for a in map_state.actors:
        if not a.is_alive:
            continue
        if mover_id and a.id == mover_id:
            continue
        other_r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        center_dist = math.sqrt((a.x - pos.x) ** 2 + (a.y - pos.y) ** 2)
        if center_dist < my_r + other_r:
            return False
    return True


def find_nearest_valid_position(
    pos: Position,
    size: Size,
    map_state: MapState,
    exclude_id: str | None = None,
) -> Position:
    """找到離 pos 最近的有效位置（無碰撞、地形可通行）。

    以 BFS 在網格上搜尋，回傳格子中心公尺座標。
    """
    gs = map_state.manifest.grid_size_m
    gx, gy = _to_grid(pos.x, pos.y, gs)

    # 先檢查原位置
    if is_valid_position(gx, gy, map_state) and can_end_move_at(pos, size, map_state, exclude_id):
        return pos

    # BFS 螺旋展開搜尋
    from collections import deque

    visited: set[tuple[int, int]] = {(gx, gy)}
    queue: deque[tuple[int, int]] = deque([(gx, gy)])
    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    while queue:
        cx, cy = queue.popleft()
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            candidate = Position.from_grid(nx, ny, gs)
            if is_valid_position(nx, ny, map_state) and can_end_move_at(
                candidate, size, map_state, exclude_id
            ):
                return candidate
            queue.append((nx, ny))

    # 退回原位置（不應發生）
    return pos


# ---------------------------------------------------------------------------
# 移動
# ---------------------------------------------------------------------------


def move_entity(
    actor: Actor,
    dx: int,
    dy: int,
    map_state: MapState,
    speed_remaining: float,
    *,
    allies: set[str] | None = None,
    mover_size: Size = Size.MEDIUM,
) -> MoveResult:
    """嘗試移動 Actor 一格（網格位移），完整 D&D 5e 移動規則。

    dx/dy 為網格方向（-1/0/1），內部將公尺座標映射到目標網格中心。
    回傳 MoveResult（成功、剩餘速度、事件列表）。
    移動成功時直接修改 actor.x/y。

    規則：
    - 地形阻擋 → 不可移動
    - 敵對 Actor 佔據 → 不可穿越（除非體型差 ≥ 2）
    - 非敵對 Actor 佔據 → 可穿越（困難地形 ×2 消耗）
    - 不可在任何生物空間內結束移動（敵友皆然）
    - 離開敵對觸及範圍 → 回傳 OA 事件
    """
    gs = map_state.manifest.grid_size_m
    allies = allies or set()
    events: list[MoveEvent] = []

    cur_gx, cur_gy = _to_grid(actor.x, actor.y, gs)
    new_gx = cur_gx + dx
    new_gy = cur_gy + dy

    # 邊界 + 地形 + Prop 阻擋（暫時排除自己）
    old_blocking = actor.is_blocking
    actor.is_blocking = False

    # 檢查地形/Prop 可通行（不含 Actor 阻擋）
    m = map_state.manifest
    if new_gx < 0 or new_gx >= m.width or new_gy < 0 or new_gy >= m.height:
        actor.is_blocking = old_blocking
        return MoveResult(success=False, speed_remaining=speed_remaining)

    if map_state.terrain and map_state.terrain[new_gy][new_gx].is_blocking:
        actor.is_blocking = old_blocking
        return MoveResult(success=False, speed_remaining=speed_remaining)

    for p in [*m.props, *map_state.props]:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == new_gx and pgy == new_gy and p.is_blocking:
            actor.is_blocking = old_blocking
            return MoveResult(success=False, speed_remaining=speed_remaining)

    # 檢查目標格上的 Actor —— 穿越規則
    cost = gs
    difficult_from_creature = False
    for other in map_state.actors:
        if other.id == actor.id or not other.is_alive or not other.is_blocking:
            continue
        ogx, ogy = _to_grid(other.x, other.y, gs)
        if ogx != new_gx or ogy != new_gy:
            continue

        is_hostile = other.id not in allies
        if not can_traverse(mover_size, Size.MEDIUM, is_hostile):
            actor.is_blocking = old_blocking
            return MoveResult(success=False, speed_remaining=speed_remaining)
        if not is_hostile:
            difficult_from_creature = True

    actor.is_blocking = old_blocking

    # 困難地形消耗
    if (
        map_state.terrain
        and 0 <= new_gy < len(map_state.terrain)
        and 0 <= new_gx < len(map_state.terrain[new_gy])
        and map_state.terrain[new_gy][new_gx].is_difficult
    ):
        cost *= 2
    elif difficult_from_creature:
        cost *= 2
        events.append(
            MoveEvent(
                event_type="difficult_terrain",
                message="穿越友軍空間，視為困難地形",
            )
        )

    if speed_remaining < cost:
        return MoveResult(success=False, speed_remaining=speed_remaining)

    # 記錄舊位置（OA 判定用）
    old_x, old_y = actor.x, actor.y

    # 執行移動
    actor.x = new_gx * gs + gs / 2
    actor.y = new_gy * gs + gs / 2

    # OA 偵測：離開敵對生物觸及範圍
    melee_range = 1.5  # Medium 觸及範圍
    for other in map_state.actors:
        if other.id == actor.id or not other.is_alive:
            continue
        if other.id in allies:
            continue
        old_dist = math.sqrt((other.x - old_x) ** 2 + (other.y - old_y) ** 2)
        new_dist = math.sqrt((other.x - actor.x) ** 2 + (other.y - actor.y) ** 2)
        if old_dist <= melee_range and new_dist > melee_range:
            events.append(
                MoveEvent(
                    event_type="opportunity_attack",
                    trigger_actor_id=other.id,
                    message=f"{other.name} 的藉機攻擊！",
                )
            )

    return MoveResult(
        success=True,
        speed_remaining=speed_remaining - cost,
        events=events,
    )


# ---------------------------------------------------------------------------
# 掩蔽偵測
# ---------------------------------------------------------------------------


def determine_cover_from_grid(
    attacker: Position,
    target: Position,
    map_state: MapState,
) -> CoverType:
    """根據 Bresenham 路徑上的阻擋物判定掩蔽。

    接受公尺座標 Position，內部轉為網格座標做 Bresenham。
    不含起終點。1 個阻擋 = 半掩蔽(+2 AC)，2+ 個 = 3/4 掩蔽(+5 AC)。
    完全掩蔽（Total）需由上層判定（如完全在牆後、無視線）。
    """
    gs = map_state.manifest.grid_size_m
    ax, ay = _to_grid(attacker.x, attacker.y, gs)
    tx, ty = _to_grid(target.x, target.y, gs)
    path = bresenham_line(ax, ay, tx, ty)
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


def zone_for_position(
    x: float | int, y: float | int, zones: list[Zone], grid_size: float = 1.5
) -> Zone | None:
    """座標 → 所屬區域。接受公尺或網格座標，自動偵測。

    Zone 邊界定義為網格座標，若傳入 float 會先轉為網格座標。
    多區域重疊時回傳第一個符合的。
    """
    # 若為 float 且不是整數值，視為公尺座標
    if isinstance(x, float) and not x.is_integer():
        gx, gy = _to_grid(x, y, grid_size)
    else:
        gx, gy = int(x), int(y)
    for z in zones:
        if z.x_min <= gx <= z.x_max and z.y_min <= gy <= z.y_max:
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


def validate_spell_range(spell: Spell, dist_m: float, grid_size: float = 1.5) -> str | None:
    """驗證法術射程（距離為公尺）。回傳錯誤訊息或 None。"""
    range_str = spell.range.strip().lower()
    if range_str == "self" or range_str.startswith("self"):
        return None
    if range_str == "touch":
        # 觸碰法術：需要在近戰觸及範圍（1.5m for Medium）
        if dist_m > grid_size:
            return f"觸碰法術需要在觸及範圍（當前 {dist_m:.1f}m）"
        return None
    range_m = parse_spell_range_meters(spell.range, grid_size)
    if range_m is not None and dist_m > range_m:
        return f"超出法術射程（{spell.range}≈{range_m:.0f}m，當前 {dist_m:.1f}m）"
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
    """BFS 用可通行判定（網格座標）。友方 actor 視為可穿越（D&D 5e 規則）。"""
    m = map_state.manifest
    gs = m.grid_size_m
    if x < 0 or x >= m.width or y < 0 or y >= m.height:
        return False
    if map_state.terrain and map_state.terrain[y][x].is_blocking:
        return False
    for p in m.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return False
    for p in map_state.props:
        pgx, pgy = _to_grid(p.x, p.y, gs)
        if pgx == x and pgy == y and p.is_blocking:
            return False
    for a in map_state.actors:
        agx, agy = _to_grid(a.x, a.y, gs)
        if agx == x and agy == y and a.is_alive and a.is_blocking:
            if a.combatant_id == mover_id:
                continue
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
    """BFS 尋路（網格上），找到 Chebyshev 距離 target ≤ reach_grids 的可通行格。

    接受公尺座標 Position，內部轉為網格座標做 BFS，
    回傳路徑為公尺座標（格子中心）。
    友方 actor 視為可穿越但不可停留（D&D 5e 規則）。
    回傳路徑 list[Position]（不含起點），或 None。
    """
    from collections import deque

    gs = map_state.manifest.grid_size_m
    sgx, sgy = _to_grid(start.x, start.y, gs)
    tgx, tgy = _to_grid(target.x, target.y, gs)

    # 起點已在範圍內
    if max(abs(sgx - tgx), abs(sgy - tgy)) <= reach_grids:
        return []

    # 不可停留的格子：友方佔據的格（穿越可以，停留不行）
    friendly_occupied: set[tuple[int, int]] = set()
    for a in map_state.actors:
        if (
            a.is_alive
            and a.is_blocking
            and a.combatant_id in friendly_ids
            and a.combatant_id != mover_id
        ):
            friendly_occupied.add(_to_grid(a.x, a.y, gs))

    queue: deque[tuple[int, int, int]] = deque()  # (gx, gy, depth)
    visited: dict[tuple[int, int], tuple[int, int] | None] = {(sgx, sgy): None}
    queue.append((sgx, sgy, 0))

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
            if can_stop and max(abs(nx - tgx), abs(ny - tgy)) <= reach_grids:
                # 回溯路徑（轉為公尺座標）
                path: list[Position] = []
                cur: tuple[int, int] | None = (nx, ny)
                while cur is not None and cur != (sgx, sgy):
                    path.append(Position.from_grid(cur[0], cur[1], gs))
                    cur = visited.get(cur)
                path.reverse()
                return path

            queue.append((nx, ny, depth + 1))

    return None


def _spawn_to_meters(sp: Position, grid_size: float) -> tuple[float, float]:
    """將 spawn point（網格座標）轉為公尺座標（格子中心）。

    spawn_points 在 JSON 中是整數網格座標，轉換為公尺座標。
    """
    return sp.x * grid_size + grid_size / 2, sp.y * grid_size + grid_size / 2


def place_actors_at_spawn(
    characters: list[Character],
    monsters: list[Monster],
    map_state: MapState,
) -> None:
    """依 spawn_points 將戰鬥者放上地圖，建立 Actor 加入 map_state.actors。

    spawn_points 的 key 對應：'players' → characters、'enemies' → monsters。
    spawn_points 為網格座標，自動轉換為公尺座標（格子中心）。
    若 spawn_points 不足，多出的戰鬥者不會被放置。
    """
    spawns = map_state.manifest.spawn_points
    gs = map_state.manifest.grid_size_m

    player_spawns = spawns.get("players", [])
    for i, char in enumerate(characters):
        if i >= len(player_spawns):
            break
        mx, my = _spawn_to_meters(player_spawns[i], gs)
        pos = Position(x=mx, y=my)
        # 碰撞修正：若 spawn 點已被佔據，找最近有效位置
        if check_collision(pos, Size.MEDIUM, map_state):
            pos = find_nearest_valid_position(pos, Size.MEDIUM, map_state)
        actor = Actor(
            id=f"pc_{i}",
            x=pos.x,
            y=pos.y,
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
        mx, my = _spawn_to_meters(enemy_spawns[i], gs)
        pos = Position(x=mx, y=my)
        if check_collision(pos, Size.MEDIUM, map_state):
            pos = find_nearest_valid_position(pos, Size.MEDIUM, map_state)
        actor = Actor(
            id=f"mob_{i}",
            x=pos.x,
            y=pos.y,
            symbol="👹",
            combatant_id=mon.id,
            combatant_type="monster",
            name=mon.label or mon.name,
            is_blocking=True,
            is_alive=mon.is_alive,
        )
        map_state.actors.append(actor)
