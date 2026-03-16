"""冒險引擎測試——條件評估 / 事件引擎 / 對話引擎。"""

from __future__ import annotations

import pytest

from tot.gremlins.bone_engine.adventure import (
    advance_dialogue,
    check_events,
    evaluate_condition,
    execute_event,
    get_available_lines,
    get_available_npcs,
    init_adventure_state,
    load_adventure,
)
from tot.models.adventure import (
    AdventureScript,
    AdventureState,
    DialogueLine,
    EventAction,
    EventTrigger,
    NpcDef,
    ScriptEvent,
)

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def empty_state() -> AdventureState:
    """空白冒險狀態。"""
    return AdventureState(script_id="test")


@pytest.fixture
def flagged_state() -> AdventureState:
    """帶有幾個 flag 的冒險狀態。"""
    return AdventureState(
        script_id="test",
        story_flags={
            "found_dragon": 1,
            "talked_to_quinn": 1,
            "quinn_affinity": 3,
            "tavern_visits": 5,
        },
        timed_flags={
            "sliding": 10,  # 在第 10 分鐘設定
        },
    )


# ── 空條件 ────────────────────────────────────────────────


class TestEmptyCondition:
    """空字串永遠成立。"""

    def test_empty_string_always_true(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("", empty_state) is True

    def test_empty_string_with_flags(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("", flagged_state) is True


# ── has / not ─────────────────────────────────────────────


class TestHasCondition:
    """has:flag — flag 存在（值 > 0）。"""

    def test_has_existing_flag(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("has:found_dragon", flagged_state) is True

    def test_has_missing_flag(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("has:found_dragon", empty_state) is False

    def test_has_zero_value_flag(self, empty_state: AdventureState) -> None:
        """值 = 0 視為不存在。"""
        empty_state.story_flags["cleared"] = 0
        assert evaluate_condition("has:cleared", empty_state) is False

    def test_has_high_value_flag(self, flagged_state: AdventureState) -> None:
        """值 > 1 也算存在。"""
        assert evaluate_condition("has:quinn_affinity", flagged_state) is True


class TestNotCondition:
    """not:flag — flag 不存在（值 = 0 或無此 key）。"""

    def test_not_missing_flag(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("not:found_dragon", empty_state) is True

    def test_not_existing_flag(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("not:found_dragon", flagged_state) is False

    def test_not_zero_value(self, empty_state: AdventureState) -> None:
        empty_state.story_flags["cleared"] = 0
        assert evaluate_condition("not:cleared", empty_state) is True


# ── all / any ─────────────────────────────────────────────


class TestAllCondition:
    """all:cond1,cond2 — 所有子條件都成立。"""

    def test_all_both_true(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("all:has:found_dragon,has:talked_to_quinn", flagged_state) is True

    def test_all_one_false(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("all:has:found_dragon,has:nonexistent", flagged_state) is False

    def test_all_both_false(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("all:has:found_dragon,has:talked_to_quinn", empty_state) is False

    def test_all_single_condition(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("all:has:found_dragon", flagged_state) is True

    def test_all_mixed_has_not(self, flagged_state: AdventureState) -> None:
        """all: 可混合 has/not。"""
        assert evaluate_condition("all:has:found_dragon,not:nonexistent", flagged_state) is True


class TestAnyCondition:
    """any:cond1,cond2 — 任一子條件成立。"""

    def test_any_both_true(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("any:has:found_dragon,has:talked_to_quinn", flagged_state) is True

    def test_any_one_true(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("any:has:found_dragon,has:nonexistent", flagged_state) is True

    def test_any_none_true(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("any:has:found_dragon,has:talked_to_quinn", empty_state) is False

    def test_any_single_condition(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("any:has:found_dragon", empty_state) is False


# ── gte / lt（數值比較）────────────────────────────────────


class TestGteCondition:
    """gte:flag:N — flag 值 ≥ N。"""

    def test_gte_equal(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("gte:quinn_affinity:3", flagged_state) is True

    def test_gte_greater(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("gte:quinn_affinity:2", flagged_state) is True

    def test_gte_less(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("gte:quinn_affinity:4", flagged_state) is False

    def test_gte_missing_flag(self, empty_state: AdventureState) -> None:
        """不存在的 flag 值為 0。"""
        assert evaluate_condition("gte:quinn_affinity:1", empty_state) is False

    def test_gte_zero_threshold(self, empty_state: AdventureState) -> None:
        """gte:flag:0 — 不存在的 flag 值 = 0 ≥ 0 → True。"""
        assert evaluate_condition("gte:missing:0", empty_state) is True


class TestLtCondition:
    """lt:flag:N — flag 值 < N。"""

    def test_lt_less(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("lt:quinn_affinity:4", flagged_state) is True

    def test_lt_equal(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("lt:quinn_affinity:3", flagged_state) is False

    def test_lt_greater(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("lt:quinn_affinity:2", flagged_state) is False

    def test_lt_missing_flag(self, empty_state: AdventureState) -> None:
        """不存在的 flag 值 = 0 < 1 → True。"""
        assert evaluate_condition("lt:quinn_affinity:1", empty_state) is True


# ── 計時條件 ──────────────────────────────────────────────


class TestTimerCondition:
    """timer:flag — 計時 flag 存在。"""

    def test_timer_exists(self, flagged_state: AdventureState) -> None:
        assert evaluate_condition("timer:sliding", flagged_state) is True

    def test_timer_missing(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("timer:sliding", empty_state) is False


class TestWithinCondition:
    """within:flag:N — 計時 flag 設定後不到 N 分鐘。"""

    def test_within_time(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 13 分鐘 → 過了 3 分鐘 < 5
        assert evaluate_condition("within:sliding:5", flagged_state, elapsed_minutes=13) is True

    def test_within_expired(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 16 分鐘 → 過了 6 分鐘 ≥ 5
        assert evaluate_condition("within:sliding:5", flagged_state, elapsed_minutes=16) is False

    def test_within_exact_boundary(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 15 分鐘 → 過了 5 分鐘 = 5（不算 within）
        assert evaluate_condition("within:sliding:5", flagged_state, elapsed_minutes=15) is False

    def test_within_missing_timer(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("within:sliding:5", empty_state, elapsed_minutes=10) is False


class TestElapsedCondition:
    """elapsed:flag:N — 計時 flag 設定後已過 N 分鐘。"""

    def test_elapsed_enough(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 16 分鐘 → 過了 6 ≥ 5
        assert evaluate_condition("elapsed:sliding:5", flagged_state, elapsed_minutes=16) is True

    def test_elapsed_not_enough(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 13 分鐘 → 過了 3 < 5
        assert evaluate_condition("elapsed:sliding:5", flagged_state, elapsed_minutes=13) is False

    def test_elapsed_exact_boundary(self, flagged_state: AdventureState) -> None:
        # sliding 在 10 分鐘設定，現在是 15 分鐘 → 過了 5 = 5（算 elapsed）
        assert evaluate_condition("elapsed:sliding:5", flagged_state, elapsed_minutes=15) is True

    def test_elapsed_missing_timer(self, empty_state: AdventureState) -> None:
        assert evaluate_condition("elapsed:sliding:5", empty_state, elapsed_minutes=20) is False


# ── 錯誤處理 ──────────────────────────────────────────────


class TestInvalidCondition:
    """未知語法應拋出 ValueError。"""

    def test_unknown_prefix(self, empty_state: AdventureState) -> None:
        with pytest.raises(ValueError, match="未知的條件語法"):
            evaluate_condition("invalid:something", empty_state)

    def test_bare_word(self, empty_state: AdventureState) -> None:
        with pytest.raises(ValueError, match="未知的條件語法"):
            evaluate_condition("just_a_word", empty_state)


# ── 模型序列化 ────────────────────────────────────────────


class TestAdventureStateSerialization:
    """AdventureState 可序列化/反序列化。"""

    def test_roundtrip_json(self, flagged_state: AdventureState) -> None:
        json_str = flagged_state.model_dump_json()
        restored = AdventureState.model_validate_json(json_str)
        assert restored.script_id == flagged_state.script_id
        assert restored.story_flags == flagged_state.story_flags
        assert restored.timed_flags == flagged_state.timed_flags
        assert restored.fired_events == flagged_state.fired_events

    def test_default_empty_state(self) -> None:
        state = AdventureState(script_id="test")
        assert state.story_flags == {}
        assert state.timed_flags == {}
        assert state.fired_events == set()
        assert state.npc_locations == {}
        assert state.active_dialogue is None
        assert state.dialogue_history == []


# ══════════════════════════════════════════════════════════
# Stage B: 事件引擎
# ══════════════════════════════════════════════════════════


def _make_script(
    events: list[ScriptEvent], npcs: dict[str, NpcDef] | None = None
) -> AdventureScript:
    """測試用：快速建立 AdventureScript。"""
    return AdventureScript(
        id="test_script",
        name="測試劇本",
        events=events,
        npcs=npcs or {},
    )


# ── check_events ──────────────────────────────────────────


class TestCheckEvents:
    """check_events() — 找出符合觸發條件的事件。"""

    def test_enter_node_matches(self) -> None:
        """進入指定節點觸發事件。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            actions=[EventAction(type="narrate", text="你進入了洞穴。")],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        matched = check_events(script, state, "enter_node", node_id="cave")
        assert len(matched) == 1
        assert matched[0].id == "ev1"

    def test_enter_node_wrong_node(self) -> None:
        """進入不同節點不觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert check_events(script, state, "enter_node", node_id="village") == []

    def test_once_event_not_refired(self) -> None:
        """once=True 事件不會重複觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            once=True,
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script", fired_events={"ev1"})
        assert check_events(script, state, "enter_node", node_id="cave") == []

    def test_once_false_can_refire(self) -> None:
        """once=False 事件可重複觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            once=False,
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script", fired_events={"ev1"})
        assert len(check_events(script, state, "enter_node", node_id="cave")) == 1

    def test_trigger_condition_filters(self) -> None:
        """觸發器 condition 不滿足 → 不觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave", condition="has:found_key"),
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert check_events(script, state, "enter_node", node_id="cave") == []

    def test_trigger_condition_passes(self) -> None:
        """觸發器 condition 滿足 → 觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave", condition="has:found_key"),
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script", story_flags={"found_key": 1})
        assert len(check_events(script, state, "enter_node", node_id="cave")) == 1

    def test_event_level_condition(self) -> None:
        """事件層級 condition 不滿足 → 不觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            condition="has:quest_started",
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert check_events(script, state, "enter_node", node_id="cave") == []

    def test_take_item_trigger(self) -> None:
        """拿取物品觸發事件。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="take_item", item_id="golden_key"),
            actions=[EventAction(type="set_flag", flag="has_key")],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert len(check_events(script, state, "take_item", item_id="golden_key")) == 1

    def test_flag_set_trigger(self) -> None:
        """flag 設定觸發事件。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="flag_set", flag="found_dragon"),
            actions=[EventAction(type="narrate", text="龍寶寶抬頭看你。")],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert len(check_events(script, state, "flag_set", flag="found_dragon")) == 1

    def test_multiple_events_order_preserved(self) -> None:
        """多個事件按定義順序回傳。"""
        ev1 = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            actions=[],
        )
        ev2 = ScriptEvent(
            id="ev2",
            trigger=EventTrigger(type="enter_node", node_id="cave"),
            actions=[],
        )
        script = _make_script([ev1, ev2])
        state = AdventureState(script_id="test_script")
        matched = check_events(script, state, "enter_node", node_id="cave")
        assert [e.id for e in matched] == ["ev1", "ev2"]

    def test_wildcard_node_id(self) -> None:
        """trigger.node_id 為空 → 任何節點都觸發。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[],
        )
        script = _make_script([ev])
        state = AdventureState(script_id="test_script")
        assert len(check_events(script, state, "enter_node", node_id="anywhere")) == 1


# ── execute_event ─────────────────────────────────────────


class TestExecuteEvent:
    """execute_event() — 執行事件 action、回傳新 state。"""

    def test_set_flag(self) -> None:
        """set_flag action 設定 story flag。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[EventAction(type="set_flag", flag="found_dragon", value=1)],
        )
        state = AdventureState(script_id="test")
        new_state, actions = execute_event(state, ev)
        assert new_state.story_flags["found_dragon"] == 1
        # 原 state 不變
        assert "found_dragon" not in state.story_flags

    def test_inc_flag(self) -> None:
        """inc_flag action 累加 flag 值。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="flag_set"),
            actions=[EventAction(type="inc_flag", flag="visits", value=2)],
        )
        state = AdventureState(script_id="test", story_flags={"visits": 3})
        new_state, _ = execute_event(state, ev)
        assert new_state.story_flags["visits"] == 5

    def test_inc_flag_from_zero(self) -> None:
        """inc_flag — flag 不存在時從 0 開始。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="flag_set"),
            actions=[EventAction(type="inc_flag", flag="visits", value=1)],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev)
        assert new_state.story_flags["visits"] == 1

    def test_start_timer(self) -> None:
        """start_timer action 記錄當前 elapsed_minutes。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[EventAction(type="start_timer", flag="sliding")],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev, elapsed_minutes=42)
        assert new_state.timed_flags["sliding"] == 42

    def test_clear_timer(self) -> None:
        """clear_timer action 移除計時 flag。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[EventAction(type="clear_timer", flag="sliding")],
        )
        state = AdventureState(script_id="test", timed_flags={"sliding": 10})
        new_state, _ = execute_event(state, ev)
        assert "sliding" not in new_state.timed_flags

    def test_clear_timer_missing(self) -> None:
        """clear_timer — flag 不存在也不報錯。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[EventAction(type="clear_timer", flag="nonexistent")],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev)
        assert "nonexistent" not in new_state.timed_flags

    def test_move_npc(self) -> None:
        """move_npc action 更新 NPC 位置。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="flag_set"),
            actions=[EventAction(type="move_npc", npc_id="quinn", node_id="tavern")],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev)
        assert new_state.npc_locations["quinn"] == "tavern"

    def test_once_event_marked_fired(self) -> None:
        """once=True 事件執行後記錄到 fired_events。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            once=True,
            actions=[],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev)
        assert "ev1" in new_state.fired_events

    def test_once_false_not_marked(self) -> None:
        """once=False 事件不記錄到 fired_events。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            once=False,
            actions=[],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev)
        assert "ev1" not in new_state.fired_events

    def test_actions_returned_in_order(self) -> None:
        """回傳的 action 列表保持原始順序。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[
                EventAction(type="narrate", text="旁白 A"),
                EventAction(type="set_flag", flag="a"),
                EventAction(type="narrate", text="旁白 B"),
            ],
        )
        state = AdventureState(script_id="test")
        _, actions = execute_event(state, ev)
        assert len(actions) == 3
        assert actions[0].text == "旁白 A"
        assert actions[1].flag == "a"
        assert actions[2].text == "旁白 B"

    def test_multiple_actions_compound(self) -> None:
        """多個 action 依序作用於同一 state。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[
                EventAction(type="set_flag", flag="found_dragon"),
                EventAction(type="inc_flag", flag="discoveries", value=1),
                EventAction(type="move_npc", npc_id="quinn", node_id="lair"),
                EventAction(type="start_timer", flag="dragon_encounter"),
            ],
        )
        state = AdventureState(script_id="test")
        new_state, _ = execute_event(state, ev, elapsed_minutes=30)
        assert new_state.story_flags["found_dragon"] == 1
        assert new_state.story_flags["discoveries"] == 1
        assert new_state.npc_locations["quinn"] == "lair"
        assert new_state.timed_flags["dragon_encounter"] == 30

    def test_narrate_action_passthrough(self) -> None:
        """narrate action 不改 state，但出現在回傳列表中。"""
        ev = ScriptEvent(
            id="ev1",
            trigger=EventTrigger(type="enter_node"),
            actions=[EventAction(type="narrate", text="你聽到遠處的吼聲。")],
        )
        state = AdventureState(script_id="test")
        new_state, actions = execute_event(state, ev)
        assert new_state.story_flags == {}
        assert len(actions) == 1
        assert actions[0].type == "narrate"


# ══════════════════════════════════════════════════════════
# Stage C: 對話引擎
# ══════════════════════════════════════════════════════════


def _quinn_npc() -> NpcDef:
    """測試用 NPC：乖僻的乖因，有條件分支對話。"""
    return NpcDef(
        id="quinn",
        name="乖僻的乖因",
        node_id="village",
        dialogue=[
            # 頂層入口
            DialogueLine(id="q_greet", speaker="quinn", text="嗨，你好！"),
            DialogueLine(
                id="q_greet_after",
                speaker="quinn",
                text="又是你啊。",
                condition="has:talked_to_quinn",
            ),
            # q_greet 的後續
            DialogueLine(
                id="q_ask_quest",
                speaker="dm",
                text="「我能幫什麼忙嗎？」",
                choice_label="問任務",
                sets_flag="asked_quest",
            ),
            DialogueLine(
                id="q_say_bye",
                speaker="dm",
                text="「再見。」",
                choice_label="離開",
                sets_flag="talked_to_quinn",
            ),
            # q_ask_quest 的後續
            DialogueLine(
                id="q_quest_detail",
                speaker="quinn",
                text="村外的巡邏路線最近不太安全……",
                sets_flag="quest_started",
            ),
        ],
    )


@pytest.fixture
def quinn() -> NpcDef:
    return _quinn_npc()


@pytest.fixture
def quinn_script() -> AdventureScript:
    npc = _quinn_npc()
    # 把對話鏈接起來
    npc.dialogue[0].next_lines = ["q_ask_quest", "q_say_bye"]  # q_greet →
    npc.dialogue[2].next_lines = ["q_quest_detail"]  # q_ask_quest → q_quest_detail
    return AdventureScript(
        id="test_script",
        name="測試劇本",
        npcs={"quinn": npc},
    )


# ── get_available_npcs ────────────────────────────────────


class TestGetAvailableNpcs:
    """get_available_npcs() — 取得節點上的 NPC。"""

    def test_npc_at_node(self, quinn_script: AdventureScript) -> None:
        state = AdventureState(script_id="test_script")
        npcs = get_available_npcs(quinn_script, state, "village")
        assert len(npcs) == 1
        assert npcs[0].id == "quinn"

    def test_npc_not_at_node(self, quinn_script: AdventureScript) -> None:
        state = AdventureState(script_id="test_script")
        npcs = get_available_npcs(quinn_script, state, "cave")
        assert npcs == []

    def test_dynamic_location_overrides(self, quinn_script: AdventureScript) -> None:
        """state.npc_locations 覆蓋 NpcDef.node_id。"""
        state = AdventureState(
            script_id="test_script",
            npc_locations={"quinn": "tavern"},
        )
        # 不再出現在 village
        assert get_available_npcs(quinn_script, state, "village") == []
        # 出現在 tavern
        npcs = get_available_npcs(quinn_script, state, "tavern")
        assert len(npcs) == 1


# ── get_available_lines ───────────────────────────────────


class TestGetAvailableLines:
    """get_available_lines() — 取得可用對話行。"""

    def test_top_level_lines(self, quinn_script: AdventureScript) -> None:
        """無 active_dialogue → 回傳頂層對話。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        lines = get_available_lines(npc, state)
        # q_greet 可用（無條件），q_greet_after 不可用（需 has:talked_to_quinn）
        assert len(lines) == 1
        assert lines[0].id == "q_greet"

    def test_top_level_with_flag(self, quinn_script: AdventureScript) -> None:
        """flag 滿足後顯示更多頂層對話。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(
            script_id="test_script",
            story_flags={"talked_to_quinn": 1},
        )
        lines = get_available_lines(npc, state)
        ids = {dl.id for dl in lines}
        assert "q_greet" in ids
        assert "q_greet_after" in ids

    def test_active_dialogue_next_lines(self, quinn_script: AdventureScript) -> None:
        """有 active_dialogue → 只回傳該行的 next_lines。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(
            script_id="test_script",
            active_dialogue="q_greet",
        )
        lines = get_available_lines(npc, state)
        ids = [dl.id for dl in lines]
        assert ids == ["q_ask_quest", "q_say_bye"]

    def test_next_lines_with_condition(self, quinn_script: AdventureScript) -> None:
        """next_lines 中不符合條件的被過濾。"""
        npc = quinn_script.npcs["quinn"]
        # 加一個有條件的 next_line
        npc.dialogue[0].next_lines.append("q_greet_after")
        state = AdventureState(
            script_id="test_script",
            active_dialogue="q_greet",
        )
        lines = get_available_lines(npc, state)
        ids = [dl.id for dl in lines]
        # q_greet_after 需要 has:talked_to_quinn，不符合
        assert "q_greet_after" not in ids


# ── advance_dialogue ──────────────────────────────────────


class TestAdvanceDialogue:
    """advance_dialogue() — 推進對話。"""

    def test_choose_line_sets_flag(self, quinn_script: AdventureScript) -> None:
        """選擇有 sets_flag 的對話行 → flag 被設定。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        new_state, chosen, _ = advance_dialogue(state, npc, "q_say_bye")
        assert chosen.id == "q_say_bye"
        assert new_state.story_flags.get("talked_to_quinn") == 1

    def test_choose_line_records_history(self, quinn_script: AdventureScript) -> None:
        """對話行記錄到 dialogue_history。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        new_state, _, _ = advance_dialogue(state, npc, "q_greet")
        assert "q_greet" in new_state.dialogue_history

    def test_history_no_duplicates(self, quinn_script: AdventureScript) -> None:
        """同一行不重複記錄。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(
            script_id="test_script",
            dialogue_history=["q_greet"],
        )
        new_state, _, _ = advance_dialogue(state, npc, "q_greet")
        assert new_state.dialogue_history.count("q_greet") == 1

    def test_next_lines_returned(self, quinn_script: AdventureScript) -> None:
        """有 next_lines → 回傳後續可選行。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        new_state, _, next_lines = advance_dialogue(state, npc, "q_greet")
        ids = [dl.id for dl in next_lines]
        assert ids == ["q_ask_quest", "q_say_bye"]
        assert new_state.active_dialogue == "q_greet"

    def test_no_next_lines_ends_dialogue(self, quinn_script: AdventureScript) -> None:
        """無 next_lines → active_dialogue 清空。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        new_state, _, next_lines = advance_dialogue(state, npc, "q_say_bye")
        assert next_lines == []
        assert new_state.active_dialogue is None

    def test_chain_dialogue(self, quinn_script: AdventureScript) -> None:
        """完整對話鏈：greet → ask_quest → quest_detail（結束）。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")

        # 第一步：打招呼
        s1, line1, next1 = advance_dialogue(state, npc, "q_greet")
        assert line1.text == "嗨，你好！"
        assert [dl.id for dl in next1] == ["q_ask_quest", "q_say_bye"]

        # 第二步：問任務
        s2, line2, next2 = advance_dialogue(s1, npc, "q_ask_quest")
        assert line2.choice_label == "問任務"
        assert s2.story_flags.get("asked_quest") == 1
        assert [dl.id for dl in next2] == ["q_quest_detail"]

        # 第三步：聽任務詳情（結束）
        s3, line3, next3 = advance_dialogue(s2, npc, "q_quest_detail")
        assert "不太安全" in line3.text
        assert s3.story_flags.get("quest_started") == 1
        assert next3 == []
        assert s3.active_dialogue is None

    def test_original_state_unchanged(self, quinn_script: AdventureScript) -> None:
        """advance_dialogue 不改原 state。"""
        npc = quinn_script.npcs["quinn"]
        state = AdventureState(script_id="test_script")
        advance_dialogue(state, npc, "q_say_bye")
        assert "talked_to_quinn" not in state.story_flags
        assert state.dialogue_history == []


# ══════════════════════════════════════════════════════════
# Stage D: 冒險載入器
# ══════════════════════════════════════════════════════════


class TestLoadAdventure:
    """load_adventure() — 從 JSON 載入劇本。"""

    def test_load_by_filename(self) -> None:
        """用檔名載入（自動在 data/adventures/ 查找）。"""
        script = load_adventure("test_adventure")
        assert script.id == "test_adventure"
        assert script.name == "測試冒險"
        assert "guard" in script.npcs
        assert len(script.events) == 2

    def test_load_by_filename_with_json(self) -> None:
        """用 .json 後綴載入。"""
        script = load_adventure("test_adventure.json")
        assert script.id == "test_adventure"

    def test_npcs_loaded_correctly(self) -> None:
        """NPC 和對話正確載入。"""
        script = load_adventure("test_adventure")
        guard = script.npcs["guard"]
        assert guard.name == "守衛"
        assert guard.node_id == "gate"
        assert len(guard.dialogue) == 3
        # 檢查對話鏈
        greet = guard.dialogue[0]
        assert greet.next_lines == ["g_answer_friend", "g_answer_stranger"]

    def test_events_loaded_correctly(self) -> None:
        """事件和條件正確載入。"""
        script = load_adventure("test_adventure")
        ev = next(e for e in script.events if e.id == "guard_lets_pass")
        assert ev.condition == "has:visited_gate"
        assert ev.trigger.type == "flag_set"
        assert ev.trigger.flag == "guard_friendly"

    def test_initial_flags_loaded(self) -> None:
        """initial_flags 正確載入。"""
        script = load_adventure("test_adventure")
        assert script.initial_flags == {"tutorial_mode": 1}

    def test_load_nonexistent_raises(self) -> None:
        """載入不存在的檔案應拋出例外。"""
        with pytest.raises(FileNotFoundError):
            load_adventure("nonexistent_adventure_xyz")


class TestInitAdventureState:
    """init_adventure_state() — 建立初始狀態。"""

    def test_initial_flags_applied(self) -> None:
        """initial_flags 複製到 story_flags。"""
        script = load_adventure("test_adventure")
        state = init_adventure_state(script)
        assert state.story_flags == {"tutorial_mode": 1}

    def test_npc_locations_initialized(self) -> None:
        """NPC 初始位置從 NpcDef.node_id 複製。"""
        script = load_adventure("test_adventure")
        state = init_adventure_state(script)
        assert state.npc_locations == {"guard": "gate"}

    def test_script_id_matches(self) -> None:
        script = load_adventure("test_adventure")
        state = init_adventure_state(script)
        assert state.script_id == "test_adventure"

    def test_empty_collections(self) -> None:
        """其他集合初始為空。"""
        script = load_adventure("test_adventure")
        state = init_adventure_state(script)
        assert state.fired_events == set()
        assert state.timed_flags == {}
        assert state.active_dialogue is None
        assert state.dialogue_history == []

    def test_initial_flags_independent(self) -> None:
        """修改 state.story_flags 不影響 script.initial_flags。"""
        script = load_adventure("test_adventure")
        state = init_adventure_state(script)
        state.story_flags["extra"] = 1
        assert "extra" not in script.initial_flags
