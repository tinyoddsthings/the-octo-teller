"""Log 面板寫入 + 檔案記錄。

封裝 RichLog widget 引用和戰鬥 log 檔案寫入。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import UUID

from textual.widgets import RichLog

from tot.models import Character, Combatant, CombatState, MapState, Monster
from tot.tui.canvas import render_braille_map
from tot.tui.combat_bridge import display_name


class LogManager:
    """管理 TUI log 面板和戰鬥紀錄檔案。"""

    def __init__(self, log_widget: RichLog) -> None:
        self._widget = log_widget
        self._log_file = self._init_log_file()
        self._last_snapshot_round: int = 0

    @staticmethod
    def _init_log_file() -> Path:
        """建立 logs/ 目錄並開啟新的戰鬥 log 檔案。"""
        log_dir = Path(__file__).resolve().parents[3] / "logs"
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = log_dir / f"combat_{ts}.log"
        path.write_text(f"=== T.O.T. 戰鬥紀錄 {ts} ===\n\n", encoding="utf-8")
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

    def log_raw(self, msg: str) -> None:
        """只寫入 log 檔案（不顯示在面板上）。"""
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    def log_player_input(self, cmd: str) -> None:
        """記錄玩家輸入到 log 檔案。"""
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(f"> {cmd}\n")

    def log_initiative(
        self,
        combat_state: CombatState,
        combatant_map: dict[UUID, Combatant],
    ) -> None:
        """記錄先攻擲骰結果。"""
        self.log("[dim]先攻擲骰結果：[/]")
        for entry in combat_state.initiative_order:
            combatant = combatant_map.get(entry.combatant_id)
            if combatant:
                self.log(f"  {display_name(combatant)}: {entry.initiative}")

    def log_round_snapshot(
        self,
        combat_state: CombatState,
        map_state: MapState,
        characters: list[Character],
        monsters: list[Monster],
        combatant_map: dict[UUID, Combatant],
    ) -> None:
        """每輪開始時記錄地圖快照 + 狀態面板到 log 檔案。

        同一輪只記錄一次。
        """
        rnd = combat_state.round_number
        if rnd <= self._last_snapshot_round:
            return
        self._last_snapshot_round = rnd

        self._log_map_snapshot(map_state, combatant_map)
        self._log_status_snapshot(map_state, characters, monsters, combatant_map)

    def _log_map_snapshot(
        self,
        map_state: MapState,
        combatant_map: dict[UUID, Combatant],
    ) -> None:
        """用 drawille 產生 braille 地圖，寫入 log 檔。"""
        rendered = render_braille_map(map_state, combatant_map, w=40, h=12)
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write("\n【地圖快照】\n")
            f.write(rendered + "\n")

    def _log_status_snapshot(
        self,
        map_state: MapState,
        characters: list[Character],
        monsters: list[Monster],
        combatant_map: dict[UUID, Combatant],
    ) -> None:
        """記錄所有角色的 HP、AC、位置、狀態效果到 log 檔。"""
        lines = ["\n【狀態面板】"]
        all_combatants: list[Character | Monster] = [*characters, *monsters]
        for combatant in all_combatants:
            name = display_name(combatant)
            hp = f"HP: {combatant.hp_current}/{combatant.hp_max}"
            ac = f"AC: {combatant.ac}"
            pos_str = ""
            from tot.tui.combat_bridge import get_actor

            actor = get_actor(combatant.id, map_state)
            if actor:
                pos_str = f"  位置: ({actor.x:.1f},{actor.y:.1f})"
            conds = [c.condition.value for c in combatant.conditions]
            cond_str = f"  [{', '.join(conds)}]" if conds else ""
            alive_str = "  [倒下]" if not combatant.is_alive else ""
            lines.append(f"  {name:<10s} {hp}  {ac}{pos_str}{cond_str}{alive_str}")
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
