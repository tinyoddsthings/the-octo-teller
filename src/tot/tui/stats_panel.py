"""StatsPanel Widget — 先攻序 + 角色狀態卡。

顯示當前回合先攻順序、HP 血條、AC、狀態異常、行動經濟。
被 app.py 的 _refresh_status() 呼叫 update_state() 驅動更新。
"""

from __future__ import annotations

from uuid import UUID

from textual.widgets import Static

from tot.models import Character, Combatant, CombatState, Monster
from tot.tui.combat_bridge import combatant_marker, display_name


class StatsPanel(Static):
    """先攻序 + 角色狀態面板。"""

    def update_state(
        self,
        combat_state: CombatState | None,
        combatant_map: dict[UUID, Combatant],
    ) -> None:
        """根據戰鬥狀態重新渲染面板內容。"""
        if not combat_state:
            self.update("")
            return

        round_num = combat_state.round_number
        lines: list[str] = [f"[bold cyan]【先攻順序】第 {round_num} 輪[/]\n"]

        for idx, entry in enumerate(combat_state.initiative_order):
            combatant = combatant_map.get(entry.combatant_id)
            if not combatant:
                continue

            line = self._format_entry(idx, entry, combatant, combat_state)
            lines.append(line)

        self.update("\n".join(lines))

    @staticmethod
    def _format_entry(
        idx: int,
        entry,
        combatant: Character | Monster,
        combat_state: CombatState,
    ) -> str:
        """格式化單一先攻條目。"""
        name = display_name(combatant)
        marker_char = combatant_marker(combatant)

        # HP 血條
        hp_cur = combatant.hp_current
        hp_max = combatant.hp_max
        ac = combatant.ac

        ratio = hp_cur / hp_max if hp_max > 0 else 0
        bar_len = 10
        filled = int(ratio * bar_len)
        if ratio > 0.5:
            color = "green"
        elif ratio > 0.25:
            color = "yellow"
        else:
            color = "red"
        bar = f"[{color}]{'█' * filled}{'░' * (bar_len - filled)}[/]"

        # 狀態標記
        turn_marker = "[bold white]▶[/] " if idx == combat_state.current_turn_index else "  "
        alive_mark = "" if combatant.is_alive else " [red]✕[/]"

        ai_mark = ""
        if isinstance(combatant, Character) and combatant.is_ai_controlled:
            ai_mark = "  [dim]\\[AI][/]"

        conds = ", ".join(c.condition.value for c in combatant.conditions)
        cond_str = f" [{conds}]" if conds else ""

        # 行動經濟（僅當前角色）
        econ_str = ""
        if idx == combat_state.current_turn_index and combatant.is_alive:
            ts = combat_state.turn_state
            act_icon = "[dim]⚔[/]" if ts.action_used else "⚔"
            bonus_icon = "[dim]+[/]" if ts.bonus_action_used else "+"
            mv_remaining = ts.movement_remaining
            econ_str = f"  {act_icon} {bonus_icon} {mv_remaining:.0f}m"

        return (
            f"{turn_marker}{marker_char} {name:<8s} "
            f"HP {hp_cur:>2d}/{hp_max:>2d} {bar} AC {ac}"
            f"{cond_str}{ai_mark}{alive_mark}{econ_str}"
        )
