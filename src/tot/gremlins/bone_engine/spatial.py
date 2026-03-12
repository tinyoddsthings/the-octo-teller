"""Bone Engine 空間邏輯。

距離計算、視線判定（Ray-AABB）、移動驗證、掩蔽偵測、區域查詢。
純確定性，無 LLM、無隨機性。座標系為左下原點（X 向右、Y 向上）。

座標單位為公尺（float），障礙物以 Wall AABB 表示。
"""

from __future__ import annotations

import math
import re
from uuid import UUID

from tot.gremlins.bone_engine.geometry import (
    AABB,
    circle_aabb_overlap,
    extract_static_obstacles,
    segment_aabb_intersect,
)
from tot.models import (
    SIZE_ORDER,
    SIZE_RADIUS_M,
    Actor,
    Character,
    CoverType,
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

# ---------------------------------------------------------------------------
# 距離計算
# ---------------------------------------------------------------------------


def distance(a: Position, b: Position) -> float:
    """Euclidean 距離（公尺）。"""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


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


# ---------------------------------------------------------------------------
# 視線判定（Ray-AABB）
# ---------------------------------------------------------------------------


def _near(ax: float, ay: float, bx: float, by: float, tol: float = 0.01) -> bool:
    """兩點是否接近（容差 tol 公尺）。"""
    return abs(ax - bx) < tol and abs(ay - by) < tol


def has_line_of_sight(
    origin: Position,
    target: Position,
    map_state: MapState,
) -> bool:
    """視線判定：線段 origin→target 是否被靜態障礙物或活的 Actor 遮擋。

    使用 Ray-AABB（Liang-Barsky）對所有靜態障礙 AABB 和
    活著的 blocking Actor 做線段交叉檢查。
    起終點所在的 Actor 不參與遮擋判定。
    """
    obstacles = extract_static_obstacles(map_state)

    # 靜態障礙物
    for ob in obstacles:
        if segment_aabb_intersect(origin.x, origin.y, target.x, target.y, ob):
            return False

    # 活著的 blocking Actor（排除在起點或終點位置的 Actor）
    for a in map_state.actors:
        if not a.is_alive or not a.is_blocking:
            continue
        if _near(a.x, a.y, origin.x, origin.y) or _near(a.x, a.y, target.x, target.y):
            continue
        r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        actor_aabb = AABB(a.x - r, a.y - r, a.x + r, a.y + r)
        if segment_aabb_intersect(origin.x, origin.y, target.x, target.y, actor_aabb):
            return False

    return True


# ---------------------------------------------------------------------------
# 位置驗證
# ---------------------------------------------------------------------------


def is_valid_position(x: float, y: float, map_state: MapState) -> bool:
    """檢查公尺座標是否在地圖內且無靜態障礙物。

    用 circle-AABB 碰撞判定（Medium 半徑 0.75m）。
    不檢查 Actor（由 can_end_move_at 另外處理）。
    """
    return is_position_clear(Position(x=x, y=y), SIZE_RADIUS_M[Size.MEDIUM], map_state)


# ---------------------------------------------------------------------------
# 實體查詢
# ---------------------------------------------------------------------------


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
    """找到離 pos 最近的有效位置（無碰撞、靜態障礙可通行）。

    在連續空間中以螺旋方式搜尋，步長 0.75m（半格）。
    """
    # 先檢查原位置
    if is_valid_position(pos.x, pos.y, map_state) and can_end_move_at(
        pos, size, map_state, exclude_id
    ):
        return pos

    # 螺旋搜尋
    step = 0.75  # 搜尋步長
    max_rings = 20  # 最多搜尋 20 圈
    for ring in range(1, max_rings + 1):
        r = ring * step
        # 每圈 8*ring 個採樣點
        n_samples = 8 * ring
        for i in range(n_samples):
            angle = 2 * math.pi * i / n_samples
            cx = pos.x + r * math.cos(angle)
            cy = pos.y + r * math.sin(angle)
            candidate = Position(x=round(cx, 2), y=round(cy, 2))
            if is_valid_position(cx, cy, map_state) and can_end_move_at(
                candidate, size, map_state, exclude_id
            ):
                return candidate

    # 退回原位置（不應發生）
    return pos


# ---------------------------------------------------------------------------
# 移動
# ---------------------------------------------------------------------------


def is_position_clear(
    pos: Position,
    radius: float,
    map_state: MapState,
) -> bool:
    """檢查圓形碰撞體在 pos 是否與靜態障礙物重疊。

    不檢查 Actor（由 can_end_move_at / can_traverse 另外處理）。
    """
    m = map_state.manifest

    # 地圖邊界（width/height 為公尺）
    if pos.x - radius < 0 or pos.x + radius > m.width:
        return False
    if pos.y - radius < 0 or pos.y + radius > m.height:
        return False

    # 靜態障礙物
    obstacles = extract_static_obstacles(map_state)
    return all(not circle_aabb_overlap(pos.x, pos.y, radius, ob) for ob in obstacles)


def move_entity(
    actor: Actor,
    tx: float,
    ty: float,
    map_state: MapState,
    speed_remaining: float,
    *,
    allies: set[str] | None = None,
    mover_size: Size = Size.MEDIUM,
) -> MoveResult:
    """嘗試移動 Actor 到目標公尺座標，完整 D&D 5e 移動規則。

    tx/ty 為目標公尺座標（連續空間），成本 = 歐幾里得距離。
    回傳 MoveResult（成功、剩餘速度、事件列表）。
    移動成功時直接修改 actor.x/y。

    規則：
    - 靜態障礙阻擋 → 不可移動
    - 敵對 Actor 佔據 → 不可穿越（除非體型差 ≥ 2）
    - 非敵對 Actor 佔據 → 可穿越（困難地形 ×2 消耗）
    - 不可在任何生物空間內結束移動（敵友皆然）
    - 離開敵對觸及範圍 → 回傳 OA 事件
    """
    allies = allies or set()
    events: list[MoveEvent] = []
    mover_radius = SIZE_RADIUS_M.get(mover_size, 0.75)

    target_pos = Position(x=tx, y=ty)

    # 暫時排除自己的阻擋
    old_blocking = actor.is_blocking
    actor.is_blocking = False

    # 1. 靜態障礙物碰撞
    if not is_position_clear(target_pos, mover_radius, map_state):
        actor.is_blocking = old_blocking
        return MoveResult(success=False, speed_remaining=speed_remaining)

    # 2. Actor 穿越規則
    difficult_from_creature = False
    for other in map_state.actors:
        if other.id == actor.id or not other.is_alive or not other.is_blocking:
            continue
        other_r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        center_dist = math.sqrt((other.x - tx) ** 2 + (other.y - ty) ** 2)
        if center_dist < mover_radius + other_r:
            is_hostile = other.id not in allies
            if not can_traverse(mover_size, Size.MEDIUM, is_hostile):
                actor.is_blocking = old_blocking
                return MoveResult(success=False, speed_remaining=speed_remaining)
            if not is_hostile:
                difficult_from_creature = True

    actor.is_blocking = old_blocking

    # 3. 成本計算
    cost = math.sqrt((tx - actor.x) ** 2 + (ty - actor.y) ** 2)

    # 穿越友軍困難地形
    if difficult_from_creature:
        cost *= 2
        events.append(
            MoveEvent(
                event_type="difficult_terrain",
                message="穿越友軍空間，視為困難地形",
            )
        )

    if speed_remaining < cost - 0.01:  # 容差 1cm
        return MoveResult(success=False, speed_remaining=speed_remaining)

    # 4. 記錄舊位置（OA 判定用）
    old_x, old_y = actor.x, actor.y

    # 5. 執行移動
    actor.x = round(tx, 2)
    actor.y = round(ty, 2)

    # 6. OA 偵測：離開敵對生物觸及範圍
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


def determine_cover(
    attacker: Position,
    target: Position,
    map_state: MapState,
) -> CoverType:
    """根據攻擊線段穿過的障礙物 AABB 判定掩蔽。

    不含起終點上的 Actor。
    1 個障礙物 = 半掩蔽(+2 AC)，2+ 個 = 3/4 掩蔽(+5 AC)。
    完全掩蔽（Total）需由上層判定（如完全在牆後、無視線）。
    """
    obstacles = extract_static_obstacles(map_state)
    blocking_count = 0

    # 靜態障礙物
    for ob in obstacles:
        if segment_aabb_intersect(attacker.x, attacker.y, target.x, target.y, ob):
            blocking_count += 1

    # 活著的 blocking Actor 也提供掩蔽（排除起終點上的）
    for a in map_state.actors:
        if not a.is_alive or not a.is_blocking:
            continue
        if _near(a.x, a.y, attacker.x, attacker.y) or _near(a.x, a.y, target.x, target.y):
            continue
        r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
        actor_aabb = AABB(a.x - r, a.y - r, a.x + r, a.y + r)
        if segment_aabb_intersect(attacker.x, attacker.y, target.x, target.y, actor_aabb):
            blocking_count += 1

    if blocking_count >= 2:
        return CoverType.THREE_QUARTERS
    if blocking_count == 1:
        return CoverType.HALF
    return CoverType.NONE


# 過渡期別名
determine_cover_from_grid = determine_cover


# ---------------------------------------------------------------------------
# 區域查詢
# ---------------------------------------------------------------------------


def zone_for_position(
    x: float | int, y: float | int, zones: list[Zone], grid_size: float = 1.5
) -> Zone | None:
    """座標 → 所屬區域。Zone 邊界為公尺座標，直接比較。"""
    fx, fy = float(x), float(y)
    for z in zones:
        if z.x_min <= fx <= z.x_max and z.y_min <= fy <= z.y_max:
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
# 法術射程驗證
# ---------------------------------------------------------------------------


def parse_spell_range_meters(range_str: str) -> float | None:
    """解析法術射程字串 → 公尺。"Self"/"Touch" → None。"""
    s = range_str.strip().lower()
    if s in ("self", "touch") or s.startswith("self"):
        return None
    # "120ft" → 120 * 0.3 = 36.0m（1ft = 0.3m）
    m = re.match(r"(\d+)\s*ft", s)
    if m:
        return int(m.group(1)) * 0.3
    return None


def validate_spell_range(spell: Spell, dist_m: float) -> str | None:
    """驗證法術射程（距離為公尺）。回傳錯誤訊息或 None。"""
    range_str = spell.range.strip().lower()
    if range_str == "self" or range_str.startswith("self"):
        return None
    if range_str == "touch":
        # 觸碰法術：需要在近戰觸及範圍（1.5m for Medium）
        if dist_m > 1.5:
            return f"觸碰法術需要在觸及範圍（當前 {dist_m:.1f}m）"
        return None
    range_m = parse_spell_range_meters(spell.range)
    if range_m is not None and dist_m > range_m:
        return f"超出法術射程（{spell.range}≈{range_m:.0f}m，當前 {dist_m:.1f}m）"
    return None


# ---------------------------------------------------------------------------
# 生成位置
# ---------------------------------------------------------------------------


def place_actors_at_spawn(
    characters: list[Character],
    monsters: list[Monster],
    map_state: MapState,
) -> None:
    """依 spawn_points 將戰鬥者放上地圖，建立 Actor 加入 map_state.actors。

    spawn_points 的 key 對應：'players' → characters、'enemies' → monsters。
    spawn_points 為公尺座標，直接使用。
    若 spawn_points 不足，多出的戰鬥者不會被放置。
    """
    spawns = map_state.manifest.spawn_points

    player_spawns = spawns.get("players", [])
    for i, char in enumerate(characters):
        if i >= len(player_spawns):
            break
        sp = player_spawns[i]
        pos = Position(x=sp.x, y=sp.y)
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
        sp = enemy_spawns[i]
        pos = Position(x=sp.x, y=sp.y)
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
