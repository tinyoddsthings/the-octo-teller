"""Prop Prefab 系統測試。

驗證 prefab 登錄表、loader 展開邏輯、地圖載入整合。
"""

from __future__ import annotations

import pytest

from tot.data.loader import _expand_props
from tot.data.prop_defs import PROP_PREFABS
from tot.models.enums import Material, ShapeType

# ---------------------------------------------------------------------------
# Prefab 登錄表
# ---------------------------------------------------------------------------


class TestPrefabRegistry:
    """PROP_PREFABS 登錄表完整性。"""

    def test_all_prefabs_registered(self) -> None:
        """10 個 prefab 全數註冊。"""
        expected = {
            "stone_pillar",
            "wall_torch",
            "wooden_door",
            "iron_gate_locked",
            "stone_chest",
            "glowing_mushrooms",
            "rubble_zone",
            "water_pool",
            "hill",
            "crevice",
        }
        assert set(PROP_PREFABS.keys()) == expected

    def test_structural_prefabs_have_material(self) -> None:
        """建築結構 prefab 必須有 material。"""
        structural_ids = ["stone_pillar", "wall_torch", "wooden_door", "iron_gate_locked"]
        for pid in structural_ids:
            assert PROP_PREFABS[pid].get("material") is not None, f"{pid} 缺少 material"

    def test_terrain_prefabs_no_material(self) -> None:
        """地形 prefab 不應有 material（不可摧毀）。"""
        terrain_ids = ["rubble_zone", "water_pool", "hill", "crevice"]
        for pid in terrain_ids:
            assert PROP_PREFABS[pid].get("material") is None, f"{pid} 不該有 material"

    def test_stone_pillar_values(self) -> None:
        """石柱 prefab 數值正確。"""
        p = PROP_PREFABS["stone_pillar"]
        assert p["is_blocking"] is True
        assert p["cover_bonus"] == 5
        assert p["material"] == Material.STONE
        assert p["object_ac"] == 17
        assert p["hp_max"] == 27
        assert p["bounds"].shape_type == ShapeType.CIRCLE
        assert p["bounds"].radius_m == 0.5

    def test_water_pool_bounds(self) -> None:
        """水池 prefab 為圓形 bounds。"""
        p = PROP_PREFABS["water_pool"]
        assert p["bounds"].shape_type == ShapeType.CIRCLE
        assert p["bounds"].radius_m == 2.5
        assert p["terrain_type"] == "water"


# ---------------------------------------------------------------------------
# _expand_props 展開邏輯
# ---------------------------------------------------------------------------


class TestExpandProps:
    """loader._expand_props() 測試。"""

    def test_basic_expansion(self) -> None:
        """prefab_id 展開後應包含模板欄位。"""
        raw = [{"id": "p1", "prefab_id": "stone_pillar", "x": 1.0, "y": 2.0}]
        result = _expand_props(raw)
        assert len(result) == 1
        assert result[0]["is_blocking"] is True
        assert result[0]["cover_bonus"] == 5
        assert result[0]["material"] == Material.STONE
        assert result[0]["x"] == 1.0
        assert result[0]["y"] == 2.0

    def test_instance_override(self) -> None:
        """實例欄位覆蓋模板預設值。"""
        raw = [{"id": "p1", "prefab_id": "stone_pillar", "x": 0, "y": 0, "name": "自訂名稱"}]
        result = _expand_props(raw)
        assert result[0]["name"] == "自訂名稱"  # 覆蓋模板的 "石柱"

    def test_no_prefab_passthrough(self) -> None:
        """無 prefab_id 的 prop 原樣傳遞。"""
        raw = [{"id": "custom", "x": 5.0, "y": 5.0, "name": "自訂"}]
        result = _expand_props(raw)
        assert result[0] == {"id": "custom", "x": 5.0, "y": 5.0, "name": "自訂"}

    def test_unknown_prefab_raises(self) -> None:
        """未知 prefab_id 應拋出 ValueError。"""
        raw = [{"id": "bad", "prefab_id": "not_exist", "x": 0, "y": 0}]
        with pytest.raises(ValueError, match="未知的 prefab_id"):
            _expand_props(raw)

    def test_deep_copy_isolation(self) -> None:
        """展開後修改不影響原始模板。"""
        original_hp = PROP_PREFABS["stone_pillar"]["hp_max"]
        raw = [{"id": "p1", "prefab_id": "stone_pillar", "x": 0, "y": 0}]
        result = _expand_props(raw)
        result[0]["hp_max"] = 999
        assert PROP_PREFABS["stone_pillar"]["hp_max"] == original_hp

    def test_empty_list(self) -> None:
        """空 list 回傳空 list。"""
        assert _expand_props([]) == []

    def test_mixed_prefab_and_inline(self) -> None:
        """混合 prefab 與 inline prop。"""
        raw = [
            {"id": "p1", "prefab_id": "wall_torch", "x": 1.0, "y": 1.0},
            {"id": "p2", "x": 2.0, "y": 2.0, "name": "inline"},
        ]
        result = _expand_props(raw)
        assert len(result) == 2
        assert result[0]["name"] == "壁掛火把"  # 來自 prefab
        assert result[1]["name"] == "inline"  # 原樣傳遞


# ---------------------------------------------------------------------------
# 地圖載入整合
# ---------------------------------------------------------------------------


class TestMapLoadIntegration:
    """驗證 prefab 展開後地圖正確載入。"""

    def test_tutorial_room_loads(self) -> None:
        """tutorial_room 4 props 全數展開。"""
        from tot.data.loader import load_map_manifest

        ms = load_map_manifest(name="tutorial_room")
        props = ms.manifest.props
        assert len(props) == 4

        doors = [p for p in props if p.prop_type == "door"]
        pillars = [p for p in props if p.is_blocking]
        assert len(doors) == 2
        assert len(pillars) == 2

        # 石柱應有 cover_bonus=5
        for p in pillars:
            assert p.cover_bonus == 5
            assert p.material == Material.STONE

    def test_cave_explore_loads(self) -> None:
        """cave_explore 13 props 展開，含 override。"""
        from tot.data.loader import load_map_manifest

        ms = load_map_manifest(name="cave_explore")
        props = ms.manifest.props
        assert len(props) == 13

        # 鐵柵門有 interactable override
        gate = next(p for p in props if p.id == "exit_north")
        assert gate.is_blocking is True
        assert gate.interactable is True
        assert gate.material == Material.IRON

        # hidden_scroll 無 prefab，保持 inline
        scroll = next(p for p in props if p.id == "hidden_scroll")
        assert scroll.hidden is True
        assert scroll.investigation_dc == 15

    def test_cave_explore_bounds_preserved(self) -> None:
        """cave_explore 的 bounds override 正確套用。"""
        from tot.data.loader import load_map_manifest

        ms = load_map_manifest(name="cave_explore")
        props = ms.manifest.props

        rubble = next(p for p in props if p.id == "rubble_zone")
        assert rubble.bounds is not None
        assert rubble.bounds.shape_type == ShapeType.RECTANGLE
        assert rubble.bounds.half_width_m == 3.0
        assert rubble.bounds.half_height_m == 2.0

        pool = next(p for p in props if p.id == "water_pool")
        assert pool.bounds is not None
        assert pool.bounds.shape_type == ShapeType.CIRCLE
        assert pool.bounds.radius_m == 2.5
