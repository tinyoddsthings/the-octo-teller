"""靜態資料載入器。

從 JSON 檔案載入地圖 manifest 並建構 MapState。
支援新格式（walls + 公尺座標）和舊格式（terrain grid + grid_size_m）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tot.models import ExplorationMap, MapManifest, MapState, Position, TerrainTile, Wall

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

    支援兩種格式：
    - 新格式：直接包含 walls 和公尺座標
    - 舊格式：terrain 定義 + grid_size_m，自動轉換為 walls
    """
    if path is None:
        if name is None:
            msg = "必須指定 path 或 name 其中之一"
            raise ValueError(msg)
        path = _MAPS_DIR / f"{name}.json"

    path = Path(path)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    # 偵測格式：有 "walls" key → 新格式
    is_new_format = "walls" in raw

    # 取出 terrain 定義（舊格式專用）
    terrain_defs: list[dict[str, Any]] = raw.pop("terrain", [])

    if is_new_format:
        # 新格式：座標已是公尺，直接讀取
        # spawn_points 中的座標已是公尺
        raw_spawns = raw.get("spawn_points", {})
        parsed_spawns: dict[str, list[Position]] = {}
        for key, points in raw_spawns.items():
            parsed_spawns[key] = [Position(x=p["x"], y=p["y"]) for p in points]
        raw["spawn_points"] = parsed_spawns

        # Props 座標已是公尺，不需轉換

        manifest = MapManifest(**raw)

        # 從 manifest.walls 複製到 MapState.walls
        return MapState(
            manifest=manifest,
            walls=list(manifest.walls),
            props=[],
        )

    # 舊格式：grid_size_m + terrain 定義
    gs = raw.get("grid_size_m", 1.5)
    raw_spawns = raw.get("spawn_points", {})
    parsed_spawns = {}
    for key, points in raw_spawns.items():
        parsed_spawns[key] = [Position.from_grid(p["x"], p["y"], gs) for p in points]
    raw["spawn_points"] = parsed_spawns

    # Props 的 x/y 是 grid 座標，轉為公尺（格子中心）
    for prop in raw.get("props", []):
        gx, gy = prop["x"], prop["y"]
        prop["x"] = gx * gs + gs / 2
        prop["y"] = gy * gs + gs / 2

    # 舊格式的 width/height 是格數，轉為公尺
    raw["width"] = raw["width"] * gs
    raw["height"] = raw["height"] * gs

    manifest = MapManifest(**raw)

    # 建構 terrain[y][x] 二維陣列（相容舊程式碼）
    grid_w = int(manifest.width / gs)
    grid_h = int(manifest.height / gs)
    terrain = _build_terrain_grid(grid_w, grid_h, terrain_defs)

    # 同時從 terrain 建構 walls
    walls = _terrain_to_walls(terrain, gs)

    return MapState(
        manifest=manifest,
        terrain=terrain,
        walls=walls,
        props=[],
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


def _terrain_to_walls(terrain: list[list[TerrainTile]], gs: float) -> list[Wall]:
    """從 terrain grid 提取 blocking tiles 轉為 Wall AABB。"""
    walls: list[Wall] = []
    for gy, row in enumerate(terrain):
        for gx, tile in enumerate(row):
            if tile.is_blocking:
                walls.append(Wall(x=gx * gs, y=gy * gs, width=gs, height=gs))
    return walls


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
