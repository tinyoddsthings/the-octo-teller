"""Scaffold 指令——建立新冒險資料夾結構和範例檔案。"""

from __future__ import annotations

from pathlib import Path

_META_TEMPLATE = """\
---
id: {adventure_id}
name: {adventure_name}
description: 在此填寫冒險簡介。
---

<!-- 初始 flag（選填，冒險開始時自動設定） -->
<!-- initial_flags:
- some_flag: 1 -->
"""

_CHAPTER_TEMPLATE = """\
---
chapter: 1
title: 開場
---

<!-- 事件語法：
  ## 事件名稱 #event_id
  trigger: enter_node node_id      （進入節點）
  trigger: take_item item_id       （拿取物品）
  trigger: flag_set flag_name      （flag 被設定）
  trigger: talk_end dialogue_id    （對話結束）
  condition: has:some_flag         （額外條件，選填）
  once: true                       （只觸發一次，預設 true）

  > 旁白文字（會轉成 narrate action）

  - set_flag: flag_name            （動作列表）
  - reveal_edge: edge_id
  - move_npc: npc_id → node_id
  - tutorial: 教學提示文字
-->

## 開場白 #opening
trigger: enter_node town_center
once: true

> 你踏入小鎮，空氣中瀰漫著不安的氣氛。

- tutorial: 輸入 `look` 查看周圍環境，輸入 `talk` 與 NPC 對話。
- set_flag: arrived
"""

_MAP_TOWN_TEMPLATE = """\
---
id: {adventure_id}_town
name: 範例城鎮
scale: town
entry: town_center
---

<!-- 城鎮地圖用 pois: 定義子節點（POI），不需要邊連接 -->

## 城鎮中心 #town_center
type: town
description: 小鎮的中心廣場。
ambient: 市集的喧鬧聲，遠處傳來鐵匠敲打聲。

pois:
- 酒館 #tavern | poi
  一間熱鬧的酒館。
  npcs: bartender
- 雜貨鋪 #shop | poi
  門口擺著幾桶乾糧的小店。
  npcs: shopkeeper

items:
- 公告欄 #notice_board | clue | dc:0
  釘滿紙條的公告欄。
"""

_MAP_ROAD_TEMPLATE = """\
---
id: {adventure_id}_road
name: 範例道路
scale: world
entry: town_gate
---

<!-- 道路地圖連接城鎮和地城，距離用天，sub_map 連結子地圖 -->

## 城鎮大門 #town_gate
type: landmark
description: 通往外界的大門。
sub_map: {adventure_id}_town

## 森林岔路 #crossroads
type: landmark
description: 小徑在此分為兩條。

items:
- 腳印 #footprints | clue | dc:10
  地上有奇怪的足跡。

## 洞穴入口 #cave_entrance
type: dungeon
description: 一個被藤蔓遮掩的洞口。
sub_map: {adventure_id}_dungeon

### → 森林岔路 #to_crossroads
to: crossroads
from: town_gate
distance: 0.5day
terrain: 泥土路
danger_level: 2

### → 洞穴入口 #to_cave
to: cave_entrance
from: crossroads
distance: 0.3day
danger_level: 5
"""

_MAP_DUNGEON_TEMPLATE = """\
---
id: {adventure_id}_dungeon
name: 範例地城
scale: dungeon
entry: entrance_hall
---

<!-- 地城地圖：房間互相連接，距離用分鐘 -->
<!-- 邊支援：locked（鎖門）、hidden_dc（隱藏通道）、one_way（單向）、jump_dc（跳躍）-->

## 入口大廳 #entrance_hall
type: room
description: 潮濕的石造大廳，火把在牆上搖曳。
ambient: 水滴聲迴盪在石壁之間。

items:
- 生鏽鑰匙 #rusty_key | item | dc:12
  藏在破碎石板下方的一把鑰匙。
  grants_key: rusty_key

## 走廊 #corridor
type: corridor
description: 狹窄的走廊，牆壁上刻著古老的符文。

## 寶庫 #treasure_room
type: room
description: 一個寬敞的洞室，角落堆著閃亮的物品。
combat_map: treasure_battle

items:
- 寶箱 #treasure_chest | chest | dc:0
  一個沒上鎖的木箱。
  value_gp: 50

### → 走廊 #to_corridor
to: corridor
from: entrance_hall
distance: 2min

### → 寶庫（鐵門） #iron_door
to: treasure_room
from: corridor
distance: 1min
locked: rusty_key
lock_dc: 14
break_dc: 18

### → 入口大廳（暗門） #secret_passage
to: entrance_hall
from: treasure_room
distance: 3min
hidden_dc: 15
"""

_NPC_TEMPLATE = """\
---
id: guard
name: 衛兵
---

<!-- NPC 格式：
  ## 背景      — 設定外觀、個性、初始位置
  ## 常態對話   — 無條件，隨時可觸發
  ## 情境對話   — 綁地圖 + 條件，特定情境下觸發
    map:       — 在哪張地圖（選填）
    chapter:   — 語法糖，chapter: 02 → has:chapter_02（選填）
    condition: — 精確條件，如 has:quest_accepted（選填）
    > 文字     — NPC 說的話
    sets_flag: — 說完後設定的 flag（選填）
    choices:   — 玩家選擇（選填）
      - **「選項」** #id → next_dialogue_id
        sets_flag: flag_name
-->

## 背景
description: 身穿皮甲的鎮衛兵，看起來有些疲憊。
location: town_center
personality: 盡忠職守但有些嘮叨。
role: quest_giver

## 常態對話 #guard_idle

> 最近治安不太好，你們出門小心。

## 初次見面 #guard_intro
condition: not:talked_to_guard

> 你是外地來的冒險者嗎？最近鎮上出了些怪事……

choices:
- **「什麼怪事？」** #guard_ask → guard_explain
  sets_flag: talked_to_guard
- **「不關我的事。」** #guard_dismiss → guard_shrug

## 說明情況 #guard_explain

> 最近有牲畜失蹤，我們懷疑是北邊森林裡的什麼東西搗的鬼。

sets_flag: quest_accepted

## 聳肩 #guard_shrug

> 隨你吧，但如果改變主意，來找我。
"""


_SCENE_TEMPLATE = """\
---
id: example_scene
name: 範例場景
trigger: enter_node town_center
condition: has:arrived
once: true
---

<!-- 場景格式：
  每段對話必須有 speaker:（場景無預設說話人）
  支援 choices: / skill_check: / next: / sets_flag:
  silent: true — 靜默節點，不顯示文字，自動推進
-->

## 歡迎旁白 #scene_welcome
speaker: dm

> 你踏入廣場，幾個人圍過來。

next: scene_guard_greet

## 衛兵問候 #scene_guard_greet
speaker: guard

> 你好，外地人，來這裡有什麼事嗎？

choices:
- **「我在冒險。」** #scene_adventuring → scene_guard_nod
- **「只是路過。」** #scene_passing → scene_guard_nod

## 衛兵點頭 #scene_guard_nod
speaker: guard

> 嗯，小心點就好。

sets_flag: scene_complete
"""


def create_adventure(
    base_dir: Path,
    adventure_id: str,
    adventure_name: str = "",
) -> Path:
    """建立新冒險資料夾結構和範例檔案。

    Args:
        base_dir: 資料夾建立位置的父目錄
        adventure_id: 冒險 ID（也是資料夾名稱）
        adventure_name: 冒險名稱（預設用 adventure_id）

    Returns:
        建立的冒險資料夾路徑
    """
    if not adventure_name:
        adventure_name = adventure_id

    root = base_dir / adventure_id
    root.mkdir(parents=True, exist_ok=True)

    chapters_dir = root / "chapters"
    maps_dir = root / "maps"
    npcs_dir = root / "npcs"
    scenes_dir = root / "scenes"

    for d in (chapters_dir, maps_dir, npcs_dir, scenes_dir):
        d.mkdir(exist_ok=True)

    fmt = {"adventure_id": adventure_id, "adventure_name": adventure_name}

    # _meta.md
    (root / "_meta.md").write_text(
        _META_TEMPLATE.format(**fmt),
        encoding="utf-8",
    )

    # 章節範例
    (chapters_dir / "01_opening.md").write_text(
        _CHAPTER_TEMPLATE,
        encoding="utf-8",
    )

    # 地圖範例（三種 scale 各一）
    (maps_dir / "town.md").write_text(
        _MAP_TOWN_TEMPLATE.format(**fmt),
        encoding="utf-8",
    )
    (maps_dir / "road.md").write_text(
        _MAP_ROAD_TEMPLATE.format(**fmt),
        encoding="utf-8",
    )
    (maps_dir / "dungeon.md").write_text(
        _MAP_DUNGEON_TEMPLATE.format(**fmt),
        encoding="utf-8",
    )

    # NPC 範例
    (npcs_dir / "guard.md").write_text(
        _NPC_TEMPLATE,
        encoding="utf-8",
    )

    # 場景範例
    (scenes_dir / "example_scene.md").write_text(
        _SCENE_TEMPLATE,
        encoding="utf-8",
    )

    return root
