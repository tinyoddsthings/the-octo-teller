# 資料模型重構設計文件

> 對應計畫：`models-refactor`（Phases A–E）
> 目的：重構 `src/tot/models.py`（898 行）為多檔案架構，提煉共基類，消除重複邏輯。

---

## 進度總覽

| Phase | 內容 | 狀態 | Commit |
|-------|------|------|--------|
| A | models.py 拆分為 models/ package | ✅ 完成 | `4f4fad1` |
| B | Combatant 基類 + 型別別名統一 | ✅ 完成 | `37fa126` |
| C | Query Methods 集中 + 重複消除 | ✅ 完成 | — |
| C+ | Combatant 型別傳播 + 死程式碼移除 | ✅ 完成 | — |
| D | Spell 子模型 + 死欄位清理 | ✅ 完成 | — |
| E | LLM Context Helpers | ⏸ 延後至 Phase 4 前 | — |

---

## 目標目錄結構

```
src/tot/models/
├── __init__.py       ← 全量 re-export，所有既有 import 路徑不變
├── enums.py          ← 所有 StrEnum + 常數對照表
├── creature.py       ← Combatant 基類 + Character + Monster + Weapon + Item
├── spell.py          ← Spell + SpellComponents + SpellAoe + SpellUpcast
├── map.py            ← Position, Entity, Actor, Prop, Wall, Zone, MapManifest, MapState
├── combat_state.py   ← TurnState, InitiativeEntry, CombatState, MoveEvent, MoveResult, AoePreview
└── exploration.py    ← Pointcrawl（NodeType, ExplorationNode, ExplorationEdge, ...）
```

`__init__.py` 負責完整 re-export，確保 `from tot.models import Character` 等既有路徑不變。

---

## Phase A：檔案拆分 ✅

**Commit** `4f4fad1` — 純搬移，zero functional change。

將 `models.py`（898 行、33 個 class）拆分為 6 個子模組。
`__init__.py` 完整 re-export 所有名稱，337 tests 全過。

---

## Phase B：Combatant 基類 ✅

**Commit** `37fa126` — 提煉共有欄位與行為。

### 變更內容

- 新增 `Combatant(BaseModel)` 基類，提煉 Character/Monster 共有的 11 個欄位：
  `id`, `name`, `size`, `ac`, `speed`, `hp_max`, `hp_current`, `proficiency_bonus`,
  `ability_scores`, `damage_resistances`, `damage_immunities`, `conditions`
- 提煉共有方法：`ability_modifier()`, `has_condition()`
- `Character(Combatant)`：繼承基類，`is_alive` 基於 death_saves + exhaustion
- `Monster(Combatant)`：override `has_condition()` 加入 `condition_immunities` 檢查
- 三處 `Combatant = Character | Monster` 型別別名改為 `from tot.models import Combatant`：
  - `conditions.py`
  - `spells.py`
  - `player_ai.py`（ruff 自動移除多餘的 Character/Monster import）

### 型別關係

```
Combatant(BaseModel)
├── Character   → 有死亡豁免、法術、武器、技能
└── Monster     → 有行動清單、免疫列表、CR
```

---

## Phase C：Query Methods 集中 + 重複消除 ✅

### 完成內容

- **C-1**：`MapState` 新增 `get_actor()` / `get_actor_position()` / `alive_actors()` query methods
- **C-2**：`CombatState` 新增 `current_entry()` query method
- **C-3**：移除 6 處重複 actor lookup（`_find_actor()` / `_find_actor_in_map()` / `_get_actor()` 等），`combat_bridge.get_actor()` 保留為 thin wrapper
- **C-4**：攻擊加值集中 — 4 處 inline/重複計算合併為 `combat.calc_weapon_attack_bonus()` / `calc_damage_modifier()`
- **C-5**：13 處 inline `math.sqrt(...)` 改用 `distance()` / `Position.distance_to()`
- **C-6**：`DAMAGE_TYPE_ZH` 字典去重 — `spells.py` 為 canonical，`combat_bridge.py` import（遵守 bone_engine→tui 架構方向）

---

## Phase C+：Combatant 型別傳播 + 清理 ✅

### 完成內容

- **C+-1**：`_get_size()` / `grapple_save_dc()` / `move_toward_target()` 參數改 `Combatant`
- **C+-1**：`_get_save_bonus()` 移除冗餘 isinstance 分支，直接 `target.ability_scores.modifier(ability)`
- **C+-2**：全 TUI 層 `dict[UUID, Character | Monster]` → `dict[UUID, Combatant]`（app.py / actions.py / combat_bridge.py / canvas.py / log_manager.py / npc_ai.py / stats_panel.py / input_handler.py / combat_runner.py / test_movement.py）
- **C+-3**：刪除死程式碼 — `start_concentration()` / `is_concentrating()`（被 `cast_spell()` inline 取代）+ `resolve_weapon_mastery()` 98 行（整個 codebase 從未呼叫）

---

## Phase D：Spell 子模型 + 死欄位清理 ✅

### 完成內容

- **D-1**：新增 3 個子模型 `SpellComponents` / `SpellAoe` / `SpellUpcast`，`__init__.py` re-export
- **D-2**：刪除 3 個死欄位（`upcast_duration_map` / `upcast_aoe_bonus` / `upcast_no_concentration_at`）+ 移除 `cast_spell()` 中對應的死路 guard
- **D-3**：遷移 ~28 處呼叫點（`aoe.py` / `spells.py` / `app.py` / `test_spells.py`）
- **D-4**：`Spell` 加 `@model_validator(mode='before')` 支援 flat→nested JSON 相容，`spells.json` 無需修改

### Spell 子模型結構

```python
class SpellComponents(BaseModel):
    required: list[str] = []       # ["V", "S", "M"]
    material_description: str = ""
    material_cost_gp: float = 0.0
    material_consumed: bool = False

class SpellAoe(BaseModel):
    shape: AoeShape | None = None
    radius_ft: int = 0
    length_ft: int = 0
    width_ft: int = 0

class SpellUpcast(BaseModel):
    dice: str = ""
    additional_targets: int = 0
```

---

## Phase E：LLM Context Helpers（延後）

> **決定**：此階段與 Phase 2 目標（完整遊戲循環）無關，延後至 Phase 4（LLM 層）前再實作。

內容備忘：
- `Combatant.to_llm_context() -> dict` — Character 完整 / Monster 模糊
- `combat_state_to_llm_context(state, combatant_map) -> dict`
- `map_state_to_llm_context(state, combatant_map) -> dict`

---

## Class 參考

### `enums.py`

| Class | 型別 | 值數 | 用途 |
|-------|------|------|------|
| `Ability` | StrEnum | 6 | STR/DEX/CON/INT/WIS/CHA |
| `Skill` | StrEnum | 18 | 技能列表 |
| `DamageType` | StrEnum | 13 | 傷害類型 |
| `Condition` | StrEnum | 18 | 狀態效果（含 DISENGAGING/DODGING 等非官方） |
| `Size` | StrEnum | 6 | TINY→GARGANTUAN |
| `CreatureType` | StrEnum | 14 | 人形/獸類/不死等 |
| `SpellSchool` | StrEnum | 8 | 法術學派 |
| `CoverType` | StrEnum | 4 | NONE/HALF/THREE_QUARTERS/TOTAL |
| `WeaponMastery` | StrEnum | 8 | 2024 武器專精（CLEAVE/GRAZE/NICK...） |
| `SpellAttackType` | StrEnum | 3 | NONE/MELEE/RANGED |
| `SpellEffectType` | StrEnum | 5 | DAMAGE/HEALING/CONDITION/BUFF/UTILITY |
| `AoeShape` | StrEnum | 4 | SPHERE/CONE/LINE/CUBE |
| `NodeType` | StrEnum | 6 | 探索節點類型 |
| `MapScale` | StrEnum | 3 | DUNGEON/TOWN/WORLD |
| `EncounterType` | StrEnum | 3 | SURPRISE/NORMAL/AMBUSH |

輔助常數：`SKILL_ABILITY_MAP`、`SIZE_RADIUS_M`、`SIZE_ORDER`

### `creature.py`

詳見 Phase B 章節。

### `map.py`

| Class | 說明 |
|-------|------|
| `Position` | 純座標 DTO。`x, y: float`（公尺，cm 精度）。有 `distance_to()` 方法 |
| `Entity(BaseModel)` | 地圖物件基底：`id`, `x`, `y`, `symbol`, `is_blocking`, `name` |
| `Actor(Entity)` | 戰鬥者代理：`combatant_id: UUID` 指向 Character/Monster |
| `Prop(Entity)` | 場景物件：`prop_type`, `hidden`, `description` |
| `Wall(BaseModel)` | AABB 牆壁：`x`, `y`, `width`, `height` |
| `Zone` | 觸發區域 |
| `MapManifest` | 地圖定義（name, width, height, walls, spawn_points, props） |
| `MapState` | 運行時地圖狀態（manifest + walls + actors + props + surfaces） |

**設計說明**：Actor 是地圖層的輕量代理，不直接持有 Character/Monster 物件，
透過 `combatant_id` 查詢。這樣地圖層不需要 import creature 模型，避免循環依賴。

### `combat_state.py`

| Class | 說明 |
|-------|------|
| `TurnState` | 當前回合狀態（movement_remaining, action_used 等） |
| `InitiativeEntry` | 先攻序列項目（combatant_id, initiative） |
| `CombatState` | 戰鬥全局狀態（round, initiative_order, is_active） |
| `MoveEvent` / `MoveResult` | 移動事件/結果 DTO |
| `AoePreview` | AoE 預覽 DTO |

### `spell.py`

詳見 Phase D 章節。

### `exploration.py`

| Class | 說明 |
|-------|------|
| `ExplorationNode` | Pointcrawl 節點 |
| `ExplorationEdge` | 節點間的邊（含 break_dc / noise） |
| `ExplorationMap` | 拓樸地圖 |
| `ExplorationState` | 探索運行時狀態 |
| `DeploymentState` | 佈陣階段狀態 |
