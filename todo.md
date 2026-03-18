# T.O.T. - The Octo-Teller 開發追蹤

## Phase A: 本地 TUI 可玩版 — 跑通「危在松溪」

> 目標：純 Bone Engine + TUI，1 人用本地終端機跑完一場完整冒險
> 📄 系統總覽：[`docs/architecture.md`](docs/architecture.md)

### A-1: GameSession 核心
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md) §1-2, §5, §7

- [ ] GamePhase enum（Exploration / Story / Combat）+ GameState model
- [ ] 狀態轉換邏輯 — transition rules + 各階段進出 hook
- [ ] GameClock 整合 — 探索現實時間 + 戰鬥 +6 秒/輪 + 效果 expires_at_second
- [ ] 存讀檔 — 單一存檔槽自動存檔（`~/.tot/saves/<adventure>.json`）

### A-2: 啟動與創角 TUI
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md) §2

- [ ] Start Menu TUI：新冒險（選劇本）/ 讀檔 / 測試模式
- [ ] 測試模式：
  - 直接戰鬥（`tutorial_room`）
  - 小地城探索（`test_dungeon`：3 節點 Pointcrawl + Area Prop/Loot + 戰鬥觸發，預設角色有遠近法藥投擲）
- [ ] 角色建造 TUI（人數→背景→種族→職業→屬性→技能→確認）
- [ ] 松溪先鎖定 1 人遊玩

### A-3: 三模式 TUI + 轉場
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md) §2

- [ ] 探索 UI：Braille 地圖 + 世界/地城地圖 + 狀態欄 + 先攻表 + RichLog + 輸入
- [ ] 劇情 UI：關閉 Braille，可捲動文字 log + 對話選項
- [ ] 戰鬥 UI：同探索佈局 + 先攻追蹤器 + 回合制指令
- [ ] 模式切換轉場畫面

### A-4: 互動系統統一

- [ ] E = 萬用互動（選對象→選動作）
  - 人物：對話 / 給予物品
  - 物品：觀察 / 拾取 / 使用 / 攻擊 / 開鎖 / 撬鎖 / 開啟
- [ ] I = 背包（選物品→觀察/使用/投擲/丟棄）
- [ ] R = 裝備（部位列表→觀察/換裝/脫下）
- [ ] T = 攻擊選單（近戰/遠程/法術/投擲→選對象）
- [ ] 轉場點提示（靠近時詢問是否轉場，拒絕則移到安全位置）

### A-5: 探索→戰鬥銜接
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md) §6

- [ ] 節點/Area 觸發戰鬥條件
- [ ] 共用 MapState 切換（位置保留）
- [ ] 戰鬥結束回到探索
- [ ] sub_map 轉場完善

### A-6: 戰鬥系統強化

- [ ] 移動：輸入座標→尋路→**步進式渲染**（每步碰撞檢查 + 藉機攻擊提醒）
- [ ] 回合制：移動/攻擊/背包/結束回合
- [ ] 攻擊流程整合 T 選單

### A-7: 冒險內容 + 端對端測試
> 📄 工具文件：[`docs/adventure-author.md`](docs/adventure-author.md)

- [ ] 「危在松溪」Markdown 撰寫（用戶負責）+ `adventure-author build`
- [ ] 測試地圖整理：
  - `tutorial_room.json` — 保留，測試模式直接戰鬥
  - 新 `test_dungeon.json` — 合併 tutorial_dungeon + cave_explore 特色
  - 移除 `tutorial_dungeon.json` / `cave_explore.json` / `starter_town.json`
  - `explore_demo.py` 更新：AVAILABLE_MAPS 改為 combat/dungeon + 冒險載入路徑
- [ ] 端到端：啟動→創角→探索→對話→遭遇→戰鬥→休息→完結

---

## Phase B: LLM 單人 TUI（Narrator + AI 隊友）

> 目標：加入 LLM 讓體驗有靈魂，單人在 TUI 中有 AI 隊友陪玩

- [ ] LLM Client（Anthropic API wrapper + 重試/fallback）
- [ ] Prompt 模板系統（Jinja2 模板 + 變數注入）
- [ ] Narrator Gremlin — 場景描述 / 戰鬥旁白 / NPC 對話 / 6 種敘事風格
- [ ] Mimic Gremlin — 自然語言→GameAction（意圖分類 + 模糊輸入處理）
- [ ] Companion Gremlin — AI 隊友（信任驅動自主決策 + 戰術評估 + 個性化對話）

---

## Phase C: LLM 多人 TUI（同裝置）

> 目標：多人同螢幕輪流操控各自角色

- [ ] 多角色輸入管理
- [ ] 升級系統（level_up + 職業特性 + ASI/Feat + 經驗值分配）

---

## Phase D: Telegram / Discord 部署

> 目標：雲端部署，玩家透過通訊軟體遊玩

- [ ] 記憶系統（Redis Working + PG Episodic + Qdrant Semantic + Context Assembler）
- [ ] Telegram Bot（aiogram 3 + webhook + MarkdownV2 + inline keyboard）
- [ ] Prep Gremlin（世界生成 + Session 準備）
- [ ] Extension Gremlin（脫稿即興處理）
- [ ] 生產化（Docker + CI/CD + 監控 + 效能優化）

---

## Backlog: 不阻擋遊玩的強化功能

### 空間物理強化
> 📄 設計文件：[`docs/spatial-engine-design.md`](docs/spatial-engine-design.md)

- [ ] 事件系統 — GameEvent + EventBus + SystemLog + NarrativeLog
- [ ] 材質系統 — MATERIAL_AC 查表 + roll_object_hp + apply_object_damage
- [ ] 表面效果 — SurfaceEffect enter/leave/stay + 傷害 + 豁免
- [ ] Z 軸地形 — Position.z + HeightCheckResult + 掉落傷害
- [ ] 掩護 v2 — Corner-Ray 演算法 + CoverResult + 投射物打掩護
- [ ] Actor.size 傳播 — bounds.overlaps() + pathfinding Minkowski
- [ ] GameStateManager — 包裝 MapState+CombatState+EventBus
- [ ] 強制位移路徑檢測 — move_entity forced=True + Liang-Barsky 碰牆

### 怪物 AI
- [ ] Behavior Tree 框架（Node/Selector/Sequence/Decorator）
- [ ] 哥布林族 / 不死族 / 野獸 / Boss AI

### 探索進階
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md) §8

- [ ] 光照與視覺（LightLevel + Darkvision）
- [ ] 行進隊形（MarchingOrder + 前衛/殿後）
- [ ] 旅行速度（TravelPace + 感知/隱匿修正）
- [ ] 隨機遭遇（danger_level + 遭遇表）
- [ ] 陷阱機制（NodeTrap + Investigation/Thieves' Tools）
- [ ] 時間壓力（火把/法術持續/NPC 行程）
- [ ] 野外地形效果（困難地形/天氣/能見度）

### 測試補齊
- [ ] test_combat.py — 攻擊/傷害/死亡豁免/武器專精/借機攻擊
- [ ] test_character.py — 12 職業建構、法術欄位、AC 計算
- [ ] test_spatial.py — 距離/LOS/掩蔽/移動
- [ ] test_exploration.py — 節點移動/隱藏通道/子地圖/時間
- [ ] test_deployment.py — 遭遇判定/佈陣/確認

### 其他
- [ ] 範圍法術 — AoE 判定（統一用 BoundingShape）+ 空間系統整合
- [ ] 休息與狀態整合 — 休息結束狀態自動清除
- [ ] TUI 架構重構 — 純規則邏輯從 TUI 搬進 bone_engine
- [ ] TUI 戰鬥移動引導重設計 — 主選單重排 + 佔位詢問

---

## 已完成工作

<details>
<summary>Phase 0~2 完成項目（點擊展開）</summary>

### Phase 0: 專案骨架 ✅
- [x] 初始化 git repo + 目錄結構 + pyproject.toml
- [x] 遷移知識庫（reference / glossary / dm_settings）
- [x] 遷移既有 bot.py 為參考文件 (docs/legacy/)

### Phase 1: Bone Engine 核心 ✅
- [x] Pydantic data models (Character, Monster, Spell, Item, Condition)
- [x] 骰子系統 (dice.py) — d4~d100、advantage/disadvantage
- [x] 角色建立流程 (character.py) — 12 職業/屬性/技能
- [x] 戰鬥引擎 (combat.py) — 先攻、回合制、攻擊/傷害/死亡豁免
- [x] 戰鬥地圖系統 — 連續座標（公尺）、拓樸區域、渲染
- [x] Pointcrawl 探索系統 — 三層拓樸（地城/城鎮/世界）
- [x] 佈陣階段 (deployment.py)

### Phase 2: Bone Engine 補完

#### 2-A: 狀態系統重構 ✅
- [x] 狀態管理 API + 回合生命週期 + 堆疊規則 + 單元測試

#### 2-B: 法術系統 ✅（除範圍法術）
- [x] 法術資料庫（36 法術）+ 載入器 + 施法檢查 + 效果執行 + 專注 + 成分 + 升環
- [x] 單元測試 57 tests

#### 2-S: 空間系統重構 ✅
- [x] Grid 移除，純連續空間 + Wall AABB

#### 2-F: 破門與噪音系統 ✅
- [x] ExplorationEdge break_dc/noise + force_open_edge + alerted 參數

#### 2-G: 角色建造器 ✅
- [x] CharacterBuilder 分步驟建角 + 5.5e 順序

#### 2-H: TUI 戰鬥介面 ✅
- [x] 四面板佈局 + 攻擊/法術/移動指令 + 怪物自動行動

#### 2-H-fix: TUI 戰鬥 Bug 修復 ✅
- [x] spawn/prop 座標轉換 + 移動輸入 + 近戰射程 + 0 HP 處理

#### 2-I: 三層測試框架 ✅
- [x] AI 自動對戰 + HeadlessCombatRunner + 規則斷言 + 試玩 Log

#### 2-M: 資料模型重構 ✅（除 Phase E）
- [x] models.py 拆分 + Combatant 基類 + Query Methods + Spell 子模型

#### 2-X: 探索 TUI ✅
- [x] 探索狀態機 + 角色選擇 + 鑰匙系統 + POI + 休息

#### 2-XA: Area 自由探索 ✅
- [x] AreaExploreState + BrailleMapCanvas 切換 + Prop 互動 + 地形效果

#### 2-XB: 渲染架構重構 ✅
- [x] MapState → RenderBuffer → BrailleMapCanvas + Prop Prefab 系統

#### 2-XC: 圖例完整化 ✅
- [x] Prop 圖例 + 門渲染簡化 + 多字元 Braille icon

#### 2-XD: Prop 碰撞體積 ✅
- [x] Prop bounds + D&D 物件免疫/抗性 + 邊緣距離互動

#### 2-XE: 危在松溪系統功能 ✅
- [x] Stage XE-A~F: 冒險資料模型 + 條件評估器 + 事件引擎 + 對話引擎 + 載入器 + TUI 整合
- [x] Stage XE-Tool: Adventure Author（Markdown → JSON）+ 101 tests
- [x] Stage XE-Encounter: 遭遇語法 + /ingest Skill
- [x] Stage XE-Scene: 場景對話系統

#### 2-K: TUI 大改 ✅
- [x] 模組化拆分 + BrailleMapCanvas + StatsPanel + AoE 覆蓋渲染

#### 2-E: 測試骨架 ✅
- [x] conftest.py fixtures + test_dice.py 39 tests

#### ① 基礎物理引擎（部分完成）
- [x] BoundingShape（5 種 ShapeType）+ Material/Fragility + Prop 可摧毀欄位

</details>
