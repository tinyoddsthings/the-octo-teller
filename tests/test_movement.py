"""bone_engine/movement.py + combat.py OA 查詢單元測試。

涵蓋：
- build_friendly_ids
- build_actor_lists
- move_toward_target
- path_to_attack_range
- check_opportunity_attacks_on_step
"""

from __future__ import annotations

import math
import random
from uuid import UUID, uuid4

from tot.gremlins.bone_engine.combat import (
    StepOAResult,
    check_opportunity_attacks_on_step,
    get_reach_m,
)
from tot.gremlins.bone_engine.movement import (
    build_actor_lists,
    build_friendly_ids,
    move_toward_target,
    path_to_attack_range,
)
from tot.models import (
    AbilityScores,
    ActiveCondition,
    Actor,
    Character,
    Combatant,
    CombatState,
    Condition,
    DamageType,
    InitiativeEntry,
    MapManifest,
    MapState,
    Monster,
    MonsterAction,
    TurnState,
    Wall,
    Weapon,
)

GS = 1.5  # 標準 grid_size


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_map(grid_w: int = 10, grid_h: int = 10) -> MapState:
    """空白地圖（width/height 為公尺）。"""
    manifest = MapManifest(name="test", width=grid_w * GS, height=grid_h * GS)
    return MapState(manifest=manifest)


def _grid_center(gx: int, gy: int) -> tuple[float, float]:
    """格子中心公尺座標。"""
    return gx * GS + GS / 2, gy * GS + GS / 2


def _make_character(
    name: str = "PC",
    *,
    char_id: UUID | None = None,
    hp: int = 20,
    ac: int = 15,
    weapon_reach: float = 1.5,
) -> Character:
    return Character(
        id=char_id or uuid4(),
        name=name,
        char_class="Fighter",
        level=1,
        hp_max=hp,
        hp_current=hp,
        ac=ac,
        speed=30,
        ability_scores=AbilityScores(STR=16, DEX=14, CON=14, INT=10, WIS=12, CHA=8),
        weapons=[
            Weapon(
                name="Longsword",
                damage_dice="1d8",
                damage_type=DamageType.SLASHING,
                range_normal=weapon_reach,
            )
        ],
    )


def _make_monster(
    name: str = "Goblin",
    *,
    mon_id: UUID | None = None,
    hp: int = 7,
    ac: int = 13,
    reach: float = 1.5,
) -> Monster:
    return Monster(
        id=mon_id or uuid4(),
        name=name,
        hp_max=hp,
        hp_current=hp,
        ac=ac,
        speed=30,
        ability_scores=AbilityScores(STR=8, DEX=14, CON=10, INT=10, WIS=8, CHA=8),
        actions=[
            MonsterAction(
                name="Scimitar",
                attack_bonus=4,
                damage_dice="1d6",
                damage_type=DamageType.SLASHING,
                reach=reach,
            )
        ],
    )


def _make_actor(
    combatant_id: UUID,
    gx: int,
    gy: int,
    *,
    combatant_type: str = "character",
    name: str = "actor",
    alive: bool = True,
) -> Actor:
    mx, my = _grid_center(gx, gy)
    return Actor(
        id=f"a_{gx}_{gy}",
        x=mx,
        y=my,
        combatant_id=combatant_id,
        combatant_type=combatant_type,
        name=name,
        is_blocking=True,
        is_alive=alive,
    )


def _make_combat_state(
    characters: list[Character],
    monsters: list[Monster],
    *,
    speed: float = 30.0,
) -> CombatState:
    """建立含先攻順序的 CombatState。"""
    order = []
    for c in characters:
        order.append(
            InitiativeEntry(
                combatant_type="character",
                combatant_id=c.id,
                initiative=10,
            )
        )
    for m in monsters:
        order.append(
            InitiativeEntry(
                combatant_type="monster",
                combatant_id=m.id,
                initiative=10,
            )
        )
    return CombatState(
        round_number=1,
        current_turn_index=0,
        initiative_order=order,
        is_active=True,
        turn_state=TurnState(movement_remaining=speed),
    )


# ===========================================================================
# build_friendly_ids
# ===========================================================================


class TestBuildFriendlyIds:
    def test_character_returns_all_character_ids(self):
        c1 = _make_character("PC1")
        c2 = _make_character("PC2")
        m1 = _make_monster("Goblin")
        ids = build_friendly_ids(c1, [c1, c2], [m1])
        assert ids == {c1.id, c2.id}

    def test_monster_returns_all_monster_ids(self):
        c1 = _make_character("PC1")
        m1 = _make_monster("Goblin A")
        m2 = _make_monster("Goblin B")
        ids = build_friendly_ids(m1, [c1], [m1, m2])
        assert ids == {m1.id, m2.id}


# ===========================================================================
# build_actor_lists
# ===========================================================================


class TestBuildActorLists:
    def test_enemy_in_blocked_friendly_in_passable(self):
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        pc2 = _make_character("PC2")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 2, 2, name="PC")
        mon_actor = _make_actor(mon.id, 5, 5, combatant_type="monster", name="Goblin")
        pc2_actor = _make_actor(pc2.id, 3, 3, name="PC2")
        map_state.actors = [pc_actor, mon_actor, pc2_actor]

        result = build_actor_lists(pc_actor, pc, map_state, [pc, pc2], [mon])
        assert mon_actor in result.blocked
        assert pc2_actor in result.passable
        assert pc_actor not in result.blocked
        assert pc_actor not in result.passable

    def test_exclude_self(self):
        pc = _make_character("PC")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 2, 2, name="PC")
        map_state.actors = [pc_actor]

        result = build_actor_lists(pc_actor, pc, map_state, [pc], [])
        assert len(result.blocked) == 0
        assert len(result.passable) == 0

    def test_exclude_id(self):
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 2, 2, name="PC")
        mon_actor = _make_actor(mon.id, 5, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]

        result = build_actor_lists(pc_actor, pc, map_state, [pc], [mon], exclude_id=mon.id)
        assert len(result.blocked) == 0

    def test_dead_actor_excluded(self):
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 2, 2, name="PC")
        mon_actor = _make_actor(mon.id, 5, 5, combatant_type="monster", name="Goblin", alive=False)
        map_state.actors = [pc_actor, mon_actor]

        result = build_actor_lists(pc_actor, pc, map_state, [pc], [mon])
        assert len(result.blocked) == 0


# ===========================================================================
# move_toward_target
# ===========================================================================


class TestMoveTowardTarget:
    def test_clear_path(self):
        """直線可達 → 回傳路徑和成本。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 1, 5, name="PC")
        mon_actor = _make_actor(mon.id, 7, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon], speed=30.0)

        result = move_toward_target(
            pc_actor,
            mon.id,
            1.5,
            pc,
            cs,
            map_state,
            [pc],
            [mon],
            greedy_fallback=False,
        )
        assert result is not None
        path, cost = result
        assert len(path) > 0
        assert cost > 0

    def test_already_in_range(self):
        """已在範圍內 → 空路徑、成本 0。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 5, 5, name="PC")
        mon_actor = _make_actor(mon.id, 6, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon])

        result = move_toward_target(
            pc_actor,
            mon.id,
            1.5,
            pc,
            cs,
            map_state,
            [pc],
            [mon],
        )
        assert result is not None
        path, cost = result
        assert path == []
        assert cost == 0.0

    def test_obstacle_detour(self):
        """有障礙 → 繞行路徑（路徑成本 > 直線距離）。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        # 在 x=7.5m 建一排牆（y=3.0~12.0m），對應 grid x=5, y=2~7
        wall = Wall(x=7.5, y=3.0, width=1.5, height=9.0, name="wall")
        map_state.walls = [wall]
        pc_actor = _make_actor(pc.id, 3, 5, name="PC")
        mon_actor = _make_actor(mon.id, 7, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon], speed=30.0)

        result = move_toward_target(
            pc_actor,
            mon.id,
            1.5,
            pc,
            cs,
            map_state,
            [pc],
            [mon],
            greedy_fallback=False,
        )
        assert result is not None
        path, cost = result
        assert len(path) > 0
        # 繞行成本 > 直線距離
        direct_dist = math.sqrt((mon_actor.x - pc_actor.x) ** 2 + (mon_actor.y - pc_actor.y) ** 2)
        assert cost > direct_dist - GS  # 減去 reach

    def test_greedy_fallback(self):
        """速度不足 → greedy_fallback 截斷。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 1, 5, name="PC")
        mon_actor = _make_actor(mon.id, 8, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        # 只給少量移動速度
        cs = _make_combat_state([pc], [mon], speed=3.0)

        result = move_toward_target(
            pc_actor,
            mon.id,
            1.5,
            pc,
            cs,
            map_state,
            [pc],
            [mon],
            greedy_fallback=True,
        )
        assert result is not None
        path, cost = result
        assert len(path) > 0
        assert cost <= 3.0 + 0.1  # 不超過移動預算

    def test_unreachable_no_greedy(self):
        """完全不可達（無 greedy_fallback）→ None。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        # 完全封閉：x=7.5m 全高牆
        wall = Wall(x=7.5, y=0.0, width=1.5, height=15.0, name="wall")
        map_state.walls = [wall]
        pc_actor = _make_actor(pc.id, 3, 5, name="PC")
        mon_actor = _make_actor(mon.id, 7, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon], speed=30.0)

        result = move_toward_target(
            pc_actor,
            mon.id,
            1.5,
            pc,
            cs,
            map_state,
            [pc],
            [mon],
            greedy_fallback=False,
        )
        assert result is None


# ===========================================================================
# path_to_attack_range
# ===========================================================================


class TestPathToAttackRange:
    def test_returns_correct_format(self):
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 1, 5, name="PC")
        mon_actor = _make_actor(mon.id, 7, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon], speed=30.0)
        combatant_map: dict[UUID, Combatant] = {pc.id: pc, mon.id: mon}

        result = path_to_attack_range(
            pc.id,
            mon.id,
            1,
            cs,
            map_state,
            combatant_map,
            [pc],
            [mon],
        )
        assert result is not None
        x, y, cost, path = result
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert cost > 0
        assert len(path) > 0

    def test_not_enough_speed(self):
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 1, 5, name="PC")
        mon_actor = _make_actor(mon.id, 8, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon], speed=1.0)
        combatant_map: dict[UUID, Combatant] = {pc.id: pc, mon.id: mon}

        result = path_to_attack_range(
            pc.id,
            mon.id,
            1,
            cs,
            map_state,
            combatant_map,
            [pc],
            [mon],
        )
        assert result is None


# ===========================================================================
# get_reach_m
# ===========================================================================


class TestGetReachM:
    def test_character_with_weapon(self):
        pc = _make_character("PC", weapon_reach=3.0)
        assert get_reach_m(pc) == 3.0

    def test_monster_with_action(self):
        mon = _make_monster("Ogre", reach=3.0)
        assert get_reach_m(mon) == 3.0

    def test_default_reach(self):
        pc = Character(
            name="Unarmed",
            char_class="Monk",
            level=1,
            hp_max=8,
            hp_current=8,
            ac=10,
            speed=30,
        )
        assert get_reach_m(pc) == 1.5


# ===========================================================================
# check_opportunity_attacks_on_step
# ===========================================================================


class TestCheckOAOnStep:
    def _setup_oa_scenario(
        self,
    ) -> tuple[Character, Monster, MapState, CombatState, dict[UUID, Combatant]]:
        """建立 OA 測試場景：PC 在 (3,5)，Goblin 在 (4,5)，相鄰。"""
        pc = _make_character("PC")
        mon = _make_monster("Goblin")
        map_state = _make_map()
        pc_actor = _make_actor(pc.id, 3, 5, name="PC")
        mon_actor = _make_actor(mon.id, 4, 5, combatant_type="monster", name="Goblin")
        map_state.actors = [pc_actor, mon_actor]
        cs = _make_combat_state([pc], [mon])
        combatant_map: dict[UUID, Combatant] = {pc.id: pc, mon.id: mon}
        return pc, mon, map_state, cs, combatant_map

    def test_disengaging_no_oa(self):
        """DISENGAGING 狀態 → 空 list。"""
        pc, mon, map_state, cs, cmap = self._setup_oa_scenario()
        pc.conditions.append(ActiveCondition(condition=Condition.DISENGAGING, source="test"))

        old_x, old_y = _grid_center(3, 5)
        new_x, new_y = _grid_center(2, 5)  # 離開 Goblin 的 reach
        results = check_opportunity_attacks_on_step(
            pc,
            old_x,
            old_y,
            new_x,
            new_y,
            cs,
            map_state,
            cmap,
            [pc],
            [mon],
        )
        assert results == []

    def test_leaving_reach_triggers_oa(self):
        """離開 reach → 觸發 OA。"""
        pc, mon, map_state, cs, cmap = self._setup_oa_scenario()

        old_x, old_y = _grid_center(3, 5)
        new_x, new_y = _grid_center(2, 5)  # 離開 Goblin 的 reach

        # 固定 RNG 確保可重複
        rng = random.Random(42)
        results = check_opportunity_attacks_on_step(
            pc,
            old_x,
            old_y,
            new_x,
            new_y,
            cs,
            map_state,
            cmap,
            [pc],
            [mon],
            rng=rng,
        )
        assert len(results) >= 1
        assert isinstance(results[0], StepOAResult)
        assert results[0].attacker.id == mon.id
        assert results[0].oa_result.triggered

    def test_staying_in_reach_no_oa(self):
        """留在 reach 內 → 不觸發。"""
        pc, mon, map_state, cs, cmap = self._setup_oa_scenario()

        old_x, old_y = _grid_center(3, 5)
        new_x, new_y = _grid_center(4, 6)  # 仍在 Goblin 的 reach 內（Chebyshev ≤ 1）
        results = check_opportunity_attacks_on_step(
            pc,
            old_x,
            old_y,
            new_x,
            new_y,
            cs,
            map_state,
            cmap,
            [pc],
            [mon],
        )
        assert results == []

    def test_same_team_no_oa(self):
        """同陣營 → 不觸發。"""
        pc1 = _make_character("PC1")
        pc2 = _make_character("PC2")
        map_state = _make_map()
        pc1_actor = _make_actor(pc1.id, 3, 5, name="PC1")
        pc2_actor = _make_actor(pc2.id, 4, 5, name="PC2")
        map_state.actors = [pc1_actor, pc2_actor]
        cs = _make_combat_state([pc1, pc2], [])
        cmap: dict[UUID, Combatant] = {pc1.id: pc1, pc2.id: pc2}

        old_x, old_y = _grid_center(3, 5)
        new_x, new_y = _grid_center(2, 5)
        results = check_opportunity_attacks_on_step(
            pc1,
            old_x,
            old_y,
            new_x,
            new_y,
            cs,
            map_state,
            cmap,
            [pc1, pc2],
            [],
        )
        assert results == []

    def test_no_damage_applied(self):
        """確認 HP 未被扣（caller 責任）。"""
        pc, mon, map_state, cs, cmap = self._setup_oa_scenario()
        hp_before = pc.hp_current

        old_x, old_y = _grid_center(3, 5)
        new_x, new_y = _grid_center(2, 5)
        check_opportunity_attacks_on_step(
            pc,
            old_x,
            old_y,
            new_x,
            new_y,
            cs,
            map_state,
            cmap,
            [pc],
            [mon],
        )
        # HP 不變——apply_damage 是 caller 的責任
        assert pc.hp_current == hp_before
