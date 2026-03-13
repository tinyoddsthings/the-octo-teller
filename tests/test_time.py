"""GameClock 統一時鐘 + TimeCosts 常數測試。"""

from __future__ import annotations

from unittest.mock import patch

from tot.gremlins.bone_engine.time_costs import (
    COMBAT_ROUND,
    DUNGEON_MOVE_DEFAULT,
    FORCE_DOOR,
    LOCKPICK,
    LONG_REST,
    RITUAL_BASE,
    SEARCH_ROOM_DUNGEON,
    SEARCH_ROOM_TOWN,
    SHORT_REST,
    TOWN_MOVE_DEFAULT,
)
from tot.models.time import GameClock, format_seconds_human

# ---------------------------------------------------------------------------
# GameClock 基礎
# ---------------------------------------------------------------------------


class TestGameClock:
    def test_default_start(self):
        clock = GameClock()
        assert clock.in_game_start_second == 28800  # 08:00
        assert clock.accumulated_seconds == 0
        assert clock.total_seconds == 28800

    def test_add_event(self):
        clock = GameClock()
        clock.add_event(600)  # 10 分鐘
        assert clock.accumulated_seconds == 600
        assert clock.total_seconds == 28800 + 600

    def test_add_combat_round(self):
        clock = GameClock()
        clock.add_combat_round()
        assert clock.accumulated_seconds == 6
        clock.add_combat_round()
        assert clock.accumulated_seconds == 12

    def test_multiple_events(self):
        clock = GameClock()
        clock.add_event(LOCKPICK)
        clock.add_combat_round()
        clock.add_event(SHORT_REST)
        assert clock.accumulated_seconds == LOCKPICK + 6 + SHORT_REST

    def test_elapsed_seconds(self):
        clock = GameClock()
        clock.add_event(300)
        assert clock.elapsed_seconds == 300

    def test_custom_start_second(self):
        clock = GameClock(in_game_start_second=0)
        assert clock.total_seconds == 0
        clock.add_event(100)
        assert clock.total_seconds == 100

    # ── 探索即時時鐘 ──

    @patch("tot.models.time.time.monotonic")
    def test_start_exploration(self, mock_mono):
        mock_mono.return_value = 1000.0
        clock = GameClock()
        clock.start_exploration()
        assert clock._explore_real_start == 1000.0

        # 模擬經過 30 秒
        mock_mono.return_value = 1030.0
        assert clock.total_seconds == 28800 + 30
        assert clock.elapsed_seconds == 30

    @patch("tot.models.time.time.monotonic")
    def test_pause_exploration(self, mock_mono):
        mock_mono.return_value = 1000.0
        clock = GameClock()
        clock.start_exploration()

        mock_mono.return_value = 1045.0
        clock.pause_exploration()

        assert clock.accumulated_seconds == 45
        assert clock._explore_real_start is None
        # 暫停後 total_seconds 不再增長
        mock_mono.return_value = 2000.0
        assert clock.total_seconds == 28800 + 45

    @patch("tot.models.time.time.monotonic")
    def test_resume_exploration(self, mock_mono):
        mock_mono.return_value = 1000.0
        clock = GameClock()
        clock.start_exploration()

        mock_mono.return_value = 1010.0
        clock.pause_exploration()
        assert clock.accumulated_seconds == 10

        mock_mono.return_value = 2000.0
        clock.resume_exploration()
        mock_mono.return_value = 2020.0
        assert clock.elapsed_seconds == 30  # 10 + 20

    @patch("tot.models.time.time.monotonic")
    def test_start_exploration_idempotent(self, mock_mono):
        """連續呼叫 start_exploration 不會重置計時。"""
        mock_mono.return_value = 1000.0
        clock = GameClock()
        clock.start_exploration()

        mock_mono.return_value = 1010.0
        clock.start_exploration()  # 不應重置

        mock_mono.return_value = 1020.0
        clock.pause_exploration()
        assert clock.accumulated_seconds == 20  # 完整 20 秒

    # ── 格式化 ──

    def test_format_game_time_default(self):
        clock = GameClock()
        assert clock.format_game_time() == "Day 1 08:00"

    def test_format_game_time_after_events(self):
        clock = GameClock()
        clock.add_event(3600)  # +1 小時
        assert clock.format_game_time() == "Day 1 09:00"

    def test_format_game_time_next_day(self):
        clock = GameClock()
        clock.add_event(LONG_REST + SHORT_REST)  # 9 小時
        assert clock.format_game_time() == "Day 1 17:00"

    def test_format_game_time_midnight_crossover(self):
        clock = GameClock()
        clock.add_event(16 * 3600)  # +16 小時 → 翌日 00:00
        assert clock.format_game_time() == "Day 2 00:00"

    def test_format_elapsed(self):
        clock = GameClock()
        clock.add_event(3665)  # 1h 1m 5s
        assert clock.format_elapsed() == "1 小時 1 分鐘"

    # ── 序列化 ──

    def test_serialization_excludes_runtime(self):
        clock = GameClock()
        data = clock.model_dump()
        assert "_explore_real_start" not in data

    def test_roundtrip(self):
        clock = GameClock(in_game_start_second=0, accumulated_seconds=999)
        data = clock.model_dump()
        restored = GameClock(**data)
        assert restored.total_seconds == 999


# ---------------------------------------------------------------------------
# format_seconds_human
# ---------------------------------------------------------------------------


class TestFormatSecondsHuman:
    def test_seconds(self):
        assert format_seconds_human(30) == "30 秒"

    def test_minutes(self):
        assert format_seconds_human(600) == "10 分鐘"

    def test_minutes_and_seconds(self):
        assert format_seconds_human(65) == "1 分 5 秒"

    def test_hours(self):
        assert format_seconds_human(3600) == "1 小時"

    def test_hours_and_minutes(self):
        assert format_seconds_human(5400) == "1 小時 30 分鐘"

    def test_days(self):
        assert format_seconds_human(86400) == "1 天"

    def test_days_and_hours(self):
        assert format_seconds_human(90000) == "1 天 1 小時"

    def test_zero(self):
        assert format_seconds_human(0) == "0 秒"


# ---------------------------------------------------------------------------
# TimeCosts 常數
# ---------------------------------------------------------------------------


class TestTimeCosts:
    def test_combat_round_is_6(self):
        assert COMBAT_ROUND == 6

    def test_lockpick(self):
        assert LOCKPICK == 60

    def test_force_door(self):
        assert FORCE_DOOR == 6

    def test_search_room_dungeon(self):
        assert SEARCH_ROOM_DUNGEON == 600

    def test_search_room_town(self):
        assert SEARCH_ROOM_TOWN == 3600

    def test_short_rest(self):
        assert SHORT_REST == 3600

    def test_long_rest(self):
        assert LONG_REST == 28800

    def test_ritual_base(self):
        assert RITUAL_BASE == 600

    def test_dungeon_move_default(self):
        assert DUNGEON_MOVE_DEFAULT == 60

    def test_town_move_default(self):
        assert TOWN_MOVE_DEFAULT == 1800
