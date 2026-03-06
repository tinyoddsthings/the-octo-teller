# T.O.T. - The Octo-Teller

Telegram 多人 AI 地下城主系統，以 D&D 5e SRD 為規則基礎。

## 核心概念：哭哭鱆雙引擎

- **Bone Engine（骷髏引擎）**：確定性規則引擎，處理骰子、戰鬥、法術、狀態等機械判定
- **Narrator（章魚說書人）**：LLM 驅動的敘事引擎，負責場景描述、NPC 對話、劇情推進

## 架構

五隻 Gremlin 代理人協作：

| Gremlin | 職責 |
|---------|------|
| **Prep** | 備戰精靈 — 世界生成、Session 準備 |
| **Bone Engine** | 骷髏引擎 — 確定性規則判定 |
| **Narrator** | 章魚說書人 — LLM 敘事生成 |
| **Mimic** | 擬態解析器 — 自然語言 → 結構化動作 |
| **Extension** | 延伸精靈 — 脫稿即興處理 |

## 三層記憶系統

- **Working Memory**：Redis — 當前回合狀態
- **Episodic Memory**：PostgreSQL + pgvector — 冒險歷史
- **Semantic Memory**：Qdrant RAG — 規則與世界知識

## 開發

```bash
uv sync --all-extras
uv run pytest
```

## 狀態

Phase 0 — 專案骨架建立中
