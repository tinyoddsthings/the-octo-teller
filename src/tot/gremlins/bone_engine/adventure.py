"""T.O.T. 冒險引擎——條件評估 / 事件觸發 / 對話管理。

所有函式為純函式，不改 state（回傳新 state 或結果物件）。
"""

from __future__ import annotations

import json
from pathlib import Path

from tot.models.adventure import (
    AdventureScript,
    AdventureState,
    DialogueLine,
    EventAction,
    NpcDef,
    SceneDef,
    ScriptEvent,
)


def evaluate_condition(
    condition: str,
    state: AdventureState,
    elapsed_minutes: int = 0,
) -> bool:
    """評估條件表達式。

    語法：
        ""                          → 永遠成立
        "has:flag_name"             → flag 存在（值 > 0）
        "not:flag_name"             → flag 不存在
        "all:cond1,cond2,..."       → 所有子條件都成立
        "any:cond1,cond2,..."       → 任一子條件成立
        "gte:flag_name:N"           → flag 值 ≥ N
        "lt:flag_name:N"            → flag 值 < N
        "within:flag_name:N"        → 計時 flag 設定後不到 N 分鐘
        "elapsed:flag_name:N"       → 計時 flag 設定後已過 N 分鐘
        "timer:flag_name"           → 計時 flag 存在
    """
    if not condition:
        return True

    # ── 組合子：all / any ──
    if condition.startswith("all:"):
        sub_conditions = _split_top_level(condition[4:])
        return all(evaluate_condition(c, state, elapsed_minutes) for c in sub_conditions)
    if condition.startswith("any:"):
        sub_conditions = _split_top_level(condition[4:])
        return any(evaluate_condition(c, state, elapsed_minutes) for c in sub_conditions)

    # ── 原子條件 ──
    if condition.startswith("has:"):
        flag = condition[4:]
        return state.story_flags.get(flag, 0) > 0

    if condition.startswith("not:"):
        flag = condition[4:]
        return state.story_flags.get(flag, 0) == 0

    if condition.startswith("gte:"):
        parts = condition[4:].rsplit(":", 1)
        flag, threshold = parts[0], int(parts[1])
        return state.story_flags.get(flag, 0) >= threshold

    if condition.startswith("lt:"):
        parts = condition[3:].rsplit(":", 1)
        flag, threshold = parts[0], int(parts[1])
        return state.story_flags.get(flag, 0) < threshold

    # ── 計時條件 ──
    if condition.startswith("timer:"):
        flag = condition[6:]
        return flag in state.timed_flags

    if condition.startswith("within:"):
        parts = condition[7:].rsplit(":", 1)
        flag, minutes = parts[0], int(parts[1])
        if flag not in state.timed_flags:
            return False
        return (elapsed_minutes - state.timed_flags[flag]) < minutes

    if condition.startswith("elapsed:"):
        parts = condition[8:].rsplit(":", 1)
        flag, minutes = parts[0], int(parts[1])
        if flag not in state.timed_flags:
            return False
        return (elapsed_minutes - state.timed_flags[flag]) >= minutes

    msg = f"未知的條件語法: {condition!r}"
    raise ValueError(msg)


def _split_top_level(expr: str) -> list[str]:
    """拆分 all:/any: 的子條件（逗號分隔）。

    "has:a,has:b" → ["has:a", "has:b"]
    "has:a,not:b"  → ["has:a", "not:b"]

    注意：不支援巢狀 all:/any:。如果未來需要巢狀，
    應改用括號語法（目前危在松溪不需要）。
    """
    return expr.split(",")


# ── 事件引擎 ──────────────────────────────────────────────


def check_events(
    script: AdventureScript,
    state: AdventureState,
    trigger_type: str,
    elapsed_minutes: int = 0,
    *,
    node_id: str = "",
    item_id: str = "",
    flag: str = "",
    dialogue_id: str = "",
) -> list[ScriptEvent]:
    """找出所有符合觸發條件的事件（不改 state）。

    回傳的事件按劇本中的定義順序排列。呼叫端應逐一
    用 execute_event() 處理。

    Args:
        trigger_type: "enter_node" / "take_item" / "flag_set" / "talk_end"
        node_id: enter_node 的目標節點
        item_id: take_item 的物品 id
        flag: flag_set 的 flag 名
        dialogue_id: talk_end 的對話 id
    """
    matched: list[ScriptEvent] = []
    for event in script.events:
        # once=True 且已觸發過 → 跳過
        if event.once and event.id in state.fired_events:
            continue

        trigger = event.trigger

        # 類型不符 → 跳過
        if trigger.type != trigger_type:
            continue

        # 觸發參數比對
        if trigger_type == "enter_node" and trigger.node_id and trigger.node_id != node_id:
            continue
        if trigger_type == "take_item" and trigger.item_id and trigger.item_id != item_id:
            continue
        if trigger_type == "flag_set" and trigger.flag and trigger.flag != flag:
            continue
        if (
            trigger_type == "talk_end"
            and trigger.dialogue_id
            and trigger.dialogue_id != dialogue_id
        ):
            continue

        # 觸發器條件
        if not evaluate_condition(trigger.condition, state, elapsed_minutes):
            continue

        # 事件層級條件
        if not evaluate_condition(event.condition, state, elapsed_minutes):
            continue

        matched.append(event)

    return matched


def execute_event(
    state: AdventureState,
    event: ScriptEvent,
    elapsed_minutes: int = 0,
) -> tuple[AdventureState, list[EventAction]]:
    """執行事件的所有 action，回傳新 state + 需要呈現的 action 列表。

    純函式——不改傳入的 state，回傳新的。
    只處理 state 變更類 action（set_flag/inc_flag/start_timer/clear_timer/move_npc）。
    呈現類 action（narrate/tutorial/reveal_node/reveal_edge/add_item）
    由呼叫端根據回傳的 action 列表處理。
    """
    # 深拷貝 state
    new_state = state.model_copy(deep=True)

    # 標記已觸發
    if event.once:
        new_state.fired_events.add(event.id)

    # 執行每個 action 的 state 變更
    for action in event.actions:
        if action.type == "set_flag":
            new_state.story_flags[action.flag] = action.value
        elif action.type == "inc_flag":
            current = new_state.story_flags.get(action.flag, 0)
            new_state.story_flags[action.flag] = current + action.value
        elif action.type == "start_timer":
            new_state.timed_flags[action.flag] = elapsed_minutes
        elif action.type == "clear_timer":
            new_state.timed_flags.pop(action.flag, None)
        elif action.type == "move_npc":
            new_state.npc_locations[action.npc_id] = action.node_id

    return new_state, list(event.actions)


# ── 對話引擎 ──────────────────────────────────────────────


def get_available_npcs(
    script: AdventureScript,
    state: AdventureState,
    node_id: str,
) -> list[NpcDef]:
    """取得目前節點上可對話的 NPC 列表。

    NPC 位置優先看 state.npc_locations（動態位置），
    其次看 NpcDef.node_id（初始位置）。
    """
    result: list[NpcDef] = []
    for npc in script.npcs.values():
        # 動態位置優先
        location = state.npc_locations.get(npc.id, npc.node_id)
        if location == node_id:
            result.append(npc)
    return result


def get_available_lines(
    npc: NpcDef,
    state: AdventureState,
    elapsed_minutes: int = 0,
) -> list[DialogueLine]:
    """取得 NPC 目前可用的對話行。

    如果有 active_dialogue → 只回傳該對話的 next_lines。
    否則回傳所有滿足 condition 的頂層對話行。

    「頂層」= 沒有被任何其他 DialogueLine.next_lines 引用的對話行。
    """
    # 建立 id → DialogueLine 索引
    line_map = {line.id: line for line in npc.dialogue}

    # 如果有進行中的對話
    if state.active_dialogue and state.active_dialogue in line_map:
        current = line_map[state.active_dialogue]
        # 回傳 next_lines 中條件符合的
        return [
            line_map[lid]
            for lid in current.next_lines
            if lid in line_map
            and evaluate_condition(line_map[lid].condition, state, elapsed_minutes)
        ]

    # 找出所有被引用的 id（非頂層）
    referenced: set[str] = set()
    for line in npc.dialogue:
        referenced.update(line.next_lines)

    # 回傳頂層且條件符合的
    return [
        line
        for line in npc.dialogue
        if line.id not in referenced and evaluate_condition(line.condition, state, elapsed_minutes)
    ]


def _build_global_line_map(
    script: AdventureScript | None,
    npc: NpcDef | None = None,
    scene: SceneDef | None = None,
) -> dict[str, DialogueLine]:
    """建立全域對話行索引（支援跨 NPC/場景對話鏈）。

    優先序（後加的覆蓋先加的）：
    1. scenes（最低優先）
    2. 其他 NPC
    3. 當前 NPC 或場景（最高優先）
    """
    line_map: dict[str, DialogueLine] = {}
    # 先加場景的（最低優先）
    if script:
        for s in script.scenes.values():
            if scene and s.id == scene.id:
                continue
            for line in s.dialogue:
                line_map[line.id] = line
    # 再加其他 NPC 的
    if script:
        npc_id = npc.id if npc else ""
        for other in script.npcs.values():
            if other.id != npc_id:
                for line in other.dialogue:
                    line_map[line.id] = line
    # 最後加當前 NPC 或場景的（最高優先）
    if npc:
        for line in npc.dialogue:
            line_map[line.id] = line
    if scene:
        for line in scene.dialogue:
            line_map[line.id] = line
    return line_map


def advance_dialogue(
    state: AdventureState,
    npc: NpcDef | None = None,
    line_id: str = "",
    script: AdventureScript | None = None,
    scene: SceneDef | None = None,
) -> tuple[AdventureState, DialogueLine, list[DialogueLine]]:
    """推進對話：選擇一行對話，回傳新 state + 當前行 + 後續可選行。

    純函式——不改傳入的 state。
    script 傳入時支援跨 NPC/場景 對話鏈。
    遇到 silent 節點會自動執行 flag 並遞迴推進。

    Returns:
        (new_state, chosen_line, next_available_lines)
        - next_available_lines 為空代表對話結束
    """
    line_map = _build_global_line_map(script, npc=npc, scene=scene)
    chosen = line_map[line_id]
    new_state = state.model_copy(deep=True)

    # 記錄到歷史
    if line_id not in new_state.dialogue_history:
        new_state.dialogue_history.append(line_id)

    # 設定 flag
    if chosen.sets_flag:
        new_state.story_flags[chosen.sets_flag] = 1

    # 決定後續
    if chosen.next_lines:
        new_state.active_dialogue = line_id
        next_lines = [
            line_map[lid]
            for lid in chosen.next_lines
            if lid in line_map and evaluate_condition(line_map[lid].condition, new_state)
        ]
    else:
        new_state.active_dialogue = None
        next_lines = []

    # silent 節點自動推進（遞迴，上限 10 層防無限迴圈）
    if chosen.silent and next_lines:
        return _advance_through_silent(new_state, next_lines[0], line_map, depth=0)

    return new_state, chosen, next_lines


def _advance_through_silent(
    state: AdventureState,
    line: DialogueLine,
    line_map: dict[str, DialogueLine],
    depth: int,
) -> tuple[AdventureState, DialogueLine, list[DialogueLine]]:
    """遞迴推進 silent 節點。"""
    if depth >= 10:
        return state, line, []

    new_state = state.model_copy(deep=True)

    if line.id not in new_state.dialogue_history:
        new_state.dialogue_history.append(line.id)

    if line.sets_flag:
        new_state.story_flags[line.sets_flag] = 1

    if line.next_lines:
        new_state.active_dialogue = line.id
        next_lines = [
            line_map[lid]
            for lid in line.next_lines
            if lid in line_map and evaluate_condition(line_map[lid].condition, new_state)
        ]
    else:
        new_state.active_dialogue = None
        next_lines = []

    if line.silent and next_lines:
        return _advance_through_silent(new_state, next_lines[0], line_map, depth + 1)

    return new_state, line, next_lines


def get_scene_entry_lines(
    scene: SceneDef,
    state: AdventureState,
    elapsed_minutes: int = 0,
) -> list[DialogueLine]:
    """取得場景的入口對話行（頂層且條件符合）。"""
    referenced: set[str] = set()
    for line in scene.dialogue:
        referenced.update(line.next_lines)

    return [
        line
        for line in scene.dialogue
        if line.id not in referenced and evaluate_condition(line.condition, state, elapsed_minutes)
    ]


# ── 載入 ──────────────────────────────────────────────────

_ADVENTURES_DIR = Path(__file__).parents[2] / "data" / "adventures"


def load_adventure(path: str | Path) -> AdventureScript:
    """從 JSON 檔案載入冒險劇本。

    path 可以是：
    - 絕對路徑
    - 相對路徑（相對於 cwd）
    - 純檔名（自動在 data/adventures/ 下查找）
    """
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        candidate = _ADVENTURES_DIR / p
        if not candidate.suffix:
            candidate = candidate.with_suffix(".json")
        p = candidate

    raw = json.loads(p.read_text(encoding="utf-8"))
    return AdventureScript.model_validate(raw)


def init_adventure_state(script: AdventureScript) -> AdventureState:
    """根據劇本建立初始冒險狀態。

    初始化 story_flags（來自 script.initial_flags）和
    npc_locations（來自各 NpcDef.node_id）。
    """
    npc_locations = {npc_id: npc.node_id for npc_id, npc in script.npcs.items() if npc.node_id}
    return AdventureState(
        script_id=script.id,
        story_flags=dict(script.initial_flags),
        npc_locations=npc_locations,
    )
