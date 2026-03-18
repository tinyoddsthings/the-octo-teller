"""探索 TUI 選單狀態機 + 指令處理。

ExplorePhase 管理目前的互動狀態（主選單/移動選擇/門互動/角色選擇…）。
所有指令最終都呼叫 bone_engine 函式。
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from tot.gremlins.bone_engine.adventure import (
    advance_dialogue,
    check_events,
    execute_event,
    get_available_lines,
    get_available_npcs,
    get_scene_entry_lines,
)
from tot.gremlins.bone_engine.area_explore import (
    check_terrain_at,
    enter_area,
    exit_area,
    explore_move,
    get_nearby_doors,
    get_nearby_props,
    get_party_position,
    reset_movement,
    search_prop,
    take_prop_loot,
    transfer_loot_to_inventory,
    unlock_area_prop,
)
from tot.gremlins.bone_engine.checks import (
    ability_check,
    best_passive_perception,
    skill_check,
)
from tot.gremlins.bone_engine.checks import skill_check as engine_skill_check
from tot.gremlins.bone_engine.dice import RollType, roll
from tot.gremlins.bone_engine.exploration import (
    MapRegistry,
    attempt_jump,
    auto_passive_perception,
    check_sub_map_transition,
    force_open_edge,
    format_time,
    get_available_exits,
    get_node_description,
    get_visible_items,
    list_pois,
    move_to_node,
    resolve_parent_map,
    search_items,
    search_room,
    take_item,
    unlock_edge,
    visit_poi,
)
from tot.gremlins.bone_engine.rest import long_rest, short_rest
from tot.models import (
    Ability,
    AreaExploreState,
    Character,
    ExplorationEdge,
    ExplorationMap,
    ExplorationState,
    Prop,
    Skill,
)
from tot.models.adventure import (
    AdventureScript,
    AdventureState,
    DialogueLine,
    EventAction,
    NpcDef,
    SceneDef,
    SkillCheckDef,
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
    # Area 自由探索模式
    AREA_MAIN = "area_main"
    AREA_SEARCH_PROP = "area_search_prop"
    AREA_SEARCH_CHAR = "area_search_char"
    AREA_TAKE = "area_take"
    AREA_USE_PROP = "area_use_prop"
    AREA_USE_ACTION = "area_use_action"
    AREA_USE_CHAR = "area_use_char"
    # 對話模式
    TALK_SELECT = "talk_select"
    DIALOGUE = "dialogue"
    SKILL_CHECK = "skill_check"


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
        # Area 探索模式
        self.area_state: AreaExploreState | None = None
        self._current_node_has_area: bool = False
        self._pending_search_prop: Prop | None = None
        self._pending_use_prop: Prop | None = None
        # 冒險劇本系統
        self.adventure_script: AdventureScript | None = None
        self.adventure_state: AdventureState | None = None
        # 子地圖管理
        self.registry: MapRegistry | None = None
        self._pending_map_change: ExplorationMap | None = None
        self._pending_talk_npc: NpcDef | None = None
        self._pending_scene: SceneDef | None = None
        self._pending_skill_check: SkillCheckDef | None = None
        self._characters: list[Character] = []
        self._state: ExplorationState | None = None

    # -----------------------------------------------------------------
    # 主選單
    # -----------------------------------------------------------------

    def show_main_menu(self, log: RichLog) -> None:
        """顯示主選單。"""
        self.phase = ExplorePhase.MAIN
        menu_text = (
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
        if self._current_node_has_area:
            menu_text += "\n  [bold magenta]explore[/] — 進入區域探索"
        if self.adventure_script and self.adventure_state:
            menu_text += "\n  [bold yellow]talk[/] — 與 NPC 對話"
        if self._state and self._state.map_stack:
            menu_text += "\n  [bold red]back[/] — 返回上層地圖"
        log.write(menu_text)
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
        self._characters = characters
        self._state = state
        cmd_lower = cmd.lower().strip()

        # Area 模式：所有指令路由到 area handlers
        if self.area_state is not None:
            return self._handle_area_command(
                cmd, cmd_lower, characters, exp_map, state, log, refresh_fn
            )

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
        if self.phase == ExplorePhase.TALK_SELECT:
            return self._handle_talk_select(cmd_lower, state, log, refresh_fn)
        if self.phase == ExplorePhase.DIALOGUE:
            return self._handle_dialogue(cmd_lower, state, log, refresh_fn)
        if self.phase == ExplorePhase.SKILL_CHECK:
            return self._handle_skill_check_input(cmd_lower, characters, state, log, refresh_fn)

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
        if self.phase == ExplorePhase.TALK_SELECT:
            return self._handle_talk_select(str(num), state, log, refresh_fn)
        if self.phase == ExplorePhase.DIALOGUE:
            return self._handle_dialogue(str(num), state, log, refresh_fn)
        if self.phase == ExplorePhase.SKILL_CHECK:
            return self._handle_skill_check_input(str(num), characters, state, log, refresh_fn)

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
        elif cmd == "explore":
            self._enter_area_mode(characters, exp_map, state, log, refresh_fn)
        elif cmd == "talk":
            self._show_talk_menu(state, log)
        elif cmd == "back" and state.map_stack:
            self._handle_exit_sub_map(state, log)
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

            # 進入新節點：自動被動感知 + 描述 + 自動 area
            self._on_enter_node(characters, exp_map, state, log, refresh_fn)
            refresh_fn()
        else:
            log.write(f"[red]{result.message}[/]")

        if self.area_state is None:
            self.show_main_menu(log)
        return False

    def _on_enter_node(
        self,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable | None = None,
    ) -> None:
        """進入新節點時觸發被動感知 + 顯示描述。

        若節點有 combat_map 且提供 refresh_fn，自動進入 area 探索模式。
        """
        node_id = state.current_node_id

        # 檢查此節點是否有 area 地圖
        self._current_node_has_area = False
        for n in exp_map.nodes:
            if n.id == node_id:
                self._current_node_has_area = bool(n.combat_map)
                break
        best_pp = best_passive_perception(characters)

        # 被動感知自動發現隱藏通道
        found_edges = auto_passive_perception(state, exp_map, node_id, best_pp)
        for edge in found_edges:
            log.write(f"[magenta]👁 被動感知發現了隱藏通道：{edge.name or edge.id}[/]")

        # 顯示節點描述
        self._do_look(exp_map, state, log)

        # 冒險劇本事件：enter_node
        self._fire_events("enter_node", state, exp_map, log, refresh_fn, node_id=node_id)

        # 子地圖轉場：節點有 sub_map 時自動進入
        if self.registry is not None:
            sub_map = check_sub_map_transition(state, self.registry, exp_map)
            if sub_map is not None:
                self._pending_map_change = sub_map
                log.write(f"\n[bold green]進入：{sub_map.name}[/]")
                return  # 後續由 app 完成子地圖的 _on_enter_node

        # 自動進入 area 探索模式
        if self._current_node_has_area and refresh_fn:
            self._enter_area_mode(characters, exp_map, state, log, refresh_fn)

    # -----------------------------------------------------------------
    # sub_map 返回上層
    # -----------------------------------------------------------------

    def _handle_exit_sub_map(
        self,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        """返回上層地圖。"""
        if not state.map_stack:
            log.write("[yellow]已在最頂層地圖。[/]")
            return

        if self.registry is None:
            log.write("[red]地圖 registry 未初始化。[/]")
            return

        parent_map = resolve_parent_map(state, self.registry)
        if parent_map is not None:
            self._pending_map_change = parent_map
            log.write(f"\n[bold green]返回：{parent_map.name}[/]")
        else:
            log.write("[red]找不到上層地圖。[/]")

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
            self._on_enter_node(characters, exp_map, state, log, refresh_fn)
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
            self._on_enter_node(characters, exp_map, state, log, refresh_fn)
            refresh_fn()
        elif result.node is not None and result.fall_damage_dice:
            # fall_damage_on_fail=True 但骰到 0（理論上不會）
            log.write(f"[yellow]❌ {result.message}[/]")
            self._on_enter_node(characters, exp_map, state, log, refresh_fn)
            refresh_fn()
        else:
            # 失敗，原地不動
            log.write(f"[yellow]❌ {result.message}[/]")

        if self.area_state is None:
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
                    # 冒險劇本事件：take_item
                    self._fire_events(
                        "take_item",
                        state,
                        exp_map,
                        log,
                        refresh_fn,
                        item_id=taken.id,
                    )
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
            "  [cyan]talk[/]     — 與 NPC 對話（劇本模式可用）\n"
            "  [cyan]explore[/]  — 進入區域探索（僅在有地圖的節點可用）\n"
            "  [cyan]help[/]     — 顯示此說明\n"
            "  [cyan]quit[/]     — 離開探索\n"
            "\n"
            "  也可以輸入數字選擇選單項目。\n"
            "  [dim]切換地圖：load ruins / load dungeon / load town / load wilderness[/]"
        )
        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # 冒險劇本：事件鉤子 + 對話
    # -----------------------------------------------------------------

    def _fire_events(
        self,
        trigger_type: str,
        state: ExplorationState,
        exp_map: ExplorationMap,
        log: RichLog,
        refresh_fn: Callable | None = None,
        **kwargs: str,
    ) -> None:
        """觸發冒險劇本事件並處理 action。"""
        if not self.adventure_script or not self.adventure_state:
            return

        elapsed = state.elapsed_minutes
        matched = check_events(
            self.adventure_script,
            self.adventure_state,
            trigger_type,
            elapsed,
            **kwargs,
        )

        for event in matched:
            self.adventure_state, actions = execute_event(self.adventure_state, event, elapsed)
            self._process_event_actions(actions, state, exp_map, log, refresh_fn)

    def _process_event_actions(
        self,
        actions: list[EventAction],
        state: ExplorationState,
        exp_map: ExplorationMap,
        log: RichLog,
        refresh_fn: Callable | None = None,
    ) -> None:
        """處理事件 action 列表中的呈現類 action。"""
        for action in actions:
            if action.type == "narrate":
                log.write(f"\n[italic]{action.text}[/]")
            elif action.type == "tutorial":
                log.write(f"\n[bold cyan]📖 {action.text}[/]")
            elif action.type == "reveal_node":
                state.discovered_nodes.add(action.node_id)
                # 找節點名稱
                node_name = action.node_id
                for n in exp_map.nodes:
                    if n.id == action.node_id:
                        n.is_discovered = True
                        node_name = n.name
                        break
                log.write(f"[magenta]🗺️ 發現新地點：{node_name}[/]")
            elif action.type == "reveal_edge":
                state.discovered_edges.add(action.edge_id)
                for e in exp_map.edges:
                    if e.id == action.edge_id:
                        e.is_discovered = True
                        break
                if refresh_fn:
                    refresh_fn()
            elif action.type == "add_item":
                # 加到當前節點的物品中
                log.write(f"[green]✨ 獲得物品：{action.item_id}[/]")
            elif action.type == "start_scene":
                self._start_scene(action.scene_id, state, log)

    def _start_scene(
        self,
        scene_id: str,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        """啟動場景對話。"""
        if not self.adventure_script or not self.adventure_state:
            return

        scene = self.adventure_script.scenes.get(scene_id)
        if not scene:
            log.write(f"[red]找不到場景：{scene_id}[/]")
            return

        self._pending_scene = scene
        log.write(f"\n[bold magenta]🎬 {scene.name}[/]")

        lines = get_scene_entry_lines(scene, self.adventure_state, state.elapsed_minutes)
        if not lines:
            log.write("[dim]（場景無對話）[/]")
            self._pending_scene = None
            return

        self._show_dialogue_options(lines, log)

    def _show_talk_menu(
        self,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        """顯示可對話的 NPC 列表。"""
        if not self.adventure_script or not self.adventure_state:
            log.write("[yellow]目前沒有劇本進行中。[/]")
            self.show_main_menu(log)
            return

        npcs = get_available_npcs(
            self.adventure_script,
            self.adventure_state,
            state.current_node_id,
        )
        if not npcs:
            log.write("[yellow]此處沒有可對話的 NPC。[/]")
            self.show_main_menu(log)
            return

        if len(npcs) == 1:
            # 只有一個 NPC，直接開始對話
            self._start_dialogue(npcs[0], state, log)
            return

        self.phase = ExplorePhase.TALK_SELECT
        self.menu_options = npcs
        log.write("\n[bold white]選擇要對話的 NPC：[/]")
        for i, npc in enumerate(npcs, 1):
            log.write(f"  [cyan]{i}.[/] {npc.name}")
        log.write("  [dim]0. ← 返回[/]")

    def _handle_talk_select(
        self,
        cmd: str,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """處理 NPC 選擇。"""
        if cmd == "0":
            self.show_main_menu(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                npc = self.menu_options[idx]
                self._start_dialogue(npc, state, log)
                return False

        log.write("[red]請選擇有效的 NPC 編號。[/]")
        return False

    def _start_dialogue(
        self,
        npc: NpcDef,
        state: ExplorationState,
        log: RichLog,
    ) -> None:
        """開始與 NPC 對話。"""
        self._pending_talk_npc = npc
        log.write(f"\n[bold yellow]💬 與{npc.name}對話[/]")
        if npc.description:
            log.write(f"[dim italic]{npc.description}[/]")

        lines = get_available_lines(npc, self.adventure_state, state.elapsed_minutes)
        if not lines:
            log.write(f"[dim]{npc.name}沒有什麼想說的。[/]")
            self._pending_talk_npc = None
            self.show_main_menu(log)
            return

        self._show_dialogue_options(lines, log)

    def _show_dialogue_options(
        self,
        lines: list[DialogueLine],
        log: RichLog,
    ) -> None:
        """顯示對話選項。"""
        self.phase = ExplorePhase.DIALOGUE
        self.menu_options = lines

        if len(lines) == 1 and not lines[0].choice_label:
            # 沒有選擇，直接顯示（自動推進）
            self._display_and_advance(lines[0], log)
            return

        for i, line in enumerate(lines, 1):
            label = line.choice_label or line.text[:40]
            log.write(f"  [cyan]{i}.[/] {label}")
        log.write("  [dim]0. ← 結束對話[/]")

    def _handle_dialogue(
        self,
        cmd: str,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """處理對話選擇。"""
        if cmd == "0":
            self._end_dialogue(log)
            return False

        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(self.menu_options):
                line = self.menu_options[idx]
                self._display_and_advance(line, log)
                return False

        log.write("[red]請選擇有效的選項。[/]")
        return False

    def _display_and_advance(
        self,
        line: DialogueLine,
        log: RichLog,
    ) -> None:
        """顯示對話行並推進。"""
        npc = self._pending_talk_npc
        scene = self._pending_scene
        if not self.adventure_state:
            return
        if not npc and not scene:
            return

        self.adventure_state, chosen, next_lines = advance_dialogue(
            self.adventure_state,
            npc=npc,
            line_id=line.id,
            script=self.adventure_script,
            scene=scene,
        )

        # silent 節點不顯示文字（advance_dialogue 已自動推進）
        if not chosen.silent:
            if chosen.speaker == "dm":
                log.write(f"\n[italic]{chosen.text}[/]")
            else:
                speaker_name = self._resolve_speaker_name(chosen.speaker)
                log.write(f"\n[bold yellow]{speaker_name}[/]：{chosen.text}")

        # 技能檢定分支
        if chosen.skill_check:
            self._show_skill_check(chosen.skill_check, log)
            return

        if not next_lines:
            self._end_dialogue(log)
            return

        self._show_dialogue_options(next_lines, log)

    # -----------------------------------------------------------------
    # 技能檢定 UI
    # -----------------------------------------------------------------

    _SKILL_ZH: dict[str, str] = {
        "Perception": "察覺",
        "Nature": "自然",
        "Survival": "生存",
        "Animal Handling": "馴獸",
        "Investigation": "調查",
        "Insight": "洞察",
        "Athletics": "運動",
        "Acrobatics": "特技",
        "Stealth": "隱匿",
        "Arcana": "奧秘",
        "History": "歷史",
        "Religion": "宗教",
        "Medicine": "醫療",
        "Deception": "欺瞞",
        "Intimidation": "威嚇",
        "Performance": "表演",
        "Persuasion": "說服",
        "Sleight of Hand": "巧手",
    }

    def _show_skill_check(self, sc: SkillCheckDef, log: RichLog) -> None:
        """顯示技能檢定提示，等待玩家確認擲骰。"""
        self._pending_skill_check = sc
        self._accepted_assists: list[int] = []  # 玩家接受的輔助索引
        self.phase = ExplorePhase.SKILL_CHECK

        skill_name = self._SKILL_ZH.get(sc.skill, sc.skill)

        # 取主角的技能加值
        bonus_str = ""
        if self._characters:
            char = self._characters[0]
            try:
                skill_enum = Skill(sc.skill)
                bonus = char.skill_bonus(skill_enum)
                bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
            except ValueError:
                pass

        log.write("")
        log.write("[bold magenta]═══ 技能檢定 ═══[/]")
        log.write(f"  技能：[bold]{skill_name}[/]（{sc.skill}）")
        if bonus_str:
            log.write(f"  你的加值：[bold cyan]{bonus_str}[/]")
        if not sc.hidden_dc:
            log.write(f"  難度：[bold]DC {sc.dc}[/]")
        else:
            log.write("  難度：[dim]???（暗骰）[/]")

        # 顯示可用輔助
        if sc.assists:
            log.write("")
            log.write("  [dim]可用輔助：[/]")
            for idx, assist in enumerate(sc.assists):
                npc_name = self._resolve_speaker_name(assist.source_npc)
                effect = f"+{assist.bonus_die}" if assist.bonus_die else "優勢"
                conc = " [yellow]⚠️專注[/]" if assist.requires_concentration else ""
                log.write(
                    f"  [cyan]{idx + 2}.[/] ✨ {assist.name}（來自{npc_name}）— {effect}{conc}"
                )

        log.write("[bold magenta]════════════════[/]")
        log.write("")
        log.write("[cyan]1.[/] 🎲 擲骰！")

    def _handle_skill_check_input(
        self,
        cmd: str,
        characters: list[Character],
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """處理技能檢定擲骰或輔助選擇。"""
        sc = self._pending_skill_check
        if not sc:
            return False

        if not cmd.isdigit():
            return False
        choice = int(cmd)

        # 選擇輔助法術（2, 3, ...）
        if choice >= 2 and sc.assists:
            assist_idx = choice - 2
            if assist_idx < len(sc.assists):
                assist = sc.assists[assist_idx]
                if assist_idx in self._accepted_assists:
                    log.write(f"  [dim]（已接受 {assist.name}）[/]")
                    return False
                self._accepted_assists.append(assist_idx)
                npc_name = self._resolve_speaker_name(assist.source_npc)
                log.write(f"  ✨ {npc_name}為你施放了{assist.name}！")
                if assist.requires_concentration:
                    log.write(f"  [dim]（{npc_name}開始專注）[/]")
                log.write("")
                log.write("[cyan]1.[/] 🎲 擲骰！")
                return False

        # 擲骰（1）
        if choice != 1:
            return False

        self._pending_skill_check = None

        if not characters:
            log.write("[red]沒有可用的角色！[/]")
            self._end_dialogue(log)
            return False

        char = characters[0]

        try:
            skill_enum = Skill(sc.skill)
        except ValueError:
            log.write(f"[red]未知技能：{sc.skill}[/]")
            self._end_dialogue(log)
            return False

        # 判斷是否有優勢
        has_advantage = any(sc.assists[i].advantage for i in self._accepted_assists)
        roll_type = RollType.ADVANTAGE if has_advantage else RollType.NORMAL

        # 執行檢定
        result = engine_skill_check(char, skill_enum, sc.dc, roll_type=roll_type)

        # 計算輔助加骰
        assist_bonus = 0
        assist_parts: list[str] = []
        for i in self._accepted_assists:
            assist = sc.assists[i]
            if assist.bonus_die:
                die_result = roll(assist.bonus_die)
                assist_bonus += die_result.total
                assist_parts.append(f"+{assist.bonus_die}({die_result.total})")

        final_total = result.total + assist_bonus
        success = final_total >= sc.dc

        # 顯示結果
        bonus = char.skill_bonus(skill_enum)
        bonus_str = f"{bonus:+d}"

        parts = [f"🎲 d20 = [bold]{result.natural}[/]", bonus_str]
        if has_advantage:
            parts.insert(1, "[dim]（優勢）[/]")
        parts.extend(assist_parts)
        parts.append(f"= [bold]{final_total}[/]")

        log.write(f"  {' '.join(parts)}")

        if success:
            log.write(f"  [bold green]✓ 成功！[/]（DC {sc.dc}）")
        else:
            log.write(f"  [bold red]✗ 失敗[/]（DC {sc.dc}）")

        # 跳轉到對應對話
        target_id = sc.pass_dialogue if success else sc.fail_dialogue
        if target_id:
            dl = self._find_dialogue_line(target_id)
            if dl:
                self._display_and_advance(dl, log)
                return False
        self._end_dialogue(log)
        return False

    def _find_dialogue_line(self, line_id: str) -> DialogueLine | None:
        """在場景、NPC 中查找對話行（支援跨檔案對話鏈）。"""
        # 先查當前場景
        scene = self._pending_scene
        if scene:
            for dl in scene.dialogue:
                if dl.id == line_id:
                    return dl
        # 再查當前對話 NPC
        npc = self._pending_talk_npc
        if npc:
            for dl in npc.dialogue:
                if dl.id == line_id:
                    return dl
        # 再查其他 NPC 和場景
        if self.adventure_script:
            for other in self.adventure_script.npcs.values():
                if npc and other.id == npc.id:
                    continue
                for dl in other.dialogue:
                    if dl.id == line_id:
                        return dl
            for s in self.adventure_script.scenes.values():
                if scene and s.id == scene.id:
                    continue
                for dl in s.dialogue:
                    if dl.id == line_id:
                        return dl
        return None

    def _resolve_speaker_name(self, speaker_id: str) -> str:
        """解析 speaker ID 為顯示名稱（支援跨 NPC 對話）。"""
        npc = self._pending_talk_npc
        if npc and speaker_id == npc.id:
            return npc.name
        if self.adventure_script:
            other = self.adventure_script.npcs.get(speaker_id)
            if other:
                return other.name
        return speaker_id

    def _end_dialogue(self, log: RichLog) -> None:
        """結束對話。"""
        npc = self._pending_talk_npc
        scene = self._pending_scene
        self._pending_talk_npc = None
        self._pending_scene = None

        if scene:
            log.write(f"[dim]（{scene.name}結束）[/]")
        elif npc:
            log.write(f"[dim]（與{npc.name}的對話結束）[/]")

        # 清除 active_dialogue
        if self.adventure_state:
            self.adventure_state.active_dialogue = None

        self.show_main_menu(log)

    # -----------------------------------------------------------------
    # Area 自由探索模式
    # -----------------------------------------------------------------

    def _enter_area_mode(
        self,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> None:
        """進入 area 探索模式。"""
        node_id = state.current_node_id
        area_state = enter_area(exp_map, node_id, characters)
        if area_state is None:
            log.write("[red]此節點無法進入區域探索。[/]")
            self.show_main_menu(log)
            return

        self.area_state = area_state
        pos = get_party_position(area_state)
        manifest = area_state.map_state.manifest
        log.write("\n[bold magenta]🗺️ 進入區域探索模式[/]")
        log.write(f"[dim]地圖：{manifest.name}（{manifest.width}×{manifest.height}m）[/]")
        if pos:
            log.write(f"[dim]起始位置：({pos.x:.1f}, {pos.y:.1f})[/]")
        refresh_fn()
        self._show_area_menu(log)

    def _exit_area_mode(
        self,
        characters: list[Character],
        log: RichLog,
        refresh_fn: Callable,
    ) -> None:
        """離開 area 探索模式。"""
        if self.area_state is None:
            return

        # 同步鑰匙：Area collected_keys → Pointcrawl _collected_keys
        self._collected_keys.update(self.area_state.collected_keys)

        # 轉移物品到角色 inventory
        items = transfer_loot_to_inventory(self.area_state, characters)
        if items:
            log.write("\n[bold green]物品已轉入背包：[/]")
            for item in items:
                log.write(f"  • {item.name} ×{item.quantity}")

        result = exit_area(self.area_state)
        if result.collected_items:
            log.write("\n[bold green]收集的物品：[/]")
            for item in result.collected_items:
                gp = f" ({item.value_gp} gp)" if item.value_gp else ""
                log.write(f"  • {item.name}{gp}")

        self.area_state = None
        log.write("\n[bold magenta]📍 返回 Pointcrawl 模式[/]")
        refresh_fn()
        self.show_main_menu(log)

    def _show_area_menu(self, log: RichLog) -> None:
        """顯示 area 模式主選單。"""
        self.phase = ExplorePhase.AREA_MAIN
        pos = get_party_position(self.area_state)
        pos_str = f"({pos.x:.1f}, {pos.y:.1f})" if pos else "(?)"
        speed_str = f"{self.area_state.speed_remaining:.1f}/{self.area_state.speed_per_turn:.1f}m"
        log.write(f"\n[bold white]Area 探索[/] — {pos_str}  移動力 {speed_str}")
        self.menu_options = [
            "look",
            "move",
            "search",
            "take",
            "use",
            "terrain",
            "reset",
            "map",
            "exit",
        ]

    def _handle_area_command(
        self,
        cmd: str,
        cmd_lower: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """Area 模式指令分派。"""
        # 數字輸入
        if cmd.isdigit():
            num = int(cmd)
            if self.phase == ExplorePhase.AREA_MAIN:
                area_cmd_map = {
                    1: "look",
                    2: "move",
                    3: "search",
                    4: "take",
                    5: "use",
                    6: "terrain",
                    7: "reset",
                    8: "map",
                    0: "exit",
                }
                resolved = area_cmd_map.get(num)
                if resolved:
                    return self._handle_area_main(
                        resolved, characters, exp_map, state, log, refresh_fn
                    )
                log.write(f"[red]無效選項：{num}[/]")
                return False
            # 選擇 phase：0 返回
            if num == 0:
                self._show_area_menu(log)
                return False
            if num < 1 or num > len(self.menu_options):
                log.write(f"[red]無效選項：{num}[/]")
                return False
            option = self.menu_options[num - 1]
            if self.phase == ExplorePhase.AREA_SEARCH_PROP:
                return self._area_do_search_prop(option, characters, log, refresh_fn)
            if self.phase == ExplorePhase.AREA_SEARCH_CHAR:
                return self._area_do_search_exec(option, log, refresh_fn)
            if self.phase == ExplorePhase.AREA_TAKE:
                return self._area_do_take_exec(option, log, refresh_fn)
            if self.phase == ExplorePhase.AREA_USE_PROP:
                return self._area_do_use_prop(option, characters, log, refresh_fn)
            if self.phase == ExplorePhase.AREA_USE_ACTION:
                return self._area_do_use_action(option, characters, exp_map, state, log, refresh_fn)
            if self.phase == ExplorePhase.AREA_USE_CHAR:
                return self._area_do_use_char(option, log, refresh_fn)
            return False

        # 文字輸入
        if self.phase == ExplorePhase.AREA_MAIN:
            return self._handle_area_main(cmd_lower, characters, exp_map, state, log, refresh_fn)

        # 選擇 phase 中的文字輸入
        if cmd_lower in ("0", "back"):
            self._show_area_menu(log)
            return False
        log.write("[red]請輸入有效的編號，或 0 返回。[/]")
        return False

    def _handle_area_main(
        self,
        cmd: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """Area 主選單指令處理。"""
        if cmd == "exit":
            self._exit_area_mode(characters, log, refresh_fn)
            return False
        if cmd == "look":
            self._area_do_look(log)
        elif cmd.startswith("move"):
            self._area_do_move(cmd, log, refresh_fn)
        elif cmd == "search":
            self._area_show_search_prop(characters, log)
        elif cmd == "take":
            self._area_show_take(log)
        elif cmd == "use":
            self._area_show_use_prop(characters, log)
        elif cmd == "terrain":
            self._area_do_terrain(log)
        elif cmd == "reset":
            self._area_do_reset(log)
        elif cmd == "map":
            refresh_fn()
            log.write("[dim]地圖已重新渲染。[/]")
            self._show_area_menu(log)
        elif cmd == "help":
            log.write(
                "\n[bold white]Area 指令說明：[/]\n"
                "  [cyan]WASD[/]    — 方向移動\n"
                "  [cyan]look[/]    — 查看附近物件\n"
                "  [cyan]search[/]  — 搜索隱藏物品\n"
                "  [cyan]take[/]    — 拾取物品\n"
                "  [cyan]use[/]     — 使用（開鎖/互動門）\n"
                "  [cyan]terrain[/] — 查看地形\n"
                "  [cyan]reset[/]   — 重置移動力\n"
                "  [cyan]map[/]     — 重新渲染地圖\n"
                "  [cyan]exit[/]    — 離開區域"
            )
            self._show_area_menu(log)
        else:
            log.write(f"[red]未知指令：{cmd}[/]")
            self._show_area_menu(log)
        return False

    def _area_do_look(self, log: RichLog) -> None:
        """查看附近可互動物件。"""
        from tot.gremlins.bone_engine.area_explore import INTERACT_RADIUS_M

        props = get_nearby_props(self.area_state)
        pos = get_party_position(self.area_state)

        if pos:
            log.write(f"\n[bold white]📍 隊伍位置：({pos.x:.1f}, {pos.y:.1f})[/]")

        terrain = check_terrain_at(self.area_state)
        if terrain.terrain_type:
            log.write(f"[yellow]地形：{terrain.description}[/]")
            if terrain.is_difficult:
                log.write("[yellow]⚠ 困難地形——移動消耗加倍[/]")

        if not props:
            log.write(f"[dim]附近 {INTERACT_RADIUS_M}m 內沒有可互動物件。[/]")
        else:
            log.write(f"\n[bold white]附近物件（{INTERACT_RADIUS_M}m 內）：[/]")
            for prop in props:
                status = ""
                if prop.is_looted:
                    status = " [dim](已拾取)[/]"
                elif prop.is_searched:
                    status = " [dim](已搜索)[/]"
                dist_str = ""
                if pos:
                    from tot.gremlins.bone_engine.spatial import distance as calc_dist
                    from tot.models import Position

                    dist = calc_dist(pos, Position(x=prop.x, y=prop.y))
                    dist_str = f" [{dist:.1f}m]"
                log.write(
                    f"  • {prop.name or prop.id} ({prop.x:.1f}, {prop.y:.1f}){dist_str}{status}"
                )

        self._show_area_menu(log)

    def _area_do_move(
        self,
        cmd: str,
        log: RichLog,
        refresh_fn: Callable,
    ) -> None:
        """移動隊伍到指定座標。"""
        parts = cmd.split()
        if len(parts) < 3:
            log.write("[yellow]用法：move x y（例：move 5.0 3.0）[/]")
            self._show_area_menu(log)
            return
        try:
            tx, ty = float(parts[1]), float(parts[2])
        except ValueError:
            log.write("[red]座標必須是數字。[/]")
            self._show_area_menu(log)
            return

        result = explore_move(self.area_state, tx, ty)
        if result.success:
            log.write(f"[green]移動成功[/] — 剩餘移動力 {result.speed_remaining:.1f}m")
            if result.terrain and result.terrain.terrain_type:
                log.write(f"[yellow]地形：{result.message}[/]")
                if result.terrain.is_difficult:
                    log.write("[yellow]⚠ 困難地形——移動消耗加倍[/]")
            refresh_fn()
        else:
            log.write(f"[red]{result.message or '移動失敗——可能超出移動力或有障礙物'}[/]")
        self._show_area_menu(log)

    def _area_show_search_prop(
        self,
        characters: list[Character],
        log: RichLog,
    ) -> None:
        """顯示附近可搜索的 Prop 清單。"""
        props = get_nearby_props(self.area_state)
        searchable = [p for p in props if not p.is_looted]

        if not searchable:
            log.write("[yellow]附近沒有可搜索的物件。[/]")
            self._show_area_menu(log)
            return

        self.phase = ExplorePhase.AREA_SEARCH_PROP
        self.menu_options = searchable

        log.write("\n[bold white]選擇要搜索的物件：[/]")
        for i, prop in enumerate(searchable, 1):
            status = " [dim](已搜索)[/]" if prop.is_searched else ""
            log.write(f"  [cyan]{i}.[/] {prop.name or prop.id}{status}")
        log.write("  [dim]0. ← 返回[/]")

    def _area_do_search_prop(
        self,
        prop: Prop,
        characters: list[Character],
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """選定 prop 後，顯示角色選擇。"""
        self._pending_search_prop = prop
        self.phase = ExplorePhase.AREA_SEARCH_CHAR
        self.menu_options = characters

        log.write(f"\n[bold white]選擇誰來搜索「{prop.name or prop.id}」：[/]")
        for i, char in enumerate(characters, 1):
            bonus = char.skill_bonus(Skill.INVESTIGATION)
            log.write(f"  [cyan]{i}.[/] {char.name} (Investigation {bonus:+d})")
        log.write("  [dim]0. ← 返回[/]")
        return False

    def _area_do_search_exec(
        self,
        char: Character,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """執行搜索。"""
        prop = self._pending_search_prop
        if not prop or not self.area_state:
            self._show_area_menu(log)
            return False

        result = search_prop(self.area_state, prop.id, char)

        if result.success:
            log.write(f"[green]✅ {result.message}[/]")
            if result.loot_available:
                log.write("[cyan]💰 此物件內有物品可拾取！[/]")
                # 自動進入拿取流程——直接提示拿取剛搜索到的物件
                searched_prop = prop
                self._pending_search_prop = None
                refresh_fn()
                self.phase = ExplorePhase.AREA_TAKE
                self.menu_options = [searched_prop]
                items_str = ", ".join(item.name for item in searched_prop.loot_items)
                log.write("\n[bold white]拾取物品：[/]")
                log.write(f"  [cyan]1.[/] {searched_prop.name or searched_prop.id} — {items_str}")
                log.write("  [dim]0. ← 返回[/]")
                return False
        else:
            log.write(f"[red]❌ {result.message}[/]")

        self._pending_search_prop = None
        refresh_fn()
        self._show_area_menu(log)
        return False

    def _area_show_take(self, log: RichLog) -> None:
        """顯示可拾取的 Prop 清單。"""
        props = get_nearby_props(self.area_state)
        lootable = [p for p in props if p.is_searched and not p.is_looted and p.loot_items]

        if not lootable:
            log.write("[yellow]附近沒有可拾取物品的物件。（需先搜索）[/]")
            self._show_area_menu(log)
            return

        self.phase = ExplorePhase.AREA_TAKE
        self.menu_options = lootable

        log.write("\n[bold white]選擇要拾取物品的物件：[/]")
        for i, prop in enumerate(lootable, 1):
            items_str = ", ".join(item.name for item in prop.loot_items)
            log.write(f"  [cyan]{i}.[/] {prop.name or prop.id} — {items_str}")
        log.write("  [dim]0. ← 返回[/]")

    def _area_do_take_exec(
        self,
        prop: Prop,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """拾取 Prop 內的物品。"""
        if not self.area_state:
            self._show_area_menu(log)
            return False

        items = take_prop_loot(self.area_state, prop.id)
        if items:
            log.write("[green]✅ 拾取了：[/]")
            for item in items:
                gp = f" ({item.value_gp} gp)" if item.value_gp else ""
                log.write(f"  • {item.name}{gp}")
                if item.grants_key:
                    self._collected_keys.add(item.grants_key)
                    log.write(f"[cyan]🔑 獲得鑰匙！（{item.grants_key}）[/]")
        else:
            log.write("[yellow]沒有可拾取的物品。[/]")

        refresh_fn()
        self._show_area_menu(log)
        return False

    # -----------------------------------------------------------------
    # Area use（門互動 / 開鎖）
    # -----------------------------------------------------------------

    def _area_show_use_prop(
        self,
        characters: list[Character],
        log: RichLog,
    ) -> None:
        """顯示附近可互動的門。"""
        if not self.area_state:
            self._show_area_menu(log)
            return

        doors = get_nearby_doors(self.area_state)
        if not doors:
            log.write("[yellow]附近沒有可使用的門或裝置。[/]")
            self._show_area_menu(log)
            return

        self.phase = ExplorePhase.AREA_USE_PROP
        self.menu_options = doors

        log.write("\n[bold white]選擇要使用的物件：[/]")
        for i, door in enumerate(doors, 1):
            lock_str = " [red](上鎖)[/]" if door.is_locked else " [green](未鎖)[/]"
            log.write(f"  [cyan]{i}.[/] {door.name or door.id}{lock_str}")
        log.write("  [dim]0. ← 返回[/]")

    def _area_do_use_prop(
        self,
        prop: Prop,
        characters: list[Character],
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """選定門 Prop 後，顯示動作選單。"""
        if not prop.is_locked:
            log.write(f"[green]「{prop.name or prop.id}」沒有上鎖。[/]")
            self._show_area_menu(log)
            return False

        self._pending_use_prop = prop
        self.phase = ExplorePhase.AREA_USE_ACTION
        options: list[str] = []

        # 檢查是否有鑰匙
        all_keys = self._collected_keys | (
            self.area_state.collected_keys if self.area_state else set()
        )
        if prop.key_item and prop.key_item in all_keys:
            options.append("key")
            log.write(f"\n[bold white]「{prop.name}」上鎖了（DC {prop.lock_dc}）[/]")
            log.write("  [cyan]1.[/] 用鑰匙開門")
        else:
            log.write(f"\n[bold white]「{prop.name}」上鎖了（DC {prop.lock_dc}）[/]")

        options.append("lockpick")
        log.write(f"  [cyan]{len(options)}.[/] 開鎖（Sleight of Hand）")

        options.append("back")
        log.write("  [dim]0. ← 返回[/]")

        self.menu_options = options
        return False

    def _area_do_use_action(
        self,
        action: str,
        characters: list[Character],
        exp_map: ExplorationMap,
        state: ExplorationState,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """動作選擇後的處理。"""
        if action == "back":
            self._show_area_menu(log)
            return False

        prop = self._pending_use_prop
        if not prop or not self.area_state:
            self._show_area_menu(log)
            return False

        if action == "key":
            # 鑰匙直接開鎖
            result = unlock_area_prop(self.area_state, prop.id, key_item_id=prop.key_item)
            if result.success:
                log.write(f"[green]{result.message}[/]")
            else:
                log.write(f"[red]{result.message}[/]")
            self._pending_use_prop = None
            refresh_fn()
            self._show_area_menu(log)
            return False

        if action == "lockpick":
            # 需要選角色
            self._pending_action = "lockpick"
            self.phase = ExplorePhase.AREA_USE_CHAR
            self.menu_options = characters
            log.write(f"\n[bold white]選擇誰來開鎖「{prop.name}」：[/]")
            for i, char in enumerate(characters, 1):
                bonus = char.skill_bonus(Skill.SLEIGHT_OF_HAND)
                log.write(f"  [cyan]{i}.[/] {char.name} (Sleight of Hand {bonus:+d})")
            log.write("  [dim]0. ← 返回[/]")
            return False

        self._show_area_menu(log)
        return False

    def _area_do_use_char(
        self,
        char: Character,
        log: RichLog,
        refresh_fn: Callable,
    ) -> bool:
        """選定角色後執行開鎖。"""
        prop = self._pending_use_prop
        if not prop or not self.area_state:
            self._show_area_menu(log)
            return False

        # 開鎖檢定
        check = skill_check(char, Skill.SLEIGHT_OF_HAND, prop.lock_dc)
        result = unlock_area_prop(self.area_state, prop.id, check_total=check.total)

        if result.success:
            log.write(f"[green]{char.name} 成功撬開了鎖！（{check.total} vs DC {prop.lock_dc}）[/]")
        else:
            log.write(f"[red]{char.name} 開鎖失敗（{check.total} vs DC {prop.lock_dc}）[/]")

        self._pending_use_prop = None
        refresh_fn()
        self._show_area_menu(log)
        return False

    def _area_do_terrain(self, log: RichLog) -> None:
        """查看當前位置的地形資訊。"""
        terrain = check_terrain_at(self.area_state)
        pos = get_party_position(self.area_state)

        if pos:
            log.write(f"\n[bold white]位置：({pos.x:.1f}, {pos.y:.1f})[/]")
        if terrain.terrain_type:
            log.write(f"[yellow]地形：{terrain.description}[/]")
            log.write(f"  類型：{terrain.terrain_type}")
            log.write(f"  海拔：{terrain.elevation_m:.1f}m")
            if terrain.is_difficult:
                log.write("[yellow]⚠ 困難地形——移動消耗加倍[/]")
        else:
            log.write("[dim]此處為普通平地。[/]")

        self._show_area_menu(log)

    def _area_do_reset(self, log: RichLog) -> None:
        """重置移動速度（新回合）。"""
        reset_movement(self.area_state)
        log.write(f"[green]移動力已重置：{self.area_state.speed_per_turn:.1f}m[/]")
        self._show_area_menu(log)

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
