# T.O.T. - The Octo-Teller 開發規範

## 語言
- 程式碼：英文（變數名、函式名、註解）
- 文件、commit message、issue：繁體中文
- Prompt 模板：英文

## 規則基礎
- D&D 2024 (5.5e)，非舊版 5e

## 架構概覽
- **雙引擎**：Bone Engine（確定性規則）+ Narrator（LLM 敘事）
- **六隻 Gremlin**：Prep / Bone Engine / Narrator / Mimic / Companion / Extension
- **三層記憶**：Working (Redis) / Episodic (PG+pgvector) / Semantic (Qdrant)
- **介面**：Telegram Bot (aiogram 3) + Mini Apps (Phase 5+)

## 專案結構
- `src/tot/` — 主套件（uv src layout）
- `src/tot/bot/` — Telegram 介面層
- `src/tot/gremlins/` — 五隻代理人
- `src/tot/memory/` — 三層記憶系統
- `src/tot/data/` — 靜態資料（SRD、reference、glossary）
- `src/tot/visuals/` — 視覺化（Phase 5+）
- `src/tot/combat_ai/` — 怪物 AI

## Git 規範
- 不在 main 上直接 commit，修改在 dev branch 上進行，透過 PR 合併到 main
- 每個 commit 都要帶 `#issue編號`
- commit message 用繁中
- Signed-off-by 必填
- pre-push hook 用 `uv run --frozen pytest` 避免 lock file 被意外修改

## 開發原則
- Bone Engine 必須是純確定性的，不依賴 LLM
- 所有 LLM 呼叫只在 Narrator / Mimic / Companion / Extension 中
- 記憶層對上層透明，透過 context.py 組裝 LLM context
- Pydantic model 用於所有跨模組資料傳遞
