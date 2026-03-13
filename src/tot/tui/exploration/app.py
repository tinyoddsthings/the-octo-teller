"""探索 TUI 主應用——Pointcrawl 探索介面。

獨立於 CombatTUI，四面板佈局（地圖/狀態/紀錄/輸入）。
純 orchestrator：接收玩家指令 → 轉給 ExploreInputHandler → 更新 Widget。
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog

from tot.models import Character, ExplorationMap, ExplorationState
from tot.tui.exploration.explore_demo import (
    AVAILABLE_MAPS,
    create_exploration_demo,
    load_map,
)
from tot.tui.exploration.explore_input import ExploreInputHandler
from tot.tui.exploration.explore_map_widget import ExploreMapWidget
from tot.tui.exploration.explore_status import ExploreStatusWidget


class ExplorationTUI(App):
    """探索 TUI 主應用。"""

    CSS_PATH = "styles.tcss"
    TITLE = "T.O.T. 探索系統"

    def __init__(self) -> None:
        super().__init__()
        self.characters: list[Character] = []
        self.exp_map: ExplorationMap | None = None
        self.state: ExplorationState | None = None
        self._handler = ExploreInputHandler()

    def compose(self) -> ComposeResult:
        yield ExploreMapWidget(id="explore-map")
        yield ExploreStatusWidget(id="explore-status")
        yield RichLog(id="explore-log", highlight=True, markup=True)
        yield Input(placeholder="> 輸入數字或指令", id="explore-input")

    async def on_mount(self) -> None:
        """啟動時載入 demo 場景。"""
        chars, exp_map, state = create_exploration_demo("ruins")
        self.characters = chars
        self.exp_map = exp_map
        self.state = state

        # 啟動遊戲時鐘（即時探索計時）
        state.game_clock.start_exploration()

        log = self.query_one("#explore-log", RichLog)
        log.write("[bold green]🐙 T.O.T. 探索系統啟動[/]")
        log.write(f"[dim]地圖：{exp_map.name}（{exp_map.scale}）[/]")
        log.write("")

        # 進入入口節點
        self._handler._on_enter_node(self.characters, self.exp_map, self.state, log)
        self._refresh_all()

    def _refresh_all(self) -> None:
        """更新地圖和狀態面板。"""
        if self.exp_map and self.state:
            map_widget = self.query_one("#explore-map", ExploreMapWidget)
            map_widget.map_state = self.exp_map
            map_widget.explore_state = self.state

            status_widget = self.query_one("#explore-status", ExploreStatusWidget)
            status_widget.update_status(self.characters, self.state.game_clock)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """處理玩家輸入。"""
        cmd = event.value.strip()
        event.input.value = ""

        if not cmd:
            return

        log = self.query_one("#explore-log", RichLog)

        if not self.exp_map or not self.state:
            log.write("[yellow]場景尚未載入。[/]")
            return

        # 地圖切換指令
        if cmd.lower().startswith("load "):
            map_key = cmd[5:].strip().lower()
            self._load_new_map(map_key, log)
            return

        # 交給 handler 處理
        should_quit = self._handler.handle_command(
            cmd,
            self.characters,
            self.exp_map,
            self.state,
            log,
            self._refresh_all,
        )

        if should_quit:
            self.exit()
            return

        self._refresh_all()

    def _load_new_map(self, map_key: str, log: RichLog) -> None:
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
        self.state.game_clock.start_exploration()

        log.write(f"\n[bold green]🗺️ 載入地圖：{exp_map.name}[/]")
        self._handler._on_enter_node(self.characters, self.exp_map, self.state, log)
        self._refresh_all()
