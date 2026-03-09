"""探索系統測試——破門、噪音、警戒連動。"""

from __future__ import annotations

import random

from tot.gremlins.bone_engine.deployment import resolve_encounter
from tot.gremlins.bone_engine.exploration import (
    MoveResult,
    force_open_edge,
    unlock_edge,
)
from tot.models import (
    AbilityScores,
    Character,
    EncounterType,
    ExplorationEdge,
    ExplorationMap,
    ExplorationNode,
    ExplorationState,
    Monster,
    Skill,
)

# ---------------------------------------------------------------------------
# 共用 fixtures
# ---------------------------------------------------------------------------


def _make_map() -> ExplorationMap:
    """建立含鎖門 + 可破門的測試地圖。"""
    return ExplorationMap(
        id="test_map",
        name="測試地圖",
        scale="dungeon",
        entry_node_id="room_a",
        nodes=[
            ExplorationNode(id="room_a", name="房間 A", node_type="room"),
            ExplorationNode(id="room_b", name="房間 B", node_type="room"),
            ExplorationNode(id="room_c", name="房間 C", node_type="room"),
        ],
        edges=[
            ExplorationEdge(
                id="door_breakable",
                from_node_id="room_a",
                to_node_id="room_b",
                name="木門",
                is_locked=True,
                lock_dc=12,
                break_dc=15,
                distance_minutes=1,
            ),
            ExplorationEdge(
                id="door_unbreakable",
                from_node_id="room_a",
                to_node_id="room_c",
                name="魔法封印門",
                is_locked=True,
                lock_dc=20,
                break_dc=0,  # 不可破壞
                distance_minutes=1,
            ),
        ],
    )


def _make_state() -> ExplorationState:
    return ExplorationState(
        current_map_id="test_map",
        current_node_id="room_a",
    )


def _make_characters() -> list[Character]:
    return [
        Character(
            name="Test Fighter",
            char_class="Fighter",
            level=3,
            ability_scores=AbilityScores(STR=16, DEX=14, CON=14, INT=10, WIS=12, CHA=10),
            proficiency_bonus=2,
            hp_max=30,
            hp_current=30,
            ac=18,
            speed=9,
            skill_proficiencies=[Skill.ATHLETICS, Skill.STEALTH],
        ),
    ]


def _make_monsters() -> list[Monster]:
    return [
        Monster(
            name="Goblin",
            monster_type="Goblin",
            ability_scores=AbilityScores(STR=8, DEX=14, CON=10, INT=10, WIS=8, CHA=8),
            hp_max=7,
            hp_current=7,
            ac=15,
            speed=9,
        ),
    ]


# ---------------------------------------------------------------------------
# 破門測試
# ---------------------------------------------------------------------------


class TestForceOpenEdge:
    """force_open_edge() 測試。"""

    def test_force_open_success(self):
        """STR 檢定 >= break_dc → 門打開 + noise_generated。"""
        state = _make_state()
        exp_map = _make_map()

        result = force_open_edge(state, exp_map, "door_breakable", str_check_total=15)

        assert result.success is True
        assert result.noise_generated is True
        # 門應該解鎖了
        edge = next(e for e in exp_map.edges if e.id == "door_breakable")
        assert edge.is_locked is False

    def test_force_open_failure(self):
        """STR 檢定 < break_dc → 門沒開，但仍有 noise_generated。"""
        state = _make_state()
        exp_map = _make_map()

        result = force_open_edge(state, exp_map, "door_breakable", str_check_total=10)

        assert result.success is False
        assert result.noise_generated is True
        # 門仍然鎖著
        edge = next(e for e in exp_map.edges if e.id == "door_breakable")
        assert edge.is_locked is True

    def test_force_open_unbreakable(self):
        """break_dc == 0 → 無法破壞，也不產生噪音。"""
        state = _make_state()
        exp_map = _make_map()

        result = force_open_edge(state, exp_map, "door_unbreakable", str_check_total=25)

        assert result.success is False
        assert result.noise_generated is False
        assert "無法被暴力破開" in result.message

    def test_force_open_already_unlocked(self):
        """門沒鎖時不需要破門。"""
        state = _make_state()
        exp_map = _make_map()
        # 先解鎖
        edge = next(e for e in exp_map.edges if e.id == "door_breakable")
        edge.is_locked = False

        result = force_open_edge(state, exp_map, "door_breakable", str_check_total=20)

        assert result.success is True
        assert result.noise_generated is False

    def test_force_open_noise_on_force_false(self):
        """noise_on_force=False 時不產生噪音。"""
        state = _make_state()
        exp_map = _make_map()
        edge = next(e for e in exp_map.edges if e.id == "door_breakable")
        edge.noise_on_force = False

        result = force_open_edge(state, exp_map, "door_breakable", str_check_total=15)

        assert result.success is True
        assert result.noise_generated is False


# ---------------------------------------------------------------------------
# MoveResult noise_generated 預設值測試
# ---------------------------------------------------------------------------


class TestMoveResultNoise:
    """MoveResult.noise_generated 預設值。"""

    def test_move_no_noise_by_default(self):
        """普通移動不產生噪音。"""
        result = MoveResult(success=True, message="ok")
        assert result.noise_generated is False

    def test_unlock_no_noise(self):
        """開鎖不產生噪音。"""
        state = _make_state()
        exp_map = _make_map()

        result = unlock_edge(state, exp_map, "door_breakable", check_total=15)

        assert result.success is True
        assert result.noise_generated is False


# ---------------------------------------------------------------------------
# 警戒 + 遭遇判定連動測試
# ---------------------------------------------------------------------------


class TestAlertedEncounter:
    """alerted=True 時 resolve_encounter 不給 surprise。"""

    def test_alerted_overrides_stealth(self):
        """alerted=True 即使 stealth_intent=True 也回傳 NORMAL。"""
        characters = _make_characters()
        monsters = _make_monsters()
        rng = random.Random(42)

        result = resolve_encounter(
            characters,
            monsters,
            stealth_intent=True,
            alerted=True,
            rng=rng,
        )

        assert result.encounter_type == EncounterType.NORMAL
        assert "驚動" in result.message

    def test_not_alerted_can_surprise(self):
        """alerted=False 且 stealth_intent=True 有機會 surprise。"""
        characters = _make_characters()
        monsters = _make_monsters()

        # 用固定種子找到可以 surprise 的情況
        # 敵方被動察覺 = 10 + WIS mod(-1) = 9
        # 角色 Stealth bonus = DEX mod(+2) + proficiency(+2) = +4
        # 只要擲出 >= 5 就 pass（很容易）
        surprise_found = False
        for seed in range(100):
            rng = random.Random(seed)
            result = resolve_encounter(
                characters,
                monsters,
                stealth_intent=True,
                alerted=False,
                rng=rng,
            )
            if result.encounter_type == EncounterType.SURPRISE:
                surprise_found = True
                break

        assert surprise_found, "在 100 個種子中應該至少有一次 surprise"

    def test_alerted_no_stealth_rolls(self):
        """alerted=True 時不擲潛行骰（stealth_rolls 為空）。"""
        characters = _make_characters()
        monsters = _make_monsters()

        result = resolve_encounter(
            characters,
            monsters,
            stealth_intent=True,
            alerted=True,
        )

        assert result.stealth_rolls == {}
