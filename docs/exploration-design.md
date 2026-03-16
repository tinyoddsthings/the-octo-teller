# 探索系統設計文件

## 現有實作摘要

### Pointcrawl 模型（Phase 1）
- `models/exploration.py`：ExplorationNode、ExplorationEdge、ExplorationMap、ExplorationState
- 三層拓樸：dungeon（分鐘）/ town（小時）/ world（天）
- 子地圖堆疊（map_stack）支援世界→地城→房間

### Bone Engine 探索邏輯
- `bone_engine/exploration.py`：move_to_node、discover_hidden、unlock_edge、force_open_edge、search_room、prepare_combat_from_node
- `bone_engine/checks.py`：skill_check、ability_check、passive_skill、best_passive_perception
- `bone_engine/rest.py`：short_rest（自動 Hit Dice 分配）、long_rest（HP 全滿+法術恢復）

### 2-X 新增（本次實作）

#### NodeItem 可發現物品
```python
class NodeItem(BaseModel):
    id: str
    name: str
    description: str = ""
    item_type: str = "item"      # item / clue / chest / trap_hint
    investigation_dc: int = 0    # 0=明顯可見，>0 需主動搜索
    is_discovered: bool = False
    is_taken: bool = False
    value_gp: int = 0
    grants_key: str | None = None  # 拿取後獲得鑰匙 id
```

#### 新增 bone_engine 函式
- `auto_passive_perception()`：進入節點時自動檢查隱藏通道
- `search_items()`：搜索隱藏物品（check_total vs investigation_dc）
- `take_item()`：拿取已發現物品
- `get_visible_items()`：回傳明顯可見+已發現物品
- `list_pois()` / `visit_poi()`：POI 互動
- `format_time()`：分鐘數格式化

#### 探索 TUI
- 獨立 `ExplorationTUI` App（與 CombatTUI 分離）
- 四面板：地圖 / 狀態 / 紀錄 / 輸入
- ExplorePhase 狀態機：MAIN / MOVE_SELECT / DOOR_ACTION / CHARACTER_SELECT / POI_SELECT / REST_SELECT / TAKE_SELECT
- 角色選擇選單（每次檢定讓玩家選人）
- 噪音追蹤（noise_alert，為戰鬥銜接鋪路）
- 鑰匙系統（NodeItem.grants_key → collected_keys → unlock_edge）

#### 測試地圖
- `tutorial_dungeon.json`：3 節點 + 物品（火把/鑰匙/符文碎片/武器架/皮包）
- `wilderness_trail.json`：5 節點野外地圖（林道→岔路→溪谷→營地→洞穴）
- `starter_town.json`：城鎮 POI（酒館/鐵匠鋪/神殿）

### 2-XA Area 自由探索
- `models/exploration.py`：AreaExploreState（map_state/party/speed/discovered/looted/collected）
- `bone_engine/area_explore.py`：enter_area/exit_area/explore_move/reset_movement/search_prop/take_prop_loot/check_terrain_at/get_nearby_props/get_party_position
- Prop Prefab 系統：structural/interactive/terrain 三類 prefab
- RenderBuffer → BrailleMapCanvas 渲染管線

### 2-XE 背包 + 鑰匙/門（Stage 1-3）
- `models/map.py` Prop 新增 `is_locked/lock_dc/key_item` 鎖定欄位
- `models/exploration.py` AreaExploreState 新增 `collected_keys` 鑰匙追蹤
- `bone_engine/area_explore.py` 新增函式：
  - `loot_to_item()`：LootEntry → Item 轉換
  - `transfer_loot_to_inventory()`：離開 Area 時物品轉入 Character.inventory
  - `unlock_area_prop()`：Area 門開鎖（鑰匙 / 檢定）
  - `get_nearby_doors()`：取得附近門 Prop
  - `take_prop_loot()` 改動：自動註冊 grants_key 到 collected_keys
- TUI `explore_input.py` 新增：
  - `AREA_USE_PROP/AREA_USE_ACTION/AREA_USE_CHAR` 三階段 use 指令
  - `_exit_area_mode()` 離開時同步鑰匙 + 轉移背包
- Prefab：`iron_gate_locked` 預設 `is_locked=True, interactable=True`

---

## 延後功能設計規格

### 1. 光照與視覺
**D&D 規則依據**：PHB Ch.8 Light & Vision — Bright/Dim/Dark 光照等級，Darkvision 在黑暗中視為昏暗。

**資料模型草案**：
```python
class LightLevel(StrEnum):
    BRIGHT = "bright"
    DIM = "dim"
    DARK = "dark"

# ExplorationNode 新增欄位
light_level: LightLevel = LightLevel.BRIGHT
```

**機制**：
- Dim Light → Perception (sight) 檢定劣勢
- Dark → 自動失敗視覺相關檢定（除非 Darkvision）
- Darkvision：黑暗視為昏暗，昏暗視為明亮

### 2. 行進隊形
**D&D 規則依據**：PHB Ch.8 Marching Order — 前衛最先觸發陷阱，殿後對抗偷襲。

**資料模型草案**：
```python
class MarchingOrder(BaseModel):
    vanguard: list[str]    # 前衛角色 id（觸發陷阱）
    middle: list[str]      # 中間
    rear_guard: list[str]  # 殿後（防偷襲）
```

**機制**：
- 陷阱觸發→前衛角色做 DEX 豁免
- 伏擊→殿後角色做 Perception 檢定

### 3. 旅行速度
**D&D 規則依據**：PHB Ch.8 Travel Pace — Fast(-5 Perception)/Normal/Slow(可隱匿)。

**資料模型草案**：
```python
class TravelPace(StrEnum):
    FAST = "fast"      # 被動感知 -5
    NORMAL = "normal"
    SLOW = "slow"      # 可使用 Stealth
```

**機制**：
- Fast：移動時間 ×0.67，被動感知 -5
- Slow：移動時間 ×1.33，可擲 Stealth 避免遭遇

### 4. 隨機遭遇
**D&D 規則依據**：DMG Ch.3 Random Encounters — 依 danger_level 決定頻率。

**機制**：
- 移動時消費 `danger_level`
- 每段路徑擲 d20，低於 danger_level → 觸發遭遇
- 遭遇表依地圖 scale 和地形類型分類

### 5. 陷阱機制
**D&D 規則依據**：DMG Ch.3 Traps — Investigation 偵測、Thieves' Tools 解除。

**資料模型草案**：
```python
class NodeTrap(BaseModel):
    id: str
    name: str
    detection_dc: int     # Investigation DC
    disarm_dc: int        # Thieves' Tools DC
    damage_dice: str      # 觸發時傷害
    damage_type: DamageType
    save_dc: int          # DEX 豁免
    save_ability: Ability = Ability.DEX
    is_detected: bool = False
    is_disarmed: bool = False
    is_triggered: bool = False
```

### 6. 時間壓力
**機制**：
- 火把持續 1 小時（60 分鐘）
- 法術持續時間隨 elapsed_minutes 遞減
- NPC 行程表（在特定時間出現/離開）

### 7. 探索→戰鬥切換
**現有支援**：`prepare_combat_from_node()` 已可載入戰鬥地圖。

**待實作**：
- 進入有 NPC 的節點 → 遭遇判定
- Stealth vs Perception → EncounterType
- 啟動佈陣（DeploymentState）
- 切到 CombatTUI 子程序
- 戰鬥結束後回到 ExplorationTUI

### 8. 野外地形效果
**機制**：
- 困難地形：移動時間 ×2
- 天氣效果：暴風雨 → Perception 劣勢、雪 → 追蹤優勢
- 能見度：霧 → 視線範圍縮短
