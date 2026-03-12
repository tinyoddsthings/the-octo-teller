"""Textual TUI 戰鬥畫面——精簡 orchestrator。

複用 Bone Engine 所有戰鬥函式，零重新實作。
選單採用數字 + 指令混合制，印在 log 面板中。
AI 隊友與怪物使用統一 NPC 排程器。

模組職責：
  - combat_bridge.py  常數、工具函式、格式化
  - log_manager.py    Log 面板 + 檔案記錄
  - actions.py        玩家動作執行
  - npc_ai.py         怪物 AI + AI 隊友
  - input_handler.py  選單狀態機
  - styles.tcss       外部 TCSS 佈局
"""

from __future__ import annotations

from uuid import UUID

from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog

from tot.gremlins.bone_engine.combat import (
    advance_turn,
    take_disengage_action,
    take_dodge_action,
)
from tot.gremlins.bone_engine.conditions import can_take_action, tick_conditions_end_of_turn
from tot.gremlins.bone_engine.spells import can_cast
from tot.models import Character, Combatant, CombatState, Condition, MapState, Monster, Spell
from tot.tui.actions import (
    execute_attack,
    player_attack,
    player_cast,
    player_cast_by_name,
    player_move,
    step_move_to,
)
from tot.tui.canvas import AoeOverlay, BrailleMapCanvas
from tot.tui.combat_bridge import (
    DIRECTION_MAP,
    display_name,
    format_status,
    get_actor,
    is_in_enemy_reach,
    is_npc_turn,
)
from tot.tui.input_handler import InputHandler, MenuPhase
from tot.tui.log_manager import LogManager
from tot.tui.npc_ai import ai_character_turn, monster_turn
from tot.tui.stats_panel import StatsPanel


class CombatTUI(App):
    """戰鬥 TUI 主應用。"""

    CSS_PATH = "styles.tcss"
    TITLE = "T.O.T. 戰鬥系統"

    def __init__(self) -> None:
        super().__init__()
        self.characters: list[Character] = []
        self.monsters: list[Monster] = []
        self.map_state: MapState | None = None
        self.combat_state: CombatState | None = None
        self._combatant_map: dict[UUID, Combatant] = {}
        self._input_locked: bool = False
        self._input_handler = InputHandler()
        # log_manager 在 compose 後初始化
        self._log: LogManager | None = None

    def compose(self) -> ComposeResult:
        yield BrailleMapCanvas(id="map-panel")
        yield StatsPanel("", id="status-panel")
        yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Input(placeholder="> 輸入數字或指令", id="cmd-input")

    async def on_mount(self) -> None:
        """啟動時初始化 demo 場景。"""
        from tot.tui.demo import create_demo_scene

        self._log = LogManager(self.query_one("#log-panel", RichLog))

        chars, mons, ms, cs = create_demo_scene()
        self.characters = chars
        self.monsters = mons
        self.map_state = ms
        self.combat_state = cs

        for c in self.characters:
            self._combatant_map[c.id] = c
        for m in self.monsters:
            self._combatant_map[m.id] = m

        self._log.log("[bold green]⚔️  戰鬥開始！[/]")
        self._log.log_initiative(self.combat_state, self._combatant_map)
        self._refresh_all()
        await self._start_next_turn()

    # ----- 面板渲染 -----

    def _refresh_all(self) -> None:
        self._refresh_map()
        self._refresh_status()

    def _refresh_map(self) -> None:
        if not self.map_state:
            return
        for actor in self.map_state.actors:
            combatant = self._combatant_map.get(actor.combatant_id)
            if combatant:
                actor.is_alive = combatant.is_alive
        canvas = self.query_one("#map-panel", BrailleMapCanvas)
        canvas.combatant_map = dict(self._combatant_map)
        canvas.map_state = self.map_state
        canvas.refresh()

    def _set_aoe_overlay(self, spell: Spell, target: Character | Monster) -> None:
        """依法術 AoE 參數設定地圖覆蓋預覽。"""
        if not spell.aoe.shape or not self.map_state:
            return
        caster = self._current_combatant()
        if not caster:
            return
        caster_actor = get_actor(caster.id, self.map_state)
        target_actor = get_actor(target.id, self.map_state)
        if not caster_actor or not target_actor:
            return

        ft_to_m = 1.5 / 5.0
        overlay = AoeOverlay(
            shape=spell.aoe.shape.value,
            center_x=target_actor.x,
            center_y=target_actor.y,
            caster_x=caster_actor.x,
            caster_y=caster_actor.y,
            radius_m=spell.aoe.radius_ft * ft_to_m,
            length_m=spell.aoe.length_ft * ft_to_m,
            width_m=(spell.aoe.width_ft or 5) * ft_to_m,
        )
        self.query_one("#map-panel", BrailleMapCanvas).aoe_overlay = overlay

    def _clear_aoe_overlay(self) -> None:
        """清除 AoE 覆蓋預覽。"""
        self.query_one("#map-panel", BrailleMapCanvas).aoe_overlay = None

    def _refresh_status(self) -> None:
        self.query_one("#status-panel", StatsPanel).update_state(
            self.combat_state, self._combatant_map, self.map_state
        )

    # ----- 指令處理 -----

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        event.input.value = ""

        if not cmd:
            return

        self._log.log_player_input(cmd)

        if self._input_locked:
            self._log.log("[yellow]NPC 回合進行中，請等待...[/]")
            return

        if cmd.lower() == "quit":
            self.exit()
            return

        if not self.combat_state or not self.combat_state.is_active:
            self._log.log("[yellow]戰鬥已結束。輸入 quit 離開。[/]")
            return

        current = self._current_combatant()
        if not current:
            return

        if isinstance(current, Monster):
            self._log.log("[yellow]現在是怪物回合，請等待...[/]")
            return

        if isinstance(current, Character) and current.is_ai_controlled:
            self._log.log("[yellow]現在是 AI 隊友回合，請等待...[/]")
            return

        cmd_lower = cmd.lower()
        ih = self._input_handler

        # 1. 全域查詢指令
        if ih.handle_query_command(
            cmd_lower,
            current,
            self.characters,
            self.monsters,
            self.combat_state,
            self._combatant_map,
            self._log,
            self._refresh_map,
        ):
            return

        # 2. confirm_move_attack phase
        if ih.phase == MenuPhase.CONFIRM_MOVE_ATTACK:
            await self._handle_confirm_move_attack(cmd_lower, current)
            return

        # 3. move_input phase
        if ih.phase == MenuPhase.MOVE_INPUT:
            if cmd_lower in DIRECTION_MAP:
                dgx, dgy = DIRECTION_MAP[cmd_lower]
                actor = get_actor(current.id, self.map_state)
                if actor:
                    await self._do_player_move(current, actor.x + dgx * 1.5, actor.y + dgy * 1.5)
                return
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    mx, my = float(parts[0]), float(parts[1])
                    await self._do_player_move(current, mx, my)
                    return
                except ValueError:
                    pass
            if cmd == "0":
                ih.show_action_choices(current, self.combat_state, self._log)
                return
            self._log.log("[red]請用：x.x y.y（公尺座標），方向（n/s/e/w），或 0 返回。[/]")
            return

        # 4. 快捷動作指令
        if await self._handle_action_command(cmd_lower, current):
            return

        # 5. 數字選單輸入
        if cmd.isdigit() or (cmd == "0"):
            await self._handle_menu_input(int(cmd), current)
            return

        self._log.log(f"[red]未知指令：{cmd}[/] — 輸入 help 查看可用指令")

    async def _handle_action_command(self, cmd: str, current: Character) -> bool:
        """處理快捷動作指令。"""
        ih = self._input_handler
        if cmd.startswith("attack "):
            target_name = cmd[7:].strip()
            await self._do_player_attack(current, target_name)
            return True
        if cmd.startswith("cast "):
            spell_name = cmd[5:].strip()
            await player_cast_by_name(
                current,
                spell_name,
                self.combat_state,
                self.map_state,
                self._combatant_map,
                self.characters,
                self.monsters,
                self._log,
                self._refresh_all,
                self._after_action,
                self._check_combat_end,
                lambda: ih.show_action_choices(current, self.combat_state, self._log),
                ih.set_confirm_state,
                ih.clear_pending_spell,
                ih.set_pending_spell,
                lambda: ih.show_spell_target_choices(
                    self.map_state,
                    self.characters,
                    self.monsters,
                    self._log,
                    current,
                ),
            )
            return True
        if cmd.startswith("move "):
            arg = cmd[5:].strip()
            if arg.lower() in DIRECTION_MAP:
                dgx, dgy = DIRECTION_MAP[arg.lower()]
                actor = get_actor(current.id, self.map_state)
                if actor:
                    await self._do_player_move(current, actor.x + dgx * 1.5, actor.y + dgy * 1.5)
                return True
            parts = arg.split()
            if len(parts) == 2:
                try:
                    mx, my = float(parts[0]), float(parts[1])
                    await self._do_player_move(current, mx, my)
                except ValueError:
                    self._log.log(
                        "[red]格式錯誤，請用：move x.x y.y 或 move 方向（n/s/e/w/ne/nw/se/sw）[/]"
                    )
            else:
                self._log.log(
                    "[red]格式錯誤，請用：move x.x y.y 或 move 方向（n/s/e/w/ne/nw/se/sw）[/]"
                )
            return True
        if cmd == "dodge":
            await self._player_dodge(current)
            return True
        if cmd in ("disengage", "撤離"):
            await self._player_disengage(current)
            return True
        if cmd == "end":
            await self._end_current_turn()
            return True
        return False

    async def _handle_menu_input(self, num: int, current: Character) -> None:
        """根據 phase 處理數字輸入。"""
        ih = self._input_handler
        if ih.phase == MenuPhase.ACTION:
            await self._handle_action_menu(num, current)
        elif ih.phase == MenuPhase.TARGET:
            await self._handle_target_menu(num, current)
        elif ih.phase == MenuPhase.SPELL:
            await self._handle_spell_menu(num, current)
        elif ih.phase == MenuPhase.SPELL_TARGET:
            await self._handle_spell_target_menu(num, current)
        elif ih.phase == MenuPhase.MOVE_INPUT:
            if num == 0:
                ih.show_action_choices(current, self.combat_state, self._log)
            else:
                self._log.log("[yellow]請輸入座標 x y（例如 5 3），或 0 返回。[/]")
        else:
            self._log.log("[yellow]目前無法使用選單。[/]")

    async def _handle_action_menu(self, num: int, current: Character) -> None:
        ih = self._input_handler
        if num < 1 or num > len(ih.menu_options):
            self._log.log(f"[red]無效選項：{num}[/]")
            return
        key, _ = ih.menu_options[num - 1]
        if key == "move":
            remaining = self.combat_state.turn_state.movement_remaining if self.combat_state else 0
            self._log.log(f"\n[bold white]移動（剩餘 {remaining:.1f}m）[/]")
            if not current.has_condition(Condition.DISENGAGING) and is_in_enemy_reach(
                current,
                self.map_state,
                self._combatant_map,
            ):
                self._log.log("  [bold yellow]⚠️  你在敵方觸及範圍內！離開將觸發藉機攻擊。[/]")
                self._log.log("  [yellow]提示：使用「撤離」動作可安全移動。[/]")
            self._log.log("  輸入目標格子座標 x y（例如 5 3）或方向（n/s/e/w/ne/nw/se/sw）")
            self._log.log("  [dim]0 — 返回[/]")
            ih.phase = MenuPhase.MOVE_INPUT
        elif key == "attack":
            ih.show_target_choices(current, self.map_state, self.monsters, self._log)
        elif key == "cast":
            ih.show_spell_choices(current, self._log)
        elif key == "dodge":
            await self._player_dodge(current)
        elif key == "disengage":
            await self._player_disengage(current)
        elif key == "status":
            self._log.log(format_status(current))
        elif key == "end":
            await self._end_current_turn()

    async def _handle_target_menu(self, num: int, current: Character) -> None:
        ih = self._input_handler
        if num == 0:
            ih.show_action_choices(current, self.combat_state, self._log)
            return
        if num < 1 or num > len(ih.menu_options):
            self._log.log(f"[red]無效選項：{num}[/]")
            return
        target_name = ih.menu_options[num - 1]
        await self._do_player_attack(current, target_name)

    async def _handle_spell_menu(self, num: int, current: Character) -> None:
        ih = self._input_handler
        if num == 0:
            ih.show_action_choices(current, self.combat_state, self._log)
            return
        if num < 1 or num > len(ih.menu_options):
            self._log.log(f"[red]無效選項：{num}[/]")
            return
        spell: Spell = ih.menu_options[num - 1]

        error = can_cast(current, spell, slot_level=spell.level if spell.level > 0 else None)
        if error is not None:
            self._log.log(f"[red]無法施放：{error.reason}[/]")
            return

        ih.pending_spell = spell
        if spell.effect_type.value in ("damage", "healing", "condition"):
            ih.show_spell_target_choices(
                self.map_state,
                self.characters,
                self.monsters,
                self._log,
                current,
            )
        else:
            await self._do_player_cast(current, spell, target=None)

    async def _handle_spell_target_menu(self, num: int, current: Character) -> None:
        ih = self._input_handler
        if num == 0:
            ih.pending_spell = None
            self._clear_aoe_overlay()
            ih.show_spell_choices(current, self._log)
            return
        if num < 1 or num > len(ih.menu_options):
            self._log.log(f"[red]無效選項：{num}[/]")
            return
        _, target = ih.menu_options[num - 1]
        spell = ih.pending_spell
        if not spell:
            return
        # AoE 預覽
        if spell.aoe.shape:
            self._set_aoe_overlay(spell, target)
        await self._do_player_cast(current, spell, target=target)

    async def _handle_confirm_move_attack(
        self,
        cmd: str,
        current: Character,
    ) -> None:
        ih = self._input_handler
        if cmd in ("y", "yes", "是"):
            pos = ih.pending_move_pos
            target = ih.pending_auto_target
            auto_type = ih.pending_auto_type
            spell = ih.pending_spell
            ih.clear_pending()

            if pos and self.combat_state and self.map_state:
                actor = get_actor(current.id, self.map_state)
                if actor:
                    killed = step_move_to(
                        current,
                        actor,
                        pos.x,
                        pos.y,
                        self.combat_state,
                        self.map_state,
                        self._combatant_map,
                        self.characters,
                        self.monsters,
                        self._log,
                    )
                    self._refresh_all()
                    if killed:
                        await self._check_combat_end()
                        return

                    if auto_type == "weapon" and target and target.is_alive:
                        execute_attack(current, target, self.combat_state, self._log)
                        self._refresh_all()
                        if await self._check_combat_end():
                            return
                    elif auto_type == "spell" and spell and target:
                        await self._do_player_cast(current, spell, target)
                        return

            await self._after_action()

        elif cmd in ("n", "no", "否"):
            ih.clear_pending()
            ih.show_action_choices(current, self.combat_state, self._log)
        else:
            self._log.log("[yellow]請輸入 y 或 n[/]")

    # ----- 動作包裝（傳遞 callback） -----

    async def _do_player_move(self, character: Character, x: float, y: float) -> None:
        ih = self._input_handler
        await player_move(
            character,
            x,
            y,
            self.combat_state,
            self.map_state,
            self._combatant_map,
            self.characters,
            self.monsters,
            self._log,
            self._refresh_all,
            self._after_action,
            self._check_combat_end,
            lambda: ih.show_action_choices(character, self.combat_state, self._log),
        )

    async def _do_player_attack(self, attacker: Character, target_name: str) -> None:
        ih = self._input_handler
        await player_attack(
            attacker,
            target_name,
            self.combat_state,
            self.map_state,
            self._combatant_map,
            self.characters,
            self.monsters,
            self._log,
            self._refresh_all,
            self._after_action,
            self._check_combat_end,
            lambda: ih.show_action_choices(attacker, self.combat_state, self._log),
            ih.set_confirm_state,
        )

    async def _do_player_cast(
        self,
        caster: Character,
        spell: Spell,
        target: Character | Monster | None,
    ) -> None:
        ih = self._input_handler
        self._clear_aoe_overlay()
        await player_cast(
            caster,
            spell,
            target,
            self.combat_state,
            self.map_state,
            self._combatant_map,
            self.characters,
            self.monsters,
            self._log,
            self._refresh_all,
            self._after_action,
            self._check_combat_end,
            lambda: ih.show_action_choices(caster, self.combat_state, self._log),
            ih.set_confirm_state,
            ih.clear_pending_spell,
        )

    async def _player_dodge(self, current: Character) -> None:
        if self.combat_state and take_dodge_action(current, self.combat_state):
            self._log.log(f"[cyan]🛡 {current.name} 採取閃避動作！（敵方攻擊獲得劣勢）[/]")
            self._refresh_all()
            await self._after_action()
        else:
            self._log.log("[yellow]無法執行閃避。[/]")

    async def _player_disengage(self, current: Character) -> None:
        if self.combat_state and take_disengage_action(current, self.combat_state):
            self._log.log(f"[cyan]🏃 {current.name} 採取撤離動作！（本輪移動不觸發藉機攻擊）[/]")
            self._refresh_all()
            await self._after_action()
        else:
            self._log.log("[yellow]無法執行撤離。[/]")

    # ----- 動作後流程 -----

    async def _after_action(self) -> None:
        if not self.combat_state:
            return
        ts = self.combat_state.turn_state
        if ts.action_used and ts.movement_remaining <= 0:
            await self._end_current_turn()
        else:
            current = self._current_combatant()
            if isinstance(current, Character):
                self._input_handler.show_action_choices(
                    current,
                    self.combat_state,
                    self._log,
                )

    # ----- 回合管理 -----

    async def _start_next_turn(self) -> None:
        if await self._check_combat_end():
            return
        current = self._current_combatant()
        if is_npc_turn(current):
            await self._schedule_npc_turns()
        elif isinstance(current, Character):
            await self._prompt_current_turn()

    async def _end_current_turn(self) -> None:
        if not self.combat_state:
            return
        self._input_handler.phase = MenuPhase.LOCKED

        current = self._current_combatant()
        if current:
            expired = tick_conditions_end_of_turn(current)
            for ac in expired:
                self._log.log(f"[dim]{display_name(current)} 的 {ac.condition.value} 效果結束。[/]")

        advance_turn(self.combat_state)
        self._refresh_all()

        await self._start_next_turn()

    async def _schedule_npc_turns(self) -> None:
        self._input_locked = True
        self._input_handler.phase = MenuPhase.LOCKED
        self.query_one("#cmd-input", Input).disabled = True
        self.set_timer(0.5, self._do_one_npc_turn)

    async def _do_one_npc_turn(self) -> None:
        current = self._current_combatant()
        if not is_npc_turn(current):
            self._input_locked = False
            self.query_one("#cmd-input", Input).disabled = False
            await self._start_next_turn()
            return

        if isinstance(current, Monster):
            monster_turn(
                current,
                self.combat_state,
                self.map_state,
                self._combatant_map,
                self.characters,
                self.monsters,
                self._log,
                self._refresh_all,
            )
        elif isinstance(current, Character) and current.is_ai_controlled:
            ai_character_turn(
                current,
                self.combat_state,
                self.map_state,
                self._combatant_map,
                self.characters,
                self.monsters,
                self._log,
                self._refresh_all,
            )

        expired = tick_conditions_end_of_turn(current)
        for ac in expired:
            self._log.log(f"[dim]{display_name(current)} 的 {ac.condition.value} 效果結束。[/]")
        advance_turn(self.combat_state)
        self._refresh_all()

        if await self._check_combat_end():
            self._input_locked = False
            self.query_one("#cmd-input", Input).disabled = False
            return

        self.set_timer(0.8, self._do_one_npc_turn)

    # ----- 玩家回合提示 -----

    async def _prompt_current_turn(self) -> None:
        current = self._current_combatant()
        if not current or not isinstance(current, Character):
            return

        if not self.combat_state:
            return

        if not current.is_alive or not can_take_action(current):
            self._log.log(f"\n[dim]{current.name} 倒下了，無法行動。[/]")
            await self._end_current_turn()
            return

        self.combat_state.turn_state.movement_remaining = float(current.speed)

        self._log.log(
            f"\n[bold white]⚔️  第 {self.combat_state.round_number} 輪 — {current.name} 的回合[/]"
        )
        self._log.log_round_snapshot(
            self.combat_state,
            self.map_state,
            self.characters,
            self.monsters,
            self._combatant_map,
        )

        input_widget = self.query_one("#cmd-input", Input)
        actor = get_actor(current.id, self.map_state)
        emoji = actor.symbol if actor else "🧙"
        input_widget.placeholder = f"{emoji} {current.name} > 輸入數字或指令"
        self._input_handler.show_action_choices(current, self.combat_state, self._log)

    # ----- 戰鬥結束判定 -----

    async def _check_combat_end(self) -> bool:
        if not self.combat_state:
            return True

        all_monsters_dead = all(not m.is_alive for m in self.monsters)
        all_pcs_down = all(c.hp_current <= 0 for c in self.characters)

        if all_monsters_dead:
            self.combat_state.is_active = False
            self._input_handler.phase = MenuPhase.LOCKED
            total_xp = sum(m.xp_reward for m in self.monsters)
            self._log.log("\n[bold green]🎉 勝利！所有敵人被擊敗！[/]")
            self._log.log(f"[green]獲得經驗值：{total_xp} XP[/]")
            self._refresh_all()
            return True

        if all_pcs_down:
            self.combat_state.is_active = False
            self._input_handler.phase = MenuPhase.LOCKED
            self._log.log("\n[bold red]💀 全滅…全體隊員倒下了。[/]")
            self._refresh_all()
            return True

        return False

    # ----- 查找輔助 -----

    def _current_combatant(self) -> Character | Monster | None:
        if not self.combat_state:
            return None
        entry = self.combat_state.initiative_order[self.combat_state.current_turn_index]
        return self._combatant_map.get(entry.combatant_id)
