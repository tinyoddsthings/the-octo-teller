# T.O.T. GameSession 架構設計

> GameSession 是 Bone Engine 與介面層之間的抽象，讓 CLI 和 Telegram 共用同一套遊戲邏輯。

---

## 1. 分層架構

```
CLI (Textual TUI)  ──┐
                      ├──→ GameSession ──→ Bone Engine
Telegram Bot (未來) ──┘    (遊戲狀態機)    (規則計算)
```

**原則**：UI 層只負責「渲染事件」和「收集輸入」，不直接呼叫 Bone Engine。

---

## 2. GameSession 職責

| 職責 | 說明 |
|------|------|
| 遊戲循環 | 驅動 探索→佈陣→戰鬥→休息 的主迴圈 |
| 狀態轉換 | 管理 GamePhase 轉換、進出各階段的 hook |
| 輸入收集 | 等待玩家輸入，轉為結構化 GameAction |
| 事件發送 | 輸出結構化「畫面更新」事件（GameEvent），UI 層只負責渲染 |
| 存讀檔 | GameState 序列化/反序列化 |

---

## 3. GameEvent 設計

UI 層不直接呼叫 Bone Engine，而是收到結構化事件後自行渲染：

```python
class GameEvent(BaseModel):
    type: EventType           # NARRATIVE, COMBAT_RESULT, MAP_UPDATE, STATUS_CHANGE, PROMPT...
    data: dict                # 事件內容（依 type 不同）
    requires_input: bool      # 是否需要等待玩家輸入
```

**好處**：CLI 可以把 `COMBAT_RESULT` 渲染成彩色文字 + 表格；Telegram 可以渲染成 MarkdownV2 + inline keyboard。核心邏輯完全不變。

---

## 4. 存讀檔系統

### 自動存檔

- 每次階段轉換時自動存檔（進入戰鬥、戰鬥結束、長休後）
- 存檔檔案：`~/.tot/saves/<save_name>.json`

### 手動存檔

- `save` 指令：任意時刻存檔
- `save <name>`：命名存檔
- `load`：列出存檔 → 選擇載入
- `load <name>`：載入指定存檔

### 存檔內容

序列化完整 `GameState`：角色隊伍、地圖狀態、探索進度、戰鬥狀態（若在戰鬥中）。

---

## 5. 開發路線

```
Phase 2 收尾
├── 2-C: rest.py（短休/長休）
└── 2-D: engine.py（GamePhase 狀態機 + GameSession 抽象層）
    ↓
CLI 介面（新 Phase，插在 2-D 之後）
├── Textual TUI 骨架（四面板佈局）
├── 各遊戲階段的 UI 渲染
├── Tab 補全 + 指令歷史
└── 存讀檔 UI
    ↓
Tutorial Dungeon 完整跑通
├── 用 tutorial_dungeon.json 跑完一場完整遊戲
├── 遊戲節奏調整、資訊密度平衡
└── 規則邊界案例修正
    ↓
Phase 4: Narrator + Mimic（接 LLM 讓體驗有靈魂）
    ↓
品質調整、平衡測試
    ↓
Phase 7: 搬上 Telegram（換 I/O 層，核心不動）
```

---

## 6. 與現有架構的關係

- **engine.py（2-D）** 就是 GameSession 的實作位置 — 設計時直接讓它輸出 GameEvent
- **models.py** 新增 `GameEvent`、`EventType`、`GamePhase` 等型別
- **不影響 Bone Engine**：GameSession 是純粹的「上層協調器」，不修改既有規則模組
