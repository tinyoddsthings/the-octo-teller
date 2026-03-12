"""HeadlessCombatRunner——純 Python 無頭戰鬥引擎。

從 CombatTUI.run_combat() 提取戰鬥迴圈，
直接呼叫 bone_engine 函式，不依賴 Textual。
用於 AI 自動對戰整合測試。
"""

from __future__ import annotations

import random
from uuid import UUID

from tot.gremlins.bone_engine.combat import (
    advance_turn,
    apply_damage,
    calc_damage_modifier,
    calc_weapon_attack_bonus,
    check_opportunity_attack,
    resolve_attack,
    roll_damage,
    take_disengage_action,
    take_dodge_action,
    use_action,
    validate_attack_preconditions,
)
from tot.gremlins.bone_engine.conditions import can_take_action, tick_conditions_end_of_turn
from tot.gremlins.bone_engine.pathfinding import find_furthest_along_path
from tot.gremlins.bone_engine.spatial import (
    distance,
    get_actor_position,
)
from tot.models import (
    Character,
    Combatant,
    CombatState,
    Condition,
    MapState,
    Monster,
    MonsterAction,
    Position,
    Weapon,
)
from tot.testing.combat_logger import CombatLogger, CombatResult
from tot.testing.player_ai import Action, ActionType, PlayerStrategy

# ---------------------------------------------------------------------------
# 輔助函式（從 app.py 提取）
# ---------------------------------------------------------------------------


def _display_name(combatant: Character | Monster) -> str:
    if isinstance(combatant, Monster):
        return combatant.label or combatant.name
    return combatant.name


def _get_weapon(combatant: Character | Monster) -> Weapon | MonsterAction | None:
    if isinstance(combatant, Monster):
        return combatant.actions[0] if combatant.actions else None
    return combatant.weapons[0] if combatant.weapons else None


def _get_reach(combatant: Character | Monster) -> float:
    """取得觸及範圍（公尺）。"""
    weapon = _get_weapon(combatant)
    if weapon is None:
        return 1.5
    if isinstance(weapon, MonsterAction):
        return weapon.reach
    return weapon.range_normal


# ---------------------------------------------------------------------------
# HeadlessCombatRunner
# ---------------------------------------------------------------------------


class HeadlessCombatRunner:
    """無頭戰鬥引擎——純 Python，不需 TUI。"""

    def __init__(
        self,
        characters: list[Character],
        monsters: list[Monster],
        map_state: MapState,
        combat_state: CombatState,
        player_strategy: PlayerStrategy,
        *,
        logger: CombatLogger | None = None,
        max_rounds: int = 50,
        rng: random.Random | None = None,
    ) -> None:
        self.characters = characters
        self.monsters = monsters
        self.map_state = map_state
        self.combat_state = combat_state
        self.strategy = player_strategy
        self.logger = logger or CombatLogger()
        self.max_rounds = max_rounds
        self.rng = rng

        # 查找表
        self._combatant_map: dict[UUID, Combatant] = {}
        for c in characters:
            self._combatant_map[c.id] = c
        for m in monsters:
            self._combatant_map[m.id] = m

    def run(self) -> CombatResult:
        """執行完整戰鬥，回傳結構化結果。"""
        current_round = self.combat_state.round_number
        logged_round = 0  # 追蹤已記錄快照的輪次，避免重複

        while self.combat_state.is_active and current_round <= self.max_rounds:
            # 新一輪開始（含第 1 輪）
            if current_round > logged_round:
                logged_round = current_round
                self.logger.log_round_start(current_round)
                self.logger.log_map_snapshot(self.map_state)
                self.logger.log_status_snapshot(self.characters, self.monsters, self.map_state)

            # 執行當前回合
            self._execute_current_turn()

            # 檢查勝負
            winner = self._check_combat_end()
            if winner:
                self.logger.log_combat_end(winner, current_round)
                return CombatResult(
                    winner=winner,
                    total_rounds=current_round,
                    log=self.logger.combat_log,
                )

            # 結束回合
            current = self._current_combatant()
            if current:
                expired = tick_conditions_end_of_turn(current)
                for ac in expired:
                    self.logger.log_action(
                        current.id,
                        _display_name(current),
                        "condition_expire",
                        f"{_display_name(current)} 的 {ac.condition.value} 效果結束",
                    )

            advance_turn(self.combat_state)
            current_round = self.combat_state.round_number

        # 達到最大輪數 → 平手
        self.logger.log_combat_end("draw", current_round)
        return CombatResult(
            winner="draw",
            total_rounds=current_round,
            log=self.logger.combat_log,
        )

    # ----- 私有方法 -----

    def _current_combatant(self) -> Character | Monster | None:
        if not self.combat_state.initiative_order:
            return None
        entry = self.combat_state.initiative_order[self.combat_state.current_turn_index]
        return self._combatant_map.get(entry.combatant_id)

    def _execute_current_turn(self) -> None:
        """執行一個戰鬥者的完整回合。"""
        combatant = self._current_combatant()
        if not combatant:
            return

        name = _display_name(combatant)
        self.logger.log_turn_start(combatant.id, name)

        # 設定移動距離
        self.combat_state.turn_state.movement_remaining = float(combatant.speed)

        # 跳過倒下/無力化角色
        if not combatant.is_alive:
            self.logger.log_action(combatant.id, name, "skip", f"{name} 已倒下，跳過回合")
            return

        if isinstance(combatant, Character) and combatant.hp_current <= 0:
            self.logger.log_action(combatant.id, name, "skip", f"{name} 已倒下，跳過回合")
            return

        if not can_take_action(combatant):
            self.logger.log_action(combatant.id, name, "skip", f"{name} 無法行動，跳過回合")
            return

        # 同步 Actor 存活狀態
        self._sync_actor_alive()

        # 決策迴圈：一個回合可能包含移動 + 動作
        max_decisions = 20  # 防止無限迴圈
        for _ in range(max_decisions):
            actor_entity = self.map_state.get_actor(combatant.id)
            if not actor_entity:
                break

            # 識別敵我
            if isinstance(combatant, Character):
                enemies = [m for m in self.monsters if m.is_alive]
                allies = [c for c in self.characters if c.is_alive and c.id != combatant.id]
            else:
                enemies = [c for c in self.characters if c.is_alive and c.hp_current > 0]
                allies = [m for m in self.monsters if m.is_alive and m.id != combatant.id]

            action = self.strategy.decide(
                combatant, actor_entity, enemies, allies, self.combat_state, self.map_state
            )

            if action.type == ActionType.END_TURN:
                break

            self._execute_action(combatant, action)

            # 如果戰鬥結束，提前退出
            if self._check_combat_end():
                break

    def _execute_action(self, combatant: Character | Monster, action: Action) -> None:
        """執行一個動作。"""
        name = _display_name(combatant)

        if action.type == ActionType.ATTACK:
            self._do_attack(combatant, action)

        elif action.type == ActionType.MOVE:
            self._do_move(combatant, action)

        elif action.type == ActionType.DODGE:
            success = take_dodge_action(combatant, self.combat_state)
            msg = f"{name} 採取閃避動作" if success else f"{name} 無法閃避"
            self.logger.log_action(combatant.id, name, "dodge", msg)

        elif action.type == ActionType.DISENGAGE:
            success = take_disengage_action(combatant, self.combat_state)
            msg = f"{name} 採取撤離動作" if success else f"{name} 無法撤離"
            self.logger.log_action(combatant.id, name, "disengage", msg)

    def _do_attack(self, attacker: Character | Monster, action: Action) -> None:
        """執行攻擊動作。"""
        if not action.target_id:
            return

        target = self._combatant_map.get(action.target_id)
        if not target or not target.is_alive:
            return

        weapon = _get_weapon(attacker)
        if not weapon:
            return

        atk_name = _display_name(attacker)
        tgt_name = _display_name(target)

        # 距離檢查
        dist = 1.5
        atk_pos = get_actor_position(attacker.id, self.map_state)
        tgt_pos = get_actor_position(target.id, self.map_state)
        if atk_pos and tgt_pos:
            dist = distance(atk_pos, tgt_pos)

        # 前置條件檢查（MonsterAction 不走 validate_attack_preconditions）
        if isinstance(weapon, Weapon):
            error = validate_attack_preconditions(attacker, weapon, self.combat_state, dist)
            if error:
                self.logger.log_action(
                    attacker.id, atk_name, "attack_fail", f"{atk_name} 攻擊失敗：{error}"
                )
                return
        else:
            # MonsterAction：手動檢查動作經濟和距離
            if not can_take_action(attacker):
                return
            if self.combat_state.turn_state.action_used:
                return
            reach_m = weapon.reach
            if dist > reach_m:
                self.logger.log_action(
                    attacker.id,
                    atk_name,
                    "attack_fail",
                    f"{atk_name} 攻擊失敗：目標超出範圍（{dist:.1f}m > {reach_m:.1f}m）",
                )
                return

        # 消耗動作
        use_action(self.combat_state)

        atk_bonus = calc_weapon_attack_bonus(attacker, weapon)
        attack_result = resolve_attack(atk_bonus, target.ac, rng=self.rng)

        if not attack_result.is_hit:
            self.logger.log_action(
                attacker.id,
                atk_name,
                "attack",
                f"{atk_name} 用 {weapon.name} 攻擊 {tgt_name} — 未中"
                f"（擲骰 {attack_result.roll_result.total} vs AC {target.ac}）",
                target_id=target.id,
                target_name=tgt_name,
                distance_to_target=dist,
            )
            return

        # 命中 → 傷害
        dmg_mod = calc_damage_modifier(attacker, weapon)
        dmg_result = roll_damage(
            weapon.damage_dice,
            weapon.damage_type,
            modifier=dmg_mod,
            is_critical=attack_result.is_critical,
            rng=self.rng,
        )

        apply_result = apply_damage(
            target,
            dmg_result.total,
            weapon.damage_type,
            attack_result.is_critical,
        )

        crit_str = "爆擊！" if attack_result.is_critical else "命中"
        self.logger.log_action(
            attacker.id,
            atk_name,
            "attack",
            f"{atk_name} 用 {weapon.name} 攻擊 {tgt_name} — {crit_str}"
            f"（擲骰 {attack_result.roll_result.total} vs AC {target.ac}）"
            f" 造成 {apply_result.actual_damage} 點傷害"
            f"（{tgt_name} HP: {target.hp_current}/{target.hp_max}）",
            target_id=target.id,
            target_name=tgt_name,
            damage_dealt=apply_result.actual_damage,
            distance_to_target=dist,
        )

        if apply_result.target_dropped_to_zero:
            self.logger.log_action(
                target.id,
                tgt_name,
                "death",
                f"{tgt_name} 倒下了！",
            )
            self._sync_actor_alive()

    def _do_move(self, combatant: Character | Monster, action: Action) -> None:
        """執行移動——使用 A* 尋路靠近目標。"""
        import math

        actor = self.map_state.get_actor(combatant.id)
        if not actor:
            return

        name = _display_name(combatant)
        speed_left = self.combat_state.turn_state.movement_remaining

        target_pos = action.position
        if not target_pos and action.target_id:
            target_pos = get_actor_position(action.target_id, self.map_state)

        if not target_pos or speed_left < 0.01:
            return

        reach_m = _get_reach(combatant)

        # 已在範圍內 → 不需移動
        cur_pos = Position(x=actor.x, y=actor.y)
        if distance(cur_pos, target_pos) <= reach_m:
            return

        # A* 尋路
        friendly_ids = self._build_friendly_ids(combatant)
        blocked = [
            a
            for a in self.map_state.actors
            if a.is_alive
            and a.is_blocking
            and a.combatant_id not in friendly_ids
            and a.id != actor.id
        ]
        passable = [
            a
            for a in self.map_state.actors
            if a.is_alive and a.is_blocking and a.combatant_id in friendly_ids and a.id != actor.id
        ]

        path = find_furthest_along_path(
            start=cur_pos,
            target=target_pos,
            reach_m=reach_m,
            map_state=self.map_state,
            mover_radius=0.75,
            max_cost=speed_left,
            blocked_actors=blocked,
            passable_actors=passable,
        )

        old_x, old_y = actor.x, actor.y
        total_movement = 0.0

        if path is not None and len(path) > 0:
            for step in path:
                step_old_x, step_old_y = actor.x, actor.y
                step_dist = math.sqrt((step.x - actor.x) ** 2 + (step.y - actor.y) ** 2)
                actor.x = step.x
                actor.y = step.y
                speed_left -= step_dist
                total_movement += step_dist
                if self._check_oa_for_step(combatant, step_old_x, step_old_y, actor.x, actor.y):
                    break

        self.combat_state.turn_state.movement_remaining = max(0.0, speed_left)

        if actor.x != old_x or actor.y != old_y:
            self.logger.log_action(
                combatant.id,
                name,
                "move",
                f"{name} 移動到 ({actor.x:.1f}, {actor.y:.1f})",
                movement_used=total_movement,
                position=Position(x=actor.x, y=actor.y),
            )

    def _check_oa_for_step(
        self,
        mover: Character | Monster,
        old_x: float,
        old_y: float,
        new_x: float,
        new_y: float,
    ) -> bool:
        """檢查移動一步是否觸發借機攻擊。回傳 True 表示 mover 倒下。"""
        if mover.has_condition(Condition.DISENGAGING):
            return False

        for entry in self.combat_state.initiative_order:
            enemy = self._combatant_map.get(entry.combatant_id)
            if not enemy or not enemy.is_alive or enemy.id == mover.id:
                continue
            if isinstance(mover, Character) and isinstance(enemy, Character):
                continue
            if isinstance(mover, Monster) and isinstance(enemy, Monster):
                continue

            enemy_actor = self.map_state.get_actor(enemy.id)
            if not enemy_actor:
                continue

            reach_m = _get_reach(enemy)
            enemy_pos = Position(x=enemy_actor.x, y=enemy_actor.y)

            old_dist = distance(Position(x=old_x, y=old_y), enemy_pos)
            if old_dist > reach_m:
                continue
            new_dist = distance(Position(x=new_x, y=new_y), enemy_pos)
            if new_dist <= reach_m:
                continue

            # 觸發 OA
            weapon: Weapon | None = None
            if isinstance(enemy, Character) and enemy.weapons:
                weapon = enemy.weapons[0]
            elif isinstance(enemy, Monster) and enemy.actions:
                # 轉為 Weapon 以供 check_opportunity_attack
                action = enemy.actions[0]
                weapon = Weapon(
                    name=action.name,
                    damage_dice=action.damage_dice,
                    damage_type=action.damage_type,
                    range_normal=action.reach,
                )

            if not weapon:
                continue

            oa = check_opportunity_attack(enemy, mover, entry, weapon, mover.ac, rng=self.rng)
            if oa.triggered and oa.attack_result:
                enemy_name = _display_name(enemy)
                mover_name = _display_name(mover)
                if oa.attack_result.is_hit and oa.damage_result:
                    apply_result = apply_damage(
                        mover, oa.damage_result.total, oa.damage_result.damage_type
                    )
                    self.logger.log_action(
                        enemy.id,
                        enemy_name,
                        "opportunity_attack",
                        f"{enemy_name} 對 {mover_name} 發動借機攻擊 — 命中！"
                        f" 造成 {apply_result.actual_damage} 點傷害",
                        target_id=mover.id,
                        target_name=mover_name,
                        damage_dealt=apply_result.actual_damage,
                    )
                    if apply_result.target_dropped_to_zero:
                        self._sync_actor_alive()
                        return True
                else:
                    self.logger.log_action(
                        enemy.id,
                        enemy_name,
                        "opportunity_attack",
                        f"{enemy_name} 對 {mover_name} 發動借機攻擊 — 未中",
                        target_id=mover.id,
                        target_name=mover_name,
                    )

        return False

    def _build_friendly_ids(self, combatant: Character | Monster) -> set[UUID]:
        if isinstance(combatant, Character):
            return {c.id for c in self.characters}
        return {m.id for m in self.monsters}

    def _sync_actor_alive(self) -> None:
        """同步 Actor.is_alive 與 Character/Monster 的實際狀態。"""
        for actor in self.map_state.actors:
            combatant = self._combatant_map.get(actor.combatant_id)
            if combatant:
                actor.is_alive = combatant.is_alive

    def _check_combat_end(self) -> str | None:
        """檢查戰鬥是否結束。回傳 "players" / "monsters" / None。"""
        alive_pcs = any(c.is_alive and c.hp_current > 0 for c in self.characters)
        alive_monsters = any(m.is_alive for m in self.monsters)

        if not alive_monsters:
            return "players"
        if not alive_pcs:
            return "monsters"
        return None
