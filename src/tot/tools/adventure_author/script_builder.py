"""ScriptIR → AdventureScript JSON dict。

產出的 dict 可通過 AdventureScript.model_validate() 驗證。
"""

from __future__ import annotations

from tot.tools.adventure_author.id_gen import name_to_id
from tot.tools.adventure_author.ir import (
    ChapterIR,
    ChoiceIR,
    DialogueIR,
    EventIR,
    NpcIR,
)


def build_script(
    meta: dict[str, str],
    initial_flags: dict[str, int],
    npcs: list[NpcIR],
    chapters: list[ChapterIR],
) -> dict:
    """將 meta + NPC + 章節合併為 AdventureScript JSON dict。"""
    npc_dict = {}
    for npc in npcs:
        npc_data = _build_npc(npc)
        npc_dict[npc_data["id"]] = npc_data

    events = []
    for chapter in chapters:
        for event_ir in chapter.events:
            event = _build_event(event_ir, chapter.chapter)
            events.append(event)

    return {
        "id": meta.get("id", ""),
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "initial_flags": initial_flags,
        "npcs": npc_dict,
        "events": events,
    }


def _build_npc(npc: NpcIR) -> dict:
    """將 NpcIR 轉為 NpcDef dict。"""
    npc_id = name_to_id(npc.name, npc.explicit_id)

    dialogue_lines = []
    for dlg in npc.dialogues:
        lines = _build_dialogue(dlg, npc_id)
        dialogue_lines.extend(lines)

    result: dict = {
        "id": npc_id,
        "name": npc.name,
        "dialogue": dialogue_lines,
    }
    if npc.description:
        result["description"] = npc.description
    if npc.location:
        result["node_id"] = npc.location

    return result


def _build_dialogue(dlg: DialogueIR, npc_id: str) -> list[dict]:
    """將 DialogueIR 轉為一或多個 DialogueLine dict。

    如果有 choices，每個 choice 也會變成獨立的 DialogueLine。
    主對話行的 next_lines 指向各 choice 的 id。
    """
    dlg_id = name_to_id(dlg.title, dlg.explicit_id)
    speaker = dlg.speaker or npc_id

    # 組合條件：chapter 語法糖 + condition
    condition = _combine_condition(dlg.condition, dlg.chapter)

    main_line: dict = {
        "id": dlg_id,
        "speaker": speaker,
        "text": dlg.text,
    }
    if condition:
        main_line["condition"] = condition
    if dlg.sets_flag:
        main_line["sets_flag"] = dlg.sets_flag
    if dlg.map_id:
        # map 綁定存在 condition 中（未來可擴展為獨立欄位）
        # 目前僅作為參考，不影響引擎行為
        pass

    result = [main_line]

    if dlg.choices:
        choice_ids = []
        for choice in dlg.choices:
            choice_line = _build_choice(choice, npc_id)
            choice_ids.append(choice_line["id"])
            result.append(choice_line)
        main_line["next_lines"] = choice_ids

    return result


def _build_choice(choice: ChoiceIR, npc_id: str) -> dict:
    """將 ChoiceIR 轉為 DialogueLine dict。"""
    choice_id = name_to_id(choice.label, choice.explicit_id)

    line: dict = {
        "id": choice_id,
        "speaker": npc_id,
        "text": "",
        "choice_label": choice.label,
    }
    if choice.sets_flag:
        line["sets_flag"] = choice.sets_flag
    if choice.next_id:
        line["next_lines"] = [choice.next_id]

    return line


def _combine_condition(condition: str, chapter: str) -> str:
    """合併 condition 和 chapter 語法糖。

    chapter: 02 → has:chapter_02
    如果 condition 也有值，用 all: 組合。
    """
    parts = []
    if chapter:
        parts.append(f"has:chapter_{chapter}")
    if condition:
        parts.append(condition)

    if len(parts) == 0:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "all:" + ",".join(parts)


def _build_event(event_ir: EventIR, chapter_num: str) -> dict:
    """將 EventIR 轉為 ScriptEvent dict。"""
    event_id = name_to_id(event_ir.name, event_ir.explicit_id)

    # 觸發器
    trigger: dict = {"type": event_ir.trigger_type}
    if event_ir.trigger_type == "enter_node" and event_ir.trigger_target:
        trigger["node_id"] = event_ir.trigger_target
    elif event_ir.trigger_type == "take_item" and event_ir.trigger_target:
        trigger["item_id"] = event_ir.trigger_target
    elif event_ir.trigger_type == "flag_set" and event_ir.trigger_target:
        trigger["flag"] = event_ir.trigger_target
    elif event_ir.trigger_type == "talk_end" and event_ir.trigger_target:
        trigger["dialogue_id"] = event_ir.trigger_target

    # 動作列表
    actions = []

    # 旁白文字 → narrate action（放在最前面）
    if event_ir.narrate:
        actions.append({"type": "narrate", "text": event_ir.narrate})

    # 其他 action
    for action_dict in event_ir.actions:
        action = dict(action_dict)  # 淺拷貝
        # 數值欄位轉型
        if "value" in action:
            action["value"] = int(action["value"])
        actions.append(action)

    result: dict = {
        "id": event_id,
        "trigger": trigger,
        "actions": actions,
    }
    if event_ir.condition:
        result["condition"] = event_ir.condition
    if not event_ir.once:
        result["once"] = False

    return result
