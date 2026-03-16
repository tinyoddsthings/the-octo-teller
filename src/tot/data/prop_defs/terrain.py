"""地形特徵 prefab 定義（無 material = 不可摧毀）。"""

from __future__ import annotations

from typing import Any

from tot.models.shapes import BoundingShape

TERRAIN_PREFABS: dict[str, dict[str, Any]] = {
    "rubble_zone": {
        "name": "碎石區",
        "prop_type": "decoration",
        "is_blocking": False,
        "terrain_type": "rubble",
        "bounds": BoundingShape.rect(6.0, 4.0),
    },
    "water_pool": {
        "name": "水池",
        "prop_type": "decoration",
        "is_blocking": False,
        "terrain_type": "water",
        "bounds": BoundingShape.circle(2.5),
    },
    "hill": {
        "name": "高台",
        "prop_type": "decoration",
        "is_blocking": False,
        "terrain_type": "hill",
        "bounds": BoundingShape.rect(4.0, 3.0),
    },
    "crevice": {
        "name": "裂縫",
        "prop_type": "decoration",
        "is_blocking": False,
        "terrain_type": "crevice",
        "bounds": BoundingShape.rect(3.0, 4.0),
    },
}
