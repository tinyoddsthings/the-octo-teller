"""角色卡 TUI — 5 分頁情境角色卡閱覽介面。"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from tot.gremlins.bone_engine.character_card import CharacterCard
from tot.models.creature import Character


class CharacterSheetApp(App[None]):
    """角色卡閱覽 TUI。"""

    CSS = """
    #main-area {
        height: 1fr;
    }

    #left-sidebar {
        width: 35;
        border-right: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    #right-content {
        width: 1fr;
    }

    TabPane {
        padding: 1;
        overflow-y: auto;
    }

    .tab-content {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "離開"),
        Binding("1", "tab_overview", "總覽"),
        Binding("2", "tab_exploration", "探索"),
        Binding("3", "tab_combat", "戰鬥"),
        Binding("4", "tab_equipment", "裝備"),
        Binding("5", "tab_personal", "個人"),
    ]

    def __init__(self, char: Character) -> None:
        super().__init__()
        self.char = char
        self.card = CharacterCard(char)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            with VerticalScroll(id="left-sidebar"):
                yield Static(self.card.overview(), id="overview-text")
            with TabbedContent(id="tabs"):
                with TabPane("總覽", id="tab-overview"):
                    yield Static(self.card.overview(), classes="tab-content")
                with TabPane("探索", id="tab-exploration"):
                    yield Static(self.card.exploration(), classes="tab-content")
                with TabPane("戰鬥", id="tab-combat"):
                    yield Static(self.card.combat(), classes="tab-content")
                with TabPane("裝備", id="tab-equipment"):
                    yield Static(self.card.equipment(), classes="tab-content")
                with TabPane("個人", id="tab-personal"):
                    yield Static(self.card.personal(), classes="tab-content")
        yield Footer()

    def on_mount(self) -> None:
        cls = list(self.char.class_levels.keys())[0] if self.char.class_levels else "?"
        lv = sum(self.char.class_levels.values())
        self.title = f"T.O.T. 角色卡  ─  {self.char.name}（{cls} Lv{lv}）"

    def action_tab_overview(self) -> None:
        self.query_one(TabbedContent).active = "tab-overview"

    def action_tab_exploration(self) -> None:
        self.query_one(TabbedContent).active = "tab-exploration"

    def action_tab_combat(self) -> None:
        self.query_one(TabbedContent).active = "tab-combat"

    def action_tab_equipment(self) -> None:
        self.query_one(TabbedContent).active = "tab-equipment"

    def action_tab_personal(self) -> None:
        self.query_one(TabbedContent).active = "tab-personal"
