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
- [x] 戰鬥地圖系統 — 連續座標（公尺）、拓樸區域、ASCII 渲染、戰爭迷霧
- [x] Pointcrawl 探索系統 — 三層拓樸（地城/城鎮/世界）
- [x] 佈陣階段 (deployment.py) — 遭遇判定 + 佈陣 + 渲染

## Phase 2: Bone Engine 補完
> 里程碑：純文字 CLI 可跑完「探索→遭遇→佈陣→戰鬥→休息」完整循環
> 開發順序：① 物理引擎 → ② 事件+協調 → ③ 實體+規則 → ④ TUI 整合

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
- [x] Step 1: 法術資料庫 — JSON 格式定義檔（戲法 + 1~3 環，36 個法術）
- [x] Step 2: 法術載入器 — load_spell_db, get_spell_by_name
- [x] Step 3: 施法前置檢查 — can_cast（法術欄位/準備/成分）
- [x] Step 4: 法術效果執行 — cast_spell 主函式（傷害/治療/狀態分支）
- [x] Step 5: 專注機制 — 開始/中斷專注 + 戰鬥中自動檢定
- [x] Step 5b: 法術成分系統 — V/S/M 欄位 + can_cast 檢查 + 材料消耗
- [x] Step 5c: 升環擴充 — 目標數/專注解除/持續時間/範圍/召喚（model 欄位全開，引擎先做①③）
- [ ] Step 6: 範圍法術 — 已併入 ③ 實體+規則（統一用 BoundingShape）
- [x] Step 7: 單元測試 — test_spells.py（57 tests）

### 2-S: 空間系統重構（連續空間 + Wall AABB + 碰撞） ✅
> Grid 系統已全面移除：TerrainTile/grid_size_m/to_grid/from_grid/grid_distance/terrain[y][x] 全數刪除
> 改為純連續空間（公尺 float）+ Wall AABB 障礙物清單
> 剩餘項目已併入 ①~④ 各階段

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

### 2-H: TUI 戰鬥介面 (tui/)
> 用 Textual 建構四面板 TUI，邊玩邊測 Bone Engine
- [x] Step 1: pyproject.toml 新增 tui optional dependency (textual>=0.50)
- [x] Step 2: demo.py — 3 PC vs 2 哥布林 demo 場景
- [x] Step 3: app.py — 四面板佈局（地圖/狀態/紀錄/輸入）
- [x] Step 4: 玩家攻擊指令 (attack <目標>)
- [x] Step 5: 怪物自動行動修復 — set_timer 排程 + 攻擊後自動結束回合
- [x] Step 6: 法術指令 (cast <法術> <目標>)
- [x] Step 7: 移動指令 (move <方向/座標>)

### 2-H-fix: TUI 戰鬥 Bug 修復（5 項）
- [x] Fix 2: spawn/prop 座標 grid→公尺轉換（loader.py）
- [x] Fix 3: 玩家移動輸入 grid→公尺 + _step_move_to 改用 move_entity
- [x] Fix 4: 近戰攻擊射程判定統一公尺（combat.py）
- [x] Fix 5: 近戰自動移動提示（Fix 4 修完後自動修復）
- [x] Fix 1: 0 HP 角色自動 UNCONSCIOUS + 回合跳過

### 2-I: 三層測試框架
> AI 自動對戰整合測試 + 結構化 Log + D&D 規則斷言
- [x] Phase A: 基礎設施 — Action/PlayerStrategy/RandomStrategy/GreedyMeleeStrategy/ScriptedStrategy + CombatLogger
- [x] Phase B: HeadlessCombatRunner — 純 Python 無頭戰鬥引擎（BFS 移動 + 攻擊 + OA + 條件跳過）
- [x] Phase C: 規則斷言 + 整合測試 — 7 項 D&D 斷言 + 24 個 pytest（多種子壓力測試）
- [x] Phase D: 人類試玩 Log 強化 — app.py 每輪自動記錄地圖快照 + 狀態面板到 log 檔

### 2-J/2-T: 已併入 ④ TUI 渲染 + 介面整合
> 詳見上方 ④ 階段

### 2-M: 資料模型重構（models-refactor）
> 📄 設計文件：[`docs/data_model.md`](docs/data_model.md)
> 目的：`models.py`（898 行）拆分為多檔案架構，提煉共基類，消除重複邏輯
- [x] Phase A: models.py 拆分為 models/ package（純搬移，`__init__.py` 全量 re-export）
- [x] Phase B: Combatant 基類 — 提煉 Character/Monster 共有 11 欄位 + ability_modifier/has_condition；型別別名統一
- [x] Phase C: Query Methods 集中 + 重複消除
  - [x] C-1: MapState 新增 get_actor / get_actor_position / alive_actors methods
  - [x] C-2: CombatState 新增 current_entry method
  - [x] C-3: 移除 6 處重複 lookup（movement.py、spatial.py、combat.py、combat_logger.py、combat_runner.py；combat_bridge.py 保留 wrapper）
  - [x] C-4: 攻擊加值集中 — 4 處合併為 combat.calc_weapon_attack_bonus() / calc_damage_modifier()
  - [x] C-5: 距離計算統一 — 13 處 inline math.sqrt 改用 distance() / Position.distance_to()
  - [x] C-6: DAMAGE_TYPE_ZH 字典去重 — spells.py 為 canonical，combat_bridge.py import
- [x] Phase C+: Combatant 型別傳播 + 清理
  - [x] C+-1: Combatant 型別 quick wins（_get_size / grapple_save_dc / _get_save_bonus / move_toward_target）
  - [x] C+-2: TUI dict 型別統一 dict[UUID, Combatant]（10 個檔案）
  - [x] C+-3: 死程式碼移除 — start_concentration / is_concentrating / resolve_weapon_mastery
- [x] Phase D: Spell 子模型 + 死欄位清理
  - [x] D-1: 新增 SpellComponents / SpellAoe / SpellUpcast 子模型 + model_validator flat→nested 相容
  - [x] D-2: 刪除 3 個死欄位（upcast_duration_map / upcast_aoe_bonus / upcast_no_concentration_at）
  - [x] D-3: 遷移呼叫點（aoe.py 7 行、spells.py 15 行、app.py 6 行、test_spells.py 6 行）
- [ ] Phase E: LLM Context Helpers（⏸ 延後至 Phase 4 前）

### ① 基礎物理引擎 + 幾何系統
> 📄 設計文件：[`docs/bone-engine-v2-design.md`](docs/bone-engine-v2-design.md) §4~§5

- [ ] 2-V A-3: 資料模型擴充 `models.py` — Position.z + TerrainTile.height_m + Actor.size/z/bounds + Material/Fragility 列舉 + Prop 可摧毀欄位+bounds + ShapeType（5種：CIRCLE/RECTANGLE/CONE/LINE/CYLINDER）+ BoundingShape（含方向欄位 direction_deg/angle_deg/length_m/height_m + intersects_line）+ SurfaceEffect（改用 bounds）+ MapState.surfaces + CoverResult
- [ ] 2-V A-4: 材質系統 `bone_engine/materials.py` — MATERIAL_AC 查表 + roll_object_hp + apply_object_damage
- [ ] 2-V A-5 (partial): `test_materials.py`（AC/HP/傷害/摧毀）
- [ ] 2-V Phase E: Actor.size + bounds 全面傳播
  - [ ] E-1: place_actors_at_spawn() 設定 actor.size — 從 Character/Monster 同步
  - [ ] E-2: spatial.py Size.MEDIUM 全面替換 — move_entity/can_end_move_at/check_collision
  - [ ] E-3: pathfinding.py + movement.py 同步 — Minkowski inflation 用真實 mover_size
  - [ ] E-4: 更新既有測試 — 所有 Actor fixture 加 size=Size.MEDIUM（explicit）
- [ ] 2-V Phase C: Z 軸地形
  - [ ] C-1: spatial.py 加高度邏輯 — check_height_traversal + calculate_falling_damage
  - [ ] C-2: move_entity 擴充 — 新增 tz 參數 + 高度差檢查
  - [ ] C-3: Actor.size 傳播 — spatial.py 中 Size.MEDIUM 硬編碼改用 actor.size
  - [ ] C-4: 測試 `test_z_axis.py` — 高度通行/掉落傷害/distance_3d

### ② 事件系統 + 遊戲協調器 + Log
> 📄 設計文件：[`docs/bone-engine-v2-design.md`](docs/bone-engine-v2-design.md) §3, §5
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md)

- [ ] 2-V A-1: 事件系統 `bone_engine/events.py` — GameEvent 基底 + 12 種事件子類 + EventBus
- [ ] 2-V A-2: 雙層 Log `bone_engine/log_layers.py` — SystemLog（結構化）+ NarrativeLog（玩家可讀）
- [ ] 2-V A-5 (partial): `test_events.py`（EventBus 訂閱/發送/歷史）
- [ ] 2-D: 遊戲協調器 (engine.py)
  - [ ] Step 1: GamePhase 列舉 + GameState 模型
  - [ ] Step 2: 狀態轉換邏輯 — transition rules + 各階段進出 hook
  - [ ] Step 3: 回合管理整合 — 串接 combat advance_turn + conditions tick
  - [ ] Step 4: 存檔/讀檔 — GameState 序列化/反序列化（JSON 檔案）
  - [ ] Step 5: CLI demo script — 純文字跑完完整遊戲循環（含存讀檔）
  - [ ] Step 6: 單元測試 — test_engine.py
- [ ] 2-V Phase F: GameStateManager + 事件整合
  - [ ] F-1: `bone_engine/game_state.py` — GameStateManager 包裝 MapState+CombatState+EventBus
  - [ ] F-2: TUI 整合（漸進式）— NarrativeLog 接入 LogManager，逐步遷移 action function
  - [ ] F-3: 測試 `test_game_state.py` — 狀態變更→事件/NarrativeLog 可讀文字/SystemLog 完整記錄

### ③ 實體定義 + 規則效果
> 📄 設計文件：[`docs/bone-engine-v2-design.md`](docs/bone-engine-v2-design.md) §6~§9

- [ ] 2-V Phase B: 表面效果系統
  - [ ] B-1: `bone_engine/surfaces.py` — check_surface_enter/leave + resolve_surface_effect + tick_surfaces_round_start
  - [ ] B-2: 測試 `test_surfaces.py` — 進入/離開幾何判定、傷害骰+豁免、持續回合遞減+過期
- [ ] 2-V Phase D: 掩護系統強化
  - [ ] D-1: spatial.py 統一掩護 API — determine_cover_from_grid() 改名為 determine_cover()，回傳 CoverResult（含掩護物件清單），整合 Bresenham + Prop 掩護 + 可摧毀狀態；test_spatial.py 2 處呼叫改用 .cover_type
  - [ ] D-2: combat.py 加投射物打掩護 — resolve_projectile_vs_cover()
  - [ ] D-3: 測試 `test_cover_v2.py` — Prop 掩護判定/多重掩護取最大/投射物打掩護/物件摧毀後掩護消失
- [ ] 2-B Step 6: 範圍法術 — AoE 判定（統一用 BoundingShape）+ 空間系統整合
- [ ] 2-C: 休息機制 (rest.py)
  - [ ] Step 1: 短休 — Hit Dice 恢復 HP、職業短休資源回復
  - [ ] Step 2: 長休 — 全滿 HP、法術欄位回復、力竭降一級、Hit Dice 回復一半
  - [ ] Step 3: 與 conditions.py 整合（休息結束狀態的自動清除）
  - [ ] Step 4: 單元測試 — test_rest.py

### ④ TUI 渲染 + 介面整合
> 📄 設計文件：[`docs/game-session-design.md`](docs/game-session-design.md)

- [ ] 2-T: TUI 架構重構 — 純規則邏輯從 TUI 搬進 bone_engine
  - [ ] Step 1: 新建 `bone_engine/movement.py` — 移動相關純計算
  - [ ] Step 2: `bone_engine/combat.py` 加借機攻擊觸發查詢
  - [ ] Step 3: 重構 `tui/actions.py` 為薄層
  - [ ] Step 4: 重構 `tui/npc_ai.py` 為薄層
  - [ ] Step 5: 單元測試 — `tests/test_movement.py`
- [ ] 2-J: TUI 戰鬥移動引導重設計
  - [ ] Step 1: 主選單重排 — 攻擊/法術/閃避/撤離置前，移動降至末段
  - [ ] Step 2: 近戰攻擊流程不變
  - [ ] Step 3: 遠程武器佔位詢問
  - [ ] Step 4: 法術佔位詢問
  - [ ] Step 5: 整合測試

### 跨階段：測試補齊
- [ ] 2-E 剩餘項目
  - [ ] test_combat.py — 攻擊/傷害/死亡豁免/武器專精/借機攻擊
  - [ ] test_character.py — 12 職業建構、法術欄位、AC 計算
  - [ ] test_spatial.py — 距離/LOS/掩蔽/移動
  - [ ] test_exploration.py — 節點移動/隱藏通道/子地圖/時間
  - [ ] test_deployment.py — 遭遇判定/佈陣/確認
  - [ ] test_map_renderer.py — ASCII 渲染/戰爭迷霧/佈陣預覽

### 2-K: TUI 大改 — Drawille 點字渲染 + 模組化拆分
> 用 Unicode Braille 2×4 次像素取代 ASCII，實現高解析度棋盤格、平滑 AoE 圓形、精確座標定位
- [x] Phase T-1: 模組化拆分（app.py 2068L → 7 模組：combat_bridge/log_manager/actions/npc_ai/input_handler/app/styles.tcss）
- [x] Phase T-2: BrailleMapCanvas Widget（drawille 渲染：格線/地形/牆壁/角色標記 + Rich 彩色標籤）
- [x] Phase T-3: StatsPanel Widget（先攻序 + HP 血條 + 行動經濟 + 狀態異常）
- [x] Phase T-4: AoE 覆蓋渲染（球/錐/方/線四種形狀預覽 + 稀疏填充 + 射線法判定）
- [x] Phase T-5: 收尾（canvas.py 單元測試 16 項 + todo.md 更新）

### 2-E: Phase 1 已完成模組的測試補齊（剩餘項目已併入跨階段測試）
- [x] conftest.py — 共用 fixtures（std_fighter/wizard/cleric + goblin/skeleton/ogre + rng42）
- [x] test_dice.py — 表達式解析/擲骰/優劣勢/kh/kl/便利函式（39 tests）

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
> 📄 架構總覽：[`docs/architecture.md`](docs/architecture.md)（Gremlin 代理人層）
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
> 📄 架構總覽：[`docs/architecture.md`](docs/architecture.md)（三層記憶架構）
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
> 📄 架構總覽：[`docs/architecture.md`](docs/architecture.md)（六隻 Gremlin 職責）
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
> 📄 架構總覽：[`docs/architecture.md`](docs/architecture.md)（Telegram Bot 層）
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
