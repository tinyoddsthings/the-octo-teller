"""AI 策略——無頭戰鬥的自動決策。

實作 PlayerStrategy Protocol，各策略回傳 Action 決定每回合動作。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from tot.gremlins.bone_engine.spatial import (
    distance,
    get_actor_position,
    grid_distance,
)
from tot.models import (
    Actor,
    Character,
    CombatState,
    MapState,
    Monster,
    Position,
    Spell,
)

# ---------------------------------------------------------------------------
# Action 資料結構
# ---------------------------------------------------------------------------


class ActionType(StrEnum):
    MOVE = "move"
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    DODGE = "dodge"
    DISENGAGE = "disengage"
    END_TURN = "end_turn"


@dataclass
class Action:
    """一個回合動作的描述。"""

    type: ActionType
    target_id: UUID | None = None  # 攻擊/施法目標的 combatant_id
    position: Position | None = None  # 移動目標位置
    spell: Spell | None = None


# ---------------------------------------------------------------------------
# PlayerStrategy Protocol
# ---------------------------------------------------------------------------

# 型別別名：Character 或 Monster
Combatant = Character | Monster


class PlayerStrategy(Protocol):
    """決定每個回合要做什麼的策略介面。"""

    def decide(
        self,
        actor: Combatant,
        actor_entity: Actor,
        enemies: list[Combatant],
        allies: list[Combatant],
        combat_state: CombatState,
        map_state: MapState,
    ) -> Action: ...


# ---------------------------------------------------------------------------
# RandomStrategy
# ---------------------------------------------------------------------------


class RandomStrategy:
    """隨機選擇合法動作——壓力測試用。

    邏輯：
    1. 如果有敵人在近戰範圍內 → 50% 攻擊 / 50% 移動
    2. 否則 → 移動靠近隨機敵人
    3. 動作已用 → 結束回合
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def decide(
        self,
        actor: Combatant,
        actor_entity: Actor,
        enemies: list[Combatant],
        allies: list[Combatant],
        combat_state: CombatState,
        map_state: MapState,
    ) -> Action:
        if not enemies:
            return Action(type=ActionType.END_TURN)

        action_used = combat_state.turn_state.action_used
        movement_left = combat_state.turn_state.movement_remaining

        actor_pos = Position(x=actor_entity.x, y=actor_entity.y)
        gs = map_state.manifest.grid_size_m

        # 找近戰範圍內的敵人
        melee_targets: list[Combatant] = []
        for enemy in enemies:
            enemy_pos = get_actor_position(enemy.id, map_state)
            if enemy_pos and grid_distance(actor_pos, enemy_pos, gs) <= gs:
                melee_targets.append(enemy)

        # 如果動作未用且有近戰目標 → 隨機選擇攻擊
        if not action_used and melee_targets:
            target = self._rng.choice(melee_targets)
            return Action(type=ActionType.ATTACK, target_id=target.id)

        # 如果還有移動距離 → 移動靠近隨機敵人
        if movement_left >= gs:
            target = self._rng.choice(enemies)
            target_pos = get_actor_position(target.id, map_state)
            if target_pos:
                return Action(type=ActionType.MOVE, target_id=target.id, position=target_pos)

        # 如果動作未用且沒有近戰目標 → 結束回合（已移動完）
        return Action(type=ActionType.END_TURN)


# ---------------------------------------------------------------------------
# GreedyMeleeStrategy
# ---------------------------------------------------------------------------


class GreedyMeleeStrategy:
    """貪心近戰——靠近最近敵人並攻擊。

    流程：先移動靠近最近敵人，再攻擊。
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def decide(
        self,
        actor: Combatant,
        actor_entity: Actor,
        enemies: list[Combatant],
        allies: list[Combatant],
        combat_state: CombatState,
        map_state: MapState,
    ) -> Action:
        if not enemies:
            return Action(type=ActionType.END_TURN)

        action_used = combat_state.turn_state.action_used
        movement_left = combat_state.turn_state.movement_remaining
        gs = map_state.manifest.grid_size_m
        actor_pos = Position(x=actor_entity.x, y=actor_entity.y)

        # 找最近的敵人
        nearest_enemy: Combatant | None = None
        best_dist = float("inf")
        for enemy in enemies:
            enemy_pos = get_actor_position(enemy.id, map_state)
            if enemy_pos:
                d = distance(actor_pos, enemy_pos)
                if d < best_dist:
                    best_dist = d
                    nearest_enemy = enemy

        if not nearest_enemy:
            return Action(type=ActionType.END_TURN)

        nearest_pos = get_actor_position(nearest_enemy.id, map_state)
        if not nearest_pos:
            return Action(type=ActionType.END_TURN)

        # 在攻擊範圍內 → 攻擊
        in_melee = grid_distance(actor_pos, nearest_pos, gs) <= gs
        if in_melee and not action_used:
            return Action(type=ActionType.ATTACK, target_id=nearest_enemy.id)

        # 不在範圍 → 移動靠近
        if movement_left >= gs:
            return Action(type=ActionType.MOVE, target_id=nearest_enemy.id, position=nearest_pos)

        return Action(type=ActionType.END_TURN)


# ---------------------------------------------------------------------------
# ScriptedStrategy
# ---------------------------------------------------------------------------


@dataclass
class ScriptedStrategy:
    """按預設腳本行動——用於可重現的特定情境測試。

    actions 列表依序執行，用完後自動 END_TURN。
    """

    actions: list[Action] = field(default_factory=list)
    _index: int = field(default=0, init=False)

    def decide(
        self,
        actor: Combatant,
        actor_entity: Actor,
        enemies: list[Combatant],
        allies: list[Combatant],
        combat_state: CombatState,
        map_state: MapState,
    ) -> Action:
        if self._index < len(self.actions):
            action = self.actions[self._index]
            self._index += 1
            return action
        return Action(type=ActionType.END_TURN)
