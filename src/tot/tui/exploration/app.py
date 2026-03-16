"""探索 TUI 主應用——Pointcrawl + Area 混合探索介面。

獨立於 CombatTUI，五面板佈局（Pointcrawl 地圖 / Area Tile 地圖 / 狀態 / 紀錄 / 輸入）。
Pointcrawl 模式使用 ASCII 拓樸圖，Area 模式使用 Tile 字元網格 + WASD 即時移動。
純 orchestrator：接收玩家指令 → 轉給 ExploreInputHandler → 更新 Widget。
"""

from __future__ import annotations

import time
from enum import StrEnum

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import Input, RichLog, Static

from tot.gremlins.bone_engine.area_explore import (
    explore_move,
    get_nearby_props,
    get_party_position,
    reset_movement,
)
from tot.models import Character, ExplorationMap, ExplorationState
from tot.tui.exploration.explore_demo import (
    AVAILABLE_MAPS,
    create_exploration_demo,
    load_map,
)
from tot.tui.exploration.explore_input import ExploreInputHandler, ExplorePhase
from tot.tui.exploration.explore_log_manager import ExploreLogManager
from tot.tui.exploration.explore_map_widget import ExploreMapWidget
from tot.tui.exploration.explore_status import ExploreStatusWidget
from tot.tui.render_buffer import RenderBuffer
from tot.tui.tile_canvas import TileMapCanvas

# ---------------------------------------------------------------------------
# WASD 移動常數（ADR-3: 物理速率模型）
# ---------------------------------------------------------------------------

# D&D speed 9m/round(6s) = 1.5 m/s × 0.1s cooldown = 0.15m per key
WASD_STEP_M = 0.15
MOVE_COOLDOWN_S = 0.1  # 100ms 防抖

WASD_DIRECTIONS: dict[str, tuple[float, float]] = {
    "w": (0.0, +WASD_STEP_M),  # 北 (+Y)
    "s": (0.0, -WASD_STEP_M),  # 南 (-Y)
    "a": (-WASD_STEP_M, 0.0),  # 西 (-X)
    "d": (+WASD_STEP_M, 0.0),  # 東 (+X)
}


class InputMode(StrEnum):
    """輸入模式。"""

    TEXT = "text"  # Input widget 可見，傳統指令輸入
    WASD = "wasd"  # Input widget 隱藏，on_key 攔截 WASD


class ExplorationTUI(App):
    """探索 TUI 主應用。"""

    CSS_PATH = "styles.tcss"
    TITLE = "T.O.T. 探索系統"

    def __init__(self, initial_map: str | None = None) -> None:
        super().__init__()
        self._initial_map = initial_map or "ruins"
        self.characters: list[Character] = []
        self.exp_map: ExplorationMap | None = None
        self.state: ExplorationState | None = None
        self._handler = ExploreInputHandler()
        self._input_mode = InputMode.TEXT
        self._last_move_time: float = 0.0
        self._log_mgr: ExploreLogManager | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-content"):
            yield TileMapCanvas(id="area-map")
            with Vertical(id="right-panel"):
                yield ExploreMapWidget(id="explore-map")
                yield ExploreStatusWidget(id="explore-status")
        yield RichLog(id="explore-log", highlight=True, markup=True)
        yield Static("", id="wasd-status")
        yield Input(placeholder="> 輸入數字或指令", id="explore-input")

    async def on_mount(self) -> None:
        """啟動時載入 demo 場景。"""
        chars, exp_map, state = create_exploration_demo(self._initial_map)
        self.characters = chars
        self.exp_map = exp_map
        self.state = state

        # 啟動遊戲時鐘（即時探索計時）
        state.game_clock.start_exploration()

        log = self.query_one("#explore-log", RichLog)
        self._log_mgr = ExploreLogManager(log)
        self._log_mgr.log("[bold green]T.O.T. 探索系統啟動[/]")
        self._log_mgr.log(f"[dim]地圖：{exp_map.name}（{exp_map.scale}）[/]")
        self._log_mgr.log("")

        # 進入入口節點（若有 area 地圖會自動進入探索模式）
        self._handler._on_enter_node(
            self.characters, self.exp_map, self.state, self._log_mgr, self._refresh_all
        )
        self._refresh_all()

        # 如果進入了 area，自動切換到 WASD 模式
        if self._handler.area_state is not None:
            self._log_area_snapshot()
            self._enter_wasd_mode()

    # ------------------------------------------------------------------
    # 輸入模式切換
    # ------------------------------------------------------------------

    def _enter_wasd_mode(self) -> None:
        """切換到 WASD 即時移動模式。"""
        self._input_mode = InputMode.WASD
        self.query_one("#explore-input", Input).display = False
        self.query_one("#wasd-status", Static).display = True
        self._update_wasd_status()

    def _exit_wasd_mode(self) -> None:
        """切換回 TEXT 指令輸入模式。"""
        self._input_mode = InputMode.TEXT
        self.query_one("#explore-input", Input).display = True
        self.query_one("#wasd-status", Static).display = False
        self.query_one("#explore-input", Input).focus()

    # ------------------------------------------------------------------
    # WASD 移動
    # ------------------------------------------------------------------

    def _do_wasd_move(self, delta: tuple[float, float]) -> None:
        """執行 WASD 方向移動（探索模式不消耗移動力）。"""
        area = self._handler.area_state
        if area is None:
            return

        # 探索模式不消耗移動力 — 每次重置確保 explore_move 不被 speed 限制
        reset_movement(area)

        pos = get_party_position(area)
        if pos is None:
            return

        tx = pos.x + delta[0]
        ty = pos.y + delta[1]
        result = explore_move(area, tx, ty)

        if result.success:
            new_pos = get_party_position(area)
            log_mgr = getattr(self, "_log_mgr", None)
            if new_pos and log_mgr:
                log_mgr.log_movement(delta[0], delta[1], new_pos.x, new_pos.y)
            self._refresh_all()
            self._update_wasd_status()

    def _update_wasd_status(self) -> None:
        """更新 WASD 狀態列（位置 + 物件提示）。"""
        status_widget = self.query_one("#wasd-status", Static)
        area = self._handler.area_state
        if area is None:
            status_widget.update("")
            return

        pos = get_party_position(area)
        if pos is None:
            status_widget.update("")
            return

        pos_text = f"位置 ({pos.x:.1f}, {pos.y:.1f})"

        # 附近可互動物件提示
        nearby = get_nearby_props(area)
        if nearby:
            prop_name = nearby[0].name or nearby[0].id
            hint = f"  目前靠近：[bold yellow][{prop_name}][/] 按 E 互動"
        else:
            hint = ""

        status_widget.update(f"[bold]{pos_text}[/]{hint}    [dim]WASD=移動 E=互動 Q=離開[/]")

    # ------------------------------------------------------------------
    # 按鍵攔截
    # ------------------------------------------------------------------

    async def on_key(self, event: Key) -> None:
        """WASD 模式下攔截按鍵。"""
        if self._input_mode != InputMode.WASD:
            return

        key = event.key.lower()

        # WASD 移動
        if key in WASD_DIRECTIONS:
            event.prevent_default()
            event.stop()

            # 100ms 防抖
            now = time.monotonic()
            if now - self._last_move_time < MOVE_COOLDOWN_S:
                return
            self._last_move_time = now

            self._do_wasd_move(WASD_DIRECTIONS[key])
            return

        # E = 互動（切回 TEXT 模式處理）
        if key == "e":
            event.prevent_default()
            event.stop()
            self._handle_interact()
            return

        # Q = 離開 area
        if key == "q":
            event.prevent_default()
            event.stop()
            self._handle_exit_area()
            return

    def _handle_interact(self) -> None:
        """E 鍵互動：切回 TEXT 模式，觸發 search 指令。"""
        if self._handler.area_state is None:
            return

        if self._log_mgr:
            self._log_mgr.log_player_input("search (E key)")
        self._exit_wasd_mode()

        # 自動觸發 search 指令（傳 log_mgr 讓事件寫入 log 檔）
        log_target = self._log_mgr or self.query_one("#explore-log", RichLog)
        self._handler.handle_command(
            "search",
            self.characters,
            self.exp_map,
            self.state,
            log_target,
            self._refresh_all,
        )
        self._refresh_all()

    def _handle_exit_area(self) -> None:
        """Q 鍵離開 area。"""
        if self._handler.area_state is None:
            return

        if self._log_mgr:
            self._log_mgr.log_player_input("exit (Q key)")
            self._log_area_snapshot()

        log_target = self._log_mgr or self.query_one("#explore-log", RichLog)
        self._handler.handle_command(
            "exit",
            self.characters,
            self.exp_map,
            self.state,
            log_target,
            self._refresh_all,
        )

        # 離開 area 後回到 TEXT 模式
        self._exit_wasd_mode()
        self._refresh_all()

    # ------------------------------------------------------------------
    # 地圖快照
    # ------------------------------------------------------------------

    def _log_area_snapshot(self) -> None:
        """記錄當前 area 地圖快照到 log 檔（braille 渲染）。"""
        if not self._log_mgr or not self._handler.area_state:
            return
        area_map = self.query_one("#area-map", TileMapCanvas)
        # 需要 widget 有實際尺寸才能渲染 braille
        if area_map.size.width < 1 or area_map.size.height < 1:
            return
        text = area_map.render()
        self._log_mgr.log_map_snapshot(text.plain)

    # ------------------------------------------------------------------
    # 地圖刷新
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        """更新地圖和狀態面板。"""
        pc_map = self.query_one("#explore-map", ExploreMapWidget)
        area_map = self.query_one("#area-map", TileMapCanvas)

        if self._handler.area_state is not None:
            # Area 模式：Tile 地圖 + Pointcrawl 並排
            area_map.display = True
            area_ms = self._handler.area_state.map_state
            buf = RenderBuffer(area_ms.manifest.width, area_ms.manifest.height)
            buf.build(area_ms)
            area_map.render_buffer = buf
            area_map.map_state = area_ms
            # Pointcrawl 始終顯示（導航縮圖）
            if self.exp_map and self.state:
                pc_map.map_state = self.exp_map
                pc_map.explore_state = self.state
        else:
            # Pointcrawl 模式：隱藏 Tile 地圖，Pointcrawl 獨佔
            area_map.display = False
            if self.exp_map and self.state:
                pc_map.map_state = self.exp_map
                pc_map.explore_state = self.state

        if self.state:
            status_widget = self.query_one("#explore-status", ExploreStatusWidget)
            status_widget.update_status(self.characters, self.state.game_clock)

    # ------------------------------------------------------------------
    # TEXT 模式輸入
    # ------------------------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """處理玩家文字輸入。"""
        cmd = event.value.strip()
        event.input.value = ""

        if not cmd:
            return

        if self._log_mgr:
            self._log_mgr.log_player_input(cmd)

        log_target = self._log_mgr or self.query_one("#explore-log", RichLog)

        if not self.exp_map or not self.state:
            log_target.write("[yellow]場景尚未載入。[/]")
            return

        # 地圖切換指令
        if cmd.lower().startswith("load "):
            map_key = cmd[5:].strip().lower()
            self._load_new_map(map_key, log_target)
            return

        # 交給 handler 處理
        should_quit = self._handler.handle_command(
            cmd,
            self.characters,
            self.exp_map,
            self.state,
            log_target,
            self._refresh_all,
        )

        if should_quit:
            self.exit()
            return

        self._refresh_all()

        # 如果剛進入 area 且 handler 回到主選單，才切換到 WASD
        # （避免在多步選單流程中途切回 WASD）
        if (
            self._handler.area_state is not None
            and self._input_mode == InputMode.TEXT
            and self._handler.phase == ExplorePhase.AREA_MAIN
        ):
            self._enter_wasd_mode()

        # 如果離開了 area（handler 完成 exit 指令後），確保回到 TEXT
        if self._handler.area_state is None and self._input_mode == InputMode.WASD:
            self._exit_wasd_mode()

    def _load_new_map(self, map_key: str, log: RichLog | ExploreLogManager) -> None:
        """切換地圖（測試用）。"""
        if map_key not in AVAILABLE_MAPS:
            log.write(f"[red]未知地圖：{map_key}[/]（可用：{', '.join(AVAILABLE_MAPS)}）")
            return

        exp_map = load_map(map_key)
        self.exp_map = exp_map
        self.state = ExplorationState(
            current_map_id=exp_map.id,
            current_node_id=exp_map.entry_node_id,
            discovered_nodes={exp_map.entry_node_id},
        )

        # 標記入口已造訪
        for node in exp_map.nodes:
            if node.id == exp_map.entry_node_id:
                node.is_visited = True
                break

        # 重置 handler 狀態 + 啟動遊戲時鐘
        self._handler = ExploreInputHandler()
        self._input_mode = InputMode.TEXT
        self.state.game_clock.start_exploration()

        log.write(f"\n[bold green]載入地圖：{exp_map.name}[/]")
        self._handler._on_enter_node(
            self.characters, self.exp_map, self.state, log, self._refresh_all
        )
        self._refresh_all()

        # 如果新地圖有 area，自動進入 WASD
        if self._handler.area_state is not None:
            self._log_area_snapshot()
            self._enter_wasd_mode()
