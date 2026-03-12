"""Bone Engine 移動邏輯。

純確定性路徑規劃，不含 UI log 和副作用（傷害、移動執行）。
從 tui/actions.py 和 tui/npc_ai.py 搬入的純計算邏輯。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from tot.gremlins.bone_engine.pathfinding import find_furthest_along_path, find_path_to_range
from tot.gremlins.bone_engine.spatial import distance, get_actor_position
from tot.models import (
    SIZE_RADIUS_M,
    Actor,
    Character,
    CombatState,
    MapState,
    Monster,
    Position,
    Size,
)

# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------


@dataclass
class ActorLists:
    """敵友分類結果。"""

    blocked: list[Actor]
    passable: list[Actor]


# ---------------------------------------------------------------------------
# Actor 查詢（bone_engine 內部用，不依賴 tui）
# ---------------------------------------------------------------------------


def _find_actor(combatant_id: UUID, map_state: MapState) -> Actor | None:
    """以 combatant_id 查詢 Actor。"""
    for a in map_state.actors:
        if a.combatant_id == combatant_id:
            return a
    return None


# ---------------------------------------------------------------------------
# 友方 / 敵友分類
# ---------------------------------------------------------------------------


def build_friendly_ids(
    mover: Character | Monster,
    characters: list[Character],
    monsters: list[Monster],
) -> set[UUID]:
    """建立友方 ID 集合（Character → 所有 character；Monster → 所有 monster）。"""
    if isinstance(mover, Character):
        return {c.id for c in characters}
    return {m.id for m in monsters}


def build_actor_lists(
    actor: Actor,
    mover: Character | Monster | None,
    map_state: MapState,
    characters: list[Character],
    monsters: list[Monster],
    *,
    exclude_id: UUID | None = None,
) -> ActorLists:
    """區分敵方（blocked）和友方（passable）Actor。

    exclude_id：攻擊目標不應視為障礙物，傳入後從 blocked 排除。
    """
    friendly_ids: set[UUID] = set()
    if mover:
        friendly_ids = build_friendly_ids(mover, characters, monsters)

    blocked: list[Actor] = []
    passable: list[Actor] = []
    for a in map_state.actors:
        if a.combatant_id == actor.combatant_id:
            continue
        if exclude_id and a.combatant_id == exclude_id:
            continue
        if not a.is_alive or not a.is_blocking:
            continue
        if a.combatant_id in friendly_ids:
            passable.append(a)
        else:
            blocked.append(a)
    return ActorLists(blocked=blocked, passable=passable)


# ---------------------------------------------------------------------------
# 路徑規劃
# ---------------------------------------------------------------------------


def move_toward_target(
    actor: Actor,
    target_id: UUID,
    reach_m: float,
    mover: Character | Monster | None,
    combat_state: CombatState,
    map_state: MapState,
    characters: list[Character],
    monsters: list[Monster],
    *,
    greedy_fallback: bool = True,
) -> tuple[list[Position], float] | None:
    """A* 尋路取得路徑，不執行移動。

    回傳 (path, estimated_cost) 或 None（完全不可達）。
    path 為空 list 表示已在範圍內（cost = 0）。

    greedy_fallback=True：速度不足時盡量靠近（NPC 用）。
    greedy_fallback=False：到不了就回傳 None。
    """
    tgt_pos = get_actor_position(target_id, map_state)
    speed_left = combat_state.turn_state.movement_remaining

    if not tgt_pos:
        return None

    cur_pos = Position(x=actor.x, y=actor.y)

    # 已在範圍內
    cur_dist = distance(cur_pos, tgt_pos)
    if cur_dist <= reach_m:
        return ([], 0.0)

    if speed_left < 0.01:
        return None

    mover_size = Size.MEDIUM
    if mover:
        mover_size = getattr(mover, "size", Size.MEDIUM)
    mover_radius = SIZE_RADIUS_M.get(mover_size, 0.75)

    lists = build_actor_lists(actor, mover, map_state, characters, monsters, exclude_id=target_id)

    # 先嘗試完整路徑
    path = find_path_to_range(
        start=cur_pos,
        target=tgt_pos,
        reach_m=reach_m,
        map_state=map_state,
        mover_radius=mover_radius,
        max_cost=speed_left,
        blocked_actors=lists.blocked,
        passable_actors=lists.passable,
    )

    if path is None and greedy_fallback:
        # 完全不可達 → 盡量靠近
        path = find_furthest_along_path(
            start=cur_pos,
            target=tgt_pos,
            reach_m=reach_m,
            map_state=map_state,
            mover_radius=mover_radius,
            max_cost=speed_left,
            blocked_actors=lists.blocked,
            passable_actors=lists.passable,
        )

    if path is None:
        return None

    # 計算路徑成本
    cost = 0.0
    prev = cur_pos
    for wp in path:
        cost += math.sqrt((wp.x - prev.x) ** 2 + (wp.y - prev.y) ** 2)
        prev = wp

    return (path, cost)


def path_to_attack_range(
    attacker_id: UUID,
    target_id: UUID,
    reach_m: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
) -> tuple[float, float, float, list[Position]] | None:
    """A* 尋路到攻擊/法術範圍。

    回傳 (x_m, y_m, 移動消耗, 路徑) 或 None。
    路徑用於 step_move_to 直接沿路徑點移動。
    """
    actor = _find_actor(attacker_id, map_state)
    tgt_pos = get_actor_position(target_id, map_state)
    if not actor or not tgt_pos:
        return None

    speed_left = combat_state.turn_state.movement_remaining
    if speed_left < 0.01:
        return None

    start = Position(x=actor.x, y=actor.y)

    combatant = combatant_map.get(attacker_id)
    mover_size = Size.MEDIUM
    if combatant:
        mover_size = getattr(combatant, "size", Size.MEDIUM)
    mover_radius = SIZE_RADIUS_M.get(mover_size, 0.75)

    lists = build_actor_lists(
        actor,
        combatant,
        map_state,
        characters,
        monsters,
        exclude_id=target_id,
    )

    path = find_path_to_range(
        start=start,
        target=tgt_pos,
        reach_m=reach_m,
        map_state=map_state,
        mover_radius=mover_radius,
        max_cost=speed_left,
        blocked_actors=lists.blocked,
        passable_actors=lists.passable,
    )

    if path is not None and len(path) > 0:
        end = path[-1]
        cost = 0.0
        prev = start
        for wp in path:
            cost += math.sqrt((wp.x - prev.x) ** 2 + (wp.y - prev.y) ** 2)
            prev = wp
        return (end.x, end.y, cost, path)
    return None
