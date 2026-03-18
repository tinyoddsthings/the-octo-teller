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

- [ ] `move_entity()` 強制位移路徑檢測 — `forced=True` 時用 Liang-Barsky 掃描路徑，碰牆停在牆前 📄 [`docs/spatial-combat-design.md`](docs/spatial-combat-design.md) §4 ADR-2.5
- [ ] 2-V A-3: 資料模型擴充 `models.py`
  - [x] Material/Fragility 列舉
  - [x] ShapeType（5種：CIRCLE/RECTANGLE/CONE/LINE/CYLINDER）+ BoundingShape（含 intersects_line）
  - [x] Prop 可摧毀欄位 + bounds + damage_resistances
  - [ ] Position.z + TerrainTile.height_m
  - [ ] Actor.size/z/bounds
  - [ ] SurfaceEffect（改用 bounds）+ MapState.surfaces
  - [ ] CoverResult
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
  - [ ] D-0: pathfinding.py docstring 補充 — `find_path_to_range()` 加呼叫者須先透過 `build_actor_lists()` 的提示 📄 [`docs/spatial-combat-design.md`](docs/spatial-combat-design.md) §3 ADR-2
  - [ ] D-1: spatial.py `determine_cover()` 重寫為 **Corner-Ray 演算法**（攻擊者 4 角→目標 4 角 = 16 射線），回傳 CoverResult（含掩護物件清單），整合 Prop 掩護 + 可摧毀狀態 📄 [`docs/spatial-combat-design.md`](docs/spatial-combat-design.md) §2 ADR-1
  - [ ] D-2: combat.py 加投射物打掩護 — resolve_projectile_vs_cover()
  - [ ] D-3: 測試 `test_cover_v2.py` — Prop 掩護判定/多重掩護取最大/投射物打掩護/物件摧毀後掩護消失
- [ ] 2-B Step 6: 範圍法術 — AoE 判定（統一用 BoundingShape）+ 空間系統整合
- [ ] 2-C: 休息機制 (rest.py)
  - [x] Step 1: 短休 — Hit Dice 恢復 HP（自動分配版，2-X E-0.3 實作）
  - [x] Step 2: 長休 — 全滿 HP、法術欄位回復、Hit Dice 回復一半（2-X E-0.3 實作）
  - [ ] Step 3: 與 conditions.py 整合（休息結束狀態的自動清除）
  - [x] Step 4: 單元測試 — test_rest.py（11 tests）

### 2-X: 探索 TUI
> 里程碑：Pointcrawl 探索可用 TUI 測試（移動/搜索/物品/開門/休息）
> 📄 設計文件：[`docs/exploration-design.md`](docs/exploration-design.md)
- [x] E-0.1: bone_engine/checks.py — 技能/屬性檢定包裝（12 tests）
- [x] E-0.2: NodeItem 模型 + exploration.py 擴充（物品搜索/拿取/POI/被動感知）
- [x] E-0.3: bone_engine/rest.py — 短休/長休（2-C Steps 1-2 子集，11 tests）
- [x] E-1.1: tui/exploration/ package + demo + explore.sh + wilderness_trail.json
- [x] E-1.2: explore_map_widget.py — Pointcrawl 節點圖 Widget
- [x] E-1.3: app.py + styles.tcss + explore_status.py
- [x] E-2.1: explore_input.py 狀態機 + 移動指令
- [x] E-2.2: 門互動 + 角色選擇 + 鑰匙
- [x] E-2.3: 搜索指令（通道 + 物品）
- [x] E-2.4: 查看 + 拿取 + POI + 休息
- [x] E-3.1: status/map/help/load 指令
- [x] E-3.2: docs/exploration-design.md + todo.md 延後功能文件化

### 🔥 2-XB: 渲染架構重構 + Prop Prefab 系統（最高優先）
> 📄 設計文件：[`docs/rendering-refactor-design.md`](docs/rendering-refactor-design.md)
> 📄 計畫詳情：[`.claude-personal/plans/parallel-nibbling-whale.md`](.claude-personal/plans/parallel-nibbling-whale.md)
> 里程碑：MapState → RenderBuffer → BrailleMapCanvas 三層分離；地圖 JSON prefab 化；entity.symbol 移除
> **前置：** 2-XA Phase 1~3 已完成

- [x] **Phase 0a**: `models/map.py` — Entity / Wall 移除 symbol 欄位
- [x] **Phase 0b**: bone_engine 四處 — aoe.py / deployment.py / spatial.py / area_explore.py 移除 symbol=
- [x] **Phase 0c**: TUI emoji_map — demo.py 移除 emoji_map；app.py / stats_panel / input_handler 改用 combatant_marker()
- [x] **Phase 0d**: 刪除 `src/tot/visuals/map_renderer.py`；combat_logger.py 改用 `render_braille_map()`
- [x] **Phase 0e**: tests 移除 symbol=（test_aoe / test_geometry / test_spatial）
- [x] **Phase 1a**: 新建 `src/tot/data/prop_defs/`（structural / interactive / terrain prefab）
- [x] **Phase 1b**: `loader.py` 新增 `_expand_props()` — prefab 展開邏輯
- [x] **Phase 1c**: `cave_explore.json` / `tutorial_room.json` — props 改用 prefab，移除 symbol
- [x] **Phase 2a**: 新建 `src/tot/tui/render_buffer.py`（RenderLayer / TextureType / RenderItem / RenderBuffer）
- [x] **Phase 2b**: `canvas.py` — 改用 RenderBuffer 驅動渲染，新增 _fill_circle / _outline_circle
- [x] **Phase 2c**: `app.py` — `_refresh_map()` 改建 RenderBuffer 傳給 canvas
- [x] **Phase 2d**: `geometry.py` — `extract_static_obstacles()` 改用 prop.bounds 計算 AABB
- [x] **Phase 3**: `render_braille_map()` / `render_to_plain()` 改用 RenderBuffer
- [x] **Phase 4**: 新增 `tests/test_prop_prefab.py`（14 tests）/ `tests/test_render_buffer.py`（17 tests）；全測試通過
- [x] **Bug**: Actor 靠近牆壁/Prop 時 braille dots 吃圖 — tile_canvas.py 字元級 winner-take-all 以少量 actor dots 取代整格牆壁 dots（修復：改為 bitwise OR 合併 dots + 最高 priority 上色，與 canvas.py 一致）

### 2-XA: Area 自由探索（Pointcrawl + Area 混合模式）
> 里程碑：進入 Pointcrawl 節點後可自由移動、搜索物件、拾取物品
> 📄 計畫文件：[`.claude-personal/plans/parallel-nibbling-whale.md`](.claude-personal/plans/parallel-nibbling-whale.md)
- [x] Phase 1: 模型層擴展 — LootEntry + Prop 探索欄位 + AreaExploreState
- [x] Phase 2: bone_engine/area_explore.py — enter/exit/move/search/take/terrain
- [x] Phase 3: cave_explore.json 探索專用地圖（25×20m 洞穴）
- [x] Phase 4: TUI Area 模式 — BrailleMapCanvas 切換 + 座標移動 + XY 軸刻度
- [x] Phase 5: Prop 互動完整流程 — 搜索→發現→拾取→鑰匙開鎖
- [x] Phase 6: 地形效果 + tests/test_area_explore.py（23 + 18 = 41 tests）

### 2-XE: 危在松溪教學冒險 — 系統功能搭建
> 以官方入門冒險「危在松溪」為劇本，邊搭建缺失的系統功能
> 📄 計畫文件：[`.claude-personal/plans/`](.claude-personal/plans/)

**Stage 1-3: 背包 + 鑰匙/門 + TUI use 指令** ✅
- [x] `models/map.py` — Prop 新增 `is_locked/lock_dc/key_item` 鎖定欄位
- [x] `models/exploration.py` — AreaExploreState 新增 `collected_keys`
- [x] `structural.py` — iron_gate_locked 加 `is_locked=True, interactable=True`
- [x] `cave_explore.json` — exit_north 加 `is_locked/lock_dc/key_item`
- [x] `area_explore.py` — 新增 `loot_to_item/transfer_loot_to_inventory/unlock_area_prop/get_nearby_doors` + `take_prop_loot` 鑰匙自動註冊
- [x] `explore_input.py` — 新增 `AREA_USE_PROP/ACTION/CHAR` 三階段 use 指令 + `_exit_area_mode` 背包轉移與鑰匙同步
- [x] 測試：62 tests 全過（新增 14 tests）

**Stage XE-A: 資料模型 + 條件評估器** ✅
- [x] `models/adventure.py` — AdventureScript/State/NpcDef/DialogueLine/ScriptEvent/EventTrigger/EventAction
- [x] `bone_engine/adventure.py` — evaluate_condition()（has/not/all/any/gte/lt/timer/within/elapsed）
- [x] `models/__init__.py` — re-export 所有冒險模型
- [x] `tests/test_adventure.py` — 41 tests（條件評估 + 序列化）

**Stage XE-B: 事件引擎** ✅
- [x] `bone_engine/adventure.py` — check_events() + execute_event()
- [x] `tests/test_adventure.py` — 23 tests（觸發比對/once/條件/執行/state 不變性）

**Stage XE-C: 對話引擎** ✅
- [x] `bone_engine/adventure.py` — get_available_npcs/lines() + advance_dialogue()
- [x] `tests/test_adventure.py` — 14 tests（NPC 位置/頂層/next_lines/條件分支/對話鏈）

**Stage XE-D: 冒險載入器** ✅
- [x] `data/adventures/test_adventure.json` — 測試用迷你冒險劇本
- [x] `bone_engine/adventure.py` — load_adventure() + init_adventure_state()
- [x] `tests/test_adventure.py` — 11 tests（檔名載入/NPC/事件/初始化/獨立性）

**Stage XE-E: TUI 整合 — 事件鉤子** ✅
- [x] `explore_input.py` — `_fire_events()` + `_process_event_actions()` 共用事件處理
- [x] `_on_enter_node()` 鉤子呼叫 `check_events(trigger_type="enter_node")`
- [x] `_handle_take_select()` 鉤子呼叫 `check_events(trigger_type="take_item")`
- [x] 支援 action: narrate/tutorial/reveal_node/reveal_edge/add_item

**Stage XE-F: TUI 整合 — talk 指令** ✅
- [x] ExplorePhase 新增 `TALK_SELECT` / `DIALOGUE`
- [x] `_show_talk_menu()` — NPC 列表（單一 NPC 自動開始）
- [x] `_start_dialogue()` + `_show_dialogue_options()` + `_display_and_advance()`
- [x] `_handle_dialogue()` — 選擇回應 + 自動推進無選擇對話
- [x] `_end_dialogue()` — 清理 active_dialogue
- [x] 主選單 + help 加入 talk 指令

**Stage XE-Tool: 冒險劇本生成工具（Adventure Author）** ✅
> Markdown → JSON 轉換工具，讓用戶用 MD 寫冒險、工具編譯成引擎可讀 JSON
- [x] `ir.py` — MapIR/NodeIR/EdgeIR/ItemIR/NpcIR/DialogueIR/ChoiceIR/EventIR/ScriptIR
- [x] `id_gen.py` — slugify() + name_to_id()
- [x] `scaffold.py` — `adventure-author new` 建資料夾 + 範例 MD
- [x] `parser.py` — parse_meta/map/npc/chapter（MD → IR）
- [x] `map_builder.py` — MapIR → ExplorationMap dict（Pydantic 驗證通過）
- [x] `script_builder.py` — ScriptIR → AdventureScript dict（Pydantic 驗證通過）
- [x] `cli.py` — new/build/build-map/validate 四個指令
- [x] 測試：89 tests 全過

**Stage XE-Encounter: Encounter 語法 + /ingest Skill** ✅
> 地城節點遭遇系統 + 自然語言→結構化 MD 轉換 Skill
- [x] `ir.py` — EncounterIR/EnemyIR/RewardIR dataclass + NodeIR.encounter 欄位
- [x] `parser.py` — encounter: 區塊解析（enemies/rewards/trigger/narration/outcome）
- [x] `models/adventure.py` — EncounterDef/EnemyDef/RewardDef Pydantic 模型
- [x] `models/exploration.py` — ExplorationNode.encounter 欄位
- [x] `map_builder.py` — encounter IR → EncounterDef dict
- [x] `script_builder.py` — encounter auto_win 自動生成 ScriptEvent
- [x] `.claude/skills/adventure-ingest/SKILL.md` — /ingest Skill 工作流程
- [x] `.claude/skills/adventure-ingest/references/md-format-spec.md` — 完整格式規格
- [x] `docs/adventure-author.md` — 工具文件 + encounter 語法
- [x] `README.md` — 開發工具/設計文件區塊
- [x] 測試：101 tests 全過（新增 12 encounter 測試）

**Stage XE-Scene: 場景對話系統（Scene Dialogue System）**
> 多角色場景獨立存在、可自動觸發、可跨檔案引用
> `scenes/*.md` 格式：frontmatter(id/name/trigger/condition/once) + ## 段落(speaker必填/silent/choices/skill_check)
- [x] S-1: IR + Parser（SceneIR + parse_scene + _parse_dialogue_blocks 共用 helper）
- [x] S-2: Builder + Model（SceneDef + DialogueLine.silent + build_script 擴充）
- [x] S-3: Engine（_build_global_line_map + silent 自動推進 + start_scene action）
- [x] S-4: TUI 整合（start_scene 處理 + silent 跳過 + 場景對話查找）
- [x] S-5: Docs + Migration + Scaffold（md-format-spec + SKILL.md + scaffold 完成）
- [x] S-6: dm.md 場景式對話鏈遷移到 scenes/（35 條對話 → 3 個場景檔）

---

#### 📝 冒險內容製作（用 Adventure Author 逐步產出）
> 流程：用戶寫 MD → `adventure-author build` → JSON → 引擎載入
> 資料夾：`adventures/peril_in_pinebrook/`

**Stage 4: 松溪冒險 Markdown 內容**
- [ ] `_meta.md` — 冒險基本資訊 + 初始 flags
- [ ] `maps/pinebrook_village.md` — 松溪村城鎮地圖（town scale）
- [ ] `maps/forest_trail.md` — 森林小徑世界地圖（world scale）
- [ ] `maps/dragon_cave.md` — 幼龍洞穴地城地圖（dungeon scale）
- [ ] `npcs/quinn.md` — 乖因（quest_giver，多場景對話）
- [ ] `npcs/shopkeeper.md` — 雜貨鋪老闆（merchant，常態對話）
- [ ] `chapters/01_arrival.md` — 第一章：抵達松溪
- [ ] `chapters/02_investigation.md` — 第二章：調查巡邏
- [ ] `chapters/03_cave_exploration.md` — 第三章：洞穴探索
- [ ] `adventure-author build` 通過 + JSON 驗證

**Stage 5: 洞穴 Area 戰鬥地圖**
- [ ] `dragon_cave_battle.json` — 幼龍巢穴戰鬥地圖（Prop/Spawn/Wall）
- [ ] cave_explore.json 風格的 Area 地圖（攀岩/冰滑道/龍蛋互動）

**Stage 6: 地圖轉場**
- [x] sub_map 轉場邏輯重構：TUI → bone_engine（MapRegistry + check_sub_map_transition + resolve_parent_map + register_map_tree）
- [ ] `Prop.exit_to_node` 欄位
- [ ] `enter_area()` 從 Pointcrawl 自動進入 Area
- [ ] 靠近 exit Prop 時自動提示轉場

**Stage 7: 洞穴場景整合測試**
- [ ] `test_cave_full_scenario()` — 進入→搜索→拿鑰匙→開門→通過→離開

**Stage 8（延後）: 探索→戰鬥銜接**
- [ ] 節點/Area 觸發戰鬥條件
- [ ] 戰鬥結束後回到探索
- [ ] Living Icicles / Egg Thieves 怪物資料

### 2-X 延後（探索進階）
> 📄 設計文件：[`docs/exploration-design.md`](docs/exploration-design.md)
- [ ] 光照與視覺（LightLevel + Darkvision 感知修正）
- [ ] 行進隊形（MarchingOrder + 前衛/後衛機制）
- [ ] 旅行速度（TravelPace + 感知/隱匿修正）
- [ ] 隨機遭遇（danger_level 消費 + 遭遇表）
- [ ] 陷阱機制（NodeTrap + Investigation/Thieves' Tools）
- [ ] 時間壓力（火把/法術持續/NPC 行程）
- [ ] 探索→戰鬥切換（遭遇判定 → CombatTUI）
- [ ] 野外地形效果（困難地形/天氣/能見度）

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

### 2-XC: 圖例完整化 + Prop 視覺區分 ✅
> 圖例動態化完成後的視覺改善：Prop 元素加入圖例、各類型元素顏色可區分
- [x] PROP_TILES 加 legend_label + 改顏色（門黃/紅、物品紫、障礙物/裝飾 cyan）
- [x] build_legend_lines() 加 present_props 參數，圖例動態顯示 prop
- [x] render_buffer.py _add_props() style 改用 resolve_prop_tile().fg（不再硬編碼 yellow）
- [x] tile_canvas.py _build_dynamic_legend() 分離 prop tiles 掃描
- [x] 門渲染簡化 — 移除十字/豎線紋理，統一用碰撞體積矩形外框（開門黃/鎖門紅，同形狀換色）
  - [x] render_buffer.py 門一律 FILL texture（開門也畫碰撞外框）
  - [x] tile_canvas.py _fill_prop() 跳過 door（不畫 grid tile）
  - [x] tiles.py _tex_door() 統一矩形外框紋理
- [x] 圖例多字元圖標 — Prop/Actor 改用 4×2 chars wide braille icon（形狀可辨識）
  - [x] braille_wide_sample() + _braille_circle_wide() + _braille_diamond_wide()
  - [x] build_legend_lines() 支援 _append_wide_entries（2 行高 icon）
  - [x] 修復 BRAILLE_TEXTURES key mismatch（decoration_blocking/nonblocking 未註冊）
- [x] 測試更新（562 tests 全過）

### 2-XD: Prop 碰撞體積 + 物件免疫/抗性 + 互動距離 ✅
> Prop bounds 系統完整化 + D&D 2024 物件規則 + 邊緣距離互動
- [x] `models/map.py` — Prop 新增 `damage_resistances` 欄位
- [x] `structural.py` — 全 prefab 補 D&D 物件免疫（Poison, Psychic）+ 材質抗性
- [x] `interactive.py` — stone_chest 加 bounds(0.9×0.6) + is_blocking；glowing_mushrooms 加 TINY size、無碰撞
- [x] `render_buffer.py` — 移除 `_size_to_render_bounds()`，統一 fallback `_INLINE_PROP_FALLBACK_BOUNDS`(1.0×1.0m)
- [x] `geometry.py` — `_PROP_HALF` 0.75→0.5 對齊 1.0m fallback
- [x] `area_explore.py` — `INTERACT_RADIUS_M = 0.5`（邊緣距離）、`_edge_gap()` 函式
- [x] `tiles.py` — `_shape_rect_narrow()` 門圖例 + 物品改 marker
- [x] `enums.py` — `RESILIENT` HP 倍率 2→3
- [x] 測試：新增 TestObjectImmunityAndResistance / TestExplicitBounds / TestInlinePropFallbackBounds

### 低優先備忘（空間幾何 ADR）
> 📄 完整分析：[`docs/spatial-combat-design.md`](docs/spatial-combat-design.md)
- [ ] Braille 長寬比驗證 — 目視確認 3m×3m 正方形房間渲染為正方形（📄 §5 ADR-3）
- [x] 距離計算哲學文件化 — 維持純歐氏距離，UI 層做 5 呎 snap 顯示（📄 §6 ADR-4）

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
