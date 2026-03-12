"""狀態效果管理——套用、移除、堆疊、回合計時。

集中管理 D&D 2024 (5.5e) 的 16+ 種狀態效果的生命週期，
讓 combat.py 專注在「狀態對戰鬥的影響」。
"""

from __future__ import annotations

from tot.models import ActiveCondition, Character, Combatant, Condition, Monster

# ---------------------------------------------------------------------------
# 狀態分類常數
# ---------------------------------------------------------------------------

# 包含無力化效果的狀態（麻痺、震懾、昏迷、石化都隱含無力化）
INCAPACITATING_CONDITIONS = frozenset(
    {
        Condition.INCAPACITATED,
        Condition.PARALYZED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
        Condition.PETRIFIED,
    }
)

# 不可堆疊的狀態（同一狀態只能存在一個實例，新的覆蓋舊的）
# 力竭(Exhaustion)特殊處理——累加等級而非覆蓋
_NON_STACKABLE = frozenset(
    {
        Condition.BLINDED,
        Condition.CHARMED,
        Condition.DEAFENED,
        Condition.DISENGAGING,
        Condition.DODGING,
        Condition.FRIGHTENED,
        Condition.INCAPACITATED,
        Condition.INVISIBLE,
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.POISONED,
        Condition.PRONE,
        Condition.RESTRAINED,
        Condition.SILENCED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
        Condition.WEAKENED,
    }
)

# 同源不堆疊的狀態（不同來源可以各有一個）
_SOURCE_STACKING = frozenset(
    {
        Condition.GRAPPLED,  # 可被多個來源同時擒抱
    }
)


# ---------------------------------------------------------------------------
# Step 1: 狀態管理 API
# ---------------------------------------------------------------------------


def apply_condition(
    combatant: Combatant,
    condition: Condition,
    *,
    source: str = "",
    remaining_rounds: int | None = None,
    exhaustion_level: int = 0,
) -> ActiveCondition | None:
    """套用狀態到生物。回傳新套用的 ActiveCondition，若被免疫則回傳 None。

    堆疊規則：
    - 免疫檢查（Monster.condition_immunities）
    - 力竭：累加等級（上限 6），不新增條目
    - 同源不堆疊（GRAPPLED 等）：同 source 的覆蓋，不同 source 的可並存
    - 其他狀態：不堆疊，新的覆蓋舊的（取較長持續時間）
    """
    # 免疫檢查
    if isinstance(combatant, Monster) and condition in combatant.condition_immunities:
        return None

    # 力竭特殊處理
    if condition == Condition.EXHAUSTION:
        return _apply_exhaustion(combatant, exhaustion_level or 1)

    # 同源堆疊狀態（如 GRAPPLED）
    if condition in _SOURCE_STACKING:
        return _apply_source_stacking(combatant, condition, source, remaining_rounds)

    # 一般不堆疊狀態
    if condition in _NON_STACKABLE:
        return _apply_non_stackable(combatant, condition, source, remaining_rounds)

    # 未分類的狀態直接加入
    ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=remaining_rounds,
    )
    combatant.conditions.append(ac)
    return ac


def remove_condition(
    combatant: Combatant,
    condition: Condition,
    *,
    source: str | None = None,
) -> list[ActiveCondition]:
    """移除狀態。回傳被移除的 ActiveCondition 列表。

    source=None → 移除所有同類型狀態
    source="xxx" → 只移除指定來源的狀態
    """
    removed: list[ActiveCondition] = []
    remaining: list[ActiveCondition] = []

    for ac in combatant.conditions:
        if ac.condition == condition and (source is None or ac.source == source):
            removed.append(ac)
        else:
            remaining.append(ac)

    combatant.conditions = remaining

    # 力竭特殊處理：同步 exhaustion_level
    if condition == Condition.EXHAUSTION and isinstance(combatant, Character):
        combatant.exhaustion_level = 0

    return removed


def has_condition_effect(
    combatant: Combatant,
    condition: Condition,
) -> bool:
    """檢查生物是否受到指定狀態效果影響（考慮免疫）。

    委派給模型上的 has_condition()，統一入口方便未來擴展。
    """
    return combatant.has_condition(condition)


def get_conditions(combatant: Combatant) -> set[Condition]:
    """取得生物目前所有生效中的狀態集合。"""
    return {ac.condition for ac in combatant.conditions}


def is_incapacitated(combatant: Combatant) -> bool:
    """檢查生物是否處於無力化狀態（含隱含無力化的狀態）。"""
    return bool(get_conditions(combatant) & INCAPACITATING_CONDITIONS)


def can_take_action(combatant: Combatant) -> bool:
    """檢查是否能採取行動（未處於無力化狀態）。"""
    return not is_incapacitated(combatant)


def exhaustion_penalty(exhaustion_level: int) -> int:
    """2024 版力竭懲罰：每級 -2 所有 d20 檢定。"""
    return -2 * exhaustion_level


# ---------------------------------------------------------------------------
# Step 2: 回合生命週期
# ---------------------------------------------------------------------------


def tick_conditions_start_of_turn(combatant: Combatant) -> list[ActiveCondition]:
    """回合開始時處理狀態。回傳本回合到期被移除的狀態。

    目前回合開始不自動移除狀態（D&D 大多數狀態在回合結束時到期），
    但保留此 hook 供未來擴展（如某些法術在回合開始時結束）。
    """
    # 預留：未來可在此處理回合開始觸發的效果
    return []


def tick_conditions_end_of_turn(combatant: Combatant) -> list[ActiveCondition]:
    """回合結束時遞減持續時間，移除到期狀態。回傳被移除的狀態。"""
    expired: list[ActiveCondition] = []
    remaining: list[ActiveCondition] = []

    for ac in combatant.conditions:
        if ac.remaining_rounds is not None:
            new_rounds = ac.remaining_rounds - 1
            if new_rounds <= 0:
                expired.append(ac)
                continue
            # 建立更新後的 ActiveCondition（Pydantic model 不直接修改）
            remaining.append(ac.model_copy(update={"remaining_rounds": new_rounds}))
        else:
            remaining.append(ac)

    combatant.conditions = remaining
    return expired


# ---------------------------------------------------------------------------
# Step 3: 堆疊規則——內部實作
# ---------------------------------------------------------------------------


def _apply_exhaustion(
    combatant: Combatant,
    levels: int = 1,
) -> ActiveCondition | None:
    """累加力竭等級。上限 6 級，6 級 = 死亡。"""
    if isinstance(combatant, Character):
        new_level = min(6, combatant.exhaustion_level + levels)
        combatant.exhaustion_level = new_level
        # 移除舊的 EXHAUSTION 條目
        combatant.conditions = [
            ac for ac in combatant.conditions if ac.condition != Condition.EXHAUSTION
        ]
    else:
        # Monster 沒有 exhaustion_level 欄位，用 ActiveCondition 追蹤
        existing = next(
            (ac for ac in combatant.conditions if ac.condition == Condition.EXHAUSTION),
            None,
        )
        if existing:
            new_level = min(6, existing.exhaustion_level + levels)
            combatant.conditions = [
                ac for ac in combatant.conditions if ac.condition != Condition.EXHAUSTION
            ]
        else:
            new_level = min(6, levels)

    ac = ActiveCondition(
        condition=Condition.EXHAUSTION,
        exhaustion_level=new_level,
    )
    combatant.conditions.append(ac)
    return ac


def _apply_source_stacking(
    combatant: Combatant,
    condition: Condition,
    source: str,
    remaining_rounds: int | None,
) -> ActiveCondition:
    """同源不堆疊、異源可並存。同源時取較長持續時間。"""
    for i, ac in enumerate(combatant.conditions):
        if ac.condition == condition and ac.source == source:
            # 同源：取較長持續時間
            new_rounds = _longer_duration(ac.remaining_rounds, remaining_rounds)
            updated = ac.model_copy(update={"remaining_rounds": new_rounds})
            combatant.conditions[i] = updated
            return updated

    # 異源：新增
    ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=remaining_rounds,
    )
    combatant.conditions.append(ac)
    return ac


_SENTINEL = object()  # 區分「沒有舊狀態」和「永久舊狀態 (None)」


def _apply_non_stackable(
    combatant: Combatant,
    condition: Condition,
    source: str,
    remaining_rounds: int | None,
) -> ActiveCondition:
    """不堆疊：移除舊的，套用新的（取較長持續時間）。"""
    old_rounds: int | None | object = _SENTINEL
    new_conditions: list[ActiveCondition] = []
    for ac in combatant.conditions:
        if ac.condition == condition:
            if old_rounds is _SENTINEL:
                old_rounds = ac.remaining_rounds
            else:
                old_rounds = _longer_duration(old_rounds, ac.remaining_rounds)
        else:
            new_conditions.append(ac)

    if old_rounds is _SENTINEL:
        final_rounds = remaining_rounds
    else:
        final_rounds = _longer_duration(old_rounds, remaining_rounds)
    new_ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=final_rounds,
    )
    new_conditions.append(new_ac)
    combatant.conditions = new_conditions
    return new_ac


def _longer_duration(
    a: int | None,
    b: int | None,
) -> int | None:
    """取兩個持續時間中較長的。None 表示無限期，永遠最長。"""
    if a is None or b is None:
        return None
    return max(a, b)
