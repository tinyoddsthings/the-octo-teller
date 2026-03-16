"""T.O.T. Pointcrawl 探索系統資料模型。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from tot.models.enums import EncounterType, MapScale, NodeType
from tot.models.map import LootEntry, MapState, Position
from tot.models.time import GameClock


class EncounterResult(BaseModel):
    """潛行對抗察覺的判定結果。"""

    encounter_type: EncounterType
    stealth_rolls: dict[str, int] = Field(default_factory=dict)
    enemy_perception: int = 0
    surprised_ids: set[UUID] = Field(default_factory=set)
    message: str = ""


class DeploymentState(BaseModel):
    """佈陣階段狀態——戰鬥開始前的角色放置。"""

    map_state: MapState
    spawn_zone: list[Position] = Field(default_factory=list)
    placements: dict[str, Position] = Field(default_factory=dict)
    encounter: EncounterResult
    is_confirmed: bool = False


class NodeItem(BaseModel):
    """節點內的可發現物品。"""

    id: str
    name: str
    description: str = ""
    item_type: str = "item"  # item / clue / chest / trap_hint
    investigation_dc: int = 0  # 0 = 明顯可見，>0 需主動搜索
    is_discovered: bool = False  # 是否已被發現
    is_taken: bool = False  # 是否已被拿取
    value_gp: int = 0  # 金幣價值
    grants_key: str | None = None  # 拿取後獲得鑰匙 id（可開鎖用）


class ExplorationNode(BaseModel):
    """Pointcrawl 節點——玩家可到達的地點。"""

    id: str
    name: str
    node_type: NodeType
    description: str = ""  # 給 Narrator 的敘事素材

    # 與戰鬥地圖的銜接
    combat_map: str | None = None  # MapManifest JSON 檔名（遭遇戰鬥時載入）

    # 子地圖連結（世界→地城/城鎮，地城→子區域）
    sub_map: str | None = None  # ExplorationMap JSON 檔名（進入此節點時載入子地圖）

    # 狀態
    is_discovered: bool = True  # 玩家是否已知此節點
    is_visited: bool = False  # 玩家是否已到過

    # 城鎮專用：內含 POI 子節點
    pois: list[ExplorationNode] = Field(default_factory=list)

    # 敘事用
    ambient: str = ""  # 環境氛圍描述（聲音、氣味…）
    npcs: list[str] = Field(default_factory=list)  # 此處可遇到的 NPC id

    # 可發現物品
    hidden_items: list[NodeItem] = Field(default_factory=list)

    # 海拔（公尺）——顯示用，正值=高處
    elevation_m: float = 0


class ExplorationEdge(BaseModel):
    """Pointcrawl 路徑——連接兩個節點。"""

    id: str
    from_node_id: str
    to_node_id: str
    name: str = ""  # 例如：「鏽蝕鐵門」「泥濘商道」

    # 通行條件
    is_discovered: bool = True  # 是否對玩家可見
    is_locked: bool = False  # 上鎖（需要盜賊檢定或鑰匙）
    lock_dc: int = 0  # 開鎖 DC
    key_item: str | None = None  # 可用鑰匙物品 id
    hidden_dc: int = 0  # 隱藏通道的偵察 DC（0=不隱藏）
    is_one_way: bool = False  # 單向通道
    break_dc: int = 0  # STR DC 破門（0=不可破壞）
    noise_on_force: bool = True  # 破門時是否產生噪音

    # 世界圖層旅行參數
    distance_days: float = 0  # 旅行天數（世界圖層）
    distance_minutes: int = 0  # 移動分鐘數（地城圖層）
    danger_level: int = 0  # 危險等級 1-10（影響隨機遭遇）
    terrain_type: str = ""  # 地形（swamp/forest/mountain…）

    # 高低地 / 跳躍
    elevation_change_m: float = 0  # 高度差：正=上升、負=下降
    requires_jump: bool = False  # 是否需要 Athletics 跳躍檢定
    jump_dc: int = 0  # 跳躍 DC
    fall_damage_on_fail: bool = False  # 失敗時是否墜落受傷（仍到達目的地）

    # 狀態
    is_blocked: bool = False  # 坍塌、封鎖等


class ExplorationMap(BaseModel):
    """Pointcrawl 拓樸地圖（一張地城/一座城鎮/一個世界）。"""

    id: str
    name: str
    scale: MapScale
    nodes: list[ExplorationNode] = Field(default_factory=list)
    edges: list[ExplorationEdge] = Field(default_factory=list)

    # 入口：玩家進入此地圖時的起始節點
    entry_node_id: str = ""


class MapStackEntry(BaseModel):
    """子地圖堆疊中的一層（記住從哪裡進來）。"""

    map_id: str
    node_id: str  # 進入子地圖前所在的節點


class ExplorationState(BaseModel):
    """玩家在 Pointcrawl 系統中的即時位置。"""

    current_map_id: str  # 目前所在的 ExplorationMap
    current_node_id: str  # 目前所在的節點
    game_clock: GameClock = Field(default_factory=GameClock)
    discovered_nodes: set[str] = Field(default_factory=set)
    discovered_edges: set[str] = Field(default_factory=set)

    # 子地圖堆疊：從世界→地城→房間，像 call stack
    map_stack: list[MapStackEntry] = Field(default_factory=list)

    @property
    def elapsed_minutes(self) -> int:
        """向後相容：回傳經過的分鐘數。"""
        return self.game_clock.elapsed_seconds // 60


class AreaExploreState(BaseModel):
    """Area 自由探索的即時狀態。

    進入 Pointcrawl 節點的 area 地圖後啟用，
    追蹤隊伍位置、移動速度、已發現/拾取的物件。
    """

    map_state: MapState
    party_actor_id: str  # 隊伍 Actor 的 id
    speed_per_turn: float = 9.0  # 每回合移動速度（公尺）
    speed_remaining: float = 9.0  # 剩餘移動速度
    discovered_props: set[str] = Field(default_factory=set)  # 已發現的隱藏 Prop id
    looted_props: set[str] = Field(default_factory=set)  # 已拾取的 Prop id
    collected_items: list[LootEntry] = Field(default_factory=list)  # 已收集物品
    collected_keys: set[str] = Field(default_factory=set)  # 已收集的鑰匙 id
