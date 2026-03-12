"""選單狀態機 + 指令解析。

管理 MenuPhase 狀態和選單顯示邏輯。
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from tot.gremlins.bone_engine.spatial import distance, get_actor_position
from tot.gremlins.bone_engine.spells import get_spell_by_name
from tot.models import (
    Character,
    Combatant,
    CombatState,
    MapState,
    Monster,
    Position,
    Spell,
)
from tot.tui.combat_bridge import (
    find_target,
    format_conditions,
    format_initiative,
    format_spells,
    format_status,
    get_actor,
    show_help,
)

if TYPE_CHECKING:
    from tot.tui.log_manager import LogManager


class MenuPhase(StrEnum):
    """選單階段。"""

    ACTION = "action"
    TARGET = "target"
    SPELL = "spell"
    SPELL_TARGET = "spell_target"
    MOVE_INPUT = "move_input"
    CONFIRM_MOVE_ATTACK = "confirm_move_attack"
    LOCKED = "locked"


class InputHandler:
    """處理玩家輸入的選單狀態機。"""

    def __init__(self) -> None:
        self.phase: MenuPhase = MenuPhase.LOCKED
        self.menu_options: list = []
        self.pending_spell: Spell | None = None
        self.pending_move_pos: Position | None = None
        self.pending_auto_target: Character | Monster | None = None
        self.pending_auto_type: str = ""  # "weapon" | "spell"

    def set_confirm_state(
        self,
        pos: Position,
        target: Character | Monster,
        auto_type: str,
        spell: Spell | None,
    ) -> None:
        """設定自動移動確認狀態。"""
        self.pending_move_pos = pos
        self.pending_auto_target = target
        self.pending_auto_type = auto_type
        if spell is not None:
            self.pending_spell = spell
        self.phase = MenuPhase.CONFIRM_MOVE_ATTACK

    def clear_pending(self) -> None:
        """清除自動移動待確認狀態。"""
        self.pending_move_pos = None
        self.pending_auto_target = None
        self.pending_auto_type = ""

    def clear_pending_spell(self) -> None:
        """清除待施放法術。"""
        self.pending_spell = None

    def set_pending_spell(self, spell: Spell) -> None:
        """設定待施放法術。"""
        self.pending_spell = spell

    # ----- 選單顯示 -----

    def show_action_choices(
        self,
        current: Character,
        combat_state: CombatState,
        log: LogManager,
    ) -> None:
        """印出動作選單到 log。"""
        action_used = bool(combat_state.turn_state.action_used)
        options: list[tuple[str, str]] = []

        remaining = combat_state.turn_state.movement_remaining
        if remaining > 0:
            options.append(("move", f"移動（剩餘 {remaining:.1f}m）"))

        if not action_used:
            options.append(("attack", "攻擊（武器）"))
            if current.spells_prepared or current.spells_known:
                options.append(("cast", "施放法術"))
            options.append(("dodge", "閃避"))
            options.append(("disengage", "撤離（安全離開觸及範圍）"))
        options.append(("status", "查看狀態"))
        options.append(("end", "結束回合"))

        self.menu_options = options
        self.phase = MenuPhase.ACTION

        log.log("\n[bold white]可用動作：[/]")
        for i, (_, label) in enumerate(options, 1):
            log.log(f"  [cyan]{i}.[/] {label}")

    def show_target_choices(
        self,
        current: Character | Monster,
        map_state: MapState | None,
        monsters: list[Monster],
        log: LogManager,
    ) -> None:
        """印出攻擊目標選單到 log。"""
        attacker_pos = None
        if current and map_state:
            attacker_pos = get_actor_position(current.id, map_state)

        alive = [(m.label or m.name) for m in monsters if m.is_alive]
        self.menu_options = alive
        self.phase = MenuPhase.TARGET

        log.log("\n[bold white]選擇目標：[/]")
        for i, name in enumerate(alive, 1):
            dist_str = ""
            emoji = ""
            if map_state:
                m = [m for m in monsters if m.is_alive and (m.label or m.name) == name]
                if m:
                    actor = get_actor(m[0].id, map_state)
                    if actor:
                        emoji = actor.symbol + " "
                    if attacker_pos:
                        tgt_pos = get_actor_position(m[0].id, map_state)
                        if tgt_pos:
                            dist = distance(attacker_pos, tgt_pos)
                            dist_str = f" ({dist:.1f}m)"
            log.log(f"  [cyan]{i}.[/] {emoji}{name}{dist_str}")
        log.log("  [dim]0. ← 返回[/]")

    def show_spell_choices(
        self,
        char: Character,
        log: LogManager,
    ) -> None:
        """印出法術選單到 log。"""
        spell_names = list(dict.fromkeys(char.spells_prepared + char.spells_known))
        spells: list[Spell] = []
        for name in spell_names:
            spell = get_spell_by_name(name)
            if spell:
                spells.append(spell)

        if not spells:
            log.log("[yellow]沒有可用法術。[/]")
            return

        self.menu_options = spells
        self.phase = MenuPhase.SPELL

        log.log("\n[bold white]選擇法術：[/]")
        for i, spell in enumerate(spells, 1):
            if spell.level == 0:
                level_str = "戲法"
                slot_str = ""
            else:
                level_str = f"{spell.level} 環"
                remaining = char.spell_slots.current_slots.get(spell.level, 0)
                slot_str = f"  [dim][剩餘: {remaining} 個 {spell.level} 環][/]"
            desc = spell.description[:30] if spell.description else ""
            log.log(f"  [cyan]{i}.[/] {spell.name} ({level_str}) — {desc}{slot_str}")
        log.log("  [dim]0. ← 返回[/]")

    def show_spell_target_choices(
        self,
        map_state: MapState | None,
        characters: list[Character],
        monsters: list[Monster],
        log: LogManager,
        current: Character | Monster | None = None,
    ) -> None:
        """印出法術目標選單到 log。"""
        spell = self.pending_spell
        if not spell:
            return

        attacker_pos = None
        if current and map_state:
            attacker_pos = get_actor_position(current.id, map_state)

        if spell.effect_type.value == "healing":
            targets = [(c.name, c) for c in characters if c.is_alive]
        else:
            targets = [(m.label or m.name, m) for m in monsters if m.is_alive]

        self.menu_options = targets
        self.phase = MenuPhase.SPELL_TARGET

        log.log("\n[bold white]選擇目標：[/]")
        for i, (name, tgt) in enumerate(targets, 1):
            dist_str = ""
            emoji = ""
            actor = get_actor(tgt.id, map_state) if map_state else None
            if actor:
                emoji = actor.symbol + " "
            if attacker_pos and map_state:
                tgt_pos = get_actor_position(tgt.id, map_state)
                if tgt_pos:
                    dist = distance(attacker_pos, tgt_pos)
                    dist_str = f" ({dist:.1f}m)"
            log.log(f"  [cyan]{i}.[/] {emoji}{name}{dist_str}")
        log.log("  [dim]0. ← 返回[/]")

    # ----- 查詢指令 -----

    def handle_query_command(
        self,
        cmd: str,
        current: Character,
        characters: list[Character],
        monsters: list[Monster],
        combat_state: CombatState | None,
        combatant_map: dict[UUID, Combatant],
        log: LogManager,
        refresh_map_fn,
    ) -> bool:
        """處理查詢指令。回傳 True 表示已處理。"""
        if cmd == "help":
            show_help(log.log)
            return True
        if cmd == "status":
            log.log(format_status(current))
            return True
        if cmd.startswith("status "):
            target_name = cmd[7:].strip()
            target = find_target(target_name, characters, monsters)
            if target:
                log.log(format_status(target))
            else:
                log.log(f"[red]找不到：{target_name}[/]")
            return True
        if cmd == "conditions":
            log.log(format_conditions(characters, monsters))
            return True
        if cmd == "initiative":
            log.log(format_initiative(combat_state, combatant_map))
            return True
        if cmd == "spells":
            if isinstance(current, Character):
                log.log(format_spells(current))
            return True
        if cmd == "map":
            refresh_map_fn()
            log.log("[dim]地圖已重新渲染。[/]")
            return True
        return False
