"""中間表示（IR）——Parser 和 Builder 之間的橋樑。

Parser 把 Markdown 轉成 IR，Builder 把 IR 轉成 JSON。
IR 用 dataclass 而非 Pydantic，因為這是工具內部結構，不需要序列化驗證。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 地圖 IR ──────────────────────────────────────────────


@dataclass
class ItemIR:
    """節點內的可發現物品。"""

    name: str
    explicit_id: str | None = None
    item_type: str = "item"  # item / clue / chest / trap_hint
    investigation_dc: int = 0
    description: str = ""
    grants_key: str | None = None
    value_gp: int = 0


@dataclass
class PoiIR:
    """城鎮 POI（子節點）。"""

    name: str
    explicit_id: str | None = None
    description: str = ""
    npcs: list[str] = field(default_factory=list)


@dataclass
class EdgeIR:
    """節點之間的邊。"""

    name: str
    explicit_id: str | None = None
    to_id: str = ""  # 目標節點 ID（解析後填入）
    from_id: str = ""  # 來源節點 ID
    properties: dict[str, str] = field(default_factory=dict)
    # properties 包含：distance, terrain, danger_level, locked, lock_dc,
    # break_dc, hidden_dc, jump_dc, fall_damage, one_way, noise_on_force


@dataclass
class NodeIR:
    """Pointcrawl 節點。"""

    name: str
    explicit_id: str | None = None
    node_type: str = ""
    description: str = ""
    ambient: str = ""
    items: list[ItemIR] = field(default_factory=list)
    pois: list[PoiIR] = field(default_factory=list)
    edges: list[EdgeIR] = field(default_factory=list)
    combat_map: str | None = None
    sub_map: str | None = None
    npcs: list[str] = field(default_factory=list)


@dataclass
class MapIR:
    """完整地圖的 IR。"""

    meta: dict[str, str] = field(default_factory=dict)
    # meta 包含：id, name, scale, entry
    nodes: list[NodeIR] = field(default_factory=list)


# ── 劇本 IR ─────────────────────────────────────────────


@dataclass
class ChoiceIR:
    """對話中的玩家選項。"""

    label: str
    explicit_id: str | None = None
    next_id: str = ""  # 下一段對話 ID
    sets_flag: str = ""


@dataclass
class DialogueIR:
    """一段 NPC 對話。"""

    title: str
    explicit_id: str | None = None
    speaker: str = ""
    text: str = ""
    condition: str = ""
    sets_flag: str = ""
    choices: list[ChoiceIR] = field(default_factory=list)
    map_id: str = ""  # 綁定地圖（選填）
    chapter: str = ""  # 語法糖，chapter: 02 → has:chapter_02


@dataclass
class NpcIR:
    """NPC 定義。"""

    name: str
    explicit_id: str | None = None
    description: str = ""
    location: str = ""
    personality: str = ""
    role: str = ""
    dialogues: list[DialogueIR] = field(default_factory=list)


@dataclass
class EventIR:
    """章節事件。"""

    name: str
    explicit_id: str | None = None
    trigger_type: str = ""  # enter_node / take_item / flag_set / talk_end
    trigger_target: str = ""  # 觸發參數（node_id / item_id / flag / dialogue_id）
    condition: str = ""
    once: bool = True
    narrate: str = ""  # > blockquote 的旁白文字
    actions: list[dict[str, str]] = field(default_factory=list)
    # actions 是 list of {"type": ..., "flag": ..., ...}


@dataclass
class ChapterIR:
    """一個章節（一份 chapter MD）。"""

    chapter: str = ""  # 章節編號（如 "1", "02"）
    title: str = ""
    events: list[EventIR] = field(default_factory=list)


@dataclass
class ScriptIR:
    """完整劇本的 IR（meta + npcs + chapters 合併後）。"""

    meta: dict[str, str] = field(default_factory=dict)
    # meta 包含：id, name, description
    initial_flags: dict[str, int] = field(default_factory=dict)
    npcs: list[NpcIR] = field(default_factory=list)
    chapters: list[ChapterIR] = field(default_factory=list)
