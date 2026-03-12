"""T.O.T. Pointcrawl 探索系統資料模型。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from tot.models.enums import EncounterType, MapScale, NodeType
from tot.models.map import MapState, Position


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


class ExplorationNode(BaseModel):
    """Pointcrawl 節點——玩家可到達的地點。"""

    id: str
    name: str
    node_type: NodeType
    description: str = ""  # 給 Narrator 的敘事素材

    # 與戰鬥地圖的銜接
    combat_map: str | None = None  # MapManifest JSON 檔名（遭遇戰鬥時載入）

    # 狀態
    is_discovered: bool = True  # 玩家是否已知此節點
    is_visited: bool = False  # 玩家是否已到過

    # 城鎮專用：內含 POI 子節點
    pois: list[ExplorationNode] = Field(default_factory=list)

    # 敘事用
    ambient: str = ""  # 環境氛圍描述（聲音、氣味…）
    npcs: list[str] = Field(default_factory=list)  # 此處可遇到的 NPC id


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
    elapsed_minutes: int = 0  # 場景經過時間
    discovered_nodes: set[str] = Field(default_factory=set)
    discovered_edges: set[str] = Field(default_factory=set)

    # 子地圖堆疊：從世界→地城→房間，像 call stack
    map_stack: list[MapStackEntry] = Field(default_factory=list)
