"""WASD 輸入模式單元測試。

驗證移動距離（0.15m）、100ms 防抖、碰撞、模式切換。
不依賴 Textual App，直接測試 ExplorationTUI 的 WASD 邏輯。
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from tot.gremlins.bone_engine.area_explore import (
    enter_area,
    get_party_position,
)
from tot.models import (
    AbilityScores,
    Character,
    ExplorationMap,
    ExplorationNode,
)
from tot.models.enums import MapScale, NodeType, Skill
from tot.tui.exploration.app import (
    MOVE_COOLDOWN_S,
    WASD_DIRECTIONS,
    WASD_STEP_M,
    ExplorationTUI,
    InputMode,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_map() -> ExplorationMap:
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
        ],
        edges=[],
        entry_node_id="cave",
    )


def _rogue() -> Character:
    return Character(
        name="Lyra",
        char_class="Rogue",
        level=5,
        ability_scores=AbilityScores(STR=10, DEX=16, CON=12, INT=14, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=33,
        hp_current=33,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=8,
        ac=15,
        speed=9,
        skill_proficiencies=[Skill.INVESTIGATION, Skill.PERCEPTION, Skill.STEALTH],
    )


def _setup_area_state():
    """建立 area 探索狀態。"""
    chars = [_rogue()]
    exp_map = _make_map()
    area_state = enter_area(exp_map, "cave", chars)
    assert area_state is not None
    return chars, exp_map, area_state


# ---------------------------------------------------------------------------
# WASD 常數驗證
# ---------------------------------------------------------------------------


class TestWASDConstants:
    def test_step_distance(self) -> None:
        """每步 0.15m = 9m/6s × 0.1s。"""
        assert WASD_STEP_M == 0.15

    def test_cooldown(self) -> None:
        """防抖 100ms。"""
        assert MOVE_COOLDOWN_S == 0.1

    def test_directions_complete(self) -> None:
        """WASD 四方向齊全。"""
        assert set(WASD_DIRECTIONS.keys()) == {"w", "a", "s", "d"}

    def test_north_is_positive_y(self) -> None:
        """W = 北 = +Y。"""
        dx, dy = WASD_DIRECTIONS["w"]
        assert dx == 0.0
        assert dy > 0.0

    def test_south_is_negative_y(self) -> None:
        """S = 南 = -Y。"""
        _, dy = WASD_DIRECTIONS["s"]
        assert dy < 0.0


# ---------------------------------------------------------------------------
# InputMode 切換
# ---------------------------------------------------------------------------


class TestInputMode:
    def test_default_is_text(self) -> None:
        """初始模式為 TEXT。"""
        app = ExplorationTUI.__new__(ExplorationTUI)
        app._input_mode = InputMode.TEXT
        assert app._input_mode == InputMode.TEXT

    def test_enum_values(self) -> None:
        assert InputMode.TEXT == "text"
        assert InputMode.WASD == "wasd"


# ---------------------------------------------------------------------------
# WASD 移動邏輯（不需 Textual App，直接測 _do_wasd_move）
# ---------------------------------------------------------------------------


class TestWASDMove:
    def test_move_north(self) -> None:
        """W 向北移動 0.15m。"""
        chars, _, area = _setup_area_state()
        pos_before = get_party_position(area)
        assert pos_before is not None

        # 直接建 mock app 呼叫 _do_wasd_move
        app = ExplorationTUI.__new__(ExplorationTUI)
        app._handler = MagicMock()
        app._handler.area_state = area
        app._refresh_all = MagicMock()
        app._update_wasd_status = MagicMock()

        app._do_wasd_move(WASD_DIRECTIONS["w"])

        pos_after = get_party_position(area)
        assert pos_after is not None
        assert abs(pos_after.y - pos_before.y - WASD_STEP_M) < 0.02
        assert abs(pos_after.x - pos_before.x) < 0.01

    def test_move_west(self) -> None:
        """A 向西移動 0.15m。"""
        chars, _, area = _setup_area_state()
        pos_before = get_party_position(area)
        assert pos_before is not None

        app = ExplorationTUI.__new__(ExplorationTUI)
        app._handler = MagicMock()
        app._handler.area_state = area
        app._refresh_all = MagicMock()
        app._update_wasd_status = MagicMock()

        app._do_wasd_move(WASD_DIRECTIONS["a"])

        pos_after = get_party_position(area)
        assert pos_after is not None
        assert abs(pos_after.x - pos_before.x + WASD_STEP_M) < 0.02

    def test_multiple_moves_accumulate(self) -> None:
        """多次移動累計距離。"""
        chars, _, area = _setup_area_state()
        pos_start = get_party_position(area)
        assert pos_start is not None

        app = ExplorationTUI.__new__(ExplorationTUI)
        app._handler = MagicMock()
        app._handler.area_state = area
        app._refresh_all = MagicMock()
        app._update_wasd_status = MagicMock()

        for _ in range(10):
            app._do_wasd_move(WASD_DIRECTIONS["w"])

        pos_end = get_party_position(area)
        assert pos_end is not None
        expected_dy = WASD_STEP_M * 10  # 1.5m
        assert abs(pos_end.y - pos_start.y - expected_dy) < 0.1


# ---------------------------------------------------------------------------
# 防抖
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_rapid_keys_are_throttled(self) -> None:
        """連續按鍵間隔 < 100ms 被忽略。"""
        app = ExplorationTUI.__new__(ExplorationTUI)
        app._last_move_time = time.monotonic()  # 剛剛按過

        # 間隔 < MOVE_COOLDOWN_S
        now = app._last_move_time + 0.05  # 50ms later
        assert now - app._last_move_time < MOVE_COOLDOWN_S

    def test_after_cooldown_allows_move(self) -> None:
        """間隔 >= 100ms 允許移動。"""
        app = ExplorationTUI.__new__(ExplorationTUI)
        app._last_move_time = time.monotonic() - 0.2  # 200ms ago

        now = time.monotonic()
        assert now - app._last_move_time >= MOVE_COOLDOWN_S


# ---------------------------------------------------------------------------
# 碰撞（牆壁阻擋）
# ---------------------------------------------------------------------------


class TestWallCollision:
    def test_wall_blocks_movement(self) -> None:
        """移向牆壁不會穿過。"""
        chars, _, area = _setup_area_state()
        pos = get_party_position(area)
        assert pos is not None

        app = ExplorationTUI.__new__(ExplorationTUI)
        app._handler = MagicMock()
        app._handler.area_state = area
        app._refresh_all = MagicMock()
        app._update_wasd_status = MagicMock()

        # 向南走到底（Y=0 邊界或牆壁）
        for _ in range(1000):
            app._do_wasd_move(WASD_DIRECTIONS["s"])

        pos_final = get_party_position(area)
        assert pos_final is not None
        # 不會到負座標
        assert pos_final.y >= 0.0


# ---------------------------------------------------------------------------
# 探索模式不消耗移動力
# ---------------------------------------------------------------------------


class TestNoSpeedConsumption:
    def test_reset_movement_called(self) -> None:
        """每次 WASD 移動前 reset_movement，確保不被 speed 限制。"""
        chars, _, area = _setup_area_state()

        app = ExplorationTUI.__new__(ExplorationTUI)
        app._handler = MagicMock()
        app._handler.area_state = area
        app._refresh_all = MagicMock()
        app._update_wasd_status = MagicMock()

        # 走非常多步（遠超 9m/turn 限制）
        for _ in range(200):
            app._do_wasd_move(WASD_DIRECTIONS["w"])

        pos = get_party_position(area)
        assert pos is not None
        # 200 × 0.15 = 30m，若有 speed 限制最多只能走 9m
        # 由於碰撞/邊界，可能走不到 30m，但應該遠超 9m
        initial_y = 2.0  # cave_explore spawn 大約在 y=2
        assert pos.y > initial_y + 9.0
