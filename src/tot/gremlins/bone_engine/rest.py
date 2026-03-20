"""休息系統——短休與長休。

D&D 2024 (5.5e) 休息規則的簡化實作。
短休自動分配 Hit Dice（完整版再加手動分配）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tot.gremlins.bone_engine.character import CLASS_REGISTRY
from tot.gremlins.bone_engine.dice import roll as dice_roll
from tot.gremlins.bone_engine.time_costs import LONG_REST, SHORT_REST
from tot.models.creature import Character
from tot.models.enums import Ability


@dataclass(frozen=True)
class RestResult:
    """休息結果。"""

    rest_type: str  # "short" | "long"
    elapsed_seconds: int  # SHORT_REST or LONG_REST
    hp_recovered: dict[str, int] = field(default_factory=dict)
    hit_dice_used: dict[str, int] = field(default_factory=dict)
    spell_slots_recovered: bool = False
    message: str = ""


def _spend_hit_die(char: Character) -> int | None:
    """花費最大面數的 Hit Die，回傳骰面大小；無可用則回傳 None。

    兼職時從最大骰面開始用（對玩家最有利）。
    """
    for die_size in sorted(char.hit_dice_remaining, reverse=True):
        if char.hit_dice_remaining[die_size] > 0:
            char.hit_dice_remaining[die_size] -= 1
            return die_size
    return None


def short_rest(
    characters: list[Character],
    *,
    rng: random.Random | None = None,
) -> RestResult:
    """短休（1 小時）。

    每位角色自動使用可用 Hit Dice 回復 HP，直到 HP 全滿或 Hit Dice 用盡。
    術士 Pact Magic 欄位在短休後恢復。
    簡化版：自動分配，不需玩家手動選擇。
    """
    hp_recovered: dict[str, int] = {}
    hit_dice_used: dict[str, int] = {}

    for char in characters:
        # 術士 Pact Magic 短休恢復
        char.pact_slots.recover_all()

        if char.hp_current >= char.hp_max:
            continue
        if char.hit_dice_remaining_count <= 0:
            continue

        total_healed = 0
        dice_used = 0
        con_mod = char.ability_modifier(Ability.CON)

        while char.hit_dice_remaining_count > 0 and char.hp_current < char.hp_max:
            die_size = _spend_hit_die(char)
            if die_size is None:
                break
            # 擲 Hit Die + CON modifier
            result = dice_roll(f"d{die_size}", rng=rng)
            healed = max(1, result.total + con_mod)  # 最少回復 1 HP
            actual = min(healed, char.hp_max - char.hp_current)
            char.hp_current += actual
            total_healed += actual
            dice_used += 1

        if total_healed > 0:
            hp_recovered[char.name] = total_healed
            hit_dice_used[char.name] = dice_used

    if hp_recovered:
        lines = [
            f"{name} 回復 {hp} HP（使用 {hit_dice_used[name]} 顆 Hit Dice）"
            for name, hp in hp_recovered.items()
        ]
        msg = "短休完畢。\n" + "\n".join(lines)
    else:
        msg = "短休完畢。全員無需回復或無可用 Hit Dice。"

    return RestResult(
        rest_type="short",
        elapsed_seconds=SHORT_REST,
        hp_recovered=hp_recovered,
        hit_dice_used=hit_dice_used,
        message=msg,
    )


def long_rest(characters: list[Character]) -> RestResult:
    """長休（8 小時）。

    - HP 回復至全滿
    - 法術欄位全部恢復
    - Hit Dice 回復一半（最少 1 顆）
    """
    hp_recovered: dict[str, int] = {}

    for char in characters:
        # HP 全滿
        healed = char.hp_max - char.hp_current
        if healed > 0:
            hp_recovered[char.name] = healed
            char.hp_current = char.hp_max

        # 法術欄位恢復（含術士 Pact Magic）
        char.spell_slots.recover_all()
        char.pact_slots.recover_all()

        # Hit Dice 回復一半（向下取整，最少 1）
        # 兼職時按比例回復各骰面（從最小骰面先補）
        total = char.hit_dice_total
        recover_count = max(1, total // 2)
        # 計算各骰面最大值（從 class_levels 反推）
        max_by_die: dict[int, int] = {}
        for cls_name, lvl in char.class_levels.items():
            cls_data = CLASS_REGISTRY.get(cls_name)
            if cls_data:
                die = cls_data.hit_die
                max_by_die[die] = max_by_die.get(die, 0) + lvl
        recovered = 0
        for die_size in sorted(max_by_die):
            if recovered >= recover_count:
                break
            current = char.hit_dice_remaining.get(die_size, 0)
            max_val = max_by_die[die_size]
            can_recover = min(recover_count - recovered, max_val - current)
            if can_recover > 0:
                char.hit_dice_remaining[die_size] = current + can_recover
                recovered += can_recover

    if hp_recovered:
        lines = [f"{name} 回復 {hp} HP" for name, hp in hp_recovered.items()]
        msg = "長休完畢。HP 全滿、法術欄位恢復。\n" + "\n".join(lines)
    else:
        msg = "長休完畢。全員 HP 已滿，法術欄位恢復。"

    return RestResult(
        rest_type="long",
        elapsed_seconds=LONG_REST,
        hp_recovered=hp_recovered,
        spell_slots_recovered=True,
        message=msg,
    )
