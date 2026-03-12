"""Bone Engine 戰鬥引擎。

處理先攻、回合順序、攻擊骰、傷害、死亡豁免、專注檢定、
掩蔽、擒抱/推撞、武器專精、借機攻擊、雙持武器與英雄激勵。
所有戰鬥機制都是確定性的（給定骰子結果），遵循 D&D 2024 規則。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from uuid import UUID

from tot.gremlins.bone_engine.conditions import (
    apply_condition,
    can_take_action,
    exhaustion_penalty,
)
from tot.gremlins.bone_engine.dice import DiceResult, RollType, roll, roll_d20
from tot.gremlins.bone_engine.spatial import distance
from tot.models import (
    Ability,
    ActiveCondition,
    Character,
    Combatant,
    CombatState,
    Condition,
    CoverType,
    DamageType,
    InitiativeEntry,
    MapState,
    Monster,
    MonsterAction,
    Position,
    Size,
    TurnState,
    Weapon,
    WeaponProperty,
)

# ---------------------------------------------------------------------------
# 全域輔助函式
# ---------------------------------------------------------------------------

# 體型排序對照表，用於擒抱/推撞體型限制
_SIZE_ORDER = {
    Size.TINY: 0,
    Size.SMALL: 1,
    Size.MEDIUM: 2,
    Size.LARGE: 3,
    Size.HUGE: 4,
    Size.GARGANTUAN: 5,
}


def _size_index(size: Size) -> int:
    """取得體型的排序索引。"""
    return _SIZE_ORDER[size]


def _get_size(combatant: Combatant) -> Size:
    """統一取得戰鬥者的體型。"""
    return combatant.size


def can_grapple_size(attacker_size: Size, target_size: Size) -> bool:
    """檢查攻擊者是否能擒抱目標（目標不超過攻擊者一個體型等級）。"""
    return _size_index(target_size) <= _size_index(attacker_size) + 1


def grapple_save_dc(attacker: Combatant) -> int:
    """計算擒抱/推撞/Topple 的豁免 DC。

    DC = 8 + 力量修正 + 熟練加值。
    """
    str_mod = attacker.ability_scores.modifier(Ability.STR)
    return 8 + str_mod + attacker.proficiency_bonus


# ---------------------------------------------------------------------------
# 武器攻擊加值 / 傷害修正（集中 API）
# ---------------------------------------------------------------------------


def _weapon_ability_mod(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """取得武器對應的屬性修正值（內部共用）。"""
    if isinstance(weapon, MonsterAction):
        return combatant.ability_scores.modifier(Ability.DEX)
    if weapon.is_finesse:
        str_mod = combatant.ability_scores.modifier(Ability.STR)
        dex_mod = combatant.ability_scores.modifier(Ability.DEX)
        return max(str_mod, dex_mod)
    if weapon.is_ranged:
        return combatant.ability_scores.modifier(Ability.DEX)
    return combatant.ability_scores.modifier(Ability.STR)


def calc_weapon_attack_bonus(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算武器攻擊加值。

    MonsterAction 直接回傳其 attack_bonus；
    Weapon 則依 Finesse/Ranged 規則選擇屬性修正 + 熟練加值。
    """
    if isinstance(weapon, MonsterAction):
        return weapon.attack_bonus or 0
    return _weapon_ability_mod(combatant, weapon) + combatant.proficiency_bonus


def calc_damage_modifier(combatant: Character | Monster, weapon: Weapon | MonsterAction) -> int:
    """計算武器傷害修正值。

    依 Finesse/Ranged 規則選擇屬性修正。
    """
    return _weapon_ability_mod(combatant, weapon)


# ---------------------------------------------------------------------------
# 掩蔽系統
# ---------------------------------------------------------------------------

_COVER_AC_BONUS = {
    CoverType.NONE: 0,
    CoverType.HALF: 2,
    CoverType.THREE_QUARTERS: 5,
    CoverType.TOTAL: 0,  # 完全掩蔽無法被直接攻擊，由上層處理
}

_COVER_SAVE_BONUS = {
    CoverType.NONE: 0,
    CoverType.HALF: 2,
    CoverType.THREE_QUARTERS: 5,
    CoverType.TOTAL: 0,
}


def apply_cover_to_ac(base_ac: int, cover: CoverType) -> int:
    """計算含掩蔽的有效 AC。"""
    return base_ac + _COVER_AC_BONUS[cover]


def cover_save_bonus(cover: CoverType) -> int:
    """掩蔽對 DEX 豁免的加值。"""
    return _COVER_SAVE_BONUS[cover]


# ---------------------------------------------------------------------------
# 先攻
# ---------------------------------------------------------------------------


def roll_initiative(
    dex_modifier: int,
    bonus: int = 0,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> DiceResult:
    """擲先攻：d20 + 敏捷修正 + 額外加值。

    突襲時可傳入 RollType.DISADVANTAGE。
    """
    return roll_d20(
        modifier=dex_modifier + bonus,
        roll_type=roll_type,
        rng=rng,
    )


def build_initiative_order(
    characters: list[Character],
    monsters: list[Monster],
    surprised_ids: set[UUID] | None = None,
    rng: random.Random | None = None,
) -> list[InitiativeEntry]:
    """為所有戰鬥者擲先攻並回傳排序後的順序。

    同值處理：角色優先於怪物，然後按敏捷修正高者優先。
    受突襲者以劣勢擲先攻，且標記 is_surprised=True。
    """
    surprised_ids = surprised_ids or set()
    entries: list[tuple[int, int, int, InitiativeEntry]] = []

    for char in characters:
        is_surprised = char.id in surprised_ids
        rt = RollType.DISADVANTAGE if is_surprised else RollType.NORMAL
        result = roll_initiative(char.initiative_bonus, roll_type=rt, rng=rng)
        entry = InitiativeEntry(
            combatant_type="character",
            combatant_id=char.id,
            initiative=result.total,
            is_surprised=is_surprised,
        )
        dex = char.ability_modifier(Ability.DEX)
        entries.append((-result.total, 0, -dex, entry))

    for mon in monsters:
        is_surprised = mon.id in surprised_ids
        rt = RollType.DISADVANTAGE if is_surprised else RollType.NORMAL
        result = roll_initiative(
            mon.ability_scores.modifier(Ability.DEX),
            roll_type=rt,
            rng=rng,
        )
        entry = InitiativeEntry(
            combatant_type="monster",
            combatant_id=mon.id,
            initiative=result.total,
            is_surprised=is_surprised,
        )
        dex = mon.ability_modifier(Ability.DEX)
        entries.append((-result.total, 1, -dex, entry))

    entries.sort(key=lambda x: (x[0], x[1], x[2]))
    return [e[3] for e in entries]


def start_combat(
    characters: list[Character],
    monsters: list[Monster],
    surprised_ids: set[UUID] | None = None,
    rng: random.Random | None = None,
) -> CombatState:
    """初始化戰鬥遭遇。"""
    order = build_initiative_order(
        characters,
        monsters,
        surprised_ids=surprised_ids,
        rng=rng,
    )
    return CombatState(
        round_number=1,
        current_turn_index=0,
        initiative_order=order,
        is_active=True,
    )


def advance_turn(state: CombatState) -> CombatState:
    """推進至下一回合。

    - 重置當前回合的 TurnState
    - 清除當前戰鬥者的 is_surprised
    - 重置當前戰鬥者的 reaction_used
    - 所有人都行動過後進入下一輪
    """
    if not state.is_active:
        return state

    # 清除當前回合者的突襲狀態
    current_entry = state.initiative_order[state.current_turn_index]
    current_entry.is_surprised = False

    # 推進索引
    next_index = state.current_turn_index + 1
    if next_index >= len(state.initiative_order):
        next_index = 0
        state.round_number += 1

    state.current_turn_index = next_index

    # 重置新回合者的動作經濟
    state.turn_state = TurnState()
    new_entry = state.initiative_order[next_index]
    new_entry.reaction_used = False

    return state


# ---------------------------------------------------------------------------
# 動作經濟
# ---------------------------------------------------------------------------


def use_action(state: CombatState) -> bool:
    """嘗試消耗行動。回傳是否成功。"""
    if state.turn_state.action_used:
        return False
    state.turn_state.action_used = True
    return True


def use_bonus_action(state: CombatState) -> bool:
    """嘗試消耗附贈動作。回傳是否成功。"""
    if state.turn_state.bonus_action_used:
        return False
    state.turn_state.bonus_action_used = True
    return True


def use_reaction(entry: InitiativeEntry) -> bool:
    """嘗試消耗反應（跨回合追蹤，儲存在 InitiativeEntry）。"""
    if entry.reaction_used:
        return False
    entry.reaction_used = True
    return True


# ---------------------------------------------------------------------------
# 無力化連鎖效應
# ---------------------------------------------------------------------------


def check_incapacitated_effects(combatant: Character | Monster) -> str | None:
    """無力化時自動中斷專注。回傳失去的法術名稱。

    當生物進入無力化狀態（或包含無力化的狀態）時呼叫。
    """
    if (
        not can_take_action(combatant)
        and isinstance(combatant, Character)
        and combatant.concentration_spell
    ):
        return break_concentration(combatant)
    return None


# ---------------------------------------------------------------------------
# 攻擊判定
# ---------------------------------------------------------------------------


@dataclass
class AttackResult:
    """攻擊骰結果。"""

    roll_result: DiceResult
    target_ac: int
    is_hit: bool
    is_critical: bool
    is_auto_crit: bool = False
    grants_inspiration: bool = False  # 自然 20 → 給予英雄激勵
    inspiration_overflow: bool = False  # 已有激勵時自然 20 → 溢出可轉贈


def validate_attack_preconditions(
    attacker: Character | Monster,
    weapon: Weapon,
    state: CombatState,
    dist: float = 1.5,
) -> str | None:
    """驗證攻擊的前置條件，回傳錯誤訊息或 None 表示通過。"""
    if not can_take_action(attacker):
        return "攻擊者無力化，無法行動"
    if state.turn_state.action_used:
        return "行動已使用"
    # 近戰：range_normal 已是公尺（1.5=近戰、3.0=長觸及）
    if not weapon.is_ranged:
        reach_m = weapon.range_normal
        if dist > reach_m:
            return f"目標超出近戰射程（射程 {reach_m:.1f}m，距離 {dist:.1f}m）"
    else:
        # 遠程武器長射程檢查
        max_range = weapon.range_long or weapon.range_normal
        if dist > max_range:
            return f"目標超出武器最大射程（{max_range}m，當前 {dist:.1f}m）"
    return None


def resolve_attack(
    attack_bonus: int,
    target_ac: int,
    roll_type: RollType = RollType.NORMAL,
    auto_crit: bool = False,
    exhaustion_level: int = 0,
    cover: CoverType = CoverType.NONE,
    rng: random.Random | None = None,
) -> AttackResult:
    """對目標 AC 進行攻擊骰判定。

    參數:
        attack_bonus: 總攻擊修正值。
        target_ac: 目標護甲等級（未含掩蔽）。
        roll_type: 正常、優勢或劣勢。
        auto_crit: 命中時自動爆擊（例如麻痺目標在 1.5m 內）。
        exhaustion_level: 攻擊者的力竭等級（每級 -2）。
        cover: 目標的掩蔽類型。
        rng: 可選的 RNG，用於測試。
    """
    effective_ac = apply_cover_to_ac(target_ac, cover)
    effective_bonus = attack_bonus + exhaustion_penalty(exhaustion_level)

    result = roll_d20(modifier=effective_bonus, roll_type=roll_type, rng=rng)

    # 自然 1 必定未中，自然 20 必定命中且爆擊
    if result.is_nat1:
        return AttackResult(
            roll_result=result,
            target_ac=effective_ac,
            is_hit=False,
            is_critical=False,
        )

    is_critical = result.is_nat20
    is_hit = is_critical or result.total >= effective_ac

    if is_hit and auto_crit:
        is_critical = True

    # 自然 20 給予英雄激勵標記（由上層系統對角色設定）
    grants_inspiration = result.is_nat20

    return AttackResult(
        roll_result=result,
        target_ac=effective_ac,
        is_hit=is_hit,
        is_critical=is_critical,
        is_auto_crit=auto_crit and is_hit,
        grants_inspiration=grants_inspiration,
    )


# ---------------------------------------------------------------------------
# 傷害
# ---------------------------------------------------------------------------


@dataclass
class DamageResult:
    """傷害骰結果。"""

    roll_result: DiceResult
    damage_type: DamageType
    is_critical: bool = False
    total: int = 0


def roll_damage(
    damage_expression: str,
    damage_type: DamageType,
    modifier: int = 0,
    is_critical: bool = False,
    rng: random.Random | None = None,
) -> DamageResult:
    """擲傷害骰，爆擊時骰子數量加倍。

    參數:
        damage_expression: 基礎骰子，例如 "1d8"（修正值另外加）。
        damage_type: 傷害類型。
        modifier: 固定傷害修正（例如力量修正）。爆擊時不加倍。
        is_critical: 若為 True，骰子數量加倍。
        rng: 可選的 RNG，用於測試。
    """
    expr = damage_expression
    if is_critical:
        m = re.match(r"(\d*)d(\d+)", expr)
        if m:
            count = int(m.group(1)) if m.group(1) else 1
            sides = m.group(2)
            expr = f"{count * 2}d{sides}"

    result = roll(expr, rng=rng)
    total = result.total + modifier

    return DamageResult(
        roll_result=result,
        damage_type=damage_type,
        is_critical=is_critical,
        total=max(0, total),
    )


# ---------------------------------------------------------------------------
# 對生物施加傷害
# ---------------------------------------------------------------------------


@dataclass
class ApplyDamageResult:
    """施加傷害的完整結果。"""

    actual_damage: int
    target_dropped_to_zero: bool = False
    instant_death: bool = False
    death_save_failures_added: int = 0
    concentration_check_dc: int | None = None  # 目標維持專注時的檢定 DC


def apply_damage(
    target: Character | Monster,
    damage: int,
    damage_type: DamageType,
    is_critical: bool = False,
) -> ApplyDamageResult:
    """對目標施加傷害，考慮抗性、免疫、虛弱、臨時 HP、即死。

    參數:
        target: 受傷目標。
        damage: 原始傷害值。
        damage_type: 傷害類型。
        is_critical: 是否為爆擊（0 HP 受傷時爆擊 = 2 次死亡豁免失敗）。
    """
    actual = damage

    # 免疫（PC 與怪物統一處理）
    if damage_type in target.damage_immunities:
        return ApplyDamageResult(actual_damage=0)

    # 抗性（PC 與怪物統一處理）
    if damage_type in target.damage_resistances:
        actual = actual // 2

    # 石化：對所有傷害具有抗性
    if target.has_condition(Condition.PETRIFIED):
        actual = actual // 2

    # 虛弱 (Weakened)：傷害減半
    if target.has_condition(Condition.WEAKENED):
        actual = actual // 2

    result = ApplyDamageResult(actual_damage=actual)

    # 專注檢定 DC（目標維持專注時）
    has_concentration = isinstance(target, Character) and target.concentration_spell is not None
    if has_concentration and actual > 0:
        result.concentration_check_dc = max(10, actual // 2)

    # 目標已在 0 HP（角色倒地時受傷 → 死亡豁免失敗）
    if isinstance(target, Character) and target.hp_current == 0 and actual > 0:
        failures = 2 if is_critical else 1
        target.death_saves.failures = min(3, target.death_saves.failures + failures)
        result.death_save_failures_added = failures
        if target.death_saves.is_dead:
            result.instant_death = True
        return result

    hp_before = target.hp_current

    # 優先扣除臨時 HP
    if isinstance(target, Character) and target.hp_temp > 0:
        if actual <= target.hp_temp:
            target.hp_temp -= actual
            return result
        remaining = actual - target.hp_temp
        target.hp_temp = 0
        target.hp_current = max(0, target.hp_current - remaining)
    else:
        target.hp_current = max(0, target.hp_current - actual)

    # 檢查是否降至 0 HP
    if target.hp_current == 0 and hp_before > 0:
        result.target_dropped_to_zero = True

        # 即死判定：溢出傷害 >= hp_max（臨時 HP 已在上面扣完）
        if isinstance(target, Character):
            overflow = actual - hp_before
            if overflow >= target.hp_max:
                result.instant_death = True

        # HP 歸零 → 自動施加昏迷 + 倒地（D&D 5e 規則）
        apply_condition(target, Condition.UNCONSCIOUS, source="damage")
        apply_condition(target, Condition.PRONE, source="damage")

    return result


# ---------------------------------------------------------------------------
# 治療
# ---------------------------------------------------------------------------


@dataclass
class HealingResult:
    """治療結果。"""

    amount_healed: int
    was_at_zero: bool = False
    revived: bool = False


def apply_healing(target: Character, amount: int) -> HealingResult:
    """對角色施加治療。

    HP 不超過 hp_max。0 HP 治療 → 復甦、重置死亡豁免、移除昏迷/倒地。
    """
    was_at_zero = target.hp_current == 0
    old_hp = target.hp_current

    target.hp_current = min(target.hp_max, target.hp_current + amount)
    actual_healed = target.hp_current - old_hp

    revived = False
    if was_at_zero and target.hp_current > 0:
        revived = True
        target.death_saves.reset()
        target.conditions = [
            c
            for c in target.conditions
            if c.condition not in (Condition.UNCONSCIOUS, Condition.PRONE)
        ]

    return HealingResult(
        amount_healed=actual_healed,
        was_at_zero=was_at_zero,
        revived=revived,
    )


# ---------------------------------------------------------------------------
# 豁免檢定
# ---------------------------------------------------------------------------


@dataclass
class SaveResult:
    """豁免檢定結果。"""

    roll_result: DiceResult
    dc: int
    success: bool
    auto_fail: bool = False


def resolve_saving_throw(
    save_bonus: int,
    dc: int,
    ability: Ability,
    conditions: list[ActiveCondition] | None = None,
    roll_type: RollType = RollType.NORMAL,
    exhaustion_level: int = 0,
    cover: CoverType = CoverType.NONE,
    rng: random.Random | None = None,
) -> SaveResult:
    """對 DC 進行豁免檢定。

    處理：
    - 麻痺/震懾/昏迷/石化時 STR/DEX 豁免自動失敗
    - 力竭減值（每級 -2）
    - 掩蔽對 DEX 豁免的加值
    - 閃避 (DODGING) 對 DEX 豁免的優勢
    """
    conditions = conditions or []
    condition_set = {c.condition for c in conditions}

    # 麻痺、震懾、昏迷、石化時，力量/敏捷豁免自動失敗
    auto_fail_conditions = {
        Condition.PARALYZED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
        Condition.PETRIFIED,
    }
    if ability in (Ability.STR, Ability.DEX) and condition_set & auto_fail_conditions:
        dummy = DiceResult(expression="d20", rolls=[0], modifier=save_bonus)
        return SaveResult(
            roll_result=dummy,
            dc=dc,
            success=False,
            auto_fail=True,
        )

    # 計算有效加值
    effective_bonus = save_bonus + exhaustion_penalty(exhaustion_level)

    # 掩蔽對 DEX 豁免的加值
    if ability == Ability.DEX:
        effective_bonus += cover_save_bonus(cover)

    # 閃避 (DODGING)：DEX 豁免優勢
    effective_roll_type = roll_type
    if ability == Ability.DEX and Condition.DODGING in condition_set:
        if effective_roll_type == RollType.DISADVANTAGE:
            effective_roll_type = RollType.NORMAL  # 優劣抵消
        else:
            effective_roll_type = RollType.ADVANTAGE

    result = roll_d20(
        modifier=effective_bonus,
        roll_type=effective_roll_type,
        rng=rng,
    )
    success = result.total >= dc

    return SaveResult(roll_result=result, dc=dc, success=success)


# ---------------------------------------------------------------------------
# 專注檢定
# ---------------------------------------------------------------------------


def concentration_check(
    con_save_bonus: int,
    damage_taken: int,
    rng: random.Random | None = None,
) -> SaveResult:
    """擲專注檢定。DC = max(10, 受到傷害 / 2)。"""
    dc = max(10, damage_taken // 2)
    return resolve_saving_throw(con_save_bonus, dc, Ability.CON, rng=rng)


def break_concentration(character: Character) -> str | None:
    """中斷專注。回傳失去的法術名稱，若無則回傳 None。"""
    if character.concentration_spell:
        lost = character.concentration_spell
        character.concentration_spell = None
        return lost
    return None


# ---------------------------------------------------------------------------
# 死亡豁免
# ---------------------------------------------------------------------------


@dataclass
class DeathSaveOutcome:
    """死亡豁免結果。"""

    roll_result: DiceResult
    stabilized: bool = False
    died: bool = False
    revived: bool = False
    grants_inspiration: bool = False  # 自然 20 同時給予英雄激勵


def roll_death_save(
    character: Character,
    rng: random.Random | None = None,
) -> DeathSaveOutcome:
    """為倒地角色擲死亡豁免。

    - 自然 20：復甦（HP = 1）+ 自動獲得英雄激勵
    - 自然 1：累計 2 次失敗
    - >= 10：累計 1 次成功
    - < 10：累計 1 次失敗
    - 3 次成功：穩定
    - 3 次失敗：死亡
    """
    result = roll_d20(rng=rng)

    if result.is_nat20:
        character.death_saves.reset()
        character.hp_current = 1
        character.conditions = [
            c
            for c in character.conditions
            if c.condition not in (Condition.UNCONSCIOUS, Condition.PRONE)
        ]
        return DeathSaveOutcome(
            roll_result=result,
            revived=True,
            grants_inspiration=True,
        )

    if result.is_nat1:
        character.death_saves.failures = min(3, character.death_saves.failures + 2)
    elif result.total >= 10:
        character.death_saves.successes = min(3, character.death_saves.successes + 1)
    else:
        character.death_saves.failures = min(3, character.death_saves.failures + 1)

    stabilized = character.death_saves.is_stable
    died = character.death_saves.is_dead

    if stabilized:
        character.death_saves.reset()

    return DeathSaveOutcome(
        roll_result=result,
        stabilized=stabilized,
        died=died,
    )


# ---------------------------------------------------------------------------
# 閃避動作
# ---------------------------------------------------------------------------


def take_dodge_action(
    combatant: Character | Monster,
    state: CombatState,
) -> bool:
    """執行閃避動作。消耗行動，加上 DODGING 狀態（1 輪）。

    回傳是否成功。
    """
    if not can_take_action(combatant):
        return False
    if not use_action(state):
        return False

    combatant.conditions.append(
        ActiveCondition(
            condition=Condition.DODGING,
            source="Dodge action",
            remaining_rounds=1,
        )
    )
    return True


def take_disengage_action(
    combatant: Character | Monster,
    state: CombatState,
) -> bool:
    """執行撤離動作。消耗行動，加上 DISENGAGING 狀態（1 輪）。

    撤離後移動不會觸發藉機攻擊。回傳是否成功。
    """
    if not can_take_action(combatant):
        return False
    if not use_action(state):
        return False

    combatant.conditions.append(
        ActiveCondition(
            condition=Condition.DISENGAGING,
            source="Disengage action",
            remaining_rounds=1,
        )
    )
    return True


# ---------------------------------------------------------------------------
# 狀態對攻擊的影響
# ---------------------------------------------------------------------------


def get_attack_roll_type(
    attacker_conditions: list[ActiveCondition],
    target_conditions: list[ActiveCondition],
    is_melee: bool = True,
    is_ranged: bool = False,
    distance: float = 1.5,
    attacker_unseen: bool = False,
    target_unseen: bool = False,
    target_has_blindsight: bool = False,
    hostile_within_melee: bool = False,
) -> RollType:
    """根據狀態判斷攻擊時的優勢/劣勢。

    2024 版變更：
    - 隱形不再自動給優勢，改用 unseen 參數判斷「是否被看見」
    - 遠程攻擊在 1.5m 內有非無力化敵人 → 劣勢
    - 目標閃避中 (DODGING) → 攻擊者劣勢

    匯總所有來源；若同時有優勢和劣勢，互相抵消。
    """
    advantages = 0
    disadvantages = 0

    attacker_set = {c.condition for c in attacker_conditions}
    target_set = {c.condition for c in target_conditions}

    # --- 攻擊者狀態 ---

    # 2024: 隱形本身不給優勢，改看 unseen
    if attacker_unseen and not target_has_blindsight:
        advantages += 1

    if Condition.BLINDED in attacker_set:
        disadvantages += 1
    if Condition.FRIGHTENED in attacker_set:
        disadvantages += 1
    if Condition.POISONED in attacker_set:
        disadvantages += 1
    if Condition.PRONE in attacker_set:
        disadvantages += 1
    if Condition.RESTRAINED in attacker_set:
        disadvantages += 1

    # --- 目標狀態 ---

    # 2024: 隱形本身不給劣勢，改看 unseen
    if target_unseen:
        disadvantages += 1

    if Condition.BLINDED in target_set:
        advantages += 1
    if Condition.PARALYZED in target_set:
        advantages += 1
    if Condition.STUNNED in target_set:
        advantages += 1
    if Condition.UNCONSCIOUS in target_set:
        advantages += 1
    if Condition.RESTRAINED in target_set:
        advantages += 1

    # 目標閃避中 (DODGING)
    if Condition.DODGING in target_set:
        disadvantages += 1

    # 倒地目標：1.5m 內近戰 = 優勢，遠程 = 劣勢
    if Condition.PRONE in target_set:
        if is_melee and distance <= 1.5:
            advantages += 1
        else:
            disadvantages += 1

    # --- 遠程近戰劣勢 ---
    # 1.5m 內有非無力化敵人且使用遠程攻擊
    if is_ranged and hostile_within_melee:
        disadvantages += 1

    # 互相抵消
    if advantages > 0 and disadvantages > 0:
        return RollType.NORMAL
    if advantages > 0:
        return RollType.ADVANTAGE
    if disadvantages > 0:
        return RollType.DISADVANTAGE
    return RollType.NORMAL


def is_auto_crit(
    target_conditions: list[ActiveCondition],
    distance: float = 1.5,
) -> bool:
    """檢查命中是否自動爆擊（1.5m 內麻痺/昏迷目標）。"""
    if distance > 1.5:
        return False
    target_set = {c.condition for c in target_conditions}
    return bool(target_set & {Condition.PARALYZED, Condition.UNCONSCIOUS})


# ---------------------------------------------------------------------------
# 擒抱（D&D 2024 豁免制）
# ---------------------------------------------------------------------------


@dataclass
class GrappleResult:
    """擒抱嘗試結果。"""

    success: bool
    save_result: SaveResult | None = None
    reason: str = ""


def attempt_grapple(
    attacker: Character | Monster,
    target: Character | Monster,
    state: CombatState,
    rng: random.Random | None = None,
) -> GrappleResult:
    """嘗試擒抱目標（2024 豁免制）。

    - 消耗行動（徒手打擊選項的一部分）
    - 檢查體型（目標不超過攻擊者一個體型等級）
    - 目標做 STR 或 DEX 豁免 vs DC
    - 失敗 → GRAPPLED 狀態
    """
    if not can_take_action(attacker):
        return GrappleResult(success=False, reason="攻擊者無力化，無法行動")

    if not use_action(state):
        return GrappleResult(success=False, reason="行動已使用")

    attacker_size = _get_size(attacker)
    target_size = _get_size(target)

    if not can_grapple_size(attacker_size, target_size):
        return GrappleResult(
            success=False,
            reason=f"目標體型（{target_size}）超過攻擊者（{attacker_size}）一個等級以上",
        )

    dc = grapple_save_dc(attacker)

    # 目標選擇 STR 或 DEX 豁免（取較高者）
    str_bonus = target.ability_scores.modifier(Ability.STR)
    dex_bonus = target.ability_scores.modifier(Ability.DEX)
    if isinstance(target, Character):
        if Ability.STR in target.saving_throw_proficiencies:
            str_bonus += target.proficiency_bonus
        if Ability.DEX in target.saving_throw_proficiencies:
            dex_bonus += target.proficiency_bonus

    if str_bonus >= dex_bonus:
        save_ability = Ability.STR
        save_bonus = str_bonus
    else:
        save_ability = Ability.DEX
        save_bonus = dex_bonus

    save = resolve_saving_throw(
        save_bonus,
        dc,
        save_ability,
        conditions=target.conditions,
        rng=rng,
    )

    if save.success:
        return GrappleResult(success=False, save_result=save, reason="目標豁免成功")

    # 施加 GRAPPLED 狀態
    target.conditions.append(
        ActiveCondition(
            condition=Condition.GRAPPLED,
            source=getattr(attacker, "name", "unknown"),
        )
    )
    return GrappleResult(success=True, save_result=save)


def attempt_escape_grapple(
    target: Character | Monster,
    dc: int,
    use_dex: bool = False,
    rng: random.Random | None = None,
) -> SaveResult:
    """嘗試脫離擒抱（目標做 STR 或 DEX 豁免 vs DC）。"""
    ability = Ability.DEX if use_dex else Ability.STR
    bonus = target.ability_scores.modifier(ability)
    if isinstance(target, Character) and ability in target.saving_throw_proficiencies:
        bonus += target.proficiency_bonus

    return resolve_saving_throw(
        bonus,
        dc,
        ability,
        conditions=target.conditions,
        rng=rng,
    )


# ---------------------------------------------------------------------------
# 推撞（D&D 2024 豁免制）
# ---------------------------------------------------------------------------


@dataclass
class ShoveResult:
    """推撞嘗試結果。"""

    success: bool
    save_result: SaveResult | None = None
    effect: str = ""  # "push" (推開 1.5m) 或 "prone" (擊倒)
    reason: str = ""


def attempt_shove(
    attacker: Character | Monster,
    target: Character | Monster,
    effect: str,
    state: CombatState,
    rng: random.Random | None = None,
) -> ShoveResult:
    """嘗試推撞目標（2024 豁免制）。

    參數:
        effect: "push"（推開 1.5m）或 "prone"（擊倒）。
    """
    if effect not in ("push", "prone"):
        return ShoveResult(success=False, reason=f"無效的推撞效果: {effect}")

    if not can_take_action(attacker):
        return ShoveResult(success=False, reason="攻擊者無力化，無法行動")

    if not use_action(state):
        return ShoveResult(success=False, reason="行動已使用")

    attacker_size = _get_size(attacker)
    target_size = _get_size(target)

    if not can_grapple_size(attacker_size, target_size):
        return ShoveResult(
            success=False,
            reason=f"目標體型（{target_size}）超過攻擊者（{attacker_size}）一個等級以上",
        )

    dc = grapple_save_dc(attacker)

    # 目標選擇 STR 或 DEX 豁免（取較高者）
    str_bonus = target.ability_scores.modifier(Ability.STR)
    dex_bonus = target.ability_scores.modifier(Ability.DEX)
    if isinstance(target, Character):
        if Ability.STR in target.saving_throw_proficiencies:
            str_bonus += target.proficiency_bonus
        if Ability.DEX in target.saving_throw_proficiencies:
            dex_bonus += target.proficiency_bonus

    if str_bonus >= dex_bonus:
        save_ability = Ability.STR
        save_bonus = str_bonus
    else:
        save_ability = Ability.DEX
        save_bonus = dex_bonus

    save = resolve_saving_throw(
        save_bonus,
        dc,
        save_ability,
        conditions=target.conditions,
        rng=rng,
    )

    if save.success:
        return ShoveResult(
            success=False,
            save_result=save,
            effect=effect,
            reason="目標豁免成功",
        )

    # 施加效果
    if effect == "prone":
        target.conditions.append(
            ActiveCondition(
                condition=Condition.PRONE,
                source=getattr(attacker, "name", "unknown"),
            )
        )

    return ShoveResult(success=True, save_result=save, effect=effect)


# ---------------------------------------------------------------------------
# 借機攻擊
# ---------------------------------------------------------------------------


@dataclass
class OpportunityAttackResult:
    """借機攻擊結果。"""

    triggered: bool
    attack_result: AttackResult | None = None
    damage_result: DamageResult | None = None
    reason: str = ""


def check_opportunity_attack(
    attacker: Character | Monster,
    target: Character | Monster,
    entry: InitiativeEntry,
    weapon: Weapon,
    target_ac: int,
    rng: random.Random | None = None,
) -> OpportunityAttackResult:
    """檢查並執行借機攻擊。

    前置條件：
    - 反應未使用
    - 未受突襲（第一回合結束前反應不可用）
    - 未無力化
    - 自願移動觸發（強制移動如 Push/Shove 不觸發，由上層區分）

    參數:
        attacker: 執行借機攻擊的戰鬥者。
        target: 離開攻擊範圍的目標。
        entry: 攻擊者的先攻條目（用於反應追蹤）。
        weapon: 使用的近戰武器。
        target_ac: 目標的 AC。
    """
    if entry.reaction_used:
        return OpportunityAttackResult(
            triggered=False,
            reason="反應已使用",
        )

    if entry.is_surprised:
        return OpportunityAttackResult(
            triggered=False,
            reason="受突襲中，反應不可用",
        )

    if not can_take_action(attacker):
        return OpportunityAttackResult(
            triggered=False,
            reason="攻擊者無力化",
        )

    # 消耗反應
    entry.reaction_used = True

    attack_bonus = calc_weapon_attack_bonus(attacker, weapon)
    ability_mod = _weapon_ability_mod(attacker, weapon)

    attack = resolve_attack(attack_bonus, target_ac, rng=rng)

    dmg = None
    if attack.is_hit:
        dmg = roll_damage(
            weapon.damage_dice,
            weapon.damage_type,
            modifier=ability_mod,
            is_critical=attack.is_critical,
            rng=rng,
        )

    return OpportunityAttackResult(
        triggered=True,
        attack_result=attack,
        damage_result=dmg,
    )


# ---------------------------------------------------------------------------
# 借機攻擊（逐步移動查詢）
# ---------------------------------------------------------------------------


@dataclass
class StepOAResult:
    """逐步移動時的借機攻擊結果（純計算，不含傷害施加）。"""

    attacker: Character | Monster
    weapon: Weapon
    oa_result: OpportunityAttackResult


def get_reach_m(combatant: Character | Monster) -> float:
    """取得戰鬥者的觸及距離（公尺）。

    集中 reach 提取邏輯，避免在多處重複。
    range_normal / reach 已是公尺值。
    """
    if isinstance(combatant, Character) and combatant.weapons:
        return combatant.weapons[0].range_normal
    if isinstance(combatant, Monster) and combatant.actions:
        return combatant.actions[0].reach
    return 1.5


def check_opportunity_attacks_on_step(
    mover: Character | Monster,
    old_x: float,
    old_y: float,
    new_x: float,
    new_y: float,
    combat_state: CombatState,
    map_state: MapState,
    combatant_map: dict[UUID, Combatant],
    characters: list[Character],
    monsters: list[Monster],
    *,
    rng: random.Random | None = None,
) -> list[StepOAResult]:
    """檢查移動一步時觸發的所有借機攻擊（純計算）。

    回傳 list[StepOAResult]，不印 log、不扣血。
    caller 負責迭代結果 → apply_damage + log。
    """
    if mover.has_condition(Condition.DISENGAGING):
        return []

    results: list[StepOAResult] = []

    for entry in combat_state.initiative_order:
        enemy = combatant_map.get(entry.combatant_id)
        if not enemy or not enemy.is_alive or enemy.id == mover.id:
            continue
        # 同陣營不觸發
        if isinstance(mover, Character) and isinstance(enemy, Character):
            continue
        if isinstance(mover, Monster) and isinstance(enemy, Monster):
            continue

        enemy_actor = map_state.get_actor(enemy.id)
        if not enemy_actor:
            continue

        reach_m = get_reach_m(enemy)
        enemy_pos = Position(x=enemy_actor.x, y=enemy_actor.y)

        old_dist = distance(Position(x=old_x, y=old_y), enemy_pos)
        if old_dist > reach_m:
            continue
        new_dist = distance(Position(x=new_x, y=new_y), enemy_pos)
        if new_dist <= reach_m:
            continue

        # 建立武器（Monster 用 actions[0] 轉為 Weapon）
        weapon: Weapon | None = None
        if isinstance(enemy, Character) and enemy.weapons:
            weapon = enemy.weapons[0]
        elif isinstance(enemy, Monster) and enemy.actions:
            act = enemy.actions[0]
            weapon = Weapon(
                name=act.name,
                damage_dice=act.damage_dice,
                damage_type=act.damage_type,
                properties=[],
            )

        if not weapon:
            continue

        oa = check_opportunity_attack(
            attacker=enemy,
            target=mover,
            entry=entry,
            weapon=weapon,
            target_ac=mover.ac,
            rng=rng,
        )
        if not oa.triggered:
            continue

        results.append(StepOAResult(attacker=enemy, weapon=weapon, oa_result=oa))

    return results


# ---------------------------------------------------------------------------
# 雙持武器
# ---------------------------------------------------------------------------


@dataclass
class TwoWeaponAttackResult:
    """雙持副手攻擊結果。"""

    attack_result: AttackResult
    damage_result: DamageResult | None = None


def offhand_attack(
    attacker: Character | Monster,
    offhand_weapon: Weapon,
    target_ac: int,
    state: CombatState,
    roll_type: RollType = RollType.NORMAL,
    cover: CoverType = CoverType.NONE,
    rng: random.Random | None = None,
) -> TwoWeaponAttackResult | None:
    """執行雙持副手攻擊。

    前置條件：副手武器必須具有 LIGHT 屬性。
    消耗附贈動作。傷害不加屬性修正。
    """
    if not can_take_action(attacker):
        return None

    if WeaponProperty.LIGHT not in offhand_weapon.properties:
        return None

    if not use_bonus_action(state):
        return None

    # 副手攻擊骰仍包含屬性修正 + 熟練加值，只有傷害不加屬性修正
    # 副手攻擊骰仍包含屬性修正 + 熟練加值
    attack_bonus = calc_weapon_attack_bonus(attacker, offhand_weapon)

    attack = resolve_attack(
        attack_bonus=attack_bonus,
        target_ac=target_ac,
        roll_type=roll_type,
        cover=cover,
        rng=rng,
    )

    dmg = None
    if attack.is_hit:
        dmg = roll_damage(
            offhand_weapon.damage_dice,
            offhand_weapon.damage_type,
            modifier=0,  # 副手不加屬性修正
            is_critical=attack.is_critical,
            rng=rng,
        )

    return TwoWeaponAttackResult(attack_result=attack, damage_result=dmg)


# ---------------------------------------------------------------------------
# 英雄激勵
# ---------------------------------------------------------------------------


def use_heroic_inspiration(
    character: Character,
    rng: random.Random | None = None,
) -> DiceResult:
    """消耗英雄激勵，重擲一顆 d20。

    回傳新的 d20 結果。由呼叫端決定是否採用。
    """
    character.heroic_inspiration = False
    return roll_d20(rng=rng)


def reroll_attack(
    character: Character,
    attack_bonus: int,
    target_ac: int,
    roll_type: RollType = RollType.NORMAL,
    cover: CoverType = CoverType.NONE,
    rng: random.Random | None = None,
) -> AttackResult:
    """消耗英雄激勵重擲攻擊。"""
    character.heroic_inspiration = False
    return resolve_attack(
        attack_bonus,
        target_ac,
        roll_type=roll_type,
        cover=cover,
        rng=rng,
    )


def reroll_save(
    character: Character,
    save_bonus: int,
    dc: int,
    ability: Ability,
    cover: CoverType = CoverType.NONE,
    rng: random.Random | None = None,
) -> SaveResult:
    """消耗英雄激勵重擲豁免。"""
    character.heroic_inspiration = False
    return resolve_saving_throw(
        save_bonus,
        dc,
        ability,
        conditions=character.conditions,
        cover=cover,
        rng=rng,
    )


def grant_inspiration(
    character: Character,
    attack_result: AttackResult,
) -> None:
    """根據攻擊結果設定英雄激勵（自然 20 觸發）。

    若角色已有激勵，標記溢出讓 UI 提示轉贈同伴。
    """
    if not attack_result.grants_inspiration:
        return
    if character.heroic_inspiration:
        attack_result.inspiration_overflow = True
    else:
        character.heroic_inspiration = True
