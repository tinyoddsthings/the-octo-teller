"""T.O.T. 固定劇本冒險系統資料模型。

冒險劇本（AdventureScript）與地圖資料分離——同一張 Pointcrawl 地圖
可以搭配不同劇本。劇本用 JSON 定義，透過 Pydantic 載入。

進度追蹤用 story_flags（dict[str, int]）：
- 值 = 1 為布林 flag（has/not）
- 值 > 1 為計數器（好感度、拜訪次數）
- 條件表達式支援 has/not/all/any/gte/lt/within/elapsed/timer
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── NPC 定義 ──────────────────────────────────────────────


class DialogueLine(BaseModel):
    """單行對話（NPC 說的話、DM 旁白、或玩家選項）。"""

    id: str
    speaker: str  # npc_id 或 "dm"（DM 旁白）
    text: str
    condition: str = ""  # 條件表達式（空 = 永遠可用）
    sets_flag: str = ""  # 說完後設定的 flag（值 = 1）
    next_lines: list[str] = []  # 後續對話 id（空 = 結束）
    choice_label: str = ""  # 選擇分支的選項文字


class NpcDef(BaseModel):
    """NPC 定義——外觀、個性、對話。"""

    id: str
    name: str
    description: str = ""
    node_id: str | None = None  # 所在 Pointcrawl 節點
    dialogue: list[DialogueLine] = Field(default_factory=list)


# ── 事件定義 ──────────────────────────────────────────────


class EventTrigger(BaseModel):
    """事件觸發條件。"""

    type: str  # "enter_node" / "take_item" / "flag_set" / "talk_end"
    node_id: str = ""  # enter_node 用
    item_id: str = ""  # take_item 用
    flag: str = ""  # flag_set 用
    dialogue_id: str = ""  # talk_end 用
    condition: str = ""  # 額外條件表達式


class EventAction(BaseModel):
    """事件觸發後的動作。"""

    type: str
    # "narrate" / "set_flag" / "inc_flag" / "start_timer" / "clear_timer"
    # / "move_npc" / "add_item" / "reveal_node" / "reveal_edge" / "tutorial"
    text: str = ""  # narrate/tutorial 的文字
    flag: str = ""  # set_flag/inc_flag/start_timer/clear_timer 的 flag 名
    value: int = 1  # set_flag 的值 / inc_flag 的增量
    npc_id: str = ""  # move_npc 的 NPC
    node_id: str = ""  # move_npc/reveal_node 的目標節點
    edge_id: str = ""  # reveal_edge 的邊
    item_id: str = ""  # add_item 的物品


class ScriptEvent(BaseModel):
    """劇本事件——觸發條件 + 動作列表。"""

    id: str
    trigger: EventTrigger
    actions: list[EventAction] = Field(default_factory=list)
    condition: str = ""  # 事件層級的前置條件
    once: bool = True  # 只觸發一次


# ── 劇本 ──────────────────────────────────────────────────


class AdventureScript(BaseModel):
    """冒險劇本——NPC + 事件的完整定義。"""

    id: str  # "peril_in_pinebrook"
    name: str  # "危在松溪"
    description: str = ""
    npcs: dict[str, NpcDef] = Field(default_factory=dict)  # npc_id → NpcDef
    events: list[ScriptEvent] = Field(default_factory=list)  # 按優先序排列
    initial_flags: dict[str, int] = Field(default_factory=dict)


# ── 冒險狀態 ──────────────────────────────────────────────


class AdventureState(BaseModel):
    """冒險進度——story flags、已觸發事件、NPC 位置、對話進度。"""

    script_id: str
    story_flags: dict[str, int] = Field(default_factory=dict)
    timed_flags: dict[str, int] = Field(default_factory=dict)  # flag → 設定時的 elapsed_minutes
    fired_events: set[str] = Field(default_factory=set)
    npc_locations: dict[str, str] = Field(default_factory=dict)  # npc_id → node_id
    active_dialogue: str | None = None  # 目前進行中的 dialogue_id
    dialogue_history: list[str] = Field(default_factory=list)
