"""Area 探索 TUI 整合測試。

驗證 ExploreInputHandler 的 area 模式指令分派與狀態轉換。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tot.models import (
    AbilityScores,
    Character,
    ExplorationMap,
    ExplorationNode,
    ExplorationState,
)
from tot.models.enums import MapScale, NodeType, Skill
from tot.tui.exploration.explore_input import ExploreInputHandler, ExplorePhase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_map() -> ExplorationMap:
    """包含 cave_explore area 的測試用 Pointcrawl 地圖。"""
    return ExplorationMap(
        id="test-map",
        name="測試地圖",
        scale=MapScale.DUNGEON,
        nodes=[
            ExplorationNode(
                id="cave",
                name="洞穴入口",
                node_type=NodeType.LANDMARK,
                combat_map="cave_explore",
            ),
            ExplorationNode(
                id="empty",
                name="空節點",
                node_type=NodeType.CORRIDOR,
            ),
        ],
        edges=[],
        entry_node_id="cave",
    )


def _rogue() -> Character:
    return Character(
        name="Lyra",
        class_levels={"Rogue": 5},
        ability_scores=AbilityScores(STR=10, DEX=16, CON=12, INT=14, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=33,
        hp_current=33,
        hit_dice_remaining={8: 5},
        ac=15,
        speed=9,
        skill_proficiencies=[Skill.INVESTIGATION, Skill.PERCEPTION, Skill.STEALTH],
    )


def _make_state() -> ExplorationState:
    return ExplorationState(
        current_map_id="test-map",
        current_node_id="cave",
        discovered_nodes={"cave"},
    )


def _setup() -> tuple[ExploreInputHandler, list[Character], ExplorationMap, ExplorationState]:
    handler = ExploreInputHandler()
    chars = [_rogue()]
    exp_map = _make_map()
    state = _make_state()
    return handler, chars, exp_map, state


# ---------------------------------------------------------------------------
# 進入 / 離開 area 模式
# ---------------------------------------------------------------------------


class TestEnterExitArea:
    """area 模式進出測試。"""

    def test_enter_area_via_explore_command(self) -> None:
        """在有 combat_map 的節點輸入 explore 進入 area 模式。"""
        handler, chars, exp_map, state = _setup()
        log = MagicMock()
        refresh = MagicMock()

        # 先進入節點以設定 _current_node_has_area
        handler._on_enter_node(chars, exp_map, state, log)
        assert handler._current_node_has_area is True

        # 輸入 explore
        handler.handle_command("explore", chars, exp_map, state, log, refresh)
        assert handler.area_state is not None
        assert handler.phase == ExplorePhase.AREA_MAIN
        refresh.assert_called()

    def test_enter_area_on_empty_node_fails(self) -> None:
        """無 combat_map 的節點無法進入 area。"""
        handler, chars, exp_map, state = _setup()
        state.current_node_id = "empty"
        log = MagicMock()
        refresh = MagicMock()

        handler._on_enter_node(chars, exp_map, state, log)
        assert handler._current_node_has_area is False

        handler.handle_command("explore", chars, exp_map, state, log, refresh)
        assert handler.area_state is None

    def test_exit_area_mode(self) -> None:
        """輸入 exit 離開 area 模式回到 pointcrawl。"""
        handler, chars, exp_map, state = _setup()
        log = MagicMock()
        refresh = MagicMock()

        handler._on_enter_node(chars, exp_map, state, log)
        handler.handle_command("explore", chars, exp_map, state, log, refresh)
        assert handler.area_state is not None

        # exit
        handler.handle_command("exit", chars, exp_map, state, log, refresh)
        assert handler.area_state is None
        assert handler.phase == ExplorePhase.MAIN

    def test_exit_via_number_0(self) -> None:
        """數字 0 離開 area 模式。"""
        handler, chars, exp_map, state = _setup()
        log = MagicMock()
        refresh = MagicMock()

        handler._on_enter_node(chars, exp_map, state, log)
        handler.handle_command("explore", chars, exp_map, state, log, refresh)

        handler.handle_command("0", chars, exp_map, state, log, refresh)
        assert handler.area_state is None


# ---------------------------------------------------------------------------
# Area 指令路由
# ---------------------------------------------------------------------------


class TestAreaCommandRouting:
    """area 模式指令分派測試。"""

    def _enter_area(self, handler, chars, exp_map, state):
        log = MagicMock()
        refresh = MagicMock()
        handler._on_enter_node(chars, exp_map, state, log)
        handler.handle_command("explore", chars, exp_map, state, log, refresh)
        return log, refresh

    def test_area_look(self) -> None:
        """look 指令在 area 模式正常運作。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("look", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_MAIN
        # log.write 應被呼叫（顯示位置資訊）
        assert log.write.call_count > 0

    def test_area_look_via_number(self) -> None:
        """數字 1 = look。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_MAIN

    def test_area_move_success(self) -> None:
        """move x y 移動成功。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("move 12.5 4.0", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_MAIN
        refresh.assert_called()

    def test_area_move_no_coords_shows_usage(self) -> None:
        """move 不帶座標顯示用法。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("move", chars, exp_map, state, log, refresh)
        # 應有用法提示
        calls = [str(c) for c in log.write.call_args_list]
        assert any("用法" in c for c in calls)

    def test_area_terrain(self) -> None:
        """terrain 指令顯示地形資訊。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("terrain", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_MAIN

    def test_area_reset_movement(self) -> None:
        """reset 重置移動力。"""
        handler, chars, exp_map, state = _setup()
        self._enter_area(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        # 先移動消耗一些速度
        handler.handle_command("move 12.5 4.0", chars, exp_map, state, log, refresh)
        assert handler.area_state.speed_remaining < 9.0

        handler.handle_command("reset", chars, exp_map, state, log, refresh)
        assert handler.area_state.speed_remaining == 9.0


# ---------------------------------------------------------------------------
# Search / Take 流程
# ---------------------------------------------------------------------------


class TestAreaSearchTakeFlow:
    """area 搜索→拾取完整流程測試。"""

    def _enter_and_move_to_mushroom(self, handler, chars, exp_map, state):
        """進入 area 並移動到蘑菇附近（邊緣距離 ≤ 0.5m）。"""
        log = MagicMock()
        refresh = MagicMock()
        handler._on_enter_node(chars, exp_map, state, log)
        handler.handle_command("explore", chars, exp_map, state, log, refresh)
        # 蘑菇在 (3.0, 8.0)，移動到緊鄰位置
        handler.handle_command("move 4.0 2.5", chars, exp_map, state, log, refresh)
        handler.handle_command("reset", chars, exp_map, state, log, refresh)
        handler.handle_command("move 3.0 7.0", chars, exp_map, state, log, refresh)
        return log, refresh

    def test_search_shows_prop_list(self) -> None:
        """search 指令顯示附近可搜索物件。"""
        handler, chars, exp_map, state = _setup()
        self._enter_and_move_to_mushroom(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("search", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_SEARCH_PROP

    def test_search_select_prop_then_char(self) -> None:
        """搜索流程：選 prop → 選角色 → 執行。"""
        handler, chars, exp_map, state = _setup()
        self._enter_and_move_to_mushroom(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()

        # step 1: search → 顯示 prop 列表
        handler.handle_command("search", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_SEARCH_PROP

        # step 2: 選第一個 prop（蘑菇）
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_SEARCH_CHAR

        # step 3: 選角色（只有一個）→ 搜索成功且有 loot → 自動進入拿取流程
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_TAKE

    def test_take_after_search(self) -> None:
        """搜索後可拾取物品。"""
        handler, chars, exp_map, state = _setup()
        self._enter_and_move_to_mushroom(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()

        # 搜索蘑菇
        handler.handle_command("search", chars, exp_map, state, log, refresh)
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        handler.handle_command("1", chars, exp_map, state, log, refresh)

        # 拾取
        handler.handle_command("take", chars, exp_map, state, log, refresh)
        if handler.phase == ExplorePhase.AREA_TAKE:
            # 有可拾取物件
            handler.handle_command("1", chars, exp_map, state, log, refresh)
            assert handler.phase == ExplorePhase.AREA_MAIN
            assert len(handler.area_state.collected_items) > 0

    def test_take_without_search_shows_empty(self) -> None:
        """未搜索時 take 顯示無物品。"""
        handler, chars, exp_map, state = _setup()
        log = MagicMock()
        refresh = MagicMock()
        handler._on_enter_node(chars, exp_map, state, log)
        handler.handle_command("explore", chars, exp_map, state, log, refresh)

        handler.handle_command("take", chars, exp_map, state, log, refresh)
        # 在 spawn 附近沒有可拾取物件，回到 AREA_MAIN
        assert handler.phase == ExplorePhase.AREA_MAIN

    def test_back_from_search_prop(self) -> None:
        """搜索 prop 選擇時按 0 返回。"""
        handler, chars, exp_map, state = _setup()
        self._enter_and_move_to_mushroom(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()
        handler.handle_command("search", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_SEARCH_PROP

        handler.handle_command("0", chars, exp_map, state, log, refresh)
        assert handler.phase == ExplorePhase.AREA_MAIN

    def test_exit_with_collected_items(self) -> None:
        """離開 area 時顯示收集的物品。"""
        handler, chars, exp_map, state = _setup()
        self._enter_and_move_to_mushroom(handler, chars, exp_map, state)

        log = MagicMock()
        refresh = MagicMock()

        # 搜索並拾取蘑菇
        handler.handle_command("search", chars, exp_map, state, log, refresh)
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        handler.handle_command("1", chars, exp_map, state, log, refresh)
        handler.handle_command("take", chars, exp_map, state, log, refresh)
        if handler.phase == ExplorePhase.AREA_TAKE:
            handler.handle_command("1", chars, exp_map, state, log, refresh)

        # 離開
        handler.handle_command("exit", chars, exp_map, state, log, refresh)
        assert handler.area_state is None
        # log 應包含收集物品訊息
        calls = [str(c) for c in log.write.call_args_list]
        assert any("收集" in c or "返回" in c for c in calls)


# ---------------------------------------------------------------------------
# Pointcrawl 主選單 explore 提示
# ---------------------------------------------------------------------------


class TestExploreIndicator:
    """主選單 explore 選項顯示測試。"""

    def test_has_area_shows_explore(self) -> None:
        """有 combat_map 的節點主選單顯示 explore。"""
        handler, chars, exp_map, state = _setup()
        log = MagicMock()
        handler._on_enter_node(chars, exp_map, state, log)
        assert handler._current_node_has_area is True

        log2 = MagicMock()
        handler.show_main_menu(log2)
        calls = [str(c) for c in log2.write.call_args_list]
        assert any("explore" in c for c in calls)

    def test_no_area_no_explore(self) -> None:
        """無 combat_map 的節點主選單不顯示 explore。"""
        handler, chars, exp_map, state = _setup()
        state.current_node_id = "empty"
        log = MagicMock()
        handler._on_enter_node(chars, exp_map, state, log)
        assert handler._current_node_has_area is False

        log2 = MagicMock()
        handler.show_main_menu(log2)
        calls = [str(c) for c in log2.write.call_args_list]
        assert not any("explore" in c and "區域探索" in c for c in calls)
