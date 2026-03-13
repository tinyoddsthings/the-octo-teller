"""AoE 瞄準系統測試。"""

from __future__ import annotations

import math
from uuid import uuid4

import pytest

from tot.gremlins.bone_engine.aoe import (
    CONE_HALF_ANGLE_COS,
    _in_cone,
    _in_cube,
    _in_line,
    _in_sphere,
    check_friendly_fire,
    compute_aoe_center,
    ft_to_m,
    get_actors_in_aoe,
    preview_aoe,
)
from tot.models import (
    Actor,
    AoeShape,
    MapManifest,
    MapState,
    Position,
    Spell,
    SpellEffectType,
    SpellSchool,
)

GS = 1.5  # 每格 1.5m


def _make_actor(
    gx: int,
    gy: int,
    name: str = "A",
    *,
    combatant_type: str = "monster",
    is_alive: bool = True,
) -> Actor:
    """建立位於網格中心的 Actor。"""
    return Actor(
        id=f"act_{name}",
        x=gx * GS + GS / 2,
        y=gy * GS + GS / 2,
        combatant_id=uuid4(),
        combatant_type=combatant_type,
        name=name,
        is_alive=is_alive,
    )


def _make_map(actors: list[Actor], grid_w: int = 10, grid_h: int = 10) -> MapState:
    """建立含 actors 的空白地圖（width/height 為公尺）。"""
    return MapState(
        manifest=MapManifest(
            id="test",
            name="test",
            width=grid_w * GS,
            height=grid_h * GS,
        ),
        actors=actors,
    )


def _fireball_spell() -> Spell:
    return Spell(
        name="火球術",
        level=3,
        school=SpellSchool.EVOCATION,
        effect_type=SpellEffectType.DAMAGE,
        aoe_shape=AoeShape.SPHERE,
        aoe_radius_ft=20,
        range="150ft",
    )


def _cone_spell() -> Spell:
    return Spell(
        name="燃燒之手",
        level=1,
        school=SpellSchool.EVOCATION,
        effect_type=SpellEffectType.DAMAGE,
        aoe_shape=AoeShape.CONE,
        aoe_length_ft=15,
        range="Self (15ft cone)",
    )


def _cube_spell() -> Spell:
    return Spell(
        name="雷鳴波",
        level=1,
        school=SpellSchool.EVOCATION,
        effect_type=SpellEffectType.DAMAGE,
        aoe_shape=AoeShape.CUBE,
        aoe_width_ft=15,
        range="Self (15ft cube)",
    )


# ---------------------------------------------------------------------------
# 單元測試：形狀判定
# ---------------------------------------------------------------------------


class TestSphere:
    def test_inside(self):
        assert _in_sphere(Position(x=1, y=0), Position(x=0, y=0), 2.0)

    def test_on_edge(self):
        assert _in_sphere(Position(x=2, y=0), Position(x=0, y=0), 2.0)

    def test_outside(self):
        assert not _in_sphere(Position(x=3, y=0), Position(x=0, y=0), 2.0)


class TestCone:
    def test_in_cone_center(self):
        """正前方、距離內 → 命中。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=3, y=0)
        assert _in_cone(target, origin, direction, 5.0)

    def test_in_cone_slight_angle(self):
        """略偏但在半角內 → 命中。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        # 偏 10° ≈ cos(10°) ≈ 0.985 > CONE_HALF_ANGLE_COS
        target = Position(x=4, y=0.7)
        assert _in_cone(target, origin, direction, 5.0)

    def test_outside_cone_angle(self):
        """超出半角 → 未命中。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        # 偏 45° → cos(45°) ≈ 0.707 < 0.894
        target = Position(x=3, y=3)
        assert not _in_cone(target, origin, direction, 5.0)

    def test_outside_cone_distance(self):
        """在角度內但超出距離 → 未命中。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=6, y=0)
        assert not _in_cone(target, origin, direction, 5.0)

    def test_at_origin(self):
        """在原點上 → 命中。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        assert _in_cone(origin, origin, direction, 5.0)

    def test_cone_half_angle_value(self):
        """驗證 CONE_HALF_ANGLE_COS ≈ cos(atan(1/2))。"""
        expected = math.cos(math.atan(0.5))
        assert abs(CONE_HALF_ANGLE_COS - expected) < 1e-6


class TestCube:
    def test_inside(self):
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=2, y=1)
        assert _in_cube(target, origin, direction, 5.0)

    def test_outside_forward(self):
        """超出前方距離。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=6, y=0)
        assert not _in_cube(target, origin, direction, 5.0)

    def test_outside_lateral(self):
        """超出側向。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=2, y=4)
        assert not _in_cube(target, origin, direction, 5.0)

    def test_behind(self):
        """在施法者背後。"""
        origin = Position(x=0, y=0)
        direction = Position(x=5, y=0)
        target = Position(x=-1, y=0)
        assert not _in_cube(target, origin, direction, 5.0)


class TestLine:
    def test_inside(self):
        origin = Position(x=0, y=0)
        direction = Position(x=10, y=0)
        target = Position(x=5, y=0.5)
        assert _in_line(target, origin, direction, 10.0, 2.0)

    def test_outside_width(self):
        origin = Position(x=0, y=0)
        direction = Position(x=10, y=0)
        target = Position(x=5, y=2)
        assert not _in_line(target, origin, direction, 10.0, 2.0)


# ---------------------------------------------------------------------------
# 整合測試
# ---------------------------------------------------------------------------


class TestComputeCenter:
    def test_single(self):
        a = _make_actor(3, 3, "solo")
        center = compute_aoe_center([a])
        assert center.x == a.x
        assert center.y == a.y

    def test_centroid(self):
        a1 = _make_actor(0, 0, "a1")
        a2 = _make_actor(4, 0, "a2")
        center = compute_aoe_center([a1, a2])
        expected_x = (a1.x + a2.x) / 2
        assert abs(center.x - expected_x) < 0.01

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="至少需要一個目標"):
            compute_aoe_center([])


class TestGetActorsInAoe:
    def test_fireball_hits(self):
        """火球術 20ft 半徑 = 6m，應命中近處目標。"""
        target = _make_actor(3, 3, "goblin")
        far = _make_actor(9, 9, "far_goblin")
        ms = _make_map([target, far])
        center = Position(x=target.x, y=target.y)
        spell = _fireball_spell()
        hit = get_actors_in_aoe(center, spell, Position(x=0, y=0), ms)
        assert target in hit
        assert far not in hit

    def test_cone_hits_forward(self):
        """燃燒之手 15ft 錐形 = 4.5m。"""
        caster_pos = Position(x=GS / 2, y=GS / 2)  # grid (0,0) center
        target_ahead = _make_actor(2, 0, "ahead")  # x=3.75, y=0.75
        target_behind = _make_actor(0, 2, "behind")  # behind/above
        ms = _make_map([target_ahead, target_behind])
        # 瞄準方向 = 正右方
        direction = Position(x=10, y=GS / 2)
        spell = _cone_spell()
        hit = get_actors_in_aoe(direction, spell, caster_pos, ms)
        assert target_ahead in hit
        assert target_behind not in hit

    def test_dead_excluded(self):
        """死亡單位不被命中（alive_only=True）。"""
        dead = _make_actor(3, 3, "dead", is_alive=False)
        ms = _make_map([dead])
        center = Position(x=dead.x, y=dead.y)
        hit = get_actors_in_aoe(center, _fireball_spell(), Position(x=0, y=0), ms)
        assert dead not in hit

    def test_non_aoe_spell(self):
        """非 AoE 法術 → 空列表。"""
        spell = Spell(
            name="火焰箭",
            level=0,
            school=SpellSchool.EVOCATION,
            effect_type=SpellEffectType.DAMAGE,
        )
        actor = _make_actor(1, 1, "a")
        ms = _make_map([actor])
        assert get_actors_in_aoe(Position(x=0, y=0), spell, Position(x=0, y=0), ms) == []


class TestFriendlyFire:
    def test_detects_ally(self):
        ally = _make_actor(3, 3, "hero", combatant_type="character")
        enemy = _make_actor(3, 4, "goblin")
        allies = {str(ally.combatant_id)}
        result = check_friendly_fire([ally, enemy], allies)
        assert ally in result
        assert enemy not in result


class TestPreview:
    def test_preview_with_friendly(self):
        """預覽包含友軍警告。"""
        hero = _make_actor(3, 3, "Hero", combatant_type="character")
        goblin = _make_actor(3, 4, "Goblin")
        ms = _make_map([hero, goblin])
        center = Position(x=hero.x, y=hero.y)
        allies = {str(hero.combatant_id)}
        preview = preview_aoe(center, _fireball_spell(), Position(x=0, y=0), ms, allies)
        assert len(preview.hit_allies) >= 1
        assert "友軍" in preview.message

    def test_preview_no_hit(self):
        """無命中目標。"""
        ms = _make_map([])
        center = Position(x=5, y=5)
        preview = preview_aoe(center, _fireball_spell(), Position(x=0, y=0), ms, set())
        assert "無命中目標" in preview.message


class TestFtToM:
    def test_5ft(self):
        assert ft_to_m(5) == 1.5

    def test_20ft(self):
        assert abs(ft_to_m(20) - 6.0) < 0.01
