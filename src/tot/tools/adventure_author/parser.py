"""Markdown → IR 解析器。

每種 MD 檔案有一個入口函式：
- parse_meta()    — _meta.md → (meta_dict, initial_flags)
- parse_map()     — maps/*.md → MapIR
- parse_npc()     — npcs/*.md → NpcIR
- parse_chapter() — chapters/*.md → ChapterIR

解析策略：逐行掃描，用 heading 層級做狀態機。
"""

from __future__ import annotations

import re

from tot.tools.adventure_author.id_gen import parse_heading_id
from tot.tools.adventure_author.ir import (
    ChapterIR,
    ChoiceIR,
    DialogueIR,
    EdgeIR,
    EventIR,
    ItemIR,
    MapIR,
    NodeIR,
    NpcIR,
    PoiIR,
)


def _parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], int]:
    """解析 YAML frontmatter（--- 包圍），回傳 dict 和下一行索引。"""
    if not lines or lines[0].strip() != "---":
        return {}, 0

    meta: dict[str, str] = {}
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line == "---":
            return meta, i + 1
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
        i += 1

    return meta, len(lines)


def _strip_comment(line: str) -> str:
    """移除行內 # 註解（不影響 heading 的 #id 標記）。"""
    # key: value # comment → key: value
    # 但 ## heading #id 不受影響（因為 heading 不經過此函式）
    idx = line.find("  #")
    if idx >= 0:
        return line[:idx].rstrip()
    return line


def _parse_kv(line: str) -> tuple[str, str] | None:
    """解析 key: value 行，回傳 (key, value) 或 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith(">"):
        return None
    if ":" in stripped and not stripped.startswith("-"):
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()
        # 排除 heading（## / ###）
        if not key.startswith("#"):
            return key, _strip_comment(val)
    return None


# ── Meta 解析 ────────────────────────────────────────────


def parse_meta(text: str) -> tuple[dict[str, str], dict[str, int]]:
    """解析 _meta.md，回傳 (meta_dict, initial_flags)。"""
    lines = text.splitlines()
    meta, start = _parse_frontmatter(lines)

    initial_flags: dict[str, int] = {}
    in_flags = False
    for i in range(start, len(lines)):
        line = lines[i].strip()
        if not line or line.startswith("<!--"):
            in_flags = False
            continue
        if line == "initial_flags:":
            in_flags = True
            continue
        if in_flags and line.startswith("- "):
            entry = line[2:].strip()
            if ":" in entry:
                k, _, v = entry.partition(":")
                initial_flags[k.strip()] = int(v.strip())

    return meta, initial_flags


# ── Map 解析 ─────────────────────────────────────────────


def parse_map(text: str) -> MapIR:
    """解析地圖 MD → MapIR。"""
    lines = text.splitlines()
    meta, start = _parse_frontmatter(lines)
    ir = MapIR(meta=meta)

    current_node: NodeIR | None = None
    current_edge: EdgeIR | None = None
    in_items = False
    in_pois = False
    current_item: ItemIR | None = None
    current_poi: PoiIR | None = None

    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 空行或註解
        if not stripped or stripped.startswith("<!--"):
            # 跳過多行註解
            if stripped.startswith("<!--") and "-->" not in stripped:
                while i < len(lines) and "-->" not in lines[i]:
                    i += 1
            i += 1
            continue

        # ## 節點
        if stripped.startswith("## ") and not stripped.startswith("### "):
            _flush_item(current_item, current_node)
            _flush_poi(current_poi, current_node)
            _flush_edge(current_edge, current_node)
            current_item = None
            current_poi = None
            current_edge = None
            in_items = False
            in_pois = False

            heading = stripped[3:]
            name, eid = parse_heading_id(heading)
            current_node = NodeIR(name=name, explicit_id=eid)
            ir.nodes.append(current_node)
            i += 1
            continue

        # ### → 邊
        if stripped.startswith("### ") and "→" in stripped:
            _flush_item(current_item, current_node)
            _flush_poi(current_poi, current_node)
            _flush_edge(current_edge, current_node)
            current_item = None
            current_poi = None
            in_items = False
            in_pois = False

            heading = stripped[4:]
            # 去掉 → 前綴
            arrow_idx = heading.index("→")
            edge_text = heading[arrow_idx + 1 :].strip()
            name, eid = parse_heading_id(edge_text)
            current_edge = EdgeIR(name=name, explicit_id=eid)
            i += 1
            continue

        # items: 區塊開始
        if stripped == "items:":
            _flush_poi(current_poi, current_node)
            current_poi = None
            in_items = True
            in_pois = False
            i += 1
            continue

        # pois: 區塊開始
        if stripped == "pois:":
            _flush_item(current_item, current_node)
            current_item = None
            in_pois = True
            in_items = False
            i += 1
            continue

        # items 列表項
        if in_items and stripped.startswith("- ") and current_node:
            _flush_item(current_item, current_node)
            current_item = _parse_item_header(stripped[2:])
            i += 1
            continue

        # item 描述（縮排行）
        if in_items and current_item and (line.startswith("  ") or line.startswith("\t")):
            item_line = stripped
            # 額外屬性
            kv = _parse_kv(item_line)
            if kv:
                key, val = kv
                if key == "grants_key":
                    current_item.grants_key = val
                elif key == "value_gp":
                    current_item.value_gp = int(val)
            elif not item_line.startswith("<!--"):
                current_item.description = item_line
            i += 1
            continue

        # pois 列表項
        if in_pois and stripped.startswith("- ") and current_node:
            _flush_poi(current_poi, current_node)
            current_poi = _parse_poi_header(stripped[2:])
            i += 1
            continue

        # poi 描述/屬性（縮排行）
        if in_pois and current_poi and (line.startswith("  ") or line.startswith("\t")):
            poi_line = stripped
            kv = _parse_kv(poi_line)
            if kv:
                key, val = kv
                if key == "npcs":
                    current_poi.npcs = [n.strip() for n in val.split(",")]
            elif not poi_line.startswith("<!--"):
                current_poi.description = poi_line
            i += 1
            continue

        # 邊屬性
        if current_edge:
            kv = _parse_kv(stripped)
            if kv:
                current_edge.properties[kv[0]] = kv[1]
            i += 1
            continue

        # 節點屬性
        if current_node:
            kv = _parse_kv(stripped)
            if kv:
                key, val = kv
                if key == "type":
                    current_node.node_type = val
                elif key == "description":
                    current_node.description = val
                elif key == "ambient":
                    current_node.ambient = val
                elif key == "combat_map":
                    current_node.combat_map = val
                elif key == "sub_map":
                    current_node.sub_map = val
                elif key == "npcs":
                    current_node.npcs = [n.strip() for n in val.split(",")]

        i += 1

    # 收尾
    _flush_item(current_item, current_node)
    _flush_poi(current_poi, current_node)
    _flush_edge(current_edge, current_node)

    return ir


def _flush_item(item: ItemIR | None, node: NodeIR | None) -> None:
    if item and node:
        node.items.append(item)


def _flush_poi(poi: PoiIR | None, node: NodeIR | None) -> None:
    if poi and node:
        node.pois.append(poi)


def _flush_edge(edge: EdgeIR | None, node: NodeIR | None) -> None:
    if edge and node:
        node.edges.append(edge)


def _parse_item_header(text: str) -> ItemIR:
    """解析 items 列表項：名稱 #id | type | dc:N"""
    parts = [p.strip() for p in text.split("|")]
    name_part = parts[0]
    name, eid = parse_heading_id(name_part)

    item = ItemIR(name=name, explicit_id=eid)
    for part in parts[1:]:
        part = part.strip()
        if part.startswith("dc:"):
            item.investigation_dc = int(part[3:])
        elif part in ("item", "clue", "chest", "trap_hint"):
            item.item_type = part
    return item


def _parse_poi_header(text: str) -> PoiIR:
    """解析 pois 列表項：名稱 #id | poi"""
    parts = [p.strip() for p in text.split("|")]
    name_part = parts[0]
    name, eid = parse_heading_id(name_part)
    return PoiIR(name=name, explicit_id=eid)


# ── NPC 解析 ─────────────────────────────────────────────


def parse_npc(text: str) -> NpcIR:
    """解析 NPC MD → NpcIR。"""
    lines = text.splitlines()
    meta, start = _parse_frontmatter(lines)

    npc = NpcIR(
        name=meta.get("name", ""),
        explicit_id=meta.get("id"),
    )

    section: str = ""  # "background" / "dialogue"
    current_dialogue: DialogueIR | None = None
    in_choices = False

    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 空行
        if not stripped:
            i += 1
            continue

        # 跳過註解
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                while i < len(lines) and "-->" not in lines[i]:
                    i += 1
            i += 1
            continue

        # ## 區塊
        if stripped.startswith("## ") and not stripped.startswith("### "):
            heading = stripped[3:]
            if heading.strip() == "背景":
                _flush_dialogue(current_dialogue, npc)
                current_dialogue = None
                section = "background"
                in_choices = False
            else:
                _flush_dialogue(current_dialogue, npc)
                in_choices = False
                section = "dialogue"
                name, eid = parse_heading_id(heading)

                # 判斷是否為常態對話
                current_dialogue = DialogueIR(
                    title=name,
                    explicit_id=eid,
                    speaker=meta.get("id", ""),
                )
            i += 1
            continue

        # 背景區屬性
        if section == "background":
            kv = _parse_kv(stripped)
            if kv:
                key, val = kv
                if key == "description":
                    npc.description = val
                elif key == "location":
                    npc.location = val
                elif key == "personality":
                    npc.personality = val
                elif key == "role":
                    npc.role = val
            i += 1
            continue

        # 對話區
        if section == "dialogue" and current_dialogue:
            # > 文字
            if stripped.startswith("> "):
                text_line = stripped[2:]
                if current_dialogue.text:
                    current_dialogue.text += "\n" + text_line
                else:
                    current_dialogue.text = text_line
                i += 1
                continue

            # choices: 區塊
            if stripped == "choices:":
                in_choices = True
                i += 1
                continue

            # 選項：- **「...」** #id → next_id
            if in_choices and stripped.startswith("- **"):
                choice = _parse_choice(stripped)
                if choice:
                    current_dialogue.choices.append(choice)
                i += 1
                continue

            # 選項的 sets_flag（縮排行）
            if in_choices and (line.startswith("  ") or line.startswith("\t")):
                kv = _parse_kv(stripped)
                if kv and kv[0] == "sets_flag" and current_dialogue.choices:
                    current_dialogue.choices[-1].sets_flag = kv[1]
                i += 1
                continue

            # 對話屬性
            kv = _parse_kv(stripped)
            if kv:
                key, val = kv
                if key == "speaker":
                    current_dialogue.speaker = val
                elif key == "condition":
                    current_dialogue.condition = val
                elif key == "sets_flag":
                    current_dialogue.sets_flag = val
                elif key == "map":
                    current_dialogue.map_id = val
                elif key == "chapter":
                    current_dialogue.chapter = val

        i += 1

    _flush_dialogue(current_dialogue, npc)
    return npc


def _flush_dialogue(dialogue: DialogueIR | None, npc: NpcIR) -> None:
    if dialogue:
        npc.dialogues.append(dialogue)


def _parse_choice(text: str) -> ChoiceIR | None:
    """解析選項行：- **「文字」** #id → next_id"""
    # 提取 **「...」** 或 **"..."** 中的文字
    label_match = re.search(r"\*\*[「\"'](.+?)[」\"']\*\*", text)
    if not label_match:
        return None

    label = label_match.group(1)
    rest = text[label_match.end() :].strip()

    # 解析 #id → next_id
    eid = None
    next_id = ""

    id_match = re.search(r"#(\S+)", rest)
    if id_match:
        eid = id_match.group(1)
        rest = rest[id_match.end() :].strip()

    arrow_match = re.search(r"→\s*(\S+)", rest)
    if arrow_match:
        next_id = arrow_match.group(1)

    return ChoiceIR(label=label, explicit_id=eid, next_id=next_id)


# ── Chapter 解析 ─────────────────────────────────────────


def parse_chapter(text: str) -> ChapterIR:
    """解析章節 MD → ChapterIR。"""
    lines = text.splitlines()
    meta, start = _parse_frontmatter(lines)

    chapter = ChapterIR(
        chapter=meta.get("chapter", ""),
        title=meta.get("title", ""),
    )

    current_event: EventIR | None = None

    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 空行
        if not stripped:
            i += 1
            continue

        # 跳過註解
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                while i < len(lines) and "-->" not in lines[i]:
                    i += 1
            i += 1
            continue

        # ## 事件
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if current_event:
                chapter.events.append(current_event)

            heading = stripped[3:]
            name, eid = parse_heading_id(heading)
            current_event = EventIR(name=name, explicit_id=eid)
            i += 1
            continue

        if not current_event:
            i += 1
            continue

        # > 旁白文字
        if stripped.startswith("> "):
            narrate_text = stripped[2:]
            if current_event.narrate:
                current_event.narrate += "\n" + narrate_text
            else:
                current_event.narrate = narrate_text
            i += 1
            continue

        # - action 列表
        if stripped.startswith("- "):
            action = _parse_action(stripped[2:])
            if action:
                current_event.actions.append(action)
            i += 1
            continue

        # 事件屬性
        kv = _parse_kv(stripped)
        if kv:
            key, val = kv
            if key == "trigger":
                _parse_trigger(val, current_event)
            elif key == "condition":
                current_event.condition = val
            elif key == "once":
                current_event.once = val.lower() != "false"
            elif key == "next_chapter":
                pass  # 僅供參考，不影響引擎邏輯

        i += 1

    if current_event:
        chapter.events.append(current_event)

    return chapter


def _parse_trigger(val: str, event: EventIR) -> None:
    """解析 trigger: type target。"""
    parts = val.strip().split(None, 1)
    event.trigger_type = parts[0] if parts else ""
    event.trigger_target = parts[1] if len(parts) > 1 else ""


def _parse_action(text: str) -> dict[str, str] | None:
    """解析 action 行（- type: params）。"""
    stripped = text.strip()
    if ":" not in stripped:
        return None

    key, _, val = stripped.partition(":")
    key = key.strip()
    val = val.strip()

    # 特殊語法
    if key == "move_npc" and "→" in val:
        parts = val.split("→")
        return {"type": "move_npc", "npc_id": parts[0].strip(), "node_id": parts[1].strip()}

    if key == "inc_flag" and "+" in val:
        parts = val.split("+")
        return {"type": "inc_flag", "flag": parts[0].strip(), "value": parts[1].strip()}

    if key == "set_flag" and "=" in val:
        parts = val.split("=")
        return {"type": "set_flag", "flag": parts[0].strip(), "value": parts[1].strip()}

    # 一般 action
    if key in ("narrate", "tutorial"):
        return {"type": key, "text": val}
    if key in ("set_flag", "start_timer", "clear_timer"):
        return {"type": key, "flag": val}
    if key in ("reveal_node", "reveal_edge"):
        return {"type": key, key.split("_")[1] + "_id": val}
    if key == "add_item":
        return {"type": "add_item", "item_id": val}

    return {"type": key, "text": val}
