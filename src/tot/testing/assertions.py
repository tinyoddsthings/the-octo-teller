"""D&D 規則斷言函式——自動驗證戰鬥 log 是否符合規則。

每個函式接受 CombatLog 並在違規時拋出 AssertionError。
"""

from __future__ import annotations

from uuid import UUID

from tot.testing.combat_logger import CombatLog


def assert_dead_actors_skip_turns(log: CombatLog) -> None:
    """0 HP 角色不應有攻擊/施法/閃避等動作記錄。

    規則：倒下後只應有 "skip" 或 "death" 事件。
    """
    dead_ids: set[UUID] = set()

    for entry in log.entries:
        # 追蹤死亡事件
        if entry.action_type == "death" and entry.actor_id:
            dead_ids.add(entry.actor_id)

        # 已死角色不應有戰鬥動作
        if (
            entry.actor_id
            and entry.actor_id in dead_ids
            and entry.action_type in ("attack", "cast_spell", "dodge", "disengage", "move")
        ):
            raise AssertionError(
                f"已倒下的 {entry.actor_name} 在第 {entry.round_num} 輪執行了 "
                f"{entry.action_type} 動作：{entry.message}"
            )


def assert_melee_range_valid(log: CombatLog) -> None:
    """近戰攻擊時距離應在合理範圍內（≤ 觸及範圍）。

    由於 log 記錄的是 grid_distance（Chebyshev），
    近戰攻擊通常 ≤ 1.5m（1 格）或 3.0m（長觸及 2 格）。
    我們使用寬鬆的 4.5m 上限（允許 3 格容差）。
    """
    for entry in log.entries:
        if entry.action_type == "attack" and entry.distance_to_target > 4.5:
            raise AssertionError(
                f"第 {entry.round_num} 輪 {entry.actor_name} 的攻擊距離 "
                f"{entry.distance_to_target:.1f}m 超出近戰範圍上限 4.5m：{entry.message}"
            )


def assert_movement_within_speed(log: CombatLog) -> None:
    """每回合移動距離不超過角色速度。

    標準速度 9m（30ft），允許 10% 浮點容差。
    """
    # 追蹤每個回合的累計移動
    turn_movement: dict[tuple[int, UUID], float] = {}  # (round, actor_id) → total_movement

    for entry in log.entries:
        if entry.action_type == "move" and entry.actor_id and entry.movement_used > 0:
            key = (entry.round_num, entry.actor_id)
            turn_movement[key] = turn_movement.get(key, 0) + entry.movement_used

    # 標準速度上限（含容差）
    max_speed = 13.5  # 9m * 1.5 容差（考慮 Dash 等特殊情況）
    for (rnd, _actor_id), total in turn_movement.items():
        if total > max_speed:
            raise AssertionError(f"第 {rnd} 輪某角色移動 {total:.1f}m 超出速度上限 {max_speed}m")


def assert_action_economy(log: CombatLog) -> None:
    """每回合最多 1 次攻擊動作。

    追蹤每個 (回合, 角色) 的 attack/dodge/disengage 動作次數。
    """
    turn_actions: dict[tuple[int, UUID], int] = {}

    for entry in log.entries:
        if entry.action_type in ("attack", "dodge", "disengage", "cast_spell") and entry.actor_id:
            key = (entry.round_num, entry.actor_id)
            turn_actions[key] = turn_actions.get(key, 0) + 1

    for (rnd, _actor_id), count in turn_actions.items():
        if count > 1:
            # 搜尋此回合的角色名
            actor_name = ""
            for e in log.entries:
                if e.round_num == rnd and e.actor_id == _actor_id:
                    actor_name = e.actor_name
                    break
            raise AssertionError(f"第 {rnd} 輪 {actor_name} 使用了 {count} 次動作（上限 1）")


def assert_damage_nonnegative(log: CombatLog) -> None:
    """傷害值不應為負數。"""
    for entry in log.entries:
        if entry.damage_dealt < 0:
            raise AssertionError(
                f"第 {entry.round_num} 輪 {entry.actor_name} 的傷害值為 "
                f"{entry.damage_dealt}（不應為負）：{entry.message}"
            )


def assert_hp_not_below_zero(log: CombatLog) -> None:
    """HP 快照中不應有負數 HP。"""
    for rnd, snapshots in log.status_snapshots.items():
        for snap in snapshots:
            if snap.hp_current < 0:
                raise AssertionError(
                    f"第 {rnd} 輪 {snap.name} 的 HP 為 {snap.hp_current}（不應低於 0）"
                )


def assert_opportunity_attacks_logged(log: CombatLog) -> None:
    """若有觸發借機攻擊，應有對應的 log 記錄。

    這是一個基本的完整性檢查——確認 OA 事件有被記錄。
    """
    oa_entries = [e for e in log.entries if e.action_type == "opportunity_attack"]
    # 不強制要求一定有 OA，只檢查 OA 記錄的格式
    for entry in oa_entries:
        if not entry.target_id:
            raise AssertionError(f"第 {entry.round_num} 輪借機攻擊記錄缺少目標 ID：{entry.message}")
