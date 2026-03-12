"""玩家動作執行（攻擊/施法/移動/閃避/撤離）。

依賴 combat_bridge 和 log_manager，不直接 import app。
所有方法接收 app context 作為參數。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tot.gremlins.bone_engine.combat import (
    apply_damage,
    check_opportunity_attacks_on_step,
    resolve_attack,
    roll_damage,
    use_action,
    validate_attack_preconditions,
)
from tot.gremlins.bone_engine.conditions import can_take_action
from tot.gremlins.bone_engine.movement import build_actor_lists, path_to_attack_range
from tot.gremlins.bone_engine.pathfinding import find_path_to_range
from tot.gremlins.bone_engine.spatial import (
    can_end_move_at,
    distance,
    get_actor_position,
    is_position_clear,
    move_entity,
    parse_spell_range_meters,
    validate_spell_range,
)
from tot.gremlins.bone_engine.spells import can_cast, cast_spell
from tot.models import (
    SIZE_RADIUS_M,
    Actor,
    Character,
    CombatState,
    MapState,
    Monster,
    MonsterAction,
    Position,
    Size,
    Spell,
    Weapon,
)
from tot.tui.combat_bridge import (
    display_name,
    get_actor,
    get_attack_bonus,
    get_damage_modifier,
    zh_dmg,
)

if TYPE_CHECKING:
    from tot.tui.log_manager import LogManager


# ---------------------------------------------------------------------------
# 逐步移動（含 OA 檢查）
# ---------------------------------------------------------------------------


def step_move_to(
    mover: Character | Monster,
    actor: Actor,
    tx: float,
    ty: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    *,
    path: list[Position] | None = None,
) -> bool:
    """沿路徑點移動角色到目標位置（公尺座標）。回傳 True 表示角色倒下。

    若提供 path，沿路徑點逐段移動（連續座標）。
    若未提供 path，直接嘗試直線移動到 (tx, ty)。
    """
    import math

    start_x, start_y = actor.x, actor.y

    # 建立移動路徑點
    waypoints = [Position(x=tx, y=ty)] if path is None else path

    for wp in waypoints:
        speed_left = combat_state.turn_state.movement_remaining
        seg_dist = math.sqrt((wp.x - actor.x) ** 2 + (wp.y - actor.y) ** 2)
        if seg_dist < 0.01:  # 已在此點
            continue
        if speed_left < seg_dist - 0.01:
            break
        old_x, old_y = actor.x, actor.y
        res = move_entity(actor, wp.x, wp.y, map_state, speed_left)
        if not res.success:
            break
        combat_state.turn_state.movement_remaining = res.speed_remaining
        if check_oa_for_step(
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
            log.log(
                f"[cyan]🚶 {display_name(mover)} 移動到 ({actor.x:.1f}, {actor.y:.1f})"
                f"（剩餘 {combat_state.turn_state.movement_remaining:.1f}m）[/]"
            )
            return True

    if actor.x != start_x or actor.y != start_y:
        log.log(
            f"[cyan]🚶 {display_name(mover)} 移動到 ({actor.x:.1f}, {actor.y:.1f})"
            f"（剩餘 {combat_state.turn_state.movement_remaining:.1f}m）[/]"
        )
    return False


# ---------------------------------------------------------------------------
# 藉機攻擊
# ---------------------------------------------------------------------------


def check_oa_for_step(
    mover: Character | Monster,
    old_x: float,
    old_y: float,
    new_x: float,
    new_y: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
) -> bool:
    """檢查移動一步時是否觸發藉機攻擊。回傳 True 表示 mover 倒下。"""
    results = check_opportunity_attacks_on_step(
        mover,
        old_x,
        old_y,
        new_x,
        new_y,
        combat_state,
        map_state,
        combatant_map,
        characters,
        monsters,
    )

    for step_oa in results:
        enemy_name = display_name(step_oa.attacker)
        mover_name = display_name(mover)
        oa = step_oa.oa_result
        weapon = step_oa.weapon

        if oa.attack_result and oa.attack_result.is_hit and oa.damage_result:
            apply_result = apply_damage(
                mover,
                oa.damage_result.total,
                weapon.damage_type,
                oa.attack_result.is_critical,
            )
            log.log(
                f"[bold red]⚡ 藉機攻擊！{enemy_name} 用 {weapon.name} "
                f"攻擊離開觸及範圍的 {mover_name} "
                f"— 造成 {apply_result.actual_damage} 點 "
                f"{zh_dmg(weapon.damage_type)} 傷害 "
                f"（HP: {mover.hp_current}/{mover.hp_max}）[/]"
            )
            if not mover.is_alive:
                log.log(f"  [bold red]☠️  {mover_name} 被藉機攻擊擊倒！[/]")
                return True
        else:
            log.log(f"[dim]⚡ 藉機攻擊！{enemy_name} 攻擊離開的 {mover_name} — 未中[/]")

    return False


# ---------------------------------------------------------------------------
# 攻擊執行
# ---------------------------------------------------------------------------


def execute_attack(
    attacker: Character | Monster,
    target: Character | Monster,
    combat_state: CombatState,
    log: LogManager,
) -> None:
    """執行一次武器攻擊。"""
    if not can_take_action(attacker):
        log.log(f"[yellow]{display_name(attacker)} 無法行動！[/]")
        return

    if not use_action(combat_state):
        log.log("[yellow]本回合已使用過動作！[/]")
        return

    weapon: Weapon | MonsterAction
    if isinstance(attacker, Monster):
        if not attacker.actions:
            log.log(f"[yellow]{display_name(attacker)} 沒有可用動作。[/]")
            return
        weapon = attacker.actions[0]
    else:
        if not attacker.weapons:
            log.log(f"[yellow]{display_name(attacker)} 沒有武器！[/]")
            return
        weapon = attacker.weapons[0]

    atk_bonus = get_attack_bonus(attacker, weapon)
    target_ac = target.ac
    attack_result = resolve_attack(atk_bonus, target_ac)

    atk_name = display_name(attacker)
    tgt_name = display_name(target)
    wpn_name = weapon.name
    roll_val = attack_result.roll_result.total

    if attack_result.is_critical:
        log.log(
            f"[bold red]💥 {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
            f"— 擲骰 {roll_val} vs AC {target_ac} — 爆擊！[/]"
        )
    elif attack_result.is_hit:
        log.log(
            f"[green]🎯 {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
            f"— 擲骰 {roll_val} vs AC {target_ac} — 命中！[/]"
        )
    else:
        log.log(
            f"[dim]❌ {atk_name} 用 {wpn_name} 攻擊 {tgt_name} "
            f"— 擲骰 {roll_val} vs AC {target_ac} — 未中[/]"
        )
        return

    dmg_mod = get_damage_modifier(attacker, weapon)
    dmg_type = weapon.damage_type
    dmg_result = roll_damage(
        weapon.damage_dice,
        dmg_type,
        modifier=dmg_mod,
        is_critical=attack_result.is_critical,
    )

    apply_result = apply_damage(target, dmg_result.total, dmg_type, attack_result.is_critical)

    log.log(
        f"  💥 造成 [bold]{apply_result.actual_damage}[/] 點 {zh_dmg(dmg_type)} 傷害 "
        f"（{tgt_name} HP: {target.hp_current}/{target.hp_max}）"
    )

    if apply_result.target_dropped_to_zero:
        if isinstance(target, Monster):
            log.log(f"  [bold red]☠️  {tgt_name} 被擊倒了！[/]")
        else:
            log.log(f"  [bold yellow]⚠️  {tgt_name} 倒下了！[/]")

    if apply_result.instant_death:
        log.log(f"  [bold red]💀 {tgt_name} 即死！[/]")


# ---------------------------------------------------------------------------
# 自動移動建議
# ---------------------------------------------------------------------------


def simulate_move_to_range(
    attacker_id: UUID,
    target_id: UUID,
    reach_m: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
) -> tuple[float, float, float, list[Position]] | None:
    """模擬 A* 移動到攻擊/法術範圍。

    回傳 (x_m, y_m, 移動消耗, 路徑) 或 None。
    路徑用於 step_move_to 直接沿路徑點移動。
    """
    return path_to_attack_range(
        attacker_id,
        target_id,
        reach_m,
        combat_state,
        map_state,
        combatant_map,
        characters,
        monsters,
    )


# ---------------------------------------------------------------------------
# 玩家移動
# ---------------------------------------------------------------------------


async def player_move(
    character: Character,
    x: float,
    y: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
    after_action_fn,
    check_combat_end_fn,
    show_action_choices_fn,
) -> None:
    """玩家移動到目標座標（公尺）。"""
    import math

    actor = get_actor(character.id, map_state)
    if not actor:
        log.log("[red]找不到角色位置。[/]")
        return

    remaining = combat_state.turn_state.movement_remaining
    mover_size = getattr(character, "size", Size.MEDIUM)
    mover_radius = SIZE_RADIUS_M.get(mover_size, 0.75)

    # 歐幾里得距離成本
    dx = x - actor.x
    dy = y - actor.y
    cost = math.sqrt(dx * dx + dy * dy)

    if cost < 0.01:
        log.log("[yellow]你已經在這個位置了。[/]")
        show_action_choices_fn()
        return

    if cost > remaining + 0.01:
        log.log(f"[red]移動距離不足！需要 {cost:.1f}m，剩餘 {remaining:.1f}m[/]")
        show_action_choices_fn()
        return

    target_pos = Position(x=x, y=y)

    # 靜態障礙碰撞
    old_blocking = actor.is_blocking
    actor.is_blocking = False
    clear = is_position_clear(target_pos, mover_radius, map_state)
    can_stop = can_end_move_at(target_pos, mover_size, map_state, mover_id=actor.id)
    actor.is_blocking = old_blocking

    if not clear:
        log.log(f"[red]目標位置 ({x:.1f}, {y:.1f}) 不可通行！[/]")
        show_action_choices_fn()
        return

    if not can_stop:
        log.log(f"[red]不可在目標位置 ({x:.1f}, {y:.1f}) 停留（有其他生物）！[/]")
        show_action_choices_fn()
        return

    # 嘗試 A* 尋路（處理障礙物繞行）
    lists = build_actor_lists(actor, character, map_state, characters, monsters)

    path = find_path_to_range(
        start=Position(x=actor.x, y=actor.y),
        target=target_pos,
        reach_m=0.01,  # 要到達目標本身
        map_state=map_state,
        mover_radius=mover_radius,
        max_cost=remaining,
        blocked_actors=lists.blocked,
        passable_actors=lists.passable,
    )

    if path is None:
        log.log(f"[red]無法到達目標位置 ({x:.1f}, {y:.1f})！[/]")
        show_action_choices_fn()
        return

    killed = step_move_to(
        character,
        actor,
        x,
        y,
        combat_state,
        map_state,
        combatant_map,
        characters,
        monsters,
        log,
        path=path if path else None,
    )
    refresh_all_fn()
    if killed:
        await check_combat_end_fn()
        return
    await after_action_fn()


# ---------------------------------------------------------------------------
# 玩家攻擊
# ---------------------------------------------------------------------------


async def player_attack(
    attacker: Character,
    target_name: str,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
    after_action_fn,
    check_combat_end_fn,
    show_action_choices_fn,
    set_confirm_state_fn,
) -> None:
    """玩家武器攻擊。"""
    from tot.tui.combat_bridge import find_target

    target = find_target(target_name, characters, monsters)
    if not target:
        log.log(f"[red]找不到目標：{target_name}[/]")
        alive = [m.label or m.name for m in monsters if m.is_alive]
        log.log(f"[dim]可攻擊目標：{', '.join(alive)}[/]")
        return
    if not target.is_alive:
        log.log(f"[yellow]{display_name(target)} 已經倒下了。[/]")
        return

    if map_state:
        atk_pos = get_actor_position(attacker.id, map_state)
        tgt_pos = get_actor_position(target.id, map_state)
        if atk_pos and tgt_pos:
            dist_m = distance(atk_pos, tgt_pos)
            if attacker.weapons:
                weapon = attacker.weapons[0]
                err = validate_attack_preconditions(
                    attacker,
                    weapon,
                    combat_state,
                    dist=dist_m,
                )
                if err and err != "行動已使用":
                    reach = weapon.range_normal
                    sim = simulate_move_to_range(
                        attacker.id,
                        target.id,
                        reach,
                        combat_state,
                        map_state,
                        combatant_map,
                        characters,
                        monsters,
                    )
                    if sim:
                        mx, my, mcost, _sim_path = sim
                        log.log(
                            f"[yellow]距離不足！移動到 ({mx:.1f}, {my:.1f}) "
                            f"後攻擊？消耗 {mcost:.1f}m 移動（y/n）[/]"
                        )
                        set_confirm_state_fn(
                            Position(x=mx, y=my),
                            target,
                            "weapon",
                            None,
                        )
                        return
                    log.log(f"[red]{err}（距離 {dist_m:.1f}m，移動距離不足以接近）[/]")
                    show_action_choices_fn()
                    return

    execute_attack(attacker, target, combat_state, log)
    refresh_all_fn()
    if await check_combat_end_fn():
        return
    await after_action_fn()


# ---------------------------------------------------------------------------
# 玩家施法
# ---------------------------------------------------------------------------


async def player_cast(
    caster: Character,
    spell: Spell,
    target: Character | Monster | None,
    combat_state: CombatState,
    map_state: MapState | None,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
    after_action_fn,
    check_combat_end_fn,
    show_action_choices_fn,
    set_confirm_state_fn,
    clear_pending_spell_fn,
) -> None:
    """執行施法。"""
    if target and map_state:
        caster_pos = get_actor_position(caster.id, map_state)
        tgt_pos = get_actor_position(target.id, map_state)
        if caster_pos and tgt_pos:
            dist = distance(caster_pos, tgt_pos)
            range_err = validate_spell_range(spell, dist)
            if range_err:
                range_m = parse_spell_range_meters(spell.range)
                reach = range_m if range_m else 1.5
                sim = simulate_move_to_range(
                    caster.id,
                    target.id,
                    reach,
                    combat_state,
                    map_state,
                    combatant_map,
                    characters,
                    monsters,
                )
                if sim:
                    mx, my, mcost, _sim_path = sim
                    log.log(
                        f"[yellow]法術射程不足！移動到 ({mx:.1f}, {my:.1f}) "
                        f"後施放？消耗 {mcost:.1f}m 移動（y/n）[/]"
                    )
                    set_confirm_state_fn(
                        Position(x=mx, y=my),
                        target,
                        "spell",
                        spell,
                    )
                    return
                log.log(f"[red]{range_err}[/]")
                clear_pending_spell_fn()
                show_action_choices_fn()
                return

    if spell.level > 0 and not use_action(combat_state):
        log.log("[yellow]本回合已使用過動作！[/]")
        return

    slot = spell.level if spell.level > 0 else None
    result = cast_spell(caster, spell, target, slot_level=slot)
    log.log(f"[magenta]✨ {result.message}[/]")

    if result.concentration_broken:
        log.log(f"[yellow]（專注中斷：{result.concentration_broken}）[/]")
    if result.concentration_started:
        log.log(f"[dim]（開始專注：{spell.name}）[/]")

    clear_pending_spell_fn()
    refresh_all_fn()

    if await check_combat_end_fn():
        return

    if spell.level == 0 and not combat_state.turn_state.action_used:
        use_action(combat_state)

    await after_action_fn()


async def player_cast_by_name(
    caster: Character,
    spell_name: str,
    combat_state: CombatState,
    map_state: MapState | None,
    combatant_map: dict[UUID, Character | Monster],
    characters: list[Character],
    monsters: list[Monster],
    log: LogManager,
    refresh_all_fn,
    after_action_fn,
    check_combat_end_fn,
    show_action_choices_fn,
    set_confirm_state_fn,
    clear_pending_spell_fn,
    set_pending_spell_fn,
    show_spell_target_choices_fn,
) -> None:
    """透過指令名稱施法。"""
    from tot.gremlins.bone_engine.spells import get_spell_by_name

    spell = get_spell_by_name(spell_name)
    if not spell:
        log.log(f"[red]找不到法術：{spell_name}[/]")
        return
    error = can_cast(caster, spell, slot_level=spell.level if spell.level > 0 else None)
    if error is not None:
        log.log(f"[red]無法施放：{error.reason}[/]")
        return
    if spell.effect_type.value in ("damage", "healing", "condition"):
        set_pending_spell_fn(spell)
        show_spell_target_choices_fn()
    else:
        await player_cast(
            caster,
            spell,
            None,
            combat_state,
            map_state,
            combatant_map,
            characters,
            monsters,
            log,
            refresh_all_fn,
            after_action_fn,
            check_combat_end_fn,
            show_action_choices_fn,
            set_confirm_state_fn,
            clear_pending_spell_fn,
        )
