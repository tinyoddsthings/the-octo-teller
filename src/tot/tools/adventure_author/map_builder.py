"""MapIR → ExplorationMap JSON dict。

產出的 dict 可通過 ExplorationMap.model_validate() 驗證。
"""

from __future__ import annotations

import re

from tot.tools.adventure_author.id_gen import name_to_id
from tot.tools.adventure_author.ir import EdgeIR, ItemIR, MapIR, NodeIR, PoiIR


def build_map(ir: MapIR) -> dict:
    """將 MapIR 轉為 ExplorationMap 相容的 JSON dict。"""
    scale = ir.meta.get("scale", "dungeon")

    # 建立節點 name → id 對應表
    node_id_map: dict[str, str] = {}
    for node in ir.nodes:
        nid = name_to_id(node.name, node.explicit_id)
        node_id_map[node.name] = nid

    nodes = [_build_node(node) for node in ir.nodes]
    edges = _collect_edges(ir, node_id_map, scale)

    return {
        "id": ir.meta.get("id", ""),
        "name": ir.meta.get("name", ""),
        "scale": scale,
        "entry_node_id": ir.meta.get("entry", ""),
        "nodes": nodes,
        "edges": edges,
    }


def _build_node(node: NodeIR) -> dict:
    """將 NodeIR 轉為節點 dict。"""
    nid = name_to_id(node.name, node.explicit_id)
    result: dict = {
        "id": nid,
        "name": node.name,
        "node_type": node.node_type or "room",
    }

    if node.description:
        result["description"] = node.description
    if node.ambient:
        result["ambient"] = node.ambient
    if node.combat_map:
        result["combat_map"] = node.combat_map
    if node.sub_map:
        result["sub_map"] = node.sub_map
    if node.npcs:
        result["npcs"] = node.npcs

    if node.pois:
        result["pois"] = [_build_poi(poi) for poi in node.pois]

    if node.items:
        result["hidden_items"] = [_build_item(item) for item in node.items]

    return result


def _build_poi(poi: PoiIR) -> dict:
    """將 PoiIR 轉為 POI 子節點 dict。"""
    pid = name_to_id(poi.name, poi.explicit_id)
    result: dict = {
        "id": pid,
        "name": poi.name,
        "node_type": "poi",
    }
    if poi.description:
        result["description"] = poi.description
    if poi.npcs:
        result["npcs"] = poi.npcs
    return result


def _build_item(item: ItemIR) -> dict:
    """將 ItemIR 轉為 NodeItem dict。"""
    iid = name_to_id(item.name, item.explicit_id)
    result: dict = {
        "id": iid,
        "name": item.name,
        "item_type": item.item_type,
        "investigation_dc": item.investigation_dc,
    }
    if item.description:
        result["description"] = item.description
    if item.grants_key:
        result["grants_key"] = item.grants_key
    if item.value_gp:
        result["value_gp"] = item.value_gp
    return result


def _collect_edges(ir: MapIR, node_id_map: dict[str, str], scale: str) -> list[dict]:
    """收集所有邊，解析 from/to 和距離。"""
    edges: list[dict] = []
    for node in ir.nodes:
        node_id = name_to_id(node.name, node.explicit_id)
        for edge_ir in node.edges:
            edge = _build_edge(edge_ir, node_id, node_id_map, scale)
            edges.append(edge)
    return edges


def _build_edge(
    edge: EdgeIR,
    parent_node_id: str,
    node_id_map: dict[str, str],
    scale: str,
) -> dict:
    """將 EdgeIR 轉為邊 dict。"""
    props = edge.properties

    # 解析 from/to
    from_id = props.get("from", parent_node_id)
    to_id = props.get("to", "")

    # edge ID
    eid = name_to_id(edge.name, edge.explicit_id) if edge.name else f"{from_id}_to_{to_id}"

    result: dict = {
        "id": eid,
        "from_node_id": from_id,
        "to_node_id": to_id,
    }

    if edge.name:
        result["name"] = edge.name

    # 距離解析
    distance = props.get("distance", "")
    if distance:
        dist_val, dist_unit = _parse_distance(distance)
        if dist_unit == "min":
            result["distance_minutes"] = int(dist_val)
        elif dist_unit == "day":
            result["distance_days"] = dist_val

    # 通行條件
    if "locked" in props:
        result["is_locked"] = True
        result["key_item"] = props["locked"]
    if "lock_dc" in props:
        result["lock_dc"] = int(props["lock_dc"])
    if "break_dc" in props:
        result["break_dc"] = int(props["break_dc"])
    if "hidden_dc" in props:
        result["is_discovered"] = False
        result["hidden_dc"] = int(props["hidden_dc"])
    if "one_way" in props and props["one_way"].lower() == "true":
        result["is_one_way"] = True
    if "jump_dc" in props:
        result["requires_jump"] = True
        result["jump_dc"] = int(props["jump_dc"])
    if "fall_damage" in props and props["fall_damage"].lower() == "true":
        result["fall_damage_on_fail"] = True

    # 世界圖層
    if "danger_level" in props:
        result["danger_level"] = int(props["danger_level"])
    if "terrain" in props:
        result["terrain_type"] = props["terrain"]

    return result


def _parse_distance(distance: str) -> tuple[float, str]:
    """解析距離字串：'10min' → (10.0, 'min'), '0.5day' → (0.5, 'day')。"""
    match = re.match(r"([\d.]+)\s*(min|day)s?", distance.strip())
    if match:
        return float(match.group(1)), match.group(2)
    # 嘗試純數字（預設分鐘）
    try:
        return float(distance), "min"
    except ValueError:
        return 0.0, "min"
