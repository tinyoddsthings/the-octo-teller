# 空間探索系統設計文件

## 概覽

本文件描述將探索模式從純 Pointcrawl 拓樸升級為**空間探索**的架構設計。
升級後探索與戰鬥共用同一張 `MapState`，`BrailleMapCanvas` 在兩種模式下均渲染當前地圖。

---

## 三層地圖階層

```
世界地圖拓樸（WorldMap）
  └── 地城 / 城鎮拓樸（ExplorationMap，Pointcrawl）
        └── 當前地圖（MapState，有物理碰撞）
              ├── 探索模式：自由移動，時間流逝
              └── 戰鬥模式：同一張 MapState，切換為回合制
```

### 各層職責

| 層級 | 模型 | 功能 |
|------|------|------|
| 世界地圖 | `ExplorationMap`（scale=WORLD） | 記錄目前在哪個地城或城鎮 |
| 地城拓樸 | `ExplorationMap`（scale=DUNGEON） | Pointcrawl 節點圖，記錄哪些房間已探索 |
| 當前地圖 | `MapState` + `MapManifest` | 角色的物理位置、碰撞、渲染 |

---

## 「當前地圖」定義

**當前地圖**指任何有物理碰撞系統運作的空間地圖，對應一個 `MapState`。

- **探索模式**：角色在 `MapState` 上自由移動，不受回合限制，時間隨行為流逝
- **戰鬥模式**：同一張 `MapState`，加入怪物 Actor，切換為 D&D 5e 回合制

兩種模式之間的切換由**遭遇判定**觸發（見下方）。

---

## 現有架構 vs 目標架構

### 現有（Pointcrawl-only）

```
ExplorationTUI
  ├── ExploreMapWidget      ← ASCII 節點拓樸圖
  ├── ExploreStatusWidget   ← 角色狀態列
  ├── RichLog               ← 事件記錄
  └── Input                 ← 指令輸入

ExplorationState
  ├── current_map_id
  ├── current_node_id
  ├── elapsed_minutes
  ├── discovered_nodes / discovered_edges
  └── map_stack
```

角色在探索階段**只有節點 ID**，沒有空間座標。

### 目標（Spatial Exploration）

```
ExplorationTUI
  ├── BrailleMapCanvas      ← 當前地圖（空間地圖，與 CombatTUI 共用）
  ├── ExploreMapWidget      ← 地城拓樸圖（縮小，顯示目前在哪個節點）
  ├── ExploreStatusWidget   ← 角色狀態列
  ├── RichLog               ← 事件記錄
  └── Input                 ← 指令輸入

ExplorationState（新增欄位）
  ├── current_map_id
  ├── current_node_id
  ├── elapsed_minutes
  ├── discovered_nodes / discovered_edges
  ├── map_stack
  ├── spatial_map: MapState | None      ← 新增：當前空間地圖
  └── party_positions: dict[UUID, Position]  ← 新增：角色空間座標
```

---

## 資料模型變更

### `ExplorationState`（`models/exploration.py`）

新增兩個欄位：

```python
class ExplorationState(BaseModel):
    # ... 現有欄位 ...

    # 當前空間地圖（None = 尚未進入任何房間）
    spatial_map: MapState | None = None

    # 角色在空間地圖上的位置（key = Character.id）
    party_positions: dict[str, Position] = Field(default_factory=dict)
```

`spatial_map` 與 `current_node_id` 保持同步：
- 進入節點 → 載入 `ExplorationNode.combat_map` → 建立 `MapState`，角色從 spawn point 出現
- 離開節點（移動至其他節點）→ `spatial_map` 清除或替換為新節點的地圖

### `ExplorationNode`（現有，無需改動）

`combat_map: str | None` 已指向 MapManifest JSON 路徑，直接複用。

---

## Bone Engine 探索邏輯新增

### `bone_engine/exploration.py` 新增函式

```python
def enter_node_spatial(
    node: ExplorationNode,
    state: ExplorationState,
    characters: list[Character],
    spawn_zone_key: str = "default",
) -> MapState:
    """載入節點對應的 MapManifest，建立 MapState，
    在 spawn point 放置角色 Actor，更新 state.spatial_map。"""

def move_in_spatial(
    character: Character,
    target: Position,
    state: ExplorationState,
    elapsed_minutes: float,
) -> MoveResult:
    """在空間地圖上移動（非回合制）。
    使用 pathfinding.find_path_to_range，消耗時間。"""

def exit_spatial_to_node(
    state: ExplorationState,
    next_node_id: str,
) -> None:
    """清除 spatial_map，準備進入下一個節點。"""
```

### 時間消耗規則

探索模式中，時間流逝由行為決定：

| 行為 | 時間消耗 |
|------|---------|
| 移動 1.5m（1 格） | ~6 秒（0.1 分鐘） |
| 搜索房間 | 10 分鐘 |
| 開鎖 | 1 分鐘 |
| 短暫休息 | 1 小時（60 分鐘） |
| 跨節點移動 | `ExplorationEdge.distance_minutes` |

---

## 碰撞系統在探索模式中的應用

現有碰撞系統（`geometry.py`、`pathfinding.py`、`spatial.py`）**直接複用**，無需改動：

| 功能 | 探索模式用途 |
|------|------------|
| `extract_static_obstacles()` | 行走路線避開牆壁和阻擋物 |
| `find_path_to_range()` | 角色自由移動的 A* 路徑 |
| `is_position_free()` | 驗證移動目標是否合法 |
| `segment_aabb_intersect()` | 視線判定（如：能否看到某物件） |

---

## BrailleMapCanvas 整合

### 探索模式渲染

`BrailleMapCanvas` 接收 `state.spatial_map`（`MapState`），渲染：

- 牆壁（AABB 填滿）
- Props（阻擋物填滿，非阻擋物外框）
- 角色 Actor（圓形符號，僅角色，無怪物）
- 刻度線（1.5m 格線）

探索模式**不顯示 AoE overlay**（戰鬥專用）。

### ExplorationTUI 佈局

```
┌─────────────────────────────┬──────────────┐
│                             │              │
│   BrailleMapCanvas          │ ExploreMap   │
│   （當前空間地圖）           │ Widget       │
│                             │ （拓樸圖）   │
├─────────────────────────────┤              │
│   ExploreStatusWidget       │              │
├─────────────────────────────┴──────────────┤
│   RichLog                                  │
├────────────────────────────────────────────┤
│   Input                                    │
└────────────────────────────────────────────┘
```

左側大面板：BrailleMapCanvas（當前空間地圖）
右上：ExploreMapWidget（地城拓樸，縮小為輔助視圖）

---

## 探索→戰鬥切換

### 觸發條件

1. **我方突襲敵方**：角色移動至敵人感知範圍，Stealth vs 敵人被動感知
2. **被敵方發現**：進入節點後，敵人被動感知 vs 我方被動感知

### 切換流程

```
[探索模式] 角色在 spatial_map 上自由移動
  │
  ▼ 遭遇觸發（bone_engine.exploration.prepare_combat_from_node）
  │
  ▼ 怪物 Actor 加入 state.spatial_map（使用 combat_map 的 spawn point）
  │
  ▼ 執行 Stealth vs Perception 判定 → EncounterResult
  │
  ▼ 建立 DeploymentState（角色已在地圖上，無需重新佈陣）
  │
  ▼ 建立 CombatState（initiative order）
  │
  ▼ 切換至 CombatTUI，傳入現有 MapState（角色位置保留）
```

**關鍵**：因為探索和戰鬥共用同一張 `MapState`，切換時角色位置**完全保留**，不需要重新佈陣。

### 戰鬥結束後回到探索

```
[戰鬥模式結束]
  │
  ▼ 怪物 Actor 從 MapState 移除（或標記為 is_alive=False）
  │
  ▼ 回到 ExplorationTUI，state.spatial_map 仍是同一張地圖
  │
  ▼ 角色繼續探索
```

---

## 實作階段規劃

### Phase A：資料模型擴充

- [ ] `ExplorationState` 新增 `spatial_map` 和 `party_positions`
- [ ] 確保 Pydantic 序列化正確（`MapState` 含 `MapManifest`）

### Phase B：Bone Engine 探索空間邏輯

- [ ] `enter_node_spatial()`：載入 MapManifest → 建立 MapState → 放置角色
- [ ] `move_in_spatial()`：A* 路徑 → 更新位置 → 消耗時間
- [ ] `exit_spatial_to_node()`：清除 spatial_map

### Phase C：ExplorationTUI 佈局更新

- [ ] 加入 `BrailleMapCanvas`（`id="explore-spatial-map"`）
- [ ] 更新 `_refresh_all()` 同步 `spatial_map` 到 canvas
- [ ] 更新 TCSS 佈局（左大右小的雙面板）
- [ ] 探索模式移動指令接 `move_in_spatial()`

### Phase D：探索→戰鬥切換

- [ ] 遭遇判定整合（Stealth vs Perception）
- [ ] 怪物 Actor 注入 `spatial_map`
- [ ] 建立 `CombatState` 並啟動 `CombatTUI`
- [ ] 戰鬥結束後回到 `ExplorationTUI`

---

## 尚未設計的部分（延後）

- 探索模式的霧戰（Fog of War）：角色視線範圍 vs 未探索區域
- 燈光系統（LightLevel）對可見度影響
- 行進隊形（MarchingOrder）
- 隨機遭遇（危險等級擲骰）

這些功能待空間探索基礎建立後，依 `exploration-design.md` 中的設計規格實作。
