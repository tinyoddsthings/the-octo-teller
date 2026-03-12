"""NPC 回合邏輯（怪物 AI + AI 隊友）。

從 app.py 搬出的 monster_turn, ai_character_turn 等函式。
使用 Visibility Graph + A* 連續空間尋路（pathfinding.py）。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from uuid import UUID

from tot.gremlins.bone_engine.combat import get_reach_m, use_action
from tot.gremlins.bone_engine.conditions import can_take_action
from tot.gremlins.bone_engine.movement import move_toward_target
from tot.gremlins.bone_engine.spatial import (
    distance,
    get_actor_position,
    move_entity,
    validate_spell_range,
)
from tot.gremlins.bone_engine.spells import can_cast, cast_spell, get_spell_by_name
from tot.models import (
    Actor,
    Character,
    CombatState,
    MapState,
    Monster,
    Position,
    Spell,
)
from tot.tui.combat_bridge import (
    display_name,
    get_actor,
    pos_to_grid,
)

if TYPE_CHECKING:
    from tot.tui.log_manager import LogManager


# ---------------------------------------------------------------------------
# 共用移動邏輯
# ---------------------------------------------------------------------------


def greedy_move_toward(
    actor: Actor,
    target_id: UUID,
    reach: int,
    mover: Character | Monster | None,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
) -> float:
    """A* 尋路移動 actor 靠近 target，回傳最終距離（公尺）。"""
    from tot.tui.actions import check_oa_for_step

    tgt_pos = get_actor_position(target_id, map_state)
    speed_left = combat_state.turn_state.movement_remaining

    if not tgt_pos:
        return float("inf")

    cur_pos = Position(x=actor.x, y=actor.y)
    gs = map_state.manifest.grid_size_m
    reach_m = reach * gs

    # 已在範圍內
    cur_dist = distance(cur_pos, tgt_pos)
    if cur_dist <= reach_m:
        return cur_dist

    if speed_left < 0.01:
        return cur_dist

    # 路徑規劃（純計算，不執行移動）
    result = move_toward_target(
        actor,
        target_id,
        reach,
        mover,
        combat_state,
        map_state,
        characters,
        monsters,
        greedy_fallback=True,
    )

    if result is not None:
        path, _ = result
        for wp in path:
            seg_dist = math.sqrt((wp.x - actor.x) ** 2 + (wp.y - actor.y) ** 2)
            if seg_dist < 0.01:
                continue
            if speed_left < seg_dist - 0.01:
                break
            old_x, old_y = actor.x, actor.y
            res = move_entity(actor, wp.x, wp.y, map_state, speed_left)
            if not res.success:
                break
            speed_left = res.speed_remaining
            if mover and check_oa_for_step(
                mover,
                old_x,
                old_y,
                actor.x,
                actor.y,
                combat_state,
                map_state,
                combatant_map,
                characters,
                monsters,
                log,
            ):
                break

    combat_state.turn_state.movement_remaining = speed_left

    new_pos = Position(x=actor.x, y=actor.y)
    return distance(new_pos, tgt_pos) if tgt_pos else float("inf")


# ---------------------------------------------------------------------------
# 怪物 AI
# ---------------------------------------------------------------------------


def monster_turn(
    monster: Monster,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
) -> None:
    """怪物自動行動——移動靠近並攻擊存活 PC。"""
    from tot.tui.actions import execute_attack

    if not monster.is_alive:
        log.log(f"[dim]{display_name(monster)} 已倒下，跳過回合。[/]")
        return

    if not can_take_action(monster):
        log.log(f"[dim]{display_name(monster)} 無法行動，跳過回合。[/]")
        return

    log.log(f"\n[bold magenta]🗡️  {display_name(monster)} 的回合[/]")
    log.log_round_snapshot(combat_state, map_state, characters, monsters, combatant_map)

    combat_state.turn_state.movement_remaining = float(monster.speed)

    alive_pcs = [c for c in characters if c.is_alive and c.hp_current > 0]
    if not alive_pcs:
        return

    mon_actor = get_actor(monster.id, map_state)
    target = alive_pcs[0]
    best_dist = float("inf")

    if mon_actor:
        mon_pos = Position(x=mon_actor.x, y=mon_actor.y)
        for pc in alive_pcs:
            pc_pos = get_actor_position(pc.id, map_state)
            if pc_pos:
                d = distance(mon_pos, pc_pos)
                if d < best_dist:
                    best_dist = d
                    target = pc

    gs = map_state.manifest.grid_size_m
    reach_m = get_reach_m(monster, gs)
    reach_grids = max(1, round(reach_m / gs))

    if mon_actor:
        old_x, old_y = mon_actor.x, mon_actor.y
        best_dist = greedy_move_toward(
            mon_actor,
            target.id,
            reach_grids,
            monster,
            combat_state,
            map_state,
            combatant_map,
            characters,
            monsters,
            log,
        )
        if not monster.is_alive:
            refresh_all_fn()
            return
        if mon_actor.x != old_x or mon_actor.y != old_y:
            mgx, mgy = pos_to_grid(mon_actor.x, mon_actor.y, gs)
            log.log(
                f"  [dim]{display_name(monster)} 移動到 "
                f"({mgx}, {mgy})（距離 {target.name}: {best_dist:.1f}m）[/]"
            )

    in_range = True
    if mon_actor and best_dist > reach_m:
        in_range = False
        name = display_name(monster)
        log.log(f"  [dim]{name} 無法接近 {target.name}（距離 {best_dist:.1f}m）[/]")

    if in_range:
        execute_attack(monster, target, combat_state, log)
    refresh_all_fn()


# ---------------------------------------------------------------------------
# AI 角色行動
# ---------------------------------------------------------------------------


def ai_character_turn(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
) -> None:
    """AI 角色回合——根據職業分派。"""
    if not char.is_alive or char.hp_current <= 0:
        log.log(f"[dim]{char.name} 已倒下，跳過回合。[/]")
        return

    if not can_take_action(char):
        log.log(f"[dim]{char.name} 無法行動，跳過回合。[/]")
        return

    log.log(f"\n[bold blue]🤖 {char.name}（AI）的回合[/]")
    log.log_round_snapshot(combat_state, map_state, characters, monsters, combatant_map)

    combat_state.turn_state.movement_remaining = float(char.speed)

    if char.char_class in ("Cleric", "Wizard", "Sorcerer", "Warlock", "Druid"):
        _ai_caster_turn(
            char,
            combat_state,
            map_state,
            combatant_map,
            characters,
            monsters,
            log,
            refresh_all_fn,
        )
    else:
        _ai_melee_turn(
            char,
            combat_state,
            map_state,
            combatant_map,
            characters,
            monsters,
            log,
            refresh_all_fn,
        )


def _ai_melee_turn(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
) -> None:
    """AI 近戰角色——移動靠近最近敵人 + 攻擊。"""
    from tot.tui.actions import execute_attack

    alive_enemies = [m for m in monsters if m.is_alive]
    if not alive_enemies:
        return

    char_actor = get_actor(char.id, map_state)
    if not char_actor:
        return

    target = alive_enemies[0]
    best_dist = float("inf")
    char_pos = Position(x=char_actor.x, y=char_actor.y)
    for enemy in alive_enemies:
        enemy_pos = get_actor_position(enemy.id, map_state)
        if enemy_pos:
            d = distance(char_pos, enemy_pos)
            if d < best_dist:
                best_dist = d
                target = enemy

    gs = map_state.manifest.grid_size_m
    reach_m = get_reach_m(char, gs)
    reach_grids = max(1, round(reach_m / gs))

    old_x, old_y = char_actor.x, char_actor.y
    best_dist = greedy_move_toward(
        char_actor,
        target.id,
        reach_grids,
        char,
        combat_state,
        map_state,
        combatant_map,
        characters,
        monsters,
        log,
    )
    if not char.is_alive:
        refresh_all_fn()
        return
    if char_actor.x != old_x or char_actor.y != old_y:
        cgx, cgy = pos_to_grid(char_actor.x, char_actor.y, gs)
        log.log(
            f"  [dim]{char.name} 移動到 ({cgx}, {cgy})"
            f"（距離 {display_name(target)}: {best_dist:.1f}m）[/]"
        )

    if best_dist <= reach_m:
        execute_attack(char, target, combat_state, log)
    else:
        log.log(f"  [dim]{char.name} 無法接近 {display_name(target)}[/]")

    refresh_all_fn()


def _ai_caster_turn(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
) -> None:
    """AI 施法者——優先治療隊友(HP<50%) → 攻擊法術 → 戲法 → 近戰。"""
    if _ai_try_heal(char, combat_state, map_state, characters, log):
        refresh_all_fn()
        return

    if _ai_try_attack_spell(char, combat_state, map_state, monsters, log):
        refresh_all_fn()
        return

    if _ai_try_cantrip(char, combat_state, map_state, monsters, log):
        refresh_all_fn()
        return

    _ai_melee_turn(
        char,
        combat_state,
        map_state,
        combatant_map,
        characters,
        monsters,
        log,
        refresh_all_fn,
    )


def _ai_try_heal(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    characters: list[Character],
    log: LogManager,
) -> bool:
    """嘗試治療 HP < 50% 的隊友。回傳 True 表示有行動。"""
    wounded = [
        c for c in characters if c.is_alive and c.hp_current > 0 and c.hp_current < c.hp_max * 0.5
    ]
    if not wounded:
        return False

    healing_spells = []
    for name in char.spells_prepared:
        spell = get_spell_by_name(name)
        if spell and spell.effect_type.value == "healing":
            healing_spells.append(spell)

    if not healing_spells:
        return False

    for spell in healing_spells:
        slot = spell.level if spell.level > 0 else None
        error = can_cast(char, spell, slot_level=slot)
        if error is not None:
            continue

        target = min(wounded, key=lambda c: c.hp_current / c.hp_max)

        if map_state:
            caster_pos = get_actor_position(char.id, map_state)
            tgt_pos = get_actor_position(target.id, map_state)
            if caster_pos and tgt_pos:
                gs = map_state.manifest.grid_size_m
                dist = distance(caster_pos, tgt_pos)
                range_err = validate_spell_range(spell, dist, gs)
                if range_err:
                    continue

        if spell.level > 0:
            use_action(combat_state)
        result = cast_spell(char, spell, target, slot_level=slot)
        log.log(f"[magenta]✨ {result.message}[/]")
        if spell.level == 0:
            use_action(combat_state)
        return True

    return False


def _ai_try_attack_spell(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    monsters: list[Monster],
    log: LogManager,
) -> bool:
    """嘗試對怪物施放攻擊法術（非戲法）。"""
    alive_enemies = [m for m in monsters if m.is_alive]
    if not alive_enemies:
        return False

    attack_spells = []
    for name in char.spells_prepared:
        spell = get_spell_by_name(name)
        if spell and spell.level > 0 and spell.effect_type.value == "damage":
            attack_spells.append(spell)

    for spell in attack_spells:
        slot = spell.level
        error = can_cast(char, spell, slot_level=slot)
        if error is not None:
            continue

        target = _find_ai_spell_target(char, spell, alive_enemies, map_state)
        if not target:
            continue

        use_action(combat_state)
        result = cast_spell(char, spell, target, slot_level=slot)
        log.log(f"[magenta]✨ {result.message}[/]")
        return True

    return False


def _ai_try_cantrip(
    char: Character,
    combat_state: CombatState,
    map_state: MapState,
    monsters: list[Monster],
    log: LogManager,
) -> bool:
    """嘗試施放攻擊戲法。"""
    alive_enemies = [m for m in monsters if m.is_alive]
    if not alive_enemies:
        return False

    cantrips = []
    for name in list(dict.fromkeys(char.spells_prepared + char.spells_known)):
        spell = get_spell_by_name(name)
        if spell and spell.level == 0 and spell.effect_type.value == "damage":
            cantrips.append(spell)

    for spell in cantrips:
        error = can_cast(char, spell, slot_level=None)
        if error is not None:
            continue

        target = _find_ai_spell_target(char, spell, alive_enemies, map_state)
        if not target:
            continue

        result = cast_spell(char, spell, target, slot_level=None)
        log.log(f"[magenta]✨ {result.message}[/]")
        use_action(combat_state)
        return True

    return False


def _find_ai_spell_target(
    caster: Character,
    spell: Spell,
    candidates: list[Monster],
    map_state: MapState,
) -> Monster | None:
    """找射程內的第一個合法目標。"""
    if not map_state:
        return candidates[0] if candidates else None

    caster_pos = get_actor_position(caster.id, map_state)
    if not caster_pos:
        return candidates[0] if candidates else None

    gs = map_state.manifest.grid_size_m
    for enemy in candidates:
        tgt_pos = get_actor_position(enemy.id, map_state)
        if not tgt_pos:
            continue
        dist = distance(caster_pos, tgt_pos)
        range_err = validate_spell_range(spell, dist, gs)
        if not range_err:
            return enemy

    return None
