"""探索 TUI 選單狀態機 + 指令處理。

ExplorePhase 管理目前的互動狀態（主選單/移動選擇/門互動/角色選擇…）。
所有指令最終都呼叫 bone_engine 函式。
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from tot.gremlins.bone_engine.checks import (
    ability_check,
    best_passive_perception,
    skill_check,
)
from tot.gremlins.bone_engine.exploration import (
    attempt_jump,
    auto_passive_perception,
    force_open_edge,
    format_time,
    get_available_exits,
    get_node_description,
    get_visible_items,
    list_pois,
    move_to_node,
    search_items,
    search_room,
    take_item,
    unlock_edge,
    visit_poi,
)
from tot.gremlins.bone_engine.rest import long_rest, short_rest
from tot.models import (
    Ability,
    Character,
    ExplorationEdge,
    ExplorationMap,
    ExplorationState,
    Skill,
)

if TYPE_CHECKING:
    from textual.widgets import RichLog


class ExplorePhase(StrEnum):
    """探索選單階段。"""

    MAIN = "main"
    MOVE_SELECT = "move_select"
    DOOR_ACTION = "door_action"
    CHARACTER_SELECT = "char_select"
    POI_SELECT = "poi_select"
    REST_SELECT = "rest_select"
    TAKE_SELECT = "take_select"
    LOCKED = "locked"


class ExploreInputHandler:
    """探索指令處理器。"""

    def __init__(self) -> None:
        self.phase: ExplorePhase = ExplorePhase.MAIN
        self.menu_options: list = []
        # 暫存狀態
        self._pending_edge: ExplorationEdge | None = None
        self._pending_action: str = ""  # "lockpick" | "force" | "search" | "jump"
        self._collected_keys: set[str] = set()
        self.noise_alert: bool = False

    # -----------------------------------------------------------------
    # 主選單
    # -----------------------------------------------------------------

    def show_main_menu(self, log: RichLog) -> None:
        """顯示主選單。"""
        self.phase = ExplorePhase.MAIN
        log.write(
            "\n[bold white]可用指令：[/]\n"
            "  [cyan]1.[/] 查看（look）\n"
            "  [cyan]2.[/] 移動（move）\n"
            "  [cyan]3.[/] 搜索（search）\n"
            "  [cyan]4.[/] 拿取（take）\n"
            "  [cyan]5.[/] 互動（interact）\n"
            "  [cyan]6.[/] 休息（rest）\n"
            "  [cyan]7.[/] 隊伍狀態（status）\n"
            "  [cyan]8.[/] 地圖（map）\n"
            "  [cyan]9.[/] 說明（help）\n"
            "  [cyan]0.[/] 離開（quit）"
        )
        self.menu_options = [
            "look",
            "move",
            "search",
            "take",
            "interact",
            "rest",
            "status",
            "map",
            "help",
            "quit",
        ]

    # -----------------------------------------------------------------
    # 指令分派
    # -----------------------------------------------------------------

    def handle_command(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """處理指令。回傳 True 表示要退出。"""
        cmd_lower = cmd.lower().strip()

        # 數字選單
        if cmd.isdigit():
            num = int(cmd)
            return self._handle_number(num, characters, exp_map, state, log, refresh_fn)

        # Phase 分派
        if self.phase == ExplorePhase.MAIN:
            return self._handle_main(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.MOVE_SELECT:
            return self._handle_move_select(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.DOOR_ACTION:
            return self._handle_door_action(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.CHARACTER_SELECT:
            return self._handle_char_select(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.POI_SELECT:
            return self._handle_poi_select(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.REST_SELECT:
            return self._handle_rest_select(cmd_lower, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.TAKE_SELECT:
            return self._handle_take_select(cmd_lower, characters, exp_map, state, log, refresh_fn)

        log.write("[yellow]目前無法處理指令。[/]")
        return False

    def _handle_number(
        self,
        num: int,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """處理數字輸入。"""
        if self.phase == ExplorePhase.MAIN:
            cmd_map = {
                1: "look",
                2: "move",
                3: "search",
                4: "take",
                5: "interact",
                6: "rest",
                7: "status",
                8: "map",
                9: "help",
                0: "quit",
            }
            cmd = cmd_map.get(num)
            if cmd:
                return self._handle_main(cmd, characters, exp_map, state, log, refresh_fn)
            log.write(f"[red]無效選項：{num}[/]")
            return False

        # 其他 phase 用數字選擇選單
        if num == 0:
            self.show_main_menu(log)
            return False

        if num < 1 or num > len(self.menu_options):
            log.write(f"[red]無效選項：{num}[/]")
            return False

        option = self.menu_options[num - 1]

        if self.phase == ExplorePhase.MOVE_SELECT:
            return self._do_move(option, characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.DOOR_ACTION:
            return self._handle_door_action(str(num), characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.CHARACTER_SELECT:
            return self._handle_char_select(str(num), characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.POI_SELECT:
            return self._handle_poi_select(str(num), characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.REST_SELECT:
            return self._handle_rest_select(str(num), characters, exp_map, state, log, refresh_fn)
        if self.phase == ExplorePhase.TAKE_SELECT:
            return self._handle_take_select(str(num), characters, exp_map, state, log, refresh_fn)

        return False

    # -----------------------------------------------------------------
    # 主選單指令
    # -----------------------------------------------------------------

    def _handle_main(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "quit":
            return True
        if cmd == "look":
            self._do_look(exp_map, state, log)
        elif cmd == "move":
            self._show_move_menu(exp_map, state, log)
        elif cmd == "search":
            self._show_char_select(characters, log, action="search")
        elif cmd == "take":
            self._show_take_menu(exp_map, state, log)
        elif cmd == "interact":
            self._show_poi_menu(exp_map, state, log)
        elif cmd == "rest":
            self._show_rest_menu(log)
        elif cmd == "status":
            self._do_status(characters, log)
        elif cmd == "map":
            refresh_fn()
            log.write("[dim]地圖已重新渲染。[/]")
        elif cmd == "help":
            self._do_help(log)
        else:
            log.write(f"[red]未知指令：{cmd}[/] — 輸入 help 或 9 查看說明")
        return False

    # -----------------------------------------------------------------
    # look
    # -----------------------------------------------------------------

    def _do_look(
        self,
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        desc = get_node_description(state, exp_map, state.current_node_id)
        node = desc.node

        log.write(f"\n[bold white]📍 {node.name}[/]")
        if node.description:
            log.write(f"[italic]{node.description}[/]")
        if node.ambient:
            log.write(f"[dim italic]{node.ambient}[/]")

        # 可見物品
        items = get_visible_items(exp_map, state.current_node_id)
        if items:
            log.write("\n[bold white]可見物品：[/]")
            for item in items:
                taken = " [dim](已拿取)[/]" if item.is_taken else ""
                log.write(f"  • {item.name}{taken}")
                if item.description:
                    log.write(f"    [dim]{item.description}[/]")

        # NPC
        if node.npcs:
            log.write(f"\n[yellow]⚠ 此處有 NPC：{', '.join(node.npcs)}[/]")

        # 出口
        exits = desc.available_exits
        if exits:
            log.write("\n[bold white]出口：[/]")
            for edge in exits:
                target_name = self._edge_target_name(edge, state, exp_map)
                lock = " 🔒" if edge.is_locked else ""
                log.write(f"  → {edge.name or edge.id}{lock} — {target_name}")

        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # move
    # -----------------------------------------------------------------

    def _show_move_menu(
        self,
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        exits = get_available_exits(state, exp_map)
        if not exits:
            log.write("[yellow]沒有可走的出口。[/]")
            self.show_main_menu(log)
            return

        self.menu_options = exits
        self.phase = ExplorePhase.MOVE_SELECT

        log.write("\n[bold white]選擇出口：[/]")
        for i, edge in enumerate(exits, 1):
            target_name = self._edge_target_name(edge, state, exp_map)
            lock = " 🔒" if edge.is_locked else ""
            time_str = ""
            if edge.distance_minutes > 0:
                time_str = f" ({edge.distance_minutes} 分鐘)"
            elif edge.distance_days > 0:
                time_str = f" ({edge.distance_days} 天)"
            log.write(f"  [cyan]{i}.[/] {edge.name or edge.id}{lock} → {target_name}{time_str}")
        log.write("  [dim]0. ← 返回[/]")

    def _handle_move_select(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False
        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                return self._do_move(
                    self.menu_options[idx], characters, exp_map, state, log, refresh_fn
                )
        log.write("[red]請選擇有效的出口編號，或 0 返回。[/]")
        return False

    def _do_move(
        self,
        edge: ExplorationEdge,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        # 上鎖→進入門互動
        if edge.is_locked:
            self._pending_edge = edge
            self._show_door_menu(edge, log)
            return False

        # 跳躍→角色選擇
        if edge.requires_jump:
            self._pending_edge = edge
            self._show_jump_info(edge, log)
            self._show_char_select(characters, log, action="jump")
            return False

        result = move_to_node(state, exp_map, edge.id)
        if result.success:
            log.write(f"\n[green]{result.message}[/]")
            log.write(f"[dim]（{format_time(result.elapsed_seconds)}）[/]")

            # 進入新節點：自動被動感知 + 描述
            self._on_enter_node(characters, exp_map, state, log)
            refresh_fn()
        else:
            log.write(f"[red]{result.message}[/]")

        self.show_main_menu(log)
        return False

    def _on_enter_node(
        self,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        """進入新節點時觸發被動感知 + 顯示描述。"""
        node_id = state.current_node_id
        best_pp = best_passive_perception(characters)

        # 被動感知自動發現隱藏通道
        found_edges = auto_passive_perception(state, exp_map, node_id, best_pp)
        for edge in found_edges:
            log.write(f"[magenta]👁 被動感知發現了隱藏通道：{edge.name or edge.id}[/]")

        # 顯示節點描述
        self._do_look(exp_map, state, log)

    # -----------------------------------------------------------------
    # door
    # -----------------------------------------------------------------

    def _show_door_menu(self, edge: ExplorationEdge, log: RichLog) -> None:
        self.phase = ExplorePhase.DOOR_ACTION
        options = []

        # 鑰匙選項
        if edge.key_item and edge.key_item in self._collected_keys:
            options.append("key")
            log.write(f"\n[bold white]「{edge.name}」上鎖了（DC {edge.lock_dc}）[/]")
            log.write("  [cyan]1.[/] 用鑰匙開門")
        else:
            log.write(f"\n[bold white]「{edge.name}」上鎖了（DC {edge.lock_dc}）[/]")

        options.append("lockpick")
        log.write(f"  [cyan]{len(options)}.[/] 開鎖（Sleight of Hand）")

        if edge.break_dc > 0:
            options.append("force")
            log.write(f"  [cyan]{len(options)}.[/] 破門（STR, DC {edge.break_dc}）")

        options.append("back")
        log.write("  [dim]0. ← 返回[/]")

        self.menu_options = options

    def _handle_door_action(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                action = self.menu_options[idx]
                if action == "back":
                    self.show_main_menu(log)
                    return False
                if action == "key":
                    return self._do_key_unlock(characters, exp_map, state, log, refresh_fn)
                self._pending_action = action
                self._show_char_select(characters, log, action=action)
                return False

        log.write("[red]請選擇有效選項。[/]")
        return False

    def _do_key_unlock(
        self,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        edge = self._pending_edge
        if not edge:
            return False
        result = unlock_edge(state, exp_map, edge.id, key_item_id=edge.key_item)
        log.write(f"[green]{result.message}[/]")
        if result.success:
            # 門開了，自動移動
            return self._do_move(edge, characters, exp_map, state, log, refresh_fn)
        self.show_main_menu(log)
        return False

    # -----------------------------------------------------------------
    # jump
    # -----------------------------------------------------------------

    def _show_jump_info(self, edge: ExplorationEdge, log: RichLog) -> None:
        """顯示跳躍路徑資訊。"""
        height = abs(edge.elevation_change_m)
        if edge.elevation_change_m > 0:
            direction = "↑ 上升"
        elif edge.elevation_change_m < 0:
            direction = "↓ 下降"
        else:
            direction = ""
        height_str = f"  高度差：{direction} {height}m" if edge.elevation_change_m != 0 else ""

        log.write(f"\n[bold yellow]⚡ 「{edge.name or edge.id}」需要跳躍！[/]")
        log.write(f"  Athletics DC {edge.jump_dc}{height_str}")

        if edge.fall_damage_on_fail:
            from tot.gremlins.bone_engine.exploration import calculate_fall_damage_dice

            dice = calculate_fall_damage_dice(height)
            log.write(f"  [red]失敗後果：墜落 {dice} 傷害（仍到達目的地）[/]")
        else:
            log.write("  [dim]失敗後果：原地不動（無傷害）[/]")

    def _do_jump(
        self,
        char: Character,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """執行跳躍檢定。"""
        edge = self._pending_edge
        if not edge:
            return False

        check = skill_check(char, Skill.ATHLETICS, dc=edge.jump_dc)
        log.write(
            f"\n[white]{char.name} 嘗試跳躍...[/]"
            f"\n  Athletics 檢定：🎲 {check.natural} + "
            f"{check.total - check.natural} = {check.total} vs DC {check.dc}"
        )

        result = attempt_jump(state, exp_map, edge.id, char, check.total)

        if result.success:
            log.write(f"[green]✅ {result.message}[/]")
            log.write(f"[dim]（{format_time(result.elapsed_seconds)}）[/]")
            self._on_enter_node(characters, exp_map, state, log)
            refresh_fn()
        elif result.fall_damage_total > 0:
            # 墜落受傷但仍到達
            log.write(f"[red]❌ {result.message}[/]")
            char.hp_current = max(0, char.hp_current - result.fall_damage_total)
            log.write(
                f"[red]💥 {char.name} HP: {char.hp_current + result.fall_damage_total}"
                f" → {char.hp_current}[/]"
            )
            log.write(f"[dim]（{format_time(result.elapsed_seconds)}）[/]")
            self._on_enter_node(characters, exp_map, state, log)
            refresh_fn()
        elif result.node is not None and result.fall_damage_dice:
            # fall_damage_on_fail=True 但骰到 0（理論上不會）
            log.write(f"[yellow]❌ {result.message}[/]")
            self._on_enter_node(characters, exp_map, state, log)
            refresh_fn()
        else:
            # 失敗，原地不動
            log.write(f"[yellow]❌ {result.message}[/]")

        self.show_main_menu(log)
        return False

    # -----------------------------------------------------------------
    # character select
    # -----------------------------------------------------------------

    def _show_char_select(
        self,
        characters: list[Character],
        log: RichLog,
        action: str = "",
    ) -> None:
        self.phase = ExplorePhase.CHARACTER_SELECT
        self._pending_action = action

        skill_label = {
            "lockpick": "Sleight of Hand",
            "force": "STR",
            "search": "Investigation",
            "jump": "Athletics",
        }.get(action, "???")

        log.write(f"\n[bold white]選擇誰來做 {skill_label} 檢定：[/]")
        self.menu_options = characters
        for i, char in enumerate(characters, 1):
            bonus = self._get_action_bonus(char, action)
            log.write(f"  [cyan]{i}.[/] {char.name} ({skill_label} {bonus:+d})")
        log.write("  [dim]0. ← 返回[/]")

    def _get_action_bonus(self, char: Character, action: str) -> int:
        if action == "lockpick":
            return char.skill_bonus(Skill.SLEIGHT_OF_HAND)
        if action == "force":
            return char.ability_modifier(Ability.STR)
        if action == "search":
            return char.skill_bonus(Skill.INVESTIGATION)
        if action == "jump":
            return char.skill_bonus(Skill.ATHLETICS)
        return 0

    def _handle_char_select(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                char = self.menu_options[idx]
                action = self._pending_action

                if action == "lockpick":
                    return self._do_lockpick(char, characters, exp_map, state, log, refresh_fn)
                if action == "force":
                    return self._do_force(char, characters, exp_map, state, log, refresh_fn)
                if action == "jump":
                    return self._do_jump(char, characters, exp_map, state, log, refresh_fn)
                if action == "search":
                    self._do_search(char, exp_map, state, log, refresh_fn)
                    return False

        log.write("[red]請選擇有效角色。[/]")
        return False

    # -----------------------------------------------------------------
    # lockpick / force
    # -----------------------------------------------------------------

    def _do_lockpick(
        self,
        char: Character,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        edge = self._pending_edge
        if not edge:
            return False
        check = skill_check(char, Skill.SLEIGHT_OF_HAND, dc=edge.lock_dc)
        log.write(
            f"\n[white]{char.name} 嘗試開鎖...[/]"
            f"\n  {check.label}：🎲 {check.natural} + {check.total - check.natural}"
            f" = {check.total} vs DC {check.dc}"
        )
        result = unlock_edge(state, exp_map, edge.id, check_total=check.total)
        if result.success:
            log.write(f"[green]✅ {result.message}[/]")
            return self._do_move(edge, characters, exp_map, state, log, refresh_fn)
        log.write(f"[red]❌ {result.message}[/]")
        self.show_main_menu(log)
        return False

    def _do_force(
        self,
        char: Character,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        edge = self._pending_edge
        if not edge:
            return False
        check = ability_check(char, Ability.STR, dc=edge.break_dc)
        log.write(
            f"\n[white]{char.name} 嘗試破門...[/]"
            f"\n  {check.label}：🎲 {check.natural} + {check.total - check.natural}"
            f" = {check.total} vs DC {check.dc}"
        )
        result = force_open_edge(state, exp_map, edge.id, check.total)
        if result.noise_generated:
            self.noise_alert = True
            log.write("[yellow]💥 巨響！噪音可能驚動了附近的敵人。[/]")
        if result.success:
            log.write(f"[green]✅ {result.message}[/]")
            return self._do_move(edge, characters, exp_map, state, log, refresh_fn)
        log.write(f"[red]❌ {result.message}[/]")
        self.show_main_menu(log)
        return False

    # -----------------------------------------------------------------
    # search
    # -----------------------------------------------------------------

    def _do_search(
        self,
        char: Character,
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> None:
        node_id = state.current_node_id
        check = skill_check(char, Skill.INVESTIGATION, dc=0)
        log.write(
            f"\n[white]{char.name} 仔細搜索房間...[/]"
            f"\n  Investigation 檢定：🎲 {check.natural} + "
            f"{check.total - check.natural} = {check.total}"
        )

        # 搜索隱藏通道
        room_result = search_room(state, exp_map, node_id, check.total)
        log.write(f"[dim]（{format_time(room_result.elapsed_seconds)}）[/]")

        if room_result.discovered_edges:
            for eid in room_result.discovered_edges:
                for e in exp_map.edges:
                    if e.id == eid:
                        log.write(f"[magenta]🔍 發現隱藏通道：{e.name or e.id}[/]")

        # 搜索隱藏物品
        found_items = search_items(exp_map, node_id, check.total)
        if found_items:
            for item in found_items:
                if item.item_type == "clue":
                    log.write(f"[cyan]📜 發現線索：{item.name}[/]")
                    if item.description:
                        log.write(f"  [dim]{item.description}[/]")
                else:
                    log.write(f"[green]🔍 發現物品：{item.name}[/]")
                    if item.description:
                        log.write(f"  [dim]{item.description}[/]")

        if not room_result.discovered_edges and not found_items:
            log.write("[dim]沒有發現任何東西。[/]")

        refresh_fn()
        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # take
    # -----------------------------------------------------------------

    def _show_take_menu(
        self,
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        items = get_visible_items(exp_map, state.current_node_id)
        takeable = [it for it in items if not it.is_taken]

        if not takeable:
            log.write("[yellow]沒有可拿取的物品。[/]")
            self.show_main_menu(log)
            return

        self.phase = ExplorePhase.TAKE_SELECT
        self.menu_options = takeable

        log.write("\n[bold white]選擇要拿取的物品：[/]")
        for i, item in enumerate(takeable, 1):
            gp_str = f" ({item.value_gp} gp)" if item.value_gp > 0 else ""
            log.write(f"  [cyan]{i}.[/] {item.name}{gp_str}")
        log.write("  [dim]0. ← 返回[/]")

    def _handle_take_select(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                item = self.menu_options[idx]
                taken = take_item(exp_map, state.current_node_id, item.id)
                if taken:
                    log.write(f"[green]✅ 拿取了：{taken.name}[/]")
                    if taken.grants_key:
                        self._collected_keys.add(taken.grants_key)
                        log.write(f"[cyan]🔑 獲得鑰匙！（{taken.grants_key}）[/]")
                    if taken.value_gp > 0:
                        log.write(f"[yellow]💰 價值 {taken.value_gp} gp[/]")
                else:
                    log.write("[red]無法拿取此物品。[/]")
                self.show_main_menu(log)
                return False

        log.write("[red]請選擇有效物品。[/]")
        return False

    # -----------------------------------------------------------------
    # interact (POI)
    # -----------------------------------------------------------------

    def _show_poi_menu(
        self,
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        pois = list_pois(exp_map, state.current_node_id)
        if not pois:
            log.write("[yellow]此處沒有可互動的場所。[/]")
            self.show_main_menu(log)
            return

        self.phase = ExplorePhase.POI_SELECT
        self.menu_options = pois

        log.write("\n[bold white]選擇要造訪的場所：[/]")
        for i, poi in enumerate(pois, 1):
            npc_str = ""
            if poi.npcs:
                npc_str = f" [dim]({', '.join(poi.npcs)})[/]"
            log.write(f"  [cyan]{i}.[/] {poi.name}{npc_str}")
        log.write("  [dim]0. ← 返回[/]")

    def _handle_poi_select(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                poi = self.menu_options[idx]
                desc = visit_poi(state, exp_map, state.current_node_id, poi.id)
                log.write(f"\n[bold white]📍 {desc.node.name}[/]")
                if desc.node.description:
                    log.write(f"[italic]{desc.node.description}[/]")
                if desc.node.ambient:
                    log.write(f"[dim italic]{desc.node.ambient}[/]")
                if desc.node.npcs:
                    log.write(f"[yellow]此處有 NPC：{', '.join(desc.node.npcs)}[/]")
                self.show_main_menu(log)
                return False

        log.write("[red]請選擇有效場所。[/]")
        return False

    # -----------------------------------------------------------------
    # rest
    # -----------------------------------------------------------------

    def _show_rest_menu(self, log: RichLog) -> None:
        self.phase = ExplorePhase.REST_SELECT
        self.menu_options = ["short", "long"]
        log.write(
            "\n[bold white]選擇休息類型：[/]\n"
            "  [cyan]1.[/] 短休（1 小時 — 消耗 Hit Dice 回復 HP）\n"
            "  [cyan]2.[/] 長休（8 小時 — HP 全滿 + 法術恢復）\n"
            "  [dim]0. ← 返回[/]"
        )

    def _handle_rest_select(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd in ("1", "short"):
            result = short_rest(characters)
            state.game_clock.add_event(result.elapsed_seconds)
            log.write(f"\n[cyan]💤 {result.message}[/]")
            log.write(f"[dim]（{format_time(result.elapsed_seconds)}）[/]")
            refresh_fn()
            self.show_main_menu(log)
            return False

        if cmd in ("2", "long"):
            result = long_rest(characters)
            state.game_clock.add_event(result.elapsed_seconds)
            log.write(f"\n[cyan]🌙 {result.message}[/]")
            log.write(f"[dim]（{format_time(result.elapsed_seconds)}）[/]")
            refresh_fn()
            self.show_main_menu(log)
            return False

        log.write("[red]請選擇 1（短休）或 2（長休），或 0 返回。[/]")
        return False

    # -----------------------------------------------------------------
    # status
    # -----------------------------------------------------------------

    def _do_status(self, characters: list[Character], log: RichLog) -> None:
        log.write("\n[bold white]隊伍狀態：[/]")
        for char in characters:
            hp_str = f"{char.hp_current}/{char.hp_max}"
            hd_str = f"HD {char.hit_dice_remaining}/{char.hit_dice_total}"
            slot_parts = []
            for lvl in sorted(char.spell_slots.max_slots):
                cur = char.spell_slots.current_slots.get(lvl, 0)
                mx = char.spell_slots.max_slots[lvl]
                slot_parts.append(f"{lvl}環:{cur}/{mx}")
            slot_str = f"  {'  '.join(slot_parts)}" if slot_parts else ""

            log.write(
                f"  [bold]{char.name}[/] ({char.char_class} Lv{char.level})"
                f"  AC {char.ac}  HP {hp_str}  {hd_str}{slot_str}"
            )
        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # help
    # -----------------------------------------------------------------

    def _do_help(self, log: RichLog) -> None:
        log.write(
            "\n[bold white]指令說明：[/]\n"
            "  [cyan]look[/]     — 查看目前位置的描述和可見物品\n"
            "  [cyan]move[/]     — 選擇出口移動到相鄰節點\n"
            "  [cyan]search[/]   — 搜索隱藏通道和物品（選角色做檢定）\n"
            "  [cyan]take[/]     — 拿取已發現的物品\n"
            "  [cyan]interact[/] — 造訪城鎮 POI / NPC\n"
            "  [cyan]rest[/]     — 短休或長休回復 HP\n"
            "  [cyan]status[/]   — 查看隊伍狀態\n"
            "  [cyan]map[/]      — 重新渲染地圖\n"
            "  [cyan]help[/]     — 顯示此說明\n"
            "  [cyan]quit[/]     — 離開探索\n"
            "\n"
            "  也可以輸入數字選擇選單項目。\n"
            "  [dim]切換地圖：load ruins / load dungeon / load town / load wilderness[/]"
        )
        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # 工具
    # -----------------------------------------------------------------

    def _edge_target_name(
        self,
        edge: ExplorationEdge,
        state: ExplorationState,
        exp_map: ExplorationMap,
    ) -> str:
        """取得路徑目標節點名稱。"""
        target_id = edge.to_node_id
        if edge.to_node_id == state.current_node_id:
            target_id = edge.from_node_id
        for node in exp_map.nodes:
            if node.id == target_id:
                return node.name
        return target_id
