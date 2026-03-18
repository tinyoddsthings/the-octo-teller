# Adventure Author — 冒險劇本生成工具

## 概述

Adventure Author 是一套 Markdown → JSON 編譯器，讓用戶用結構化的 Markdown 撰寫冒險劇本，
工具將其編譯成 Bone Engine 可讀的 JSON 格式。

```
紙本冒險書（自然語言）
  → /ingest skill（Claude 轉換）
    → 結構化 MD（地圖/NPC/章節）
      → adventure-author build
        → JSON（引擎可讀）
```

## CLI 用法

```bash
# 建立新冒險資料夾骨架（含範例檔案）
uv run adventure-author new <adventure_id> [--name <名稱>] [--dir <父目錄>]

# 驗證冒險資料夾語法（不輸出 JSON）
uv run adventure-author validate <adventure_dir>

# 編譯整個冒險資料夾（輸出到 output/）
uv run adventure-author build <adventure_dir> [-o <output_dir>]

# 編譯單張地圖
uv run adventure-author build-map <map.md> [-o <output.json>]
```

## 資料夾結構

```
adventures/<adventure_id>/
├── _meta.md              # 冒險基本資訊 + 初始 flags
├── maps/                 # 地圖（town/world/dungeon 三種 scale）
├── npcs/                 # NPC（一個 NPC 一份 MD）
├── chapters/             # 章節事件（按順序編號）
└── output/               # 編譯輸出的 JSON（自動建立）
```

## 編譯流程

1. **地圖 MD → ExplorationMap JSON**
   - `parser.py` 將 MD 解析為 `MapIR`（中間表示）
   - `map_builder.py` 將 `MapIR` 轉為 Pydantic `ExplorationMap` 相容的 dict
   - 地圖中的 `encounter:` 區塊轉為 `EncounterDef` 嵌入節點

2. **NPC + 章節 + 地圖遭遇 → AdventureScript JSON**
   - `parser.py` 解析所有 NPC/章節 MD
   - `script_builder.py` 合併為 `AdventureScript` dict
   - 地圖遭遇自動生成對應的 `ScriptEvent`（enter_node 觸發）

## Encounter（遭遇）語法

遭遇是**空間綁定**的——放在地圖 MD 的地城節點下，而非章節中。

```markdown
## 巢穴 #dragon_nest
type: room
description: 一個寬敞的洞室。

encounter:
  enemies:
  - 幼藍龍 #young_blue_dragon | CR:2
    一隻藍色的小龍。
  - 冰凍蜥蜴 #ice_lizard | CR:1/4
    count: 2
  trigger: enter_node
  narration: 幼龍猛然抬起頭，發出一聲低吼。
  outcome: auto_win
  rewards:
  - 龍鱗碎片 #dragon_scale_piece | value_gp: 10
  - 經驗值 #encounter_xp | xp: 450
  sets_flag: dragon_defeated
```

### 現階段行為（`outcome: auto_win`）

進入節點 → 顯示 narration → 自動勝利 → sets_flag → 給獎勵。
不跑戰鬥引擎。

### 未來行為（`outcome: combat`）

同一空間載入 Area 地圖 → 生成敵人 → 跑完整戰鬥引擎 → 勝利後 sets_flag + 獎勵。

## 模組架構

```
src/tot/tools/adventure_author/
├── cli.py           # CLI 入口（new/build/build-map/validate）
├── scaffold.py      # new 指令——建資料夾 + 範例檔案
├── parser.py        # MD → IR 解析器（逐行狀態機）
├── ir.py            # 中間表示（dataclass，工具內部用）
├── map_builder.py   # MapIR → ExplorationMap dict
├── script_builder.py# ScriptIR → AdventureScript dict
└── id_gen.py        # 名稱 → ID 轉換（slugify / CJK 檢查）
```

## `/ingest` Skill

Claude Code Skill（`.claude/skills/adventure-ingest/`），用自然語言輸入冒險內容，
Claude 轉換為精確的 MD 格式。支援增量轉換——每次先掃描已有檔案建立 ID 索引。

觸發方式：`/ingest` 或用自然語言描述冒險內容。

完整格式規格：`.claude/skills/adventure-ingest/references/md-format-spec.md`
