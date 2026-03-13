"""探索隊伍狀態面板。

顯示隊員 HP 血條 + AC + 法術欄位 + 經過時間。
"""

from __future__ import annotations

from textual.widgets import Static

from tot.models.creature import Character
from tot.models.time import GameClock


class ExploreStatusWidget(Static):
    """隊伍狀態面板。"""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.characters: list[Character] = []
        self.game_clock: GameClock = GameClock()

    def update_status(
        self,
        characters: list[Character],
        game_clock: GameClock,
    ) -> None:
        """更新面板內容。"""
        self.characters = characters
        self.game_clock = game_clock
        self.refresh()

    def render(self) -> str:
        if not self.characters:
            return "[dim]等待隊伍載入...[/]"

        lines: list[str] = []
        clock = self.game_clock
        lines.append(f"[bold white]⏱ {clock.format_game_time()} ({clock.format_elapsed()})[/]")
        lines.append("")

        for char in self.characters:
            # HP 血條
            hp_ratio = char.hp_current / char.hp_max if char.hp_max > 0 else 0
            bar_len = 15
            filled = int(hp_ratio * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)

            if hp_ratio > 0.5:
                bar_color = "green"
            elif hp_ratio > 0.25:
                bar_color = "yellow"
            else:
                bar_color = "red"

            hp_str = f"{char.hp_current}/{char.hp_max}"

            # 法術欄位摘要
            slot_str = ""
            if char.spell_slots.max_slots:
                slot_parts = []
                for lvl in sorted(char.spell_slots.max_slots):
                    cur = char.spell_slots.current_slots.get(lvl, 0)
                    mx = char.spell_slots.max_slots[lvl]
                    slot_parts.append(f"{lvl}環:{cur}/{mx}")
                slot_str = f"  [dim]{'  '.join(slot_parts)}[/]"

            # Hit Dice
            hd_str = f"  [dim]HD:{char.hit_dice_remaining}/{char.hit_dice_total}[/]"

            lines.append(f"  [bold]{char.name}[/] ({char.char_class} Lv{char.level})  AC {char.ac}")
            lines.append(f"    [{bar_color}]{bar}[/] {hp_str}{hd_str}{slot_str}")

        return "\n".join(lines)
