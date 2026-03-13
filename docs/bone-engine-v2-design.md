# Bone Engine V2 — 遊戲引擎架構重建設計文件

> **版本**：v1.2（BoundingShape 擴充 CONE/LINE 有方向形狀，統一 AoE 幾何）
> **日期**：2026-03-12
> **對應 todo.md**：Phase 2-V

## 1. 背景與目標

Bone Engine 目前是扁平的戰鬥引擎：2D 空間、無事件系統、無地形高度、無可摧毀物件、無表面效果。
為支援開放世界、多層地形、動態掩護等 D&D 2024 規則，需要從底層重建核心架構。

**目標**：建立事件驅動的遊戲狀態管理器，支援 Z 軸、表面效果、可摧毀物件、射線掩護。

**原則**：
- 向後相容：所有新欄位有預設值，既有地圖 JSON 不需修改
- 漸進式遷移：新系統包裝既有函式，一次只改一個 action function
- bone_engine/ 絕不 import tui/

---

## 2. 相依圖

```
Phase A (基礎) ────────────────────┐
    │       │       │       │      │
    ▼       ▼       ▼       ▼      │
Phase B  Phase C  Phase D  Phase E │
(表面)   (Z軸)   (掩護)   (Size)  │
    │       │       │       │      │
    └───────┴───────┴───────┘      │
                │                  │
                ▼                  │
            Phase F ◄──────────────┘
        (GameStateManager)
```

B/C/D/E 互相獨立，Phase A 之後可任意順序或並行。Phase F 收束所有。

---

## 3. 事件型別總覽

所有事件繼承 `GameEvent`，由 `EventBus.emit()` 同步派發。
`SystemLog` 記錄全部事件，`NarrativeLog` 只訂閱需要敘事的子集。

### 3.1 GameEvent 基底

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `timestamp` | `float` | `time.monotonic()` | 事件發生時間（單調遞增） |
| `source_entity_id` | `str \| None` | `None` | 觸發事件的實體 ID |

### 3.2 移動類事件

#### EntityMoveEvent

實體完成移動時 emit。觸發時機：`GameStateManager.move_actor()` 成功後。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 移動的 Actor.id |
| `from_x`, `from_y`, `from_z` | `float` | 移動前座標（公尺） |
| `to_x`, `to_y`, `to_z` | `float` | 移動後座標（公尺） |
| `speed_cost` | `float` | 消耗的移動速度（公尺） |

#### EnterRangeEvent

進入另一實體的特定距離範圍時 emit（用於借機攻擊偵測、光環觸發等）。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 移動中的實體 |
| `other_id` | `str` | 被接近的實體 |
| `range_m` | `float` | 觸發距離（公尺） |

#### LeaveRangeEvent

離開另一實體的特定距離範圍時 emit（借機攻擊的主要觸發點）。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 移動中的實體 |
| `other_id` | `str` | 被離開的實體 |
| `range_m` | `float` | 觸發距離（公尺） |

### 3.3 傷害與治療類事件

#### DamageEvent

對生物造成傷害時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `target_id` | `str` | 受傷者 Actor.id |
| `amount` | `int` | 傷害量（套用抗性/免疫後） |
| `damage_type` | `DamageType` | 傷害類型 |
| `source_id` | `str \| None` | 傷害來源（攻擊者/表面效果） |
| `is_critical` | `bool` | 是否暴擊 |

#### HealEvent

治療生物時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `target_id` | `str` | 被治療者 Actor.id |
| `amount` | `int` | 治療量 |
| `source_id` | `str \| None` | 治療來源 |

### 3.4 狀態類事件

#### StatusChangeEvent

狀態施加、移除或過期時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 受影響實體 |
| `condition` | `Condition` | 狀態類型 |
| `action` | `str` | `"applied"` / `"removed"` / `"expired"` |

### 3.5 掩護類事件

#### CoverChangeEvent

掩護關係變更時 emit（通常是掩護物件被摧毀後）。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `observer_id` | `str` | 觀察者（攻擊者） |
| `target_id` | `str` | 被觀察者（防禦者） |
| `old_cover` | `CoverType` | 變更前掩護等級 |
| `new_cover` | `CoverType` | 變更後掩護等級 |

### 3.6 表面效果類事件

#### SurfaceEffectEvent

實體觸發表面效果（進入/停留/離開）時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 觸發者 |
| `surface_id` | `str` | 表面效果 ID |
| `trigger` | `str` | `"enter"` / `"stay"` / `"leave"` |

### 3.7 物件傷害類事件

#### ObjectDamagedEvent

可摧毀物件受傷時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `object_id` | `str` | 受傷的 Prop.id |
| `damage` | `int` | 傷害量 |
| `damage_type` | `DamageType` | 傷害類型 |
| `hp_remaining` | `int` | 剩餘 HP |

#### ObjectDestroyedEvent

可摧毀物件 HP 歸零時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `object_id` | `str` | 被摧毀的 Prop.id |
| `destroyed_by` | `str \| None` | 摧毀者 ID |

### 3.8 掉落類事件

#### FallingEvent

實體從高處掉落時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 掉落者 |
| `height_m` | `float` | 掉落高度（公尺） |
| `damage_dice` | `str` | 傷害骰（如 `"3d6"`） |
| `feather_fall` | `bool` | 是否有羽落術保護 |

### 3.9 投射物類事件

#### ProjectileHitCoverEvent

遠程攻擊 miss 後命中掩護物件時 emit。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `attacker_id` | `str` | 射擊者 |
| `cover_object_id` | `str` | 被命中的掩護 Prop.id |
| `damage` | `int` | 投射物造成的傷害 |

### 3.10 事件訂閱矩陣

| 事件類型 | SystemLog | NarrativeLog | GameStateManager 內部 |
|----------|:---------:|:------------:|:--------------------:|
| EntityMoveEvent | ✓ | ✓ | 觸發 surface enter/leave |
| EnterRangeEvent | ✓ | | |
| LeaveRangeEvent | ✓ | | |
| DamageEvent | ✓ | ✓ | |
| HealEvent | ✓ | ✓ | |
| StatusChangeEvent | ✓ | ✓ | |
| CoverChangeEvent | ✓ | | |
| SurfaceEffectEvent | ✓ | ✓ | |
| ObjectDamagedEvent | ✓ | | |
| ObjectDestroyedEvent | ✓ | ✓ | 觸發 CoverChangeEvent |
| FallingEvent | ✓ | ✓ | |
| ProjectileHitCoverEvent | ✓ | ✓ | 觸發 ObjectDamagedEvent |

### 3.11 典型事件鏈

```
移動進入火焰區域：
  EntityMoveEvent → SurfaceEffectEvent(enter) → DamageEvent

遠程攻擊打掩護：
  [attack miss] → ProjectileHitCoverEvent → ObjectDamagedEvent
                → ObjectDestroyedEvent → CoverChangeEvent

掉落：
  FallingEvent → DamageEvent → (若 0 HP) StatusChangeEvent(Unconscious)
```

---

## 4. 資料結構變更總覽

### 4.1 修改的既有類別

#### Position（`models.py`）

| 欄位 | 變更 | 型別 | 預設值 | 說明 |
|------|------|------|--------|------|
| `z` | **新增** | `float` | `0.0` | 高度（公尺），高於地面 |

| 方法 | 變更 | 說明 |
|------|------|------|
| `distance_to()` | **不變** | 維持 2D Euclidean（不破壞現有呼叫） |
| `distance_3d()` | **新增** | 3D Euclidean 距離 |
| `height_diff()` | **新增** | `abs(self.z - other.z)` |

> **設計決策**：`distance_to` 維持 2D。D&D 中水平移動距離和高度差是分開計算的（水平 = 速度消耗，垂直 = 跳/爬），且現有上百處呼叫全部假設 2D。

#### TerrainTile（`models.py`）

| 欄位 | 變更 | 型別 | 預設值 | 說明 |
|------|------|------|--------|------|
| `height_m` | **新增** | `float` | `0.0` | 此格地面高度（公尺） |
| `tile_type` | **新增** | `TileType` | `FLOOR` | 地格類型 |

#### Actor（`models.py`）

| 欄位 | 變更 | 型別 | 預設值 | 說明 |
|------|------|------|--------|------|
| `size` | **新增** | `Size` | `Size.MEDIUM` | 從 Character/Monster 同步 |
| `z` | **新增** | `float` | `0.0` | 當前高度（公尺） |
| `bounds` | **新增** | `BoundingShape` | `BoundingShape.from_size(Size.MEDIUM)` | 碰撞幾何（從 size 生成圓形） |

#### Prop（`models.py`）

| 欄位 | 變更 | 型別 | 預設值 | 說明 |
|------|------|------|--------|------|
| `material` | **新增** | `Material \| None` | `None` | 材質（None = 不可摧毀） |
| `fragility` | **新增** | `Fragility` | `RESILIENT` | 堅固程度（HP 倍數） |
| `object_size` | **新增** | `Size` | `MEDIUM` | 物件尺寸（決定 HP 骰） |
| `hp_max` | **新增** | `int` | `0` | 最大 HP（0 = 不可摧毀） |
| `hp_current` | **新增** | `int` | `0` | 目前 HP |
| `object_ac` | **新增** | `int` | `15` | 物件 AC（由 material 查表） |
| `damage_immunities` | **新增** | `list[DamageType]` | `[]` | 傷害免疫類型 |
| `damage_threshold` | **新增** | `int` | `0` | 傷害門檻（低於此值無效） |
| `bounds` | **新增** | `BoundingShape \| None` | `None` | 碰撞幾何（None = 沿用 grid-snap AABB） |

> **設計決策**：不另開 DestructibleObject 子類，直接在 Prop 加欄位。
> - 所有現有 Prop 的新欄位全部有合理預設值（None/0）
> - 地圖 JSON `props` 陣列不用改結構
> - `material is None or hp_max == 0` → 不可摧毀

#### MapState（`models.py`）

| 欄位 | 變更 | 型別 | 預設值 | 說明 |
|------|------|------|--------|------|
| `surfaces` | **新增** | `list[SurfaceEffect]` | `[]` | 場上表面效果 |

### 4.2 新增的列舉

#### TileType（`models.py`）

```python
class TileType(StrEnum):
    FLOOR = "floor"
    WALL = "wall"       # 不可摧毀，永遠 blocking
```

#### Material（`models.py`）

D&D 2024 DMG 物件材質，決定物件 AC。

| 成員 | AC |
|------|-----|
| `CLOTH`, `PAPER`, `ROPE` | 11 |
| `CRYSTAL`, `GLASS`, `ICE` | 13 |
| `WOOD`, `BONE` | 15 |
| `STONE` | 17 |
| `IRON`, `STEEL` | 19 |
| `MITHRAL` | 21 |
| `ADAMANTINE` | 23 |

#### Fragility（`models.py`）

| 成員 | HP 倍數 | 說明 |
|------|---------|------|
| `FRAGILE` | ×1 | 易碎 |
| `RESILIENT` | ×2 | 堅固（預設） |

#### ShapeType（`models.py`）

通用幾何形狀類型（供 `BoundingShape` 使用）。

| 成員 | 方向性 | 說明 |
|------|--------|------|
| `CIRCLE` | 無 | 圓形（碰撞 + SurfaceEffect + AoE sphere） |
| `RECTANGLE` | 無 | 矩形（碰撞 + SurfaceEffect + AoE cube） |
| `CONE` | **水平方向** | 錐形（AoE cone、未來視野錐）— 需 `direction_deg` |
| `LINE` | **水平方向** | 線段（AoE line，零寬度）— 需 `direction_deg` |
| `CYLINDER` | **垂直** | 圓柱（AoE cylinder，如月光術）— 2D 投影 = CIRCLE，Z 軸有高度 |

> **方向性區分**：
> - CIRCLE/RECTANGLE/CYLINDER：無水平方向（centroid-based），用於碰撞和靜態效果
> - CONE/LINE：有水平方向（需 `direction_deg`），用於 AoE、視野、方向性 SurfaceEffect
> - CYLINDER：垂直方向由 `height_m` 正負決定（正=向上、負=向下），2D contains_point 等同 CIRCLE
>
> **LINE 是純線段**：幾何上寬度為零，命中判定靠「LINE 線段是否穿過目標的碰撞圓」（line-circle intersection），不靠 contains_point。

#### SurfaceTrigger（`models.py`）

| 成員 | 說明 |
|------|------|
| `ENTER` | 進入時觸發 |
| `STAY` | 回合開始停留時觸發 |
| `LEAVE` | 離開時觸發 |

### 4.3 新增的資料模型

#### BoundingShape（`models.py`）

通用碰撞/範圍幾何。可嵌入 SurfaceEffect（效果區域）、Prop（物件體積）、Actor（生物佔據空間）。
座標系統：以持有者的 (x, y) 為中心。

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `shape_type` | `ShapeType` | `CIRCLE` | 形狀類型 |
| `radius_m` | `float` | `0.0` | 圓形/CYLINDER 半徑（公尺） |
| `half_width_m` | `float` | `0.0` | 矩形 X 方向半寬 |
| `half_height_m` | `float` | `0.0` | 矩形 Y 方向半高 |
| `direction_deg` | `float \| None` | `None` | 水平朝向角度（度，0=+Y 北，順時針）。None = 無方向。CONE/LINE 使用 |
| `angle_deg` | `float` | `53.0` | CONE 全角（D&D 標準 ≈ 53°，半角 26.57°） |
| `length_m` | `float` | `0.0` | CONE/LINE 長度（從頂點/起點延伸） |
| `height_m` | `float` | `0.0` | CYLINDER 垂直高度（正=向上、負=向下，0=2D 模式） |

方法：
- `contains_point(cx, cy, px, py) -> bool`：點 (px, py) 是否在以 (cx, cy) 為中心的此形狀內
  - CONE：dir = (sin(rad), cos(rad))；dot-product 角度 + dist ≤ length_m
  - LINE：點到線段的垂直距離 < ε（~0.01m），實務上 LINE AoE 用 `intersects_line` 判定命中
  - CYLINDER：等同 CIRCLE（Z 軸高度檢查在 GameStateManager 層做）
- `overlaps(cx, cy, other, ox, oy) -> bool`：兩個 BoundingShape 是否重疊（碰撞判定核心）
  - CONE/LINE/CYLINDER 不支援（raise NotImplementedError）— 碰撞不用方向/柱形狀
- `to_aabb(cx, cy) -> AABB`：轉為軸對齊 AABB（供 Minkowski inflation / extract_static_obstacles）
  - CONE/LINE = 保守正方形（半徑=length_m）；CYLINDER = 同 CIRCLE
- `intersects_line(cx, cy, target_bounds, tx, ty) -> bool`：**LINE 專用**命中判定 — 此 LINE 線段是否穿過 target 的碰撞圓（line-circle intersection）

工廠方法：
- `BoundingShape.circle(radius_m)` → 圓形
- `BoundingShape.rect(width_m, height_m)` → 矩形
- `BoundingShape.from_size(size: Size)` → 從 D&D 體型查 `SIZE_RADIUS_M` 生成碰撞圓
- `BoundingShape.cone(length_m, direction_deg, angle_deg=53.0)` → 錐形（AoE cone、視野）
- `BoundingShape.line(length_m, direction_deg)` → 零寬度線段（AoE line）
- `BoundingShape.cylinder(radius_m, height_m)` → 圓柱（2D = circle，高度待 Z 軸用）

#### AoE 統一遷移策略

`AoeShape` → `ShapeType` 對照：

| AoeShape | ShapeType | BoundingShape 欄位 | 備註 |
|----------|-----------|-------------------|------|
| `SPHERE` | `CIRCLE` | `radius_m` | 直接對應 |
| `CONE` | `CONE` | `length_m` + `direction_deg` | 方向由目標點算出 |
| `LINE` | `LINE` | `length_m` + `direction_deg`（零寬度） | 命中用 `intersects_line` |
| `CUBE` | `RECTANGLE` + `direction_deg` | 延後處理 | 僅雷鳴波使用 |
| （無） | `CYLINDER` | `radius_m` + `height_m` | 如月光術/精神尖嘯 |

遷移順序：
1. **現在**：設計文件定義 CONE/LINE/CYLINDER（本節）
2. **Phase A-3 實作**：`models.py` 含完整 BoundingShape（5 種 ShapeType）
3. **之後**：`Spell.to_bounding_shape()` 做 ft→m + direction 轉換
4. **重構**：`aoe.py` 內部改用 `BoundingShape.contains_point()`
5. **最終**：deprecate `AoeShape` enum

#### SurfaceEffect（`models.py`）

場上的持續效果區域（如火牆、糾纏藤蔓）。

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `id` | `str` | — | 唯一識別碼 |
| `name` | `str` | — | 顯示名稱（如「火焰區域」） |
| `bounds` | `BoundingShape` | — | 效果區域幾何 |
| `center_x`, `center_y` | `float` | — | 中心座標（公尺） |
| `center_z` | `float` | `0.0` | 中心高度 |
| `damage_dice` | `str` | `""` | 傷害骰（如 `"2d6"`） |
| `damage_type` | `DamageType \| None` | `None` | 傷害類型 |
| `save_dc` | `int` | `0` | 豁免 DC（0 = 不需豁免） |
| `save_ability` | `Ability \| None` | `None` | 豁免屬性 |
| `save_half` | `bool` | `False` | 豁免成功是否半傷 |
| `applies_condition` | `Condition \| None` | `None` | 施加的狀態 |
| `is_difficult_terrain` | `bool` | `False` | 是否為困難地形 |
| `triggers` | `list[SurfaceTrigger]` | `[ENTER]` | 觸發時機 |
| `remaining_rounds` | `int \| None` | `None` | 剩餘回合（None = 永久） |
| `source_id` | `str \| None` | `None` | 創建者 ID |

方法：
- `contains_point(x, y) -> bool`：委託 `self.bounds.contains_point(self.center_x, self.center_y, x, y)`

#### CoverResult（`models.py`）

掩護查詢的完整結果（取代原本的純 `CoverType` 回傳）。

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `cover_type` | `CoverType` | — | 掩護等級 |
| `cover_objects` | `list[str]` | `[]` | 提供掩護的 Prop.id 列表 |
| `primary_cover_id` | `str \| None` | `None` | 最大掩護來源的 Prop.id |

#### OBJECT_HP_DICE（`models.py`，常數）

| Size | HP 骰 |
|------|--------|
| `TINY` | `1d4` |
| `SMALL` | `3d6` |
| `MEDIUM` | `4d6` |
| `LARGE` | `5d6` |

### 4.4 向後相容性驗證

| 類別 | 新欄位數 | 全部有預設值 | 既有 JSON 相容 |
|------|---------|:----------:|:------------:|
| Position | 1 (`z`) | ✓ | ✓ |
| TerrainTile | 2 | ✓ | ✓ |
| Actor | 3 (`size`, `z`, `bounds`) | ✓ | ✓ |
| Prop | 9 (+`bounds`) | ✓ | ✓ |
| MapState | 1 (`surfaces`) | ✓ | ✓ |

所有新欄位的預設值代表「V1 行為」：z=0 平面、不可摧毀、無表面效果。
既有地圖 JSON 載入時自動套用預設值，**零修改即可運作**。

### 4.5 API 變更

| 函式 | 變更 | 遷移方式 |
|------|------|---------|
| `determine_cover_from_grid()` | 改名為 `determine_cover()`，回傳型別 `CoverType` → `CoverResult` | 呼叫端改用 `.cover_type`（共 2 處） |
| `move_entity()` | 新增 `tz: float \| None = None` 參數 | 不傳 = 忽略高度（V1 行為） |
| `place_actors_at_spawn()` | Actor 新增 `size` 欄位設定 | 自動從 Character/Monster 同步 |

---

## 5. Phase A：基礎建設 — 事件系統 + 資料模型擴充

### A-1：事件系統 `bone_engine/events.py`（新建，~200 行）

事件系統是整個 V2 架構的脊樑。所有狀態變更都透過事件傳遞，
解耦「規則引擎」與「渲染/Log/AI」。

```python
import time
from collections.abc import Callable
from pydantic import BaseModel, Field
from tot.models import CoverType, Condition, DamageType


class GameEvent(BaseModel):
    """不可變事件基底。所有事件都繼承此類。"""
    timestamp: float = Field(default_factory=time.monotonic)
    source_entity_id: str | None = None


# --- 移動 ---

class EntityMoveEvent(GameEvent):
    """實體移動事件。"""
    entity_id: str
    from_x: float
    from_y: float
    from_z: float = 0.0
    to_x: float
    to_y: float
    to_z: float = 0.0
    speed_cost: float = 0.0


class EnterRangeEvent(GameEvent):
    """進入某實體觸及範圍。"""
    entity_id: str
    other_id: str
    range_m: float


class LeaveRangeEvent(GameEvent):
    """離開某實體觸及範圍。"""
    entity_id: str
    other_id: str
    range_m: float


# --- 傷害與治療 ---

class DamageEvent(GameEvent):
    """傷害事件（對生物）。"""
    target_id: str
    amount: int
    damage_type: DamageType
    source_id: str | None = None
    is_critical: bool = False


class HealEvent(GameEvent):
    """治療事件。"""
    target_id: str
    amount: int
    source_id: str | None = None


# --- 狀態 ---

class StatusChangeEvent(GameEvent):
    """狀態變更事件。"""
    entity_id: str
    condition: Condition
    action: str  # "applied" | "removed" | "expired"


# --- 掩護 ---

class CoverChangeEvent(GameEvent):
    """掩護變更事件（物件摧毀導致掩護消失）。"""
    observer_id: str
    target_id: str
    old_cover: CoverType
    new_cover: CoverType


# --- 表面效果 ---

class SurfaceEffectEvent(GameEvent):
    """實體觸發表面效果。"""
    entity_id: str
    surface_id: str
    trigger: str  # "enter" | "stay" | "leave"


# --- 物件傷害 ---

class ObjectDamagedEvent(GameEvent):
    """可摧毀物件受傷。"""
    object_id: str
    damage: int
    damage_type: DamageType
    hp_remaining: int


class ObjectDestroyedEvent(GameEvent):
    """可摧毀物件被摧毀。"""
    object_id: str
    destroyed_by: str | None = None


# --- 掉落 ---

class FallingEvent(GameEvent):
    """掉落事件。"""
    entity_id: str
    height_m: float
    damage_dice: str  # 例如 "3d6"
    feather_fall: bool = False


# --- 投射物 ---

class ProjectileHitCoverEvent(GameEvent):
    """投射物命中掩護物件。"""
    attacker_id: str
    cover_object_id: str
    damage: int


# --- EventBus ---

EventHandler = Callable[[GameEvent], None]


class EventBus:
    """同步事件派發器。

    設計決策：同步而非非同步。
    原因：D&D 回合制遊戲中事件順序很重要（進入火焰 → 傷害 → 專注檢定），
    非同步會引入非確定性，違反 Bone Engine 核心原則。
    """

    def __init__(self) -> None:
        self._handlers: dict[type[GameEvent], list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._history: list[GameEvent] = []

    def subscribe(self, event_type: type[GameEvent], handler: EventHandler) -> None:
        """訂閱特定事件類型。"""
        self._handlers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """訂閱所有事件（用於 SystemLog）。"""
        self._global_handlers.append(handler)

    def emit(self, event: GameEvent) -> None:
        """發送事件，依序呼叫所有 handler。"""
        self._history.append(event)
        # 全域 handler 先執行（確保 SystemLog 完整記錄）
        for handler in self._global_handlers:
            handler(event)
        # 特定類型 handler
        for handler in self._handlers.get(type(event), []):
            handler(event)

    @property
    def history(self) -> list[GameEvent]:
        """取得事件歷史（唯讀）。"""
        return list(self._history)

    def clear_history(self) -> None:
        """清除歷史紀錄。"""
        self._history.clear()
```

### A-2：雙層 Log `bone_engine/log_layers.py`（新建，~100 行）

將「結構化後端紀錄」與「玩家可讀敘事」分離。
TUI 的 `LogManager` 消費 `NarrativeLog.pop_new_messages()` 顯示給玩家，
`SystemLog.entries` 供 debug / 戰鬥回放。

```python
from tot.gremlins.bone_engine.events import (
    EventBus, GameEvent,
    EntityMoveEvent, DamageEvent, HealEvent,
    StatusChangeEvent, ObjectDestroyedEvent,
    SurfaceEffectEvent, FallingEvent, ProjectileHitCoverEvent,
)


class SystemLog:
    """結構化後端事件 log。

    subscribe_all → 原封保存 GameEvent，供 debug / 回放。
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._entries: list[GameEvent] = []
        event_bus.subscribe_all(self._on_event)

    def _on_event(self, event: GameEvent) -> None:
        self._entries.append(event)

    @property
    def entries(self) -> list[GameEvent]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


class NarrativeLog:
    """玩家可讀敘事 log。

    按事件類型生成 Rich 格式文字。
    name_resolver 是一個 callable，接收 entity_id 回傳顯示名稱。
    """

    def __init__(
        self,
        event_bus: EventBus,
        name_resolver: Callable[[str], str] | None = None,
    ) -> None:
        self._messages: list[str] = []
        self._name_resolver = name_resolver or (lambda x: x)
        # 訂閱需要敘事的事件類型
        event_bus.subscribe(EntityMoveEvent, self._on_move)
        event_bus.subscribe(DamageEvent, self._on_damage)
        event_bus.subscribe(HealEvent, self._on_heal)
        event_bus.subscribe(StatusChangeEvent, self._on_status)
        event_bus.subscribe(ObjectDestroyedEvent, self._on_object_destroyed)
        event_bus.subscribe(SurfaceEffectEvent, self._on_surface)
        event_bus.subscribe(FallingEvent, self._on_falling)
        event_bus.subscribe(ProjectileHitCoverEvent, self._on_projectile_cover)

    def _name(self, entity_id: str) -> str:
        return self._name_resolver(entity_id)

    def _on_move(self, event: GameEvent) -> None:
        e = event  # type: EntityMoveEvent
        self._messages.append(
            f"{self._name(e.entity_id)} 移動到 "
            f"({e.to_x:.1f}, {e.to_y:.1f})"
        )

    def _on_damage(self, event: GameEvent) -> None:
        e = event  # type: DamageEvent
        src = f"（來自 {self._name(e.source_id)}）" if e.source_id else ""
        crit = " [暴擊！]" if e.is_critical else ""
        self._messages.append(
            f"{self._name(e.target_id)} 受到 {e.amount} 點"
            f"{e.damage_type.value}傷害{src}{crit}"
        )

    def _on_heal(self, event: GameEvent) -> None:
        e = event  # type: HealEvent
        self._messages.append(
            f"{self._name(e.target_id)} 恢復 {e.amount} HP"
        )

    def _on_status(self, event: GameEvent) -> None:
        e = event  # type: StatusChangeEvent
        action_text = {"applied": "受到", "removed": "解除", "expired": "效果過期"}
        self._messages.append(
            f"{self._name(e.entity_id)} "
            f"{action_text.get(e.action, e.action)} "
            f"{e.condition.value}"
        )

    def _on_object_destroyed(self, event: GameEvent) -> None:
        e = event  # type: ObjectDestroyedEvent
        self._messages.append(f"{self._name(e.object_id)} 被摧毀！")

    def _on_surface(self, event: GameEvent) -> None:
        e = event  # type: SurfaceEffectEvent
        trigger_text = {"enter": "踏入", "stay": "停留在", "leave": "離開"}
        self._messages.append(
            f"{self._name(e.entity_id)} "
            f"{trigger_text.get(e.trigger, e.trigger)} "
            f"效果區域"
        )

    def _on_falling(self, event: GameEvent) -> None:
        e = event  # type: FallingEvent
        if e.feather_fall:
            self._messages.append(
                f"{self._name(e.entity_id)} 從 {e.height_m:.1f}m 高處飄落（羽落術）"
            )
        else:
            self._messages.append(
                f"{self._name(e.entity_id)} 從 {e.height_m:.1f}m 高處墜落！"
                f"（{e.damage_dice} 傷害）"
            )

    def _on_projectile_cover(self, event: GameEvent) -> None:
        e = event  # type: ProjectileHitCoverEvent
        self._messages.append(
            f"投射物命中 {self._name(e.cover_object_id)}！"
            f"（{e.damage} 傷害）"
        )

    def pop_new_messages(self) -> list[str]:
        """取出並清空待顯示訊息。TUI LogManager 呼叫此方法。"""
        msgs = list(self._messages)
        self._messages.clear()
        return msgs
```

### A-3：資料模型擴充（修改 `models.py`，~150 行增量）

#### Position 加 z 軸（向後相容 z=0.0）

```python
class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0  # 公尺，高於地面 0

    # ... 既有 field_validator, to_grid, from_grid 不變 ...

    def distance_to(self, other: Position) -> float:
        """Euclidean 距離（公尺）— 維持 2D，不破壞現有邏輯。"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def distance_3d(self, other: Position) -> float:
        """3D Euclidean 距離（公尺）。"""
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def height_diff(self, other: Position) -> float:
        """高度差絕對值。"""
        return abs(self.z - other.z)
```

> **設計決策**：`distance_to` 維持 2D，新增 `distance_3d`。
> **原因**：D&D 中水平移動距離和高度差是分開計算的（水平 = 速度消耗，垂直 = 跳/爬），
> 且現有上百處呼叫全部假設 2D。

#### TerrainTile 加高度與類型

```python
class TileType(StrEnum):
    FLOOR = "floor"
    WALL = "wall"  # 不可摧毀，永遠 blocking

class TerrainTile(BaseModel):
    symbol: str = " "
    is_blocking: bool = False
    name: str = "floor"
    is_difficult: bool = False
    # --- V2 新增 ---
    height_m: float = 0.0             # 地面高度（公尺）
    tile_type: TileType = TileType.FLOOR
```

#### Actor 加 size + z + bounds

```python
class Actor(Entity):
    combatant_id: UUID
    combatant_type: Literal["character", "monster"]
    is_blocking: bool = True
    is_alive: bool = True
    # --- V2 新增 ---
    size: Size = Size.MEDIUM   # 從 Character/Monster 同步
    z: float = 0.0             # 當前高度
    bounds: BoundingShape = Field(
        default_factory=lambda: BoundingShape.from_size(Size.MEDIUM)
    )
```

#### 材質系統（新增列舉與常數）

```python
class Material(StrEnum):
    """D&D 2024 物件材質，決定 AC。"""
    CLOTH = "cloth"          # AC 11
    PAPER = "paper"          # AC 11
    ROPE = "rope"            # AC 11
    CRYSTAL = "crystal"      # AC 13
    GLASS = "glass"          # AC 13
    ICE = "ice"              # AC 13
    WOOD = "wood"            # AC 15
    BONE = "bone"            # AC 15
    STONE = "stone"          # AC 17
    IRON = "iron"            # AC 19
    STEEL = "steel"          # AC 19
    MITHRAL = "mithral"      # AC 21
    ADAMANTINE = "adamantine" # AC 23

class Fragility(StrEnum):
    """物件堅固程度，影響 HP 倍數。"""
    FRAGILE = "fragile"      # HP ×1
    RESILIENT = "resilient"  # HP ×2

# HP 骰 by Size（D&D 2024 DMG 物件規則）
OBJECT_HP_DICE: dict[Size, str] = {
    Size.TINY: "1d4",
    Size.SMALL: "3d6",
    Size.MEDIUM: "4d6",
    Size.LARGE: "5d6",
}
```

#### 可摧毀物件（擴充 Prop）

```python
class Prop(Entity):
    # --- 既有欄位 ---
    prop_type: str = "decoration"
    hidden: bool = False
    cover_bonus: int = 0
    # --- V2 新增：可摧毀欄位（全部 optional，既有 JSON 不受影響）---
    material: Material | None = None         # None = 不可摧毀
    fragility: Fragility = Fragility.RESILIENT
    object_size: Size = Size.MEDIUM
    hp_max: int = 0                          # 0 = 不可摧毀
    hp_current: int = 0
    object_ac: int = 15                      # 由 material 查表填入
    damage_immunities: list[DamageType] = Field(default_factory=list)
    damage_threshold: int = 0                # 低於此值的傷害無效
    bounds: BoundingShape | None = None      # None = 沿用 grid-snap AABB
```

> **設計決策**：不另開 DestructibleObject 子類，直接在 Prop 加欄位。
> **原因**：
> 1. 所有現有 Prop 的新欄位全部有合理預設值（None/0）
> 2. 地圖 JSON `props` 陣列不用改結構
> 3. 掩護判定直接查 `prop.cover_bonus` + `prop.hp_current`，不用型別分派
> 4. `material is None or hp_max == 0` = 不可摧毀

#### 通用幾何形狀 + BoundingShape

```python
class ShapeType(StrEnum):
    """通用幾何形狀類型。"""
    CIRCLE = "circle"
    RECTANGLE = "rectangle"
    CONE = "cone"          # 有方向
    LINE = "line"          # 有方向，零寬度線段
    CYLINDER = "cylinder"  # 2D = circle，有 height_m

class BoundingShape(BaseModel):
    """通用碰撞/範圍幾何。

    可嵌入 SurfaceEffect（效果區域）、Prop（物件體積）、Actor（生物佔據空間）。
    座標系統：以持有者的 (x, y) 為中心。

    方向性形狀（CONE/LINE）需要 direction_deg 指定朝向。
    CYLINDER 在 2D 等同 CIRCLE，Z 軸高度檢查在 GameStateManager 層做。
    """
    shape_type: ShapeType = ShapeType.CIRCLE
    radius_m: float = 0.0
    half_width_m: float = 0.0    # 矩形 X 方向半寬
    half_height_m: float = 0.0   # 矩形 Y 方向半高
    direction_deg: float | None = None  # CONE/LINE 水平朝向（0=+Y北，順時針）
    angle_deg: float = 53.0             # CONE 全角（D&D 標準）
    length_m: float = 0.0               # CONE/LINE 長度
    height_m: float = 0.0               # CYLINDER 垂直高度（正=上，負=下）

    def contains_point(self, cx: float, cy: float, px: float, py: float) -> bool:
        """點 (px, py) 是否在以 (cx, cy) 為中心的此形狀內。"""
        if self.shape_type == ShapeType.CIRCLE:
            dx = px - cx
            dy = py - cy
            return (dx * dx + dy * dy) <= self.radius_m * self.radius_m
        elif self.shape_type == ShapeType.RECTANGLE:
            return (
                abs(px - cx) <= self.half_width_m
                and abs(py - cy) <= self.half_height_m
            )
        elif self.shape_type == ShapeType.CONE:
            # 錐形：方向向量 + dot-product 角度 + 距離
            dx = px - cx
            dy = py - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > self.length_m or dist < 1e-9:
                return dist < 1e-9  # 頂點本身算在內
            rad = math.radians(self.direction_deg or 0.0)
            dir_x = math.sin(rad)   # 0° = +Y (北)，順時針
            dir_y = math.cos(rad)
            cos_angle = (dx * dir_x + dy * dir_y) / dist
            half_angle_cos = math.cos(math.radians(self.angle_deg / 2))
            return cos_angle >= half_angle_cos
        elif self.shape_type == ShapeType.LINE:
            # 線段：點到線段的垂直距離 < ε
            # 實務上 LINE AoE 用 intersects_line() 判定命中
            rad = math.radians(self.direction_deg or 0.0)
            dir_x = math.sin(rad)
            dir_y = math.cos(rad)
            dx = px - cx
            dy = py - cy
            proj = dx * dir_x + dy * dir_y
            if proj < 0 or proj > self.length_m:
                return False
            perp_dist_sq = (dx - proj * dir_x) ** 2 + (dy - proj * dir_y) ** 2
            return perp_dist_sq < 0.01 * 0.01  # ε = 0.01m
        else:  # CYLINDER — 2D 等同 CIRCLE
            dx = px - cx
            dy = py - cy
            return (dx * dx + dy * dy) <= self.radius_m * self.radius_m

    def intersects_line(
        self, cx: float, cy: float,
        target_bounds: BoundingShape, tx: float, ty: float,
    ) -> bool:
        """LINE 專用：此 LINE 線段是否穿過 target 的碰撞圓。

        使用 line-circle intersection：
        線段從 (cx, cy) 延伸 length_m 到終點，
        判定是否與以 (tx, ty) 為中心、radius_m 為半徑的圓重疊。
        """
        if self.shape_type != ShapeType.LINE:
            raise ValueError("intersects_line 只適用於 LINE 形狀")
        rad = math.radians(self.direction_deg or 0.0)
        dir_x = math.sin(rad)
        dir_y = math.cos(rad)
        # 線段終點
        ex = cx + dir_x * self.length_m
        ey = cy + dir_y * self.length_m
        # 最近點投影
        dx = ex - cx
        dy = ey - cy
        fx = cx - tx
        fy = cy - ty
        a = dx * dx + dy * dy
        b = 2 * (fx * dx + fy * dy)
        r = target_bounds.radius_m
        c = fx * fx + fy * fy - r * r
        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return False
        discriminant = math.sqrt(discriminant)
        t1 = (-b - discriminant) / (2 * a)
        t2 = (-b + discriminant) / (2 * a)
        # 線段範圍 t ∈ [0, 1]
        return t1 <= 1.0 and t2 >= 0.0

    def overlaps(
        self, cx: float, cy: float,
        other: BoundingShape, ox: float, oy: float,
    ) -> bool:
        """兩個 BoundingShape 是否重疊（碰撞判定核心）。

        支援 circle×circle、circle×rect、rect×rect 三種組合。
        CONE/LINE/CYLINDER 不支援碰撞判定。
        """
        # 方向/柱形狀不參與碰撞
        _no_overlap = {ShapeType.CONE, ShapeType.LINE, ShapeType.CYLINDER}
        if self.shape_type in _no_overlap or other.shape_type in _no_overlap:
            raise NotImplementedError(
                f"overlaps 不支援 {self.shape_type}/{other.shape_type}，"
                "碰撞僅限 CIRCLE/RECTANGLE"
            )
        if (
            self.shape_type == ShapeType.CIRCLE
            and other.shape_type == ShapeType.CIRCLE
        ):
            # 圓 × 圓：中心距 < 兩半徑之和
            dx = cx - ox
            dy = cy - oy
            dist_sq = dx * dx + dy * dy
            r_sum = self.radius_m + other.radius_m
            return dist_sq < r_sum * r_sum
        elif (
            self.shape_type == ShapeType.RECTANGLE
            and other.shape_type == ShapeType.RECTANGLE
        ):
            # 矩形 × 矩形：AABB overlap
            return (
                abs(cx - ox) < self.half_width_m + other.half_width_m
                and abs(cy - oy) < self.half_height_m + other.half_height_m
            )
        else:
            # 圓 × 矩形：委託 geometry.py 的 circle_aabb_overlap
            if self.shape_type == ShapeType.CIRCLE:
                circle_cx, circle_cy, circle_r = cx, cy, self.radius_m
                rect = other.to_aabb(ox, oy)
            else:
                circle_cx, circle_cy, circle_r = ox, oy, other.radius_m
                rect = self.to_aabb(cx, cy)
            return circle_aabb_overlap(
                circle_cx, circle_cy, circle_r, rect
            )

    def to_aabb(self, cx: float, cy: float) -> AABB:
        """轉為軸對齊 AABB（供 Minkowski inflation / extract_static_obstacles）。"""
        if self.shape_type == ShapeType.CIRCLE:
            return AABB(
                cx - self.radius_m, cy - self.radius_m,
                cx + self.radius_m, cy + self.radius_m,
            )
        elif self.shape_type == ShapeType.RECTANGLE:
            return AABB(
                cx - self.half_width_m, cy - self.half_height_m,
                cx + self.half_width_m, cy + self.half_height_m,
            )
        elif self.shape_type in (ShapeType.CONE, ShapeType.LINE):
            # 保守正方形：以 length_m 為半徑
            return AABB(
                cx - self.length_m, cy - self.length_m,
                cx + self.length_m, cy + self.length_m,
            )
        else:  # CYLINDER — 同 CIRCLE
            return AABB(
                cx - self.radius_m, cy - self.radius_m,
                cx + self.radius_m, cy + self.radius_m,
            )

    @classmethod
    def circle(cls, radius_m: float) -> BoundingShape:
        return cls(shape_type=ShapeType.CIRCLE, radius_m=radius_m)

    @classmethod
    def rect(cls, width_m: float, height_m: float) -> BoundingShape:
        return cls(shape_type=ShapeType.RECTANGLE,
                   half_width_m=width_m / 2, half_height_m=height_m / 2)

    @classmethod
    def from_size(cls, size: Size) -> BoundingShape:
        """從 D&D 體型查 SIZE_RADIUS_M 生成碰撞圓。"""
        return cls.circle(SIZE_RADIUS_M[size])

    @classmethod
    def cone(
        cls, length_m: float, direction_deg: float, angle_deg: float = 53.0,
    ) -> BoundingShape:
        """錐形（AoE cone、未來視野錐）。"""
        return cls(
            shape_type=ShapeType.CONE,
            length_m=length_m,
            direction_deg=direction_deg,
            angle_deg=angle_deg,
        )

    @classmethod
    def line(cls, length_m: float, direction_deg: float) -> BoundingShape:
        """零寬度線段（AoE line）。"""
        return cls(
            shape_type=ShapeType.LINE,
            length_m=length_m,
            direction_deg=direction_deg,
        )

    @classmethod
    def cylinder(cls, radius_m: float, height_m: float) -> BoundingShape:
        """圓柱（2D = circle，高度待 Z 軸用）。"""
        return cls(
            shape_type=ShapeType.CYLINDER,
            radius_m=radius_m,
            height_m=height_m,
        )
```

#### 表面效果模型

```python
class SurfaceTrigger(StrEnum):
    ENTER = "enter"
    STAY = "stay"
    LEAVE = "leave"

class SurfaceEffect(BaseModel):
    """場上的持續效果區域（如燃燒地面、寒冰區域、糾纏藤蔓）。"""
    id: str
    name: str
    bounds: BoundingShape          # 效果區域幾何
    center_x: float
    center_y: float
    center_z: float = 0.0
    damage_dice: str = ""
    damage_type: DamageType | None = None
    save_dc: int = 0
    save_ability: Ability | None = None
    save_half: bool = False
    applies_condition: Condition | None = None
    is_difficult_terrain: bool = False
    triggers: list[SurfaceTrigger] = Field(
        default_factory=lambda: [SurfaceTrigger.ENTER]
    )
    remaining_rounds: int | None = None  # None = 永久
    source_id: str | None = None

    def contains_point(self, x: float, y: float) -> bool:
        """判斷點 (x, y) 是否在效果範圍內（委託 BoundingShape）。"""
        return self.bounds.contains_point(self.center_x, self.center_y, x, y)
```

#### MapState 加 surfaces

```python
class MapState(BaseModel):
    manifest: MapManifest
    terrain: list[list[TerrainTile]] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)
    # --- V2 新增 ---
    surfaces: list[SurfaceEffect] = Field(default_factory=list)
```

#### 掩護查詢結果

```python
class CoverResult(BaseModel):
    """完整掩護查詢結果，包含提供掩護的物件清單。"""
    cover_type: CoverType
    cover_objects: list[str] = Field(default_factory=list)  # 提供掩護的 Prop.id
    primary_cover_id: str | None = None  # 最大掩護來源
```

### A-4：材質常數 + 物件傷害 `bone_engine/materials.py`（新建，~120 行）

```python
from tot.models import Material, Fragility, Size, DamageType, Prop, OBJECT_HP_DICE
from tot.gremlins.bone_engine.dice import roll_expression
from dataclasses import dataclass

MATERIAL_AC: dict[Material, int] = {
    Material.CLOTH: 11, Material.PAPER: 11, Material.ROPE: 11,
    Material.CRYSTAL: 13, Material.GLASS: 13, Material.ICE: 13,
    Material.WOOD: 15, Material.BONE: 15,
    Material.STONE: 17,
    Material.IRON: 19, Material.STEEL: 19,
    Material.MITHRAL: 21,
    Material.ADAMANTINE: 23,
}

def object_ac(material: Material) -> int:
    """查表取得物件 AC。"""
    return MATERIAL_AC[material]

def roll_object_hp(
    size: Size,
    fragility: Fragility,
    rng=None,
) -> int:
    """擲物件 HP 骰。RESILIENT = ×2 倍。"""
    dice_expr = OBJECT_HP_DICE.get(size, "4d6")
    result = roll_expression(dice_expr, rng=rng)
    hp = result.total
    if fragility == Fragility.RESILIENT:
        hp *= 2
    return max(1, hp)


@dataclass
class ObjectDamageResult:
    """物件受傷結果。"""
    damage_dealt: int
    hp_remaining: int
    destroyed: bool


def apply_object_damage(
    prop: Prop,
    amount: int,
    damage_type: DamageType,
) -> ObjectDamageResult:
    """對可摧毀物件施加傷害。

    規則：
    - 免疫的傷害類型 → 0
    - 低於 damage_threshold → 0
    - 不可摧毀（material is None or hp_max == 0）→ 0
    """
    if prop.material is None or prop.hp_max == 0:
        return ObjectDamageResult(0, prop.hp_current, False)
    if damage_type in prop.damage_immunities:
        return ObjectDamageResult(0, prop.hp_current, False)
    if amount < prop.damage_threshold:
        return ObjectDamageResult(0, prop.hp_current, False)

    prop.hp_current = max(0, prop.hp_current - amount)
    destroyed = prop.hp_current <= 0
    return ObjectDamageResult(amount, prop.hp_current, destroyed)


def is_object_destroyed(prop: Prop) -> bool:
    """判斷物件是否已被摧毀。"""
    if prop.material is None or prop.hp_max == 0:
        return False
    return prop.hp_current <= 0
```

### A-5：測試

- `tests/test_events.py`（~150 行）— EventBus 訂閱/發送/歷史/subscribe_all
- `tests/test_materials.py`（~120 行）— AC 查表、HP 骰、物件傷害/摧毀/免疫/門檻

---

## 6. Phase B：表面效果系統

**相依：Phase A 模型**

### B-1：`bone_engine/surfaces.py`（新建，~180 行）

```python
from dataclasses import dataclass
from tot.models import SurfaceEffect, SurfaceTrigger, Condition, DamageType

@dataclass
class SurfaceEffectResult:
    """表面效果觸發結果。"""
    surface_id: str
    surface_name: str
    trigger: SurfaceTrigger
    damage_dealt: int = 0
    damage_type: DamageType | None = None
    save_succeeded: bool | None = None  # None = 不需豁免
    condition_applied: Condition | None = None


def check_surface_enter(
    entity_id: str,
    old_pos: tuple[float, float],
    new_pos: tuple[float, float],
    surfaces: list[SurfaceEffect],
) -> list[SurfaceEffect]:
    """檢查移動是否進入任何表面效果區域。

    回傳新進入的 surface 列表（舊位置不在、新位置在的）。
    """
    ...


def check_surface_leave(
    entity_id: str,
    old_pos: tuple[float, float],
    new_pos: tuple[float, float],
    surfaces: list[SurfaceEffect],
) -> list[SurfaceEffect]:
    """檢查移動是否離開任何表面效果區域。"""
    ...


def resolve_surface_effect(
    entity,           # Character | Monster
    surface: SurfaceEffect,
    trigger: SurfaceTrigger,
    *,
    rng=None,
) -> SurfaceEffectResult:
    """解算表面效果。

    流程：
    1. 有 save_dc → 擲豁免
    2. 豁免失敗（或無豁免）→ 擲傷害骰
    3. save_half 且豁免成功 → 半傷
    4. 有 applies_condition → 施加狀態
    """
    ...


def tick_surfaces_round_start(
    surfaces: list[SurfaceEffect],
) -> tuple[list[SurfaceEffect], list[SurfaceEffect]]:
    """回合開始時更新表面效果。

    remaining_rounds 不為 None 的 surface 減 1，
    減到 0 就過期移除。

    回傳：(仍存在的 surfaces, 過期的 surfaces)
    """
    ...
```

### B-2：測試 `tests/test_surfaces.py`（~180 行）

覆蓋項目：
- 進入/離開幾何判定（圓形 + 矩形）
- 傷害骰 + 豁免（成功/失敗/半傷）
- 狀態施加
- 持續回合遞減 + 過期移除
- 困難地形標記

---

## 7. Phase C：Z 軸地形

**相依：Phase A 模型**

### C-1：spatial.py 加高度邏輯（+~70 行）

```python
from dataclasses import dataclass

@dataclass
class HeightCheckResult:
    """高度通行檢查結果。"""
    can_pass: bool
    needs_jump: bool = False
    height_diff: float = 0.0


def check_height_traversal(
    from_z: float,
    to_z: float,
    jump_height: float = 0.25,
) -> HeightCheckResult:
    """檢查高度差能否通行。

    規則：
    - ≤ 25cm (jump_height)：自動通過（台階、小石頭）
    - > 25cm：需要跳躍/攀爬檢定
    """
    diff = abs(to_z - from_z)
    if diff <= jump_height:
        return HeightCheckResult(can_pass=True, height_diff=diff)
    return HeightCheckResult(
        can_pass=False, needs_jump=True, height_diff=diff
    )


def calculate_falling_damage(height_m: float) -> str:
    """計算掉落傷害骰。

    D&D 2024 規則：每 3m = 1d6，上限 20d6 (= 60m)。
    """
    dice_count = min(int(height_m / 3), 20)
    if dice_count <= 0:
        return "0"
    return f"{dice_count}d6"
```

### C-2：move_entity 擴充

`move_entity()` 新增 `tz: float | None = None` 參數（None = 忽略高度）。
當 `tz is not None`，內部查 `TerrainTile.height_m` 做高度差檢查。

```python
def move_entity(
    actor: Actor,
    tx: float,
    ty: float,
    map_state: MapState,
    speed_remaining: float,
    *,
    tz: float | None = None,  # V2 新增：目標高度（None = 忽略）
    allies: set[str] | None = None,
    mover_size: Size = Size.MEDIUM,
) -> MoveResult:
    # ... 既有邏輯不變 ...
    # V2：高度差檢查（tz 有值時）
    if tz is not None:
        height_result = check_height_traversal(actor.z, tz)
        if not height_result.can_pass:
            # 回傳需要跳躍的事件
            ...
        else:
            actor.z = tz
```

### C-3：Actor.size 傳播（此 Phase 只做 spatial.py 內的硬編碼修正）

`spatial.py` 中以下位置的 `Size.MEDIUM` 硬編碼 → 改用 `actor.size`：
- `move_entity()` 中 `other_r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)` → `SIZE_RADIUS_M.get(other.size, 0.75)`
- `can_end_move_at()` 中同上
- `can_traverse()` 呼叫處也需要拿到真實 size

> **風險**：改動行為影響所有碰撞判定，需逐個測試驗證。

### C-4：測試 `tests/test_z_axis.py`（~130 行）

覆蓋項目：
- 高度差 ≤ 25cm 自動通過
- 高度差 > 25cm 需要 jump
- 掉落傷害 1d6/3m，上限 20d6
- Feather Fall 免疫
- Position.distance_3d 正確性
- Position.height_diff 正確性

---

## 8. Phase D：掩護系統強化

> ⚠️ D-1 演算法已更新為 Corner-Ray 模型，詳見 [`spatial-combat-design.md`](spatial-combat-design.md) §2（ADR-1）

**相依：Phase A 模型 + 材質系統**

### D-1：spatial.py 加射線掩護（+~90 行）

```python
from tot.models import CoverResult, CoverType

def determine_cover(
    attacker: Position,
    target: Position,
    map_state: MapState,
) -> CoverResult:
    """整合 Bresenham 路徑 + Prop 掩護的完整版掩護判定。

    演算法：
    1. Bresenham 射線掃描攻擊者到目標的每個格子
    2. 格子上有 blocking terrain → 按既有規則計掩護
    3. 格子上有 Prop(cover_bonus > 0) 且未被摧毀 → 取 cover_bonus
    4. 多重掩護不疊加，取最大值
    5. 回傳 CoverResult（含提供掩護的物件清單）

    取代原 determine_cover_from_grid()（只有 3 個呼叫點，migration 輕量）。
    舊版只看 terrain blocking 且回傳 CoverType，新版：
    - 額外看 Prop.cover_bonus + 可摧毀狀態
    - 回傳 CoverResult（呼叫端用 .cover_type 取得原本的 CoverType）
    """
    cover_objects: list[str] = []
    max_bonus = 0
    primary_id: str | None = None

    # Bresenham 射線
    ax, ay = attacker.to_grid()
    tx, ty = target.to_grid()
    path = bresenham_line(ax, ay, tx, ty)

    for gx, gy in path[1:-1]:  # 跳過起終點
        # 地形 blocking
        if _is_terrain_blocking(gx, gy, map_state):
            max_bonus = max(max_bonus, 5)  # 地形 blocking = 至少 3/4 掩護

        # Prop 掩護
        for prop in map_state.props + map_state.manifest.props:
            px, py = prop.grid_pos()
            if (px, py) == (gx, gy) and prop.cover_bonus > 0:
                # 可摧毀物件已被摧毀 → 不提供掩護
                if prop.material is not None and prop.hp_current <= 0:
                    continue
                if prop.cover_bonus > max_bonus:
                    max_bonus = prop.cover_bonus
                    primary_id = prop.id
                cover_objects.append(prop.id)

    # bonus → CoverType 轉換
    if max_bonus >= 99:
        cover_type = CoverType.TOTAL
    elif max_bonus >= 5:
        cover_type = CoverType.THREE_QUARTERS
    elif max_bonus >= 2:
        cover_type = CoverType.HALF
    else:
        cover_type = CoverType.NONE

    return CoverResult(
        cover_type=cover_type,
        cover_objects=cover_objects,
        primary_cover_id=primary_id,
    )
```

**Migration**：`determine_cover_from_grid()` 改名為 `determine_cover()`，回傳型別從 `CoverType` 改為 `CoverResult`。
呼叫點只有 `tests/test_spatial.py`（2 處），改為 `.cover_type` 即可。不保留舊函式 — 呼叫點少、沒有向後相容壓力。

### D-2：combat.py 加投射物打掩護（+~30 行）

```python
def resolve_projectile_vs_cover(
    attack_roll: int,
    target_ac: int,
    cover_result: CoverResult,
) -> str | None:
    """遠程攻擊 miss 時檢查是否命中掩護物件。

    D&D 2024 可選規則：
    遠程 miss 且 roll >= (AC - cover_bonus) → 投射物命中掩護物件。
    回傳被擊中的 Prop.id 或 None。
    """
    if cover_result.cover_type == CoverType.NONE:
        return None
    if cover_result.primary_cover_id is None:
        return None

    # cover_bonus 從 CoverType 反查
    cover_bonus = _COVER_AC_BONUS.get(cover_result.cover_type, 0)
    effective_ac_without_cover = target_ac - cover_bonus

    if attack_roll >= effective_ac_without_cover:
        return cover_result.primary_cover_id
    return None
```

### D-3：測試 `tests/test_cover_v2.py`（~170 行）

覆蓋項目：
- Prop 掩護判定（半掩護木箱 cover_bonus=2、3/4 石柱 cover_bonus=5）
- 多重掩護取最大值
- 投射物打掩護觸發物件傷害
- 物件摧毀後掩護消失（hp_current=0 → 不計掩護）
- 舊 test_spatial.py 掩護測試遷移到 `.cover_type` 存取

---

## 9. Phase E：Actor.size 全面傳播

**相依：Phase A（Actor.size 欄位）**

### E-1：place_actors_at_spawn() 設定 actor.size + bounds

`place_actors_at_spawn()` 從 Character/Monster 讀取 `size` → 設定到 `Actor.size` 和 `Actor.bounds`：

```python
def place_actors_at_spawn(
    characters: list[Character],
    monsters: list[Monster],
    map_state: MapState,
) -> None:
    # ... 在建立 Actor 時 ...
    actor = Actor(
        id=f"pc_{i}",
        combatant_id=char.id,
        combatant_type="character",
        x=mx, y=my,
        symbol=char.name[0],
        name=char.name,
        size=char.size,                        # V2：從 Character 同步
        bounds=BoundingShape.from_size(char.size),  # V2：碰撞幾何
    )
```

### E-2：spatial.py 碰撞判定改用 `bounds.overlaps()`

Before（散落 16 處 `SIZE_RADIUS_M.get(...)` 呼叫）：
```python
my_r = SIZE_RADIUS_M[size]
other_r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
center_dist = math.sqrt((a.x - pos.x)**2 + (a.y - pos.y)**2)
if center_dist < my_r + other_r:
```

After（統一使用 `bounds`）：
```python
if my_bounds.overlaps(pos.x, pos.y, other.bounds, other.x, other.y):
```

改動範圍：
- `move_entity()` 中碰撞檢查 → `actor.bounds.overlaps(...)`
- `can_end_move_at()` 中位置驗證 → `actor.bounds.overlaps(...)`
- `check_collision()` 相關呼叫 → 統一用 `bounds`

### E-3：pathfinding.py + movement.py 改用 `bounds.to_aabb()`

Before：
```python
r = SIZE_RADIUS_M.get(Size.MEDIUM, 0.75)
dynamic_obs.append(AABB(actor.x - r, actor.y - r, actor.x + r, actor.y + r))
```

After：
```python
dynamic_obs.append(actor.bounds.to_aabb(actor.x, actor.y))
```

Minkowski inflation 也改用 `mover.bounds.radius_m`（圓形）或 `mover.bounds.to_aabb()` 外擴。

### E-4：更新既有測試

所有建立 Actor 的測試 fixture 需加 `size=Size.MEDIUM, bounds=BoundingShape.from_size(Size.MEDIUM)`（explicit default）。

---

## 10. Phase F：GameStateManager + 事件整合

**相依：所有前置 Phase**

### F-1：`bone_engine/game_state.py`（新建，~300 行）

```python
from uuid import UUID
from tot.models import (
    Actor, Character, Monster, Position, MapState, CombatState,
    SurfaceEffect, CoverResult, MoveResult, Prop, DamageType, Condition,
)
from tot.gremlins.bone_engine.events import EventBus, GameEvent
from tot.gremlins.bone_engine.log_layers import SystemLog, NarrativeLog
from tot.gremlins.bone_engine.surfaces import (
    check_surface_enter, check_surface_leave,
    resolve_surface_effect, tick_surfaces_round_start,
    SurfaceEffectResult,
)
from tot.gremlins.bone_engine.materials import apply_object_damage
from tot.gremlins.bone_engine import spatial, combat


class GameStateManager:
    """全域狀態管理器，包裝 MapState + CombatState + EventBus。

    所有狀態變更經由此 manager，自動 emit 事件。
    不取代既有函式，而是包裝它們 + emit event。

    設計原則：
    - 查詢方法直接代理到 spatial/combat
    - 變更方法先呼叫底層函式，再 emit 事件
    - TUI 透過 NarrativeLog 取得可讀訊息，不直接操作 EventBus
    """

    def __init__(
        self,
        combat_state: CombatState,
        map_state: MapState,
        characters: list[Character],
        monsters: list[Monster],
    ) -> None:
        self.combat_state = combat_state
        self.map_state = map_state
        self.characters = {c.id: c for c in characters}
        self.monsters = {m.id: m for m in monsters}

        self.event_bus = EventBus()
        self.system_log = SystemLog(self.event_bus)
        self.narrative_log = NarrativeLog(
            self.event_bus,
            name_resolver=self._resolve_name,
        )

    def _resolve_name(self, entity_id: str) -> str:
        """將 entity_id 解析為顯示名稱。"""
        # 查 Actor
        for actor in self.map_state.actors:
            if actor.id == entity_id:
                return actor.name or entity_id
        # 查 Prop
        for prop in self.map_state.props + self.map_state.manifest.props:
            if prop.id == entity_id:
                return prop.name or entity_id
        # 查 Surface
        for surface in self.map_state.surfaces:
            if surface.id == entity_id:
                return surface.name
        return entity_id

    # --- 查詢 ---

    def get_actor(self, combatant_id: UUID) -> Actor | None:
        """依 combatant_id 查詢 Actor。"""
        return spatial.get_actor_by_combatant_id(combatant_id, self.map_state)

    def get_combatant(self, combatant_id: UUID) -> Character | Monster | None:
        """依 combatant_id 查詢 Character 或 Monster。"""
        return self.characters.get(combatant_id) or self.monsters.get(combatant_id)

    def actors_in_radius(
        self, center: Position, radius_m: float
    ) -> list[Actor]:
        return spatial.actors_in_radius(center, radius_m, self.map_state)

    def surfaces_at(self, x: float, y: float) -> list[SurfaceEffect]:
        return [s for s in self.map_state.surfaces if s.contains_point(x, y)]

    # --- 變更（emit event）---

    def move_actor(
        self, actor: Actor, tx: float, ty: float, tz: float = 0.0,
        *, allies: set[str] | None = None,
    ) -> MoveResult:
        """移動 Actor 並 emit 事件 + 觸發表面效果。"""
        old_x, old_y, old_z = actor.x, actor.y, actor.z
        result = spatial.move_entity(
            actor, tx, ty, self.map_state,
            speed_remaining=self.combat_state.turn_state.movement_remaining,
            allies=allies,
            mover_size=actor.size,
        )
        if result.success:
            # 表面效果：離開
            left = check_surface_leave(
                actor.id, (old_x, old_y), (actor.x, actor.y),
                self.map_state.surfaces,
            )
            # 表面效果：進入
            entered = check_surface_enter(
                actor.id, (old_x, old_y), (actor.x, actor.y),
                self.map_state.surfaces,
            )
            # Emit 移動事件
            from tot.gremlins.bone_engine.events import (
                EntityMoveEvent, SurfaceEffectEvent, DamageEvent,
            )
            self.event_bus.emit(EntityMoveEvent(
                entity_id=actor.id,
                from_x=old_x, from_y=old_y, from_z=old_z,
                to_x=actor.x, to_y=actor.y, to_z=actor.z,
                speed_cost=self.combat_state.turn_state.movement_remaining - result.speed_remaining,
            ))
            # 觸發進入的表面效果
            for surface in entered:
                self.event_bus.emit(SurfaceEffectEvent(
                    entity_id=actor.id,
                    surface_id=surface.id,
                    trigger="enter",
                ))
                # 解算效果
                combatant = self.get_combatant(actor.combatant_id)
                if combatant:
                    effect_result = resolve_surface_effect(
                        combatant, surface, SurfaceTrigger.ENTER,
                    )
                    if effect_result.damage_dealt > 0:
                        self.event_bus.emit(DamageEvent(
                            target_id=actor.id,
                            amount=effect_result.damage_dealt,
                            damage_type=effect_result.damage_type,
                            source_entity_id=surface.id,
                        ))

        return result

    def apply_damage_to_combatant(
        self, target_id: str, amount: int, damage_type: DamageType,
        *, source_id: str | None = None, is_critical: bool = False,
    ):
        """對生物施加傷害 + emit 事件。"""
        from tot.gremlins.bone_engine.events import DamageEvent
        # 底層呼叫 combat.apply_damage (由呼叫端處理)
        self.event_bus.emit(DamageEvent(
            target_id=target_id,
            amount=amount,
            damage_type=damage_type,
            source_id=source_id,
            is_critical=is_critical,
        ))

    def apply_damage_to_object(
        self, prop: Prop, amount: int, damage_type: DamageType,
        *, source_id: str | None = None,
    ):
        """對可摧毀物件施加傷害 + emit 事件。"""
        from tot.gremlins.bone_engine.events import (
            ObjectDamagedEvent, ObjectDestroyedEvent, CoverChangeEvent,
        )
        result = apply_object_damage(prop, amount, damage_type)
        if result.damage_dealt > 0:
            self.event_bus.emit(ObjectDamagedEvent(
                object_id=prop.id,
                damage=result.damage_dealt,
                damage_type=damage_type,
                hp_remaining=result.hp_remaining,
            ))
        if result.destroyed:
            self.event_bus.emit(ObjectDestroyedEvent(
                object_id=prop.id,
                destroyed_by=source_id,
            ))

    def apply_healing(
        self, target_id: str, amount: int,
        *, source_id: str | None = None,
    ) -> int:
        """治療 + emit 事件。回傳實際治療量。"""
        from tot.gremlins.bone_engine.events import HealEvent
        self.event_bus.emit(HealEvent(
            target_id=target_id,
            amount=amount,
            source_id=source_id,
        ))
        return amount

    def apply_condition(
        self, target_id: str, condition: Condition,
        *, source: str = "",
    ):
        """施加狀態 + emit 事件。"""
        from tot.gremlins.bone_engine.events import StatusChangeEvent
        self.event_bus.emit(StatusChangeEvent(
            entity_id=target_id,
            condition=condition,
            action="applied",
        ))

    def add_surface(self, surface: SurfaceEffect) -> None:
        """新增表面效果到地圖。"""
        self.map_state.surfaces.append(surface)

    def remove_surface(self, surface_id: str) -> None:
        """移除表面效果。"""
        self.map_state.surfaces = [
            s for s in self.map_state.surfaces if s.id != surface_id
        ]

    def tick_surfaces(self) -> None:
        """回合開始時更新所有表面效果。"""
        remaining, expired = tick_surfaces_round_start(self.map_state.surfaces)
        self.map_state.surfaces = remaining

    def check_surface_effects(
        self, entity_id: str, trigger,
    ) -> list[SurfaceEffectResult]:
        """手動檢查特定 trigger 的表面效果（如 STAY）。"""
        actor = next(
            (a for a in self.map_state.actors if a.id == entity_id), None
        )
        if not actor:
            return []
        results = []
        for surface in self.map_state.surfaces:
            if surface.contains_point(actor.x, actor.y):
                if trigger in surface.triggers:
                    combatant = self.get_combatant(actor.combatant_id)
                    if combatant:
                        result = resolve_surface_effect(
                            combatant, surface, trigger,
                        )
                        results.append(result)
        return results
```

### F-2：TUI 整合（漸進式）

`GameStateManager` 不取代既有函式，而是包裝它們 + emit event。
TUI 呼叫端從 `log.log(...)` 改為讓 `NarrativeLog` 自動產生文字。

漸進遷移策略：一次只改一個 action function：
1. 先在 `app.py` 建立 `GameStateManager` 實例
2. 把 `NarrativeLog.pop_new_messages()` 接到 `LogManager`
3. 逐步將 `actions.py` / `npc_ai.py` 的直接呼叫改為透過 manager

### F-3：測試 `tests/test_game_state.py`（~180 行）

覆蓋項目：
- 狀態變更 → emit 正確事件
- NarrativeLog 產生可讀文字
- SystemLog 完整記錄所有事件
- 移動觸發表面效果的完整流程
- 物件摧毀觸發掩護變更
- tick_surfaces 正確遞減/過期

---

## 11. 事件流範例

### 移動觸發表面效果

```
player_move("5 3")
  → GameStateManager.move_actor(actor, 7.5, 4.5)
    → spatial.move_entity()             → MoveResult
    → surfaces.check_surface_leave()    → [離開的 surface]
    → surfaces.check_surface_enter()    → [進入的 surface]
    → emit(EntityMoveEvent)
    → emit(SurfaceEffectEvent(trigger="enter"))
    → emit(DamageEvent)                 → 火焰傷害
  → NarrativeLog: "Aldric 移動到 (5,3)，踏入火焰區域！受到 2d6 火焰傷害。"
  → SystemLog: [EntityMoveEvent, SurfaceEffectEvent, DamageEvent]
```

### 遠程攻擊打掩護

```
player_attack("哥布林A", ranged=True)
  → determine_cover(atk_pos, tgt_pos, map_state)
    → CoverResult(HALF, cover_objects=["wooden_crate"], primary_cover_id="wooden_crate")
  → resolve_attack(roll=14, target_ac=16)  → miss
  → resolve_projectile_vs_cover(14, 16, cover_result)
    → 14 >= (16-2) → 命中木箱
  → apply_damage_to_object(wooden_crate, projectile_dmg)
  → emit(ProjectileHitCoverEvent)
  → if hp_current <= 0: emit(ObjectDestroyedEvent), emit(CoverChangeEvent)
```

---

## 12. 關鍵檔案

| 檔案 | 動作 | 預估增量 |
|------|------|---------|
| `src/tot/models.py` | 修改 | +200 行（含 BoundingShape ~50 行） |
| `src/tot/gremlins/bone_engine/events.py` | **新建** | ~200 行 |
| `src/tot/gremlins/bone_engine/log_layers.py` | **新建** | ~100 行 |
| `src/tot/gremlins/bone_engine/materials.py` | **新建** | ~120 行 |
| `src/tot/gremlins/bone_engine/surfaces.py` | **新建** | ~180 行 |
| `src/tot/gremlins/bone_engine/game_state.py` | **新建** | ~300 行 |
| `src/tot/gremlins/bone_engine/spatial.py` | 修改 | +160 行 |
| `src/tot/gremlins/bone_engine/combat.py` | 修改 | +30 行 |
| `tests/test_events.py` | **新建** | ~150 行 |
| `tests/test_materials.py` | **新建** | ~120 行 |
| `tests/test_surfaces.py` | **新建** | ~180 行 |
| `tests/test_z_axis.py` | **新建** | ~130 行 |
| `tests/test_cover_v2.py` | **新建** | ~170 行 |
| `tests/test_game_state.py` | **新建** | ~180 行 |

**總計：新增 ~1,500 行，修改 ~370 行，新增測試 ~930 行**

---

## 13. 風險與注意事項

1. **Position.distance_to 維持 2D**：不破壞現有呼叫者。需要 3D 時明確呼叫 `distance_3d`。
2. **地圖 JSON 相容**：所有新欄位有預設值，舊地圖 JSON 不需修改即可載入。
3. **TUI 渲染不動**：braille canvas 是 2D，Z 軸只影響 bone_engine 邏輯層。
4. **EventBus 效能**：同步派發，handler 只做 append（不做重計算），延遲格式化。
5. **Prop 不拆類**：在 Prop 上直接加可摧毀欄位，避免型別系統分裂 + 地圖 JSON 結構變動。
6. **Size.MEDIUM 替換風險**：Phase E 改動影響所有碰撞判定，需逐個測試驗證。

---

## 14. 驗證

每個 Phase commit 後：
1. `uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/`
2. `uv run --frozen pytest` — 所有既有 + 新增測試通過
3. Phase F 完成後：`./play.sh` 手動驗證事件流
