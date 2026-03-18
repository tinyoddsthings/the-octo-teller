# T.O.T. GameSession 架構設計

> **來源**：整併自 `game-session-design.md` + `spatial-exploration-design.md` + `time-system-design.md` + `exploration-design.md`
> **日期**：2026-03-18

---

## 1. 分層架構

```
CLI (Textual TUI)  ──┐
                      ├──→ GameSession ──→ Bone Engine
Telegram Bot (未來) ──┘    (遊戲狀態機)    (規則計算)
```

**原則**：UI 層只負責「渲染事件」和「收集輸入」，不直接呼叫 Bone Engine。

### GameSession 職責

| 職責 | 說明 |
|------|------|
| 遊戲循環 | 驅動 探索→劇情→戰鬥 的主迴圈 |
| 狀態轉換 | 管理 GamePhase 轉換、進出各階段的 hook |
| 輸入收集 | 等待玩家輸入，轉為結構化 GameAction |
| 事件發送 | 輸出結構化 GameEvent，UI 層只負責渲染 |
| 存讀檔 | GameState 序列化/反序列化 |

### GameEvent 設計

UI 層不直接呼叫 Bone Engine，而是收到結構化事件後自行渲染：

```python
class GameEvent(BaseModel):
    type: EventType           # NARRATIVE, COMBAT_RESULT, MAP_UPDATE, STATUS_CHANGE, PROMPT...
    data: dict                # 事件內容（依 type 不同）
    requires_input: bool      # 是否需要等待玩家輸入
```

CLI 可以把 `COMBAT_RESULT` 渲染成彩色文字 + 表格；Telegram 可以渲染成 MarkdownV2 + inline keyboard。核心邏輯完全不變。

---

## 2. Game Phase 狀態機

### 三種遊戲模式

```
┌──────────┐    遭遇觸發    ┌──────────┐
│  探索模式  │──────────────→│  戰鬥模式  │
│Exploration│←──────────────│  Combat   │
└──────┬───┘   戰鬥結束     └──────────┘
       │
       │ 對話/劇情觸發
       ▼
┌──────────┐
│  劇情模式  │
│   Story   │
└──────┬───┘
       │ 劇情結束
       └──→ 回到探索
```

### 轉場規則

| 來源 | 觸發條件 | 目標 |
|------|---------|------|
| 探索 → 戰鬥 | 遭遇判定（節點/Area 觸發） | 戰鬥 |
| 探索 → 劇情 | NPC 對話 / 場景事件 | 劇情 |
| 戰鬥 → 探索 | 所有敵人消滅或撤退 | 探索 |
| 劇情 → 探索 | 對話結束 / 玩家離開 | 探索 |

### GamePhase 列舉

```python
class GamePhase(StrEnum):
    EXPLORATION = "exploration"  # 自由移動、搜索、互動
    STORY = "story"              # 對話、劇情事件、選擇
    COMBAT = "combat"            # D&D 5e 回合制戰鬥
```

---

## 3. 三層地圖階層

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

### 「當前地圖」定義

- **探索模式**：角色在 `MapState` 上自由移動，不受回合限制，時間隨行為流逝
- **戰鬥模式**：同一張 `MapState`，加入怪物 Actor，切換為 D&D 5e 回合制

---

## 4. 空間探索

### 現有架構 vs 目標架構

**現有（Pointcrawl-only）**：角色在探索階段只有節點 ID，沒有空間座標。

**目標（Spatial Exploration）**：ExplorationState 新增 `spatial_map: MapState | None` 和 `party_positions: dict[str, Position]`。

### 資料模型變更

```python
class ExplorationState(BaseModel):
    # ... 現有欄位 ...
    spatial_map: MapState | None = None           # 當前空間地圖
    party_positions: dict[str, Position] = Field(default_factory=dict)
```

`spatial_map` 與 `current_node_id` 保持同步：
- 進入節點 → 載入 `ExplorationNode.combat_map` → 建立 MapState
- 離開節點 → spatial_map 清除或替換

### Bone Engine 探索空間邏輯

```python
def enter_node_spatial(node, state, characters, spawn_zone_key="default") -> MapState:
    """載入 MapManifest → 建立 MapState → 放置角色 Actor。"""

def move_in_spatial(character, target, state, elapsed_minutes) -> MoveResult:
    """空間地圖上移動（非回合制），消耗時間。"""

def exit_spatial_to_node(state, next_node_id) -> None:
    """清除 spatial_map，準備進入下一節點。"""
```

### 碰撞系統複用

現有碰撞系統直接複用，無需改動：extract_static_obstacles / find_path_to_range / is_position_free / segment_aabb_intersect。

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

---

## 5. 時間系統

### 設計原則

1. **統一單位**：所有時間以**秒**為底層單位
2. **探索用現實時間**：玩家花多少現實時間探索，遊戲世界就過多少時間
3. **戰鬥用輪次**：每輪固定 +6 秒，且必須所有戰鬥者都行動完才算一輪
4. **效果用絕對到期秒數**：比對 `clock.total_seconds >= expires_at`

### GameClock 資料模型

```python
class GameClock(BaseModel):
    in_game_start_second: int = 28800  # Day 1 08:00
    accumulated_seconds: int = 0       # 顯式事件累積秒數

# Runtime（不序列化）
_explore_real_start: float | None      # 探索開始的 monotonic 時間戳
```

### 屬性與方法

```python
@property
def total_seconds(self) -> int:
    """目前遊戲世界的絕對秒數。"""
    real = int(time.monotonic() - self._explore_real_start) if self._explore_real_start else 0
    return self.in_game_start_second + self.accumulated_seconds + real
```

| 方法 | 呼叫時機 |
|------|---------|
| `start_exploration()` | 遊戲啟動 / 從戰鬥返回探索 |
| `pause_exploration()` | 進入戰鬥 / 執行耗時事件前 |
| `resume_exploration()` | 耗時事件結束後 |
| `add_combat_round()` | `round_number` 遞增時（+6秒） |
| `add_event(seconds)` | 開鎖、休息、儀式法術等 |

### 戰鬥中時鐘狀態

```
進入戰鬥 → game_clock.pause_exploration()   ← 現實時間停止
每輪結束 → game_clock.add_combat_round()    ← +6 秒
離開戰鬥 → game_clock.start_exploration()   ← 現實時間重新計時
```

### 效果到期系統

棄用 `remaining_rounds` 倒數，改為 `expires_at_second: int | None`（None = 永久）。

```python
def is_expired(effect_expires_at: int | None, clock: GameClock) -> bool:
    if effect_expires_at is None:
        return False
    return clock.total_seconds >= effect_expires_at
```

### 顯示格式

- **探索模式**：`format_seconds_human()` — 秒/分鐘/小時
- **戰鬥模式**：`format_seconds_rounds()` — ceil(remaining/6) 輪
- **遊戲世界**：`format_game_time()` — 第 N 天 HH:MM

### 預設耗時事件常數

```python
class TimeCost:
    COMBAT_ROUND = 6
    LOCKPICK = 60
    FORCE_DOOR = 6
    SEARCH_ROOM_DUNGEON = 600
    SEARCH_ROOM_TOWN = 3600
    SHORT_REST = 3600
    LONG_REST = 28800
    RITUAL_BASE = 600
```

### 與空間探索的整合

`GameClock` 作為 `ExplorationState` 的一部分（取代 `elapsed_minutes`），在探索與戰鬥之間傳遞。

### 時間消耗規則（探索模式）

| 行為 | 時間消耗 |
|------|---------|
| 移動 1.5m | ~6 秒 |
| 搜索房間 | 10 分鐘 |
| 開鎖 | 1 分鐘 |
| 短暫休息 | 1 小時 |
| 跨節點移動 | `ExplorationEdge.distance_minutes` |

### 影響範圍

| 檔案 | 變更 |
|------|------|
| `models/time.py` | `GameClock` 資料模型（新建） |
| `bone_engine/time_costs.py` | 耗時事件常數（新建） |
| `models/exploration.py` | `elapsed_minutes` → `game_clock: GameClock` |
| `models/map.py` | `SurfaceEffect.remaining_rounds` → `expires_at_second` |
| `models/creature.py` | `ActiveCondition.remaining_rounds` → `expires_at_second` |
| `bone_engine/combat.py` | `advance_turn()` 呼叫 `add_combat_round()` |
| `bone_engine/conditions.py` | `tick_conditions_end_of_turn()` 改為比對 `expires_at_second` |
| `bone_engine/exploration.py` | `elapsed_minutes +=` 改為 `game_clock.add_event()` |

---

## 6. 探索→戰鬥銜接

### 觸發條件

1. **我方突襲敵方**：角色移動至敵人感知範圍，Stealth vs 被動感知
2. **被敵方發現**：進入節點後，敵人被動感知 vs 我方被動感知

### 切換流程

```
[探索模式] 角色在 spatial_map 上自由移動
  │
  ▼ 遭遇觸發（bone_engine.exploration.prepare_combat_from_node）
  │
  ▼ 怪物 Actor 加入 state.spatial_map（使用 combat_map 的 spawn point）
  │
  ▼ Stealth vs Perception 判定 → EncounterResult
  │
  ▼ 建立 DeploymentState（角色已在地圖上，無需重新佈陣）
  │
  ▼ 建立 CombatState（initiative order）
  │
  ▼ 切換至 CombatTUI，傳入現有 MapState（角色位置保留）
```

**關鍵**：探索和戰鬥共用同一張 `MapState`，切換時角色位置完全保留。

### 戰鬥結束後

```
[戰鬥模式結束]
  → 怪物 Actor 移除（或 is_alive=False）
  → 回到 ExplorationTUI，spatial_map 不變
  → 角色繼續探索
```

---

## 7. 存讀檔

### 單一存檔槽 + 自動存檔

- 每次階段轉換時自動存檔（進入戰鬥、戰鬥結束、長休後）
- 存檔檔案：`~/.tot/saves/<adventure_name>.json`
- 序列化完整 GameState：角色隊伍、地圖狀態、探索進度、戰鬥狀態（若在戰鬥中）

---

## 8. 探索功能待辦

> 以下功能不阻擋 Phase A 遊玩，延後實作。

### 光照與視覺

```python
class LightLevel(StrEnum):
    BRIGHT = "bright"
    DIM = "dim"      # Perception (sight) 檢定劣勢
    DARK = "dark"    # 自動失敗視覺檢定（除非 Darkvision）
```

### 行進隊形

```python
class MarchingOrder(BaseModel):
    vanguard: list[str]    # 前衛（觸發陷阱）
    middle: list[str]
    rear_guard: list[str]  # 殿後（防偷襲）
```

### 旅行速度

```python
class TravelPace(StrEnum):
    FAST = "fast"      # 移動 ×0.67，被動感知 -5
    NORMAL = "normal"
    SLOW = "slow"      # 移動 ×1.33，可隱匿
```

### 其他延後項目

- **隨機遭遇**：danger_level 消費 + d20 擲骰
- **陷阱機制**：NodeTrap（Investigation 偵測、Thieves' Tools 解除）
- **時間壓力**：火把持續、法術持續、NPC 行程表
- **野外地形**：困難地形 ×2 移動、天氣效果、能見度

---

## 9. 已完成的探索功能摘要

### Pointcrawl 探索（Phase 1）
- ExplorationNode/Edge/Map/State 三層拓樸
- 子地圖堆疊（map_stack）

### Bone Engine 探索邏輯
- move_to_node / discover_hidden / unlock_edge / force_open_edge / search_room / prepare_combat_from_node
- skill_check / ability_check / passive_skill / best_passive_perception
- short_rest / long_rest

### NodeItem 可發現物品
- auto_passive_perception / search_items / take_item / get_visible_items
- list_pois / visit_poi / format_time

### Area 自由探索（2-XA）
- AreaExploreState / enter_area / exit_area / explore_move
- Prop Prefab 系統（structural/interactive/terrain）
- RenderBuffer → BrailleMapCanvas 渲染管線

### 背包 + 鑰匙/門（2-XE Stage 1-3）
- Prop is_locked/lock_dc/key_item
- loot_to_item / transfer_loot_to_inventory / unlock_area_prop

### 冒險劇本系統（2-XE）
- AdventureScript/State 資料模型
- 條件評估器 / 事件引擎 / 對話引擎
- Adventure Author（Markdown → JSON）
- 場景對話系統（scenes/*.md）
