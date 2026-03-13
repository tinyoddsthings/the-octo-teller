# 遊戲時鐘系統設計文件

## 設計原則

1. **統一單位**：所有時間以**秒**為底層單位
2. **探索用現實時間**：玩家花多少現實時間探索，遊戲世界就過多少時間
3. **戰鬥用輪次**：每輪固定 +6 秒，且必須**所有戰鬥者都行動完**才算一輪
4. **效果用絕對到期秒數**：不再倒數，改為比對 `clock.total_seconds >= expires_at`

---

## GameClock 設計

### 資料模型

```python
class GameClock(BaseModel):
    """遊戲時鐘——單一時間來源。"""

    # 遊戲世界的起始秒數（例：Day 1 08:00 = 28800）
    in_game_start_second: int = 28800

    # 所有顯式事件的累積秒數（戰鬥輪、休息、開鎖、儀式法術等）
    accumulated_seconds: int = 0
```

> `GameClock` 可序列化，可存檔/讀檔。

### Runtime 時鐘（不序列化）

```python
# 探索模式開始時紀錄的 time.monotonic() 時間戳
# None = 目前在戰鬥中（現實時間暫停）
_explore_real_start: float | None
```

### 屬性

```python
@property
def total_seconds(self) -> int:
    """目前遊戲世界的絕對秒數。"""
    real = int(time.monotonic() - self._explore_real_start) if self._explore_real_start else 0
    return self.in_game_start_second + self.accumulated_seconds + real
```

### 方法

| 方法 | 呼叫時機 |
|------|---------|
| `start_exploration()` | 遊戲啟動 / 從戰鬥返回探索 |
| `pause_exploration()` | 進入戰鬥 / 執行耗時事件前 |
| `resume_exploration()` | 耗時事件結束後 |
| `add_combat_round()` | `CombatState.round_number` 遞增時（+6秒） |
| `add_event(seconds)` | 開鎖、休息、儀式法術等 |

### 方法實作草案

```python
def start_exploration(self) -> None:
    """開始計算現實時間（遊戲啟動 / 從戰鬥返回）。"""
    self._explore_real_start = time.monotonic()

def pause_exploration(self) -> None:
    """暫停現實時間（進入戰鬥 / 執行耗時事件）。"""
    if self._explore_real_start is not None:
        self.accumulated_seconds += int(time.monotonic() - self._explore_real_start)
        self._explore_real_start = None

def resume_exploration(self) -> None:
    """恢復現實時間（耗時事件結束後）。"""
    self._explore_real_start = time.monotonic()

def add_combat_round(self) -> None:
    """戰鬥一輪結束（所有戰鬥者都行動完）。"""
    self.accumulated_seconds += 6

def add_event(self, seconds: int) -> None:
    """顯式耗時事件（開鎖、休息、儀式法術等）。
    自動暫停再恢復現實時間。
    """
    self.pause_exploration()
    self.accumulated_seconds += seconds
    self.resume_exploration()
```

---

## 戰鬥輪次與時鐘

### 關鍵規則

**1 輪 = 6 秒 = 所有戰鬥者都行動完**

`add_combat_round()` 的呼叫時機是 `round_number` 遞增時，不是每個角色結束回合時。

```python
# bone_engine/combat.py advance_turn()
# 當 round_number 遞增時：
game_clock.add_combat_round()
```

### 戰鬥中時鐘狀態

```
進入戰鬥 → game_clock.pause_exploration()   ← 現實時間停止
每輪結束 → game_clock.add_combat_round()    ← +6 秒
離開戰鬥 → game_clock.start_exploration()   ← 現實時間重新計時
```

---

## 效果到期系統

### 棄用：remaining_rounds 倒數

```python
# 舊設計（棄用）
remaining_rounds: int | None  # 每輪 -1，None = 永久
```

### 採用：expires_at_second 絕對到期

```python
# 新設計
expires_at_second: int | None  # None = 永久
```

### 效果建立

施放法術或施加條件時：

```python
duration_seconds = duration_rounds * 6  # e.g., 10 分鐘 = 600 輪 = 600 秒

# 若在戰鬥前施放，無條件進位到完整的輪數
# （實際上對秒數沒有影響，進位是顯示用的）
expires_at = game_clock.total_seconds + duration_seconds
```

### 到期判定

```python
def is_expired(effect_expires_at: int | None, clock: GameClock) -> bool:
    if effect_expires_at is None:
        return False
    return clock.total_seconds >= effect_expires_at
```

---

## 顯示格式

### 探索模式（人類可讀）

```python
def format_seconds_human(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} 秒"
    elif seconds < 3600:
        return f"{seconds // 60} 分鐘"
    else:
        return f"{seconds / 3600:.1f} 小時"
```

### 戰鬥模式（換算回合，無條件進位）

```python
import math

def format_seconds_rounds(remaining_seconds: int) -> str:
    """剩餘秒數換算為回合數（ceil）。
    戰鬥前施放的法術也向上取整，確保不會少算。
    """
    rounds = math.ceil(remaining_seconds / 6)
    return f"{rounds} 輪"
```

### 遊戲世界時間

```python
def format_game_time(total_seconds: int) -> str:
    """顯示遊戲世界的時間（Day N, HH:MM）。"""
    days = total_seconds // 86400 + 1
    remaining = total_seconds % 86400
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    return f"第 {days} 天 {hours:02d}:{minutes:02d}"
```

---

## 預設耗時事件常數

```python
# bone_engine/time_costs.py
class TimeCost:
    """顯式耗時事件的秒數常數。"""

    # 戰鬥
    COMBAT_ROUND = 6            # 一回合（所有人行動完）

    # 探索行動
    LOCKPICK = 60               # 開鎖（1 分鐘）
    FORCE_DOOR = 6              # 撞門（1 輪）
    SEARCH_ROOM_DUNGEON = 600   # 搜索房間，地城（10 分鐘）
    SEARCH_ROOM_TOWN = 3600     # 搜索房間，城鎮（1 小時）

    # 休息
    SHORT_REST = 3600           # 短休（1 小時）
    LONG_REST = 28800           # 長休（8 小時）

    # 儀式法術（施法時間 + 10 分鐘）
    RITUAL_BASE = 600           # 儀式附加時間（10 分鐘）
```

---

## 影響範圍總覽

### 新增

| 檔案 | 內容 |
|------|------|
| `models/time.py` | `GameClock` 資料模型 |
| `bone_engine/time_costs.py` | 耗時事件常數 |

### 修改

| 檔案 | 變更 |
|------|------|
| `models/exploration.py` | `elapsed_minutes: int` → `game_clock: GameClock` |
| `models/map.py` | `SurfaceEffect.remaining_rounds` → `expires_at_second: int \| None` |
| `models/creature.py` | `ActiveCondition.remaining_rounds` → `expires_at_second: int \| None` |
| `models/__init__.py` | 匯出 `GameClock` |
| `bone_engine/combat.py` | `advance_turn()` 於輪數遞增時呼叫 `game_clock.add_combat_round()` |
| `bone_engine/conditions.py` | `tick_conditions_end_of_turn()` 改為比對 `expires_at_second` |
| `bone_engine/exploration.py` | 所有 `elapsed_minutes +=` 改為 `game_clock.add_event()` |
| `tui/app.py` (CombatTUI) | 進入/離開戰鬥時呼叫 `pause/start_exploration()` |
| `tui/exploration/app.py` | 啟動時呼叫 `game_clock.start_exploration()` |

---

## 與空間探索的整合

詳見 `spatial-exploration-design.md`。

`GameClock` 作為 `ExplorationState` 的一部分，在探索與戰鬥之間傳遞，保持時間連貫。

```
ExplorationState
  ├── game_clock: GameClock   ← 取代 elapsed_minutes
  ├── spatial_map: MapState | None
  └── ...

CombatTUI 接收 game_clock 引用
  → 戰鬥結束後原樣歸還 ExplorationState
```
