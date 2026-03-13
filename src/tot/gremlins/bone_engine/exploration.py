"""Pointcrawl 探索邏輯。

節點對節點的移動系統，處理三層拓樸（地城/城鎮/世界）。
純確定性——不呼叫 LLM。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from tot.data.loader import load_map_manifest
from tot.gremlins.bone_engine.dice import roll_damage
from tot.gremlins.bone_engine.time_costs import (
    DUNGEON_MOVE_DEFAULT,
    SEARCH_ROOM_DUNGEON,
    SEARCH_ROOM_TOWN,
    TOWN_MOVE_DEFAULT,
)
from tot.models import (
    Character,
    ExplorationEdge,
    ExplorationMap,
    ExplorationNode,
    ExplorationState,
    MapScale,
    MapStackEntry,
    MapState,
    NodeItem,
    format_seconds_human,
)

# ---------------------------------------------------------------------------
# 結果型別
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveResult:
    """移動結果。"""

    success: bool
    node: ExplorationNode | None = None  # 到達的節點
    elapsed_seconds: int = 0  # 消耗時間（秒）
    message: str = ""
    noise_generated: bool = False  # 此次行動是否產生噪音


@dataclass(frozen=True)
class SearchResult:
    """搜索房間結果。"""

    elapsed_seconds: int = 600  # 搜索消耗時間（秒），預設 10 分鐘
    discovered_edges: list[str] | None = None  # 發現的隱藏通道 id
    message: str = ""


@dataclass(frozen=True)
class JumpResult:
    """跳躍/攀爬結果。"""

    success: bool
    node: ExplorationNode | None = None
    elapsed_seconds: int = 0  # 消耗時間（秒）
    message: str = ""
    fall_damage_dice: str = ""  # e.g. "3d6"
    fall_damage_total: int = 0  # 實際傷害
    check_total: int = 0
    check_dc: int = 0
    character_name: str = ""


@dataclass(frozen=True)
class NodeDescription:
    """組裝給 Narrator 的節點描述素材。"""

    node: ExplorationNode
    available_exits: list[ExplorationEdge]
    is_first_visit: bool


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------


def _get_node(exp_map: ExplorationMap, node_id: str) -> ExplorationNode | None:
    """依 id 查找節點。"""
    for n in exp_map.nodes:
        if n.id == node_id:
            return n
    return None


def _get_node_strict(exp_map: ExplorationMap, node_id: str) -> ExplorationNode:
    """依 id 查找節點，找不到則拋錯。"""
    for n in exp_map.nodes:
        if n.id == node_id:
            return n
    msg = f"節點 '{node_id}' 不存在於地圖 '{exp_map.id}'"
    raise KeyError(msg)


def _get_edge(exp_map: ExplorationMap, edge_id: str) -> ExplorationEdge:
    """依 id 查找路徑，找不到則拋錯。"""
    for e in exp_map.edges:
        if e.id == edge_id:
            return e
    msg = f"路徑 '{edge_id}' 不存在於地圖 '{exp_map.id}'"
    raise KeyError(msg)


def _scale_to_seconds(scale: MapScale, edge: ExplorationEdge) -> int:
    """根據地圖尺度計算移動時間（秒）。"""
    if scale == MapScale.DUNGEON:
        if edge.distance_minutes > 0:
            return edge.distance_minutes * 60
        return DUNGEON_MOVE_DEFAULT
    if scale == MapScale.TOWN:
        if edge.distance_minutes > 0:
            return edge.distance_minutes * 60
        return TOWN_MOVE_DEFAULT
    # 世界圖層：天 → 秒
    days = edge.distance_days if edge.distance_days > 0 else 1
    return int(days * 86400)


# ---------------------------------------------------------------------------
# 跳躍 / 墜落
# ---------------------------------------------------------------------------


def calculate_fall_damage_dice(height_m: float) -> str:
    """根據墜落高度計算傷害骰。

    D&D 規則：每 3m（10 呎）1d6，最高 20d6。
    """
    if height_m <= 0:
        return ""
    dice_count = min(math.ceil(height_m / 3), 20)
    return f"{dice_count}d6"


def attempt_jump(
    state: ExplorationState,
    exp_map: ExplorationMap,
    edge_id: str,
    character: Character,
    check_total: int,
    *,
    rng: random.Random | None = None,
) -> JumpResult:
    """嘗試跳躍/攀爬通過路徑。

    成功（total >= jump_dc）：移動到目的地。
    失敗 + fall_damage_on_fail：仍移動到目的地，骰墜落傷害。
    失敗 + 無 fall_damage：不移動，回傳失敗。
    """
    edge = _get_edge(exp_map, edge_id)
    current = state.current_node_id

    # 判斷目標節點
    if edge.from_node_id == current:
        target_id = edge.to_node_id
    elif not edge.is_one_way and edge.to_node_id == current:
        target_id = edge.from_node_id
    else:
        return JumpResult(success=False, message="這條路徑不在你目前的位置")

    target_node = _get_node_strict(exp_map, target_id)
    elapsed = _scale_to_seconds(exp_map.scale, edge)

    if check_total >= edge.jump_dc:
        # 成功
        state.current_node_id = target_id
        state.game_clock.add_event(elapsed)
        state.discovered_nodes.add(target_id)
        target_node.is_visited = True
        return JumpResult(
            success=True,
            node=target_node,
            elapsed_seconds=elapsed,
            message=f"{character.name} 成功通過了「{edge.name or edge_id}」！",
            check_total=check_total,
            check_dc=edge.jump_dc,
            character_name=character.name,
        )

    # 失敗
    if edge.fall_damage_on_fail:
        # 墜落但仍到達目的地
        height = abs(edge.elevation_change_m)
        dice_expr = calculate_fall_damage_dice(height)
        damage = 0
        if dice_expr:
            damage = roll_damage(dice_expr, rng=rng).total

        state.current_node_id = target_id
        state.game_clock.add_event(elapsed)
        state.discovered_nodes.add(target_id)
        target_node.is_visited = True
        return JumpResult(
            success=False,
            node=target_node,
            elapsed_seconds=elapsed,
            message=(
                f"{character.name} 跳躍失敗，墜落到了「{target_node.name}」！"
                f"受到 {damage} 點墜落傷害（{dice_expr}）"
            ),
            fall_damage_dice=dice_expr,
            fall_damage_total=damage,
            check_total=check_total,
            check_dc=edge.jump_dc,
            character_name=character.name,
        )

    # 失敗，不墜落，原地不動
    return JumpResult(
        success=False,
        message=f"{character.name} 攀爬失敗，滑了下來。",
        check_total=check_total,
        check_dc=edge.jump_dc,
        character_name=character.name,
    )


# ---------------------------------------------------------------------------
# 核心函式
# ---------------------------------------------------------------------------


def get_available_exits(
    state: ExplorationState,
    exp_map: ExplorationMap,
) -> list[ExplorationEdge]:
    """取得目前節點可走的路徑。

    過濾規則：
    - 只回傳已發現的 (is_discovered) 路徑
    - 包含上鎖 (is_locked) 的路徑（讓玩家知道門在但鎖住了）
    - 排除被封鎖 (is_blocked) 的路徑
    - 雙向路徑從兩端都可走；單向路徑只能從 from_node_id 走
    """
    current = state.current_node_id
    exits: list[ExplorationEdge] = []

    for edge in exp_map.edges:
        if edge.is_blocked:
            continue
        if not edge.is_discovered and edge.id not in state.discovered_edges:
            continue

        # 從 from_node 可走（正向）；非單向時從 to_node 也可走（反向）
        if edge.from_node_id == current or (not edge.is_one_way and edge.to_node_id == current):
            exits.append(edge)

    return exits


def move_to_node(
    state: ExplorationState,
    exp_map: ExplorationMap,
    edge_id: str,
) -> MoveResult:
    """沿著指定路徑移動到相鄰節點。

    會就地修改 state（位置、時間、發現狀態）。
    """
    edge = _get_edge(exp_map, edge_id)

    # 確認路徑可達
    current = state.current_node_id
    if edge.from_node_id == current:
        target_id = edge.to_node_id
    elif not edge.is_one_way and edge.to_node_id == current:
        target_id = edge.from_node_id
    else:
        return MoveResult(success=False, message="這條路徑不在你目前的位置")

    if edge.is_blocked:
        return MoveResult(success=False, message=f"路徑「{edge.name or edge_id}」已被封鎖")

    if edge.is_locked:
        return MoveResult(
            success=False,
            message=f"「{edge.name or edge_id}」上鎖了（DC {edge.lock_dc}）",
        )

    if edge.requires_jump:
        return MoveResult(
            success=False,
            message=f"「{edge.name or edge_id}」需要跳躍才能通過！請使用跳躍指令。",
        )

    target_node = _get_node_strict(exp_map, target_id)
    elapsed = _scale_to_seconds(exp_map.scale, edge)

    # 更新狀態
    state.current_node_id = target_id
    state.game_clock.add_event(elapsed)
    state.discovered_nodes.add(target_id)
    target_node.is_visited = True

    return MoveResult(
        success=True,
        node=target_node,
        elapsed_seconds=elapsed,
        message=f"你移動到了「{target_node.name}」",
    )


def discover_hidden(
    state: ExplorationState,
    exp_map: ExplorationMap,
    node_id: str,
    check_total: int,
) -> list[ExplorationEdge]:
    """嘗試發現節點周圍的隱藏通道。

    比對所有 hidden_dc > 0 且尚未被發現的路徑。
    回傳新發現的路徑列表。
    """
    discovered: list[ExplorationEdge] = []

    for edge in exp_map.edges:
        if edge.hidden_dc <= 0:
            continue
        if edge.is_discovered or edge.id in state.discovered_edges:
            continue

        # 只檢查與指定節點相關的路徑
        if edge.from_node_id != node_id and edge.to_node_id != node_id:
            continue

        if check_total >= edge.hidden_dc:
            edge.is_discovered = True
            state.discovered_edges.add(edge.id)
            discovered.append(edge)

    return discovered


def unlock_edge(
    state: ExplorationState,
    exp_map: ExplorationMap,
    edge_id: str,
    *,
    check_total: int = 0,
    key_item_id: str | None = None,
) -> MoveResult:
    """嘗試開鎖。

    可用盜賊工具檢定 (check_total vs lock_dc) 或鑰匙物品。
    """
    edge = _get_edge(exp_map, edge_id)

    if not edge.is_locked:
        return MoveResult(success=True, message="這條路徑沒有鎖")

    # 鑰匙直接開鎖
    if key_item_id and edge.key_item and key_item_id == edge.key_item:
        edge.is_locked = False
        return MoveResult(success=True, message=f"用鑰匙打開了「{edge.name or edge_id}」")

    # 檢定開鎖
    if check_total >= edge.lock_dc:
        edge.is_locked = False
        return MoveResult(
            success=True,
            message=f"成功撬開了「{edge.name or edge_id}」（DC {edge.lock_dc}）",
        )

    return MoveResult(
        success=False,
        message=f"開鎖失敗（{check_total} vs DC {edge.lock_dc}）",
    )


def force_open_edge(
    state: ExplorationState,
    exp_map: ExplorationMap,
    edge_id: str,
    str_check_total: int,
) -> MoveResult:
    """嘗試暴力破門（STR 檢定）。

    不管成敗都會產生噪音 (noise_generated=True)。
    break_dc == 0 表示此門無法被暴力破開。
    """
    edge = _get_edge(exp_map, edge_id)

    if not edge.is_locked:
        return MoveResult(success=True, message="這條路徑沒有鎖，不需要破門")

    if edge.break_dc == 0:
        return MoveResult(
            success=False,
            message=f"「{edge.name or edge_id}」無法被暴力破開",
        )

    noise = edge.noise_on_force

    if str_check_total >= edge.break_dc:
        edge.is_locked = False
        return MoveResult(
            success=True,
            noise_generated=noise,
            message=f"你猛力撞開了「{edge.name or edge_id}」！（DC {edge.break_dc}）",
        )

    return MoveResult(
        success=False,
        noise_generated=noise,
        message=f"破門失敗（{str_check_total} vs DC {edge.break_dc}），但巨響已經傳出去了",
    )


def search_room(
    state: ExplorationState,
    exp_map: ExplorationMap,
    node_id: str,
    check_total: int,
) -> SearchResult:
    """搜索房間：消耗時間 + 嘗試發現隱藏通道。

    地城圖層消耗 10 分鐘，城鎮消耗 60 分鐘。
    """
    search_seconds = SEARCH_ROOM_DUNGEON if exp_map.scale == MapScale.DUNGEON else SEARCH_ROOM_TOWN
    state.game_clock.add_event(search_seconds)

    found = discover_hidden(state, exp_map, node_id, check_total)
    found_ids = [e.id for e in found]

    time_str = format_seconds_human(search_seconds)
    if found:
        names = "、".join(e.name or e.id for e in found)
        msg = f"搜索了 {time_str}，發現了隱藏通道：{names}"
    else:
        msg = f"搜索了 {time_str}，沒有發現任何東西"

    return SearchResult(
        elapsed_seconds=search_seconds,
        discovered_edges=found_ids if found_ids else None,
        message=msg,
    )


def get_node_description(
    state: ExplorationState,
    exp_map: ExplorationMap,
    node_id: str,
) -> NodeDescription:
    """組裝節點描述素材，供 Narrator 使用。"""
    node = _get_node_strict(exp_map, node_id)
    exits = get_available_exits(state, exp_map)
    is_first = node_id not in state.discovered_nodes or not node.is_visited

    return NodeDescription(
        node=node,
        available_exits=exits,
        is_first_visit=is_first,
    )


# ---------------------------------------------------------------------------
# POI 互動
# ---------------------------------------------------------------------------


def list_pois(exp_map: ExplorationMap, node_id: str) -> list[ExplorationNode]:
    """列出節點內的 POI 子節點（城鎮專用）。"""
    node = _get_node_strict(exp_map, node_id)
    return list(node.pois)


def visit_poi(
    state: ExplorationState,
    exp_map: ExplorationMap,
    node_id: str,
    poi_id: str,
) -> NodeDescription:
    """造訪 POI 子節點，回傳描述素材。

    城鎮內 POI 不消耗移動時間（已在節點內）。
    """
    node = _get_node_strict(exp_map, node_id)
    poi = None
    for p in node.pois:
        if p.id == poi_id:
            poi = p
            break
    if poi is None:
        msg = f"POI '{poi_id}' 不存在於節點 '{node_id}'"
        raise KeyError(msg)

    poi.is_visited = True
    return NodeDescription(
        node=poi,
        available_exits=[],
        is_first_visit=not poi.is_visited,
    )


# ---------------------------------------------------------------------------
# 被動感知 + 物品搜索
# ---------------------------------------------------------------------------


def auto_passive_perception(
    state: ExplorationState,
    exp_map: ExplorationMap,
    node_id: str,
    best_passive: int,
) -> list[ExplorationEdge]:
    """進入新節點時自動以隊伍最高被動感知檢查隱藏通道。

    不消耗時間（被動 = 不需主動宣告），回傳新發現的路徑。
    """
    return discover_hidden(state, exp_map, node_id, best_passive)


def get_visible_items(
    exp_map: ExplorationMap,
    node_id: str,
) -> list[NodeItem]:
    """回傳明顯可見（investigation_dc == 0）或已發現的物品。

    進入節點時自動顯示用。
    """
    node = _get_node_strict(exp_map, node_id)
    return [
        item
        for item in node.hidden_items
        if not item.is_taken and (item.investigation_dc == 0 or item.is_discovered)
    ]


def search_items(
    exp_map: ExplorationMap,
    node_id: str,
    check_total: int,
) -> list[NodeItem]:
    """搜索節點內未發現的隱藏物品。

    check_total vs investigation_dc，回傳新發現的物品。
    不消耗額外時間（已包含在 search_room 的 10 分鐘中）。
    """
    node = _get_node_strict(exp_map, node_id)
    found: list[NodeItem] = []
    for item in node.hidden_items:
        if item.is_discovered or item.is_taken:
            continue
        if item.investigation_dc <= 0:
            continue
        if check_total >= item.investigation_dc:
            item.is_discovered = True
            found.append(item)
    return found


def take_item(
    exp_map: ExplorationMap,
    node_id: str,
    item_id: str,
) -> NodeItem | None:
    """拿取已發現的物品。標記 is_taken，回傳該物品；找不到回傳 None。"""
    node = _get_node_strict(exp_map, node_id)
    for item in node.hidden_items:
        if item.id == item_id and item.is_discovered and not item.is_taken:
            item.is_taken = True
            return item
    return None


# ---------------------------------------------------------------------------
# 格式化工具
# ---------------------------------------------------------------------------


def format_time(seconds: int) -> str:
    """將秒數格式化為可讀字串。委派給 format_seconds_human。"""
    return format_seconds_human(seconds)


# ---------------------------------------------------------------------------
# 子地圖進出
# ---------------------------------------------------------------------------


def enter_sub_map(
    state: ExplorationState,
    sub_map: ExplorationMap,
) -> ExplorationState:
    """進入子地圖（例如從世界地圖進入地城）。

    將目前位置推入堆疊，切換到子地圖的入口節點。
    """
    state.map_stack.append(
        MapStackEntry(map_id=state.current_map_id, node_id=state.current_node_id)
    )
    state.current_map_id = sub_map.id
    state.current_node_id = sub_map.entry_node_id
    state.discovered_nodes.add(sub_map.entry_node_id)

    # 標記入口節點為已造訪
    entry = _get_node(sub_map, sub_map.entry_node_id)
    if entry:
        entry.is_visited = True

    return state


def exit_to_parent_map(state: ExplorationState) -> ExplorationState:
    """返回上層地圖。

    從堆疊彈出上一層的位置。
    """
    if not state.map_stack:
        msg = "已在最頂層地圖，無法返回上層"
        raise ValueError(msg)

    parent = state.map_stack.pop()
    state.current_map_id = parent.map_id
    state.current_node_id = parent.node_id

    return state


# ---------------------------------------------------------------------------
# 探索→戰鬥銜接
# ---------------------------------------------------------------------------


def prepare_combat_from_node(
    exp_map: ExplorationMap,
    node_id: str,
) -> MapState | None:
    """從探索節點載入對應的戰鬥格子地圖。

    若節點有 combat_map 欄位，載入對應的 MapManifest 並回傳 MapState。
    若沒有 combat_map，回傳 None（在此節點無法進行格子戰鬥）。

    戰鬥結束後，上層直接繼續使用原本的 ExplorationState。
    """
    node = _get_node_strict(exp_map, node_id)
    if not node.combat_map:
        return None

    return load_map_manifest(name=node.combat_map)
