"""可互動物品 prefab 定義。"""

from __future__ import annotations

from typing import Any

from tot.models.enums import Fragility, Material, Size

INTERACTIVE_PREFABS: dict[str, dict[str, Any]] = {
    "stone_chest": {
        "name": "石箱",
        "prop_type": "item",
        "is_blocking": False,
        "interactable": True,
        "investigation_dc": 12,
        "material": Material.STONE,
        "object_ac": 17,
        "object_size": Size.SMALL,
        "fragility": Fragility.RESILIENT,
        "hp_max": 7,
        "hp_current": 7,
    },
    "glowing_mushrooms": {
        "name": "發光蘑菇群",
        "prop_type": "item",
        "is_blocking": False,
        "interactable": True,
        "investigation_dc": 0,
    },
}
