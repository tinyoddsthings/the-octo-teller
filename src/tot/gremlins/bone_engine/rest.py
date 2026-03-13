"""休息系統——短休與長休。

D&D 2024 (5.5e) 休息規則的簡化實作。
短休自動分配 Hit Dice（完整版再加手動分配）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

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


def short_rest(
    characters: list[Character],
    *,
    rng: random.Random | None = None,
) -> RestResult:
    """短休（1 小時）。

    每位角色自動使用可用 Hit Dice 回復 HP，直到 HP 全滿或 Hit Dice 用盡。
    簡化版：自動分配，不需玩家手動選擇。
    """
    hp_recovered: dict[str, int] = {}
    hit_dice_used: dict[str, int] = {}

    for char in characters:
        if char.hp_current >= char.hp_max:
            continue
        if char.hit_dice_remaining <= 0:
            continue

        total_healed = 0
        dice_used = 0
        con_mod = char.ability_modifier(Ability.CON)

        while char.hit_dice_remaining > 0 and char.hp_current < char.hp_max:
            # 擲 Hit Die + CON modifier
            result = dice_roll(f"d{char.hit_die_size}", rng=rng)
            healed = max(1, result.total + con_mod)  # 最少回復 1 HP
            actual = min(healed, char.hp_max - char.hp_current)
            char.hp_current += actual
            char.hit_dice_remaining -= 1
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

        # 法術欄位恢復
        char.spell_slots.recover_all()

        # Hit Dice 回復一半（向下取整，最少 1）
        recover_dice = max(1, char.hit_dice_total // 2)
        char.hit_dice_remaining = min(
            char.hit_dice_total,
            char.hit_dice_remaining + recover_dice,
        )

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
