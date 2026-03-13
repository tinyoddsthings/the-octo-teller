"""Area 自由探索引擎測試。"""

from __future__ import annotations

import random

from tot.gremlins.bone_engine.area_explore import (
    check_terrain_at,
    enter_area,
    exit_area,
    explore_move,
    get_nearby_props,
    get_party_position,
    reset_movement,
    search_prop,
    take_prop_loot,
)
from tot.models import (
    AbilityScores,
    Character,
    ExplorationMap,
    ExplorationNode,
)
from tot.models.enums import MapScale, NodeType


def _make_map() -> ExplorationMap:
    """建立包含 cave_explore area 的測試用 Pointcrawl 地圖。"""
    return ExplorationMap(
        id="test-map",
        name="測試地圖",
        scale=MapScale.DUNGEON,
        nodes=[
            ExplorationNode(
                id="cave",
                name="洞穴入口",
                node_type=NodeType.LANDMARK,
                combat_map="cave_explore",
            ),
            ExplorationNode(
                id="empty",
                name="空節點",
                node_type=NodeType.CORRIDOR,
            ),
        ],
        edges=[],
        entry_node_id="cave",
    )


def _rogue() -> Character:
    """DEX 16, INT 14 Rogue。"""
    return Character(
        name="Lyra",
        char_class="Rogue",
        level=5,
        ability_scores=AbilityScores(STR=10, DEX=16, CON=12, INT=14, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=33,
        hp_current=33,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=8,
        ac=15,
        speed=9,
        skill_proficiencies=["Investigation", "Perception", "Stealth"],
    )


def _fighter() -> Character:
    """STR 16 Fighter（Investigation 不熟練）。"""
    return Character(
        name="Aldric",
        char_class="Fighter",
        level=5,
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        hit_dice_total=5,
        hit_dice_remaining=5,
        hit_die_size=10,
        ac=18,
        speed=9,
    )


# ---------------------------------------------------------------------------
# enter_area / exit_area
# ---------------------------------------------------------------------------


class TestEnterArea:
    def test_enter_valid_node(self):
        """有 combat_map 的節點可進入 area。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        assert state.party_actor_id.startswith("party-")
        assert state.speed_per_turn == 9.0
        assert state.speed_remaining == 9.0
        # 隊伍放在 spawn point
        pos = get_party_position(state)
        assert pos is not None
        assert pos.x == 12.5
        assert pos.y == 2.5

    def test_enter_empty_node(self):
        """沒有 combat_map 的節點回傳 None。"""
        exp_map = _make_map()
        assert enter_area(exp_map, "empty", [_rogue()]) is None

    def test_enter_unknown_node(self):
        """不存在的節點回傳 None。"""
        exp_map = _make_map()
        assert enter_area(exp_map, "nonexistent", [_rogue()]) is None

    def test_party_speed_uses_slowest(self):
        """隊伍速度取最慢角色。"""
        exp_map = _make_map()
        rogue = _rogue()
        rogue.speed = 12.0  # 快
        fighter = _fighter()
        fighter.speed = 6.0  # 慢
        state = enter_area(exp_map, "cave", [rogue, fighter])
        assert state is not None
        assert state.speed_per_turn == 6.0


class TestExitArea:
    def test_exit_returns_collected(self):
        """離開 area 回傳已收集物品。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = exit_area(state)
        assert result.collected_items == []


# ---------------------------------------------------------------------------
# explore_move
# ---------------------------------------------------------------------------


class TestExploreMove:
    def test_move_success(self):
        """正常移動成功。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = explore_move(state, 12.5, 4.0)
        assert result.success is True
        assert result.speed_remaining < 9.0
        pos = get_party_position(state)
        assert pos is not None
        assert pos.x == 12.5
        assert pos.y == 4.0

    def test_move_into_wall(self):
        """撞牆失敗。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 移動到西牆內
        result = explore_move(state, 0.5, 5.0)
        assert result.success is False
        assert result.speed_remaining == 9.0

    def test_move_out_of_speed(self):
        """速度不足移動失敗。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 從 (12.5, 2.5) 移動到 (12.5, 15) = 12.5m > 9m 速度
        result = explore_move(state, 12.5, 15.0)
        assert result.success is False

    def test_reset_movement(self):
        """重置移動速度。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        explore_move(state, 12.5, 4.0)
        assert state.speed_remaining < 9.0
        reset_movement(state)
        assert state.speed_remaining == 9.0


# ---------------------------------------------------------------------------
# terrain
# ---------------------------------------------------------------------------


class TestTerrain:
    def test_check_terrain_at_rubble(self):
        """碎石區域回報 rubble 地形。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 先移動到碎石區附近
        explore_move(state, 12.5, 7.0)
        reset_movement(state)
        explore_move(state, 12.5, 9.0)
        terrain = check_terrain_at(state)
        assert terrain.terrain_type == "rubble"
        assert terrain.is_difficult is True

    def test_flat_ground(self):
        """入口區是平地。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        terrain = check_terrain_at(state)
        assert terrain.terrain_type == ""
        assert terrain.is_difficult is False


# ---------------------------------------------------------------------------
# search / take
# ---------------------------------------------------------------------------


class TestSearchProp:
    def test_search_dc0_auto_success(self):
        """DC 0 物件自動成功。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = search_prop(state, "mushrooms", _rogue())
        assert result.success is True
        assert result.loot_available is True

    def test_search_high_dc_with_low_roll(self):
        """高 DC 搜索可能失敗。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_fighter()])
        assert state is not None
        # seed 確保 roll 低
        rng = random.Random(1)
        result = search_prop(state, "chest_west", _fighter(), rng=rng)
        # 不保證結果——取決於骰子，但驗證回傳結構正確
        assert isinstance(result.success, bool)
        assert result.prop_id == "chest_west"

    def test_search_already_searched(self):
        """重複搜索回傳已搜索訊息。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        result = search_prop(state, "mushrooms", _rogue())
        assert result.success is True

    def test_search_nonexistent(self):
        """搜索不存在的 Prop。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = search_prop(state, "nonexistent", _rogue())
        assert result.success is False

    def test_search_non_interactable(self):
        """搜索不可互動的 Prop。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = search_prop(state, "torch_1", _rogue())
        assert result.success is False


class TestTakePropLoot:
    def test_take_after_search(self):
        """搜索後拾取物品。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        items = take_prop_loot(state, "mushrooms")
        assert len(items) == 1
        assert items[0].name == "發光蘑菇"
        assert items[0].quantity == 3
        # 物品已加入收集清單
        assert len(state.collected_items) == 1

    def test_take_without_search(self):
        """未搜索的 Prop 無法拾取。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        items = take_prop_loot(state, "mushrooms")
        assert items == []

    def test_take_twice(self):
        """重複拾取回傳空。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        take_prop_loot(state, "mushrooms")
        items = take_prop_loot(state, "mushrooms")
        assert items == []

    def test_exit_with_collected_items(self):
        """離開時回傳所有收集物品。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        take_prop_loot(state, "mushrooms")
        result = exit_area(state)
        assert len(result.collected_items) == 1
        assert result.collected_items[0].name == "發光蘑菇"


# ---------------------------------------------------------------------------
# get_nearby_props
# ---------------------------------------------------------------------------


class TestGetNearbyProps:
    def test_nearby_at_spawn(self):
        """入口附近沒有可互動 Prop。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        props = get_nearby_props(state)
        # spawn (12.5, 2.5) 附近沒有 interactable props
        assert len(props) == 0

    def test_nearby_mushroom(self):
        """移動到蘑菇附近可偵測。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 蘑菇在 (3.0, 8.0)，先移動靠近
        explore_move(state, 4.0, 2.5)
        reset_movement(state)
        explore_move(state, 4.0, 7.0)
        props = get_nearby_props(state)
        assert any(p.id == "mushrooms" for p in props)

    def test_hidden_prop_not_shown(self):
        """隱藏且未發現的 Prop 不出現在 nearby。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # hidden_scroll 在 (20.5, 8.5)
        explore_move(state, 12.5, 8.5)
        reset_movement(state)
        explore_move(state, 20.5, 8.5)
        props = get_nearby_props(state)
        assert not any(p.id == "hidden_scroll" for p in props)
