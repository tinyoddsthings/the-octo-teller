"""AI 自動對戰整合測試——用 HeadlessCombatRunner 驗證 D&D 規則。

每個測試跑一場完整戰鬥，用斷言函式驗證 log。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tot.testing.assertions import (
    assert_action_economy,
    assert_damage_nonnegative,
    assert_dead_actors_skip_turns,
    assert_hp_not_below_zero,
    assert_melee_range_valid,
    assert_movement_within_speed,
    assert_opportunity_attacks_logged,
)
from tot.testing.combat_logger import CombatLogger
from tot.testing.combat_runner import HeadlessCombatRunner
from tot.testing.player_ai import (
    GreedyMeleeStrategy,
    RandomStrategy,
)
from tot.tui.demo import create_demo_scene

# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------


def _run_demo_battle(strategy, *, seed: int = 42, max_rounds: int = 30):
    """用指定策略跑一場 demo 戰鬥。"""
    import random

    chars, mons, ms, cs = create_demo_scene()
    rng = random.Random(seed)
    logger = CombatLogger()
    runner = HeadlessCombatRunner(
        characters=chars,
        monsters=mons,
        map_state=ms,
        combat_state=cs,
        player_strategy=strategy,
        logger=logger,
        max_rounds=max_rounds,
        rng=rng,
    )
    return runner.run()


# ---------------------------------------------------------------------------
# 測試
# ---------------------------------------------------------------------------


class TestRandomStrategy:
    """隨機策略跑 tutorial 戰鬥——壓力測試基本規則。"""

    def test_completes_without_crash(self):
        """隨機策略應能跑完不 crash。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert result.winner in ("players", "monsters", "draw")
        assert result.total_rounds >= 1

    def test_dead_actors_skip_turns(self):
        """倒下的角色不應有動作。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert_dead_actors_skip_turns(result.log)

    def test_action_economy(self):
        """每回合最多 1 次動作。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert_action_economy(result.log)

    def test_damage_nonnegative(self):
        """傷害值不為負。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert_damage_nonnegative(result.log)

    def test_hp_not_below_zero(self):
        """HP 不低於 0。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert_hp_not_below_zero(result.log)

    def test_has_log_entries(self):
        """應有 log 記錄。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert len(result.log.entries) > 0

    def test_has_map_snapshots(self):
        """應有地圖快照。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert len(result.log.map_snapshots) > 0

    def test_has_status_snapshots(self):
        """應有狀態快照。"""
        result = _run_demo_battle(RandomStrategy(seed=42))
        assert len(result.log.status_snapshots) > 0


class TestGreedyMelee:
    """貪心近戰策略——驗證移動+攻擊流程。"""

    def test_completes_without_crash(self):
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        assert result.winner in ("players", "monsters", "draw")

    def test_melee_range_valid(self):
        """近戰攻擊距離合理。"""
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        assert_melee_range_valid(result.log)

    def test_movement_within_speed(self):
        """移動距離不超速。"""
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        assert_movement_within_speed(result.log)

    def test_dead_actors_skip(self):
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        assert_dead_actors_skip_turns(result.log)

    def test_opportunity_attacks_logged(self):
        """借機攻擊記錄格式正確。"""
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        assert_opportunity_attacks_logged(result.log)


class TestMultipleSeeds:
    """多種子壓力測試——確保不同隨機序列都能正常運行。"""

    @pytest.mark.parametrize("seed", [1, 7, 13, 42, 99, 256, 1024])
    def test_random_strategy_various_seeds(self, seed: int):
        result = _run_demo_battle(RandomStrategy(seed=seed), seed=seed)
        assert result.winner in ("players", "monsters", "draw")
        assert_dead_actors_skip_turns(result.log)
        assert_action_economy(result.log)

    @pytest.mark.parametrize("seed", [1, 42, 99])
    def test_greedy_melee_various_seeds(self, seed: int):
        result = _run_demo_battle(GreedyMeleeStrategy(seed=seed), seed=seed)
        assert result.winner in ("players", "monsters", "draw")
        assert_melee_range_valid(result.log)


class TestLogSave:
    """測試 log 輸出。"""

    def test_save_log_to_file(self, tmp_path: Path):
        """log 可以正確寫入檔案。"""
        result = _run_demo_battle(GreedyMeleeStrategy(seed=42))
        log_path = tmp_path / "selfplay_test.log"
        logger = CombatLogger()
        logger._log = result.log
        logger.save(log_path)

        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "自動對戰紀錄" in content
        assert "第 1 輪" in content
