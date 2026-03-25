"""T.O.T. 角色建造 TUI — 8 步驟 Wizard 介面（2024 PHB 流程）。

步驟：職業 → 背景 → 種族 → 屬性值 → 技能 → 裝備 → 戲法法術 → 名稱＋確認
"""

from __future__ import annotations

import json
from pathlib import Path

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

from tot.data.classes import (
    CLASS_DISPLAY,
    STANDARD_ARRAY_SUGGESTION,
)
from tot.data.feats import FeatData, ORIGIN_FEAT_REGISTRY, get_available_class_skills
from tot.data.origins import (
    ABILITY_ZH,
    BACKGROUND_REGISTRY,
    SKILL_ZH,
    SPECIES_REGISTRY,
)
from tot.gremlins.bone_engine.character import (
    CLASS_REGISTRY,
    POINT_BUY_BUDGET,
    POINT_BUY_COSTS,
    STANDARD_ARRAY,
    CharacterBuilder,
    apply_background_bonus,
    validate_point_buy,
    validate_skill_selection,
    validate_spell_selection,
    validate_standard_array,
)
from tot.gremlins.bone_engine.dice import roll_ability_scores
from tot.models.creature import AbilityScores, Character
from tot.models.enums import Ability, Skill

# ── 常數 ──────────────────────────────────────────────────────────────────────

TOTAL_STEPS = 8

STEP_TITLES = {
    1: "選擇職業",
    2: "選擇背景",
    3: "選擇種族",
    4: "設定屬性值",
    5: "選擇技能",
    6: "選擇裝備",
    7: "戲法與法術",
    8: "角色名稱＋確認",
}

ABILITY_ORDER: list[Ability] = [
    Ability.STR,
    Ability.DEX,
    Ability.CON,
    Ability.INT,
    Ability.WIS,
    Ability.CHA,
]

DAMAGE_TYPE_ZH: dict[str, str] = {
    "Fire": "火焰", "Cold": "寒冷", "Lightning": "閃電", "Thunder": "雷鳴",
    "Acid": "酸液", "Poison": "毒素", "Necrotic": "黯蝕", "Radiant": "光輝",
    "Force": "力場", "Psychic": "心靈", "Bludgeoning": "鈍擊",
    "Piercing": "穿刺", "Slashing": "揮砍",
}

EFFECT_TYPE_ZH: dict[str, str] = {
    "damage": "傷害", "healing": "治療", "condition": "狀態",
    "buff": "增益", "utility": "功能",
}

# ── 法術載入 ──────────────────────────────────────────────────────────────────

_SPELLS_DIR = Path(__file__).resolve().parents[2] / "data" / "spells"
_SPELLS_JSON_LEGACY = Path(__file__).resolve().parents[2] / "data" / "spells.json"


def _load_spells() -> list[dict]:
    """從 spells 目錄載入所有法術列表。"""
    result: list[dict] = []
    if _SPELLS_DIR.is_dir():
        for f in sorted(_SPELLS_DIR.glob("*.json")):
            with open(f) as fp:
                result.extend(json.load(fp))
    elif _SPELLS_JSON_LEGACY.exists():
        with open(_SPELLS_JSON_LEGACY) as f:
            result = json.load(f)
    return result


def _spells_for_class(class_id: str, level: int) -> list[dict]:
    """取得某職業某環級的法術列表。"""
    return [
        s
        for s in _load_spells()
        if level == s.get("level", -1) and class_id in s.get("classes", [])
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
        self._step: int = 1
        self._data: dict = {
            "char_class": "",
            "background": "",
            "species": "",
            "lineage": "",
            "score_method": "standard",  # "standard" / "point_buy" / "roll"
            "scores": {a: 10 for a in Ability},
            "bg_adjust_mode": "+1/+1/+1",  # "+1/+1/+1" or "+2/+1"
            "bg_adjust": {},  # {Ability: int} 背景調整值
            "feat_skills": [],  # 起源專長選位技能（如 Skilled）
            "class_skills": [],
            "bg_equipment": "A",
            "class_equipment": "A",
            "cantrips": [],
            "spells": [],
            "name": "",
            # 擲骰結果暫存
            "_rolled_values": [],
            # 標準陣列分配暫存
            "_std_assign": {a: 0 for a in Ability},
        }

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
        s = self._step
        label = STEP_TITLES.get(s, "確認建角")
        self.title = f"T.O.T. 角色建造  ─  步驟 {s}/{TOTAL_STEPS}：{label}"

    # ── Step rendering ────────────────────────────────────────────────────────

    async def _render_step(self) -> None:
        """清除左側面板，重建當步 widgets。"""
        left = self.query_one("#left-panel", Vertical)
        await left.remove_children()

        step = self._step
        widgets: list = []
        label = STEP_TITLES.get(step, "")
        widgets.append(Label(f"步驟 {step}/{TOTAL_STEPS}：{label}", id="step-title"))

        render_fn = {
            1: self._widgets_class,
            2: self._widgets_background,
            3: self._widgets_species,
            4: self._widgets_ability_scores,
            5: self._widgets_skills,
            6: self._widgets_equipment,
            7: self._widgets_spells,
            8: self._widgets_confirm,
        }.get(step)

        if render_fn:
            render_fn(widgets)

        # 最後一步用確認按鈕，其餘用下一步按鈕
        if step == TOTAL_STEPS:
            widgets.append(Button("確認建角", id="confirm-btn", variant="success"))
        else:
            widgets.append(Button("確認 →  (Ctrl+N)", id="next-btn", variant="primary"))

        await left.mount(*widgets)

    # ── Step 1: 職業 ──────────────────────────────────────────────────────────

    def _widgets_class(self, w: list) -> None:
        cc = self._data["char_class"]
        btns = []
        for cid, cd in CLASS_DISPLAY.items():
            label = f"{cd.name_zh}（{cd.name_en}）— {cd.description[:20]}…"
            btns.append(RadioButton(label, value=(cid == cc)))
        w.append(RadioSet(*btns, id="class-radio"))

    # ── Step 2: 背景 ──────────────────────────────────────────────────────────

    def _widgets_background(self, w: list) -> None:
        bg = self._data["background"]
        btns = []
        for bid, bd in BACKGROUND_REGISTRY.items():
            label = f"{bd.name_zh}（{bd.name_en}）"
            btns.append(RadioButton(label, value=(bid == bg)))
        w.append(RadioSet(*btns, id="bg-radio"))

    # ── Step 3: 種族 ──────────────────────────────────────────────────────────

    def _widgets_species(self, w: list) -> None:
        sp = self._data["species"]
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
                cur_lin = self._data["lineage"]
                lin_btns = []
                for lo in sd.lineage_options:
                    lb = f"{lo.name_zh}（{lo.name_en}）— {lo.description}"
                    lin_btns.append(RadioButton(lb, value=(lo.id == cur_lin)))
                w.append(RadioSet(*lin_btns, id="lineage-radio"))

    # ── Step 4: 屬性值 ────────────────────────────────────────────────────────

    def _widgets_ability_scores(self, w: list) -> None:
        method = self._data["score_method"]

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
        bg_id = self._data["background"]
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            tags = [ABILITY_ZH[a] for a in bg.ability_tags]
            w.append(
                Label(
                    f"── 背景屬性調整（{bg.name_zh}：{'/'.join(tags)}）──", classes="section-label"
                )
            )
            adj_mode = self._data["bg_adjust_mode"]
            adj_btns = [
                RadioButton("三項各 +1（預設）", value=(adj_mode == "+1/+1/+1")),
                RadioButton("一項 +2，一項 +1", value=(adj_mode == "+2/+1")),
            ]
            w.append(RadioSet(*adj_btns, id="adjust-mode-radio"))

            if adj_mode == "+2/+1":
                w.append(Label("  +2 給："))
                opts_2 = [(ABILITY_ZH[a], a) for a in bg.ability_tags]
                cur_adj = self._data.get("bg_adjust", {})
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
        cc = self._data["char_class"]
        # 自動帶入職業建議值
        if cc in STANDARD_ARRAY_SUGGESTION:
            sug = STANDARD_ARRAY_SUGGESTION[cc]
            assign = dict(zip(ABILITY_ORDER, sug, strict=False))
        else:
            assign = dict(zip(ABILITY_ORDER, STANDARD_ARRAY, strict=False))
        self._data["_std_assign"] = assign
        self._data["scores"] = assign
        for ab in ABILITY_ORDER:
            val = assign[ab]
            mod = (val - 10) // 2
            sign = "+" if mod >= 0 else ""
            w.append(Label(f"  {ABILITY_ZH[ab]}（{ab.value}）：{val}（{sign}{mod}）"))

    def _widgets_point_buy(self, w: list) -> None:
        scores = self._data["scores"]
        total_cost = sum(POINT_BUY_COSTS.get(scores.get(a, 8), 0) for a in Ability)
        remaining = POINT_BUY_BUDGET - total_cost
        w.append(
            Label(
                f"── 點數購買（剩餘：{remaining}/{POINT_BUY_BUDGET} 點）──", classes="section-label"
            )
        )
        cost_str = "  花費：" + ", ".join(f"{v}={c}點" for v, c in POINT_BUY_COSTS.items())
        w.append(Label(cost_str))

        pb_opts = [(str(v), v) for v in range(8, 16)]
        for ab in ABILITY_ORDER:
            cur = scores.get(ab, 8)
            w.append(Label(f"  {ab.value} {ABILITY_ZH[ab]}", classes="ability-label"))
            w.append(Select(pb_opts, value=cur, id=f"pb-{ab.value}"))

    def _widgets_roll(self, w: list) -> None:
        rolled = self._data.get("_rolled_values", [])
        if not rolled:
            w.append(Label("  按「確認→下一步」後自動擲骰並分配"))
        else:
            w.append(
                Label(f"── 擲骰結果：{sorted(rolled, reverse=True)}（依職業最優分配）──", classes="section-label")
            )
            # 自動分配：按職業主屬性優先
            assign = self._auto_assign_rolls(rolled)
            self._data["_std_assign"] = assign
            self._data["scores"] = assign
            for ab in ABILITY_ORDER:
                val = assign.get(ab, 10)
                mod = (val - 10) // 2
                sign = "+" if mod >= 0 else ""
                w.append(Label(f"  {ABILITY_ZH[ab]}（{ab.value}）：{val}（{sign}{mod}）"))
            w.append(Button("重新擲骰", id="reroll-btn", variant="warning"))

    def _auto_assign_rolls(self, rolled: list[int]) -> dict[Ability, int]:
        """依職業屬性優先順序自動分配擲骰結果。"""
        cc = self._data["char_class"]
        sorted_vals = sorted(rolled, reverse=True)
        # 用標準陣列建議的順序來決定優先度
        if cc in STANDARD_ARRAY_SUGGESTION:
            sug = STANDARD_ARRAY_SUGGESTION[cc]
            # 建議值越高的屬性越重要，給越高的擲骰結果
            priority = sorted(range(6), key=lambda i: sug[i], reverse=True)
        else:
            # 預設 STR>DEX>CON>INT>WIS>CHA
            priority = list(range(6))
        assign: dict[Ability, int] = {}
        for rank, val in enumerate(sorted_vals):
            ab_idx = priority[rank]
            assign[ABILITY_ORDER[ab_idx]] = val
        return assign

    # ── Step 5: 技能 ──────────────────────────────────────────────────────────

    def _widgets_skills(self, w: list) -> None:
        bg_id = self._data["background"]
        cc = self._data["char_class"]

        # 背景固定技能（顯示，不可改）
        bg_skill_set: set[Skill] = set()
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            bg_skill_set = set(bg.skill_proficiencies)
            bg_labels = [f"{SKILL_ZH[s]}（{s.value}）" for s in bg.skill_proficiencies]
            w.append(Label(f"── 背景技能（{bg.name_zh}，已固定）──", classes="section-label"))
            w.append(Label(f"  {', '.join(bg_labels)}"))

        # 合併選位：專長 + 職業 = 一張表
        # 總選位數 = feat.skill_choice_count + cls.num_skills
        feat = self._get_origin_feat()
        feat_count = feat.skill_choice_count if feat and feat.skill_choice_count > 0 else 0
        cls_count = 0
        if cc and cc in CLASS_REGISTRY:
            cls_count = CLASS_REGISTRY[cc].num_skills
        total_picks = feat_count + cls_count

        if total_picks > 0:
            # 候選池 = (專長池 ∪ 職業池) - 背景已佔
            # 專長池為空時 = 全 18 項；職業池 = skill_choices
            candidate_set: set[Skill] = set()
            if feat_count > 0:
                if feat.skill_choice_pool:
                    candidate_set.update(feat.skill_choice_pool)
                else:
                    candidate_set.update(Skill)  # 全 18 項
            if cc and cc in CLASS_REGISTRY:
                candidate_set.update(CLASS_REGISTRY[cc].skill_choices)
            candidate_set -= bg_skill_set

            # 來源標記
            cls_set = set(CLASS_REGISTRY[cc].skill_choices) if cc and cc in CLASS_REGISTRY else set()
            sources = []
            if feat_count > 0:
                sources.append(f"{feat.name_zh} {feat_count}")
            if cls_count > 0:
                cd = CLASS_DISPLAY.get(cc)
                name = cd.name_zh if cd else cc
                sources.append(f"{name} {cls_count}")

            w.append(Label(
                f"── 選擇技能熟練（共 {total_picks} 項：{'＋'.join(sources)}）──",
                classes="section-label",
            ))

            selected = self._data.get("class_skills", [])
            options = []
            # 職業技能優先排列
            for s in sorted(candidate_set, key=lambda s: (s not in cls_set, s.value)):
                ab = _skill_ability(s)
                marker = "" if s in cls_set else "　☆" if feat_count > 0 else ""
                label = f"{SKILL_ZH.get(s, s.value)}（{s.value}）— {ABILITY_ZH.get(ab, '')}{marker}"
                options.append((label, s, s in selected))
            w.append(SelectionList(*options, id="skills-list"))

    def _get_origin_feat(self) -> FeatData | None:
        """取得當前背景的起源專長資料。"""
        bg_id = self._data["background"]
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            feat_id = BACKGROUND_REGISTRY[bg_id].feat
            return ORIGIN_FEAT_REGISTRY.get(feat_id)
        return None

    # ── Step 6: 裝備 ──────────────────────────────────────────────────────────

    def _widgets_equipment(self, w: list) -> None:
        bg_id = self._data["background"]
        cc = self._data["char_class"]

        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            w.append(Label(f"── 背景裝備（{bg.name_zh}）──", classes="section-label"))
            w.append(Label(f"  A：{bg.equipment_a}"))
            w.append(Label(f"  B：{bg.equipment_b}"))
            cur_bg = self._data.get("bg_equipment", "A")
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
            cur_cls = self._data.get("class_equipment", "A")
            btns = [
                RadioButton("選 A", value=(cur_cls == "A")),
                RadioButton("選 B", value=(cur_cls == "B")),
            ]
            w.append(RadioSet(*btns, id="cls-equip-radio"))

    # ── Step 7: 戲法與法術 ────────────────────────────────────────────────────

    def _widgets_spells(self, w: list) -> None:
        cc = self._data["char_class"]
        if not cc:
            w.append(Label("請先選擇職業"))
            return

        cd = CLASS_DISPLAY.get(cc)
        if not cd or (cd.num_cantrips == 0 and cd.num_prepared_spells == 0):
            w.append(Label(f"{cd.name_zh if cd else cc} 在 1 級沒有施法能力，跳過此步。"))
            return

        # 戲法
        if cd.num_cantrips > 0:
            cantrips = _spells_for_class(cc, 0)
            w.append(
                Label(
                    f"── 戲法（選 {cd.num_cantrips} 個）──",
                    classes="section-label",
                )
            )
            if cantrips:
                sel = self._data.get("cantrips", [])
                opts = []
                for s in cantrips:
                    dt = DAMAGE_TYPE_ZH.get(s.get("damage_type", ""), "")
                    et = EFFECT_TYPE_ZH.get(s.get("effect_type", ""), "")
                    tag = dt if dt else et
                    opts.append((
                        f"{s['name']}（{s['en_name']}）— {tag}",
                        s["en_name"],
                        s["en_name"] in sel,
                    ))
                w.append(SelectionList(*opts, id="cantrip-list"))
            else:
                w.append(Label("  （法術資料庫尚無此職業的戲法）"))

        # 1 環法術
        if cd.num_prepared_spells > 0:
            spells_1 = _spells_for_class(cc, 1)
            w.append(
                Label(
                    f"── 1 環法術（選 {cd.num_prepared_spells} 個）──",
                    classes="section-label",
                )
            )
            if spells_1:
                sel = self._data.get("spells", [])
                opts = []
                for s in spells_1:
                    dt = DAMAGE_TYPE_ZH.get(s.get("damage_type", ""), "")
                    et = EFFECT_TYPE_ZH.get(s.get("effect_type", ""), "")
                    tag = dt if dt else et
                    opts.append((
                        f"{s['name']}（{s['en_name']}）— {tag}",
                        s["en_name"],
                        s["en_name"] in sel,
                    ))
                w.append(SelectionList(*opts, id="spell-list"))
            else:
                w.append(Label("  （法術資料庫尚無此職業的 1 環法術）"))

    # ── Step 8: 名稱＋確認 ────────────────────────────────────────────────────

    def _widgets_confirm(self, w: list) -> None:
        w.append(Label("── 角色名稱 ──", classes="section-label"))
        w.append(
            Input(
                value=self._data["name"],
                placeholder="輸入角色名稱...",
                id="name-input",
            )
        )

        # 完整角色卡預覽
        w.append(Label("── 角色卡預覽 ──", classes="section-label"))
        try:
            char = self._build_character()
            summary = self._format_full_summary(char)
            w.append(Static(summary))
        except Exception as e:
            w.append(Static(f"[red]建角錯誤：{e}[/red]"))

    # ── Preview panel ─────────────────────────────────────────────────────────

    def _update_preview(self) -> None:
        """更新右側預覽面板：顯示已選項目的詳細資訊。"""
        d = self._data
        preview = self.query_one("#preview-panel", Static)
        lines: list[str] = ["角色預覽", "─" * 36]

        # 職業
        cc = d["char_class"]
        if cc and cc in CLASS_DISPLAY:
            cd = CLASS_DISPLAY[cc]
            cls = CLASS_REGISTRY.get(cc)
            lines.append(f"職業：{cd.name_zh}（{cd.name_en}）")
            lines.append(f"  {cd.description}")
            lines.append(f"  複雜度：{cd.complexity}　生命骰：d{cls.hit_die if cls else '?'}")
            if cls:
                sa = cls.spellcasting_ability
                lines.append(
                    f"  核心能力：{ABILITY_ZH.get(cls.primary_ability, '?')}"
                    + (f"　施法屬性：{ABILITY_ZH.get(sa, '')}" if sa else "")
                )
            lines.append(f"  護甲：{', '.join(cd.armor_training) or '無'}")
            lines.append(f"  武器：{', '.join(cd.weapon_training)}")
            if cd.num_cantrips or cd.num_prepared_spells:
                lines.append(f"  1級戲法：{cd.num_cantrips}　1級法術：{cd.num_prepared_spells}")
            if cd.features_1st:
                lines.append(f"  1級特性：{', '.join(cd.features_1st)}")
        else:
            lines.append("職業：—")

        lines.append("")

        # 背景
        bg_id = d["background"]
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[bg_id]
            feat = ORIGIN_FEAT_REGISTRY.get(bg.feat)
            lines.append(f"背景：{bg.name_zh}（{bg.name_en}）")
            lines.append(f"  {bg.description}")
            lines.append(f"  專長：{bg.feat_zh}")
            if feat:
                lines.append(f"    {feat.description}")
            bg_skills = [f"{SKILL_ZH[s]}" for s in bg.skill_proficiencies]
            lines.append(f"  技能：{', '.join(bg_skills)}　工具：{bg.tool_proficiency}")
            tags = [ABILITY_ZH[a] for a in bg.ability_tags]
            lines.append(f"  屬性調整：{'/'.join(tags)} 中選 +2/+1 或各 +1")
        else:
            lines.append("背景：—")

        lines.append("")

        # 種族
        sp_id = d["species"]
        if sp_id and sp_id in SPECIES_REGISTRY:
            sd = SPECIES_REGISTRY[sp_id]
            lines.append(f"種族：{sd.name_zh}（{sd.name_en}）")
            lines.append(f"  {sd.description}")
            lines.append(f"  體型：{sd.size}　速度：{sd.speed}")
            lines.append(f"  特性：{', '.join(sd.traits)}")
            lines.append(f"  {sd.traits_description}")
            lin = d.get("lineage")
            if lin and sd.lineage_options:
                lo = next((l for l in sd.lineage_options if l.id == lin), None)
                if lo:
                    lines.append(f"  血統：{lo.name_zh}（{lo.name_en}）— {lo.description}")
        else:
            lines.append("種族：—")

        lines.append("")

        # 屬性值
        scores = d["scores"]
        bg_adj = d.get("bg_adjust", {})
        if any(v != 10 for v in scores.values()):
            lines.append("屬性值：")
            for ab in ABILITY_ORDER:
                base = scores.get(ab, 10)
                adj = bg_adj.get(ab, 0)
                total = base + adj
                mod = (total - 10) // 2
                sign = "+" if mod >= 0 else ""
                adj_str = f" (+{adj})" if adj > 0 else ""
                lines.append(
                    f"  {ab.value} {ABILITY_ZH[ab]:<4} {total:>2}{adj_str:<6} 修正值 {sign}{mod}"
                )
        else:
            lines.append("屬性值：—")

        # 技能（合併顯示）
        cls_skills = d.get("class_skills", [])
        if cls_skills:
            sk_str = ", ".join(SKILL_ZH.get(s, s.value) for s in cls_skills)
            lines.append(f"\n技能熟練：{sk_str}")

        # 裝備（步驟 6 以後才顯示）
        if self._step < 6:
            preview.update("\n".join(lines))
            return
        bg_eq = d.get("bg_equipment", "A")
        cls_eq = d.get("class_equipment", "A")
        bg_id_eq = d["background"]
        cc_eq = d["char_class"]
        equip_lines = []
        if bg_id_eq and bg_id_eq in BACKGROUND_REGISTRY:
            bg_data = BACKGROUND_REGISTRY[bg_id_eq]
            eq_text = bg_data.equipment_a if bg_eq == "A" else bg_data.equipment_b
            equip_lines.append(f"  背景（{bg_eq}）：{eq_text}")
        if cc_eq and cc_eq in CLASS_DISPLAY:
            cd_data = CLASS_DISPLAY[cc_eq]
            eq_text = cd_data.equipment_a if cls_eq == "A" else cd_data.equipment_b
            equip_lines.append(f"  職業（{cls_eq}）：{eq_text}")
        if equip_lines:
            lines.append("\n裝備：")
            lines.extend(equip_lines)

        # 法術
        cantrips = d.get("cantrips", [])
        spells = d.get("spells", [])
        if cantrips or spells:
            lines.append("")
            all_spell_data = _load_spells()
            spell_lookup = {s["en_name"]: s for s in all_spell_data}
            if cantrips:
                names = []
                for en in cantrips:
                    sd = spell_lookup.get(en)
                    names.append(sd["name"] if sd else en)
                lines.append(f"戲法：{', '.join(names)}")
            if spells:
                names = []
                for en in spells:
                    sd = spell_lookup.get(en)
                    names.append(sd["name"] if sd else en)
                lines.append(f"1 環法術：{', '.join(names)}")
            # 所有選中的法術都顯示詳情
            all_selected = list(cantrips) + list(spells)
            for en in all_selected:
                sd = spell_lookup.get(en)
                if sd:
                    dt = DAMAGE_TYPE_ZH.get(sd.get("damage_type", ""), "")
                    et = EFFECT_TYPE_ZH.get(sd.get("effect_type", ""), "")
                    tag = dt if dt else et
                    lines.append(f"  ▸ {sd['name']}（{tag}）：{sd.get('description', '')[:60]}")

        preview.update("\n".join(lines))

    # ── Build helper ──────────────────────────────────────────────────────────

    def _build_character(self) -> Character:
        """從 _data 建出 Character。"""
        d = self._data
        builder = CharacterBuilder()
        builder.set_name(d["name"] or "冒險者")
        builder.set_background(d["background"] or "Unknown")
        builder.set_species(d["species"] or "Unknown")
        builder.set_class(d["char_class"])

        # 屬性值：先建基礎值，再用 bone_engine 套用背景加值（含上限 20 檢查）
        base = d["scores"]
        base_scores = AbilityScores(
            STR=base.get(Ability.STR, 10),
            DEX=base.get(Ability.DEX, 10),
            CON=base.get(Ability.CON, 10),
            INT=base.get(Ability.INT, 10),
            WIS=base.get(Ability.WIS, 10),
            CHA=base.get(Ability.CHA, 10),
        )
        bg_adj = d.get("bg_adjust", {})
        if bg_adj:
            try:
                final_scores = apply_background_bonus(base_scores, bg_adj)
            except ValueError:
                # 加值導致超過 20 等異常，退回基礎值
                final_scores = base_scores
        else:
            final_scores = base_scores
        builder.set_ability_scores(final_scores)

        # 技能：背景（固定） + 專長（選位） + 職業（選位）
        all_skills: list[Skill] = []
        bg_id = d["background"]
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            for s in BACKGROUND_REGISTRY[bg_id].skill_proficiencies:
                if s not in all_skills:
                    all_skills.append(s)
        for s in d.get("feat_skills", []):
            if s not in all_skills:
                all_skills.append(s)
        for s in d.get("class_skills", []):
            if s not in all_skills:
                all_skills.append(s)

        # 確保數量至少足夠 CharacterBuilder
        cc = d["char_class"]
        if cc in CLASS_REGISTRY:
            needed = CLASS_REGISTRY[cc].num_skills
            cls_only = [
                s
                for s in all_skills
                if bg_id not in BACKGROUND_REGISTRY
                or s not in BACKGROUND_REGISTRY[bg_id].skill_proficiencies
            ]
            if len(cls_only) < needed:
                available = list(CLASS_REGISTRY[cc].skill_choices)
                for s in available:
                    if s not in all_skills and len(cls_only) < needed:
                        all_skills.append(s)
                        cls_only.append(s)

        builder.set_skills(all_skills)

        # 護甲：由 ClassDisplayData.default_armor 決定（選裝備包 A 時使用預設）
        equip_choice = d.get("class_equipment", "A")
        if equip_choice == "A" and cc in CLASS_DISPLAY:
            cd = CLASS_DISPLAY[cc]
            if cd.default_armor != "none":
                builder.set_armor(cd.default_armor)

        return builder.build()

    def _format_full_summary(self, char: Character) -> str:
        """格式化完整角色卡摘要。"""
        d = self._data
        cc = d["char_class"]
        bg_id = d["background"]
        sp_id = d["species"]

        cd = CLASS_DISPLAY.get(cc)
        bg = BACKGROUND_REGISTRY.get(bg_id) if bg_id else None
        sd = SPECIES_REGISTRY.get(sp_id) if sp_id else None

        lines = [
            f"角色名稱：{char.name}",
            f"職業：{cd.name_zh if cd else cc}　等級：{char.level}",
            f"背景：{bg.name_zh if bg else bg_id}　種族：{sd.name_zh if sd else sp_id}",
        ]

        # 血統
        lin = d.get("lineage")
        if lin and sd and sd.lineage_options:
            lo = next((l for l in sd.lineage_options if l.id == lin), None)
            if lo:
                lines.append(f"血統：{lo.name_zh}（{lo.name_en}）")

        lines += ["", "── 屬性值 ──"]
        bg_adj = d.get("bg_adjust", {})
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
            f"被動感知：{char.passive_perception}　先攻：{'+' if char.ability_scores.modifier(Ability.DEX) >= 0 else ''}{char.ability_scores.modifier(Ability.DEX)}",
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
            feat = ORIGIN_FEAT_REGISTRY.get(bg.feat)
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
        for s in d.get("class_skills", []):
            bonus = char.skill_bonus(s)
            sign = "+" if bonus >= 0 else ""
            lines.append(f"  {SKILL_ZH.get(s, s.value):<8}（{s.value}）{sign}{bonus}  [職業]")

        # 工具熟練
        if bg:
            lines.append(f"\n工具熟練：{bg.tool_proficiency}")

        # 裝備
        lines += ["", "── 起始裝備 ──"]
        bg_eq = d.get("bg_equipment", "A")
        cls_eq = d.get("class_equipment", "A")
        if bg:
            eq_text = bg.equipment_a if bg_eq == "A" else bg.equipment_b
            lines.append(f"  背景：{eq_text}")
        if cd:
            eq_text = cd.equipment_a if cls_eq == "A" else cd.equipment_b
            lines.append(f"  職業：{eq_text}")

        # 種族特性
        if sd:
            lines += ["", "── 種族特性 ──"]
            lines.append(f"  {', '.join(sd.traits)}")
            lines.append(f"  {sd.traits_description}")

        # 戲法與法術
        cantrips = d.get("cantrips", [])
        spells = d.get("spells", [])
        if cantrips or spells:
            lines += ["", "── 法術 ──"]
            if cantrips:
                lines.append(f"  戲法：{', '.join(cantrips)}")
            if spells:
                lines.append(f"  1 環法術：{', '.join(spells)}")
            if cc in CLASS_REGISTRY and CLASS_REGISTRY[cc].spellcasting_ability:
                sa = CLASS_REGISTRY[cc].spellcasting_ability
                lines.append(f"  施法屬性：{ABILITY_ZH.get(sa, '')}（{sa.value}）")

        # 1 級職業特性
        if cd and cd.features_1st:
            lines += ["", "── 1 級職業特性 ──"]
            for feat_name in cd.features_1st:
                lines.append(f"  • {feat_name}")

        return "\n".join(lines)

    # ── Data collection ───────────────────────────────────────────────────────

    def _collect_step_data(self, step: int) -> None:
        """讀取當步 widget → _data。驗證失敗 raise ValueError。"""
        if step == 1:
            self._collect_class()
        elif step == 2:
            self._collect_background()
        elif step == 3:
            self._collect_species()
        elif step == 4:
            self._collect_ability_scores()
        elif step == 5:
            self._collect_skills()
        elif step == 6:
            self._collect_equipment()
        elif step == 7:
            self._collect_spells()
        elif step == 8:
            self._collect_confirm()

    def _collect_class(self) -> None:
        rs = self.query_one("#class-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇職業")
        keys = list(CLASS_DISPLAY.keys())
        new_class = keys[idx]
        if new_class != self._data["char_class"]:
            # 切換職業時清空依賴資料
            self._data["class_skills"] = []
            self._data["_std_assign"] = {}
            self._data["scores"] = {a: 10 for a in Ability}
        self._data["char_class"] = new_class

    def _collect_background(self) -> None:
        rs = self.query_one("#bg-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇背景")
        keys = list(BACKGROUND_REGISTRY.keys())
        self._data["background"] = keys[idx]

    def _collect_species(self) -> None:
        rs = self.query_one("#species-radio", RadioSet)
        idx = rs.pressed_index
        if idx is None:
            raise ValueError("請選擇種族")
        keys = list(SPECIES_REGISTRY.keys())
        sp_id = keys[idx]
        self._data["species"] = sp_id

        # 血統子選項
        sd = SPECIES_REGISTRY[sp_id]
        if sd.lineage_options:
            try:
                lin_rs = self.query_one("#lineage-radio", RadioSet)
                lin_idx = lin_rs.pressed_index
                if lin_idx is not None:
                    self._data["lineage"] = sd.lineage_options[lin_idx].id
                else:
                    # 未選血統，自動選第一個
                    self._data["lineage"] = sd.lineage_options[0].id
            except Exception:
                # RadioSet 尚未渲染（首次選擇種族），預設第一個
                self._data["lineage"] = sd.lineage_options[0].id
        else:
            self._data["lineage"] = ""

    def _collect_ability_scores(self) -> None:
        # 方法
        try:
            mrs = self.query_one("#method-radio", RadioSet)
            idx = mrs.pressed_index
            if idx is not None:
                self._data["score_method"] = ["standard", "point_buy", "roll"][idx]
        except Exception:
            pass

        method = self._data["score_method"]

        if method == "standard":
            self._collect_standard_array()
        elif method == "point_buy":
            self._collect_point_buy()
        elif method == "roll":
            self._collect_roll()

        # 背景調整
        self._collect_bg_adjust()

    def _collect_standard_array(self) -> None:
        # 標準陣列已在 _widgets_standard_array 中自動分配
        # 這裡只確認 scores 已設定
        if not self._data.get("scores") or all(v == 10 for v in self._data["scores"].values()):
            cc = self._data["char_class"]
            if cc in STANDARD_ARRAY_SUGGESTION:
                sug = STANDARD_ARRAY_SUGGESTION[cc]
                assign = dict(zip(ABILITY_ORDER, sug, strict=False))
            else:
                assign = dict(zip(ABILITY_ORDER, STANDARD_ARRAY, strict=False))
            self._data["scores"] = assign
            self._data["_std_assign"] = assign

    def _collect_point_buy(self) -> None:
        scores: dict[Ability, int] = {}
        for ab in ABILITY_ORDER:
            try:
                sel = self.query_one(f"#pb-{ab.value}", Select)
                val = sel.value
                if val is not None and val != Select.BLANK:
                    scores[ab] = int(val)
                else:
                    scores[ab] = 8
            except Exception:
                scores[ab] = 8

        ok, msg = validate_point_buy(scores)
        if not ok:
            raise ValueError(msg)

        self._data["scores"] = scores

    def _collect_roll(self) -> None:
        rolled = self._data.get("_rolled_values", [])
        if not rolled:
            # 首次進入擲骰模式，自動擲骰並分配
            rolled = roll_ability_scores()
            self._data["_rolled_values"] = rolled
            assign = self._auto_assign_rolls(rolled)
            self._data["scores"] = assign
            self._data["_std_assign"] = assign
            raise ValueError("已擲骰並自動分配，請確認結果")

        # 擲骰結果已在 _widgets_roll 中自動分配
        if not self._data.get("scores") or all(v == 10 for v in self._data["scores"].values()):
            assign = self._auto_assign_rolls(rolled)
            self._data["scores"] = assign
            self._data["_std_assign"] = assign

    def _collect_bg_adjust(self) -> None:
        bg_id = self._data["background"]
        if not bg_id or bg_id not in BACKGROUND_REGISTRY:
            return

        bg = BACKGROUND_REGISTRY[bg_id]

        # 調整模式
        try:
            adj_rs = self.query_one("#adjust-mode-radio", RadioSet)
            idx = adj_rs.pressed_index
            if idx is not None:
                self._data["bg_adjust_mode"] = ["+1/+1/+1", "+2/+1"][idx]
        except Exception:
            pass

        mode = self._data["bg_adjust_mode"]

        if mode == "+1/+1/+1":
            self._data["bg_adjust"] = {a: 1 for a in bg.ability_tags}
        elif mode == "+2/+1":
            adj: dict[Ability, int] = {}
            try:
                sel2 = self.query_one("#adj-plus2", Select)
                if isinstance(sel2.value, Ability):
                    adj[sel2.value] = 2
            except Exception:
                pass
            try:
                sel1 = self.query_one("#adj-plus1", Select)
                if isinstance(sel1.value, Ability) and sel1.value not in adj:
                    adj[sel1.value] = 1
            except Exception:
                pass

            if not adj:
                # 預設：第一項 +2，第二項 +1
                adj = {bg.ability_tags[0]: 2, bg.ability_tags[1]: 1}

            self._data["bg_adjust"] = adj

    def _collect_skills(self) -> None:
        cc = self._data["char_class"]
        if not cc or cc not in CLASS_REGISTRY:
            return
        bg_id = self._data["background"]
        bg_skills = (
            list(BACKGROUND_REGISTRY[bg_id].skill_proficiencies)
            if bg_id and bg_id in BACKGROUND_REGISTRY
            else []
        )

        # 合併選位：從單一 skills-list 收集
        feat = self._get_origin_feat()
        feat_count = feat.skill_choice_count if feat and feat.skill_choice_count > 0 else 0
        cls_count = CLASS_REGISTRY[cc].num_skills
        total_picks = feat_count + cls_count

        try:
            sl = self.query_one("#skills-list", SelectionList)
            selected = list(sl.selected)
            if len(selected) != total_picks:
                raise ValueError(f"需選 {total_picks} 項技能，已選 {len(selected)}")
            # 確認無重複且不在背景中
            bg_set = set(bg_skills)
            for s in selected:
                if s in bg_set:
                    raise ValueError(f"技能 {SKILL_ZH.get(s, s.value)} 已由背景提供")
            self._data["class_skills"] = selected
            self._data["feat_skills"] = []  # 不再分開存，統一在 class_skills
        except ValueError:
            raise
        except Exception:
            pass

    def _collect_equipment(self) -> None:
        try:
            bg_rs = self.query_one("#bg-equip-radio", RadioSet)
            idx = bg_rs.pressed_index
            if idx is not None:
                self._data["bg_equipment"] = "A" if idx == 0 else "B"
        except Exception:
            pass
        try:
            cls_rs = self.query_one("#cls-equip-radio", RadioSet)
            idx = cls_rs.pressed_index
            if idx is not None:
                self._data["class_equipment"] = "A" if idx == 0 else "B"
        except Exception:
            pass

    def _collect_spells(self) -> None:
        cc = self._data["char_class"]
        cd = CLASS_DISPLAY.get(cc) if cc else None
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

        # 只在有法術資料庫時驗證數量
        has_cantrips_db = bool(_spells_for_class(cc, 0)) if cd.num_cantrips > 0 else False
        has_spells_db = bool(_spells_for_class(cc, 1)) if cd.num_prepared_spells > 0 else False
        ok, msg = validate_spell_selection(
            cantrips_sel if has_cantrips_db else ["_"] * cd.num_cantrips,
            spells_sel if has_spells_db else ["_"] * cd.num_prepared_spells,
            cd.num_cantrips,
            cd.num_prepared_spells,
        )
        if not ok:
            raise ValueError(msg)

        self._data["cantrips"] = cantrips_sel
        self._data["spells"] = spells_sel

    def _collect_confirm(self) -> None:
        try:
            name_input = self.query_one("#name-input", Input)
            val = name_input.value.strip()
            if not val:
                raise ValueError("角色名稱不能為空")
            self._data["name"] = val
        except ValueError:
            raise
        except Exception:
            raise ValueError("角色名稱不能為空")

    # ── Actions ───────────────────────────────────────────────────────────────

    async def action_next_step(self) -> None:
        step = self._step
        if step == TOTAL_STEPS:
            self._finish()
            return
        try:
            self._collect_step_data(step)
        except ValueError as e:
            self.notify(str(e), severity="error")
            # 擲骰模式首次進入需重新渲染
            if "已擲骰" in str(e):
                await self._render_step()
                self._update_preview()
            return

        # 非施法職業跳過步驟 7
        if self._step == 6:
            cc = self._data["char_class"]
            cd = CLASS_DISPLAY.get(cc)
            if cd and cd.num_cantrips == 0 and cd.num_prepared_spells == 0:
                self._step = 7  # 會被 += 1 變成 8

        self._step += 1
        await self._render_step()
        self._update_preview()
        self._update_title()

    async def action_prev_step(self) -> None:
        if self._step > 1:
            # 非施法職業從步驟 8 退回跳過 7
            if self._step == 8:
                cc = self._data["char_class"]
                cd = CLASS_DISPLAY.get(cc)
                if cd and cd.num_cantrips == 0 and cd.num_prepared_spells == 0:
                    self._step = 7  # 會被 -= 1 變成 6

            self._step -= 1
            await self._render_step()
            self._update_preview()
            self._update_title()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("next-btn", "confirm-btn"):
            await self.action_next_step()
        elif event.button.id == "reroll-btn":
            self._data["_rolled_values"] = roll_ability_scores()
            self._data["_std_assign"] = {a: 0 for a in Ability}
            await self._render_step()

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Select 變更時即時更新。"""
        sel_id = event.select.id or ""
        if sel_id.startswith("pb-"):
            # 即時更新 scores 和計算剩餘點數
            total_cost = 0
            scores: dict[Ability, int] = {}
            for ab in ABILITY_ORDER:
                try:
                    sel = self.query_one(f"#pb-{ab.value}", Select)
                    val = sel.value
                    if isinstance(val, int):
                        scores[ab] = val
                        total_cost += POINT_BUY_COSTS.get(val, 0)
                    else:
                        scores[ab] = 8
                except Exception:
                    scores[ab] = 8
            self._data["scores"] = scores
            remaining = POINT_BUY_BUDGET - total_cost
            self._update_preview()
            severity = "error" if remaining < 0 else "information"
            self.notify(f"剩餘點數：{remaining}/{POINT_BUY_BUDGET}", severity=severity)
        elif sel_id in ("adj-plus2", "adj-plus1"):
            # +2/+1 不可選同一屬性
            try:
                sel2 = self.query_one("#adj-plus2", Select)
                sel1 = self.query_one("#adj-plus1", Select)
                if (isinstance(sel2.value, Ability) and isinstance(sel1.value, Ability)
                        and sel2.value == sel1.value):
                    self.notify("+2 和 +1 不能選同一屬性！", severity="error")
                else:
                    # 即時更新 bg_adjust 資料
                    adj: dict[Ability, int] = {}
                    if isinstance(sel2.value, Ability):
                        adj[sel2.value] = 2
                    if isinstance(sel1.value, Ability) and sel1.value not in adj:
                        adj[sel1.value] = 1
                    self._data["bg_adjust"] = adj
                    self._update_preview()
            except Exception:
                pass

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        """技能/法術勾選時即時更新預覽。"""
        sl_id = event.selection_list.id or ""
        if sl_id == "skills-list":
            self._data["class_skills"] = list(event.selection_list.selected)
            self._update_preview()
        elif sl_id == "cantrip-list":
            self._data["cantrips"] = list(event.selection_list.selected)
            self._update_preview()
        elif sl_id == "spell-list":
            self._data["spells"] = list(event.selection_list.selected)
            self._update_preview()

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
                self._data["char_class"] = keys[idx]
                self._update_preview()

        elif rs_id == "bg-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(BACKGROUND_REGISTRY.keys())
                self._data["background"] = keys[idx]
                self._update_preview()

        elif rs_id == "species-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                keys = list(SPECIES_REGISTRY.keys())
                new_sp = keys[idx]
                old_sp = self._data.get("species", "")
                self._data["species"] = new_sp
                self._data["lineage"] = ""
                self._update_preview()
                # 切換種族時重新渲染（顯示或隱藏血統選項）
                if new_sp != old_sp:
                    await self._render_step()

        elif rs_id == "lineage-radio":
            sp_id = self._data.get("species", "")
            if sp_id in SPECIES_REGISTRY:
                sd = SPECIES_REGISTRY[sp_id]
                idx = event.radio_set.pressed_index
                if idx is not None and idx < len(sd.lineage_options):
                    self._data["lineage"] = sd.lineage_options[idx].id
                    self._update_preview()

        elif rs_id == "adjust-mode-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                mode = ["+1/+1/+1", "+2/+1"][idx]
                self._data["bg_adjust_mode"] = mode
                # 即時更新 bg_adjust
                bg_id = self._data["background"]
                if mode == "+1/+1/+1" and bg_id in BACKGROUND_REGISTRY:
                    bg = BACKGROUND_REGISTRY[bg_id]
                    self._data["bg_adjust"] = {a: 1 for a in bg.ability_tags}
                await self._render_step()

        elif rs_id == "bg-equip-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                self._data["bg_equipment"] = "A" if idx == 0 else "B"
                self._update_preview()

        elif rs_id == "cls-equip-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                self._data["class_equipment"] = "A" if idx == 0 else "B"
                self._update_preview()

        elif rs_id == "method-radio":
            idx = event.radio_set.pressed_index
            if idx is not None:
                self._data["score_method"] = ["standard", "point_buy", "roll"][idx]
                await self._render_step()

    def _finish(self) -> None:
        try:
            self._collect_step_data(TOTAL_STEPS)
            char = self._build_character()
            # 自動存檔角色卡
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
