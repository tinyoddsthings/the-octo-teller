"""狀態效果管理——套用、移除、堆疊、回合計時。

集中管理 D&D 2024 (5.5e) 的 16+ 種狀態效果的生命週期，
讓 combat.py 專注在「狀態對戰鬥的影響」。
"""

from __future__ import annotations

import math

from tot.models import ActiveCondition, Character, Combatant, Condition, GameClock, Monster
from tot.models.time import format_seconds_human

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
    expires_at_second: int | None = None,
    exhaustion_level: int = 0,
) -> ActiveCondition | None:
    """套用狀態到生物。回傳新套用的 ActiveCondition，若被免疫則回傳 None。

    持續時間可用兩種方式指定（二擇一）：
    - remaining_rounds: 傳統回合倒數（向後相容）
    - expires_at_second: 絕對秒數到期（配合 GameClock）

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
        return _apply_source_stacking(
            combatant, condition, source, remaining_rounds, expires_at_second
        )

    # 一般不堆疊狀態
    if condition in _NON_STACKABLE:
        return _apply_non_stackable(
            combatant, condition, source, remaining_rounds, expires_at_second
        )

    # 未分類的狀態直接加入
    ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=remaining_rounds,
        expires_at_second=expires_at_second,
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


def tick_conditions_end_of_turn(
    combatant: Combatant,
    game_clock: GameClock | None = None,
) -> list[ActiveCondition]:
    """回合結束時處理到期狀態。回傳被移除的狀態。

    雙模式支援：
    - expires_at_second + game_clock：比對絕對時間
    - remaining_rounds（向後相容）：倒數遞減
    """
    expired: list[ActiveCondition] = []
    remaining: list[ActiveCondition] = []
    now = game_clock.total_seconds if game_clock else None

    for ac in combatant.conditions:
        # 優先用絕對秒數判斷
        if ac.expires_at_second is not None and now is not None:
            if now >= ac.expires_at_second:
                expired.append(ac)
                continue
            remaining.append(ac)
        elif ac.remaining_rounds is not None:
            new_rounds = ac.remaining_rounds - 1
            if new_rounds <= 0:
                expired.append(ac)
                continue
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
    expires_at_second: int | None = None,
) -> ActiveCondition:
    """同源不堆疊、異源可並存。同源時取較長持續時間。"""
    for i, ac in enumerate(combatant.conditions):
        if ac.condition == condition and ac.source == source:
            # 同源：取較長持續時間
            new_rounds = _longer_duration(ac.remaining_rounds, remaining_rounds)
            new_expires = _longer_duration(ac.expires_at_second, expires_at_second)
            updated = ac.model_copy(
                update={"remaining_rounds": new_rounds, "expires_at_second": new_expires}
            )
            combatant.conditions[i] = updated
            return updated

    # 異源：新增
    ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=remaining_rounds,
        expires_at_second=expires_at_second,
    )
    combatant.conditions.append(ac)
    return ac


_SENTINEL = object()  # 區分「沒有舊狀態」和「永久舊狀態 (None)」


def _apply_non_stackable(
    combatant: Combatant,
    condition: Condition,
    source: str,
    remaining_rounds: int | None,
    expires_at_second: int | None = None,
) -> ActiveCondition:
    """不堆疊：移除舊的，套用新的（取較長持續時間）。"""
    old_rounds: int | None | object = _SENTINEL
    old_expires: int | None | object = _SENTINEL
    new_conditions: list[ActiveCondition] = []
    for ac in combatant.conditions:
        if ac.condition == condition:
            if old_rounds is _SENTINEL:
                old_rounds = ac.remaining_rounds
            else:
                old_rounds = _longer_duration(old_rounds, ac.remaining_rounds)
            if old_expires is _SENTINEL:
                old_expires = ac.expires_at_second
            else:
                old_expires = _longer_duration(old_expires, ac.expires_at_second)
        else:
            new_conditions.append(ac)

    if old_rounds is _SENTINEL:
        final_rounds = remaining_rounds
    else:
        final_rounds = _longer_duration(old_rounds, remaining_rounds)
    if old_expires is _SENTINEL:
        final_expires = expires_at_second
    else:
        final_expires = _longer_duration(old_expires, expires_at_second)
    new_ac = ActiveCondition(
        condition=condition,
        source=source,
        remaining_rounds=final_rounds,
        expires_at_second=final_expires,
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


# ---------------------------------------------------------------------------
# Step 4: 顯示工具
# ---------------------------------------------------------------------------


def format_remaining(
    expires_at: int | None,
    clock: GameClock,
    *,
    in_combat: bool = False,
) -> str:
    """格式化效果剩餘時間。

    in_combat=True → 顯示「N 輪」
    in_combat=False → 顯示人類可讀時間
    永久效果 → 「永久」
    """
    if expires_at is None:
        return "永久"
    remaining = expires_at - clock.total_seconds
    if remaining <= 0:
        return "已到期"
    if in_combat:
        rounds = math.ceil(remaining / 6)
        return f"{rounds} 輪"
    return format_seconds_human(remaining)
