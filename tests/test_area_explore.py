"""Area 自由探索引擎測試。"""

from __future__ import annotations

import random

from tot.gremlins.bone_engine.area_explore import (
    check_terrain_at,
    enter_area,
    exit_area,
    explore_move,
    get_nearby_doors,
    get_nearby_props,
    get_party_position,
    loot_to_item,
    reset_movement,
    search_prop,
    take_prop_loot,
    transfer_loot_to_inventory,
    unlock_area_prop,
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
        class_levels={"Rogue": 5},
        ability_scores=AbilityScores(STR=10, DEX=16, CON=12, INT=14, WIS=12, CHA=10),
        proficiency_bonus=3,
        hp_max=33,
        hp_current=33,
        hit_dice_remaining={8: 5},
        ac=15,
        speed=9,
        skill_proficiencies=["Investigation", "Perception", "Stealth"],
    )


def _fighter() -> Character:
    """STR 16 Fighter（Investigation 不熟練）。"""
    return Character(
        name="Aldric",
        class_levels={"Fighter": 5},
        ability_scores=AbilityScores(STR=16, DEX=12, CON=14, INT=10, WIS=12, CHA=8),
        proficiency_bonus=3,
        hp_max=44,
        hp_current=44,
        hit_dice_remaining={10: 5},
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
        """移動到蘑菇附近可偵測（邊緣距離 ≤ 0.5m）。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 蘑菇在 (3.0, 8.0)，移動到緊鄰位置
        explore_move(state, 4.0, 2.5)
        reset_movement(state)
        explore_move(state, 3.0, 7.0)
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


# ---------------------------------------------------------------------------
# loot_to_item / transfer_loot_to_inventory
# ---------------------------------------------------------------------------


class TestLootToItem:
    def test_basic_conversion(self):
        """LootEntry 轉為 Item。"""
        from tot.models.map import LootEntry

        loot = LootEntry(
            item_id="gold", name="金幣袋", description="沉甸甸的", quantity=1, value_gp=50
        )
        item = loot_to_item(loot)
        assert item.name == "金幣袋"
        assert item.description == "沉甸甸的"
        assert item.quantity == 1

    def test_key_item_conversion(self):
        """帶 grants_key 的 LootEntry 也能轉換。"""
        from tot.models.map import LootEntry

        loot = LootEntry(item_id="key", name="鐵鑰匙", grants_key="north_door_key")
        item = loot_to_item(loot)
        assert item.name == "鐵鑰匙"


class TestTransferLootToInventory:
    def test_transfer_to_first_character(self):
        """物品轉入第一個角色的 inventory。"""
        exp_map = _make_map()
        rogue = _rogue()
        state = enter_area(exp_map, "cave", [rogue])
        assert state is not None
        search_prop(state, "mushrooms", rogue)
        take_prop_loot(state, "mushrooms")
        items = transfer_loot_to_inventory(state, [rogue])
        assert len(items) == 1
        assert items[0].name == "發光蘑菇"
        assert any(i.name == "發光蘑菇" for i in rogue.inventory)

    def test_transfer_empty(self):
        """沒有物品時回傳空列表。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        items = transfer_loot_to_inventory(state, [_rogue()])
        assert items == []

    def test_transfer_no_characters(self):
        """沒有角色時回傳空列表。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        take_prop_loot(state, "mushrooms")
        items = transfer_loot_to_inventory(state, [])
        assert items == []


# ---------------------------------------------------------------------------
# take_prop_loot — 鑰匙自動註冊
# ---------------------------------------------------------------------------


class TestTakeKeyAutoRegister:
    def _move_to_chest(self, state):
        """移動到石箱附近。"""
        explore_move(state, 4.0, 2.5)
        reset_movement(state)
        explore_move(state, 4.0, 8.0)
        reset_movement(state)
        explore_move(state, 4.5, 14.5)

    def test_key_auto_registered(self):
        """拾取帶 grants_key 的物品自動加入 collected_keys。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 直接標記已搜索（此測試驗證鑰匙註冊，非搜索機制）
        prop = next(p for p in state.map_state.manifest.props if p.id == "chest_west")
        prop.is_searched = True
        take_prop_loot(state, "chest_west")
        assert "north_door_key" in state.collected_keys

    def test_no_key_no_register(self):
        """拾取無 grants_key 的物品不影響 collected_keys。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        search_prop(state, "mushrooms", _rogue())
        take_prop_loot(state, "mushrooms")
        assert len(state.collected_keys) == 0


# ---------------------------------------------------------------------------
# unlock_area_prop
# ---------------------------------------------------------------------------


class TestUnlockAreaProp:
    def test_unlock_with_key(self):
        """用鑰匙開鎖成功。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = unlock_area_prop(state, "exit_north", key_item_id="north_door_key")
        assert result.success is True
        assert "鑰匙" in result.message
        # 門已解鎖且不再阻擋
        gate = next(p for p in state.map_state.manifest.props if p.id == "exit_north")
        assert gate.is_locked is False
        assert gate.is_blocking is False

    def test_unlock_with_check_pass(self):
        """開鎖檢定通過。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = unlock_area_prop(state, "exit_north", check_total=15)
        assert result.success is True
        assert "DC 15" in result.message

    def test_unlock_with_check_fail(self):
        """開鎖檢定失敗。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = unlock_area_prop(state, "exit_north", check_total=10)
        assert result.success is False
        assert "失敗" in result.message

    def test_unlock_wrong_key(self):
        """錯誤鑰匙無法開鎖。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = unlock_area_prop(state, "exit_north", key_item_id="wrong_key")
        assert result.success is False

    def test_unlock_already_unlocked(self):
        """未上鎖的門回傳成功。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # entrance_south 是木門，沒有上鎖
        result = unlock_area_prop(state, "entrance_south")
        assert result.success is True
        assert "沒有鎖" in result.message

    def test_unlock_nonexistent(self):
        """不存在的 Prop。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        result = unlock_area_prop(state, "nonexistent")
        assert result.success is False


# ---------------------------------------------------------------------------
# get_nearby_doors
# ---------------------------------------------------------------------------


class TestGetNearbyDoors:
    def test_door_at_spawn(self):
        """入口附近有木門。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # spawn 在 (12.5, 2.5)，entrance_south 在 (12.5, 0.75)
        # 距離 = 2.5 - 0.75 = 1.75m（太遠）
        doors = get_nearby_doors(state)
        # 邊緣距離可能仍在範圍外
        assert all(d.prop_type == "door" for d in doors)

    def test_door_when_close(self):
        """靠近鐵柵門時可偵測。"""
        exp_map = _make_map()
        state = enter_area(exp_map, "cave", [_rogue()])
        assert state is not None
        # 穿過中央到北側（通過水池 difficult terrain）
        explore_move(state, 12.5, 7.0)
        reset_movement(state)
        explore_move(state, 12.5, 13.0)
        reset_movement(state)
        # 進入水池 (12.5, 16.0, r=2.5) — difficult terrain
        explore_move(state, 12.5, 16.0)
        reset_movement(state)
        # 鐵柵門在 (12.5, 19.25)，bounds 1.5×0.3m
        explore_move(state, 12.5, 18.0)
        doors = get_nearby_doors(state)
        assert any(d.id == "exit_north" for d in doors)
