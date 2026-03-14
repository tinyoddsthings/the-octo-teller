"""建築結構物件 prefab 定義。

HP 計算依 D&D 2024 DMG：avg(OBJECT_HP_DICE[size]) × FRAGILITY_HP_MULTIPLIER[fragility]。
"""

from __future__ import annotations

from typing import Any

from tot.models.enums import Fragility, Material, Size
from tot.models.shapes import BoundingShape

STRUCTURAL_PREFABS: dict[str, dict[str, Any]] = {
    "stone_pillar": {
        "name": "石柱",
        "prop_type": "decoration",
        "is_blocking": True,
        "cover_bonus": 5,
        "material": Material.STONE,
        "object_ac": 17,
        "object_size": Size.LARGE,
        "fragility": Fragility.RESILIENT,
        "hp_max": 27,
        "hp_current": 27,
        "bounds": BoundingShape.circle(0.5),
    },
    "wall_torch": {
        "name": "壁掛火把",
        "prop_type": "decoration",
        "is_blocking": False,
        "cover_bonus": 0,
        "material": Material.IRON,
        "object_ac": 19,
        "object_size": Size.TINY,
        "fragility": Fragility.RESILIENT,
        "hp_max": 5,
        "hp_current": 5,
    },
    "wooden_door": {
        "name": "木門",
        "prop_type": "door",
        "is_blocking": False,
        "cover_bonus": 2,
        "material": Material.WOOD,
        "object_ac": 15,
        "object_size": Size.LARGE,
        "fragility": Fragility.RESILIENT,
        "hp_max": 18,
        "hp_current": 18,
        "bounds": BoundingShape.rect(1.5, 0.3),
    },
    "iron_gate_locked": {
        "name": "鐵柵門（鎖）",
        "prop_type": "door",
        "is_blocking": True,
        "cover_bonus": 2,
        "material": Material.IRON,
        "object_ac": 19,
        "object_size": Size.LARGE,
        "fragility": Fragility.RESILIENT,
        "hp_max": 0,  # 不可摧毀
        "hp_current": 0,
        "bounds": BoundingShape.rect(1.5, 0.3),
    },
}
