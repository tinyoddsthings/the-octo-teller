"""T.O.T. 角色建造 TUI — 動態步驟 Wizard 介面（2024 PHB 流程）。

步驟由 StepType + session.get_steps() 動態決定，依職業自動插入/跳過。
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    SelectionList,
    Static,
)

from tot.data.classes import CLASS_DISPLAY, INVOCATION_REGISTRY
from tot.data.feats import ORIGIN_FEAT_REGISTRY
from tot.data.origins import (
    ABILITY_ZH,
    BACKGROUND_REGISTRY,
    SKILL_ZH,
    SPECIES_REGISTRY,
    TOOL_DATA,
    TOOL_ZH,
)
from tot.gremlins.bone_engine.character import (
    CLASS_REGISTRY,
    POINT_BUY_BUDGET,
    POINT_BUY_COSTS,
)
from tot.gremlins.bone_engine.character_session import (
    CharacterCreationData,
    CharacterCreationSession,
    StepType,
)
from tot.models.creature import Character
from tot.models.enums import Ability, Skill

# ── 常數 ──────────────────────────────────────────────────────────────────────

ABILITY_ORDER: list[Ability] = [
    Ability.STR,
    Ability.DEX,
    Ability.CON,
    Ability.INT,
    Ability.WIS,
    Ability.CHA,
]


# ── 主 App ────────────────────────────────────────────────────────────────────


class CharacterCreationApp(App[Character | None]):
    """T.O.T. 角色建造 Wizard（2024 PHB 流程）。"""

    TITLE = "T.O.T. 角色建造"

    CSS = """
    Screen { layout: vertical; }

    #main-area { height: 1fr; }

    #left-panel {
        width: 2fr;
        border: solid $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    #preview-panel {
        width: 3fr;
        border: solid $primary;
        padding: 1 2;
        overflow-y: auto;
    }

    #step-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    .section-label {
        color: $text-muted;
        margin-top: 1;
        text-style: italic;
    }

    .ability-row { height: 3; }
    .ability-label { width: 16; height: 3; padding-top: 1; }

    #next-btn, #confirm-btn { margin-top: 1; width: 100%; }

    RadioSet { height: auto; }
    SelectionList { height: auto; max-height: 20; }
    Select { width: 20; }
    """

    BINDINGS = [
        Binding("escape", "prev_step", "上一步"),
        Binding("ctrl+n", "next_step", "確認→下一步"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._step_index: int = 0
        self.session = CharacterCreationSession()
        # 多選上限追蹤：{widget_id: [value_order]}
        self._selection_order: dict[str, list] = {}

    # ── Step helpers ───────────────────────────────────────────────────────

    @property
    def _current_step(self) -> StepType:
        steps = self.session.get_steps()
        return steps[self._step_index]

    @property
    def _total_steps(self) -> int:
        return len(self.session.get_steps())

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            yield Vertical(id="left-panel")
            yield Static("", id="preview-panel")
        yield Footer()

    async def on_mount(self) -> None:
        await self._render_step()
        self._update_preview()
        self._update_title()

    # ── Title ─────────────────────────────────────────────────────────────────

    def _update_title(self) -> None:
        step = self._current_step
        idx = self._step_index + 1
        total = self._total_steps
        title = self.session.get_step_title(step)
        self.title = f"T.O.T. 角色建造  ─  步驟 {idx}/{total}：{title}"

    # ── Step rendering ────────────────────────────────────────────────────────

    async def _render_step(self) -> None:
        """清除左側面板，重建當步 widgets。"""
        left = self.query_one("#left-panel", Vertical)
        await left.remove_children()

        step = self._current_step
        idx = self._step_index + 1
        total = self._total_steps
        title = self.session.get_step_title(step)
        widgets: list = []
        widgets.append(Label(f"步驟 {idx}/{total}：{title}", id="step-title"))

        render_fn = {
            StepType.CLASS: self._widgets_class,
            StepType.BACKGROUND: self._widgets_background,
            StepType.SPECIES: self._widgets_species,
            StepType.ABILITY_SCORES: self._widgets_ability_scores,
            StepType.SKILLS: self._widgets_skills,
            StepType.INVOCATIONS: self._widgets_invocations,
            StepType.SPELLS: self._widgets_spells,
            StepType.EQUIPMENT: self._widgets_equipment,
            StepType.CONFIRM: self._widgets_confirm,
            # 未實作的步驟用 placeholder
            StepType.DIVINE_ORDER: self._widgets_placeholder,
            StepType.PRIMAL_ORDER: self._widgets_placeholder,
            StepType.FIGHTING_STYLE: self._widgets_placeholder,
            StepType.WEAPON_MASTERY: self._widgets_placeholder,
            StepType.EXPERTISE: self._widgets_placeholder,
            StepType.LANGUAGE: self._widgets_placeholder,
        }.get(step)

        if render_fn:
            render_fn(widgets)

        # 最後一步用確認按鈕，其餘用下一步按鈕
        if step == StepType.CONFIRM:
            widgets.append(Button("確認建角", id="confirm-btn", variant="success"))
        else:
            widgets.append(Button("確認 →  (Ctrl+N)", id="next-btn", variant="primary"))

        await left.mount(*widgets)

    def _widgets_placeholder(self, w: list) -> None:
        """未實作步驟的佔位。"""
        w.append(Label("此步驟尚未實作，請按 Ctrl+N 跳過。"))

    # ── Step 1: 職業 ──────────────────────────────────────────────────────────

    def _widgets_class(self, w: list) -> None:
        cc = self.session.data.char_class
        btns = []
        for cid, cd in CLASS_DISPLAY.items():
            label = f"{cd.name_zh}（{cd.name_en}）— {cd.description[:20]}…"
            btns.append(RadioButton(label, value=(cid == cc)))
        w.append(RadioSet(*btns, id="class-radio"))

    # ── Step 2: 背景 ──────────────────────────────────────────────────────────

    def _widgets_background(self, w: list) -> None:
        bg = self.session.data.background
        btns = []
        for bid, bd in BACKGROUND_REGISTRY.items():
            label = f"{bd.name_zh}（{bd.name_en}）"
            btns.append(RadioButton(label, value=(bid == bg)))
        w.append(RadioSet(*btns, id="bg-radio"))

        # 若背景有「任選一種」工具，顯示工具選擇
        bg_id = self.session.data.background
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg_data = BACKGROUND_REGISTRY[bg_id]
            if bg_data.tool_proficiency_category:
                w.append(Label(f"── {bg_data.tool_proficiency_label} ──", classes="section-label"))
                available_tools = self.session.get_available_bg_tools()
                cur_tool = self.session.data.bg_tool_choice
                tool_btns = []
                for t in available_tools:
                    info = TOOL_DATA.get(t)
                    desc = f"（{info.ability}）{info.utilize}" if info else ""
                    craft = f"｜製作：{info.craft}" if info and info.craft else ""
                    label = f"{TOOL_ZH.get(t, t.value)} — {desc}{craft}"
                    tool_btns.append(RadioButton(label, value=(t == cur_tool)))
                w.append(RadioSet(*tool_btns, id="bg-tool-radio"))

    # ── Step 3: 種族 ──────────────────────────────────────────────────────────

    def _widgets_species(self, w: list) -> None:
        sp = self.session.data.species
        btns = []
        for sid, sd in SPECIES_REGISTRY.items():
            label = f"{sd.name_zh}（{sd.name_en}）— {sd.description}"
            btns.append(RadioButton(label, value=(sid == sp)))
        w.append(RadioSet(*btns, id="species-radio"))

        # 若已選種族且有血統子選項，顯示
        if sp and sp in SPECIES_REGISTRY:
            sd = SPECIES_REGISTRY[sp]
            if sd.lineage_options:
                w.append(Label("── 選擇血統/先祖 ──", classes="section-label"))
                cur_lin = self.session.data.lineage
                lin_btns = []
                for lo in sd.lineage_options:
                    lb = f"{lo.name_zh}（{lo.name_en}）— {lo.description}"
                    lin_btns.append(RadioButton(lb, value=(lo.id == cur_lin)))
                w.append(RadioSet(*lin_btns, id="lineage-radio"))

            # 血統法術施法屬性選擇（Tiefling 等）
            if sd.has_lineage_spellcasting_choice:
                w.append(
                    Label(
                        "── 血統法術施法屬性（選擇後永久綁定）──",
                        classes="section-label",
                    )
                )
                cur_sa = self.session.data.species_spellcasting_ability
                sa_btns = [
                    RadioButton(
                        f"{ABILITY_ZH[Ability.INT]}（INT）— 適合法師",
                        value=(cur_sa == Ability.INT),
                    ),
                    RadioButton(
                        f"{ABILITY_ZH[Ability.WIS]}（WIS）— 適合牧師、德魯伊、遊俠",
                        value=(cur_sa == Ability.WIS),
                    ),
                    RadioButton(
                        f"{ABILITY_ZH[Ability.CHA]}（CHA）— 適合術士、契術師、吟遊詩人",
                        value=(cur_sa == Ability.CHA),
                    ),
                ]
                w.append(RadioSet(*sa_btns, id="species-sa-radio"))

            # 多藝：選起源專長（Human）
            if sd.feat_choice_count > 0:
                w.append(Label("── 多藝：選擇起源專長 ──", classes="section-label"))
                cur_feat = self.session.data.species_feat
                feat_btns = []
                for fid, fd in ORIGIN_FEAT_REGISTRY.items():
                    label = f"{fd.name_zh}（{fd.name_en}）— {fd.description[:50]}"
                    feat_btns.append(RadioButton(label, value=(fid == cur_feat)))
                w.append(RadioSet(*feat_btns, id="species-feat-radio"))

    # ── Step 4: 屬性值 ────────────────────────────────────────────────────────

    def _widgets_ability_scores(self, w: list) -> None:
        d = self.session.data
        method = d.score_method

        # 方法選擇
        w.append(Label("── 屬性值生成方式 ──", classes="section-label"))
        method_btns = [
            RadioButton("標準陣列（15, 14, 13, 12, 10, 8）", value=(method == "standard")),
            RadioButton("點數購買（27 點預算，8~15）", value=(method == "point_buy")),
            RadioButton("擲骰（4d6 取高 3，共 6 組）", value=(method == "roll")),
        ]
        w.append(RadioSet(*method_btns, id="method-radio"))

        if method == "standard":
            self._widgets_standard_array(w)
        elif method == "point_buy":
            self._widgets_point_buy(w)
        elif method == "roll":
            self._widgets_roll(w)

        # 背景屬性調整
        bg_id = d.background
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            tags = [ABILITY_ZH[a] for a in bg.ability_tags]
            w.append(
                Label(
                    f"── 背景屬性調整（{bg.name_zh}：{'/'.join(tags)}）──", classes="section-label"
                )
            )
            adj_mode = d.bg_adjust_mode
            adj_btns = [
                RadioButton("三項各 +1（預設）", value=(adj_mode == "+1/+1/+1")),
                RadioButton("一項 +2，一項 +1", value=(adj_mode == "+2/+1")),
            ]
            w.append(RadioSet(*adj_btns, id="adjust-mode-radio"))

            if adj_mode == "+2/+1":
                w.append(Label("  +2 給："))
                opts_2 = [(ABILITY_ZH[a], a) for a in bg.ability_tags]
                cur_adj = d.bg_adjust
                plus2_ab = next((a for a, v in cur_adj.items() if v == 2), None)
                plus2_sel = Select(opts_2, allow_blank=True, id="adj-plus2")
                if plus2_ab is not None:
                    plus2_sel.value = plus2_ab
                w.append(plus2_sel)
                w.append(Label("  +1 給："))
                plus1_ab = next((a for a, v in cur_adj.items() if v == 1), None)
                plus1_sel = Select(opts_2, allow_blank=True, id="adj-plus1")
                if plus1_ab is not None:
                    plus1_sel.value = plus1_ab
                w.append(plus1_sel)

    def _widgets_standard_array(self, w: list) -> None:
        w.append(Label("── 標準陣列（依職業建議自動分配）──", classes="section-label"))
        # 讓 session 設定 standard 並自動分配
        self.session.set_ability_method("standard")
        for ab in ABILITY_ORDER:
            w.append(Label(self.session.format_score_line(ab)))

    def _widgets_point_buy(self, w: list) -> None:
        d = self.session.data
        w.append(Label("── 點數購買（8~15，改動時右下角顯示剩餘）──", classes="section-label"))
        cost_str = "  花費：" + ", ".join(f"{v}={c}點" for v, c in POINT_BUY_COSTS.items())
        w.append(Label(cost_str))

        pb_opts = [(str(v), v) for v in range(8, 16)]
        for ab in ABILITY_ORDER:
            cur = d.scores.get(ab, 8)
            w.append(Label(f"  {ab.value} {ABILITY_ZH[ab]}", classes="ability-label"))
            w.append(Select(pb_opts, value=cur, id=f"pb-{ab.value}"))

    def _widgets_roll(self, w: list) -> None:
        rolled = self.session.data.rolled_values
        if not rolled:
            w.append(Label("  按「確認→下一步」後自動擲骰並分配"))
        else:
            w.append(
                Label(
                    f"── 擲骰結果：{sorted(rolled, reverse=True)}（依職業最優分配）──",
                    classes="section-label",
                )
            )
            # session 已分配好 scores
            for ab in ABILITY_ORDER:
                w.append(Label(self.session.format_score_line(ab)))
            w.append(Button("重新擲骰", id="reroll-btn", variant="warning"))

    # ── Step 5: 技能 ──────────────────────────────────────────────────────────

    def _widgets_skills(self, w: list) -> None:
        d = self.session.data
        bg_id = d.background
        cc = d.char_class

        # 背景固定技能（顯示，不可改）
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            bg_labels = [f"{SKILL_ZH[s]}（{s.value}）" for s in bg.skill_proficiencies]
            w.append(Label(f"── 背景技能（{bg.name_zh}，已固定）──", classes="section-label"))
            w.append(Label(f"  {', '.join(bg_labels)}"))

        # 從 session 取可選技能和選位數
        available = self.session.get_available_skills()
        total_picks = self.session.get_total_skill_picks()
        feat = self.session.get_origin_feat()
        feat_count = feat.skill_choice_count if feat and feat.skill_choice_count > 0 else 0

        if total_picks > 0:
            # 來源說明
            sources = []
            if feat_count > 0:
                sources.append(feat.name_zh)
            if cc and cc in CLASS_REGISTRY:
                cd = CLASS_DISPLAY.get(cc)
                sources.append(cd.name_zh if cd else cc)
            source_text = "與".join(sources)

            w.append(
                Label(
                    f"── 依{source_text}，選擇 {total_picks} 項技能熟練 ──",
                    classes="section-label",
                )
            )

            selected = d.skills
            options = []
            for s in available:
                ab = _skill_ability(s)
                label = f"{SKILL_ZH.get(s, s.value)}（{s.value}）— {ABILITY_ZH.get(ab, '')}"
                options.append((label, s, s in selected))
            w.append(SelectionList(*options, id="skills-list"))

    # ── Step 6: 裝備 ──────────────────────────────────────────────────────────

    def _widgets_equipment(self, w: list) -> None:
        d = self.session.data
        bg_id = d.background
        cc = d.char_class

        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            w.append(Label(f"── 背景裝備（{bg.name_zh}）──", classes="section-label"))
            w.append(Label(f"  A：{bg.equipment_a}"))
            w.append(Label(f"  B：{bg.equipment_b}"))
            cur_bg = d.bg_equipment or "A"
            btns = [
                RadioButton("選 A", value=(cur_bg == "A")),
                RadioButton("選 B", value=(cur_bg == "B")),
            ]
            w.append(RadioSet(*btns, id="bg-equip-radio"))

        if cc and cc in CLASS_DISPLAY:
            cd = CLASS_DISPLAY[cc]
            w.append(Label(f"── 職業裝備（{cd.name_zh}）──", classes="section-label"))
            w.append(Label(f"  A：{cd.equipment_a}"))
            w.append(Label(f"  B：{cd.equipment_b}"))
            cur_cls = d.class_equipment or "A"
            btns = [
                RadioButton("選 A", value=(cur_cls == "A")),
                RadioButton("選 B", value=(cur_cls == "B")),
            ]
            w.append(RadioSet(*btns, id="cls-equip-radio"))

    # ── Step: 魔能祈喚（Warlock 獨立步驟）──────────────────────────────────────

    def _widgets_invocations(self, w: list) -> None:
        d = self.session.data
        cc = d.char_class
        cd = CLASS_DISPLAY.get(cc)
        if not cd or cd.num_invocations == 0:
            w.append(Label("此職業沒有魔能祈喚。"))
            return

        num_inv = cd.num_invocations
        available_inv = self.session.get_available_invocations()
        w.append(
            Label(
                f"── 魔能祈喚（選 {num_inv} 項）──",
                classes="section-label",
            )
        )
        if available_inv:
            sel = d.invocations
            opts = []
            for inv in available_inv:
                opts.append(
                    (
                        f"{inv.name_zh}（{inv.name_en}）",
                        inv.id,
                        inv.id in sel,
                    )
                )
            w.append(SelectionList(*opts, id="invocation-list"))
            # 顯示各祈喚的完整描述
            for inv in available_inv:
                marker = "▶ " if inv.id in sel else "  "
                w.append(Static(f"{marker}{inv.name_zh}：{inv.description}"))

    # ── Step: 戲法與法術 ─────────────────────────────────────────────────────

    def _widgets_spells(self, w: list) -> None:
        d = self.session.data
        cc = d.char_class
        if not cc:
            w.append(Label("請先選擇職業"))
            return

        cd = CLASS_DISPLAY.get(cc)
        has_class_spells = cd and (cd.num_cantrips > 0 or cd.num_prepared_spells > 0)
        has_feat_spells = self.session.has_feat_spell_choices()

        if not has_class_spells and not has_feat_spells:
            w.append(Label(f"{cd.name_zh if cd else cc} 在 1 級沒有施法能力。"))
            return

        # ── 種族/血統已有的戲法（不可重複選）──
        granted = self.session.get_species_granted_cantrips()
        if granted:
            from tot.gremlins.bone_engine.spells import load_spell_db

            db = load_spell_db()
            names = []
            for en in granted:
                sp = db.get(en) or next((s for s in db.values() if s.en_name == en), None)
                names.append(sp.name if sp else en)
            w.append(
                Label(
                    f"── 種族戲法（已有，不可重複選）：{', '.join(names)} ──",
                    classes="section-label",
                )
            )

        # ── 專長法術（Magic Initiate）──────────────────────────────
        if has_feat_spells:
            self._widgets_feat_spells(w, d)

        # ── 職業戲法 ──────────────────────────────────────────────
        if cd and cd.num_cantrips > 0:
            cantrips = self.session.get_available_cantrips()
            w.append(
                Label(
                    f"── 職業戲法（選 {cd.num_cantrips} 個）──",
                    classes="section-label",
                )
            )
            if cantrips:
                sel = d.cantrips
                opts = []
                for s in cantrips:
                    tag = s["damage_type_zh"] if s["damage_type_zh"] else s["effect_type_zh"]
                    opts.append(
                        (
                            f"{s['name']}（{s['en_name']}）— {tag}",
                            s["en_name"],
                            s["en_name"] in sel,
                        )
                    )
                w.append(SelectionList(*opts, id="cantrip-list"))
            else:
                w.append(Label("  （法術資料庫尚無此職業的戲法）"))

        # ── 職業 1 環法術 ────────────────────────────────────────
        if cd and cd.num_prepared_spells > 0:
            spells_1 = self.session.get_available_spells()
            w.append(
                Label(
                    f"── 職業 1 環法術（選 {cd.num_prepared_spells} 個）──",
                    classes="section-label",
                )
            )
            if spells_1:
                sel = d.spells
                opts = []
                for s in spells_1:
                    tag = s["damage_type_zh"] if s["damage_type_zh"] else s["effect_type_zh"]
                    opts.append(
                        (
                            f"{s['name']}（{s['en_name']}）— {tag}",
                            s["en_name"],
                            s["en_name"] in sel,
                        )
                    )
                w.append(SelectionList(*opts, id="spell-list"))
            else:
                w.append(Label("  （法術資料庫尚無此職業的 1 環法術）"))

        # 已選法術詳情預覽
        self._render_spell_details(w, d)

    def _widgets_feat_spells(self, w: list, d: CharacterCreationData) -> None:
        """渲染 Magic Initiate 專長的法術選擇區塊。"""
        spell_feat = self.session._get_spell_feat()
        if not spell_feat:
            return

        w.append(Label(f"── {spell_feat.name_zh} ──", classes="section-label"))

        # 施法屬性選擇（INT/WIS/CHA）
        if spell_feat.spellcasting_ability_choice:
            w.append(Label("  施法屬性："))
            cur_ab = d.feat_spellcasting_ability
            ab_btns = [
                RadioButton("智力（INT）", value=(cur_ab == Ability.INT)),
                RadioButton("感知（WIS）", value=(cur_ab == Ability.WIS)),
                RadioButton("魅力（CHA）", value=(cur_ab == Ability.CHA)),
            ]
            w.append(RadioSet(*ab_btns, id="feat-ability-radio"))

        # 專長戲法
        if spell_feat.num_feat_cantrips > 0:
            feat_cantrips = self.session.get_available_feat_cantrips()
            w.append(
                Label(
                    f"── 專長戲法（選 {spell_feat.num_feat_cantrips} 個）──",
                    classes="section-label",
                )
            )
            if feat_cantrips:
                sel = d.feat_cantrips
                opts = []
                for s in feat_cantrips:
                    tag = s["damage_type_zh"] if s["damage_type_zh"] else s["effect_type_zh"]
                    opts.append(
                        (
                            f"{s['name']}（{s['en_name']}）— {tag}",
                            s["en_name"],
                            s["en_name"] in sel,
                        )
                    )
                w.append(SelectionList(*opts, id="feat-cantrip-list"))
            else:
                w.append(Label(f"  （法術資料庫尚無{spell_feat.spell_class}的戲法）"))

        # 專長 1 環法術
        if spell_feat.num_feat_spells > 0:
            feat_spells_1 = self.session.get_available_feat_spells()
            w.append(
                Label(
                    f"── 專長 1 環法術（選 {spell_feat.num_feat_spells} 個）──",
                    classes="section-label",
                )
            )
            if feat_spells_1:
                sel = d.feat_spells
                opts = []
                for s in feat_spells_1:
                    tag = s["damage_type_zh"] if s["damage_type_zh"] else s["effect_type_zh"]
                    opts.append(
                        (
                            f"{s['name']}（{s['en_name']}）— {tag}",
                            s["en_name"],
                            s["en_name"] in sel,
                        )
                    )
                w.append(SelectionList(*opts, id="feat-spell-list"))
            else:
                w.append(Label(f"  （法術資料庫尚無{spell_feat.spell_class}的 1 環法術）"))

    def _render_spell_details(self, w: list, d: CharacterCreationData) -> None:
        """渲染已選法術的詳細資訊。"""
        all_cantrips = {s["en_name"]: s for s in self.session.get_available_cantrips()}
        all_spells = {s["en_name"]: s for s in self.session.get_available_spells()}
        # 也加入專長法術的查找表
        for s in self.session.get_available_feat_cantrips():
            all_cantrips.setdefault(s["en_name"], s)
        for s in self.session.get_available_feat_spells():
            all_spells.setdefault(s["en_name"], s)
        selected = list(d.feat_cantrips) + list(d.feat_spells) + list(d.cantrips) + list(d.spells)
        if not selected:
            return
        w.append(Label("── 已選法術詳情 ──", classes="section-label"))
        for en in selected:
            sd = all_cantrips.get(en) or all_spells.get(en)
            if not sd:
                continue
            dt = sd.get("damage_type_zh", "")
            et = sd.get("effect_type_zh", "")
            tag = dt if dt else et
            lv = "戲法" if sd["level"] == 0 else f"{sd['level']} 環"
            w.append(Label(f"  ◆ {sd['name']}（{lv}・{sd['school']}・{tag}）"))
            # 用 Static 顯示長文字，自動換行
            w.append(Static(f"    {sd.get('description', '')}"))

    # ── Step: 名稱＋確認 ──────────────────────────────────────────────────────

    def _widgets_confirm(self, w: list) -> None:
        d = self.session.data
        w.append(Label("── 角色名稱 ──", classes="section-label"))
        w.append(
            Input(
                value=d.name,
                placeholder="輸入角色名稱...",
                id="name-input",
            )
        )

        # 完整角色卡預覽
        w.append(Label("── 角色卡預覽 ──", classes="section-label"))
        try:
            ok, msg = self.session.validate()
            if ok:
                char = self.session.build_character()
                summary = self._format_confirm_summary(char)
                w.append(Static(summary))
            else:
                w.append(Static(f"[yellow]{msg}[/yellow]"))
        except Exception as e:
            w.append(Static(f"[red]建角錯誤：{e}[/red]"))

    def _format_confirm_summary(self, char: Character) -> str:
        """格式化確認頁的角色卡摘要（含計算後數值）。"""
        d = self.session.data
        cc = d.char_class
        bg_id = d.background
        sp_id = d.species

        cd = CLASS_DISPLAY.get(cc)
        bg = BACKGROUND_REGISTRY.get(bg_id) if bg_id else None
        sd = SPECIES_REGISTRY.get(sp_id) if sp_id else None

        lines = [
            f"角色名稱：{char.name}",
            f"職業：{cd.name_zh if cd else cc}　等級：{char.level}",
            f"背景：{bg.name_zh if bg else bg_id}　種族：{sd.name_zh if sd else sp_id}",
        ]

        # 血統
        lin = d.lineage
        if lin and sd and sd.lineage_options:
            lo = next((opt for opt in sd.lineage_options if opt.id == lin), None)
            if lo:
                lines.append(f"血統：{lo.name_zh}（{lo.name_en}）")

        lines += ["", "── 屬性值 ──"]
        bg_adj = d.bg_adjust
        for ab in ABILITY_ORDER:
            val = char.ability_scores.score(ab)
            mod = char.ability_scores.modifier(ab)
            sign = "+" if mod >= 0 else ""
            adj = bg_adj.get(ab, 0)
            adj_note = f" (背景+{adj})" if adj > 0 else ""
            lines.append(f"  {ab.value} {ABILITY_ZH[ab]:<4}  {val:>2}  ({sign}{mod}){adj_note}")

        lines += [
            "",
            f"HP：{char.hp_current}　AC：{char.ac}　速度：{sd.speed if sd else '9m'}",
            f"被動感知：{char.passive_perception}　先攻："
            f"{'+' if char.ability_scores.modifier(Ability.DEX) >= 0 else ''}"
            f"{char.ability_scores.modifier(Ability.DEX)}",
            "熟練加值：+2",
        ]

        # 豁免
        if cc in CLASS_REGISTRY:
            saves = CLASS_REGISTRY[cc].saving_throws
            save_str = ", ".join(f"{ABILITY_ZH[a]}（{a.value}）" for a in saves)
            lines.append(f"豁免熟練：{save_str}")

        # 護甲/武器訓練
        if cd:
            lines.append(f"護甲訓練：{', '.join(cd.armor_training) or '無'}")
            lines.append(f"武器訓練：{', '.join(cd.weapon_training)}")

        # 背景起源專長
        if bg:
            feat = self.session.get_origin_feat()
            lines += ["", "── 起源專長 ──"]
            lines.append(f"  {bg.feat_zh}（{bg.feat}）")
            if feat:
                lines.append(f"  {feat.description}")

        # 技能
        lines += ["", "── 技能熟練 ──"]
        if bg:
            for s in bg.skill_proficiencies:
                bonus = char.skill_bonus(s)
                sign = "+" if bonus >= 0 else ""
                lines.append(f"  {SKILL_ZH.get(s, s.value):<8}（{s.value}）{sign}{bonus}  [背景]")
        for s in d.skills:
            bonus = char.skill_bonus(s)
            sign = "+" if bonus >= 0 else ""
            lines.append(f"  {SKILL_ZH.get(s, s.value):<8}（{s.value}）{sign}{bonus}  [職業]")

        # 工具熟練
        if bg:
            lines.append(f"\n工具熟練：{bg.tool_proficiency}")

        # 裝備
        lines += ["", "── 起始裝備 ──"]
        if bg:
            eq_text = bg.equipment_a if d.bg_equipment == "A" else bg.equipment_b
            lines.append(f"  背景：{eq_text}")
        if cd:
            eq_text = cd.equipment_a if d.class_equipment == "A" else cd.equipment_b
            lines.append(f"  職業：{eq_text}")

        # 種族特性
        if sd:
            lines += ["", "── 種族特性 ──"]
            lines.append(f"  {', '.join(sd.traits)}")
            lines.append(f"  {sd.traits_description}")

        # 專長法術（Magic Initiate）
        if d.feat_cantrips or d.feat_spells:
            spell_feat = self.session._get_spell_feat()
            if spell_feat:
                sa = d.feat_spellcasting_ability
                sa_name = ABILITY_ZH.get(sa, "未選") if sa else "未選"
                lines += [
                    "",
                    f"── 專長法術（{spell_feat.name_zh}，施法屬性：{sa_name}）──",
                ]
                if d.feat_cantrips:
                    lines.append(f"  戲法：{', '.join(d.feat_cantrips)}")
                if d.feat_spells:
                    lines.append(f"  1 環法術：{', '.join(d.feat_spells)}")

        # 職業戲法與法術
        if d.cantrips or d.spells:
            lines += ["", "── 職業法術 ──"]
            if d.cantrips:
                lines.append(f"  戲法：{', '.join(d.cantrips)}")
            if d.spells:
                lines.append(f"  1 環法術：{', '.join(d.spells)}")
            if cc in CLASS_REGISTRY and CLASS_REGISTRY[cc].spellcasting_ability:
                sa = CLASS_REGISTRY[cc].spellcasting_ability
                lines.append(f"  施法屬性：{ABILITY_ZH.get(sa, '')}（{sa.value}）")

        # 魔能祈喚（Warlock）
        if d.invocations:
            lines += ["", "── 魔能祈喚 ──"]
            for inv_id in d.invocations:
                inv = INVOCATION_REGISTRY.get(inv_id)
                if inv:
                    lines.append(f"  • {inv.name_zh}（{inv.name_en}）")
                    lines.append(f"    {inv.description}")

        # 1 級職業特性
        if cd and cd.features_1st:
            lines += ["", "── 1 級職業特性 ──"]
            for feat_name in cd.features_1st:
                lines.append(f"  • {feat_name}")

        return "\n".join(lines)

    # ── Preview panel ─────────────────────────────────────────────────────────

    def _update_preview(self) -> None:
        """更新右側預覽面板：委託 session.get_summary()。"""
        preview = self.query_one("#preview-panel", Static)
        summary = self.session.get_summary()
        header = "角色預覽\n" + "─" * 36 + "\n"
        if summary:
            preview.update(header + summary)
        else:
            preview.update(header + "（尚無選擇）")

    # ── Data collection ───────────────────────────────────────────────────────

    def _collect_step_data(self) -> None:
        """讀取當步 widget → session。驗證失敗 raise ValueError。"""
        step = self._current_step
        collectors = {
            StepType.CLASS: self._collect_class,
            StepType.BACKGROUND: self._collect_background,
            StepType.SPECIES: self._collect_species,
            StepType.ABILITY_SCORES: self._collect_ability_scores,
            StepType.SKILLS: self._collect_skills,
            StepType.INVOCATIONS: self._collect_invocations,
            StepType.SPELLS: self._collect_spells,
            StepType.EQUIPMENT: self._collect_equipment,
            StepType.CONFIRM: self._collect_confirm,
        }
        collector = collectors.get(step)
        if collector:
            collector()

    def _collect_class(self) -> None:
        rs = self.query_one("#class-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇職業")
        keys = list(CLASS_DISPLAY.keys())
        self.session.set_class(keys[idx])

    def _collect_background(self) -> None:
        rs = self.query_one("#bg-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇背景")
        keys = list(BACKGROUND_REGISTRY.keys())
        bg_id = keys[idx]
        self.session.set_background(bg_id)

        # 背景「任選一種」工具
        bg_data = BACKGROUND_REGISTRY[bg_id]
        if bg_data.tool_proficiency_category:
            try:
                tool_rs = self.query_one("#bg-tool-radio", RadioSet)
                tool_idx = tool_rs.pressed_index
                if tool_idx is not None:
                    available = self.session.get_available_bg_tools()
                    if tool_idx < len(available):
                        self.session.set_bg_tool_choice(available[tool_idx])
                else:
                    raise ValueError(f"請選擇{bg_data.tool_proficiency_label}")
            except ValueError:
                raise
            except Exception:
                raise ValueError(f"請選擇{bg_data.tool_proficiency_label}") from None

    def _collect_species(self) -> None:
        rs = self.query_one("#species-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇種族")
        keys = list(SPECIES_REGISTRY.keys())
        sp_id = keys[idx]

        # 血統子選項
        sd = SPECIES_REGISTRY[sp_id]
        lineage_id = ""
        if sd.lineage_options:
            try:
                lin_rs = self.query_one("#lineage-radio", RadioSet)
                lin_idx = lin_rs.pressed_index
                if lin_idx is not None:
                    lineage_id = sd.lineage_options[lin_idx].id
            except Exception:
                pass

        self.session.set_species(sp_id, lineage_id)

        # 血統法術施法屬性（Tiefling 等）
        sd = SPECIES_REGISTRY[sp_id]
        if sd.has_lineage_spellcasting_choice:
            try:
                sa_rs = self.query_one("#species-sa-radio", RadioSet)
                sa_idx = sa_rs.pressed_index
                if sa_idx is not None:
                    ab_map = [Ability.INT, Ability.WIS, Ability.CHA]
                    self.session.set_species_spellcasting_ability(ab_map[sa_idx])
                else:
                    raise ValueError("請選擇血統法術施法屬性（INT/WIS/CHA）")
            except ValueError:
                raise
            except Exception:
                raise ValueError("請選擇血統法術施法屬性（INT/WIS/CHA）") from None

        # 多藝起源專長
        if sd.feat_choice_count > 0:
            try:
                feat_rs = self.query_one("#species-feat-radio", RadioSet)
                feat_idx = feat_rs.pressed_index
                if feat_idx is not None:
                    feat_keys = list(ORIGIN_FEAT_REGISTRY.keys())
                    if feat_idx < len(feat_keys):
                        self.session.set_species_feat(feat_keys[feat_idx])
                else:
                    raise ValueError("請選擇起源專長（多藝）")
            except ValueError:
                raise
            except Exception:
                raise ValueError("請選擇起源專長（多藝）") from None

    def _collect_ability_scores(self) -> None:
        # 方法
        try:
            mrs = self.query_one("#method-radio", RadioSet)
            idx = mrs.pressed_index
            if idx is not None:
                method = ["standard", "point_buy", "roll"][idx]
                self.session.set_ability_method(method)
        except Exception:
            pass

        method = self.session.data.score_method

        if method == "point_buy":
            self._collect_point_buy()
        elif method == "roll":
            self._collect_roll()
        # standard 已在 set_ability_method 中自動分配

        # 背景調整
        self._collect_bg_adjust()

    def _collect_point_buy(self) -> None:
        for ab in ABILITY_ORDER:
            try:
                sel = self.query_one(f"#pb-{ab.value}", Select)
                val = sel.value
                if val is not None and val != Select.BLANK:
                    self.session.set_point_buy_score(ab, int(val))
            except Exception:
                pass

        # 驗證購點預算
        remaining = self.session.get_point_buy_remaining()
        if remaining < 0:
            raise ValueError(f"購點超支 {-remaining} 點")
        if remaining > 0:
            raise ValueError(f"還有 {remaining} 點未使用")

    def _collect_roll(self) -> None:
        rolled = self.session.data.rolled_values
        if not rolled:
            # 首次進入擲骰模式，自動擲骰
            self.session.reroll_abilities()
            raise ValueError("已擲骰並自動分配，請確認結果")

    def _collect_bg_adjust(self) -> None:
        d = self.session.data
        if not d.background or d.background not in BACKGROUND_REGISTRY:
            return

        # 調整模式
        try:
            adj_rs = self.query_one("#adjust-mode-radio", RadioSet)
            idx = adj_rs.pressed_index
            if idx is not None:
                mode = ["+1/+1/+1", "+2/+1"][idx]
                self.session.set_bg_adjust_mode(mode)
        except Exception:
            pass

        if d.bg_adjust_mode == "+2/+1":
            try:
                sel2 = self.query_one("#adj-plus2", Select)
                if isinstance(sel2.value, Ability):
                    self.session.set_bg_adjust_plus2(sel2.value)
            except Exception:
                pass
            try:
                sel1 = self.query_one("#adj-plus1", Select)
                if isinstance(sel1.value, Ability):
                    self.session.set_bg_adjust_plus1(sel1.value)
            except Exception:
                pass

    def _collect_skills(self) -> None:
        try:
            sl = self.query_one("#skills-list", SelectionList)
            self.session.set_skills(list(sl.selected))
        except ValueError:
            raise
        except Exception:
            pass

    def _collect_equipment(self) -> None:
        d = self.session.data
        bg_eq = d.bg_equipment or "A"
        cls_eq = d.class_equipment or "A"

        try:
            bg_rs = self.query_one("#bg-equip-radio", RadioSet)
            idx = bg_rs.pressed_index
            if idx is not None:
                bg_eq = "A" if idx == 0 else "B"
        except Exception:
            pass
        try:
            cls_rs = self.query_one("#cls-equip-radio", RadioSet)
            idx = cls_rs.pressed_index
            if idx is not None:
                cls_eq = "A" if idx == 0 else "B"
        except Exception:
            pass

        self.session.set_equipment(bg_eq, cls_eq)

    def _collect_invocations(self) -> None:
        """收集魔能祈喚選擇（Warlock 獨立步驟）。"""
        try:
            sl = self.query_one("#invocation-list", SelectionList)
            self.session.set_invocations(list(sl.selected))
        except ValueError:
            raise
        except Exception:
            pass

    def _collect_spells(self) -> None:
        d = self.session.data
        cc = d.char_class
        cd = CLASS_DISPLAY.get(cc) if cc else None

        # ── 專長法術（Magic Initiate）──
        if self.session.has_feat_spell_choices():
            spell_feat = self.session._get_spell_feat()
            if spell_feat:
                # 施法屬性
                if spell_feat.spellcasting_ability_choice:
                    try:
                        ab_rs = self.query_one("#feat-ability-radio", RadioSet)
                        ab_idx = ab_rs.pressed_index
                        if ab_idx is not None:
                            ab_map = [Ability.INT, Ability.WIS, Ability.CHA]
                            self.session.set_feat_spellcasting_ability(ab_map[ab_idx])
                        else:
                            raise ValueError("請選擇專長施法屬性")
                    except ValueError:
                        raise
                    except Exception:
                        raise ValueError("請選擇專長施法屬性") from None

                # 專長戲法
                if spell_feat.num_feat_cantrips > 0:
                    try:
                        sl = self.query_one("#feat-cantrip-list", SelectionList)
                        self.session.set_feat_cantrips(list(sl.selected))
                    except Exception:
                        pass

                # 專長 1 環法術
                if spell_feat.num_feat_spells > 0:
                    try:
                        sl = self.query_one("#feat-spell-list", SelectionList)
                        self.session.set_feat_spells(list(sl.selected))
                    except Exception:
                        pass

        # ── 職業法術 ──
        if not cd:
            return

        cantrips_sel: list[str] = []
        spells_sel: list[str] = []

        if cd.num_cantrips > 0:
            try:
                sl = self.query_one("#cantrip-list", SelectionList)
                cantrips_sel = list(sl.selected)
            except Exception:
                pass

        if cd.num_prepared_spells > 0:
            try:
                sl = self.query_one("#spell-list", SelectionList)
                spells_sel = list(sl.selected)
            except Exception:
                pass

        self.session.set_cantrips(cantrips_sel)
        self.session.set_spells(spells_sel)

    def _collect_confirm(self) -> None:
        try:
            name_input = self.query_one("#name-input", Input)
            self.session.set_name(name_input.value)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("角色名稱不能為空") from exc

    # ── Actions ───────────────────────────────────────────────────────────────

    async def action_next_step(self) -> None:
        if self._current_step == StepType.CONFIRM:
            self._finish()
            return
        try:
            self._collect_step_data()
        except ValueError as e:
            self.notify(str(e), severity="error")
            # 擲骰模式首次進入需重新渲染
            if "已擲骰" in str(e):
                await self._render_step()
                self._update_preview()
            return

        self._step_index += 1
        await self._render_step()
        self._update_preview()
        self._update_title()

    async def action_prev_step(self) -> None:
        if self._step_index > 0:
            self._step_index -= 1
            await self._render_step()
            self._update_preview()
            self._update_title()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("next-btn", "confirm-btn"):
            await self.action_next_step()
        elif event.button.id == "reroll-btn":
            self.session.reroll_abilities()
            await self._render_step()
            self._update_preview()

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Select 變更時即時更新。"""
        sel_id = event.select.id or ""
        if sel_id.startswith("pb-"):
            # 即時更新 scores
            for ab in ABILITY_ORDER:
                try:
                    sel = self.query_one(f"#pb-{ab.value}", Select)
                    val = sel.value
                    if isinstance(val, int):
                        self.session.set_point_buy_score(ab, val)
                except Exception:
                    pass
            # 同步暫存以便切換方法後恢復
            self.session.sync_point_buy_cache()
            remaining = self.session.get_point_buy_remaining()
            self._update_preview()
            severity = "error" if remaining < 0 else "information"
            self.notify(f"剩餘點數：{remaining}/{POINT_BUY_BUDGET}", severity=severity)
        elif sel_id in ("adj-plus2", "adj-plus1"):
            # +2/+1 不可選同一屬性
            try:
                sel2 = self.query_one("#adj-plus2", Select)
                sel1 = self.query_one("#adj-plus1", Select)
                if (
                    isinstance(sel2.value, Ability)
                    and isinstance(sel1.value, Ability)
                    and sel2.value == sel1.value
                ):
                    self.notify("+2 和 +1 不能選同一屬性！", severity="error")
                else:
                    if isinstance(sel2.value, Ability):
                        self.session.set_bg_adjust_plus2(sel2.value)
                    if isinstance(sel1.value, Ability):
                        import contextlib

                        with contextlib.suppress(ValueError):
                            self.session.set_bg_adjust_plus1(sel1.value)
                    self._update_preview()
            except Exception:
                pass

    def _get_selection_limit(self, sl_id: str) -> int:
        """取得 SelectionList 的選取上限。"""
        cc = self.session.data.char_class
        cd = CLASS_DISPLAY.get(cc) if cc else None
        if sl_id == "invocation-list":
            return self.session.get_num_invocations()
        elif sl_id == "skills-list":
            return self.session.get_total_skill_picks()
        elif sl_id == "cantrip-list":
            return cd.num_cantrips if cd else 0
        elif sl_id == "spell-list":
            return cd.num_prepared_spells if cd else 0
        elif sl_id == "feat-cantrip-list":
            spell_feat = self.session._get_spell_feat()
            return spell_feat.num_feat_cantrips if spell_feat else 0
        elif sl_id == "feat-spell-list":
            spell_feat = self.session._get_spell_feat()
            return spell_feat.num_feat_spells if spell_feat else 0
        return 999

    def _enforce_selection_limit(self, sl: SelectionList, sl_id: str, limit: int) -> list:
        """強制多選上限。超過時取消最早選的。回傳最終 selected list。"""
        selected = list(sl.selected)
        order = self._selection_order.setdefault(sl_id, [])
        # 更新順序：新增的加到尾部
        current_set = set(selected)
        # 移除已取消的
        order = [v for v in order if v in current_set]
        # 新增的（在 selected 中但不在 order 中）
        for v in selected:
            if v not in order:
                order.append(v)
        self._selection_order[sl_id] = order

        # 超過上限：取消最早的
        while len(order) > limit:
            oldest = order.pop(0)
            sl.deselect(oldest)
        return list(sl.selected)

    async def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        """技能/法術勾選時即時更新預覽，超過上限自動取消最早的。"""
        sl = event.selection_list
        sl_id = sl.id or ""
        limit = self._get_selection_limit(sl_id)

        if sl_id == "invocation-list":
            selected = self._enforce_selection_limit(sl, sl_id, limit)
            self.session.data.invocations = selected
            self._update_preview()
            # 重新渲染以更新祈喚描述的 ▶ 標記
            await self._render_step()
        elif sl_id == "skills-list":
            selected = self._enforce_selection_limit(sl, sl_id, limit)
            self.session.data.skills = selected
            self._update_preview()
        elif sl_id in ("cantrip-list", "spell-list"):
            selected = self._enforce_selection_limit(sl, sl_id, limit)
            if sl_id == "cantrip-list":
                self.session.data.cantrips = selected
            else:
                self.session.data.spells = selected
            self._update_preview()
            # 重新渲染以更新法術詳情區塊
            await self._render_step()
        elif sl_id in ("feat-cantrip-list", "feat-spell-list"):
            selected = self._enforce_selection_limit(sl, sl_id, limit)
            if sl_id == "feat-cantrip-list":
                self.session.data.feat_cantrips = selected
            else:
                self.session.data.feat_spells = selected
            self._update_preview()
            await self._render_step()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "name-input":
            await self.action_next_step()

    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """RadioSet 變更時即時更新預覽。"""
        rs_id = event.radio_set.id or ""

        if rs_id == "class-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(CLASS_DISPLAY.keys())
                self.session.set_class(keys[idx])
                self._update_preview()

        elif rs_id == "bg-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(BACKGROUND_REGISTRY.keys())
                old_bg = self.session.data.background
                self.session.set_background(keys[idx])
                self._update_preview()
                # 背景切換時重新渲染（顯示/隱藏工具選擇）
                if keys[idx] != old_bg:
                    await self._render_step()

        elif rs_id == "bg-tool-radio":
            available = self.session.get_available_bg_tools()
            idx = event.radio_set.pressed_index
            if idx is not None and idx < len(available):
                self.session.set_bg_tool_choice(available[idx])
                self._update_preview()

        elif rs_id == "species-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(SPECIES_REGISTRY.keys())
                new_sp = keys[idx]
                old_sp = self.session.data.species
                self.session.set_species(new_sp)
                self._update_preview()
                # 切換種族時重新渲染（顯示或隱藏血統選項）
                if new_sp != old_sp:
                    await self._render_step()

        elif rs_id == "lineage-radio":
            sp_id = self.session.data.species
            if sp_id in SPECIES_REGISTRY:
                sd = SPECIES_REGISTRY[sp_id]
                idx = event.radio_set.pressed_index
                if idx is not None and idx < len(sd.lineage_options):
                    self.session.set_species(sp_id, sd.lineage_options[idx].id)
                    self._update_preview()

        elif rs_id == "species-sa-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                ab_map = [Ability.INT, Ability.WIS, Ability.CHA]
                self.session.set_species_spellcasting_ability(ab_map[idx])
                self._update_preview()

        elif rs_id == "species-feat-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(ORIGIN_FEAT_REGISTRY.keys())
                if idx < len(keys):
                    self.session.set_species_feat(keys[idx])
                    self._update_preview()

        elif rs_id == "adjust-mode-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                mode = ["+1/+1/+1", "+2/+1"][idx]
                self.session.set_bg_adjust_mode(mode)
                await self._render_step()
                self._update_preview()

        elif rs_id == "bg-equip-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                bg_eq = "A" if idx == 0 else "B"
                cls_eq = self.session.data.class_equipment or "A"
                self.session.set_equipment(bg_eq, cls_eq)
                self._update_preview()

        elif rs_id == "cls-equip-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                bg_eq = self.session.data.bg_equipment or "A"
                cls_eq = "A" if idx == 0 else "B"
                self.session.set_equipment(bg_eq, cls_eq)
                self._update_preview()

        elif rs_id == "method-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                method = ["standard", "point_buy", "roll"][idx]
                self.session.set_ability_method(method)
                await self._render_step()
                self._update_preview()

    def _finish(self) -> None:
        try:
            self._collect_step_data()
            ok, msg = self.session.validate()
            if not ok:
                self.notify(msg, severity="error")
                return
            char = self.session.build_character()
            from tot.tui.character_io import save_character

            saved_path = save_character(char)
            self.notify(f"角色卡已儲存：{saved_path}", severity="information")
            self.exit(result=char)
        except ValueError as e:
            self.notify(str(e), severity="error")


# ── 工具函式 ──────────────────────────────────────────────────────────────────


def _skill_ability(skill: Skill) -> Ability:
    """取得技能對應的屬性。"""
    from tot.models.enums import SKILL_ABILITY_MAP

    return SKILL_ABILITY_MAP.get(skill, Ability.STR)
