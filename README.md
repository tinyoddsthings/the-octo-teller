# T.O.T. - The Octo-Teller

> Telegram 多人 AI 地下城主系統，以 D&D 2024 (5.5e) 為規則基礎。

## 核心概念：哭哭鱆雙引擎

- **Bone Engine（骷髏引擎）**：確定性規則引擎，處理骰子、戰鬥、法術、狀態等機械判定
- **Narrator（章魚說書人）**：LLM 驅動的敘事引擎，負責場景描述、NPC 對話、劇情推進

## 架構

六隻 Gremlin 代理人協作：

| Gremlin | 職責 |
|---------|------|
| **Prep** | 備戰精靈 — 世界生成、Session 準備 |
| **Bone Engine** | 骷髏引擎 — 確定性規則判定 |
| **Narrator** | 章魚說書人 — LLM 敘事生成 |
| **Mimic** | 擬態解析器 — 自然語言 → 結構化動作 |
| **Companion** | AI 隊友 — 信任驅動的自主決策同伴 |
| **Extension** | 延伸精靈 — 脫稿即興處理 |

## 三層記憶系統

| 層級 | 技術 | 用途 |
|------|------|------|
| Working Memory | Redis | 當前回合狀態、戰鬥追蹤 |
| Episodic Memory | PostgreSQL + pgvector | 冒險歷史、NPC 互動記錄 |
| Semantic Memory | Qdrant RAG | D&D 5e 規則、世界知識檢索 |

## 專案結構

```
src/tot/
├── bot/              # Telegram 介面 (aiogram 3)
│   ├── handlers/     # 指令處理（遊戲/戰鬥/角色/設定/管理）
│   ├── tma/          # Telegram Mini Apps (Phase 5+)
│   └── ...
├── gremlins/         # 六隻 Gremlin 代理人
│   ├── bone_engine/  # 骷髏引擎 — 骰子/戰鬥/法術/狀態/休息
│   ├── narrator/     # 章魚說書人 — LLM 敘事 + prompt 模板
│   ├── mimic/        # 擬態解析器 — NL → 結構化動作
│   ├── companion/    # AI 隊友 — 信任/個性/情境自主決策
│   ├── prep/         # 備戰精靈 — 世界生成/session 準備
│   └── extension/    # 延伸精靈 — 脫稿即興
├── memory/           # 三層記憶系統
├── data/             # D&D 5e 靜態資料（SRD/職業/法術/怪物...）
├── visuals/          # 視覺化 — 地圖/面板/AI 圖片 (Phase 5+)
└── combat_ai/        # 怪物 AI — Behavior Tree + GOAP
```

## 技術棧

| 類別 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| 套件管理 | uv (src layout) |
| Bot 框架 | aiogram 3 |
| LLM | Anthropic Claude API |
| 資料驗證 | Pydantic v2 |
| 資料庫 | Redis / PostgreSQL + pgvector / Qdrant |
| CI/CD | GitHub Actions (ruff lint + pytest) |
| Commit 規範 | Commitizen (conventional commits) |

## 開發

```bash
# 安裝所有依賴
uv sync --all-extras

# 只裝基礎 + 開發工具
uv sync --extra dev

# 執行測試
uv run pytest

# Lint 檢查
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## Git 工作流程

1. 從 `main` 建立 `dev/feature-name` branch
2. 開發、commit（帶 `#issue編號`、中文 commit message）
3. 推送並開 PR
4. CI 通過後 merge

## 開發階段

| Phase | 內容 | 狀態 |
|-------|------|------|
| 0 | 專案骨架 + 知識庫遷移 | ✅ 完成 |
| 1 | Bone Engine 核心 — 戰鬥與空間（骰子/角色/戰鬥/地圖/探索/佈陣） | ✅ 完成 |
| 2 | Bone Engine 補完 — 法術、狀態、休息、協調器 | 🔨 進行中 |
| 3 | 怪物 AI + 升級系統 | 待開始 |
| 4 | Mimic + Narrator（LLM 意圖解析 + 敘事） | 待開始 |
| 5 | 三層記憶系統（Redis / PG+pgvector / Qdrant） | 待開始 |
| 6 | 進階 Gremlin + 系統擴展（Companion / Prep / Extension） | 待開始 |
| 7 | Telegram Bot 介面 | 待開始 |
| 8 | 視覺化 + Mini Apps | 待開始 |
| 9 | 生產化（Docker、CI/CD、監控） | 待開始 |

詳見 [todo.md](todo.md) 了解各 Phase 細項。
