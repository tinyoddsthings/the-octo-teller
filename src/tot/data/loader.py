"""靜態資料載入器。

從 JSON 檔案載入地圖 manifest 並建構 MapState。
地圖格式：walls + 公尺座標（連續空間）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tot.models import ExplorationMap, MapManifest, MapState, Position

# 預設地圖資料夾
_MAPS_DIR = Path(__file__).parent / "maps"


def load_map_manifest(
    path: str | Path | None = None,
    *,
    name: str | None = None,
) -> MapState:
    """從 JSON 載入地圖，回傳完整的 MapState。

    參數:
        path: JSON 檔案路徑。若未指定則從內建地圖資料夾以 name 查找。
        name: 內建地圖名稱（不含 .json），例如 'tutorial_room'。
    """
    if path is None:
        if name is None:
            msg = "必須指定 path 或 name 其中之一"
            raise ValueError(msg)
        path = _MAPS_DIR / f"{name}.json"

    path = Path(path)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    # 忽略舊格式殘留的 terrain 欄位
    raw.pop("terrain", None)

    # spawn_points 中的座標已是公尺
    raw_spawns = raw.get("spawn_points", {})
    parsed_spawns: dict[str, list[Position]] = {}
    for key, points in raw_spawns.items():
        parsed_spawns[key] = [Position(x=p["x"], y=p["y"]) for p in points]
    raw["spawn_points"] = parsed_spawns

    manifest = MapManifest(**raw)

    return MapState(
        manifest=manifest,
        walls=list(manifest.walls),
        props=[],
    )


# ---------------------------------------------------------------------------
# Pointcrawl 探索地圖載入
# ---------------------------------------------------------------------------


def load_exploration_map(
    path: str | Path | None = None,
    *,
    name: str | None = None,
) -> ExplorationMap:
    """從 JSON 載入 Pointcrawl 探索地圖。

    參數:
        path: JSON 檔案路徑。若未指定則從內建地圖資料夾以 name 查找。
        name: 內建地圖名稱（不含 .json），例如 'tutorial_dungeon'。
    """
    if path is None:
        if name is None:
            msg = "必須指定 path 或 name 其中之一"
            raise ValueError(msg)
        path = _MAPS_DIR / f"{name}.json"

    path = Path(path)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    return ExplorationMap(**raw)
