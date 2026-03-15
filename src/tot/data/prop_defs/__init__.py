"""Prop Prefab 登錄表。

地圖 JSON 用 prefab_id 引用這些模板，loader.py 在載入時展開。
"""

from __future__ import annotations

from typing import Any

from tot.data.prop_defs.interactive import INTERACTIVE_PREFABS
from tot.data.prop_defs.structural import STRUCTURAL_PREFABS
from tot.data.prop_defs.terrain import TERRAIN_PREFABS

PROP_PREFABS: dict[str, dict[str, Any]] = {
    **STRUCTURAL_PREFABS,
    **INTERACTIVE_PREFABS,
    **TERRAIN_PREFABS,
}

__all__ = [
    "INTERACTIVE_PREFABS",
    "PROP_PREFABS",
    "STRUCTURAL_PREFABS",
    "TERRAIN_PREFABS",
]
