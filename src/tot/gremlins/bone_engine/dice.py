"""Bone Engine 骰子系統。

處理所有 D&D 骰子：d4、d6、d8、d10、d12、d20、d100。
支援優勢/劣勢、修正值、多骰擲骰。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from enum import StrEnum


class RollType(StrEnum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


@dataclass
class DiceResult:
    """骰子結果，含完整的審計紀錄。"""

    expression: str  # 原始表達式，例如 "2d6+3"
    rolls: list[int] = field(default_factory=list)  # 各顆骰子的結果
    modifier: int = 0
    roll_type: RollType = RollType.NORMAL
    advantage_rolls: list[int] = field(default_factory=list)  # 優勢/劣勢時兩顆 d20 的原始值
    dropped: list[int] = field(default_factory=list)  # 被丟棄未計入的骰子

    @property
    def total(self) -> int:
        return sum(self.rolls) + self.modifier

    @property
    def natural(self) -> int | None:
        """單顆 d20 時的自然骰值（未加修正）。"""
        if len(self.rolls) == 1:
            return self.rolls[0]
        return None

    @property
    def is_nat20(self) -> bool:
        return self.natural == 20

    @property
    def is_nat1(self) -> bool:
        return self.natural == 1


# 正規表達式：解析 "2d6+3"、"d20"、"1d8-1"、"4d6kh3"（保留最高 3 顆）
_DICE_PATTERN = re.compile(
    r"^(\d*)d(\d+)"  # NdS（骰子數量 d 面數）
    r"(?:kh(\d+))?"  # 可選：保留最高 N 顆
    r"(?:kl(\d+))?"  # 可選：保留最低 N 顆
    r"([+-]\d+)?$",  # 可選：修正值
    re.IGNORECASE,
)


def parse_expression(expr: str) -> tuple[int, int, int | None, int | None, int]:
    """解析骰子表達式為 (數量, 面數, 保留最高, 保留最低, 修正值)。

    範例:
        "2d6+3" -> (2, 6, None, None, 3)
        "d20"   -> (1, 20, None, None, 0)
        "4d6kh3" -> (4, 6, 3, None, 0)
    """
    expr = expr.strip().replace(" ", "")
    m = _DICE_PATTERN.match(expr)
    if not m:
        raise ValueError(f"無效的骰子表達式: {expr!r}")

    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    keep_high = int(m.group(3)) if m.group(3) else None
    keep_low = int(m.group(4)) if m.group(4) else None
    modifier = int(m.group(5)) if m.group(5) else 0

    if sides < 1:
        raise ValueError(f"骰子至少要有 1 面，收到 {sides}")
    if count < 1:
        raise ValueError(f"至少要擲 1 顆骰子，收到 {count}")

    return count, sides, keep_high, keep_low, modifier


def roll(
    expression: str,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> DiceResult:
    """從表達式擲骰，例如 '2d6+3' 或 'd20'。

    參數:
        expression: 骰子表示法字串（例如 "d20"、"2d6+3"、"4d6kh3"）。
        roll_type: NORMAL、ADVANTAGE 或 DISADVANTAGE。
            優勢/劣勢僅在單顆 d20 時生效。
        rng: 可選的 Random 實例，用於確定性測試。

    回傳:
        DiceResult，含完整的擲骰細節與審計紀錄。
    """
    r = rng or random
    count, sides, keep_high, keep_low, modifier = parse_expression(expression)

    # 擲所有骰子
    all_rolls = [r.randint(1, sides) for _ in range(count)]

    # 優勢/劣勢：僅在單顆 d20 時適用
    advantage_rolls: list[int] = []
    if count == 1 and sides == 20 and roll_type != RollType.NORMAL:
        second = r.randint(1, sides)
        advantage_rolls = [all_rolls[0], second]
        if roll_type == RollType.ADVANTAGE:
            all_rolls = [max(advantage_rolls)]
        else:
            all_rolls = [min(advantage_rolls)]

    # 保留最高/保留最低
    dropped: list[int] = []
    kept = list(all_rolls)
    if keep_high is not None:
        sorted_desc = sorted(kept, reverse=True)
        kept = sorted_desc[:keep_high]
        dropped = sorted_desc[keep_high:]
    elif keep_low is not None:
        sorted_asc = sorted(kept)
        kept = sorted_asc[:keep_low]
        dropped = sorted_asc[keep_low:]

    return DiceResult(
        expression=expression,
        rolls=kept,
        modifier=modifier,
        roll_type=roll_type,
        advantage_rolls=advantage_rolls,
        dropped=dropped,
    )


# ---------------------------------------------------------------------------
# 便利函式
# ---------------------------------------------------------------------------


def roll_d20(
    modifier: int = 0,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> DiceResult:
    """d20 擲骰的快捷方式（攻擊、豁免、檢定）。"""
    expr = f"d20+{modifier}" if modifier >= 0 else f"d20{modifier}"
    return roll(expr, roll_type=roll_type, rng=rng)


def roll_damage(expression: str, rng: random.Random | None = None) -> DiceResult:
    """傷害骰的快捷方式（永遠是 normal，無優勢）。"""
    return roll(expression, roll_type=RollType.NORMAL, rng=rng)


def roll_ability_scores(rng: random.Random | None = None) -> list[int]:
    """擲 4d6 棄最低，重複六次。回傳 6 個屬性值。"""
    scores = []
    for _ in range(6):
        result = roll("4d6kh3", rng=rng)
        scores.append(result.total)
    return scores
