# 空間引擎設計文件

> **來源**：整併自 `bone-engine-v2-design.md` + `spatial-combat-design.md`
> **日期**：2026-03-18
> **對應 todo.md**：Backlog 空間物理強化

## 1. 背景與目標

Bone Engine 目前是 2D 平面戰鬥引擎。為支援多層地形、動態掩護、表面效果等 D&D 2024 規則，
需要擴充事件驅動的狀態管理、Z 軸、表面效果、可摧毀物件、射線掩護等機制。

**原則**：向後相容（新欄位有預設值）、漸進式遷移、bone_engine/ 絕不 import tui/。

---

## 2. 相依圖（未完成的 Phase）

```
Phase A (基礎：事件+模型) ─────────┐
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

**Phase A 部分已完成**：BoundingShape（5 種 ShapeType）、Material/Fragility 列舉、Prop 可摧毀欄位。
**Phase A 未完成**：事件系統（events.py）、雙層 Log（log_layers.py）、材質系統（materials.py）、Position.z、Actor.size/z/bounds、SurfaceEffect、CoverResult。

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

| 欄位 | 型別 | 說明 |
|------|------|------|
| `target_id` | `str` | 受傷者 Actor.id |
| `amount` | `int` | 傷害量（套用抗性/免疫後） |
| `damage_type` | `DamageType` | 傷害類型 |
| `source_id` | `str \| None` | 傷害來源 |
| `is_critical` | `bool` | 是否暴擊 |

#### HealEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `target_id` | `str` | 被治療者 Actor.id |
| `amount` | `int` | 治療量 |
| `source_id` | `str \| None` | 治療來源 |

### 3.4 狀態類事件

#### StatusChangeEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 受影響實體 |
| `condition` | `Condition` | 狀態類型 |
| `action` | `str` | `"applied"` / `"removed"` / `"expired"` |

### 3.5 掩護類事件

#### CoverChangeEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `observer_id` | `str` | 觀察者（攻擊者） |
| `target_id` | `str` | 被觀察者（防禦者） |
| `old_cover` | `CoverType` | 變更前掩護等級 |
| `new_cover` | `CoverType` | 變更後掩護等級 |

### 3.6 表面效果類事件

#### SurfaceEffectEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 觸發者 |
| `surface_id` | `str` | 表面效果 ID |
| `trigger` | `str` | `"enter"` / `"stay"` / `"leave"` |

### 3.7 物件傷害類事件

#### ObjectDamagedEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `object_id` | `str` | 受傷的 Prop.id |
| `damage` | `int` | 傷害量 |
| `damage_type` | `DamageType` | 傷害類型 |
| `hp_remaining` | `int` | 剩餘 HP |

#### ObjectDestroyedEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `object_id` | `str` | 被摧毀的 Prop.id |
| `destroyed_by` | `str \| None` | 摧毀者 ID |

### 3.8 掉落類事件

#### FallingEvent

| 欄位 | 型別 | 說明 |
|------|------|------|
| `entity_id` | `str` | 掉落者 |
| `height_m` | `float` | 掉落高度（公尺） |
| `damage_dice` | `str` | 傷害骰（如 `"3d6"`） |
| `feather_fall` | `bool` | 是否有羽落術保護 |

### 3.9 投射物類事件

#### ProjectileHitCoverEvent

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

## 4. Phase B：表面效果系統

**相依：Phase A 模型**

### B-1：`bone_engine/surfaces.py`

```python
@dataclass
class SurfaceEffectResult:
    surface_id: str
    surface_name: str
    trigger: SurfaceTrigger
    damage_dealt: int = 0
    damage_type: DamageType | None = None
    save_succeeded: bool | None = None
    condition_applied: Condition | None = None

def check_surface_enter(entity_id, old_pos, new_pos, surfaces) -> list[SurfaceEffect]:
    """回傳新進入的 surface 列表（舊位置不在、新位置在的）。"""

def check_surface_leave(entity_id, old_pos, new_pos, surfaces) -> list[SurfaceEffect]:
    """回傳新離開的 surface 列表。"""

def resolve_surface_effect(entity, surface, trigger, *, rng=None) -> SurfaceEffectResult:
    """解算表面效果：豁免→傷害→狀態施加。"""

def tick_surfaces_round_start(surfaces) -> tuple[list, list]:
    """回合開始：remaining_rounds 減 1，過期移除。回傳 (存在, 過期)。"""
```

### B-2：測試覆蓋

進入/離開幾何判定、傷害骰+豁免、狀態施加、持續回合遞減+過期、困難地形。

---

## 5. Phase C：Z 軸地形

**相依：Phase A 模型**

### C-1：spatial.py 加高度邏輯

```python
def check_height_traversal(from_z, to_z, jump_height=0.25) -> HeightCheckResult:
    """≤ 25cm 自動通過；> 25cm 需跳躍/攀爬檢定。"""

def calculate_falling_damage(height_m: float) -> str:
    """每 3m = 1d6，上限 20d6 (= 60m)。"""
```

### C-2：move_entity 擴充

新增 `tz: float | None = None` 參數。當 tz 有值時查 TerrainTile.height_m 做高度差檢查。

### C-3：Actor.size 傳播（spatial.py 硬編碼修正）

`Size.MEDIUM` 硬編碼 → 改用 `actor.size`（move_entity / can_end_move_at / can_traverse）。

### C-4：測試覆蓋

高度通行/掉落傷害/Feather Fall/distance_3d/height_diff。

---

## 6. Phase D：掩護系統強化

> ⚠️ D-1 演算法已更新為 Corner-Ray 模型，詳見附錄 ADR-1

**相依：Phase A 模型 + 材質系統**

### D-1：`determine_cover()` 重寫為 Corner-Ray

攻擊者 AABB 4 角 → 目標 AABB 4 角 = 16 射線，取「最佳角落」。
回傳 `CoverResult`（含掩護物件清單）。

### D-2：combat.py 加投射物打掩護

```python
def resolve_projectile_vs_cover(attack_roll, target_ac, cover_result) -> str | None:
    """遠程 miss 且 roll >= (AC - cover_bonus) → 命中掩護物件。"""
```

### D-3：測試覆蓋

Prop 掩護判定/多重掩護取最大/投射物打掩護/物件摧毀後掩護消失。

---

## 7. Phase E：Actor.size 全面傳播

**相依：Phase A（Actor.size 欄位）**

### E-1：place_actors_at_spawn 設定 size + bounds

從 Character/Monster 讀取 `size` → 設定到 `Actor.size` 和 `Actor.bounds`。

### E-2：spatial.py 碰撞判定改用 bounds.overlaps()

散落 16 處 `SIZE_RADIUS_M.get(...)` → 統一 `actor.bounds.overlaps(...)`。

### E-3：pathfinding.py + movement.py 改用 bounds.to_aabb()

Minkowski inflation 用真實 mover_size。

### E-4：更新既有測試

所有 Actor fixture 加 `size=Size.MEDIUM, bounds=BoundingShape.from_size(Size.MEDIUM)`。

---

## 8. Phase F：GameStateManager + 事件整合

**相依：所有前置 Phase**

### F-1：`bone_engine/game_state.py`

`GameStateManager` 包裝 MapState + CombatState + EventBus。
所有狀態變更經由此 manager 自動 emit 事件。

核心方法：
- `move_actor()` — 移動 + 表面效果觸發 + emit 事件
- `apply_damage_to_combatant()` — 傷害 + emit
- `apply_damage_to_object()` — 物件傷害 + 摧毀判定 + emit
- `apply_healing()` / `apply_condition()` — 治療/狀態 + emit
- `tick_surfaces()` — 回合開始更新表面效果

### F-2：TUI 整合（漸進式）

一次只遷移一個 action function：
1. `app.py` 建立 `GameStateManager` 實例
2. `NarrativeLog.pop_new_messages()` 接入 `LogManager`
3. 逐步將 `actions.py` / `npc_ai.py` 改為透過 manager

### F-3：測試覆蓋

狀態變更→事件、NarrativeLog 可讀文字、SystemLog 完整記錄、移動觸發表面效果、物件摧毀觸發掩護變更。

---

## 9. 事件流範例

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
    → CoverResult(HALF, cover_objects=["wooden_crate"])
  → resolve_attack(roll=14, target_ac=16)  → miss
  → resolve_projectile_vs_cover(14, 16, cover_result)
    → 14 >= (16-2) → 命中木箱
  → apply_damage_to_object(wooden_crate, projectile_dmg)
  → emit(ProjectileHitCoverEvent)
  → if hp_current <= 0: emit(ObjectDestroyedEvent), emit(CoverChangeEvent)
```

---

## 附錄：空間戰鬥幾何 ADR

> 來源：`spatial-combat-design.md` v1.0（2026-03-13）

### ADR-1：掩蔽判定射線模型（Cover Ray Model）— HIGH

**現況**：`determine_cover()` 使用單條中心→中心射線 + 障礙物計數法。
**選定方案**：改為 **Corner-Ray**（攻擊者 4 角 → 目標 4 角 = 16 射線），取最佳角落。

判定規則：
- 4/4 通過 → NONE
- 3/4 通過 → HALF (+2 AC)
- 1-2/4 通過 → THREE_QUARTERS (+5 AC)
- 0/4 通過 → TOTAL（無法瞄準）

效能：16 rays × N obstacles，Liang-Barsky 單次 ~10ns → <10μs。
LoS 維持 center→center 單射線（二元判定）。

### ADR-2：動態路徑障礙 — LOW

**現況**：已大半實作（can_traverse 敵/友區分、blocked/passable 分離、passable cost ×2、死亡 Actor 過濾）。
**選定方案**：維持現狀 + docstring 補強。

### ADR-2.5：強制位移路徑碰撞檢測（Forced Movement CCD）— MEDIUM

**問題**：強制位移（推/法術）繞過 A* 路徑規劃，可能穿牆。
**選定方案**：`move_entity()` 加 `forced=True` 參數，用 `segment_aabb_intersect()` 掃描起終點路徑，碰牆停在牆前（Liang-Barsky 最近交點）。

### ADR-3：Braille 長寬比 — NONE（已驗證非問題）

Braille 2×4 矩陣天然補償終端字元 ~2:1 長寬比，每個 dot 近似正方形。

### ADR-4：距離計算哲學 — NONE

**選定方案**：維持純歐氏距離。連續空間中無格線，斜走懲罰自然消失。
UI 層做 5 呎 snap 顯示供玩家參考。
