"""探索 Log 管理——面板寫入 + 檔案記錄。

仿照 log_manager.py 的 LogManager，專為探索模式設計。
記錄移動軌跡、事件、地圖快照到 logs/exploration_*.log。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from textual.widgets import RichLog


class ExploreLogManager:
    """管理探索模式 log 面板和檔案紀錄。"""

    def __init__(self, log_widget: RichLog) -> None:
        self._widget = log_widget
        self._log_file = self._init_log_file()
        self._move_buffer: list[str] = []

    @staticmethod
    def _init_log_file() -> Path:
        """建立 logs/ 目錄並開啟新的探索 log 檔案。"""
        log_dir = Path(__file__).resolve().parents[4] / "logs"
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = log_dir / f"exploration_{ts}.log"
        path.write_text(f"=== T.O.T. 探索紀錄 {ts} ===\n\n", encoding="utf-8")
        return path

    @staticmethod
    def _strip_markup(text: str) -> str:
        """移除 Rich markup tags，保留純文字。"""
        return re.sub(r"\[/?[^\]]*\]", "", text)

    def log(self, msg: str) -> None:
        """寫入 log 面板 + log 檔案。"""
        self._widget.write(msg)
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(self._strip_markup(msg) + "\n")

    def write(self, msg: str) -> None:
        """兼容 RichLog.write() 的介面，讓 handler duck-type 使用。"""
        self.log(msg)

    def log_raw(self, msg: str) -> None:
        """只寫入 log 檔案（不顯示在面板上）。"""
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def log_player_input(self, cmd: str) -> None:
        """記錄玩家輸入到 log 檔案。"""
        self._flush_moves()
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(f"> {cmd}\n")

    def log_movement(self, dx: float, dy: float, x: float, y: float) -> None:
        """批次記錄 WASD 移動（累積後一次寫入）。"""
        direction = ""
        if dy > 0:
            direction = "N"
        elif dy < 0:
            direction = "S"
        if dx > 0:
            direction += "E"
        elif dx < 0:
            direction += "W"
        self._move_buffer.append(f"{direction}→({x:.1f},{y:.1f})")
        # 每 20 步自動 flush
        if len(self._move_buffer) >= 20:
            self._flush_moves()

    def _flush_moves(self) -> None:
        """將累積的移動紀錄寫入檔案。"""
        if not self._move_buffer:
            return
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write("[移動] " + " ".join(self._move_buffer) + "\n")
        self._move_buffer.clear()

    def log_map_snapshot(self, map_lines: str) -> None:
        """寫入地圖快照到 log 檔案。"""
        self._flush_moves()
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write("\n【探索地圖快照】\n")
            f.write(map_lines + "\n")

    def flush(self) -> None:
        """強制寫入所有緩衝的紀錄。"""
        self._flush_moves()
