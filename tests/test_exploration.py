"""探索系統測試——破門、噪音、警戒連動、跳躍/墜落、崖岸遺跡地圖。"""

from __future__ import annotations

import random

from tot.data.loader import load_exploration_map
from tot.gremlins.bone_engine.deployment import resolve_encounter
from tot.gremlins.bone_engine.exploration import (
    MapRegistry,
    MoveResult,
    attempt_jump,
    calculate_fall_damage_dice,
    check_sub_map_transition,
    force_open_edge,
    move_to_node,
    register_map_tree,
    resolve_parent_map,
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
    MapStackEntry,
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


# ---------------------------------------------------------------------------
# 墜落傷害骰計算測試
# ---------------------------------------------------------------------------


class TestCalculateFallDamageDice:
    """calculate_fall_damage_dice() 規則正確性。"""

    def test_zero_height(self):
        """高度 <= 0 → 無傷害骰。"""
        assert calculate_fall_damage_dice(0) == ""
        assert calculate_fall_damage_dice(-5) == ""

    def test_three_meters(self):
        """3m（10 呎）= 1d6。"""
        assert calculate_fall_damage_dice(3) == "1d6"

    def test_six_meters(self):
        """6m（20 呎）= 2d6。"""
        assert calculate_fall_damage_dice(6) == "2d6"

    def test_ten_meters(self):
        """10m → ceil(10/3)=4d6（非整除向上取整）。"""
        assert calculate_fall_damage_dice(10) == "4d6"

    def test_sixty_meters_cap(self):
        """60m+ 上限 20d6。"""
        assert calculate_fall_damage_dice(60) == "20d6"
        assert calculate_fall_damage_dice(100) == "20d6"


# ---------------------------------------------------------------------------
# 跳躍/墜落測試
# ---------------------------------------------------------------------------


def _make_jump_map(fall_damage_on_fail: bool = True) -> ExplorationMap:
    """建立含跳躍邊的測試地圖（room_a → room_b，DC12，-6m）。"""
    return ExplorationMap(
        id="jump_map",
        name="跳躍測試地圖",
        scale="dungeon",
        entry_node_id="room_a",
        nodes=[
            ExplorationNode(id="room_a", name="起跳點", node_type="room", elevation_m=6),
            ExplorationNode(id="room_b", name="落地點", node_type="room", elevation_m=0),
        ],
        edges=[
            ExplorationEdge(
                id="jump_edge",
                from_node_id="room_a",
                to_node_id="room_b",
                name="斷橋跳躍",
                requires_jump=True,
                jump_dc=12,
                fall_damage_on_fail=fall_damage_on_fail,
                elevation_change_m=-6,
                distance_minutes=1,
            ),
        ],
    )


def _make_jump_state() -> ExplorationState:
    return ExplorationState(
        current_map_id="jump_map",
        current_node_id="room_a",
        discovered_nodes={"room_a"},
    )


class TestAttemptJump:
    """attempt_jump() 成功/失敗/墜落分支。"""

    def test_jump_success(self):
        """check_total >= jump_dc → 成功，移動到目的地。"""
        exp_map = _make_jump_map()
        state = _make_jump_state()
        char = _make_characters()[0]
        rng = random.Random(42)

        result = attempt_jump(state, exp_map, "jump_edge", char, 15, rng=rng)

        assert result.success is True
        assert result.node is not None
        assert result.node.id == "room_b"
        assert state.current_node_id == "room_b"
        assert result.fall_damage_total == 0

    def test_jump_fail_with_fall(self):
        """check_total < jump_dc + fall_damage_on_fail → 仍到達，有墜落傷害。"""
        exp_map = _make_jump_map(fall_damage_on_fail=True)
        state = _make_jump_state()
        char = _make_characters()[0]
        rng = random.Random(42)

        result = attempt_jump(state, exp_map, "jump_edge", char, 8, rng=rng)

        assert result.success is False
        assert result.node is not None
        assert result.node.id == "room_b"  # 仍到達
        assert state.current_node_id == "room_b"  # state 已更新
        assert result.fall_damage_total > 0
        assert result.fall_damage_dice == "2d6"  # ceil(6/3)=2d6

    def test_jump_fail_no_fall(self):
        """check_total < jump_dc + fall_damage_on_fail=False → 原地不動，無傷害。"""
        exp_map = _make_jump_map(fall_damage_on_fail=False)
        state = _make_jump_state()
        char = _make_characters()[0]

        result = attempt_jump(state, exp_map, "jump_edge", char, 8)

        assert result.success is False
        assert result.node is None
        assert state.current_node_id == "room_a"  # 沒動
        assert result.fall_damage_total == 0


class TestMoveBlockedByJump:
    """move_to_node() 遇到 requires_jump 邊應回傳失敗。"""

    def test_move_blocked_by_jump(self):
        exp_map = _make_jump_map()
        state = _make_jump_state()

        result = move_to_node(state, exp_map, "jump_edge")

        assert result.success is False
        assert "跳躍" in result.message
        assert state.current_node_id == "room_a"  # 沒移動


# ---------------------------------------------------------------------------
# 崖岸遺跡地圖載入測試
# ---------------------------------------------------------------------------


class TestCliffRuinsMap:
    """cliff_ruins.json 地圖完整性。"""

    def test_load_cliff_ruins(self):
        """地圖可正常載入。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        assert exp_map.id == "cliff_ruins"

    def test_node_count(self):
        """應有 10 個節點。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        assert len(exp_map.nodes) == 10

    def test_edge_count(self):
        """應有 11 條路徑。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        assert len(exp_map.edges) == 11

    def test_has_jump_edges(self):
        """至少有 3 條跳躍路徑。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        jump_edges = [e for e in exp_map.edges if e.requires_jump]
        assert len(jump_edges) >= 3

    def test_has_hidden_edge(self):
        """暗門 (hidden_dc=14) 存在。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        hidden = [e for e in exp_map.edges if e.hidden_dc > 0]
        assert len(hidden) >= 1

    def test_elevation_variety(self):
        """節點海拔至少三種不同值。"""
        exp_map = load_exploration_map(name="cliff_ruins")
        elevations = {n.elevation_m for n in exp_map.nodes}
        assert len(elevations) >= 3


# ---------------------------------------------------------------------------
# MapRegistry + 轉場函式測試
# ---------------------------------------------------------------------------


def _make_sub_map() -> ExplorationMap:
    """建立子地圖。"""
    return ExplorationMap(
        id="sub_dungeon",
        name="子地城",
        scale="dungeon",
        entry_node_id="sub_room_a",
        nodes=[
            ExplorationNode(id="sub_room_a", name="子房間 A", node_type="room"),
        ],
        edges=[],
    )


def _make_parent_map_with_sub() -> ExplorationMap:
    """建立含子地圖引用的父地圖。"""
    return ExplorationMap(
        id="parent_map",
        name="父地圖",
        scale="world",
        entry_node_id="town",
        nodes=[
            ExplorationNode(id="town", name="城鎮", node_type="town"),
            ExplorationNode(id="cave", name="洞穴入口", node_type="poi", sub_map="sub_dungeon"),
        ],
        edges=[
            ExplorationEdge(
                id="path_to_cave",
                from_node_id="town",
                to_node_id="cave",
                name="前往洞穴",
                distance_days=1,
            ),
        ],
    )


class TestMapRegistry:
    """MapRegistry 基本操作。"""

    def test_register_and_get(self):
        """註冊後可取得地圖。"""
        registry = MapRegistry()
        exp_map = _make_map()
        registry.register(exp_map)

        assert "test_map" in registry
        assert registry.get("test_map") is exp_map

    def test_get_missing(self):
        """取不存在的地圖回傳 None。"""
        registry = MapRegistry()
        assert registry.get("nonexistent") is None
        assert "nonexistent" not in registry


class TestCheckSubMapTransition:
    """check_sub_map_transition() 測試。"""

    def test_enters_sub_map(self):
        """在有 sub_map 的節點自動進入子地圖。"""
        parent = _make_parent_map_with_sub()
        sub = _make_sub_map()
        registry = MapRegistry()
        registry.register(parent)
        registry.register(sub)

        state = ExplorationState(
            current_map_id="parent_map",
            current_node_id="cave",
            discovered_nodes={"town", "cave"},
        )

        result = check_sub_map_transition(state, registry, parent)

        assert result is sub
        assert state.current_map_id == "sub_dungeon"
        assert state.current_node_id == "sub_room_a"
        assert len(state.map_stack) == 1
        assert state.map_stack[0].map_id == "parent_map"
        assert state.map_stack[0].node_id == "cave"

    def test_no_sub_map(self):
        """節點沒有 sub_map 時回傳 None。"""
        parent = _make_parent_map_with_sub()
        registry = MapRegistry()
        registry.register(parent)

        state = ExplorationState(
            current_map_id="parent_map",
            current_node_id="town",
            discovered_nodes={"town"},
        )

        result = check_sub_map_transition(state, registry, parent)

        assert result is None
        assert state.current_map_id == "parent_map"
        assert state.current_node_id == "town"


class TestResolveParentMap:
    """resolve_parent_map() 測試。"""

    def test_resolve_parent(self):
        """從子地圖返回父地圖。"""
        parent = _make_parent_map_with_sub()
        sub = _make_sub_map()
        registry = MapRegistry()
        registry.register(parent)
        registry.register(sub)

        state = ExplorationState(
            current_map_id="sub_dungeon",
            current_node_id="sub_room_a",
            map_stack=[MapStackEntry(map_id="parent_map", node_id="cave")],
        )

        result = resolve_parent_map(state, registry)

        assert result is parent
        assert state.current_map_id == "parent_map"
        assert state.current_node_id == "cave"
        assert len(state.map_stack) == 0

    def test_at_top_level(self):
        """已在最頂層時回傳 None。"""
        registry = MapRegistry()
        state = ExplorationState(
            current_map_id="parent_map",
            current_node_id="town",
        )

        result = resolve_parent_map(state, registry)
        assert result is None


class TestRegisterMapTree:
    """register_map_tree() 遞迴註冊測試。"""

    def test_recursive_registration(self):
        """遞迴掃描 sub_map 引用並載入。"""
        parent = _make_parent_map_with_sub()
        sub = _make_sub_map()
        registry = MapRegistry()

        # 注入假 loader：只認 sub_dungeon
        def fake_loader(*, name: str) -> ExplorationMap:
            if name == "sub_dungeon":
                return sub
            msg = f"找不到地圖：{name}"
            raise FileNotFoundError(msg)

        register_map_tree(registry, parent, loader=fake_loader)

        assert "parent_map" in registry
        assert "sub_dungeon" in registry
        assert registry.get("parent_map") is parent
        assert registry.get("sub_dungeon") is sub
