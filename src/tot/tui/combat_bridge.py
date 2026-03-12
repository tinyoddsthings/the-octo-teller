"""TUI 共用工具函式、常數、格式化方法。

被所有 TUI 子模組引用，只 import models 層，不 import app。
避免 circular import 的基石。
"""

from __future__ import annotations

from uuid import UUID

from tot.gremlins.bone_engine.movement import build_friendly_ids as build_friendly_ids
from tot.gremlins.bone_engine.spells import get_spell_by_name
from tot.models import (
    Ability,
    Actor,
    Character,
    DamageType,
    Monster,
    MonsterAction,
    Position,
    Weapon,
)

# ---------------------------------------------------------------------------
# 傷害類型中文化
# ---------------------------------------------------------------------------

DAMAGE_TYPE_ZH: dict[str, str] = {
    "Acid": "強酸",
    "Bludgeoning": "鈍擊",
    "Cold": "寒冷",
    "Fire": "火焰",
    "Force": "力場",
    "Lightning": "閃電",
    "Necrotic": "黯蝕",
    "Piercing": "穿刺",
    "Poison": "毒素",
    "Psychic": "心靈",
    "Radiant": "光輝",
    "Slashing": "揮砍",
    "Thunder": "雷鳴",
}


def zh_dmg(dmg_type: DamageType) -> str:
    """傷害類型中文翻譯。"""
    return DAMAGE_TYPE_ZH.get(dmg_type.value, dmg_type.value)


# ---------------------------------------------------------------------------
# 方向對照表
# ---------------------------------------------------------------------------

DIRECTION_MAP: dict[str, tuple[int, int]] = {
    "n": (0, 1),
    "north": (0, 1),
    "上": (0, 1),
    "s": (0, -1),
    "south": (0, -1),
    "下": (0, -1),
    "e": (1, 0),
    "east": (1, 0),
    "右": (1, 0),
    "w": (-1, 0),
    "west": (-1, 0),
    "左": (-1, 0),
    "ne": (1, 1),
    "northeast": (1, 1),
    "右上": (1, 1),
    "nw": (-1, 1),
    "northwest": (-1, 1),
    "左上": (-1, 1),
    "se": (1, -1),
    "southeast": (1, -1),
    "右下": (1, -1),
    "sw": (-1, -1),
    "southwest": (-1, -1),
    "左下": (-1, -1),
}

# ---------------------------------------------------------------------------
# 攻擊加值計算
# ---------------------------------------------------------------------------


def get_attack_bonus(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算攻擊加值。"""
    if isinstance(weapon, MonsterAction):
        return weapon.attack_bonus or 0
    if weapon.is_finesse:
        str_mod = combatant.ability_scores.modifier(Ability.STR)
        dex_mod = combatant.ability_scores.modifier(Ability.DEX)
        ability_mod = max(str_mod, dex_mod)
    elif weapon.is_ranged:
        ability_mod = combatant.ability_scores.modifier(Ability.DEX)
    else:
        ability_mod = combatant.ability_scores.modifier(Ability.STR)
    return ability_mod + combatant.proficiency_bonus


def get_damage_modifier(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算傷害修正值。"""
    if isinstance(weapon, MonsterAction):
        return combatant.ability_scores.modifier(Ability.DEX)
    if weapon.is_finesse:
        str_mod = combatant.ability_scores.modifier(Ability.STR)
        dex_mod = combatant.ability_scores.modifier(Ability.DEX)
        return max(str_mod, dex_mod)
    if weapon.is_ranged:
        return combatant.ability_scores.modifier(Ability.DEX)
    return combatant.ability_scores.modifier(Ability.STR)


# ---------------------------------------------------------------------------
# 查找輔助
# ---------------------------------------------------------------------------


def display_name(combatant: Character | Monster) -> str:
    """取得顯示名稱。"""
    if isinstance(combatant, Monster):
        return combatant.label or combatant.name
    return combatant.name


def find_target(
    name: str,
    characters: list[Character],
    monsters: list[Monster],
) -> Character | Monster | None:
    """模糊搜尋目標名稱。"""
    name_lower = name.lower()
    for m in monsters:
        label = (m.label or m.name).lower()
        if label == name_lower or m.name.lower() == name_lower:
            return m
    for m in monsters:
        label = (m.label or m.name).lower()
        if name_lower in label or name_lower in m.name.lower():
            return m
    for c in characters:
        if c.name.lower() == name_lower or name_lower in c.name.lower():
            return c
    return None


def pos_to_grid(x: float, y: float, grid_size: float) -> tuple[int, int]:
    """公尺座標轉 grid 座標（顯示用）。"""
    return Position(x=x, y=y).to_grid(grid_size)


def is_npc_turn(combatant: Character | Monster | None) -> bool:
    """判斷是否為 NPC（怪物或 AI 角色）回合。"""
    if isinstance(combatant, Monster):
        return True
    return isinstance(combatant, Character) and combatant.is_ai_controlled


def is_in_enemy_reach(
    combatant: Character | Monster,
    map_state,
    combatant_map: dict[UUID, Character | Monster],
) -> bool:
    """檢查角色是否在任何敵方的觸及範圍內。"""
    from tot.gremlins.bone_engine.spatial import distance

    if not map_state:
        return False
    actor = get_actor(combatant.id, map_state)
    if not actor:
        return False
    for other in map_state.actors:
        if other.combatant_id == combatant.id or not other.is_alive:
            continue
        enemy = combatant_map.get(other.combatant_id)
        if not enemy:
            continue
        if isinstance(combatant, Character) and isinstance(enemy, Character):
            continue
        if isinstance(combatant, Monster) and isinstance(enemy, Monster):
            continue
        reach_m = 1.5
        if isinstance(enemy, Character) and enemy.weapons:
            reach_m = enemy.weapons[0].range_normal
        elif isinstance(enemy, Monster) and enemy.actions:
            reach_m = enemy.actions[0].reach
        dist = distance(Position(x=other.x, y=other.y), Position(x=actor.x, y=actor.y))
        if dist <= reach_m:
            return True
    return False


def get_actor(combatant_id: UUID, map_state) -> Actor | None:
    """以 UUID 查詢 Actor。"""
    if not map_state:
        return None
    for a in map_state.actors:
        if a.combatant_id == combatant_id:
            return a
    return None


# ---------------------------------------------------------------------------
# 格式化方法
# ---------------------------------------------------------------------------


def format_status(combatant: Character | Monster) -> str:
    """格式化完整角色狀態。"""
    name = display_name(combatant)
    lines = [f"\n[bold cyan]── {name} 狀態 ──[/]"]

    if isinstance(combatant, Character):
        lines.append(f"  等級 {combatant.level} {combatant.char_class}")
    else:
        lines.append(f"  CR {combatant.challenge_rating}")

    lines.append(f"  HP: {combatant.hp_current}/{combatant.hp_max}  AC: {combatant.ac}")

    scores = combatant.ability_scores
    stats = []
    for ab in Ability:
        val = scores.score(ab)
        mod = scores.modifier(ab)
        sign = "+" if mod >= 0 else ""
        stats.append(f"{ab.value} {val}({sign}{mod})")
    lines.append(f"  {' | '.join(stats)}")

    if isinstance(combatant, Character) and combatant.weapons:
        wpns = ", ".join(w.name for w in combatant.weapons)
        lines.append(f"  武器: {wpns}")
    elif isinstance(combatant, Monster) and combatant.actions:
        acts = ", ".join(a.name for a in combatant.actions)
        lines.append(f"  動作: {acts}")

    if combatant.conditions:
        conds = ", ".join(c.condition.value for c in combatant.conditions)
        lines.append(f"  狀態異常: [yellow]{conds}[/]")

    if isinstance(combatant, Character) and combatant.spell_dc:
        lines.append(f"  法術 DC: {combatant.spell_dc}  攻擊: +{combatant.spell_attack}")

    return "\n".join(lines)


def format_conditions(
    characters: list[Character],
    monsters: list[Monster],
) -> str:
    """所有戰場上的狀態異常。"""
    lines = ["\n[bold yellow]── 戰場狀態異常 ──[/]"]
    found = False
    all_combatants: list[Character | Monster] = [*characters, *monsters]
    for c in all_combatants:
        if c.conditions:
            name = display_name(c)
            for ac in c.conditions:
                remaining = (
                    f"（{ac.remaining_rounds} 輪）"
                    if ac.remaining_rounds is not None
                    else "（持續）"
                )
                lines.append(f"  {name}: {ac.condition.value} {remaining}")
            found = True
    if not found:
        lines.append("  [dim]無任何狀態異常[/]")
    return "\n".join(lines)


def format_initiative(
    combat_state,
    combatant_map: dict[UUID, Character | Monster],
) -> str:
    """完整先攻順序。"""
    if not combat_state:
        return ""
    lines = ["\n[bold cyan]── 先攻順序 ──[/]"]
    for idx, entry in enumerate(combat_state.initiative_order):
        combatant = combatant_map.get(entry.combatant_id)
        if not combatant:
            continue
        name = display_name(combatant)
        marker = " ◀ 當前" if idx == combat_state.current_turn_index else ""
        alive = "" if combatant.is_alive else " [red]💀[/]"
        lines.append(f"  {entry.initiative:2d} — {name}{alive}{marker}")
    return "\n".join(lines)


def format_spells(char: Character) -> str:
    """法術列表 + 剩餘欄位。"""
    lines = [f"\n[bold magenta]── {char.name} 法術 ──[/]"]

    if char.spell_slots.max_slots:
        slot_parts = []
        for lvl in sorted(char.spell_slots.max_slots.keys()):
            cur = char.spell_slots.current_slots.get(lvl, 0)
            mx = char.spell_slots.max_slots[lvl]
            slot_parts.append(f"{lvl}環: {cur}/{mx}")
        lines.append(f"  欄位: {' | '.join(slot_parts)}")

    spell_names = list(dict.fromkeys(char.spells_prepared + char.spells_known))
    if spell_names:
        for name in spell_names:
            spell = get_spell_by_name(name)
            if spell:
                level_str = "戲法" if spell.level == 0 else f"{spell.level}環"
                lines.append(f"  • {spell.name} ({level_str}) — {spell.description[:40]}")
    else:
        lines.append("  [dim]無已準備法術[/]")

    if char.concentration_spell:
        lines.append(f"  [yellow]專注中: {char.concentration_spell}[/]")

    return "\n".join(lines)


def show_help(log_fn) -> None:
    """顯示完整指令說明。"""
    log_fn("\n[bold white]── 指令說明 ──[/]")
    log_fn("[cyan]查詢指令[/]（不消耗動作）：")
    log_fn("  status          — 當前角色狀態")
    log_fn("  status <名字>   — 指定角色/怪物狀態")
    log_fn("  conditions      — 所有戰場狀態異常")
    log_fn("  initiative      — 先攻順序")
    log_fn("  spells          — 法術列表 + 剩餘欄位")
    log_fn("  map             — 重新渲染地圖")
    log_fn("  help            — 本說明")
    log_fn("[cyan]動作指令[/]：")
    log_fn("  move x y        — 移動到座標 (x, y)")
    log_fn("  move 方向       — 方向移動（n/s/e/w/ne/nw/se/sw）")
    log_fn("  attack <目標>   — 武器攻擊（消耗動作）")
    log_fn("  cast <法術名>   — 施放法術（消耗動作）")
    log_fn("  dodge           — 閃避（消耗動作）")
    log_fn("  disengage       — 撤離（消耗動作，安全離開觸及範圍）")
    log_fn("  end             — 結束回合")
    log_fn("  quit            — 離開遊戲")
    log_fn("[dim]也可使用數字選單選擇動作。[/]")
