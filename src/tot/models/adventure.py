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

# ── 遭遇定義 ──────────────────────────────────────────────


class EnemyDef(BaseModel):
    """遭遇中的敵人定義。"""

    id: str
    name: str
    cr: str = "0"
    description: str = ""
    count: int = 1


class RewardDef(BaseModel):
    """遭遇獎勵。"""

    id: str
    name: str
    reward_type: str = "item"  # item / xp
    value_gp: int = 0
    xp: int = 0


class EncounterDef(BaseModel):
    """節點內的遭遇定義。"""

    enemies: list[EnemyDef] = Field(default_factory=list)
    trigger: str = "enter_node"  # enter_node / interact / flag_set
    narration: str = ""
    outcome: str = "auto_win"  # auto_win / combat
    rewards: list[RewardDef] = Field(default_factory=list)
    sets_flag: str = ""


# ── NPC 定義 ──────────────────────────────────────────────


class SpellAssistDef(BaseModel):
    """技能檢定時的輔助法術定義。"""

    name: str  # "導引術"
    spell_id: str  # "guidance"
    source_npc: str  # NPC ID（如 "evendorn"）
    bonus_die: str = ""  # "1d4" — 加骰型輔助
    advantage: bool = False  # True = 給予優勢
    requires_concentration: bool = True


class SkillCheckDef(BaseModel):
    """對話中的技能檢定定義。"""

    skill: str  # Skill enum value（如 "Perception"）
    dc: int
    pass_dialogue: str  # 成功時跳轉的對話 ID
    fail_dialogue: str  # 失敗時跳轉的對話 ID
    hidden_dc: bool = False  # True = 暗骰，不顯示 DC
    assists: list[SpellAssistDef] = Field(default_factory=list)


class DialogueLine(BaseModel):
    """單行對話（NPC 說的話、DM 旁白、或玩家選項）。"""

    id: str
    speaker: str  # npc_id 或 "dm"（DM 旁白）
    text: str
    condition: str = ""  # 條件表達式（空 = 永遠可用）
    sets_flag: str = ""  # 說完後設定的 flag（值 = 1）
    silent: bool = False  # 靜默節點（不顯示文字，自動推進）
    next_lines: list[str] = []  # 後續對話 id（空 = 結束）
    choice_label: str = ""  # 選擇分支的選項文字
    skill_check: SkillCheckDef | None = None  # 技能檢定（有時取代 choices）


class NpcDef(BaseModel):
    """NPC 定義——外觀、個性、對話。"""

    id: str
    name: str
    description: str = ""
    node_id: str | None = None  # 所在 Pointcrawl 節點
    dialogue: list[DialogueLine] = Field(default_factory=list)


# ── 場景定義 ──────────────────────────────────────────────


class SceneDef(BaseModel):
    """場景定義——多角色互動場景。"""

    id: str
    name: str
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
    scene_id: str = ""  # start_scene 的場景 ID


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
    scenes: dict[str, SceneDef] = Field(default_factory=dict)  # scene_id → SceneDef
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
