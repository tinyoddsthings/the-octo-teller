"""T.O.T. 統一遊戲時鐘。

三種時間模式統一為絕對秒數：
- 探索模式：現實時間 1:1（玩多久過多久）
- 戰鬥模式：+6 秒/輪（所有人都動完才算一輪）
- 效果到期：用絕對秒數比對，不倒數
"""

from __future__ import annotations

import time

from pydantic import BaseModel, PrivateAttr


class GameClock(BaseModel):
    """統一遊戲時鐘——所有時間計算的唯一來源。

    in_game_start_second: 冒險開始的遊戲世界時間（秒），預設 Day 1 08:00。
    accumulated_seconds: 累積的遊戲內經過時間（秒）。
    _explore_real_start: 探索模式啟動時的 monotonic 時間戳（不序列化）。
    """

    in_game_start_second: int = 28800  # Day 1 08:00 = 8 * 3600
    accumulated_seconds: int = 0

    # 執行期狀態，不進 JSON
    _explore_real_start: float | None = PrivateAttr(default=None)

    @property
    def total_seconds(self) -> int:
        """目前的遊戲世界絕對秒數（含即時探索累計）。"""
        base = self.in_game_start_second + self.accumulated_seconds
        if self._explore_real_start is not None:
            elapsed = time.monotonic() - self._explore_real_start
            base += int(elapsed)
        return base

    @property
    def elapsed_seconds(self) -> int:
        """冒險開始後經過的總秒數（不含 in_game_start）。"""
        result = self.accumulated_seconds
        if self._explore_real_start is not None:
            result += int(time.monotonic() - self._explore_real_start)
        return result

    def start_exploration(self) -> None:
        """開始探索模式——啟動即時時鐘。"""
        if self._explore_real_start is None:
            self._flush_realtime()
            self._explore_real_start = time.monotonic()

    def pause_exploration(self) -> None:
        """暫停探索模式——將即時累積寫入 accumulated_seconds。"""
        self._flush_realtime()

    def resume_exploration(self) -> None:
        """恢復探索模式。等同 start_exploration，語意更明確。"""
        self.start_exploration()

    def add_combat_round(self) -> None:
        """戰鬥中推進一輪（+6 秒）。"""
        self.accumulated_seconds += 6

    def add_event(self, seconds: int) -> None:
        """加入一次性事件消耗的時間（開鎖、搜索、休息等）。"""
        self.accumulated_seconds += seconds

    def _flush_realtime(self) -> None:
        """將即時探索累計的秒數寫入 accumulated_seconds 並重置。"""
        if self._explore_real_start is not None:
            elapsed = time.monotonic() - self._explore_real_start
            self.accumulated_seconds += int(elapsed)
            self._explore_real_start = None

    # ── 顯示用工具 ──

    def format_game_time(self) -> str:
        """格式化為遊戲世界時間（Day X HH:MM）。"""
        total = self.total_seconds
        day = total // 86400 + 1
        remainder = total % 86400
        hours = remainder // 3600
        minutes = (remainder % 3600) // 60
        return f"Day {day} {hours:02d}:{minutes:02d}"

    def format_elapsed(self) -> str:
        """格式化冒險經過時間。"""
        return format_seconds_human(self.elapsed_seconds)


def format_seconds_human(seconds: int) -> str:
    """將秒數格式化為人類可讀字串。"""
    if seconds < 60:
        return f"{seconds} 秒"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        if secs == 0:
            return f"{minutes} 分鐘"
        return f"{minutes} 分 {secs} 秒"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        if mins == 0:
            return f"{hours} 小時"
        return f"{hours} 小時 {mins} 分鐘"
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours == 0:
        return f"{days} 天"
    return f"{days} 天 {remaining_hours} 小時"
