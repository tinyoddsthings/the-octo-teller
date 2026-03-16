# 渲染架構重構 + Prop Prefab 系統設計文件

> **對應 todo：** `2-XB`（最高優先）
> **計畫詳情：** [`.claude-personal/plans/parallel-nibbling-whale.md`](../.claude-personal/plans/parallel-nibbling-whale.md)

---

## 一、問題背景

### 目前架構的缺陷

```
MapState  ─────────────────────────────►  BrailleMapCanvas
          直接讀取、直接渲染（無中介層）
```

1. **Entity.symbol 污染模型層**
   `Entity.symbol = "?"` 和 `Wall.symbol = "#"` 讓「視覺符號」存活在骨幹引擎的資料模型裡，違反 MVC 分層原則。不同渲染器（Drawille vs ASCII）對同一個實體需要不同視覺呈現，但模型只能存一個值。

2. **渲染邏輯散落在 TUI Widget**
   `BrailleMapCanvas.render()` 同時負責座標轉換、形狀判斷、顏色決定、標籤計算，難以測試，也難以加新功能（縮放、視角平移、迷霧等）。

3. **Prop 定義高度重複**
   地圖 JSON 每次放一個石柱就要重複定義 `is_blocking`、`cover_bonus`、`material`、`hp`、`bounds`。目前 17 個 props 裡有大量重複，每個完整定義約 180~250 bytes，可以壓縮到 40 bytes（prefab_id + 座標）。

4. **ASCII 渲染器成為孤島**
   `src/tot/visuals/map_renderer.py` 僅被 `combat_logger.py` 使用，且依賴 `Entity.symbol`。移除 symbol 後它就無法維持，且 `canvas.py` 已有 `render_braille_map()` 可替代其功能。

---

## 二、目標架構

### 三層分離

```
MapState（模型層）
    │  entity 屬性、物理規則、戰鬥狀態
    │
    ▼  RenderBuffer.build(map_state, combatant_map, aoe)
    │
RenderBuffer（中介層）    ← 此次新增
    │  items: list[RenderItem]，按 layer 排序
    │  每個 item 有 bounds + texture（繪製模式）
    │  未來支援 viewport 參數（camera_x/y，zoom）
    │
    ▼  BrailleMapCanvas 讀 render_buffer.items
    │
BrailleMapCanvas（TUI Widget）
    只管「怎麼畫」，不再直接讀 MapState
```

### Prop Prefab 系統

```
PROP_PREFABS（Python dict registry）
    stone_pillar, wooden_door, wall_torch, ...
    │  定義物件的物理屬性（一份）
    │
    ▼  loader._expand_props()
    │
地圖 JSON（只含 prefab_id + 位置 + 覆蓋值）
    {"id":"pillar_1","prefab_id":"stone_pillar","x":6.0,"y":8.0}
```

---

## 三、Phase 0：移除 Entity.symbol

### 動機

Emoji（🧙、👹）是「哪個角色是哪個人」的純 TUI 視覺資訊，不應存在骨幹引擎的資料模型中。移除後由 `CombatTUI` 維護 `emoji_map: dict[UUID, str]`，鍵為 `combatant_id`。

### 資料流變更

**現在：**
```python
# demo.py
Actor(id=str(char.id), symbol="🧙", ...)

# stats_panel.py
actor = get_actor(entry.combatant_id, map_state)
emoji = actor.symbol if actor else "?"
```

**改後：**
```python
# demo.py
emoji_map[char.id] = "🧙"
Actor(id=str(char.id), ...)            # 無 symbol
return chars, mons, map_state, cs, emoji_map   # 5-tuple

# stats_panel.py
emoji = emoji_map.get(entry.combatant_id, "?")
```

### emoji_map 的 key 選擇

使用 `combatant_id: UUID` 而非 actor string id，因為：
- `stats_panel` 從 `combat_state.initiative_order[i].combatant_id` 開始查
- `input_handler` 從 `m[0].id`（Monster.id，UUID 型別）查
- 統一用 UUID 可避免不同地方用不同 key scheme 的混淆

### 刪除 ASCII 渲染器

`map_renderer.py` 的所有功能可被 `canvas.py:render_braille_map()` 取代：
- `render_full()` → `render_braille_map(map_state, combatant_map, w, h)`
- `describe_cell()` → 不再使用（exploration TUI 有自己的描述邏輯）

`combat_logger.py` 唯一使用者，改用：
```python
from tot.tui.canvas import render_braille_map
rendered = render_braille_map(map_state, {}, w=60, h=20)
```

---

## 四、Phase 1：Prop Prefab Registry

### 設計原則

- **Prefab = 物件類別的預設物理屬性**（不含 symbol、不含位置、不含 id）
- **地圖 JSON = prefab_id + 位置 + 實例覆蓋值**（只寫「不同的部分」）
- **Loader 展開**：讀 JSON → `_expand_props()` 深拷貝模板 + 覆蓋 → Pydantic 驗證

### Prefab 模組結構

```
src/tot/data/prop_defs/
    __init__.py          # PROP_PREFABS = {**STRUCTURAL, **INTERACTIVE, **TERRAIN}
    structural.py        # 建築結構物件
    interactive.py       # 可互動物品
    terrain.py           # 地形特徵
```

### 各類別 Prefab 定義

#### structural.py — 建築結構

| prefab_id | name | is_blocking | cover_bonus | material | AC | HP | size |
|-----------|------|:-----------:|:-----------:|----------|:--:|:--:|------|
| `stone_pillar` | 石柱 | ✓ | 5 | STONE | 17 | 27 | LARGE |
| `wooden_door` | 木門（開） | ✗ | 2 | WOOD | 15 | 18 | LARGE |
| `iron_gate_locked` | 鐵柵門（鎖） | ✓ | 2 | IRON | 19 | 0（不可摧毀） | LARGE |
| `wall_torch` | 壁掛火把 | ✗ | 0 | IRON | 19 | 2 | TINY |

HP 計算依 D&D 2024 DMG：`OBJECT_HP_DICE[size] × FRAGILITY_HP_MULTIPLIER[fragility]`，以平均值取整。

#### interactive.py — 可互動物品

| prefab_id | name | is_blocking | interactable | investigation_dc | prop_type |
|-----------|------|:-----------:|:------------:|:----------------:|-----------|
| `stone_chest` | 石箱 | ✗ | ✓ | 12 | item |
| `glowing_mushrooms` | 發光蘑菇群 | ✗ | ✓ | 0 | item |

#### terrain.py — 地形特徵（不可摧毀）

| prefab_id | name | terrain_type | is_blocking | bounds 預設 |
|-----------|------|-------------|:-----------:|-------------|
| `rubble_zone` | 碎石區 | rubble | ✗ | rect(3.0, 2.0) |
| `water_pool` | 水池 | water | ✗ | circle(2.5) |
| `hill` | 高台 | hill | ✗ | rect(2.0, 1.5) |
| `crevice` | 裂縫 | crevice | ✗ | rect(1.5, 2.0) |

地形 prefab 無 material/HP，代表不可摧毀。

### 展開邏輯

```python
def _expand_props(raw_props: list[dict]) -> list[dict]:
    """展開 prefab_id：深拷貝模板 + 實例覆蓋。"""
    result = []
    for entry in raw_props:
        prefab_id = entry.pop("prefab_id", None)
        if prefab_id:
            if prefab_id not in PROP_PREFABS:
                raise ValueError(f"未知的 prefab_id：{prefab_id}")
            merged = {**copy.deepcopy(PROP_PREFABS[prefab_id]), **entry}
            result.append(merged)
        else:
            result.append(entry)   # 無 prefab_id 的 prop 直接傳遞
    return result
```

**呼叫位置**：`load_map_manifest()` 中，在 `MapManifest(**raw)` 之前：
```python
raw["props"] = _expand_props(raw.get("props", []))
```

### 地圖 JSON 範例

```json
// 展開前（地圖 JSON）
{"id": "pillar_1", "prefab_id": "stone_pillar", "x": 6.0, "y": 8.0, "name": "天然石柱"}

// 展開後（進入 Pydantic）
{
  "id": "pillar_1", "x": 6.0, "y": 8.0, "name": "天然石柱",
  "is_blocking": true, "prop_type": "decoration", "cover_bonus": 5,
  "material": "Stone", "object_ac": 17, "object_size": "Large",
  "fragility": "Resilient", "hp_max": 27, "hp_current": 27,
  "bounds": {"shape_type": "circle", "radius_m": 0.5}
}
```

---

## 五、Phase 2：RenderBuffer 中介層

### 渲染圖層（由下到上）

```python
class RenderLayer(IntEnum):
    GRID    = 0   # 刻度線背景
    TERRAIN = 1   # 地形區域（碎石、水池、高台）
    WALL    = 2   # 牆壁
    PROP    = 3   # 靜態物件（門、柱、火把）
    ACTOR   = 4   # 角色、怪物
    AOE     = 5   # 範圍效果覆蓋
```

### 紋理類型

```python
class TextureType(StrEnum):
    FILL            = "fill"             # 填滿矩形（阻擋型方形 prop）
    OUTLINE         = "outline"          # 矩形外框（非阻擋型方形 prop）
    CIRCLE_FILL     = "circle_fill"      # 填滿圓（阻擋型圓形 prop）
    CIRCLE_OUTLINE  = "circle_outline"   # 圓形外框（非阻擋型圓形 prop）
    ACTOR_CIRCLE    = "actor_circle"     # PC（圓形，21 dots）
    ACTOR_DIAMOND   = "actor_diamond"    # 怪物（菱形，13 dots）
    ACTOR_X         = "actor_x"          # 死亡（X 形，9 dots）
    SPARSE          = "sparse"           # AoE 稀疏填充
```

### 紋理決定邏輯

```python
def _prop_texture(prop: Prop) -> TextureType:
    is_circle = prop.bounds and prop.bounds.shape_type == ShapeType.CIRCLE
    if prop.is_blocking:
        return TextureType.CIRCLE_FILL if is_circle else TextureType.FILL
    return TextureType.CIRCLE_OUTLINE if is_circle else TextureType.OUTLINE

def _actor_texture(actor: Actor) -> TextureType:
    if not actor.is_alive:                         return TextureType.ACTOR_X
    if actor.combatant_type == "character":        return TextureType.ACTOR_CIRCLE
    return TextureType.ACTOR_DIAMOND
```

### RenderItem 資料結構

```python
@dataclass
class RenderItem:
    entity_id: str
    layer:     RenderLayer
    center_x:  float          # 公尺座標
    center_y:  float
    bounds:    BoundingShape   # 形狀 + 尺寸
    texture:   TextureType
    style:     str = ""        # Rich color style（標籤、高亮）
    label:     str = ""        # 文字標籤（actor 名字等）
```

### RenderBuffer 生命週期

```python
class RenderBuffer:
    def __init__(self, world_w: float, world_h: float):
        self.world_w = world_w
        self.world_h = world_h
        self.items: list[RenderItem] = []
        # 視口參數（此次預設全地圖，未來擴充用）
        self.camera_x: float = world_w / 2
        self.camera_y: float = world_h / 2
        self.viewport_w: float = world_w
        self.viewport_h: float = world_h

    def build(self, ms: MapState, combatant_map: dict, aoe=None) -> None:
        self.items.clear()
        self._add_walls(ms)
        self._add_props(ms)
        self._add_actors(ms, combatant_map)
        if aoe:
            self._add_aoe(aoe)
        self.items.sort(key=lambda i: i.layer)
```

### BrailleMapCanvas 修改

**新增 reactive：**
```python
render_buffer: reactive[RenderBuffer | None] = reactive(None)
```

**新 render() 主體（簡化後）：**
```python
def render(self) -> Text:
    buf = self.render_buffer
    if not buf:
        return Text("（等待地圖資料…）")

    scale = self._compute_scale(draw_w, draw_h, buf.world_w, buf.world_h)
    canvas = Canvas()

    for item in buf.items:
        self._draw_item(canvas, item, scale, canvas_h)

    # 標籤、軸刻度（保留現有邏輯）
    ...
```

**`_draw_item()` 紋理分派：**
```python
def _draw_item(self, canvas, item: RenderItem, scale, canvas_h):
    match item.texture:
        case TextureType.FILL:           self._fill_rect(...)
        case TextureType.OUTLINE:        self._outline_rect(...)
        case TextureType.CIRCLE_FILL:    self._fill_circle(...)
        case TextureType.CIRCLE_OUTLINE: self._outline_circle(...)
        case TextureType.ACTOR_CIRCLE:   self._draw_offsets(..., _CIRCLE_OFFSETS)
        case TextureType.ACTOR_DIAMOND:  self._draw_offsets(..., _DIAMOND_OFFSETS)
        case TextureType.ACTOR_X:        self._draw_offsets(..., _X_OFFSETS)
        case TextureType.SPARSE:         self._sparse_fill(...)
```

### App 層整合

```python
# app.py _refresh_map()
def _refresh_map(self) -> None:
    if not self.map_state:
        return
    for actor in self.map_state.actors:
        combatant = self._combatant_map.get(actor.combatant_id)
        if combatant:
            actor.is_alive = combatant.is_alive

    buf = RenderBuffer(
        self.map_state.manifest.width,
        self.map_state.manifest.height,
    )
    buf.build(self.map_state, self._combatant_map, self._aoe_overlay)
    canvas = self.query_one("#map-panel", BrailleMapCanvas)
    canvas.render_buffer = buf
```

---

## 六、Phase 3：整合 render_braille_map()

`render_braille_map()`（canvas.py:777）和 `render_to_plain()`（canvas.py:729）的內部實作改用 `RenderBuffer`，對外介面不變，確保 `combat_logger.py` 和測試不受影響。

---

## 七、Phase 4：測試

### 新增測試

#### `tests/test_prop_prefab.py`
- `test_basic_prefab_expansion` — stone_pillar 展開後有正確 AC/HP/bounds
- `test_instance_overrides_prefab` — 實例值覆蓋模板值
- `test_unknown_prefab_raises` — 未知 prefab_id 拋 ValueError
- `test_no_prefab_passthrough` — 無 prefab_id 的 prop 直接傳遞
- `test_map_load_expands_props` — `load_map_manifest("tutorial_room")` 後 props 已展開

#### `tests/test_render_buffer.py`
- `test_walls_produce_render_items` — wall 轉為 RenderLayer.WALL item
- `test_prop_texture_assignment` — blocking circle prop → CIRCLE_FILL
- `test_actor_textures` — PC → ACTOR_CIRCLE，monster → ACTOR_DIAMOND，dead → ACTOR_X
- `test_layer_order_sorted` — items 按 layer 升序排列
- `test_aoe_layer_on_top` — AoE items 在 ACTOR 之上

### 修改既有測試

| 測試檔 | 修改 |
|--------|------|
| `tests/test_aoe.py` | Actor fixture 移除 `symbol=` |
| `tests/test_geometry.py` | Prop/Actor fixture 移除 `symbol=` |
| `tests/test_spatial.py` | Prop/Actor fixture 移除 `symbol=` |
| `tests/test_area_explore.py` | 確認 prefab 展開後探索功能不受影響 |

---

## 八、重用的現有函式

| 函式 | 位置 | 用途 |
|------|------|------|
| `_fill_rect()` | canvas.py:220 | 矩形填滿（牆壁、方形阻擋 prop） |
| `_outline_rect()` | canvas.py:240 | 矩形外框（非阻擋方形 prop） |
| `_meter_to_px()` | canvas.py | 公尺座標 → 像素座標 |
| `_compute_scale()` | canvas.py:133 | 保持長寬比縮放計算 |
| `_CIRCLE_OFFSETS` | canvas.py:70 | PC 圓形（21 dot offsets） |
| `_DIAMOND_OFFSETS` | canvas.py:82 | 怪物菱形（13 dot offsets） |
| `_X_OFFSETS` | canvas.py:93 | 死亡 X 形（9 dot offsets） |
| `_sparse_fill_polygon()` | canvas.py:506 | AoE 稀疏填充 |
| `render_braille_map()` | canvas.py:777 | 純文字渲染（替代 MapRenderer） |
| `BoundingShape.circle()` / `.rect()` | shapes.py | 形狀工廠方法 |
| `BoundingShape.contains_point()` | shapes.py | 碰撞/命中判定 |

---

## 九、驗證方式

```bash
# 1. Lint
uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/

# 2. 新增測試
uv run pytest tests/test_prop_prefab.py tests/test_render_buffer.py -v

# 3. 全測試通過
uv run pytest

# 4. 戰鬥 TUI 驗證（RenderBuffer 替換透明）
./play.sh

# 5. 探索 TUI 驗證（prefab 載入 + 多形狀渲染）
./explore.sh  # 選 ruins
```

---

## 九之一、Prop Bounds 完整化（Phase 2-XD）

### Size/Bounds 分離

**問題**：`_size_to_render_bounds(object_size)` 用 D&D 生物體型推導物件渲染尺寸，
語意混淆且 3 段分支不直覺。

**解法**：
- 所有有 `material` 的 prefab 補上 explicit `bounds`
- 移除 `_size_to_render_bounds()`
- 無 bounds 的 inline prop 統一 fallback `_INLINE_PROP_FALLBACK_BOUNDS = BoundingShape.rect(1.0, 1.0)`
- `geometry.py` `_PROP_HALF` 同步從 0.75→0.5（對齊 1.0m）

### 物件免疫/抗性（D&D 2024 DMG）

| 材質 | 免疫 | 抗性 |
|------|------|------|
| 所有（有 material） | Poison, Psychic | — |
| STONE | Poison, Psychic | Piercing |
| IRON | Poison, Psychic | Piercing, Slashing |
| WOOD | Poison, Psychic | — |

### 邊緣距離互動

`INTERACT_RADIUS_M = 0.5`（邊緣到邊緣），取代舊的 3.0m 中心距離。
`_edge_gap(actor, prop)` 依 prop bounds 類型計算：
- 無 bounds → 點（center_dist - actor_r）
- CIRCLE → center_dist - actor_r - prop_r
- RECTANGLE → clamp 法找最近點 - actor_r

---

## 十、未來擴充（此次不實作）

| 功能 | 實作方式 |
|------|---------|
| **視角平移** | 調整 `RenderBuffer.camera_x/y`，`_draw_item()` 做 offset 計算 |
| **縮放** | 調整 `RenderBuffer.viewport_w/h`，重算 scale |
| **迷霧戰爭** | `build()` 前過濾 RenderItems（超出 LOS 的移除或換 SPARSE texture） |
| **進階紋理** | 新增 `HATCHED`（斜線地形）、`DOTTED`（點狀）、`WAVE`（水面） |
| **滑鼠 hit-test** | `RenderBuffer.item_at(px_x, px_y)` → entity lookup |
| **Minimap** | 同一個 RenderBuffer，以更小的 scale 渲染到角落 Widget |
