# T.O.T. - The Octo-Teller 開發追蹤

## Phase 0: 專案骨架
- [x] 初始化 git repo
- [x] 建立完整目錄結構
- [x] pyproject.toml (uv src layout)
- [x] .gitignore / README.md / CLAUDE.md
- [x] docker-compose.yml (Redis placeholder)
- [x] 所有 __init__.py 與 placeholder 檔案
- [x] 遷移知識庫（reference / glossary / dm_settings）從 memory/dnd/
- [x] 遷移既有 bot.py 邏輯為參考文件 (docs/legacy/)

## Phase 1: Bone Engine 核心
- [x] Pydantic data models (Character, Monster, Spell, Item, Condition)
- [x] 骰子系統 (dice.py) — d4~d100、advantage/disadvantage、modifier
- [x] 角色建立流程 (character.py) — 種族/職業/屬性/技能
- [x] 戰鬥引擎 (combat.py) — 先攻、回合制、攻擊/傷害判定
- [ ] 戰鬥地圖系統 — 格子座標、拓樸區域、ASCII 渲染、戰爭迷霧
  - [x] Step 1: 座標系統模型 — Position, Entity, Actor, Prop, TerrainTile
  - [x] Step 2: 拓樸與地圖模型 — Zone, ZoneConnection, MapManifest, MapState
  - [x] Step 3: 空間邏輯核心 — grid_distance, bresenham_line, has_line_of_sight
  - [x] Step 4: 實體查詢與移動 — get_entities_at, move_entity, has_hostile_within_melee
  - [ ] Step 5: 掩蔽與區域查詢 — determine_cover_from_grid, zone_for_position, place_actors_at_spawn
  - [ ] Step 6: 地圖載入器 — load_map_manifest + tutorial_room.json
  - [ ] Step 7: ASCII 渲染引擎 — MapRenderer (Z-index 圖層 + 座標軸)
  - [ ] Step 8: 戰爭迷霧 — render_viewport + fog_of_war
- [ ] 法術系統 (spells.py) — 施法、法術位、專注
- [ ] 狀態系統 (conditions.py) — 12 種基礎狀態 + 堆疊規則
- [ ] 休息機制 (rest.py) — 短休/長休、HP/法術位恢復
- [ ] 單元測試覆蓋率 > 90%

## Phase 2: 記憶系統
- [ ] Working Memory (Redis) — 當前戰鬥/場景狀態
- [ ] Episodic Memory (PostgreSQL + pgvector) — 冒險歷史、NPC 互動
- [ ] Semantic Memory (Qdrant RAG) — SRD 規則、世界知識
- [ ] Context Assembler — 根據情境組裝 LLM prompt context
- [ ] 記憶清理與壓縮策略

## Phase 3: Narrator + Mimic
- [ ] LLM Client (llm_client.py) — Anthropic API wrapper
- [ ] Narrator Gremlin — 場景描述、戰鬥旁白、NPC 對話
- [ ] Narrative Styles — 6 種敘事風格切換
- [ ] Difficulty Adaptation — 根據玩家經驗調整描述深度
- [ ] Mimic Gremlin — 自然語言意圖解析
- [ ] Intent Classification — 動作/對話/查詢/系統指令
- [ ] Structured Action Output — NL → GameAction Pydantic model
- [ ] Prompt 模板系統 (prompts/)

## Phase 4: Telegram Bot 介面
- [ ] Bot 啟動與設定 (app.py)
- [ ] Game Handler — 開團/加入/離開/存檔/讀檔
- [ ] Combat Handler — 戰鬥流程 UI
- [ ] Character Handler — 角色建立/查看/升級
- [ ] DM Settings Handler — 敘事風格/難度設定
- [ ] Admin Handler — 管理員指令
- [ ] Inline Keyboards — 動作選單、骰子按鈕
- [ ] Formatters — Telegram MarkdownV2 格式化
- [ ] Middleware — 權限檢查、session 管理、錯誤處理

## Phase 5: 視覺化 + Mini Apps
- [ ] 地圖渲染器 (map_renderer.py) — ASCII/圖片混合
- [ ] 面板渲染器 (panel_renderer.py) — 角色卡、戰鬥面板
- [ ] AI 圖片生成 (ai_gen.py) — 場景/NPC 插圖
- [ ] Telegram Mini App 骨架
- [ ] 互動式角色卡介面
- [ ] 戰鬥地圖互動

## Phase 6: 進階系統
- [ ] Prep Gremlin — 世界生成、Session 準備
- [ ] Extension Gremlin — 脫稿即興、自定義規則
- [ ] 怪物 AI (combat_ai/) — Behavior Tree + GOAP
- [ ] 怪物族群 AI (goblinoid, undead, beast, boss)
- [ ] 多團同時進行支援
- [ ] 存檔/讀檔系統

## Phase 7: 生產化
- [ ] Docker 化（bot + 所有服務）
- [ ] CI/CD pipeline
- [ ] 監控與日誌
- [ ] 效能優化（LLM 快取、批次查詢）
- [ ] 使用者文件
- [ ] 壓力測試
