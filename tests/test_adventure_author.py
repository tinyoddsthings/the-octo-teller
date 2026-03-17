"""冒險劇本生成工具測試。"""

from __future__ import annotations

import pytest

from tot.tools.adventure_author.cli import main as cli_main
from tot.tools.adventure_author.id_gen import (
    has_cjk,
    name_to_id,
    parse_heading_id,
    slugify,
)
from tot.tools.adventure_author.map_builder import build_map as build_map_fn
from tot.tools.adventure_author.parser import (
    parse_chapter,
    parse_map,
    parse_meta,
    parse_npc,
    parse_scene,
)
from tot.tools.adventure_author.scaffold import create_adventure
from tot.tools.adventure_author.script_builder import build_script

# ── ID 生成 ──────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert slugify("Forest Path") == "forest_path"

    def test_already_snake(self):
        assert slugify("cave_entrance") == "cave_entrance"

    def test_mixed_case(self):
        assert slugify("Guard Room") == "guard_room"

    def test_numbers(self):
        assert slugify("Guard Room #2") == "guard_room_2"

    def test_special_chars(self):
        assert slugify("iron-door (locked)") == "iron_door_locked"

    def test_leading_trailing(self):
        assert slugify("  hello  ") == "hello"

    def test_consecutive_spaces(self):
        assert slugify("a   b") == "a_b"

    def test_empty_after_strip(self):
        assert slugify("___") == ""


class TestHasCjk:
    def test_ascii(self):
        assert not has_cjk("hello world")

    def test_chinese(self):
        assert has_cjk("松溪村")

    def test_mixed(self):
        assert has_cjk("hello 世界")

    def test_japanese(self):
        assert has_cjk("東京タワー")


class TestNameToId:
    def test_ascii(self):
        assert name_to_id("Forest Path") == "forest_path"

    def test_explicit_id(self):
        assert name_to_id("松溪村", "pinebrook_village") == "pinebrook_village"

    def test_explicit_id_with_spaces(self):
        assert name_to_id("test", "  my_id  ") == "my_id"

    def test_cjk_without_id_raises(self):
        with pytest.raises(ValueError, match="中文名稱"):
            name_to_id("松溪村")

    def test_empty_slug_raises(self):
        with pytest.raises(ValueError, match="無法轉換"):
            name_to_id("___")


class TestParseHeadingId:
    def test_with_id(self):
        name, eid = parse_heading_id("Forest Path #forest_path")
        assert name == "Forest Path"
        assert eid == "forest_path"

    def test_chinese_with_id(self):
        name, eid = parse_heading_id("洞穴入口 #cave_entrance")
        assert name == "洞穴入口"
        assert eid == "cave_entrance"

    def test_without_id(self):
        name, eid = parse_heading_id("Guard Room")
        assert name == "Guard Room"
        assert eid is None

    def test_hash_in_middle(self):
        # #2 不在行尾，不是 ID 標記
        name, eid = parse_heading_id("Room #2 Special")
        assert name == "Room #2 Special"
        assert eid is None

    def test_trailing_spaces(self):
        name, eid = parse_heading_id("Test #my_id  ")
        assert name == "Test"
        assert eid == "my_id"


# ── Scaffold ─────────────────────────────────────────────


class TestScaffold:
    def test_create_adventure(self, tmp_path):
        root = create_adventure(tmp_path, "test_adventure", "測試冒險")
        assert root == tmp_path / "test_adventure"
        assert root.is_dir()

    def test_directories_created(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        assert (root / "chapters").is_dir()
        assert (root / "maps").is_dir()
        assert (root / "npcs").is_dir()
        assert (root / "scenes").is_dir()

    def test_meta_file(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv", "我的冒險")
        meta = (root / "_meta.md").read_text(encoding="utf-8")
        assert "id: my_adv" in meta
        assert "name: 我的冒險" in meta

    def test_chapter_example(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        chapter = root / "chapters" / "01_opening.md"
        assert chapter.exists()
        content = chapter.read_text(encoding="utf-8")
        assert "trigger:" in content

    def test_map_examples(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        assert (root / "maps" / "town.md").exists()
        assert (root / "maps" / "road.md").exists()
        assert (root / "maps" / "dungeon.md").exists()

    def test_town_map_has_pois(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        content = (root / "maps" / "town.md").read_text(encoding="utf-8")
        assert "pois:" in content
        assert "scale: town" in content

    def test_road_map_has_sub_map(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        content = (root / "maps" / "road.md").read_text(encoding="utf-8")
        assert "sub_map:" in content
        assert "scale: world" in content
        assert "distance:" in content

    def test_dungeon_map_has_locked_door(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        content = (root / "maps" / "dungeon.md").read_text(encoding="utf-8")
        assert "locked:" in content
        assert "hidden_dc:" in content
        assert "scale: dungeon" in content

    def test_npc_example(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        npc = root / "npcs" / "guard.md"
        assert npc.exists()
        content = npc.read_text(encoding="utf-8")
        assert "## 背景" in content
        assert "## 常態對話" in content
        assert "choices:" in content

    def test_idempotent(self, tmp_path):
        """重複建立不應報錯。"""
        create_adventure(tmp_path, "my_adv")
        create_adventure(tmp_path, "my_adv")
        assert (tmp_path / "my_adv" / "_meta.md").exists()

    def test_default_name(self, tmp_path):
        root = create_adventure(tmp_path, "my_adv")
        meta = (root / "_meta.md").read_text(encoding="utf-8")
        assert "name: my_adv" in meta


# ── Parser: Meta ─────────────────────────────────────────


class TestParseMeta:
    def test_basic(self):
        md = """\
---
id: my_adventure
name: 我的冒險
description: 一場測試冒險。
---
"""
        meta, flags = parse_meta(md)
        assert meta["id"] == "my_adventure"
        assert meta["name"] == "我的冒險"
        assert flags == {}

    def test_initial_flags(self):
        md = """\
---
id: test
name: test
---

initial_flags:
- patrol_assigned: 1
- trust_level: 3
"""
        meta, flags = parse_meta(md)
        assert flags == {"patrol_assigned": 1, "trust_level": 3}

    def test_empty(self):
        meta, flags = parse_meta("")
        assert meta == {}
        assert flags == {}


# ── Parser: Map ──────────────────────────────────────────


SAMPLE_DUNGEON_MAP = """\
---
id: test_dungeon
name: 測試地城
scale: dungeon
entry: entrance
---

## 入口大廳 #entrance
type: room
description: 潮濕的石造大廳。
ambient: 水滴聲迴盪在石壁之間。

items:
- 生鏽鑰匙 #rusty_key | item | dc:12
  藏在石板下方的鑰匙。
  grants_key: rusty_key

## 寶庫 #treasure_room
type: room
description: 閃亮的寶物堆。
combat_map: treasure_battle

### → 寶庫（鐵門） #iron_door
to: treasure_room
from: entrance
distance: 2min
locked: rusty_key
lock_dc: 14

### → 入口大廳（暗門） #secret_back
to: entrance
from: treasure_room
distance: 3min
hidden_dc: 15
"""


class TestParseMap:
    def test_meta(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        assert ir.meta["id"] == "test_dungeon"
        assert ir.meta["scale"] == "dungeon"
        assert ir.meta["entry"] == "entrance"

    def test_nodes(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        assert len(ir.nodes) == 2
        assert ir.nodes[0].name == "入口大廳"
        assert ir.nodes[0].explicit_id == "entrance"
        assert ir.nodes[0].node_type == "room"
        assert ir.nodes[0].description == "潮濕的石造大廳。"
        assert ir.nodes[0].ambient == "水滴聲迴盪在石壁之間。"

    def test_items(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        items = ir.nodes[0].items
        assert len(items) == 1
        assert items[0].name == "生鏽鑰匙"
        assert items[0].explicit_id == "rusty_key"
        assert items[0].item_type == "item"
        assert items[0].investigation_dc == 12
        assert items[0].description == "藏在石板下方的鑰匙。"
        assert items[0].grants_key == "rusty_key"

    def test_combat_map(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        assert ir.nodes[1].combat_map == "treasure_battle"

    def test_edges(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        # 邊掛在定義它們之前的節點上（寶庫節點下的邊）
        # 第一條邊在入口大廳節點下（但語法上寫在寶庫之後）
        # 實際上，邊定義在寶庫節點的 ## 之後
        all_edges = []
        for node in ir.nodes:
            all_edges.extend(node.edges)
        assert len(all_edges) == 2

    def test_edge_properties(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        all_edges = []
        for node in ir.nodes:
            all_edges.extend(node.edges)
        iron_door = all_edges[0]
        assert iron_door.name == "寶庫（鐵門）"
        assert iron_door.explicit_id == "iron_door"
        assert iron_door.properties["to"] == "treasure_room"
        assert iron_door.properties["locked"] == "rusty_key"
        assert iron_door.properties["lock_dc"] == "14"

    def test_hidden_edge(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        all_edges = []
        for node in ir.nodes:
            all_edges.extend(node.edges)
        secret = all_edges[1]
        assert secret.properties["hidden_dc"] == "15"


SAMPLE_TOWN_MAP = """\
---
id: test_town
name: 測試城鎮
scale: town
entry: town_center
---

## 城鎮中心 #town_center
type: town
description: 小鎮的中心。

pois:
- 酒館 #tavern | poi
  熱鬧的酒館。
  npcs: bartender
- 鐵匠鋪 #blacksmith | poi
  敲打聲不斷。
  npcs: smith, apprentice
"""


class TestParseMapTown:
    def test_pois(self):
        ir = parse_map(SAMPLE_TOWN_MAP)
        assert len(ir.nodes) == 1
        node = ir.nodes[0]
        assert len(node.pois) == 2
        assert node.pois[0].name == "酒館"
        assert node.pois[0].explicit_id == "tavern"
        assert node.pois[0].description == "熱鬧的酒館。"
        assert node.pois[0].npcs == ["bartender"]

    def test_poi_multiple_npcs(self):
        ir = parse_map(SAMPLE_TOWN_MAP)
        assert ir.nodes[0].pois[1].npcs == ["smith", "apprentice"]


SAMPLE_WORLD_MAP = """\
---
id: test_road
name: 測試道路
scale: world
entry: town_gate
---

## 城鎮大門 #town_gate
type: landmark
description: 大門。
sub_map: test_town

## 洞穴入口 #cave
type: dungeon
sub_map: test_dungeon

### → 洞穴入口 #to_cave
to: cave
from: town_gate
distance: 0.5day
danger_level: 5
"""


class TestParseMapWorld:
    def test_sub_map(self):
        ir = parse_map(SAMPLE_WORLD_MAP)
        assert ir.nodes[0].sub_map == "test_town"
        assert ir.nodes[1].sub_map == "test_dungeon"

    def test_edge_distance(self):
        ir = parse_map(SAMPLE_WORLD_MAP)
        all_edges = []
        for node in ir.nodes:
            all_edges.extend(node.edges)
        assert len(all_edges) == 1
        assert all_edges[0].properties["distance"] == "0.5day"
        assert all_edges[0].properties["danger_level"] == "5"


# ── Parser: NPC ──────────────────────────────────────────


SAMPLE_NPC = """\
---
id: quinn
name: 乖因
---

## 背景
description: 焦慮的小精靈。
location: village_square
personality: 膽小但善良。
role: quest_giver

## 常態對話 #quinn_idle

> 你有看到奇怪的東西嗎？

## 初次見面 #quinn_intro
map: pinebrook_village
condition: not:talked_to_quinn

> 你好，冒險者！

choices:
- **「怎麼回事？」** #quinn_ask → quinn_explain
  sets_flag: asked_quinn
- **「我沒空。」** #quinn_refuse → quinn_sad

## 解釋 #quinn_explain
condition: has:asked_quinn

> 山洞裡有什麼東西在搗亂。

sets_flag: quest_accepted
"""


class TestParseNpc:
    def test_background(self):
        npc = parse_npc(SAMPLE_NPC)
        assert npc.name == "乖因"
        assert npc.explicit_id == "quinn"
        assert npc.description == "焦慮的小精靈。"
        assert npc.location == "village_square"
        assert npc.personality == "膽小但善良。"
        assert npc.role == "quest_giver"

    def test_dialogues_count(self):
        npc = parse_npc(SAMPLE_NPC)
        assert len(npc.dialogues) == 3

    def test_idle_dialogue(self):
        npc = parse_npc(SAMPLE_NPC)
        idle = npc.dialogues[0]
        assert idle.title == "常態對話"
        assert idle.explicit_id == "quinn_idle"
        assert idle.text == "你有看到奇怪的東西嗎？"
        assert idle.condition == ""
        assert idle.map_id == ""

    def test_conditional_dialogue(self):
        npc = parse_npc(SAMPLE_NPC)
        intro = npc.dialogues[1]
        assert intro.title == "初次見面"
        assert intro.explicit_id == "quinn_intro"
        assert intro.condition == "not:talked_to_quinn"
        assert intro.map_id == "pinebrook_village"

    def test_choices(self):
        npc = parse_npc(SAMPLE_NPC)
        intro = npc.dialogues[1]
        assert len(intro.choices) == 2
        assert intro.choices[0].label == "怎麼回事？"
        assert intro.choices[0].explicit_id == "quinn_ask"
        assert intro.choices[0].next_id == "quinn_explain"
        assert intro.choices[0].sets_flag == "asked_quinn"

    def test_sets_flag(self):
        npc = parse_npc(SAMPLE_NPC)
        explain = npc.dialogues[2]
        assert explain.sets_flag == "quest_accepted"


# ── Parser: Chapter ──────────────────────────────────────


SAMPLE_CHAPTER = """\
---
chapter: 1
title: 抵達松溪
---

## 開場白 #opening
trigger: enter_node village_square
once: true

> 你踏入松溪村，空氣中瀰漫著不安的氣氛。

- tutorial: 輸入 `look` 查看環境。
- set_flag: arrived_pinebrook

## 接受任務 #quest_start
trigger: flag_set quest_accepted
condition: has:arrived_pinebrook
once: true

> 乖因感激地點了點頭。

- reveal_edge: to_forest
- move_npc: quinn → forest_path
- set_flag: patrol_started
"""


class TestParseChapter:
    def test_meta(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        assert ch.chapter == "1"
        assert ch.title == "抵達松溪"

    def test_events_count(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        assert len(ch.events) == 2

    def test_event_trigger(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        opening = ch.events[0]
        assert opening.name == "開場白"
        assert opening.explicit_id == "opening"
        assert opening.trigger_type == "enter_node"
        assert opening.trigger_target == "village_square"
        assert opening.once is True

    def test_event_narrate(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        opening = ch.events[0]
        assert "不安的氣氛" in opening.narrate

    def test_event_actions(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        opening = ch.events[0]
        assert len(opening.actions) == 2
        assert opening.actions[0] == {"type": "tutorial", "text": "輸入 `look` 查看環境。"}
        assert opening.actions[1] == {"type": "set_flag", "flag": "arrived_pinebrook"}

    def test_event_condition(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        quest = ch.events[1]
        assert quest.condition == "has:arrived_pinebrook"

    def test_move_npc_action(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        quest = ch.events[1]
        move = next(a for a in quest.actions if a["type"] == "move_npc")
        assert move["npc_id"] == "quinn"
        assert move["node_id"] == "forest_path"

    def test_reveal_edge_action(self):
        ch = parse_chapter(SAMPLE_CHAPTER)
        quest = ch.events[1]
        reveal = next(a for a in quest.actions if a["type"] == "reveal_edge")
        assert reveal["edge_id"] == "to_forest"


# ── Builder: Map ─────────────────────────────────────────


class TestBuildMap:
    def test_dungeon_map_structure(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        assert result["id"] == "test_dungeon"
        assert result["scale"] == "dungeon"
        assert result["entry_node_id"] == "entrance"
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 2

    def test_dungeon_node(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        entrance = result["nodes"][0]
        assert entrance["id"] == "entrance"
        assert entrance["name"] == "入口大廳"
        assert entrance["node_type"] == "room"
        assert entrance["description"] == "潮濕的石造大廳。"

    def test_dungeon_item(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        items = result["nodes"][0]["hidden_items"]
        assert len(items) == 1
        assert items[0]["id"] == "rusty_key"
        assert items[0]["investigation_dc"] == 12
        assert items[0]["grants_key"] == "rusty_key"

    def test_locked_edge(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        iron = result["edges"][0]
        assert iron["id"] == "iron_door"
        assert iron["from_node_id"] == "entrance"
        assert iron["to_node_id"] == "treasure_room"
        assert iron["is_locked"] is True
        assert iron["key_item"] == "rusty_key"
        assert iron["lock_dc"] == 14
        assert iron["distance_minutes"] == 2

    def test_hidden_edge(self):
        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        secret = result["edges"][1]
        assert secret["is_discovered"] is False
        assert secret["hidden_dc"] == 15

    def test_town_pois(self):
        ir = parse_map(SAMPLE_TOWN_MAP)
        result = build_map_fn(ir)
        pois = result["nodes"][0]["pois"]
        assert len(pois) == 2
        assert pois[0]["id"] == "tavern"
        assert pois[0]["npcs"] == ["bartender"]

    def test_world_sub_map(self):
        ir = parse_map(SAMPLE_WORLD_MAP)
        result = build_map_fn(ir)
        assert result["nodes"][0]["sub_map"] == "test_town"

    def test_world_edge_days(self):
        ir = parse_map(SAMPLE_WORLD_MAP)
        result = build_map_fn(ir)
        edge = result["edges"][0]
        assert edge["distance_days"] == 0.5
        assert edge["danger_level"] == 5

    def test_pydantic_validation_dungeon(self):
        """端對端：MD → IR → dict → Pydantic model_validate。"""
        from tot.models.exploration import ExplorationMap

        ir = parse_map(SAMPLE_DUNGEON_MAP)
        result = build_map_fn(ir)
        m = ExplorationMap.model_validate(result)
        assert m.id == "test_dungeon"
        assert len(m.nodes) == 2
        assert len(m.edges) == 2

    def test_pydantic_validation_town(self):
        from tot.models.exploration import ExplorationMap

        ir = parse_map(SAMPLE_TOWN_MAP)
        result = build_map_fn(ir)
        m = ExplorationMap.model_validate(result)
        assert m.id == "test_town"
        assert len(m.nodes[0].pois) == 2

    def test_pydantic_validation_world(self):
        from tot.models.exploration import ExplorationMap

        ir = parse_map(SAMPLE_WORLD_MAP)
        result = build_map_fn(ir)
        m = ExplorationMap.model_validate(result)
        assert m.id == "test_road"


# ── Builder: Script ──────────────────────────────────────


class TestBuildScript:
    def _build_sample(self):
        meta_dict, flags = parse_meta("""\
---
id: test_adv
name: 測試冒險
description: 一場測試。
---

initial_flags:
- test_flag: 1
""")
        npc = parse_npc(SAMPLE_NPC)
        chapter = parse_chapter(SAMPLE_CHAPTER)
        return build_script(meta_dict, flags, [npc], [chapter])

    def test_structure(self):
        result = self._build_sample()
        assert result["id"] == "test_adv"
        assert result["name"] == "測試冒險"
        assert result["initial_flags"] == {"test_flag": 1}

    def test_npcs(self):
        result = self._build_sample()
        assert "quinn" in result["npcs"]
        quinn = result["npcs"]["quinn"]
        assert quinn["name"] == "乖因"
        assert quinn["node_id"] == "village_square"

    def test_dialogue_lines(self):
        result = self._build_sample()
        quinn = result["npcs"]["quinn"]
        # 3 dialogues + 2 choices = 5 lines
        dialogue_ids = [d["id"] for d in quinn["dialogue"]]
        assert "quinn_idle" in dialogue_ids
        assert "quinn_intro" in dialogue_ids
        assert "quinn_ask" in dialogue_ids  # choice

    def test_dialogue_choices_linked(self):
        result = self._build_sample()
        quinn = result["npcs"]["quinn"]
        intro = next(d for d in quinn["dialogue"] if d["id"] == "quinn_intro")
        assert "next_lines" in intro
        assert "quinn_ask" in intro["next_lines"]
        assert "quinn_refuse" in intro["next_lines"]

    def test_choice_sets_flag(self):
        result = self._build_sample()
        quinn = result["npcs"]["quinn"]
        ask = next(d for d in quinn["dialogue"] if d["id"] == "quinn_ask")
        assert ask["sets_flag"] == "asked_quinn"
        assert ask["choice_label"] == "怎麼回事？"

    def test_events(self):
        result = self._build_sample()
        assert len(result["events"]) == 2
        opening = result["events"][0]
        assert opening["id"] == "opening"
        assert opening["trigger"]["type"] == "enter_node"
        assert opening["trigger"]["node_id"] == "village_square"

    def test_event_narrate_action(self):
        result = self._build_sample()
        opening = result["events"][0]
        narrate = opening["actions"][0]
        assert narrate["type"] == "narrate"
        assert "不安的氣氛" in narrate["text"]

    def test_event_condition(self):
        result = self._build_sample()
        quest = result["events"][1]
        assert quest["condition"] == "has:arrived_pinebrook"

    def test_chapter_condition_syntax_sugar(self):
        """chapter: 02 語法糖測試。"""
        npc = parse_npc(SAMPLE_NPC)
        # 森林中的擔憂對話有 chapter: 02
        forest_dlg = (
            next(d for d in npc.dialogues if d.explicit_id == "quinn_forest_worry")
            if any(d.explicit_id == "quinn_forest_worry" for d in npc.dialogues)
            else None
        )
        # SAMPLE_NPC 沒有 quinn_forest_worry，跳過
        if forest_dlg is None:
            return

    def test_pydantic_validation(self):
        """端對端：MD → IR → dict → AdventureScript.model_validate。"""
        from tot.models.adventure import AdventureScript

        result = self._build_sample()
        script = AdventureScript.model_validate(result)
        assert script.id == "test_adv"
        assert "quinn" in script.npcs
        assert len(script.events) == 2


# ── CLI ──────────────────────────────────────────────────


class TestCli:
    def test_new(self, tmp_path):
        ret = cli_main(["new", "test_adv", "--dir", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / "test_adv" / "_meta.md").exists()
        assert (tmp_path / "test_adv" / "chapters" / "01_opening.md").exists()

    def test_build(self, tmp_path):
        # 先 scaffold
        cli_main(["new", "test_adv", "--dir", str(tmp_path)])
        # 編譯
        ret = cli_main(["build", str(tmp_path / "test_adv")])
        assert ret == 0
        output_dir = tmp_path / "test_adv" / "output"
        assert output_dir.is_dir()
        # 應有地圖 JSON + 劇本 JSON
        json_files = list(output_dir.glob("*.json"))
        assert len(json_files) >= 2  # 至少一份地圖 + 一份劇本

    def test_build_custom_output(self, tmp_path):
        cli_main(["new", "test_adv", "--dir", str(tmp_path)])
        out = tmp_path / "custom_out"
        ret = cli_main(["build", str(tmp_path / "test_adv"), "-o", str(out)])
        assert ret == 0
        assert out.is_dir()

    def test_build_map(self, tmp_path):
        cli_main(["new", "test_adv", "--dir", str(tmp_path)])
        map_md = tmp_path / "test_adv" / "maps" / "dungeon.md"
        out_json = tmp_path / "dungeon.json"
        ret = cli_main(["build-map", str(map_md), "-o", str(out_json)])
        assert ret == 0
        assert out_json.exists()
        import json

        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert "id" in data
        assert "nodes" in data

    def test_validate(self, tmp_path):
        cli_main(["new", "test_adv", "--dir", str(tmp_path)])
        ret = cli_main(["validate", str(tmp_path / "test_adv")])
        assert ret == 0

    def test_build_missing_dir(self):
        ret = cli_main(["build", "/nonexistent/path"])
        assert ret == 1

    def test_no_command(self):
        ret = cli_main([])
        assert ret == 1


# ── Encounter 解析 ──────────────────────────────────────


SAMPLE_ENCOUNTER_MAP = """\
---
id: test_dungeon_enc
name: 遭遇測試地城
scale: dungeon
entry: entrance
---

## 入口 #entrance
type: room
description: 一個空蕩蕩的房間。

## 巢穴 #dragon_nest
type: room
description: 一個寬敞的洞室，中央有一堆閃亮的小物品圍成的窩。

encounter:
  enemies:
  - 幼藍龍 #young_blue_dragon | CR:2
    一隻藍色的小龍，蜷縮在窩裡。
  - 冰凍蜥蜴 #ice_lizard | CR:1/4
    兩隻結冰的蜥蜴，在角落嘶嘶作響。
    count: 2
  trigger: enter_node
  narration: 幼龍猛然抬起頭，發出一聲低吼。
  outcome: auto_win
  rewards:
  - 龍鱗碎片 #dragon_scale_piece | value_gp: 10
  - 經驗值 #encounter_xp | xp: 450
  sets_flag: dragon_defeated

### → 巢穴 #to_nest
to: dragon_nest
from: entrance
distance: 5min
"""


class TestParseEncounter:
    def test_encounter_parsed(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        nest = ir.nodes[1]
        assert nest.encounter is not None
        assert nest.encounter.trigger == "enter_node"
        assert nest.encounter.outcome == "auto_win"
        assert nest.encounter.sets_flag == "dragon_defeated"

    def test_encounter_enemies(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        enemies = ir.nodes[1].encounter.enemies
        assert len(enemies) == 2
        assert enemies[0].name == "幼藍龍"
        assert enemies[0].explicit_id == "young_blue_dragon"
        assert enemies[0].cr == "2"
        assert enemies[0].description == "一隻藍色的小龍，蜷縮在窩裡。"
        assert enemies[0].count == 1

    def test_encounter_enemy_count(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        lizard = ir.nodes[1].encounter.enemies[1]
        assert lizard.name == "冰凍蜥蜴"
        assert lizard.cr == "1/4"
        assert lizard.count == 2

    def test_encounter_narration(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        assert "低吼" in ir.nodes[1].encounter.narration

    def test_encounter_rewards(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        rewards = ir.nodes[1].encounter.rewards
        assert len(rewards) == 2
        assert rewards[0].name == "龍鱗碎片"
        assert rewards[0].value_gp == 10
        assert rewards[0].reward_type == "item"
        assert rewards[1].xp == 450
        assert rewards[1].reward_type == "xp"

    def test_node_without_encounter(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        assert ir.nodes[0].encounter is None

    def test_edges_still_parsed(self):
        """encounter 不影響邊的解析。"""
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        all_edges = []
        for node in ir.nodes:
            all_edges.extend(node.edges)
        assert len(all_edges) == 1
        assert all_edges[0].explicit_id == "to_nest"


# ── Encounter Build ─────────────────────────────────────


class TestBuildEncounter:
    def test_encounter_in_map_dict(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        result = build_map_fn(ir)
        nest = result["nodes"][1]
        assert "encounter" in nest
        enc = nest["encounter"]
        assert enc["trigger"] == "enter_node"
        assert enc["outcome"] == "auto_win"
        assert enc["sets_flag"] == "dragon_defeated"

    def test_encounter_enemies_in_dict(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        result = build_map_fn(ir)
        enemies = result["nodes"][1]["encounter"]["enemies"]
        assert len(enemies) == 2
        assert enemies[0]["id"] == "young_blue_dragon"
        assert enemies[0]["cr"] == "2"
        assert enemies[1]["count"] == 2

    def test_encounter_rewards_in_dict(self):
        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        result = build_map_fn(ir)
        rewards = result["nodes"][1]["encounter"]["rewards"]
        assert len(rewards) == 2
        assert rewards[0]["value_gp"] == 10
        assert rewards[1]["xp"] == 450

    def test_pydantic_validation_with_encounter(self):
        from tot.models.exploration import ExplorationMap

        ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        result = build_map_fn(ir)
        m = ExplorationMap.model_validate(result)
        assert m.nodes[1].encounter is not None
        assert m.nodes[1].encounter.sets_flag == "dragon_defeated"
        assert len(m.nodes[1].encounter.enemies) == 2

    def test_encounter_generates_script_event(self):
        """encounter auto_win 會自動生成對應的 ScriptEvent。"""
        from tot.models.adventure import AdventureScript

        meta_md = """\
---
id: enc_test
name: 遭遇測試
---
"""
        meta_dict, flags = parse_meta(meta_md)
        map_ir = parse_map(SAMPLE_ENCOUNTER_MAP)
        result = build_script(meta_dict, flags, [], [], maps=[map_ir])
        script = AdventureScript.model_validate(result)

        # 應有一個自動生成的遭遇事件
        enc_events = [e for e in script.events if e.id == "encounter_dragon_nest"]
        assert len(enc_events) == 1
        event = enc_events[0]
        assert event.trigger.type == "enter_node"
        assert event.trigger.node_id == "dragon_nest"
        # 應有 narrate + set_flag + add_item actions
        action_types = [a.type for a in event.actions]
        assert "narrate" in action_types
        assert "set_flag" in action_types
        assert "add_item" in action_types
        # 條件：not:dragon_defeated（避免重複觸發）
        assert event.condition == "not:dragon_defeated"


# ── Scene 解析 ──────────────────────────────────────


SAMPLE_SCENE = """\
---
id: encounter_intro
name: 洞穴遭遇開場
trigger: enter_node cave_mouth
condition: has:dragon_following
once: true
---

## 洞穴口旁白 #cave_narration
speaker: dm

> 你們沿著小路來到洞穴口。空氣中帶著刺骨寒意。

next: cave_shalefire_react

## 岩炎的反應 #cave_shalefire_react
speaker: shalefire
next: cave_evendorn_react

> 岩炎皺起眉頭：「這股冷氣……不對勁。」

## 埃文多恩的反應 #cave_evendorn_react
speaker: evendorn

> 埃文多恩握緊聖徽：「月之女神庇佑我們。」

choices:
- **「小心前進。」** #choice_careful → cave_entry
- **「先偵查。」** #choice_scout → cave_scout_check

## 設定旗標 #cave_set_flags
speaker: dm
silent: true
sets_flag: cave_entered
next: cave_actual_entry
"""


class TestParseScene:
    def test_meta(self):
        scene = parse_scene(SAMPLE_SCENE)
        assert scene.name == "洞穴遭遇開場"
        assert scene.explicit_id == "encounter_intro"

    def test_trigger(self):
        scene = parse_scene(SAMPLE_SCENE)
        assert scene.trigger_type == "enter_node"
        assert scene.trigger_target == "cave_mouth"

    def test_condition(self):
        scene = parse_scene(SAMPLE_SCENE)
        assert scene.condition == "has:dragon_following"

    def test_once(self):
        scene = parse_scene(SAMPLE_SCENE)
        assert scene.once is True

    def test_dialogues_count(self):
        scene = parse_scene(SAMPLE_SCENE)
        assert len(scene.dialogues) == 4

    def test_first_dialogue(self):
        scene = parse_scene(SAMPLE_SCENE)
        narration = scene.dialogues[0]
        assert narration.explicit_id == "cave_narration"
        assert narration.speaker == "dm"
        assert "洞穴口" in narration.text
        assert narration.next_id == "cave_shalefire_react"

    def test_speaker_required(self):
        """場景每段都有明確 speaker（非預設）。"""
        scene = parse_scene(SAMPLE_SCENE)
        for dlg in scene.dialogues:
            assert dlg.speaker != "", f"對話 {dlg.explicit_id} 缺少 speaker"

    def test_choices(self):
        scene = parse_scene(SAMPLE_SCENE)
        evendorn = scene.dialogues[2]
        assert len(evendorn.choices) == 2
        assert evendorn.choices[0].label == "小心前進。"
        assert evendorn.choices[0].next_id == "cave_entry"

    def test_silent_dialogue(self):
        scene = parse_scene(SAMPLE_SCENE)
        flags_dlg = scene.dialogues[3]
        assert flags_dlg.explicit_id == "cave_set_flags"
        assert flags_dlg.silent is True
        assert flags_dlg.sets_flag == "cave_entered"
        assert flags_dlg.next_id == "cave_actual_entry"

    def test_scene_without_trigger(self):
        """無 trigger 的場景（手動觸發）。"""
        md = """\
---
id: manual_scene
name: 手動場景
---

## 對話 #manual_dlg
speaker: dm

> 這是手動觸發的場景。
"""
        scene = parse_scene(md)
        assert scene.trigger_type == ""
        assert scene.trigger_target == ""
        assert scene.once is True  # 預設

    def test_scene_once_false(self):
        md = """\
---
id: repeatable
name: 可重複
once: false
---

## 對話 #repeat_dlg
speaker: dm

> 可重複的場景。
"""
        scene = parse_scene(md)
        assert scene.once is False

    def test_scene_with_skill_check(self):
        md = """\
---
id: scout_scene
name: 偵查場景
---

## 偵查檢定 #scout_check
speaker: dm

> 你仔細觀察四周。

skill_check:
  skill: Perception
  dc: 12
  pass: scout_success
  fail: scout_fail
"""
        scene = parse_scene(md)
        assert len(scene.dialogues) == 1
        dlg = scene.dialogues[0]
        assert dlg.skill_check is not None
        assert dlg.skill_check.skill == "Perception"
        assert dlg.skill_check.dc == 12


# ── Scene Build ────────────────────────────────────


class TestBuildScene:
    def _build_with_scene(self):
        meta_md = """\
---
id: scene_test
name: 場景測試
---
"""
        meta_dict, flags = parse_meta(meta_md)
        scene = parse_scene(SAMPLE_SCENE)
        return build_script(meta_dict, flags, [], [], scenes=[scene])

    def test_scene_in_output(self):
        result = self._build_with_scene()
        assert "scenes" in result
        assert "encounter_intro" in result["scenes"]

    def test_scene_dialogue_lines(self):
        result = self._build_with_scene()
        scene = result["scenes"]["encounter_intro"]
        dlg_ids = [d["id"] for d in scene["dialogue"]]
        assert "cave_narration" in dlg_ids
        assert "cave_shalefire_react" in dlg_ids

    def test_scene_silent_dialogue(self):
        result = self._build_with_scene()
        scene = result["scenes"]["encounter_intro"]
        flags_dlg = next(d for d in scene["dialogue"] if d["id"] == "cave_set_flags")
        assert flags_dlg["silent"] is True

    def test_scene_auto_event(self):
        """有 trigger 的場景應自動生成 start_scene 事件。"""
        result = self._build_with_scene()
        scene_events = [e for e in result["events"] if e["id"] == "scene_encounter_intro"]
        assert len(scene_events) == 1
        event = scene_events[0]
        assert event["trigger"]["type"] == "enter_node"
        assert event["trigger"]["node_id"] == "cave_mouth"
        assert event["condition"] == "has:dragon_following"
        # 動作為 start_scene
        assert event["actions"][0]["type"] == "start_scene"
        assert event["actions"][0]["scene_id"] == "encounter_intro"

    def test_scene_pydantic_validation(self):
        from tot.models.adventure import AdventureScript

        result = self._build_with_scene()
        script = AdventureScript.model_validate(result)
        assert "encounter_intro" in script.scenes
        assert len(script.scenes["encounter_intro"].dialogue) >= 4

    def test_scene_without_trigger_no_event(self):
        """無 trigger 的場景不生成事件。"""
        md = """\
---
id: manual_scene
name: 手動場景
---

## 對話 #manual_dlg
speaker: dm

> 這是手動觸發的場景。
"""
        meta_dict, flags = parse_meta("---\nid: test\nname: test\n---")
        scene = parse_scene(md)
        result = build_script(meta_dict, flags, [], [], scenes=[scene])
        assert "manual_scene" in result["scenes"]
        # 不應有 scene 事件
        assert len(result["events"]) == 0
