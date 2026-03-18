# Adventure Author MD 格式規格

本文件定義 Adventure Author 工具的完整 Markdown 語法。
所有冒險內容必須嚴格遵循此格式，才能通過 `adventure-author validate` 和 `adventure-author build`。

---

## 1. 冒險資料夾結構

```
adventures/<adventure_id>/
├── _meta.md              # 冒險基本資訊
├── maps/                 # 地圖（可多張）
│   ├── village.md
│   ├── road.md
│   └── dungeon.md
├── npcs/                 # NPC（一個 NPC 一份）
│   ├── quinn.md
│   └── shopkeeper.md
├── scenes/               # 場景（多角色互動對話）
│   ├── encounter_intro.md
│   └── group_discussion.md
└── chapters/             # 章節（按順序編號）
    ├── 01_arrival.md
    └── 02_investigation.md
```

---

## 2. `_meta.md` — 冒險概述

```markdown
---
id: peril_in_pinebrook
name: 危在松溪
description: 松溪村的牲畜失蹤了，冒險者們需要調查原因。
---

<!-- 初始 flag（選填，冒險開始時自動設定） -->
initial_flags:
- patrol_assigned: 1
- trust_level: 3
```

### 必填欄位
| 欄位 | 說明 |
|------|------|
| `id` | 冒險唯一 ID（snake_case） |
| `name` | 冒險名稱 |

### 選填欄位
| 欄位 | 說明 |
|------|------|
| `description` | 冒險簡介 |
| `initial_flags` | 初始 flag 清單（`- flag_name: value`） |

---

## 3. `maps/*.md` — 地圖

### 3.1 Frontmatter

```markdown
---
id: pinebrook_village
name: 松溪村
scale: town          # town / world / dungeon
entry: village_square
---
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `id` | ✅ | 地圖唯一 ID |
| `name` | ✅ | 地圖名稱 |
| `scale` | ✅ | `town` / `world` / `dungeon` |
| `entry` | ✅ | 入口節點 ID |

### 3.2 節點語法

```markdown
## 節點名稱 #node_id
type: room
description: 這是一個房間。
ambient: 水滴聲迴盪。
```

**中文名稱必須附帶 `#id`**：
```markdown
## 城鎮中心 #town_center
## 洞穴入口 #cave_entrance
```

**ASCII 名稱可省略 `#id`**（自動 slugify）：
```markdown
## Guard Room
<!-- 自動生成 id = guard_room -->
```

#### 節點屬性

| 屬性 | 必填 | 說明 |
|------|------|------|
| `type` | ✅ | 節點類型（見下表） |
| `description` | 建議 | 場景描述（給 Narrator 用） |
| `ambient` | 選填 | 環境氛圍（聲音、氣味） |
| `combat_map` | 選填 | 戰鬥地圖 JSON 檔名 |
| `sub_map` | 選填 | 子地圖 ID（world→town/dungeon） |
| `npcs` | 選填 | NPC ID 列表（逗號分隔） |

#### 節點類型

| type | 用途 | 常見 scale |
|------|------|-----------|
| `town` | 城鎮（含 POI 子節點） | town |
| `poi` | 城鎮內的興趣點 | town |
| `landmark` | 地標 | world |
| `dungeon` | 地城入口 | world |
| `room` | 房間 | dungeon |
| `corridor` | 走廊 | dungeon |
| `cavern` | 洞穴 | dungeon |

### 3.3 POI（城鎮子節點）

只在 `scale: town` 的節點下使用：

```markdown
## 城鎮中心 #town_center
type: town
description: 小鎮的中心廣場。

pois:
- 酒館 #tavern | poi
  熱鬧的酒館。
  npcs: bartender
- 鐵匠鋪 #blacksmith | poi
  敲打聲不斷。
  npcs: smith, apprentice
```

### 3.4 物品（可搜索/拾取）

```markdown
items:
- 生鏽鑰匙 #rusty_key | item | dc:12
  藏在石板下方的鑰匙。
  grants_key: rusty_key
- 寶箱 #treasure_chest | chest | dc:0
  一個沒上鎖的木箱。
  value_gp: 50
- 腳印 #footprints | clue | dc:10
  地上有奇怪的足跡。
```

#### 物品語法
```
- 名稱 #id | type | dc:N
  描述文字
  grants_key: key_id    （拿取後獲得鑰匙，選填）
  value_gp: N           （金幣價值，選填）
```

| type | 說明 |
|------|------|
| `item` | 一般物品 |
| `clue` | 線索 |
| `chest` | 寶箱 |
| `trap_hint` | 陷阱提示 |

### 3.5 邊（路徑）

```markdown
### → 目標節點名稱 #edge_id
to: target_node_id
from: source_node_id
distance: 2min           # 地城用 min，世界用 day
```

**注意**：邊定義的位置不重要，但慣例放在 `from` 節點的 `##` 區塊之後。

#### 邊屬性

| 屬性 | 必填 | 說明 |
|------|------|------|
| `to` | ✅ | 目標節點 ID |
| `from` | ✅ | 來源節點 ID |
| `distance` | 建議 | 距離（`Nmin` 或 `N.Nday`） |

#### 通行條件（選填）

| 屬性 | 說明 |
|------|------|
| `locked: key_id` | 上鎖（需要鑰匙 ID） |
| `lock_dc: N` | 開鎖 DC |
| `break_dc: N` | 破門 STR DC |
| `hidden_dc: N` | 隱藏通道偵察 DC |
| `one_way: true` | 單向通道 |
| `jump_dc: N` | 跳躍 DC |
| `fall_damage: true` | 失敗時墜落受傷 |

#### 世界圖層（選填）

| 屬性 | 說明 |
|------|------|
| `terrain: 泥土路` | 地形類型 |
| `danger_level: 5` | 危險等級 1-10 |

### 3.6 遭遇（Encounter）

地城節點內的遭遇區塊。遭遇是**空間綁定**的——敵人在特定房間，進入即觸發。

```markdown
## 巢穴 #dragon_nest
type: room
description: 一個寬敞的洞室，中央有一堆閃亮的小物品圍成的窩。

encounter:
  enemies:
  - 幼藍龍 #young_blue_dragon | CR:2
    一隻藍色的小龍，蜷縮在窩裡。
  - 冰凍蜥蜴 #ice_lizard | CR:1/4
    兩隻結冰的蜥蜴，在角落嘶嘶作響。
    count: 2
  trigger: enter_node
  narration: 幼龍猛然抬起頭，發出一聲低吼。
  outcome: auto_win
  rewards:
  - 龍鱗碎片 #dragon_scale_piece | value_gp: 10
  - 經驗值 #encounter_xp | xp: 450
  sets_flag: dragon_defeated
```

#### encounter 結構

| 欄位 | 必填 | 說明 |
|------|------|------|
| `enemies` | ✅ | 敵人列表 |
| `trigger` | 選填 | 觸發方式（預設 `enter_node`） |
| `narration` | 建議 | 遭遇描述文字 |
| `outcome` | 選填 | `auto_win`（現階段）/ `combat`（未來） |
| `rewards` | 選填 | 獎勵列表 |
| `sets_flag` | 建議 | 勝利後設定的 flag |

#### enemies 語法
```
  - 敵人名稱 #enemy_id | CR:N
    描述文字（選填）
    count: N              （數量，預設 1）
```

CR 格式：`CR:2`、`CR:1/4`、`CR:1/2`

#### rewards 語法
```
  - 物品名稱 #item_id | value_gp: N
  - 經驗值 #xp_id | xp: N
```

#### 引擎行為（現階段 `outcome: auto_win`）

1. 進入節點 → 顯示 encounter narration
2. 自動標記勝利 → sets_flag
3. 給獎勵（items + xp）
4. 不跑戰鬥引擎

#### 引擎行為（未來 `outcome: combat`）

1. 進入節點 → 載入同一空間的 Area 地圖
2. 生成敵人（用 spawn_points + enemy CR）
3. 跑完整戰鬥引擎
4. 勝利後 sets_flag + 給獎勵

---

## 4. `npcs/*.md` — NPC

```markdown
---
id: quinn
name: 乖因
---

## 背景
description: 焦慮的小精靈。
location: village_square
personality: 膽小但善良。
role: quest_giver

## 常態對話 #quinn_idle

> 你有看到奇怪的東西嗎？

## 初次見面 #quinn_intro
map: pinebrook_village
condition: not:talked_to_quinn

> 你好，冒險者！

choices:
- **「怎麼回事？」** #quinn_ask → quinn_explain
  sets_flag: asked_quinn
- **「我沒空。」** #quinn_refuse → quinn_sad

## 解釋 #quinn_explain
condition: has:asked_quinn

> 山洞裡有什麼東西在搗亂。

sets_flag: quest_accepted
```

### 4.1 Frontmatter

| 欄位 | 必填 | 說明 |
|------|------|------|
| `id` | ✅ | NPC 唯一 ID（snake_case） |
| `name` | ✅ | NPC 名稱 |

### 4.2 `## 背景` 區塊

| 屬性 | 必填 | 說明 |
|------|------|------|
| `description` | 建議 | 外觀描述 |
| `location` | 建議 | 初始所在節點 ID |
| `personality` | 選填 | 個性描述 |
| `role` | 選填 | 角色定位（quest_giver/merchant/guard…） |

### 4.3 對話語法

```markdown
## 對話標題 #dialogue_id
map: map_id              （在哪張地圖觸發，選填）
chapter: 02              （語法糖，= has:chapter_02，選填）
condition: has:some_flag  （觸發條件，選填）

> NPC 說的話（可多行）
> 第二行文字

sets_flag: flag_name      （說完後設定 flag，選填）

choices:
- **「選項文字」** #choice_id → next_dialogue_id
  sets_flag: flag_name
```

#### 對話類型
- **常態對話**（`## 常態對話 #id`）：無條件，隨時可觸發
- **情境對話**（`## 任意標題 #id`）：有 condition/map/chapter 限制

#### 選項語法
```
- **「選項文字」** #choice_id → next_dialogue_id
  sets_flag: flag_name    （選填）
```

- `#choice_id`：此選項的 ID
- `→ next_dialogue_id`：選擇後跳到的對話 ID
- `sets_flag`：選擇後設定的 flag

### 4.4 技能檢定語法（`skill_check:`）

對話中可嵌入技能檢定，取代 choices。檢定結果跳轉到不同對話。

```markdown
## 偵查 #scout_check
speaker: dm

> 你仔細觀察四周……

skill_check:
  skill: Perception
  dc: 12
  pass: scout_success
  fail: scout_fail
  hidden_dc: true
  assists:
  - 導引術 #guidance | evendorn | 1d4 | concentration
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `skill` | ✅ | 技能名稱（如 Perception, Nature, Survival） |
| `dc` | ✅ | 難度等級 |
| `pass` | ✅ | 成功跳轉的對話 ID |
| `fail` | ✅ | 失敗跳轉的對話 ID |
| `hidden_dc` | 選填 | `true` = 暗骰，不顯示 DC（預設 false） |
| `assists` | 選填 | 輔助法術列表 |

#### assists 語法
```
  - 法術名稱 #spell_id | source_npc | bonus_die_or_advantage | concentration
```

### 4.5 無選項串接語法（`next:`）

對話段落可用 `next:` 直接串接到下一段對話，不需要 choices。

```markdown
## 旁白 #narration_01
speaker: dm

> 你們沿著小路來到洞穴口。

next: narration_02
```

`next: dialogue_id` 可跨 NPC 和場景檔案引用。

---

## 5. `chapters/*.md` — 章節

```markdown
---
chapter: 1
title: 抵達松溪
---

## 開場白 #opening
trigger: enter_node village_square
once: true

> 你踏入松溪村，空氣中瀰漫著不安的氣氛。

- tutorial: 輸入 `look` 查看環境。
- set_flag: arrived_pinebrook

## 接受任務 #quest_start
trigger: flag_set quest_accepted
condition: has:arrived_pinebrook
once: true

> 乖因感激地點了點頭。

- reveal_edge: to_forest
- move_npc: quinn → forest_path
- set_flag: patrol_started
```

### 5.1 Frontmatter

| 欄位 | 必填 | 說明 |
|------|------|------|
| `chapter` | ✅ | 章節編號（如 `1`、`02`） |
| `title` | ✅ | 章節標題 |

### 5.2 事件語法

```markdown
## 事件名稱 #event_id
trigger: <type> <target>
condition: <condition_expr>
once: true

> 旁白文字（可多行）

- action_type: params
```

### 5.3 觸發類型

| trigger | 格式 | 說明 |
|---------|------|------|
| `enter_node` | `trigger: enter_node node_id` | 進入節點時 |
| `take_item` | `trigger: take_item item_id` | 拿取物品時 |
| `flag_set` | `trigger: flag_set flag_name` | flag 被設定時 |
| `talk_end` | `trigger: talk_end dialogue_id` | 對話結束時 |

### 5.4 動作類型

| action | 格式 | 說明 |
|--------|------|------|
| `narrate` | `- narrate: 文字` | DM 旁白（也可用 `> ` 語法） |
| `tutorial` | `- tutorial: 文字` | 教學提示 |
| `set_flag` | `- set_flag: flag_name` | 設定 flag = 1 |
| `set_flag` | `- set_flag: flag_name = N` | 設定 flag = N |
| `inc_flag` | `- inc_flag: flag_name + N` | flag 增加 N |
| `reveal_node` | `- reveal_node: node_id` | 揭示隱藏節點 |
| `reveal_edge` | `- reveal_edge: edge_id` | 揭示隱藏路徑 |
| `move_npc` | `- move_npc: npc_id → node_id` | 移動 NPC |
| `add_item` | `- add_item: item_id` | 給予物品 |
| `start_timer` | `- start_timer: flag_name` | 開始計時 |
| `clear_timer` | `- clear_timer: flag_name` | 清除計時 |
| `start_scene` | `- start_scene: scene_id` | 啟動場景對話 |

### 5.5 條件表達式

| 語法 | 說明 |
|------|------|
| `has:flag` | flag 存在（值 >= 1） |
| `not:flag` | flag 不存在 |
| `all:cond1,cond2` | 全部滿足 |
| `any:cond1,cond2` | 任一滿足 |
| `gte:flag:N` | flag >= N |
| `lt:flag:N` | flag < N |
| `within:flag:N` | 設定 flag 後 N 分鐘內 |
| `elapsed:N` | 遊戲已過 N 分鐘 |
| `timer:flag:N` | flag 的計時器已過 N 分鐘 |

---

## 6. 共通規則

### 6.1 ID 命名
- 全小寫 snake_case：`village_square`、`quest_accepted`
- 中文名稱**必須**附帶 `#ascii_id`
- ID 在整個冒險中唯一（同類型不重複即可）

### 6.2 註解
```markdown
<!-- 這是單行註解 -->
<!--
這是
多行註解
-->
```

### 6.3 交叉引用
- 章節事件的 `trigger: enter_node node_id` 中的 `node_id` 必須存在於某張地圖
- NPC 的 `location: node_id` 必須存在於某張地圖
- 邊的 `to` / `from` 必須是同一地圖的節點 ID
- 對話的 `→ next_dialogue_id` 可跨 NPC 和場景檔案引用
- `locked: key_id` 中的 `key_id` 應對應某個物品的 `grants_key`

### 6.4 編譯與驗證

```bash
# 驗證（不輸出）
uv run adventure-author validate adventures/<id>/

# 編譯（輸出 JSON 到 output/）
uv run adventure-author build adventures/<id>/

# 編譯單張地圖
uv run adventure-author build-map adventures/<id>/maps/dungeon.md -o out.json
```

---

## 7. `scenes/*.md` — 場景

場景用於多角色互動對話，獨立於 NPC 檔案。適合：
- 群體場景（開場白、戰鬥事件、團體討論）
- DM 旁白搭配多角色反應
- 需要 choices/skill_check 的互動場景

### 7.1 Frontmatter

```markdown
---
id: encounter_intro
name: 洞穴遭遇開場
trigger: enter_node cave_mouth
condition: has:dragon_following
once: true
---
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `id` | ✅ | 場景唯一 ID（snake_case） |
| `name` | ✅ | 場景名稱 |
| `trigger` | 選填 | 自動觸發條件（格式同章節事件） |
| `condition` | 選填 | 前置條件表達式 |
| `once` | 選填 | 只觸發一次（預設 `true`） |

有 `trigger` 的場景會自動生成 `start_scene` 事件。無 `trigger` 的場景需要由章節事件手動觸發（`- start_scene: scene_id`）。

### 7.2 對話段落

場景的對話語法與 NPC 相同，但**每段必須有 `speaker:`**（場景沒有預設說話人）。

```markdown
## 洞穴口旁白 #cave_narration
speaker: dm

> 你們沿著小路來到洞穴口。空氣中帶著刺骨寒意。

next: cave_shalefire_react

## 岩炎的反應 #cave_shalefire_react
speaker: shalefire

> 岩炎皺起眉頭：「這股冷氣……不對勁。」

choices:
- **「小心前進。」** #choice_careful → cave_entry
- **「先偵查。」** #choice_scout → cave_scout_check
```

支援的語法：`> 引言`、`choices:`、`skill_check:`、`next:`、`sets_flag:`、`condition:`

### 7.3 靜默節點（`silent: true`）

靜默節點不顯示文字，執行 flag 後自動推進到 `next:` 目標。

```markdown
## 設定旗標 #cave_set_flags
speaker: dm
silent: true
sets_flag: cave_entered
next: cave_actual_entry
```

多個 silent 節點可連續串接，引擎會遞迴推進直到遇到非 silent 節點（上限 10 層）。

### 7.4 檔案命名

場景檔名用 scene ID 的 snake_case：
```
scenes/encounter_intro.md
scenes/group_discussion.md
scenes/dragon_egg_discovery.md
```
