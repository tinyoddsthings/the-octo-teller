"""Textual TUI 戰鬥畫面——垂直堆疊佈局 + 文字選單系統。

複用 Bone Engine 所有戰鬥函式，零重新實作。
選單採用數字 + 指令混合制，印在 log 面板中。
AI 隊友與怪物使用統一 NPC 排程器。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import UUID

from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog, Static

from tot.gremlins.bone_engine.combat import (
    advance_turn,
    apply_damage,
    check_opportunity_attack,
    resolve_attack,
    roll_damage,
    take_disengage_action,
    take_dodge_action,
    use_action,
    validate_attack_preconditions,
)
from tot.gremlins.bone_engine.conditions import can_take_action, tick_conditions_end_of_turn
from tot.gremlins.bone_engine.spatial import (
    bfs_path_to_range,
    get_actor_position,
    grid_distance,
    is_valid_position,
    move_entity,
    parse_spell_range_meters,
    validate_spell_range,
)
from tot.gremlins.bone_engine.spells import can_cast, cast_spell, get_spell_by_name
from tot.models import (
    Ability,
    Actor,
    Character,
    CombatState,
    Condition,
    DamageType,
    InitiativeEntry,
    MapState,
    Monster,
    MonsterAction,
    Position,
    Spell,
    Weapon,
)
from tot.tui.demo import create_demo_scene
from tot.visuals.map_renderer import MapRenderer

# ---------------------------------------------------------------------------
# 傷害類型中文化
# ---------------------------------------------------------------------------

DAMAGE_TYPE_ZH: dict[str, str] = {
    "Acid": "強酸", "Bludgeoning": "鈍擊", "Cold": "寒冷",
    "Fire": "火焰", "Force": "力場", "Lightning": "閃電",
    "Necrotic": "黯蝕", "Piercing": "穿刺", "Poison": "毒素",
    "Psychic": "心靈", "Radiant": "光輝", "Slashing": "揮砍",
    "Thunder": "雷鳴",
}


def _zh_dmg(dmg_type: DamageType) -> str:
    """傷害類型中文翻譯。"""
    return DAMAGE_TYPE_ZH.get(dmg_type.value, dmg_type.value)


# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------


def _get_attack_bonus(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算攻擊加值。"""
    if isinstance(weapon, MonsterAction):
        return weapon.attack_bonus or 0
    # Character 武器攻擊
    if weapon.is_finesse:
        str_mod = combatant.ability_scores.modifier(Ability.STR)
        dex_mod = combatant.ability_scores.modifier(Ability.DEX)
        ability_mod = max(str_mod, dex_mod)
    elif weapon.is_ranged:
        ability_mod = combatant.ability_scores.modifier(Ability.DEX)
    else:
        ability_mod = combatant.ability_scores.modifier(Ability.STR)
    return ability_mod + combatant.proficiency_bonus


def _get_damage_modifier(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算傷害修正值。"""
    if isinstance(weapon, MonsterAction):
        return combatant.ability_scores.modifier(Ability.DEX)
    if weapon.is_finesse:
        str_mod = combatant.ability_scores.modifier(Ability.STR)
        dex_mod = combatant.ability_scores.modifier(Ability.DEX)
        return max(str_mod, dex_mod)
    if weapon.is_ranged:
        return combatant.ability_scores.modifier(Ability.DEX)
    return combatant.ability_scores.modifier(Ability.STR)


# ---------------------------------------------------------------------------
# TUI App
# ---------------------------------------------------------------------------

CSS = """
Screen {
    layout: vertical;
}
#map-panel {
    height: 40%;
    border: round green;
    padding: 0 1;
}
#status-panel {
    height: 20%;
    border: round cyan;
    padding: 0 1;
}
#log-panel {
    height: 35%;
    border: round yellow;
}
#cmd-input {
    dock: bottom;
    height: 3;
}
"""


class CombatTUI(App):
    """戰鬥 TUI 主應用。"""

    CSS = CSS
    TITLE = "T.O.T. 戰鬥系統"

    def __init__(self) -> None:
        super().__init__()
        self.characters: list[Character] = []
        self.monsters: list[Monster] = []
        self.map_state: MapState | None = None
        self.combat_state: CombatState | None = None
        # 快速查找表：UUID → Character/Monster
        self._combatant_map: dict[UUID, Character | Monster] = {}
        # NPC 回合期間鎖定玩家輸入
        self._input_locked: bool = False
        # 選單階段
        # action | target | spell | spell_target | move_input | confirm_move_attack | locked
        self._menu_phase: str = "locked"
        self._menu_options: list = []  # 當前選單選項（用來對應數字輸入）
        self._pending_spell: Spell | None = None  # 選定待施放的法術
        # 自動移動建議
        self._pending_move_pos: Position | None = None
        self._pending_auto_target: Character | Monster | None = None
        self._pending_auto_type: str = ""  # "weapon" | "spell"
        # 戰鬥 log 檔案
        self._log_file = self._init_log_file()

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

    def _get_actor(self, combatant_id: UUID) -> Actor | None:
        """以 UUID 查詢 Actor。"""
        if not self.map_state:
            return None
        for a in self.map_state.actors:
            if a.combatant_id == combatant_id:
                return a
        return None

    def compose(self) -> ComposeResult:
        yield Static("", id="map-panel")
        yield Static("", id="status-panel")
        yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Input(placeholder="> 輸入數字或指令", id="cmd-input")

    async def on_mount(self) -> None:
        """啟動時初始化 demo 場景。"""
        chars, mons, ms, cs = create_demo_scene()
        self.characters = chars
        self.monsters = mons
        self.map_state = ms
        self.combat_state = cs

        # 建立查找表
        for c in self.characters:
            self._combatant_map[c.id] = c
        for m in self.monsters:
            self._combatant_map[m.id] = m

        self._log("[bold green]⚔️  戰鬥開始！[/]")
        self._log_initiative()
        self._refresh_all()
        await self._start_next_turn()

    # ----- 面板渲染 -----

    def _refresh_all(self) -> None:
        """重新繪製地圖和狀態面板。"""
        self._refresh_map()
        self._refresh_status()

    def _refresh_map(self) -> None:
        if not self.map_state:
            return
        for actor in self.map_state.actors:
            combatant = self._combatant_map.get(actor.combatant_id)
            if combatant:
                actor.is_alive = combatant.is_alive
        rendered = MapRenderer(self.map_state).render_full()
        self.query_one("#map-panel", Static).update(rendered)

    def _refresh_status(self) -> None:
        if not self.combat_state:
            return
        round_num = self.combat_state.round_number
        lines: list[str] = [f"[bold cyan]【先攻順序】第 {round_num} 輪[/]\n"]
        for idx, entry in enumerate(self.combat_state.initiative_order):
            combatant = self._combatant_map.get(entry.combatant_id)
            if not combatant:
                continue
            name = self._display_name(combatant)

            # 取得 Actor emoji
            actor = self._get_actor(entry.combatant_id)
            emoji = actor.symbol if actor else "?"

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

            marker = "[bold white]▶[/] " if idx == self.combat_state.current_turn_index else "  "
            alive_mark = "" if combatant.is_alive else " [red]💀[/]"

            # AI 標記
            ai_mark = ""
            if isinstance(combatant, Character) and combatant.is_ai_controlled:
                ai_mark = "  [dim]\\[AI][/]"

            conds = ", ".join(c.condition.value for c in combatant.conditions)
            cond_str = f" [{conds}]" if conds else ""

            # 當前回合角色顯示動作經濟
            econ_str = ""
            if idx == self.combat_state.current_turn_index and combatant.is_alive:
                ts = self.combat_state.turn_state
                act_icon = "[dim]⚔️[/]" if ts.action_used else "⚔️"
                bonus_icon = "[dim]➕[/]" if ts.bonus_action_used else "➕"
                mv_remaining = ts.movement_remaining
                econ_str = f"  {act_icon} {bonus_icon} 🦶 {mv_remaining:.0f}m"

            # 名稱對齊：用 emoji 前綴
            line = (
                f"{marker}{emoji} {name:<8s} "
                f"HP {hp_cur:>2d}/{hp_max:>2d} {bar} AC {ac}"
                f"{cond_str}{ai_mark}{alive_mark}{econ_str}"
            )
            lines.append(line)

        self.query_one("#status-panel", Static).update("\n".join(lines))

    # ----- 紀錄面板 -----

    def _log(self, msg: str) -> None:
        self.query_one("#log-panel", RichLog).write(msg)
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(self._strip_markup(msg) + "\n")

    def _log_initiative(self) -> None:
        if not self.combat_state:
            return
        self._log("[dim]先攻擲骰結果：[/]")
        for entry in self.combat_state.initiative_order:
            combatant = self._combatant_map.get(entry.combatant_id)
            if combatant:
                self._log(f"  {self._display_name(combatant)}: {entry.initiative}")

    # ----- 選單顯示方法 -----

    def _show_action_choices(self) -> None:
        """印出動作選單到 log。"""
        current = self._current_combatant()
        if not current or not isinstance(current, Character):
            return

        action_used = bool(self.combat_state and self.combat_state.turn_state.action_used)
        options: list[tuple[str, str]] = []  # (key, label)

        # 移動不消耗 Action（D&D 5.5e 規則）
        remaining = self.combat_state.turn_state.movement_remaining if self.combat_state else 0
        if remaining > 0:
            options.append(("move", f"移動（剩餘 {remaining:.1f}m）"))

        if not action_used:
            options.append(("attack", "攻擊（武器）"))
            # 法術選項：角色有 spells_prepared 或 spells_known 時才顯示
            if current.spells_prepared or current.spells_known:
                options.append(("cast", "施放法術"))
            options.append(("dodge", "閃避"))
            options.append(("disengage", "撤離（安全離開觸及範圍）"))
        options.append(("status", "查看狀態"))
        options.append(("end", "結束回合"))

        self._menu_options = options
        self._menu_phase = "action"

        self._log("\n[bold white]可用動作：[/]")
        for i, (_, label) in enumerate(options, 1):
            self._log(f"  [cyan]{i}.[/] {label}")

    def _show_target_choices(self) -> None:
        """印出攻擊目標選單到 log（含距離資訊與 emoji）。"""
        current = self._current_combatant()
        attacker_pos = None
        if current and self.map_state:
            attacker_pos = get_actor_position(current.id, self.map_state)

        alive = [(m.label or m.name) for m in self.monsters if m.is_alive]
        self._menu_options = alive
        self._menu_phase = "target"

        self._log("\n[bold white]選擇目標：[/]")
        for i, name in enumerate(alive, 1):
            dist_str = ""
            emoji = ""
            if self.map_state:
                m = [m for m in self.monsters if m.is_alive and (m.label or m.name) == name]
                if m:
                    actor = self._get_actor(m[0].id)
                    if actor:
                        emoji = actor.symbol + " "
                    if attacker_pos:
                        tgt_pos = get_actor_position(m[0].id, self.map_state)
                        if tgt_pos:
                            gs = self.map_state.manifest.grid_size_m
                            dist = grid_distance(attacker_pos, tgt_pos, gs)
                            dist_str = f" ({dist:.1f}m)"
            self._log(f"  [cyan]{i}.[/] {emoji}{name}{dist_str}")
        self._log("  [dim]0. ← 返回[/]")

    def _show_spell_choices(self, char: Character) -> None:
        """印出法術選單到 log。"""
        # 蒐集已準備的法術（含戲法）
        spell_names = list(dict.fromkeys(char.spells_prepared + char.spells_known))
        spells: list[Spell] = []
        for name in spell_names:
            spell = get_spell_by_name(name)
            if spell:
                spells.append(spell)

        if not spells:
            self._log("[yellow]沒有可用法術。[/]")
            self._show_action_choices()
            return

        self._menu_options = spells
        self._menu_phase = "spell"

        self._log("\n[bold white]選擇法術：[/]")
        for i, spell in enumerate(spells, 1):
            if spell.level == 0:
                level_str = "戲法"
                slot_str = ""
            else:
                level_str = f"{spell.level} 環"
                remaining = char.spell_slots.current_slots.get(spell.level, 0)
                slot_str = f"  [dim][剩餘: {remaining} 個 {spell.level} 環][/]"
            desc = spell.description[:30] if spell.description else ""
            self._log(f"  [cyan]{i}.[/] {spell.name} ({level_str}) — {desc}{slot_str}")
        self._log("  [dim]0. ← 返回[/]")

    def _show_spell_target_choices(self) -> None:
        """印出法術目標選單到 log（含距離資訊與 emoji）。"""
        # 傷害法術 → 怪物；治療法術 → 隊友
        spell = self._pending_spell
        if not spell:
            return

        current = self._current_combatant()
        attacker_pos = None
        if current and self.map_state:
            attacker_pos = get_actor_position(current.id, self.map_state)

        if spell.effect_type.value == "healing":
            targets = [(c.name, c) for c in self.characters if c.is_alive]
        else:
            targets = [(m.label or m.name, m) for m in self.monsters if m.is_alive]

        self._menu_options = targets
        self._menu_phase = "spell_target"

        self._log("\n[bold white]選擇目標：[/]")
        for i, (name, tgt) in enumerate(targets, 1):
            dist_str = ""
            emoji = ""
            actor = self._get_actor(tgt.id)
            if actor:
                emoji = actor.symbol + " "
            if attacker_pos and self.map_state:
                tgt_pos = get_actor_position(tgt.id, self.map_state)
                if tgt_pos:
                    dist = grid_distance(attacker_pos, tgt_pos, self.map_state.manifest.grid_size_m)
                    dist_str = f" ({dist:.1f}m)"
            self._log(f"  [cyan]{i}.[/] {emoji}{name}{dist_str}")
        self._log("  [dim]0. ← 返回[/]")

    # ----- 指令處理 -----

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        event.input.value = ""

        if not cmd:
            return

        # 記錄玩家輸入
        with self._log_file.open("a", encoding="utf-8") as f:
            f.write(f"> {cmd}\n")

        if self._input_locked:
            self._log("[yellow]NPC 回合進行中，請等待...[/]")
            return

        if cmd.lower() == "quit":
            self.exit()
            return

        if not self.combat_state or not self.combat_state.is_active:
            self._log("[yellow]戰鬥已結束。輸入 quit 離開。[/]")
            return

        current = self._current_combatant()
        if not current:
            return

        if isinstance(current, Monster):
            self._log("[yellow]現在是怪物回合，請等待...[/]")
            return

        if isinstance(current, Character) and current.is_ai_controlled:
            self._log("[yellow]現在是 AI 隊友回合，請等待...[/]")
            return

        # 1. 全域查詢指令（不消耗動作，不改變 phase）
        cmd_lower = cmd.lower()
        if await self._handle_query_command(cmd_lower, current):
            return

        # 2. confirm_move_attack phase：自動移動確認
        if self._menu_phase == "confirm_move_attack":
            await self._handle_confirm_move_attack(cmd_lower, current)
            return

        # 3. move_input phase：解析座標 x y 或方向
        if self._menu_phase == "move_input":
            if cmd_lower in self._DIRECTION_MAP:
                dx, dy = self._DIRECTION_MAP[cmd_lower]
                actor = self._get_actor(current.id)
                if actor:
                    await self._player_move(current, actor.x + dx, actor.y + dy)
                return
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    x, y = int(parts[0]), int(parts[1])
                    await self._player_move(current, x, y)
                    return
                except ValueError:
                    pass
            if cmd == "0":
                self._show_action_choices()
                return
            self._log("[red]請用：x y（例如 5 3）或方向（n/s/e/w），或 0 返回。[/]")
            return

        # 4. 快捷動作指令
        if await self._handle_action_command(cmd_lower, current):
            return

        # 5. 數字選單輸入
        if cmd.isdigit() or (cmd == "0"):
            await self._handle_menu_input(int(cmd), current)
            return

        self._log(f"[red]未知指令：{cmd}[/] — 輸入 help 查看可用指令")

    async def _handle_query_command(self, cmd: str, current: Character) -> bool:
        """處理查詢指令。回傳 True 表示已處理。"""
        if cmd == "help":
            self._show_help()
            return True
        if cmd == "status":
            self._log(self._format_status(current))
            return True
        if cmd.startswith("status "):
            target_name = cmd[7:].strip()
            target = self._find_target(target_name)
            if target:
                self._log(self._format_status(target))
            else:
                self._log(f"[red]找不到：{target_name}[/]")
            return True
        if cmd == "conditions":
            self._log(self._format_conditions())
            return True
        if cmd == "initiative":
            self._log(self._format_initiative())
            return True
        if cmd == "spells":
            if isinstance(current, Character):
                self._log(self._format_spells(current))
            return True
        if cmd == "map":
            self._refresh_map()
            self._log("[dim]地圖已重新渲染。[/]")
            return True
        return False

    # 方向 → (dx, dy) 對照表
    _DIRECTION_MAP: dict[str, tuple[int, int]] = {
        "n": (0, 1), "north": (0, 1), "上": (0, 1),
        "s": (0, -1), "south": (0, -1), "下": (0, -1),
        "e": (1, 0), "east": (1, 0), "右": (1, 0),
        "w": (-1, 0), "west": (-1, 0), "左": (-1, 0),
        "ne": (1, 1), "northeast": (1, 1), "右上": (1, 1),
        "nw": (-1, 1), "northwest": (-1, 1), "左上": (-1, 1),
        "se": (1, -1), "southeast": (1, -1), "右下": (1, -1),
        "sw": (-1, -1), "southwest": (-1, -1), "左下": (-1, -1),
    }

    async def _handle_action_command(self, cmd: str, current: Character) -> bool:
        """處理快捷動作指令。回傳 True 表示已處理。"""
        if cmd.startswith("attack "):
            target_name = cmd[7:].strip()
            await self._player_attack(current, target_name)
            return True
        if cmd.startswith("cast "):
            spell_name = cmd[5:].strip()
            await self._player_cast_by_name(current, spell_name)
            return True
        if cmd.startswith("move "):
            arg = cmd[5:].strip()
            # 方向移動：move n / move 上
            if arg.lower() in self._DIRECTION_MAP:
                dx, dy = self._DIRECTION_MAP[arg.lower()]
                actor = self._get_actor(current.id)
                if actor:
                    await self._player_move(current, actor.x + dx, actor.y + dy)
                return True
            # 座標移動：move x y
            parts = arg.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                await self._player_move(current, int(parts[0]), int(parts[1]))
            else:
                self._log("[red]格式錯誤，請用：move x y 或 move 方向（n/s/e/w/ne/nw/se/sw）[/]")
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
        """根據 _menu_phase 處理數字輸入。"""
        if self._menu_phase == "action":
            await self._handle_action_menu(num, current)
        elif self._menu_phase == "target":
            await self._handle_target_menu(num, current)
        elif self._menu_phase == "spell":
            await self._handle_spell_menu(num, current)
        elif self._menu_phase == "spell_target":
            await self._handle_spell_target_menu(num, current)
        elif self._menu_phase == "move_input":
            if num == 0:
                self._show_action_choices()
            else:
                self._log("[yellow]請輸入座標 x y（例如 5 3），或 0 返回。[/]")
        else:
            self._log("[yellow]目前無法使用選單。[/]")

    async def _handle_action_menu(self, num: int, current: Character) -> None:
        """動作選單數字處理。"""
        if num < 1 or num > len(self._menu_options):
            self._log(f"[red]無效選項：{num}[/]")
            return
        key, _ = self._menu_options[num - 1]
        if key == "move":
            remaining = self.combat_state.turn_state.movement_remaining if self.combat_state else 0
            self._log(f"\n[bold white]移動（剩餘 {remaining:.1f}m）[/]")
            # OA 警告：在敵方觸及範圍內且未撤離
            if not current.has_condition(Condition.DISENGAGING) and self._is_in_enemy_reach(current):
                self._log("  [bold yellow]⚠️  你在敵方觸及範圍內！離開將觸發藉機攻擊。[/]")
                self._log("  [yellow]提示：使用「撤離」動作可安全移動。[/]")
            self._log("  輸入目標座標 x y（例如 5 3）或方向（n/s/e/w/ne/nw/se/sw）")
            self._log("  [dim]0 — 返回[/]")
            self._menu_phase = "move_input"
        elif key == "attack":
            self._show_target_choices()
        elif key == "cast":
            self._show_spell_choices(current)
        elif key == "dodge":
            await self._player_dodge(current)
        elif key == "disengage":
            await self._player_disengage(current)
        elif key == "status":
            self._log(self._format_status(current))
        elif key == "end":
            await self._end_current_turn()

    async def _handle_target_menu(self, num: int, current: Character) -> None:
        """攻擊目標選單數字處理。"""
        if num == 0:
            self._show_action_choices()
            return
        if num < 1 or num > len(self._menu_options):
            self._log(f"[red]無效選項：{num}[/]")
            return
        target_name = self._menu_options[num - 1]
        await self._player_attack(current, target_name)

    async def _handle_spell_menu(self, num: int, current: Character) -> None:
        """法術選單數字處理。"""
        if num == 0:
            self._show_action_choices()
            return
        if num < 1 or num > len(self._menu_options):
            self._log(f"[red]無效選項：{num}[/]")
            return
        spell: Spell = self._menu_options[num - 1]

        # 先檢查能否施放
        error = can_cast(current, spell, slot_level=spell.level if spell.level > 0 else None)
        if error is not None:
            self._log(f"[red]無法施放：{error.reason}[/]")
            return

        self._pending_spell = spell
        # 需要目標的法術 → 進入目標選單
        if spell.effect_type.value in ("damage", "healing", "condition"):
            self._show_spell_target_choices()
        else:
            # BUFF / UTILITY → 直接施放（無目標）
            await self._player_cast(current, spell, target=None)

    async def _handle_spell_target_menu(self, num: int, current: Character) -> None:
        """法術目標選單數字處理。"""
        if num == 0:
            self._pending_spell = None
            self._show_spell_choices(current)
            return
        if num < 1 or num > len(self._menu_options):
            self._log(f"[red]無效選項：{num}[/]")
            return
        _, target = self._menu_options[num - 1]
        spell = self._pending_spell
        if not spell:
            return
        await self._player_cast(current, spell, target=target)

    # ----- 動作後流程 -----

    async def _after_action(self) -> None:
        """動作消耗後決定是否自動結束。"""
        if not self.combat_state:
            return
        ts = self.combat_state.turn_state
        if ts.action_used and ts.movement_remaining <= 0:
            await self._end_current_turn()
        else:
            self._show_action_choices()

    # ----- 玩家動作 -----

    def _step_move_to(
        self, mover: Character | Monster, actor: Actor, tx: int, ty: int,
    ) -> bool:
        """逐步移動角色到目標位置，每步檢查藉機攻擊。回傳 True 表示角色倒下。"""
        if not self.combat_state or not self.map_state:
            return False
        gs = self.map_state.manifest.grid_size_m
        start_x, start_y = actor.x, actor.y
        while actor.x != tx or actor.y != ty:
            old_x, old_y = actor.x, actor.y
            dx = 0 if tx == actor.x else (1 if tx > actor.x else -1)
            dy = 0 if ty == actor.y else (1 if ty > actor.y else -1)
            actor.x += dx
            actor.y += dy
            self.combat_state.turn_state.movement_remaining -= gs
            if self._check_oa_for_step(mover, old_x, old_y, actor.x, actor.y):
                total = max(abs(actor.x - start_x), abs(actor.y - start_y)) * gs
                self._log(
                    f"[cyan]🚶 {self._display_name(mover)} 移動到 ({actor.x}, {actor.y})"
                    f"（消耗 {total:.1f}m，剩餘 "
                    f"{self.combat_state.turn_state.movement_remaining:.1f}m）[/]"
                )
                return True
        total = max(abs(actor.x - start_x), abs(actor.y - start_y)) * gs
        if total > 0:
            self._log(
                f"[cyan]🚶 {self._display_name(mover)} 移動到 ({actor.x}, {actor.y})"
                f"（消耗 {total:.1f}m，剩餘 "
                f"{self.combat_state.turn_state.movement_remaining:.1f}m）[/]"
            )
        return False

    async def _player_move(self, character: Character, x: int, y: int) -> None:
        """玩家移動到目標座標。"""
        if not self.combat_state or not self.map_state:
            self._log("[yellow]無法移動。[/]")
            return

        actor = self._get_actor(character.id)
        if not actor:
            self._log("[red]找不到角色位置。[/]")
            return

        grid_size = self.map_state.manifest.grid_size_m
        remaining = self.combat_state.turn_state.movement_remaining

        # 計算 Chebyshev 距離
        dx = abs(x - actor.x)
        dy = abs(y - actor.y)
        grids = max(dx, dy)
        cost = grids * grid_size

        if cost == 0:
            self._log("[yellow]你已經在這個位置了。[/]")
            self._show_action_choices()
            return

        if cost > remaining:
            self._log(
                f"[red]移動距離不足！需要 {cost:.1f}m，剩餘 {remaining:.1f}m[/]"
            )
            self._show_action_choices()
            return

        # 檢查目標可通行（暫時解除自身阻擋）
        old_blocking = actor.is_blocking
        actor.is_blocking = False
        valid = is_valid_position(x, y, self.map_state)
        actor.is_blocking = old_blocking

        if not valid:
            self._log(f"[red]目標位置 ({x}, {y}) 不可通行！[/]")
            self._show_action_choices()
            return

        # 逐步移動（含 OA 檢查）
        killed = self._step_move_to(character, actor, x, y)
        self._refresh_all()
        if killed:
            await self._check_combat_end()
            return
        await self._after_action()

    async def _player_attack(self, attacker: Character, target_name: str) -> None:
        target = self._find_target(target_name)
        if not target:
            self._log(f"[red]找不到目標：{target_name}[/]")
            self._log(f"[dim]可攻擊目標：{', '.join(self._alive_monster_names())}[/]")
            return
        if not target.is_alive:
            self._log(f"[yellow]{self._display_name(target)} 已經倒下了。[/]")
            return

        # 距離檢查
        if self.map_state and self.combat_state:
            atk_pos = get_actor_position(attacker.id, self.map_state)
            tgt_pos = get_actor_position(target.id, self.map_state)
            if atk_pos and tgt_pos:
                gs = self.map_state.manifest.grid_size_m
                dist = grid_distance(atk_pos, tgt_pos, gs)
                if attacker.weapons:
                    weapon = attacker.weapons[0]
                    err = validate_attack_preconditions(
                        attacker, weapon, self.combat_state,
                        distance=dist, grid_size=gs,
                    )
                    if err and err != "行動已使用":
                        # 嘗試自動移動建議
                        reach = weapon.range_normal
                        sim = self._simulate_move_to_range(
                            attacker.id, target.id, reach,
                        )
                        if sim:
                            mx, my, mcost = sim
                            self._log(
                                f"[yellow]距離不足！移動到 ({mx}, {my}) "
                                f"後攻擊？消耗 {mcost:.1f}m 移動（y/n）[/]"
                            )
                            self._pending_move_pos = Position(x=mx, y=my)
                            self._pending_auto_target = target
                            self._pending_auto_type = "weapon"
                            self._menu_phase = "confirm_move_attack"
                            return
                        self._log(f"[red]{err}（距離 {dist:.1f}m，移動距離不足以接近）[/]")
                        self._show_action_choices()
                        return

        self._execute_attack(attacker, target)
        self._refresh_all()
        if await self._check_combat_end():
            return
        await self._after_action()

    async def _player_dodge(self, current: Character) -> None:
        """閃避動作。"""
        if self.combat_state and take_dodge_action(current, self.combat_state):
            self._log(f"[cyan]🛡 {current.name} 採取閃避動作！（敵方攻擊獲得劣勢）[/]")
            self._refresh_all()
            await self._after_action()
        else:
            self._log("[yellow]無法執行閃避。[/]")

    async def _player_disengage(self, current: Character) -> None:
        """撤離動作。"""
        if self.combat_state and take_disengage_action(current, self.combat_state):
            self._log(f"[cyan]🏃 {current.name} 採取撤離動作！（本輪移動不觸發藉機攻擊）[/]")
            self._refresh_all()
            await self._after_action()
        else:
            self._log("[yellow]無法執行撤離。[/]")

    def _is_in_enemy_reach(self, combatant: Character | Monster) -> bool:
        """檢查角色是否在任何敵方的觸及範圍內。"""
        if not self.map_state:
            return False
        actor = self._get_actor(combatant.id)
        if not actor:
            return False
        for other in self.map_state.actors:
            if other.combatant_id == combatant.id or not other.is_alive:
                continue
            enemy = self._combatant_map.get(other.combatant_id)
            if not enemy:
                continue
            # 同陣營不算
            if isinstance(combatant, Character) and isinstance(enemy, Character):
                continue
            if isinstance(combatant, Monster) and isinstance(enemy, Monster):
                continue
            # 取得觸及範圍
            reach = 1
            if isinstance(enemy, Character) and enemy.weapons:
                reach = enemy.weapons[0].range_normal
            elif isinstance(enemy, Monster) and enemy.actions:
                reach = enemy.actions[0].reach
            dist = max(abs(other.x - actor.x), abs(other.y - actor.y))
            if dist <= reach:
                return True
        return False

    async def _player_cast_by_name(self, caster: Character, spell_name: str) -> None:
        """透過指令名稱施法。"""
        spell = get_spell_by_name(spell_name)
        if not spell:
            self._log(f"[red]找不到法術：{spell_name}[/]")
            return
        error = can_cast(caster, spell, slot_level=spell.level if spell.level > 0 else None)
        if error is not None:
            self._log(f"[red]無法施放：{error.reason}[/]")
            return
        # 需要目標 → 進入目標選單
        if spell.effect_type.value in ("damage", "healing", "condition"):
            self._pending_spell = spell
            self._show_spell_target_choices()
        else:
            await self._player_cast(caster, spell, target=None)

    async def _player_cast(
        self, caster: Character, spell: Spell, target: Character | Monster | None
    ) -> None:
        """執行施法。"""
        if not self.combat_state:
            return

        # 法術射程檢查
        if target and self.map_state:
            caster_pos = get_actor_position(caster.id, self.map_state)
            tgt_pos = get_actor_position(target.id, self.map_state)
            if caster_pos and tgt_pos:
                gs = self.map_state.manifest.grid_size_m
                dist = grid_distance(caster_pos, tgt_pos, gs)
                range_err = validate_spell_range(spell, dist, gs)
                if range_err:
                    # 嘗試自動移動建議
                    range_m = parse_spell_range_meters(spell.range, gs)
                    range_grids = max(1, int(range_m / gs)) if range_m else 1
                    sim = self._simulate_move_to_range(
                        caster.id, target.id, range_grids,
                    )
                    if sim:
                        mx, my, mcost = sim
                        self._log(
                            f"[yellow]法術射程不足！移動到 ({mx}, {my}) "
                            f"後施放？消耗 {mcost:.1f}m 移動（y/n）[/]"
                        )
                        self._pending_move_pos = Position(x=mx, y=my)
                        self._pending_auto_target = target
                        self._pending_auto_type = "spell"
                        self._menu_phase = "confirm_move_attack"
                        return
                    self._log(f"[red]{range_err}[/]")
                    self._pending_spell = None
                    self._show_action_choices()
                    return

        # 非戲法消耗 Action
        if spell.level > 0 and not use_action(self.combat_state):
            self._log("[yellow]本回合已使用過動作！[/]")
            return

        slot = spell.level if spell.level > 0 else None
        result = cast_spell(caster, spell, target, slot_level=slot)
        self._log(f"[magenta]✨ {result.message}[/]")

        if result.concentration_broken:
            self._log(f"[yellow]（專注中斷：{result.concentration_broken}）[/]")
        if result.concentration_started:
            self._log(f"[dim]（開始專注：{spell.name}）[/]")

        self._pending_spell = None
        self._refresh_all()

        if await self._check_combat_end():
            return

        # 戲法：手動標記 action
        if spell.level == 0 and not self.combat_state.turn_state.action_used:
            use_action(self.combat_state)

        await self._after_action()

    # ----- 攻擊執行 -----

    def _execute_attack(self, attacker: Character | Monster, target: Character | Monster) -> None:
        if not self.combat_state:
            return

        if not can_take_action(attacker):
            self._log(f"[yellow]{self._display_name(attacker)} 無法行動！[/]")
            return

        if not use_action(self.combat_state):
            self._log("[yellow]本回合已使用過動作！[/]")
            return

        weapon: Weapon | MonsterAction
        if isinstance(attacker, Monster):
            if not attacker.actions:
                self._log(f"[yellow]{self._display_name(attacker)} 沒有可用動作。[/]")
                return
            weapon = attacker.actions[0]
        else:
            if not attacker.weapons:
                self._log(f"[yellow]{self._display_name(attacker)} 沒有武器！[/]")
                return
            weapon = attacker.weapons[0]

        atk_bonus = _get_attack_bonus(attacker, weapon)
        target_ac = target.ac
        attack_result = resolve_attack(atk_bonus, target_ac)

        atk_name = self._display_name(attacker)
        tgt_name = self._display_name(target)
        wpn_name = weapon.name
        roll_val = attack_result.roll_result.total

        if attack_result.is_critical:
            self._log(
                f"[bold red]💥 {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
                f"— 擲骰 {roll_val} vs AC {target_ac} — 爆擊！[/]"
            )
        elif attack_result.is_hit:
            self._log(
                f"[green]🎯 {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
                f"— 擲骰 {roll_val} vs AC {target_ac} — 命中！[/]"
            )
        else:
            self._log(
                f"[dim]❌ {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
                f"— 擲骰 {roll_val} vs AC {target_ac} — 未中[/]"
            )
            return

        dmg_mod = _get_damage_modifier(attacker, weapon)
        dmg_type = weapon.damage_type
        dmg_result = roll_damage(
            weapon.damage_dice,
            dmg_type,
            modifier=dmg_mod,
            is_critical=attack_result.is_critical,
        )

        apply_result = apply_damage(target, dmg_result.total, dmg_type, attack_result.is_critical)

        self._log(
            f"  💥 造成 [bold]{apply_result.actual_damage}[/] 點 {_zh_dmg(dmg_type)} 傷害 "
            f"（{tgt_name} HP: {target.hp_current}/{target.hp_max}）"
        )

        if apply_result.target_dropped_to_zero:
            if isinstance(target, Monster):
                self._log(f"  [bold red]☠️  {tgt_name} 被擊倒了！[/]")
            else:
                self._log(f"  [bold yellow]⚠️  {tgt_name} 倒下了！[/]")

        if apply_result.instant_death:
            self._log(f"  [bold red]💀 {tgt_name} 即死！[/]")

    # ----- 藉機攻擊 -----

    def _check_oa_for_step(
        self,
        mover: Character | Monster,
        old_x: int,
        old_y: int,
        new_x: int,
        new_y: int,
    ) -> bool:
        """檢查移動一步時是否觸發藉機攻擊。回傳 True 表示 mover 倒下。"""
        if not self.combat_state or not self.map_state:
            return False

        # 撤離動作：不觸發藉機攻擊
        if mover.has_condition(Condition.DISENGAGING):
            return False

        for entry in self.combat_state.initiative_order:
            enemy = self._combatant_map.get(entry.combatant_id)
            if not enemy or not enemy.is_alive or enemy.id == mover.id:
                continue
            # 同陣營不觸發
            if isinstance(mover, Character) and isinstance(enemy, Character):
                continue
            if isinstance(mover, Monster) and isinstance(enemy, Monster):
                continue

            enemy_actor = self._get_actor(enemy.id)
            if not enemy_actor:
                continue

            # 取得觸及範圍（格數）
            reach = 1
            if isinstance(enemy, Character) and enemy.weapons:
                reach = enemy.weapons[0].range_normal
            elif isinstance(enemy, Monster) and enemy.actions:
                reach = enemy.actions[0].reach

            # 移動前在觸及範圍內？
            old_dist = max(abs(enemy_actor.x - old_x), abs(enemy_actor.y - old_y))
            if old_dist > reach:
                continue
            # 移動後仍在觸及範圍？→ 不觸發
            new_dist = max(abs(enemy_actor.x - new_x), abs(enemy_actor.y - new_y))
            if new_dist <= reach:
                continue

            # 建立武器
            weapon: Weapon | None = None
            if isinstance(enemy, Character) and enemy.weapons:
                weapon = enemy.weapons[0]
            elif isinstance(enemy, Monster) and enemy.actions:
                act = enemy.actions[0]
                weapon = Weapon(
                    name=act.name,
                    damage_dice=act.damage_dice,
                    damage_type=act.damage_type,
                    properties=[],
                )

            if not weapon:
                continue

            oa = check_opportunity_attack(
                attacker=enemy,
                target=mover,
                entry=entry,
                weapon=weapon,
                target_ac=mover.ac,
            )
            if not oa.triggered:
                continue

            enemy_name = self._display_name(enemy)
            mover_name = self._display_name(mover)

            if oa.attack_result and oa.attack_result.is_hit and oa.damage_result:
                apply_result = apply_damage(
                    mover,
                    oa.damage_result.total,
                    weapon.damage_type,
                    oa.attack_result.is_critical,
                )
                self._log(
                    f"[bold red]⚡ 藉機攻擊！{enemy_name} 用 {weapon.name} "
                    f"攻擊離開觸及範圍的 {mover_name} "
                    f"— 造成 {apply_result.actual_damage} 點 "
                    f"{_zh_dmg(weapon.damage_type)} 傷害 "
                    f"（HP: {mover.hp_current}/{mover.hp_max}）[/]"
                )
                if not mover.is_alive:
                    self._log(
                        f"  [bold red]☠️  {mover_name} 被藉機攻擊擊倒！[/]"
                    )
                    return True
            else:
                self._log(
                    f"[dim]⚡ 藉機攻擊！{enemy_name} 攻擊離開的 "
                    f"{mover_name} — 未中[/]"
                )

        return False

    # ----- 自動移動建議 -----

    def _simulate_move_to_range(
        self,
        attacker_id: UUID,
        target_id: UUID,
        range_grids: int,
    ) -> tuple[int, int, float] | None:
        """模擬 BFS 移動到攻擊/法術範圍。回傳 (x, y, 移動消耗) 或 None。"""
        if not self.map_state or not self.combat_state:
            return None

        gs = self.map_state.manifest.grid_size_m
        actor = self._get_actor(attacker_id)
        tgt_pos = get_actor_position(target_id, self.map_state)
        if not actor or not tgt_pos:
            return None

        speed_left = self.combat_state.turn_state.movement_remaining
        max_steps = int(speed_left / gs)
        if max_steps <= 0:
            return None

        start = Position(x=actor.x, y=actor.y)

        # 建立友方 ID
        combatant = self._combatant_map.get(actor.combatant_id)
        friendly_ids: set[UUID] = set()
        if combatant:
            friendly_ids = self._build_friendly_ids(combatant)

        path = bfs_path_to_range(
            start=start,
            target=tgt_pos,
            reach_grids=range_grids,
            map_state=self.map_state,
            max_steps=max_steps,
            mover_id=actor.combatant_id,
            friendly_ids=friendly_ids,
        )

        if path is not None and len(path) > 0:
            end = path[-1]
            cost = len(path) * gs
            return (end.x, end.y, cost)
        return None

    def _clear_pending(self) -> None:
        """清除自動移動待確認狀態。"""
        self._pending_move_pos = None
        self._pending_auto_target = None
        self._pending_auto_type = ""

    async def _handle_confirm_move_attack(
        self, cmd: str, current: Character,
    ) -> None:
        """處理自動移動確認。"""
        if cmd in ("y", "yes", "是"):
            pos = self._pending_move_pos
            target = self._pending_auto_target
            auto_type = self._pending_auto_type
            spell = self._pending_spell
            self._clear_pending()

            if pos and self.combat_state:
                actor = self._get_actor(current.id)
                if actor:
                    killed = self._step_move_to(current, actor, pos.x, pos.y)
                    self._refresh_all()
                    if killed:
                        await self._check_combat_end()
                        return

                    # 執行攻擊或施法
                    if auto_type == "weapon" and target and target.is_alive:
                        self._execute_attack(current, target)
                        self._refresh_all()
                        if await self._check_combat_end():
                            return
                    elif auto_type == "spell" and spell and target:
                        await self._player_cast(current, spell, target)
                        return

            await self._after_action()

        elif cmd in ("n", "no", "否"):
            self._clear_pending()
            self._show_action_choices()
        else:
            self._log("[yellow]請輸入 y 或 n[/]")

    # ----- 回合管理 -----

    def _is_npc_turn(self, combatant: Character | Monster | None) -> bool:
        """判斷是否為 NPC（怪物或 AI 角色）回合。"""
        if isinstance(combatant, Monster):
            return True
        if isinstance(combatant, Character) and combatant.is_ai_controlled:
            return True
        return False

    async def _start_next_turn(self) -> None:
        """統一入口：判斷當前回合是 PC、AI 隊友還是怪物。"""
        if await self._check_combat_end():
            return
        current = self._current_combatant()
        if self._is_npc_turn(current):
            await self._schedule_npc_turns()
        elif isinstance(current, Character):
            await self._prompt_current_turn()

    async def _end_current_turn(self) -> None:
        if not self.combat_state:
            return
        self._menu_phase = "locked"

        current = self._current_combatant()
        if current:
            expired = tick_conditions_end_of_turn(current)
            for ac in expired:
                self._log(
                    f"[dim]{self._display_name(current)} 的 {ac.condition.value} 效果結束。[/]"
                )

        advance_turn(self.combat_state)
        self._refresh_all()

        await self._start_next_turn()

    async def _schedule_npc_turns(self) -> None:
        """排程 NPC（怪物 + AI 角色）回合。"""
        self._input_locked = True
        self._menu_phase = "locked"
        self.query_one("#cmd-input", Input).disabled = True
        self.set_timer(0.5, self._do_one_npc_turn)

    async def _do_one_npc_turn(self) -> None:
        """執行一個 NPC 的完整回合（怪物或 AI 角色）。"""
        current = self._current_combatant()
        if not self._is_npc_turn(current):
            # 到了玩家回合，解鎖輸入
            self._input_locked = False
            self.query_one("#cmd-input", Input).disabled = False
            await self._start_next_turn()
            return

        # 執行 NPC 回合
        if isinstance(current, Monster):
            self._monster_turn(current)
        elif isinstance(current, Character) and current.is_ai_controlled:
            self._ai_character_turn(current)

        expired = tick_conditions_end_of_turn(current)
        for ac in expired:
            self._log(f"[dim]{self._display_name(current)} 的 {ac.condition.value} 效果結束。[/]")
        advance_turn(self.combat_state)
        self._refresh_all()

        if await self._check_combat_end():
            self._input_locked = False
            self.query_one("#cmd-input", Input).disabled = False
            return

        self.set_timer(0.8, self._do_one_npc_turn)

    # ----- 共用移動邏輯 -----

    def _build_friendly_ids(self, mover: Character | Monster) -> set[UUID]:
        """建立友方 ID 集合（Character → 所有 character；Monster → 所有 monster）。"""
        if isinstance(mover, Character):
            return {c.id for c in self.characters}
        return {m.id for m in self.monsters}

    def _greedy_move_toward(
        self,
        actor: Actor,
        target_id: UUID,
        reach: int = 1,
        mover: Character | Monster | None = None,
    ) -> float:
        """BFS 尋路移動 actor 靠近 target，回傳最終距離（公尺）。

        若提供 mover，每步會檢查藉機攻擊。
        BFS 失敗時回退到 greedy。
        """
        if not self.map_state or not self.combat_state:
            return float("inf")

        gs = self.map_state.manifest.grid_size_m
        tgt_pos = get_actor_position(target_id, self.map_state)
        speed_left = self.combat_state.turn_state.movement_remaining

        if not tgt_pos:
            return float("inf")

        # 已在攻擊範圍內
        cur_pos = Position(x=actor.x, y=actor.y)
        if grid_distance(cur_pos, tgt_pos, gs) <= reach * gs:
            return grid_distance(cur_pos, tgt_pos, gs)

        max_steps = int(speed_left / gs)
        if max_steps <= 0:
            return grid_distance(cur_pos, tgt_pos, gs)

        # 建立友方 ID
        friendly_ids = self._build_friendly_ids(mover) if mover else set()

        path = bfs_path_to_range(
            start=cur_pos,
            target=tgt_pos,
            reach_grids=reach,
            map_state=self.map_state,
            max_steps=max_steps,
            mover_id=actor.combatant_id,
            friendly_ids=friendly_ids,
        )

        if path is not None and len(path) > 0:
            # 沿 BFS 路徑逐步移動
            for step in path:
                if speed_left < gs:
                    break
                old_x, old_y = actor.x, actor.y
                actor.x = step.x
                actor.y = step.y
                speed_left -= gs
                if mover and self._check_oa_for_step(mover, old_x, old_y, actor.x, actor.y):
                    break  # mover 被擊倒
        else:
            # BFS 失敗 → greedy fallback
            steps = 0
            while steps < max_steps and speed_left >= gs:
                cp = Position(x=actor.x, y=actor.y)
                if grid_distance(cp, tgt_pos, gs) <= reach * gs:
                    break
                dx = 0 if tgt_pos.x == actor.x else (1 if tgt_pos.x > actor.x else -1)
                dy = 0 if tgt_pos.y == actor.y else (1 if tgt_pos.y > actor.y else -1)
                old_x, old_y = actor.x, actor.y
                ok, speed_left = move_entity(actor, dx, dy, self.map_state, speed_left)
                if not ok:
                    if dx != 0:
                        ok, speed_left = move_entity(actor, dx, 0, self.map_state, speed_left)
                    if not ok and dy != 0:
                        ok, speed_left = move_entity(actor, 0, dy, self.map_state, speed_left)
                    if not ok:
                        break
                if mover and self._check_oa_for_step(mover, old_x, old_y, actor.x, actor.y):
                    break
                steps += 1

        self.combat_state.turn_state.movement_remaining = speed_left

        new_pos = Position(x=actor.x, y=actor.y)
        return grid_distance(new_pos, tgt_pos, gs) if tgt_pos else float("inf")

    # ----- 怪物 AI -----

    def _monster_turn(self, monster: Monster) -> None:
        """怪物自動行動——移動靠近並攻擊存活 PC。"""
        if not monster.is_alive:
            self._log(f"[dim]{self._display_name(monster)} 已倒下，跳過回合。[/]")
            return

        if not can_take_action(monster):
            self._log(f"[dim]{self._display_name(monster)} 無法行動，跳過回合。[/]")
            return

        self._log(f"\n[bold magenta]🗡️  {self._display_name(monster)} 的回合[/]")

        # 設定怪物移動距離
        if self.combat_state:
            self.combat_state.turn_state.movement_remaining = float(monster.speed)

        alive_pcs = [c for c in self.characters if c.is_alive and c.hp_current > 0]
        if not alive_pcs:
            return

        # 找最近的存活 PC
        mon_actor = self._get_actor(monster.id)
        target = alive_pcs[0]
        best_dist = float("inf")

        if mon_actor and self.map_state:
            mon_pos = Position(x=mon_actor.x, y=mon_actor.y)
            for pc in alive_pcs:
                pc_pos = get_actor_position(pc.id, self.map_state)
                if pc_pos:
                    d = grid_distance(mon_pos, pc_pos, self.map_state.manifest.grid_size_m)
                    if d < best_dist:
                        best_dist = d
                        target = pc

        # 取得武器/動作的觸及範圍（格數）
        reach_grids = 1
        if monster.actions:
            reach_grids = monster.actions[0].reach

        # 嘗試移動靠近目標
        if mon_actor and self.map_state and self.combat_state:
            old_x, old_y = mon_actor.x, mon_actor.y
            best_dist = self._greedy_move_toward(
                mon_actor, target.id, reach_grids, mover=monster,
            )
            if not monster.is_alive:
                self._refresh_all()
                return
            if mon_actor.x != old_x or mon_actor.y != old_y:
                self._log(
                    f"  [dim]{self._display_name(monster)} 移動到 "
                    f"({mon_actor.x}, {mon_actor.y})（距離 {target.name}: {best_dist:.1f}m）[/]"
                )

        # 距離檢查
        in_range = True
        if mon_actor and self.map_state:
            gs = self.map_state.manifest.grid_size_m
            if best_dist > reach_grids * gs:
                in_range = False
                name = self._display_name(monster)
                self._log(
                    f"  [dim]{name} 無法接近 {target.name}"
                    f"（距離 {best_dist:.1f}m）[/]"
                )

        if in_range:
            self._execute_attack(monster, target)
        self._refresh_all()

    # ----- AI 角色行動 -----

    def _ai_character_turn(self, char: Character) -> None:
        """AI 角色回合——根據職業分派。"""
        if not char.is_alive or char.hp_current <= 0:
            self._log(f"[dim]{char.name} 已倒下，跳過回合。[/]")
            return

        if not can_take_action(char):
            self._log(f"[dim]{char.name} 無法行動，跳過回合。[/]")
            return

        self._log(f"\n[bold blue]🤖 {char.name}（AI）的回合[/]")

        if self.combat_state:
            self.combat_state.turn_state.movement_remaining = float(char.speed)

        # 根據職業分派
        if char.char_class in ("Cleric", "Wizard", "Sorcerer", "Warlock", "Druid"):
            self._ai_caster_turn(char)
        else:
            self._ai_melee_turn(char)

    def _ai_melee_turn(self, char: Character) -> None:
        """AI 近戰角色——移動靠近最近敵人 + 攻擊。"""
        alive_enemies = [m for m in self.monsters if m.is_alive]
        if not alive_enemies:
            return

        char_actor = self._get_actor(char.id)
        if not char_actor or not self.map_state:
            return

        # 找最近的敵人
        target = alive_enemies[0]
        best_dist = float("inf")
        char_pos = Position(x=char_actor.x, y=char_actor.y)
        for enemy in alive_enemies:
            enemy_pos = get_actor_position(enemy.id, self.map_state)
            if enemy_pos:
                d = grid_distance(char_pos, enemy_pos, self.map_state.manifest.grid_size_m)
                if d < best_dist:
                    best_dist = d
                    target = enemy

        # 取得武器觸及範圍
        reach = 1
        if char.weapons:
            reach = char.weapons[0].range_normal

        # 移動靠近
        if self.combat_state:
            old_x, old_y = char_actor.x, char_actor.y
            best_dist = self._greedy_move_toward(
                char_actor, target.id, reach, mover=char,
            )
            if not char.is_alive:
                self._refresh_all()
                return
            if char_actor.x != old_x or char_actor.y != old_y:
                self._log(
                    f"  [dim]{char.name} 移動到 ({char_actor.x}, {char_actor.y})"
                    f"（距離 {self._display_name(target)}: {best_dist:.1f}m）[/]"
                )

        # 攻擊
        gs = self.map_state.manifest.grid_size_m
        if best_dist <= reach * gs:
            self._execute_attack(char, target)
        else:
            self._log(f"  [dim]{char.name} 無法接近 {self._display_name(target)}[/]")

        self._refresh_all()

    def _ai_caster_turn(self, char: Character) -> None:
        """AI 施法者——優先治療隊友(HP<50%) → 攻擊法術 → 戲法 → 近戰。"""
        # 1. 檢查是否有隊友需要治療
        if self._ai_try_heal(char):
            self._refresh_all()
            return

        # 2. 嘗試攻擊法術
        if self._ai_try_attack_spell(char):
            self._refresh_all()
            return

        # 3. 嘗試戲法
        if self._ai_try_cantrip(char):
            self._refresh_all()
            return

        # 4. 退化為近戰
        self._ai_melee_turn(char)

    def _ai_try_heal(self, char: Character) -> bool:
        """嘗試治療 HP < 50% 的隊友。回傳 True 表示有行動。"""
        if not self.combat_state:
            return False

        # 找受傷隊友
        wounded = [
            c for c in self.characters
            if c.is_alive and c.hp_current > 0
            and c.hp_current < c.hp_max * 0.5
        ]
        if not wounded:
            return False

        # 找治療法術
        healing_spells = []
        for name in char.spells_prepared:
            spell = get_spell_by_name(name)
            if spell and spell.effect_type.value == "healing":
                healing_spells.append(spell)

        if not healing_spells:
            return False

        # 選第一個能施放的治療法術
        for spell in healing_spells:
            slot = spell.level if spell.level > 0 else None
            error = can_cast(char, spell, slot_level=slot)
            if error is not None:
                continue

            # 選 HP 最低的隊友
            target = min(wounded, key=lambda c: c.hp_current / c.hp_max)

            # 射程檢查
            if self.map_state:
                caster_pos = get_actor_position(char.id, self.map_state)
                tgt_pos = get_actor_position(target.id, self.map_state)
                if caster_pos and tgt_pos:
                    gs = self.map_state.manifest.grid_size_m
                    dist = grid_distance(caster_pos, tgt_pos, gs)
                    range_err = validate_spell_range(spell, dist, gs)
                    if range_err:
                        continue

            # 施法
            if spell.level > 0:
                use_action(self.combat_state)
            result = cast_spell(char, spell, target, slot_level=slot)
            self._log(f"[magenta]✨ {result.message}[/]")
            if spell.level == 0:
                use_action(self.combat_state)
            return True

        return False

    def _ai_try_attack_spell(self, char: Character) -> bool:
        """嘗試對怪物施放攻擊法術（非戲法）。回傳 True 表示有行動。"""
        if not self.combat_state:
            return False

        alive_enemies = [m for m in self.monsters if m.is_alive]
        if not alive_enemies:
            return False

        # 找攻擊法術（非戲法）
        attack_spells = []
        for name in char.spells_prepared:
            spell = get_spell_by_name(name)
            if spell and spell.level > 0 and spell.effect_type.value == "damage":
                attack_spells.append(spell)

        for spell in attack_spells:
            slot = spell.level
            error = can_cast(char, spell, slot_level=slot)
            if error is not None:
                continue

            # 找射程內的目標
            target = self._find_ai_spell_target(char, spell, alive_enemies)
            if not target:
                continue

            use_action(self.combat_state)
            result = cast_spell(char, spell, target, slot_level=slot)
            self._log(f"[magenta]✨ {result.message}[/]")
            return True

        return False

    def _ai_try_cantrip(self, char: Character) -> bool:
        """嘗試施放攻擊戲法。回傳 True 表示有行動。"""
        if not self.combat_state:
            return False

        alive_enemies = [m for m in self.monsters if m.is_alive]
        if not alive_enemies:
            return False

        # 找戲法
        cantrips = []
        for name in list(dict.fromkeys(char.spells_prepared + char.spells_known)):
            spell = get_spell_by_name(name)
            if spell and spell.level == 0 and spell.effect_type.value == "damage":
                cantrips.append(spell)

        for spell in cantrips:
            error = can_cast(char, spell, slot_level=None)
            if error is not None:
                continue

            target = self._find_ai_spell_target(char, spell, alive_enemies)
            if not target:
                continue

            result = cast_spell(char, spell, target, slot_level=None)
            self._log(f"[magenta]✨ {result.message}[/]")
            use_action(self.combat_state)
            return True

        return False

    def _find_ai_spell_target(
        self, caster: Character, spell: Spell, candidates: list[Monster]
    ) -> Monster | None:
        """找射程內的第一個合法目標。"""
        if not self.map_state:
            return candidates[0] if candidates else None

        caster_pos = get_actor_position(caster.id, self.map_state)
        if not caster_pos:
            return candidates[0] if candidates else None

        gs = self.map_state.manifest.grid_size_m
        for enemy in candidates:
            tgt_pos = get_actor_position(enemy.id, self.map_state)
            if not tgt_pos:
                continue
            dist = grid_distance(caster_pos, tgt_pos, gs)
            range_err = validate_spell_range(spell, dist, gs)
            if not range_err:
                return enemy

        return None

    # ----- 玩家回合提示 -----

    async def _prompt_current_turn(self) -> None:
        """提示當前玩家行動並印出動作選單。"""
        current = self._current_combatant()
        if not current or not isinstance(current, Character):
            return

        if not self.combat_state:
            return

        # 回合開始設定移動距離
        self.combat_state.turn_state.movement_remaining = float(current.speed)

        self._log(
            f"\n[bold white]⚔️  第 {self.combat_state.round_number} 輪 — {current.name} 的回合[/]"
        )

        input_widget = self.query_one("#cmd-input", Input)
        actor = self._get_actor(current.id)
        emoji = actor.symbol if actor else "🧙"
        input_widget.placeholder = f"{emoji} {current.name} > 輸入數字或指令"
        self._show_action_choices()

    async def _check_combat_end(self) -> bool:
        """檢查戰鬥是否結束。"""
        if not self.combat_state:
            return True

        all_monsters_dead = all(not m.is_alive for m in self.monsters)
        all_pcs_down = all(c.hp_current <= 0 for c in self.characters)

        if all_monsters_dead:
            self.combat_state.is_active = False
            self._menu_phase = "locked"
            total_xp = sum(m.xp_reward for m in self.monsters)
            self._log("\n[bold green]🎉 勝利！所有敵人被擊敗！[/]")
            self._log(f"[green]獲得經驗值：{total_xp} XP[/]")
            self._refresh_all()
            return True

        if all_pcs_down:
            self.combat_state.is_active = False
            self._menu_phase = "locked"
            self._log("\n[bold red]💀 全滅…全體隊員倒下了。[/]")
            self._refresh_all()
            return True

        return False

    # ----- 顯示格式化方法 -----

    def _format_status(self, combatant: Character | Monster) -> str:
        """格式化完整角色狀態。"""
        name = self._display_name(combatant)
        lines = [f"\n[bold cyan]── {name} 狀態 ──[/]"]

        if isinstance(combatant, Character):
            lines.append(f"  等級 {combatant.level} {combatant.char_class}")
        else:
            lines.append(f"  CR {combatant.challenge_rating}")

        lines.append(f"  HP: {combatant.hp_current}/{combatant.hp_max}  AC: {combatant.ac}")

        # 六屬性
        scores = combatant.ability_scores
        stats = []
        for ab in Ability:
            val = scores.score(ab)
            mod = scores.modifier(ab)
            sign = "+" if mod >= 0 else ""
            stats.append(f"{ab.value} {val}({sign}{mod})")
        lines.append(f"  {' | '.join(stats)}")

        # 武器
        if isinstance(combatant, Character) and combatant.weapons:
            wpns = ", ".join(w.name for w in combatant.weapons)
            lines.append(f"  武器: {wpns}")
        elif isinstance(combatant, Monster) and combatant.actions:
            acts = ", ".join(a.name for a in combatant.actions)
            lines.append(f"  動作: {acts}")

        # 狀態異常
        if combatant.conditions:
            conds = ", ".join(c.condition.value for c in combatant.conditions)
            lines.append(f"  狀態異常: [yellow]{conds}[/]")

        # 法術（Character only）
        if isinstance(combatant, Character) and combatant.spell_dc:
            lines.append(f"  法術 DC: {combatant.spell_dc}  攻擊: +{combatant.spell_attack}")

        return "\n".join(lines)

    def _format_conditions(self) -> str:
        """所有戰場上的狀態異常。"""
        lines = ["\n[bold yellow]── 戰場狀態異常 ──[/]"]
        found = False
        all_combatants = list(self.characters) + list(self.monsters)
        for c in all_combatants:
            if c.conditions:
                name = self._display_name(c)
                for ac in c.conditions:
                    remaining = (
                        f"（{ac.remaining_rounds} 輪）"
                        if ac.remaining_rounds is not None
                        else "（持續）"
                    )
                    lines.append(f"  {name}: {ac.condition.value} {remaining}")
                found = True
        if not found:
            lines.append("  [dim]無任何狀態異常[/]")
        return "\n".join(lines)

    def _format_initiative(self) -> str:
        """完整先攻順序。"""
        if not self.combat_state:
            return ""
        lines = ["\n[bold cyan]── 先攻順序 ──[/]"]
        for idx, entry in enumerate(self.combat_state.initiative_order):
            combatant = self._combatant_map.get(entry.combatant_id)
            if not combatant:
                continue
            name = self._display_name(combatant)
            marker = " ◀ 當前" if idx == self.combat_state.current_turn_index else ""
            alive = "" if combatant.is_alive else " [red]💀[/]"
            lines.append(f"  {entry.initiative:2d} — {name}{alive}{marker}")
        return "\n".join(lines)

    def _format_spells(self, char: Character) -> str:
        """法術列表 + 剩餘欄位。"""
        lines = [f"\n[bold magenta]── {char.name} 法術 ──[/]"]

        # 法術欄位
        if char.spell_slots.max_slots:
            slot_parts = []
            for lvl in sorted(char.spell_slots.max_slots.keys()):
                cur = char.spell_slots.current_slots.get(lvl, 0)
                mx = char.spell_slots.max_slots[lvl]
                slot_parts.append(f"{lvl}環: {cur}/{mx}")
            lines.append(f"  欄位: {' | '.join(slot_parts)}")

        # 已準備法術
        spell_names = list(dict.fromkeys(char.spells_prepared + char.spells_known))
        if spell_names:
            for name in spell_names:
                spell = get_spell_by_name(name)
                if spell:
                    level_str = "戲法" if spell.level == 0 else f"{spell.level}環"
                    lines.append(f"  • {spell.name} ({level_str}) — {spell.description[:40]}")
        else:
            lines.append("  [dim]無已準備法術[/]")

        if char.concentration_spell:
            lines.append(f"  [yellow]專注中: {char.concentration_spell}[/]")

        return "\n".join(lines)

    def _show_help(self) -> None:
        """顯示完整指令說明。"""
        self._log("\n[bold white]── 指令說明 ──[/]")
        self._log("[cyan]查詢指令[/]（不消耗動作）：")
        self._log("  status          — 當前角色狀態")
        self._log("  status <名字>   — 指定角色/怪物狀態")
        self._log("  conditions      — 所有戰場狀態異常")
        self._log("  initiative      — 先攻順序")
        self._log("  spells          — 法術列表 + 剩餘欄位")
        self._log("  map             — 重新渲染地圖")
        self._log("  help            — 本說明")
        self._log("[cyan]動作指令[/]：")
        self._log("  move x y        — 移動到座標 (x, y)")
        self._log("  move 方向       — 方向移動（n/s/e/w/ne/nw/se/sw）")
        self._log("  attack <目標>   — 武器攻擊（消耗動作）")
        self._log("  cast <法術名>   — 施放法術（消耗動作）")
        self._log("  dodge           — 閃避（消耗動作）")
        self._log("  disengage       — 撤離（消耗動作，安全離開觸及範圍）")
        self._log("  end             — 結束回合")
        self._log("  quit            — 離開遊戲")
        self._log("[dim]也可使用數字選單選擇動作。[/]")

    # ----- 查找輔助 -----

    def _current_combatant(self) -> Character | Monster | None:
        if not self.combat_state:
            return None
        entry = self.combat_state.initiative_order[self.combat_state.current_turn_index]
        return self._combatant_map.get(entry.combatant_id)

    def _find_target(self, name: str) -> Character | Monster | None:
        """模糊搜尋目標名稱。"""
        name_lower = name.lower()
        for m in self.monsters:
            label = (m.label or m.name).lower()
            if label == name_lower or m.name.lower() == name_lower:
                return m
        for m in self.monsters:
            label = (m.label or m.name).lower()
            if name_lower in label or name_lower in m.name.lower():
                return m
        for c in self.characters:
            if c.name.lower() == name_lower or name_lower in c.name.lower():
                return c
        return None

    def _alive_monster_names(self) -> list[str]:
        return [m.label or m.name for m in self.monsters if m.is_alive]

    @staticmethod
    def _display_name(combatant: Character | Monster) -> str:
        if isinstance(combatant, Monster):
            return combatant.label or combatant.name
        return combatant.name
