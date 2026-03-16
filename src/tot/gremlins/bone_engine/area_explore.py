"""Area 自由探索引擎。

Pointcrawl 節點 → 進入 area 地圖 → 自由移動 + 搜索/拾取 Prop。
純確定性邏輯——不呼叫 LLM、不含 UI 副作用。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from uuid import uuid4

from tot.data.loader import load_map_manifest
from tot.gremlins.bone_engine.checks import skill_check
from tot.gremlins.bone_engine.spatial import distance, move_entity
from tot.models import (
    Actor,
    AreaExploreState,
    Character,
    ExplorationMap,
    Item,
    LootEntry,
    MapState,
    MoveResult,
    Position,
    Prop,
    Size,
)
from tot.models.enums import ShapeType, Skill

# ---------------------------------------------------------------------------
# 結果資料結構
# ---------------------------------------------------------------------------

INTERACT_RADIUS_M = 0.5  # 互動半徑（邊緣到邊緣）


@dataclass(frozen=True)
class SearchResult:
    """搜索 Prop 的結果。"""

    success: bool
    prop_id: str
    message: str
    loot_available: bool = False


@dataclass(frozen=True)
class TerrainInfo:
    """當前位置的地形資訊。"""

    terrain_type: str  # "" = 平地
    elevation_m: float
    is_difficult: bool  # 困難地形（移動消耗 ×2）
    description: str


@dataclass(frozen=True)
class AreaMoveResult:
    """Area 移動結果（包裝 MoveResult + 地形資訊）。"""

    success: bool
    speed_remaining: float
    terrain: TerrainInfo | None = None
    message: str = ""


@dataclass
class AreaExitResult:
    """離開 area 的結果。"""

    collected_items: list[LootEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 地形效果
# ---------------------------------------------------------------------------

_TERRAIN_DESCRIPTIONS: dict[str, str] = {
    "hill": "地勢升高，腳下是崎嶇的斜坡",
    "crevice": "地面出現深深的裂縫，需要小心通過",
    "water": "淺水區域，行走困難",
    "rubble": "碎石遍地，行走緩慢",
}

_DIFFICULT_TERRAINS: set[str] = {"water", "rubble", "crevice"}


# ---------------------------------------------------------------------------
# 核心函式
# ---------------------------------------------------------------------------


def enter_area(
    exp_map: ExplorationMap,
    node_id: str,
    characters: list[Character],
) -> AreaExploreState | None:
    """從 Pointcrawl 節點進入 area 地圖。

    回傳 AreaExploreState，若節點沒有 combat_map 則回傳 None。
    隊伍以單一 Actor token 表示，放置在地圖第一個 player spawn point。
    """
    # 找到節點
    node = None
    for n in exp_map.nodes:
        if n.id == node_id:
            node = n
            break
    if node is None or not node.combat_map:
        return None

    map_state = load_map_manifest(name=node.combat_map)

    # 建立隊伍 Actor
    spawn_pos = _get_party_spawn(map_state)
    party_id = f"party-{uuid4().hex[:8]}"
    party_actor = Actor(
        id=party_id,
        x=spawn_pos.x,
        y=spawn_pos.y,
        is_blocking=True,
        name="隊伍",
        combatant_id=uuid4(),
        combatant_type="character",
        size=Size.MEDIUM,
    )
    map_state.actors.append(party_actor)

    # 計算隊伍速度（取最慢角色）
    speed = min((c.speed for c in characters), default=9.0)

    return AreaExploreState(
        map_state=map_state,
        party_actor_id=party_id,
        speed_per_turn=speed,
        speed_remaining=speed,
    )


def exit_area(area_state: AreaExploreState) -> AreaExitResult:
    """離開 area，回傳收集的物品。"""
    return AreaExitResult(collected_items=list(area_state.collected_items))


def explore_move(
    area_state: AreaExploreState,
    tx: float,
    ty: float,
) -> AreaMoveResult:
    """自由移動隊伍到指定座標。

    委託 spatial.move_entity()，不檢查 OA（探索模式無敵人）。
    地形 Prop 的困難地形效果由此函式處理。
    """
    actor = _get_party_actor(area_state)
    if actor is None:
        return AreaMoveResult(
            success=False,
            speed_remaining=area_state.speed_remaining,
            message="找不到隊伍",
        )

    # 檢查目標位置是否有地形效果 → 調整速度消耗
    terrain = _check_terrain_at_pos(area_state.map_state, tx, ty)

    # 困難地形需要 ×2 速度消耗——先用一半的 speed_remaining 計算
    effective_speed = area_state.speed_remaining
    if terrain and terrain.is_difficult:
        effective_speed = area_state.speed_remaining / 2.0

    result: MoveResult = move_entity(actor, tx, ty, area_state.map_state, effective_speed)

    if result.success:
        # 實際消耗 = 原始消耗 × 困難地形倍率
        base_cost = effective_speed - result.speed_remaining
        actual_cost = base_cost * 2.0 if (terrain and terrain.is_difficult) else base_cost
        area_state.speed_remaining -= actual_cost
    else:
        terrain = None  # 沒有移動到，不回報地形

    return AreaMoveResult(
        success=result.success,
        speed_remaining=area_state.speed_remaining,
        terrain=terrain,
        message=terrain.description if terrain and terrain.terrain_type else "",
    )


def reset_movement(area_state: AreaExploreState) -> None:
    """重置移動速度（相當於新回合）。"""
    area_state.speed_remaining = area_state.speed_per_turn


def _edge_gap(actor: Actor, prop: Prop) -> float:
    """Actor 邊緣到 Prop 邊緣的距離（公尺）。

    負值表示重疊。Actor 一律視為圓形（from_size）。
    Prop 無 bounds 時視為點（半徑 0）。
    """
    dx = actor.x - prop.x
    dy = actor.y - prop.y
    actor_r = actor.bounds.radius_m if actor.bounds else 0.75

    if prop.bounds is None:
        # 無碰撞的小物件（蘑菇、掉落物）→ 視為點
        return math.sqrt(dx * dx + dy * dy) - actor_r

    if prop.bounds.shape_type == ShapeType.CIRCLE:
        return math.sqrt(dx * dx + dy * dy) - actor_r - prop.bounds.radius_m

    # 矩形：找 prop 邊緣上離 actor 中心最近的點
    hw = prop.bounds.half_width_m
    hh = prop.bounds.half_height_m
    nearest_x = max(prop.x - hw, min(actor.x, prop.x + hw))
    nearest_y = max(prop.y - hh, min(actor.y, prop.y + hh))
    ndx = actor.x - nearest_x
    ndy = actor.y - nearest_y
    return math.sqrt(ndx * ndx + ndy * ndy) - actor_r


def get_nearby_props(
    area_state: AreaExploreState,
    radius: float = INTERACT_RADIUS_M,
) -> list[Prop]:
    """取得隊伍附近的可互動 Prop（邊緣到邊緣距離）。"""
    actor = _get_party_actor(area_state)
    if actor is None:
        return []

    result: list[Prop] = []

    for prop in area_state.map_state.manifest.props:
        if not prop.interactable:
            continue
        # 隱藏且未發現 → 跳過
        if prop.hidden and prop.id not in area_state.discovered_props:
            continue
        if _edge_gap(actor, prop) <= radius:
            result.append(prop)

    return result


def search_prop(
    area_state: AreaExploreState,
    prop_id: str,
    character: Character,
    *,
    rng: random.Random | None = None,
) -> SearchResult:
    """搜索指定 Prop。

    使用 Investigation 技能檢定 vs Prop 的 investigation_dc。
    DC 為 0 表示明顯可見（自動成功）。
    """
    prop = _find_prop(area_state.map_state, prop_id)
    if prop is None:
        return SearchResult(success=False, prop_id=prop_id, message="找不到該物件")

    if not prop.interactable:
        return SearchResult(success=False, prop_id=prop_id, message="此物件無法互動")

    if prop.is_searched:
        has_loot = bool(prop.loot_items) and not prop.is_looted
        return SearchResult(
            success=True,
            prop_id=prop_id,
            message=prop.interact_message or "已經搜索過了",
            loot_available=has_loot,
        )

    # DC 0 = 自動成功
    if prop.investigation_dc <= 0:
        prop.is_searched = True
        area_state.discovered_props.add(prop_id)
        has_loot = bool(prop.loot_items) and not prop.is_looted
        return SearchResult(
            success=True,
            prop_id=prop_id,
            message=prop.interact_message or "你發現了什麼",
            loot_available=has_loot,
        )

    # Investigation 檢定
    check = skill_check(character, Skill.INVESTIGATION, prop.investigation_dc, rng=rng)
    if check.success:
        prop.is_searched = True
        area_state.discovered_props.add(prop_id)
        has_loot = bool(prop.loot_items) and not prop.is_looted
        return SearchResult(
            success=True,
            prop_id=prop_id,
            message=prop.interact_message or "仔細搜索後，你發現了東西",
            loot_available=has_loot,
        )

    return SearchResult(
        success=False,
        prop_id=prop_id,
        message=f"搜索失敗（{check.total} vs DC {prop.investigation_dc}）",
    )


def take_prop_loot(
    area_state: AreaExploreState,
    prop_id: str,
) -> list[LootEntry]:
    """拾取 Prop 內的所有物品。

    回傳拾取的物品列表。已拾取過的 Prop 回傳空列表。
    """
    prop = _find_prop(area_state.map_state, prop_id)
    if prop is None or prop.is_looted or not prop.loot_items:
        return []

    if not prop.is_searched:
        return []  # 尚未搜索，不知道有東西

    items = list(prop.loot_items)
    area_state.collected_items.extend(items)
    area_state.looted_props.add(prop_id)
    prop.is_looted = True

    # 自動註冊鑰匙
    for item in items:
        if item.grants_key:
            area_state.collected_keys.add(item.grants_key)

    return items


def check_terrain_at(area_state: AreaExploreState) -> TerrainInfo:
    """檢查隊伍當前位置的地形效果。"""
    actor = _get_party_actor(area_state)
    if actor is None:
        return TerrainInfo(terrain_type="", elevation_m=0.0, is_difficult=False, description="")
    return _check_terrain_at_pos(area_state.map_state, actor.x, actor.y)


def get_party_position(area_state: AreaExploreState) -> Position | None:
    """取得隊伍目前位置。"""
    actor = _get_party_actor(area_state)
    if actor is None:
        return None
    return Position(x=actor.x, y=actor.y)


# ---------------------------------------------------------------------------
# 背包系統
# ---------------------------------------------------------------------------


def loot_to_item(loot: LootEntry) -> Item:
    """LootEntry → Item 轉換。"""
    return Item(
        name=loot.name,
        description=loot.description,
        quantity=loot.quantity,
    )


def transfer_loot_to_inventory(
    area_state: AreaExploreState,
    characters: list[Character],
) -> list[Item]:
    """離開 Area 時，將 collected_items 轉入第一個角色的 inventory。

    回傳轉換後的 Item 列表。
    """
    if not area_state.collected_items or not characters:
        return []

    items = [loot_to_item(loot) for loot in area_state.collected_items]
    characters[0].inventory.extend(items)
    return items


# ---------------------------------------------------------------------------
# 鑰匙 / 門互動
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnlockResult:
    """開鎖結果。"""

    success: bool
    prop_id: str
    message: str


def unlock_area_prop(
    area_state: AreaExploreState,
    prop_id: str,
    *,
    check_total: int = 0,
    key_item_id: str | None = None,
) -> UnlockResult:
    """嘗試開鎖 Area 中的 Prop（門）。

    可用鑰匙直接開鎖，或用開鎖檢定（check_total vs lock_dc）。
    開鎖後 is_locked=False + is_blocking=False（門打開可通行）。
    """
    prop = _find_prop(area_state.map_state, prop_id)
    if prop is None:
        return UnlockResult(success=False, prop_id=prop_id, message="找不到該物件")

    if not prop.is_locked:
        return UnlockResult(success=True, prop_id=prop_id, message="這扇門沒有鎖")

    # 鑰匙直接開鎖
    if key_item_id and prop.key_item and key_item_id == prop.key_item:
        prop.is_locked = False
        prop.is_blocking = False
        return UnlockResult(
            success=True,
            prop_id=prop_id,
            message=f"用鑰匙打開了「{prop.name or prop_id}」",
        )

    # 檢定開鎖
    if check_total >= prop.lock_dc:
        prop.is_locked = False
        prop.is_blocking = False
        return UnlockResult(
            success=True,
            prop_id=prop_id,
            message=f"成功撬開了「{prop.name or prop_id}」（DC {prop.lock_dc}）",
        )

    return UnlockResult(
        success=False,
        prop_id=prop_id,
        message=f"開鎖失敗（{check_total} vs DC {prop.lock_dc}）",
    )


def get_nearby_doors(
    area_state: AreaExploreState,
    radius: float = INTERACT_RADIUS_M,
) -> list[Prop]:
    """取得隊伍附近的門 Prop（含上鎖的）。"""
    actor = _get_party_actor(area_state)
    if actor is None:
        return []

    result: list[Prop] = []
    for prop in area_state.map_state.manifest.props:
        if prop.prop_type != "door":
            continue
        if _edge_gap(actor, prop) <= radius:
            result.append(prop)
    return result


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------


def _get_party_actor(area_state: AreaExploreState) -> Actor | None:
    """取得隊伍 Actor。"""
    for actor in area_state.map_state.actors:
        if actor.id == area_state.party_actor_id:
            return actor
    return None


def _get_party_spawn(map_state: MapState) -> Position:
    """取得第一個 player spawn point。"""
    players = map_state.manifest.spawn_points.get("players", [])
    if players:
        return players[0]
    # fallback: 地圖中央
    m = map_state.manifest
    return Position(
        x=round(m.width / 2, 2),
        y=round(m.height / 2, 2),
    )


def _find_prop(map_state: MapState, prop_id: str) -> Prop | None:
    """依 id 找 Prop（從 manifest.props 查找）。"""
    for p in map_state.manifest.props:
        if p.id == prop_id:
            return p
    return None


def _check_terrain_at_pos(map_state: MapState, x: float, y: float) -> TerrainInfo:
    """檢查指定座標的地形 Prop。"""
    pos = Position(x=x, y=y)
    best_terrain = ""
    best_elevation = 0.0

    for prop in map_state.manifest.props:
        if not prop.terrain_type:
            continue
        prop_pos = Position(x=prop.x, y=prop.y)
        # 地形 Prop 影響範圍：用 bounds 或預設 1m 半徑
        if prop.bounds:
            if prop.bounds.contains_point(prop.x, prop.y, x, y):
                best_terrain = prop.terrain_type
                best_elevation = prop.elevation_m
        elif distance(pos, prop_pos) <= 1.0:
            best_terrain = prop.terrain_type
            best_elevation = prop.elevation_m

    return TerrainInfo(
        terrain_type=best_terrain,
        elevation_m=best_elevation,
        is_difficult=best_terrain in _DIFFICULT_TERRAINS,
        description=_TERRAIN_DESCRIPTIONS.get(best_terrain, ""),
    )
