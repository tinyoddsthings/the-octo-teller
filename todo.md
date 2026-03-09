# T.O.T. - The Octo-Teller 開發追蹤

## Phase 0: 專案骨架 ✅
- [x] 初始化 git repo
- [x] 建立完整目錄結構
- [x] pyproject.toml (uv src layout)
- [x] .gitignore / README.md / CLAUDE.md
- [x] docker-compose.yml (Redis placeholder)
- [x] 所有 __init__.py 與 placeholder 檔案
- [x] 遷移知識庫（reference / glossary / dm_settings）從 memory/dnd/
- [x] 遷移既有 bot.py 邏輯為參考文件 (docs/legacy/)

## Phase 1: Bone Engine 核心 — 戰鬥與空間 ✅
- [x] Pydantic data models (Character, Monster, Spell, Item, Condition)
- [x] 骰子系統 (dice.py) — d4~d100、advantage/disadvantage、modifier
- [x] 角色建立流程 (character.py) — 12 職業/屬性/技能
- [x] 戰鬥引擎 (combat.py) — 先攻、回合制、攻擊/傷害/死亡豁免/武器專精
- [x] 戰鬥地圖系統 — 格子座標、拓樸區域、ASCII 渲染、戰爭迷霧
- [x] Pointcrawl 探索系統 — 三層拓樸（地城/城鎮/世界）
- [x] 佈陣階段 (deployment.py) — 遭遇判定 + 佈陣 + 渲染

## Phase 2: Bone Engine 補完 — 法術、休息、協調器
> 里程碑：純文字 CLI 可跑完「探索→遭遇→佈陣→戰鬥→休息」完整循環

### 2-A: 狀態系統重構 (conditions.py)
> combat.py 已內聯處理 13 種狀態的攻擊/豁免效果，
> 缺少：回合開始/結束的自動清除、堆疊規則、持續時間計時器
- [x] Step 1: 狀態管理 API — apply_condition, remove_condition, has_condition_effect
- [x] Step 2: 回合生命週期 — tick_conditions_start_of_turn, tick_conditions_end_of_turn
- [x] Step 3: 堆疊規則 — 同源不堆疊、力竭等級累加、擒抱來源追蹤
- [x] Step 4: 從 combat.py 抽取狀態查詢邏輯（保持呼叫介面不變）
- [x] Step 5: 單元測試 — test_conditions.py

### 2-B: 法術系統 (spells.py)
> Spell model 已定義，character.py 已有法術欄位/DC/攻擊計算，
> 缺少施法動作解析、效果執行、專注維持
- [ ] Step 1: 法術資料庫 — JSON 格式定義檔（戲法 + 1~3 環，約 30 個常用法術）
- [ ] Step 2: 法術載入器 — load_spell_db, get_spell_by_name
- [ ] Step 3: 施法前置檢查 — can_cast（法術欄位/準備/射程/成分/動作經濟）
- [ ] Step 4: 法術效果執行 — cast_spell 主函式（傷害/治療/狀態分支）
- [ ] Step 5: 專注機制 — 開始/中斷專注 + 戰鬥中自動檢定
- [x] Step 5b: 法術成分系統 — V/S/M 欄位 + can_cast 檢查 + 材料消耗
- [x] Step 5c: 升環擴充 — 目標數/專注解除/持續時間/範圍/召喚（model 欄位全開，引擎先做①③）
- [ ] Step 6: 範圍法術 — AoE 判定（圓形/錐形/線形）+ 空間系統整合
- [ ] Step 7: 單元測試 — test_spells.py

### 2-C: 休息機制 (rest.py)
- [ ] Step 1: 短休 — Hit Dice 恢復 HP、職業短休資源回復
- [ ] Step 2: 長休 — 全滿 HP、法術欄位回復、力竭降一級、Hit Dice 回復一半
- [ ] Step 3: 與 conditions.py 整合（休息結束狀態的自動清除）
- [ ] Step 4: 單元測試 — test_rest.py

### 2-D: 遊戲協調器 (engine.py)
> 將探索→佈陣→戰鬥→休息串成狀態機
- [ ] Step 1: GamePhase 列舉 + GameState 模型
- [ ] Step 2: 狀態轉換邏輯 — transition rules + 各階段進出 hook
- [ ] Step 3: 回合管理整合 — 串接 combat advance_turn + conditions tick
- [ ] Step 4: 存檔/讀檔 — GameState 序列化/反序列化（JSON 檔案）
- [ ] Step 5: CLI demo script — 純文字跑完完整遊戲循環（含存讀檔）
- [ ] Step 6: 單元測試 — test_engine.py

### 2-F: 破門與噪音系統
- [x] Step 1: ExplorationEdge 加 break_dc / noise_on_force；MoveResult 加 noise_generated
- [x] Step 2: force_open_edge() 破門函式
- [x] Step 3: resolve_encounter + start_deployment_from_node 加 alerted 參數
- [x] Step 4: tutorial_dungeon.json 加 break_dc
- [x] Step 5: 單元測試 — test_exploration.py

### 2-G: 角色建造器 (CharacterBuilder)
- [x] Step 1: CharacterBuilder 類別 — 分步驟建角 + 前置條件驗證
- [x] Step 2: 5.5e 建角順序（背景→種族→職業→屬性→技能）
- [x] Step 3: 單元測試 — test_character_builder.py

### 2-E: Phase 1 已完成模組的測試補齊
- [ ] conftest.py — 共用 fixtures（標準角色、怪物、地圖）
- [ ] test_dice.py — 骰子分布、advantage/disadvantage、modifier
- [ ] test_combat.py — 攻擊/傷害/死亡豁免/武器專精/借機攻擊
- [ ] test_character.py — 12 職業建構、法術欄位、AC 計算
- [ ] test_spatial.py — 距離/LOS/掩蔽/移動
- [ ] test_exploration.py — 節點移動/隱藏通道/子地圖/時間
- [ ] test_deployment.py — 遭遇判定/佈陣/確認
- [ ] test_map_renderer.py — ASCII 渲染/戰爭迷霧/佈陣預覽

## Phase 3: 怪物 AI + 升級系統
> 里程碑：怪物有智慧行為、角色可升級（純確定性，屬 Bone Engine）

### 3-A: 怪物 AI (combat_ai/)
- [ ] Step 1: Behavior Tree 框架 — Node/Selector/Sequence/Decorator
- [ ] Step 2: 基礎戰術 (tactics.py) — 目標選擇/走位/脫離
- [ ] Step 3: 哥布林族 AI — 群體包抄、弱目標優先、撤退門檻
- [ ] Step 4: 不死族 AI — 無畏衝鋒、群聚圍攻
- [ ] Step 5: 野獸 AI — 掠食者/獵物行為、士氣崩潰
- [ ] Step 6: Boss AI — 多階段/傳奇動作/環境互動
- [ ] Step 7: 單元測試 — test_combat_ai.py

### 3-B: 升級系統
> character.py 已有 level_for_xp() 但缺 level_up()
- [ ] Step 1: level_up 函式 — HP 增加、熟練加值更新、法術欄位重算
- [ ] Step 2: 職業特性選擇框架 — 子職業、ASI/Feat 選擇
- [ ] Step 3: 經驗值分配 — gain_xp + 自動偵測可升級
- [ ] Step 4: 單元測試 — test_level_up.py

## Phase 4: Mimic + Narrator（LLM 層）
> 里程碑：自然語言輸入→結構化動作→敘事輸出

### 4-A: LLM 基礎建設
- [ ] LLM Client (llm_client.py) — Anthropic API wrapper + 重試/fallback
- [ ] Prompt 模板系統 (prompts/) — Jinja2 模板 + 變數注入
- [ ] 回應解析器 — JSON schema 驗證 + 錯誤恢復

### 4-B: Mimic Gremlin — 意圖解析
- [ ] Intent Classification — 動作/對話/查詢/系統指令
- [ ] Structured Action Output — 自然語言 → GameAction Pydantic model
- [ ] 模糊輸入處理 — 拼字容錯、縮寫展開、上下文推斷
- [ ] 單元測試 — test_mimic.py（mock LLM）

### 4-C: Narrator Gremlin — 敘事引擎
- [ ] 場景描述生成 — 探索/進入新區域
- [ ] 戰鬥旁白 — 攻擊/傷害/死亡/法術效果描述
- [ ] NPC 對話 — 角色語音/個性/情境反應
- [ ] Narrative Styles — 6 種敘事風格切換
- [ ] Difficulty Adaptation — 根據玩家經驗調整描述深度
- [ ] 單元測試 — test_narrator.py（mock LLM）

## Phase 5: 記憶系統
> 里程碑：跨 session 記憶、規則 RAG 查詢
> 需要 Docker 運行 Redis / PostgreSQL / Qdrant

### 5-A: Working Memory (Redis)
- [ ] Redis 連線管理 + 序列化策略
- [ ] 戰鬥狀態快取 — CombatState / MapState
- [ ] Session 狀態 — 玩家連線/活躍遊戲追蹤

### 5-B: Episodic Memory (PostgreSQL + pgvector)
- [ ] 資料表設計 — 冒險歷史、NPC 互動、重要事件
- [ ] 事件寫入 — 自動記錄戰鬥結果/探索發現/對話重點
- [ ] 向量搜尋 — pgvector 嵌入 + 相似度查詢

### 5-C: Semantic Memory (Qdrant RAG)
- [ ] SRD 規則向量化 — 分塊 + 嵌入 + 上傳
- [ ] 世界知識庫 — 自定義設定/NPC/地點
- [ ] RAG 查詢 API — 給 Narrator/Extension 用的規則查詢

### 5-D: Context Assembler
- [ ] 情境組裝器 — 根據遊戲階段組合 Working + Episodic + Semantic
- [ ] Token 預算管理 — 確保 context 不超過 LLM 限制
- [ ] 記憶壓縮 — 過長對話的摘要策略

## Phase 6: 進階 Gremlin + 系統擴展
> 里程碑：完整六隻 Gremlin 架構

### 6-A: Companion Gremlin — NPC 隊友
- [ ] 人格系統 (personality.py) — 個性特質/動機/恐懼
- [ ] 信任系統 (trust.py) — 好感度/忠誠度/背叛門檻
- [ ] 戰鬥決策 (tactics.py) — 根據個性選擇行為
- [ ] 對話系統 (dialogue.py) — 個性化語音 + 情境反應
- [ ] 判斷系統 (judgment.py) — 評估玩家行為、道德判定

### 6-B: Prep Gremlin — 世界生成
- [ ] 世界生成 (world_gen.py) — 自動生成探索地圖 + 遭遇
- [ ] Session 準備 (session_prep.py) — NPC/事件/伏筆排程

### 6-C: Extension Gremlin — 即興擴展
- [ ] 即興引擎 (improviser.py) — 超出預設規則時的 LLM 裁決
- [ ] 自定義規則 — 玩家/DM 新增 house rules

### 6-D: 多團支援
- [ ] 多 session 同時進行 — 狀態隔離/資源管理

## Phase 7: Telegram Bot 介面
> 里程碑：可透過 Telegram 開團、建角、探索、戰鬥

### 7-A: Bot 核心
- [ ] Bot 啟動與設定 (app.py) — aiogram 3 + webhook/polling
- [ ] Middleware — session 管理、權限檢查、錯誤處理
- [ ] Formatters — Telegram MarkdownV2 格式化
- [ ] Inline Keyboards — 動作選單、骰子按鈕、確認/取消

### 7-B: Game Handler — 遊戲生命週期
- [ ] 開團/加入/離開 — 群組 session 管理
- [ ] DM Settings — 敘事風格/難度設定

### 7-C: 遊戲流程 Handler
- [ ] Character Handler — 建角引導（互動式問答）
- [ ] Exploration Handler — 移動/搜索/互動
- [ ] Combat Handler — 戰鬥 UI（先攻顯示/動作選擇/骰子結果）
- [ ] Admin Handler — 管理員指令（GM 覆寫/debug）

### 7-D: 面板渲染
- [ ] 角色卡面板 (panel_renderer.py) — HP/AC/狀態/法術欄位
- [ ] 戰鬥狀態面板 — 先攻順序/回合標記/地圖

## Phase 8: 視覺化 + Mini Apps
> 里程碑：圖形化地圖、AI 插圖、互動式介面

- [ ] 地圖渲染升級 — ASCII → 圖片混合（Pillow/SVG）
- [ ] AI 圖片生成 (ai_gen.py) — 場景/NPC 插圖
- [ ] Telegram Mini App 骨架
- [ ] 互動式角色卡介面
- [ ] 戰鬥地圖互動（點擊移動/攻擊目標）

## Phase 9: 生產化
- [ ] Docker 化（bot + Redis + PG + Qdrant）
- [ ] CI/CD pipeline（pytest + lint + 自動部署）
- [ ] 監控與日誌（結構化日誌 + 健康檢查）
- [ ] 效能優化（LLM 快取、批次查詢、連線池）
- [ ] 使用者文件（玩家指南 + DM 指南）
- [ ] 壓力測試（多人並發 + 長時間 session）
