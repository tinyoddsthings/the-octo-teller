"""Dice rolling system for the Bone Engine.

Handles all D&D dice: d4, d6, d8, d10, d12, d20, d100.
Supports advantage/disadvantage, modifiers, and multi-dice rolls.
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
    """Result of a dice roll, with full audit trail."""

    expression: str  # original expression, e.g. "2d6+3"
    rolls: list[int] = field(default_factory=list)  # individual die results
    modifier: int = 0
    roll_type: RollType = RollType.NORMAL
    # for advantage/disadvantage on d20: both raw values
    advantage_rolls: list[int] = field(default_factory=list)
    dropped: list[int] = field(default_factory=list)  # dice not counted

    @property
    def total(self) -> int:
        return sum(self.rolls) + self.modifier

    @property
    def natural(self) -> int | None:
        """For single d20 rolls, the natural (unmodified) result."""
        if len(self.rolls) == 1:
            return self.rolls[0]
        return None

    @property
    def is_nat20(self) -> bool:
        return self.natural == 20

    @property
    def is_nat1(self) -> bool:
        return self.natural == 1


# Regex: "2d6+3", "d20", "1d8-1", "4d6kh3" (keep highest 3)
_DICE_PATTERN = re.compile(
    r"^(\d*)d(\d+)"          # NdS
    r"(?:kh(\d+))?"          # optional: keep highest N
    r"(?:kl(\d+))?"          # optional: keep lowest N
    r"([+-]\d+)?$",          # optional modifier
    re.IGNORECASE,
)


def parse_expression(expr: str) -> tuple[int, int, int | None, int | None, int]:
    """Parse a dice expression into (count, sides, keep_high, keep_low, modifier).

    Examples:
        "2d6+3" -> (2, 6, None, None, 3)
        "d20"   -> (1, 20, None, None, 0)
        "4d6kh3" -> (4, 6, 3, None, 0)
    """
    expr = expr.strip().replace(" ", "")
    m = _DICE_PATTERN.match(expr)
    if not m:
        raise ValueError(f"Invalid dice expression: {expr!r}")

    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    keep_high = int(m.group(3)) if m.group(3) else None
    keep_low = int(m.group(4)) if m.group(4) else None
    modifier = int(m.group(5)) if m.group(5) else 0

    if sides < 1:
        raise ValueError(f"Die must have at least 1 side, got {sides}")
    if count < 1:
        raise ValueError(f"Must roll at least 1 die, got {count}")

    return count, sides, keep_high, keep_low, modifier


def roll(
    expression: str,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> DiceResult:
    """Roll dice from an expression like '2d6+3' or 'd20'.

    Args:
        expression: Dice notation string (e.g. "d20", "2d6+3", "4d6kh3").
        roll_type: NORMAL, ADVANTAGE, or DISADVANTAGE.
            Advantage/disadvantage only applies to single d20 rolls.
        rng: Optional Random instance for deterministic testing.

    Returns:
        DiceResult with full roll details and audit trail.
    """
    # TODO(human): implement the roll function
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def roll_d20(
    modifier: int = 0,
    roll_type: RollType = RollType.NORMAL,
    rng: random.Random | None = None,
) -> DiceResult:
    """Shortcut for d20 rolls (attack, save, check)."""
    expr = f"d20+{modifier}" if modifier >= 0 else f"d20{modifier}"
    return roll(expr, roll_type=roll_type, rng=rng)


def roll_damage(expression: str, rng: random.Random | None = None) -> DiceResult:
    """Shortcut for damage rolls (always normal, no advantage)."""
    return roll(expression, roll_type=RollType.NORMAL, rng=rng)


def roll_ability_scores(rng: random.Random | None = None) -> list[int]:
    """Roll 4d6 drop lowest, six times. Returns 6 scores."""
    scores = []
    for _ in range(6):
        result = roll("4d6kh3", rng=rng)
        scores.append(result.total)
    return scores
