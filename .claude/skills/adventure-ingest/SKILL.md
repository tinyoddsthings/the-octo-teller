---
name: adventure-ingest
description: >
  Convert natural language adventure content into structured Adventure Author
  Markdown format. This skill should be used when the user says "adventure-ingest",
  "轉換冒險", "輸入劇本", "寫地圖", "寫NPC", "寫章節", or provides natural
  language adventure content to convert into structured Adventure Author
  Markdown format.
---

# /adventure-ingest — 自然語言 → 結構化 Adventure Author MD

## 工作流程

### 1. 確認冒險資料夾

- **首次**：詢問冒險 ID（如 `peril_in_pinebrook`），用 `adventure-author new <id>` 建骨架
- **後續**：讀取已存在的 `adventures/<id>/` 資料夾

```bash
# 首次建立
cd ~/Desktop/tot-the-octo-teller
uv run adventure-author new <id> --dir adventures
```

### 2. 讀取已有內容（增量轉換的關鍵）

每次轉換前，掃描資料夾中已存在的 MD 檔案，彙整已定義的 ID 清單：

```bash
# 掃描已有檔案
ls adventures/<id>/maps/*.md 2>/dev/null
ls adventures/<id>/npcs/*.md 2>/dev/null
ls adventures/<id>/chapters/*.md 2>/dev/null
ls adventures/<id>/scenes/*.md 2>/dev/null
cat adventures/<id>/_meta.md 2>/dev/null
```

讀取所有已有檔案，記錄：
- 地圖 ID、節點 ID、邊 ID
- NPC ID
- Flag 名稱
- Item ID

**這一步很重要**：新段落的 ID 引用必須與已有內容一致。

### 3. 判斷類型

根據用戶輸入自動判斷屬於哪種檔案：

| 用戶輸入內容 | 目標檔案 |
|-------------|---------|
| 冒險概述、整體設定 | `_meta.md` |
| 地點、場景、地圖描述 | `maps/*.md`（自動判斷 scale：town/world/dungeon） |
| 角色描述、NPC 設定 | `npcs/*.md` |
| 多角色互動場景、戰鬥事件、群體對話 | `scenes/*.md` |
| 故事事件、劇情推進 | `chapters/*.md` |

### 4. 轉換

**嚴格按照** `references/md-format-spec.md` 的精確語法轉換：

- 自動生成 `#id`：中文名稱**一律**需要 explicit `#ascii_id`
- 補全必填欄位（type, trigger, condition 等）
- 保留原文描述和氛圍文字
- 地城節點有敵人時加入 `encounter:` 區塊
- 引用其他檔案的 ID 時**確認存在**（交叉驗證）

### 5. 寫入檔案

用 Write tool 寫入對應位置，檔名規則：
- `maps/` — 用地圖名稱的 snake_case（如 `pinebrook_village.md`）
- `npcs/` — 用 NPC ID（如 `quinn.md`）
- `chapters/` — 用 `NN_slug.md`（如 `01_arrival.md`）
- `scenes/` — 用 scene ID 的 snake_case（如 `encounter_intro.md`）

### 6. 驗證

```bash
cd ~/Desktop/tot-the-octo-teller
uv run adventure-author validate adventures/<id>/
```

驗證通過後告知用戶。如有錯誤，修正後重新驗證。

---

## 轉換規則摘要

### 命名規則
- 所有中文名稱**必須**附帶 `#ascii_id`（如 `## 松溪村 #pinebrook_village`）
- ASCII 名稱可自動 slugify（如 `## Forest Path` → id = `forest_path`）
- ID 風格：snake_case，全小寫

### 地圖 Scale 判斷
- **town**：有 POI 子節點的定居點（村莊/城鎮/城堡內部）
- **world**：連接各地點的旅行路線（距離用天）
- **dungeon**：探索空間（距離用分鐘，房間/走廊/洞穴）

### 遭遇（Encounter）
- 地城節點有敵人時加入 `encounter:` 區塊
- 現階段用 `outcome: auto_win`（進入 → 旁白 → 自動獲勝 → 獎勵）
- 未來 Phase 3 改為 `outcome: combat` 即可啟動真正戰鬥

### 場景（Scene）
- 多角色對話放 `scenes/*.md`，**不要**塞在某個 NPC 檔案裡
- DM 旁白搭配多角色反應 → 場景
- 場景每段對話**必須**有 `speaker:`（無預設說話人）
- `silent: true` 靜默節點：不顯示文字，執行 flag 後自動推進
- 有 `trigger` 的場景自動觸發；無 `trigger` 的場景由章節事件 `start_scene` 觸發
- `next:` 可跨 NPC 和場景檔案引用

### 章節事件觸發類型
- `enter_node <node_id>` — 進入節點
- `take_item <item_id>` — 拿取物品
- `flag_set <flag_name>` — flag 被設定
- `talk_end <dialogue_id>` — 對話結束

### 對話條件語法
- `has:flag` — flag 存在
- `not:flag` — flag 不存在
- `all:cond1,cond2` — 全部滿足
- `any:cond1,cond2` — 任一滿足
- `gte:flag:N` — flag >= N
- `lt:flag:N` — flag < N

---

## 增量轉換設計

用戶可以分段輸入同一份冒險。建議順序：

1. 概述（`_meta.md`）
2. 地圖（一張一張，先大後小：world → town → dungeon）
3. NPC（一個一個）
4. 場景（多角色互動場景）
5. 章節（一章一章）

每次 `/ingest` 先掃描已有 MD 檔案、建立 ID 索引，確保新內容能正確引用舊 ID。

---

## 注意事項

- **不自動 build**：轉換完讓用戶確認，用戶想 build 時再執行 `uv run adventure-author build`
- **不修改引擎程式碼**：Skill 只產出 MD 檔案
- **格式規格以 `references/md-format-spec.md` 為準**：有疑問時查閱規格文件
