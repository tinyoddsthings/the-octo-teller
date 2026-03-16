"""靜態資料載入器。

從 JSON 檔案載入地圖 manifest 並建構 MapState。
地圖格式：walls + 公尺座標（連續空間）。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tot.models import ExplorationMap, MapManifest, MapState, Position

# 預設地圖資料夾
_MAPS_DIR = Path(__file__).parent / "maps"

# 名稱→路徑快取（遞迴搜索子資料夾）
_name_cache: dict[str, Path] = {}


def _resolve_map_path(name: str) -> Path:
    """依名稱在 maps/ 子資料夾中遞迴查找 JSON 檔案。"""
    if name in _name_cache:
        return _name_cache[name]

    # 重建快取
    if not _name_cache:
        for p in _MAPS_DIR.rglob("*.json"):
            _name_cache[p.stem] = p

    if name in _name_cache:
        return _name_cache[name]

    msg = f"找不到地圖：{name}（在 {_MAPS_DIR} 及其子資料夾中）"
    raise FileNotFoundError(msg)


def _expand_props(raw_props: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """將 prefab_id 展開為完整 prop dict。

    深拷貝模板後以實例欄位覆蓋，無 prefab_id 的 prop 原樣傳遞（向後相容）。
    """
    from tot.data.prop_defs import PROP_PREFABS

    expanded: list[dict[str, Any]] = []
    for entry in raw_props:
        prefab_id = entry.pop("prefab_id", None)
        if prefab_id:
            if prefab_id not in PROP_PREFABS:
                msg = f"未知的 prefab_id：{prefab_id}"
                raise ValueError(msg)
            template = copy.deepcopy(PROP_PREFABS[prefab_id])
            template.update(entry)
            expanded.append(template)
        else:
            expanded.append(entry)
    return expanded


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
        path = _resolve_map_path(name)

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

    # Prefab 展開：prefab_id → 深拷貝模板 + 實例覆蓋
    raw["props"] = _expand_props(raw.get("props", []))

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
        path = _resolve_map_path(name)

    path = Path(path)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    return ExplorationMap(**raw)
