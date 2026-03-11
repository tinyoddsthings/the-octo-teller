"""空間系統單元測試。

涵蓋：
- S-1 浮點座標模型
- S-2 Euclidean 距離 + actors_in_radius
- S-3 碰撞系統（體型半徑、穿越規則、停留判定）
- 既有功能迴歸（LOS、掩蔽、移動、BFS）
"""

from __future__ import annotations

import math

import pytest

from tot.gremlins.bone_engine.spatial import (
    actors_in_radius,
    bfs_path_to_range,
    can_end_move_at,
    can_traverse,
    check_collision,
    determine_cover_from_grid,
    distance,
    find_nearest_valid_position,
    grid_distance,
    has_hostile_within_melee,
    has_line_of_sight,
    move_entity,
    parse_spell_range_meters,
    validate_spell_range,
    zone_for_position,
)
from tot.models import (
    SIZE_RADIUS_M,
    Actor,
    CoverType,
    MapManifest,
    MapState,
    Position,
    Prop,
    Size,
    Spell,
    SpellSchool,
    TerrainTile,
    Zone,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_map() -> MapState:
    """5×5 空白地圖（grid_size=1.5m）。"""
    manifest = MapManifest(name="test", width=5, height=5, grid_size_m=1.5)
    terrain = [[TerrainTile() for _ in range(5)] for _ in range(5)]
    return MapState(manifest=manifest, terrain=terrain)


@pytest.fixture
def map_with_wall() -> MapState:
    """5×5 地圖，(2,2) 有一面牆。"""
    manifest = MapManifest(
        name="wall_test",
        width=5,
        height=5,
        grid_size_m=1.5,
        props=[Prop(id="wall1", x=3.75, y=3.75, symbol="🧱", is_blocking=True, prop_type="wall")],
    )
    terrain = [[TerrainTile() for _ in range(5)] for _ in range(5)]
    return MapState(manifest=manifest, terrain=terrain)


def _make_actor(
    actor_id: str,
    gx: int,
    gy: int,
    gs: float = 1.5,
    *,
    alive: bool = True,
    combatant_type: str = "monster",
) -> Actor:
    """建立在網格 (gx, gy) 中心的 Actor。"""
    from uuid import uuid4

    mx = gx * gs + gs / 2
    my = gy * gs + gs / 2
    return Actor(
        id=actor_id,
        x=mx,
        y=my,
        combatant_id=uuid4(),
        combatant_type=combatant_type,
        name=f"actor_{actor_id}",
        is_blocking=True,
        is_alive=alive,
    )


# ===========================================================================
# S-1: 浮點座標模型
# ===========================================================================


class TestPositionFloat:
    """Position 浮點座標基本功能。"""

    def test_int_auto_coerce(self):
        """整數自動轉 float。"""
        p = Position(x=3, y=4)
        assert isinstance(p.x, float)
        assert p.x == 3.0

    def test_round_to_cm(self):
        """四捨五入到 cm 精度。"""
        p = Position(x=1.111, y=2.999)
        assert p.x == 1.11
        assert p.y == 3.0

    def test_to_grid(self):
        """公尺座標 → 網格座標。"""
        p = Position(x=3.75, y=5.25)  # 格 (2,3) 中心
        assert p.to_grid(1.5) == (2, 3)

    def test_to_grid_edge(self):
        """格子邊界上的座標。"""
        p = Position(x=3.0, y=3.0)  # (3.0/1.5)=2.0 → grid (2, 2)
        assert p.to_grid(1.5) == (2, 2)

    def test_from_grid(self):
        """網格座標 → 公尺座標（格子中心）。"""
        p = Position.from_grid(2, 3, 1.5)
        assert p.x == 3.75
        assert p.y == 5.25

    def test_distance_to(self):
        """Euclidean 距離計算。"""
        a = Position(x=0, y=0)
        b = Position(x=3, y=4)
        assert a.distance_to(b) == pytest.approx(5.0)

    def test_distance_to_same(self):
        p = Position(x=1.5, y=1.5)
        assert p.distance_to(p) == 0.0

    def test_from_grid_roundtrip(self):
        """from_grid → to_grid 往返一致。"""
        for gx in range(5):
            for gy in range(5):
                p = Position.from_grid(gx, gy, 1.5)
                assert p.to_grid(1.5) == (gx, gy)


# ===========================================================================
# S-2: 距離與空間查詢
# ===========================================================================


class TestDistance:
    """Euclidean 距離函式。"""

    def test_basic(self):
        a = Position(x=0, y=0)
        b = Position(x=3, y=4)
        assert distance(a, b) == pytest.approx(5.0)

    def test_same_point(self):
        a = Position(x=1.5, y=1.5)
        assert distance(a, a) == 0.0

    def test_diagonal_grid(self):
        """對角線 1 格 ≈ 2.12m（不再是 Chebyshev 的 1.5m）。"""
        a = Position.from_grid(0, 0, 1.5)
        b = Position.from_grid(1, 1, 1.5)
        assert distance(a, b) == pytest.approx(1.5 * math.sqrt(2))


class TestGridDistanceDeprecated:
    """grid_distance（deprecated）仍正確工作。"""

    def test_chebyshev(self):
        a = Position.from_grid(0, 0, 1.5)
        b = Position.from_grid(3, 2, 1.5)
        assert grid_distance(a, b, 1.5) == pytest.approx(4.5)  # max(3,2)*1.5


class TestActorsInRadius:
    """actors_in_radius 查詢。"""

    def test_find_within(self, empty_map: MapState):
        a1 = _make_actor("a1", 2, 2)
        a2 = _make_actor("a2", 3, 2)
        a3 = _make_actor("a3", 4, 4)
        empty_map.actors = [a1, a2, a3]

        center = Position.from_grid(2, 2, 1.5)
        result = actors_in_radius(center, 2.0, empty_map)
        ids = {a.id for a in result}
        assert "a1" in ids  # 自己（距離 0）
        assert "a2" in ids  # 距離 1.5m
        assert "a3" not in ids  # 距離 > 2m

    def test_exclude_dead(self, empty_map: MapState):
        a_dead = _make_actor("dead", 2, 2, alive=False)
        empty_map.actors = [a_dead]
        center = Position.from_grid(2, 2, 1.5)
        assert actors_in_radius(center, 5.0, empty_map) == []

    def test_include_dead(self, empty_map: MapState):
        a_dead = _make_actor("dead", 2, 2, alive=False)
        empty_map.actors = [a_dead]
        center = Position.from_grid(2, 2, 1.5)
        assert len(actors_in_radius(center, 5.0, empty_map, alive_only=False)) == 1


# ===========================================================================
# S-3: 碰撞系統
# ===========================================================================


class TestSizeRadius:
    """體型碰撞半徑定義。"""

    def test_medium_radius(self):
        assert SIZE_RADIUS_M[Size.MEDIUM] == 0.75

    def test_all_sizes_defined(self):
        for s in Size:
            assert s in SIZE_RADIUS_M


class TestCanTraverse:
    """穿越規則（D&D 5e PHB）。"""

    def test_friendly_always(self):
        """非敵對：永遠可穿越。"""
        assert can_traverse(Size.MEDIUM, Size.MEDIUM, is_hostile=False) is True

    def test_hostile_same_size(self):
        """敵對同體型：不可穿越。"""
        assert can_traverse(Size.MEDIUM, Size.MEDIUM, is_hostile=True) is False

    def test_hostile_one_size_diff(self):
        """敵對差 1 級：不可穿越。"""
        assert can_traverse(Size.MEDIUM, Size.LARGE, is_hostile=True) is False

    def test_hostile_two_size_diff(self):
        """敵對差 2 級：可穿越。"""
        assert can_traverse(Size.MEDIUM, Size.HUGE, is_hostile=True) is True
        assert can_traverse(Size.TINY, Size.MEDIUM, is_hostile=True) is True

    def test_hostile_three_size_diff(self):
        """敵對差 3 級：可穿越。"""
        assert can_traverse(Size.TINY, Size.LARGE, is_hostile=True) is True


class TestCheckCollision:
    """碰撞偵測。"""

    def test_no_collision_empty(self, empty_map: MapState):
        pos = Position.from_grid(2, 2, 1.5)
        assert check_collision(pos, Size.MEDIUM, empty_map) is None

    def test_collision_same_cell(self, empty_map: MapState):
        a = _make_actor("a1", 2, 2)
        empty_map.actors = [a]
        pos = Position.from_grid(2, 2, 1.5)
        result = check_collision(pos, Size.MEDIUM, empty_map)
        assert result is not None
        assert result.id == "a1"

    def test_exclude_self(self, empty_map: MapState):
        a = _make_actor("a1", 2, 2)
        empty_map.actors = [a]
        pos = Position.from_grid(2, 2, 1.5)
        assert check_collision(pos, Size.MEDIUM, empty_map, exclude_id="a1") is None

    def test_no_collision_far(self, empty_map: MapState):
        a = _make_actor("a1", 0, 0)
        empty_map.actors = [a]
        pos = Position.from_grid(4, 4, 1.5)
        assert check_collision(pos, Size.MEDIUM, empty_map) is None


class TestCanEndMoveAt:
    """停留判定。"""

    def test_empty_ok(self, empty_map: MapState):
        pos = Position.from_grid(2, 2, 1.5)
        assert can_end_move_at(pos, Size.MEDIUM, empty_map) is True

    def test_occupied_blocked(self, empty_map: MapState):
        """不可在任何生物空間內結束移動（含友方）。"""
        a = _make_actor("a1", 2, 2)
        empty_map.actors = [a]
        pos = Position.from_grid(2, 2, 1.5)
        assert can_end_move_at(pos, Size.MEDIUM, empty_map) is False

    def test_self_excluded(self, empty_map: MapState):
        a = _make_actor("a1", 2, 2)
        empty_map.actors = [a]
        pos = Position.from_grid(2, 2, 1.5)
        assert can_end_move_at(pos, Size.MEDIUM, empty_map, mover_id="a1") is True


class TestFindNearestValid:
    """找到最近有效位置。"""

    def test_already_valid(self, empty_map: MapState):
        pos = Position.from_grid(2, 2, 1.5)
        result = find_nearest_valid_position(pos, Size.MEDIUM, empty_map)
        assert result.x == pos.x and result.y == pos.y

    def test_find_adjacent(self, empty_map: MapState):
        blocker = _make_actor("b", 2, 2)
        empty_map.actors = [blocker]
        pos = Position.from_grid(2, 2, 1.5)
        result = find_nearest_valid_position(pos, Size.MEDIUM, empty_map, exclude_id="me")
        # 應找到鄰格
        rgx, rgy = result.to_grid(1.5)
        assert (rgx, rgy) != (2, 2)
        assert 0 <= rgx < 5 and 0 <= rgy < 5


# ===========================================================================
# 既有功能迴歸測試
# ===========================================================================


class TestLineOfSight:
    """視線判定（float Position 輸入）。"""

    def test_clear_los(self, empty_map: MapState):
        a = Position.from_grid(0, 0, 1.5)
        b = Position.from_grid(4, 4, 1.5)
        assert has_line_of_sight(a, b, empty_map) is True

    def test_blocked_by_wall(self, map_with_wall: MapState):
        a = Position.from_grid(0, 0, 1.5)
        b = Position.from_grid(4, 4, 1.5)
        # (2,2) 有牆，Bresenham 路徑會經過
        assert has_line_of_sight(a, b, map_with_wall) is False


class TestCover:
    """掩蔽判定。"""

    def test_no_cover(self, empty_map: MapState):
        a = Position.from_grid(0, 0, 1.5)
        b = Position.from_grid(3, 0, 1.5)
        assert determine_cover_from_grid(a, b, empty_map) == CoverType.NONE

    def test_half_cover(self, map_with_wall: MapState):
        a = Position.from_grid(1, 2, 1.5)
        b = Position.from_grid(3, 2, 1.5)
        result = determine_cover_from_grid(a, b, map_with_wall)
        assert result in (CoverType.HALF, CoverType.THREE_QUARTERS)


class TestMoveEntity:
    """移動（網格位移 + 公尺座標儲存 + D&D 5e 規則）。"""

    def test_basic_move(self, empty_map: MapState):
        actor = _make_actor("m", 2, 2)
        empty_map.actors = [actor]
        result = move_entity(actor, 1, 0, empty_map, 9.0)
        assert result.success is True
        assert actor.grid_pos(1.5) == (3, 2)
        assert result.speed_remaining == pytest.approx(7.5)

    def test_blocked_move(self, map_with_wall: MapState):
        actor = _make_actor("m", 1, 2)
        map_with_wall.actors = [actor]
        result = move_entity(actor, 1, 0, map_with_wall, 9.0)
        assert result.success is False

    def test_no_speed(self, empty_map: MapState):
        actor = _make_actor("m", 2, 2)
        empty_map.actors = [actor]
        result = move_entity(actor, 1, 0, empty_map, 0.5)
        assert result.success is False

    def test_oa_event(self, empty_map: MapState):
        """離開敵方觸及範圍觸發 OA 事件。"""
        mover = _make_actor("pc", 2, 2, combatant_type="character")
        enemy = _make_actor("mob", 3, 2)
        empty_map.actors = [mover, enemy]
        # 向左移動 (2,2)→(1,2)，離開 enemy 的 1.5m 觸及範圍
        result = move_entity(mover, -1, 0, empty_map, 9.0)
        assert result.success is True
        oa_events = [e for e in result.events if e.event_type == "opportunity_attack"]
        assert len(oa_events) == 1
        assert oa_events[0].trigger_actor_id == "mob"

    def test_traverse_hostile_blocked(self, empty_map: MapState):
        """不可穿越敵對同體型生物。"""
        mover = _make_actor("pc", 2, 2, combatant_type="character")
        enemy = _make_actor("mob", 3, 2)
        empty_map.actors = [mover, enemy]
        result = move_entity(mover, 1, 0, empty_map, 9.0)
        assert result.success is False

    def test_traverse_friendly_difficult(self, empty_map: MapState):
        """穿越友軍空間視為困難地形（×2 消耗）。"""
        mover = _make_actor("pc1", 2, 2, combatant_type="character")
        ally = _make_actor("pc2", 3, 2, combatant_type="character")
        empty_map.actors = [mover, ally]
        result = move_entity(
            mover,
            1,
            0,
            empty_map,
            9.0,
            allies={mover.id, ally.id},
        )
        assert result.success is True
        # 困難地形：消耗 3.0m 而非 1.5m
        assert result.speed_remaining == pytest.approx(6.0)


class TestBFS:
    """BFS 尋路。"""

    def test_already_in_range(self, empty_map: MapState):
        start = Position.from_grid(2, 2, 1.5)
        target = Position.from_grid(3, 2, 1.5)
        path = bfs_path_to_range(
            start,
            target,
            1,
            empty_map,
            10,
            mover_id=_make_actor("x", 0, 0).combatant_id,
            friendly_ids=set(),
        )
        assert path == []

    def test_basic_path(self, empty_map: MapState):
        start = Position.from_grid(0, 0, 1.5)
        target = Position.from_grid(4, 0, 1.5)
        from uuid import uuid4

        mid = uuid4()
        path = bfs_path_to_range(
            start,
            target,
            1,
            empty_map,
            10,
            mover_id=mid,
            friendly_ids=set(),
        )
        assert path is not None
        assert len(path) > 0


class TestSpellRange:
    """法術射程驗證。"""

    def test_self_always_ok(self):
        spell = Spell(name="t", level=0, school=SpellSchool.EVOCATION, range="Self")
        assert validate_spell_range(spell, 100.0) is None

    def test_touch_in_range(self):
        spell = Spell(name="t", level=0, school=SpellSchool.EVOCATION, range="Touch")
        assert validate_spell_range(spell, 1.0) is None

    def test_touch_out_of_range(self):
        spell = Spell(name="t", level=0, school=SpellSchool.EVOCATION, range="Touch")
        result = validate_spell_range(spell, 5.0)
        assert result is not None
        assert "觸及" in result or "觸碰" in result

    def test_ranged_in_range(self):
        spell = Spell(name="t", level=0, school=SpellSchool.EVOCATION, range="120ft")
        assert validate_spell_range(spell, 30.0) is None

    def test_ranged_out(self):
        spell = Spell(name="t", level=0, school=SpellSchool.EVOCATION, range="120ft")
        result = validate_spell_range(spell, 40.0)
        assert result is not None


class TestZoneQuery:
    """區域查詢。"""

    def test_float_position(self):
        zones = [Zone(name="z1", x_min=0, y_min=0, x_max=3, y_max=3)]
        z = zone_for_position(3.75, 3.75, zones, grid_size=1.5)
        assert z is not None
        assert z.name == "z1"

    def test_outside(self):
        zones = [Zone(name="z1", x_min=0, y_min=0, x_max=1, y_max=1)]
        z = zone_for_position(7.5, 7.5, zones, grid_size=1.5)
        assert z is None


class TestHostileWithinMelee:
    """近戰範圍偵測（Euclidean 距離）。"""

    def test_adjacent(self, empty_map: MapState):
        a = _make_actor("a", 2, 2, combatant_type="character")
        b = _make_actor("b", 3, 2)
        empty_map.actors = [a, b]
        assert has_hostile_within_melee(a, empty_map, allies={a.combatant_id})

    def test_far(self, empty_map: MapState):
        a = _make_actor("a", 0, 0, combatant_type="character")
        b = _make_actor("b", 4, 4)
        empty_map.actors = [a, b]
        assert not has_hostile_within_melee(a, empty_map, allies={a.combatant_id})


class TestParseSpellRange:
    """法術射程解析。"""

    def test_feet(self):
        assert parse_spell_range_meters("120ft") == pytest.approx(36.0)

    def test_self(self):
        assert parse_spell_range_meters("Self") is None

    def test_self_cone(self):
        assert parse_spell_range_meters("Self (15ft cone)") is None

    def test_touch(self):
        assert parse_spell_range_meters("Touch") is None
