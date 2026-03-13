"""技能檢定與屬性檢定包裝。

提供結構化的 d20 檢定介面，供探索系統使用。
純確定性——不呼叫 LLM。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tot.gremlins.bone_engine.dice import RollType, roll_d20
from tot.models.creature import Character, Combatant
from tot.models.enums import Ability, Skill


@dataclass(frozen=True)
class CheckResult:
    """檢定結果。"""

    success: bool
    total: int  # d20 + modifier
    natural: int  # d20 原始值
    dc: int
    label: str  # "Perception 檢定" 等


def skill_check(
    character: Character,
    skill: Skill,
    dc: int,
    *,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> CheckResult:
    """技能檢定：d20 + skill_bonus vs DC。"""
    bonus = character.skill_bonus(skill)
    result = roll_d20(modifier=bonus, roll_type=roll_type, rng=rng)
    return CheckResult(
        success=result.total >= dc,
        total=result.total,
        natural=result.natural or result.rolls[0],
        dc=dc,
        label=f"{skill.value} 檢定",
    )


def ability_check(
    combatant: Combatant,
    ability: Ability,
    dc: int,
    *,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> CheckResult:
    """屬性檢定：d20 + ability_modifier vs DC。"""
    bonus = combatant.ability_modifier(ability)
    result = roll_d20(modifier=bonus, roll_type=roll_type, rng=rng)
    return CheckResult(
        success=result.total >= dc,
        total=result.total,
        natural=result.natural or result.rolls[0],
        dc=dc,
        label=f"{ability.value} 檢定",
    )


def passive_skill(character: Character, skill: Skill) -> int:
    """被動技能值：10 + skill_bonus。

    泛化 Character.passive_perception 到任意技能。
    """
    return 10 + character.skill_bonus(skill)


def best_passive_perception(characters: list[Character]) -> int:
    """回傳隊伍中最高的被動感知值。"""
    if not characters:
        return 0
    return max(c.passive_perception for c in characters)
