"""中間表示（IR）——Parser 和 Builder 之間的橋樑。

Parser 把 Markdown 轉成 IR，Builder 把 IR 轉成 JSON。
IR 用 dataclass 而非 Pydantic，因為這是工具內部結構，不需要序列化驗證。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 遭遇 IR ─────────────────────────────────────────────


@dataclass
class EnemyIR:
    """遭遇中的敵人。"""

    name: str
    explicit_id: str | None = None
    cr: str = "0"  # Challenge Rating（如 "2", "1/4"）
    description: str = ""
    count: int = 1


@dataclass
class RewardIR:
    """遭遇獎勵（物品或經驗值）。"""

    name: str
    explicit_id: str | None = None
    reward_type: str = "item"  # item / xp
    value_gp: int = 0
    xp: int = 0


@dataclass
class EncounterIR:
    """節點內的遭遇區塊。"""

    enemies: list[EnemyIR] = field(default_factory=list)
    trigger: str = "enter_node"  # enter_node / interact / flag_set
    narration: str = ""
    outcome: str = "auto_win"  # auto_win / combat
    rewards: list[RewardIR] = field(default_factory=list)
    sets_flag: str = ""


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
    encounter: EncounterIR | None = None


@dataclass
class MapIR:
    """完整地圖的 IR。"""

    meta: dict[str, str] = field(default_factory=dict)
    # meta 包含：id, name, scale, entry
    nodes: list[NodeIR] = field(default_factory=list)


# ── 劇本 IR ─────────────────────────────────────────────


@dataclass
class SpellAssistIR:
    """技能檢定的輔助法術。"""

    name: str  # "導引術"
    spell_id: str = ""  # "guidance"
    source_npc: str = ""  # "evendorn"
    bonus_die: str = ""  # "1d4"
    advantage: bool = False
    requires_concentration: bool = True


@dataclass
class SkillCheckIR:
    """對話中的技能檢定。"""

    skill: str  # "Perception", "Nature" 等
    dc: int = 10
    pass_id: str = ""  # 成功跳轉的對話 ID
    fail_id: str = ""  # 失敗跳轉的對話 ID
    hidden_dc: bool = False
    assists: list[SpellAssistIR] = field(default_factory=list)


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
    silent: bool = False
    condition: str = ""
    sets_flag: str = ""
    choices: list[ChoiceIR] = field(default_factory=list)
    skill_check: SkillCheckIR | None = None  # 技能檢定（取代 choices）
    next_id: str = ""  # 無選項時自動推進到下一段對話 ID
    map_id: str = ""  # 綁定地圖（選填）
    chapter: str = ""  # 語法糖，chapter: 02 → has:chapter_02


@dataclass
class SceneIR:
    """場景定義——多角色互動場景。"""

    name: str
    explicit_id: str | None = None
    trigger_type: str = ""  # enter_node / flag_set / etc.
    trigger_target: str = ""
    condition: str = ""
    once: bool = True
    dialogues: list[DialogueIR] = field(default_factory=list)


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
