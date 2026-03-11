"""靜態資料載入器。

從 JSON 檔案載入地圖 manifest 並建構 terrain 二維陣列。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tot.models import ExplorationMap, MapManifest, MapState, Position, TerrainTile

# 預設地圖資料夾
_MAPS_DIR = Path(__file__).parent / "maps"


def load_map_manifest(
    path: str | Path | None = None,
    *,
    name: str | None = None,
) -> MapState:
    """從 JSON 載入地圖，回傳完整的 MapState（含 terrain 二維陣列）。

    參數:
        path: JSON 檔案路徑。若未指定則從內建地圖資料夾以 name 查找。
        name: 內建地圖名稱（不含 .json），例如 'tutorial_room'。

    terrain JSON 格式:
        - {"symbol": "#", "positions": [[x,y], ...], "is_blocking": true, "name": "wall"}
        - {"symbol": ".", "fill": true, ...}  ← fill=true 填滿未指定的格子
    """
    if path is None:
        if name is None:
            msg = "必須指定 path 或 name 其中之一"
            raise ValueError(msg)
        path = _MAPS_DIR / f"{name}.json"

    path = Path(path)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    # 取出 terrain 定義（載入器專用格式，不屬於 MapManifest）
    terrain_defs: list[dict[str, Any]] = raw.pop("terrain", [])

    # 解析 spawn_points：JSON 中是 {key: [{x, y}, ...]}，座標為 grid 座標
    gs = raw.get("grid_size_m", 1.5)
    raw_spawns = raw.get("spawn_points", {})
    parsed_spawns: dict[str, list[Position]] = {}
    for key, points in raw_spawns.items():
        parsed_spawns[key] = [Position.from_grid(p["x"], p["y"], gs) for p in points]
    raw["spawn_points"] = parsed_spawns

    # Props 的 x/y 也是 grid 座標，轉為公尺（格子中心）
    for prop in raw.get("props", []):
        gx, gy = prop["x"], prop["y"]
        prop["x"] = gx * gs + gs / 2
        prop["y"] = gy * gs + gs / 2

    manifest = MapManifest(**raw)

    # 建構 terrain[y][x] 二維陣列，y=0 為最底列
    terrain = _build_terrain_grid(manifest.width, manifest.height, terrain_defs)

    return MapState(
        manifest=manifest,
        terrain=terrain,
        props=[],  # 執行期動態 props 初始為空
    )


def _build_terrain_grid(
    width: int,
    height: int,
    terrain_defs: list[dict[str, Any]],
) -> list[list[TerrainTile]]:
    """從 terrain 定義建構二維陣列。

    先處理有明確 positions 的定義，再用 fill=true 的定義填滿剩餘格子。
    """
    grid: list[list[TerrainTile | None]] = [[None for _ in range(width)] for _ in range(height)]

    fill_def: dict[str, Any] | None = None

    for tdef in terrain_defs:
        if tdef.get("fill"):
            fill_def = tdef
            continue

        tile = TerrainTile(
            symbol=tdef.get("symbol", "."),
            is_blocking=tdef.get("is_blocking", False),
            name=tdef.get("name", "floor"),
            is_difficult=tdef.get("is_difficult", False),
        )

        for pos in tdef.get("positions", []):
            x, y = pos[0], pos[1]
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = tile.model_copy()

    # 填滿未指定的格子
    if fill_def:
        fill_tile = TerrainTile(
            symbol=fill_def.get("symbol", "."),
            is_blocking=fill_def.get("is_blocking", False),
            name=fill_def.get("name", "floor"),
            is_difficult=fill_def.get("is_difficult", False),
        )
        for y in range(height):
            for x in range(width):
                if grid[y][x] is None:
                    grid[y][x] = fill_tile.model_copy()

    # 未被填滿的格子給預設地板
    for y in range(height):
        for x in range(width):
            if grid[y][x] is None:
                grid[y][x] = TerrainTile()

    return grid  # type: ignore[return-value]


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
