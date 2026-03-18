"""ScriptIR → AdventureScript JSON dict。

產出的 dict 可通過 AdventureScript.model_validate() 驗證。
"""

from __future__ import annotations

from tot.tools.adventure_author.id_gen import name_to_id
from tot.tools.adventure_author.ir import (
    ChapterIR,
    ChoiceIR,
    DialogueIR,
    EncounterIR,
    EventIR,
    MapIR,
    NpcIR,
    SceneIR,
)


def build_script(
    meta: dict[str, str],
    initial_flags: dict[str, int],
    npcs: list[NpcIR],
    chapters: list[ChapterIR],
    maps: list[MapIR] | None = None,
    scenes: list[SceneIR] | None = None,
) -> dict:
    """將 meta + NPC + 章節 + 地圖遭遇 + 場景合併為 AdventureScript JSON dict。"""
    npc_dict = {}
    for npc in npcs:
        npc_data = _build_npc(npc)
        npc_dict[npc_data["id"]] = npc_data

    scene_dict = {}
    events = []

    # 從場景生成 SceneDef + 自動觸發事件
    if scenes:
        for scene_ir in scenes:
            scene_data = _build_scene(scene_ir)
            scene_dict[scene_data["id"]] = scene_data
            # 有 trigger 的場景自動生成 start_scene 事件
            if scene_ir.trigger_type:
                scene_event = _build_scene_event(scene_ir)
                events.append(scene_event)

    # 從地圖遭遇自動生成事件
    if maps:
        for map_ir in maps:
            for node in map_ir.nodes:
                if node.encounter:
                    node_id = name_to_id(node.name, node.explicit_id)
                    encounter_events = _build_encounter_events(
                        node.encounter,
                        node_id,
                    )
                    events.extend(encounter_events)

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
        "scenes": scene_dict,
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
    if dlg.silent:
        main_line["silent"] = True
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
    elif dlg.skill_check:
        sc = dlg.skill_check
        sc_dict: dict = {
            "skill": sc.skill,
            "dc": sc.dc,
            "pass_dialogue": sc.pass_id,
            "fail_dialogue": sc.fail_id,
            "hidden_dc": sc.hidden_dc,
        }
        if sc.assists:
            sc_dict["assists"] = [
                {
                    "name": a.name,
                    "spell_id": a.spell_id,
                    "source_npc": a.source_npc,
                    "bonus_die": a.bonus_die,
                    "advantage": a.advantage,
                    "requires_concentration": a.requires_concentration,
                }
                for a in sc.assists
            ]
        main_line["skill_check"] = sc_dict
    elif dlg.next_id:
        main_line["next_lines"] = [dlg.next_id]

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


def _build_scene(scene_ir: SceneIR) -> dict:
    """將 SceneIR 轉為 SceneDef dict。"""
    scene_id = name_to_id(scene_ir.name, scene_ir.explicit_id)

    dialogue_lines = []
    for dlg in scene_ir.dialogues:
        lines = _build_dialogue(dlg, "")
        dialogue_lines.extend(lines)

    return {
        "id": scene_id,
        "name": scene_ir.name,
        "dialogue": dialogue_lines,
    }


def _build_scene_event(scene_ir: SceneIR) -> dict:
    """從有 trigger 的 SceneIR 自動生成 start_scene 事件。"""
    scene_id = name_to_id(scene_ir.name, scene_ir.explicit_id)

    trigger: dict = {"type": scene_ir.trigger_type}
    if scene_ir.trigger_type == "enter_node" and scene_ir.trigger_target:
        trigger["node_id"] = scene_ir.trigger_target
    elif scene_ir.trigger_type == "flag_set" and scene_ir.trigger_target:
        trigger["flag"] = scene_ir.trigger_target
    elif scene_ir.trigger_type == "take_item" and scene_ir.trigger_target:
        trigger["item_id"] = scene_ir.trigger_target
    elif scene_ir.trigger_type == "talk_end" and scene_ir.trigger_target:
        trigger["dialogue_id"] = scene_ir.trigger_target

    result: dict = {
        "id": f"scene_{scene_id}",
        "trigger": trigger,
        "actions": [{"type": "start_scene", "scene_id": scene_id}],
    }
    if scene_ir.condition:
        result["condition"] = scene_ir.condition
    if not scene_ir.once:
        result["once"] = False

    return result


def _build_encounter_events(
    encounter: EncounterIR,
    node_id: str,
) -> list[dict]:
    """從 EncounterIR 自動生成 enter_node 事件（auto_win 模式）。

    產出一個事件：進入節點 → 旁白 → set_flag → add_item（獎勵）。
    """
    event_id = f"encounter_{node_id}"
    actions: list[dict] = []

    # 旁白
    if encounter.narration:
        actions.append({"type": "narrate", "text": encounter.narration})

    # 設定 flag
    if encounter.sets_flag:
        actions.append({"type": "set_flag", "flag": encounter.sets_flag})

    # 獎勵物品
    for reward in encounter.rewards:
        if reward.reward_type == "item":
            rid = name_to_id(reward.name, reward.explicit_id)
            actions.append({"type": "add_item", "item_id": rid})

    # 觸發器
    trigger: dict = {"type": encounter.trigger}
    if encounter.trigger == "enter_node":
        trigger["node_id"] = node_id

    result: dict = {
        "id": event_id,
        "trigger": trigger,
        "actions": actions,
    }

    # auto_win 遭遇只觸發一次
    if encounter.sets_flag:
        result["condition"] = f"not:{encounter.sets_flag}"

    return [result]


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
