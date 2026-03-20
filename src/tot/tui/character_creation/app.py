"""T.O.T. 角色建造 TUI — 6 步驟 Wizard 介面。"""

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
    SelectionList,
    Static,
)

from tot.gremlins.bone_engine.character import CLASS_REGISTRY, CharacterBuilder
from tot.models.creature import AbilityScores, Character
from tot.models.enums import Ability, Skill

# ── 資料常數 ──────────────────────────────────────────────────────────────────

PHB_BACKGROUNDS = [
    "Acolyte",
    "Artisan",
    "Charlatan",
    "Criminal",
    "Entertainer",
    "Farmer",
    "Guard",
    "Guide",
    "Hermit",
    "Merchant",
    "Noble",
    "Sage",
    "Sailor",
    "Scribe",
    "Soldier",
    "Wayfarer",
]

PHB_SPECIES = [
    "Aasimar",
    "Dragonborn",
    "Dwarf",
    "Elf",
    "Gnome",
    "Goliath",
    "Half-Orc",
    "Halfling",
    "Human",
    "Tiefling",
]

ARMOR_TYPES = ["none", "light", "medium", "heavy"]

STEP_TITLES = {
    1: "角色名稱",
    2: "選擇背景",
    3: "選擇種族",
    4: "選擇職業",
    5: "設定屬性值",
    6: "選擇技能",
    7: "確認建角",
}

# (Ability 列舉成員, 顯示標籤) 配對清單
ABILITY_ROWS: list[tuple[Ability, str]] = [
    (Ability.STR, "STR 力量"),
    (Ability.DEX, "DEX 敏捷"),
    (Ability.CON, "CON 體質"),
    (Ability.INT, "INT 智力"),
    (Ability.WIS, "WIS 感知"),
    (Ability.CHA, "CHA 魅力"),
]


# ── 主 App ────────────────────────────────────────────────────────────────────


class CharacterCreationApp(App[Character | None]):
    """T.O.T. 角色建造 Wizard。走完 6 步後以 exit(result=Character) 回傳角色。"""

    TITLE = "T.O.T. 角色建造"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        height: 1fr;
    }

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

    .ability-label {
        width: 14;
        height: 1;
        margin-top: 1;
    }

    .ability-input {
        width: 8;
        height: 3;
    }

    #next-btn, #confirm-btn {
        margin-top: 1;
        width: 100%;
    }

    RadioSet {
        height: auto;
    }

    SelectionList {
        height: auto;
        max-height: 20;
    }
    """

    BINDINGS = [
        Binding("escape", "prev_step", "上一步"),
        Binding("ctrl+n", "next_step", "確認→下一步"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._step: int = 1
        # 儲存所有已填入的資料（不依賴 builder 的步驟鎖）
        self._data: dict = {
            "name": "",
            "background": "",
            "species": "",
            "char_class": "",
            "scores": {a: 10 for a in Ability},
            "armor_type": "none",
            "subclass": "",
            "skills": [],
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
        step = self._step
        if step <= 6:
            self.title = f"T.O.T. 角色建造  ─  步驟 {step}/6：{STEP_TITLES[step]}"
        else:
            self.title = "T.O.T. 角色建造  ─  確認建角"

    # ── Step rendering ────────────────────────────────────────────────────────

    async def _render_step(self) -> None:
        """清除左側面板，重建當步的 widgets。"""
        left = self.query_one("#left-panel", Vertical)
        await left.remove_children()

        step = self._step
        widgets: list = []

        # 步驟標題
        step_label = f"步驟 {step}/6：{STEP_TITLES[step]}" if step <= 6 else "步驟 7：確認建角"
        widgets.append(Label(step_label, id="step-title"))

        if step == 1:
            widgets.append(
                Input(
                    value=self._data["name"],
                    placeholder="輸入角色名稱...",
                    id="name-input",
                )
            )

        elif step == 2:
            bg = self._data["background"]
            btns = [RadioButton(b, value=(b == bg)) for b in PHB_BACKGROUNDS]
            widgets.append(RadioSet(*btns, id="bg-radio"))

        elif step == 3:
            sp = self._data["species"]
            btns = [RadioButton(s, value=(s == sp)) for s in PHB_SPECIES]
            widgets.append(RadioSet(*btns, id="species-radio"))

        elif step == 4:
            classes = list(CLASS_REGISTRY.keys())
            cc = self._data["char_class"]
            btns = [RadioButton(c, value=(c == cc)) for c in classes]
            widgets.append(RadioSet(*btns, id="class-radio"))

        elif step == 5:
            widgets.append(Label("── 屬性值 ──"))
            for ability, label_text in ABILITY_ROWS:
                widgets.append(Label(label_text, classes="ability-label"))
                widgets.append(
                    Input(
                        value=str(self._data["scores"].get(ability, 10)),
                        id=f"score-{ability.value}",
                        classes="ability-input",
                    )
                )
            widgets.append(Label("── 護甲類型（可選）──"))
            armor_btns = [
                RadioButton(a, value=(a == self._data["armor_type"])) for a in ARMOR_TYPES
            ]
            widgets.append(RadioSet(*armor_btns, id="armor-radio"))
            widgets.append(Label("子職業（可選，可留空）"))
            widgets.append(
                Input(
                    value=self._data["subclass"],
                    placeholder="子職業名稱...",
                    id="subclass-input",
                )
            )

        elif step == 6:
            char_class = self._data["char_class"]
            if char_class and char_class in CLASS_REGISTRY:
                cls_data = CLASS_REGISTRY[char_class]
                available = list(cls_data.skill_choices)
                num = cls_data.num_skills
            else:
                available = list(Skill)
                num = 2
            widgets.append(Label(f"請選擇 {num} 個技能（{char_class}）"))
            selected = self._data["skills"]
            options = [(s.value, s, s in selected) for s in available]
            widgets.append(SelectionList(*options, id="skills-list"))

        elif step == 7:
            try:
                char = self._build_character()
                summary = self._format_summary(char)
                widgets.append(Static(summary))
                widgets.append(Button("確認建角 ✓", id="confirm-btn", variant="success"))
            except ValueError as e:
                widgets.append(Static(f"[red]錯誤：{e}[/red]"))
            await left.mount(*widgets)
            return  # 步驟 7 不需要 next-btn

        widgets.append(Button("確認 →  (Ctrl+N)", id="next-btn", variant="primary"))
        await left.mount(*widgets)

    # ── Preview panel ─────────────────────────────────────────────────────────

    def _update_preview(self) -> None:
        """更新右側預覽面板。"""
        d = self._data
        preview = self.query_one("#preview-panel", Static)

        lines = [
            "角色預覽",
            "─" * 28,
            f"名稱  : {d['name'] or '—'}",
            f"背景  : {d['background'] or '—'}",
            f"種族  : {d['species'] or '—'}",
            f"職業  : {d['char_class'] or '—'}",
        ]

        scores = d["scores"]
        if any(v != 10 for v in scores.values()):
            parts = []
            for ab, _ in ABILITY_ROWS:
                val = scores.get(ab, 10)
                mod = (val - 10) // 2
                sign = "+" if mod >= 0 else ""
                parts.append(f"{ab.value}:{val}({sign}{mod})")
            lines.append("屬性  : " + "  ".join(parts[:3]))
            lines.append("        " + "  ".join(parts[3:]))
        else:
            lines.append("屬性  : —")

        if d["skills"]:
            lines.append(f"技能  : {', '.join(s.value for s in d['skills'])}")
        else:
            lines.append("技能  : —")

        # 計算 HP/AC（只有必填欄位都有值時才嘗試）
        if d["name"] and d["char_class"] and d["skills"]:
            try:
                char = self._build_character()
                lines += [
                    "",
                    "─" * 28,
                    f"HP    : {char.hp_current}    AC : {char.ac}",
                    f"被動感知 : {char.passive_perception}",
                ]
            except Exception:
                pass

        preview.update("\n".join(lines))

    # ── Build helper ──────────────────────────────────────────────────────────

    def _build_character(self) -> Character:
        """從 _data 呼叫 CharacterBuilder 建出完整角色。"""
        d = self._data
        builder = CharacterBuilder()
        builder.set_name(d["name"] or "角色")
        builder.set_background(d["background"] or "Unknown")
        builder.set_species(d["species"] or "Unknown")
        builder.set_class(d["char_class"])

        s = d["scores"]
        ability_scores = AbilityScores(
            STR=s.get(Ability.STR, 10),
            DEX=s.get(Ability.DEX, 10),
            CON=s.get(Ability.CON, 10),
            INT=s.get(Ability.INT, 10),
            WIS=s.get(Ability.WIS, 10),
            CHA=s.get(Ability.CHA, 10),
        )
        builder.set_ability_scores(ability_scores)

        # 技能：若選擇數不符則以職業前 N 項補足（供預覽用）
        char_class = d["char_class"]
        skills = list(d["skills"])
        if char_class in CLASS_REGISTRY:
            num = CLASS_REGISTRY[char_class].num_skills
            if len(skills) != num:
                available = list(CLASS_REGISTRY[char_class].skill_choices)
                skills = available[:num]
        builder.set_skills(skills)

        if d["armor_type"] and d["armor_type"] != "none":
            builder.set_armor(d["armor_type"])
        if d["subclass"]:
            builder.set_subclass(d["subclass"])

        return builder.build()

    def _format_summary(self, char: Character) -> str:
        """格式化步驟 7 的完整角色卡文字。"""
        lines = [
            f"角色名稱：{char.name}",
            f"職業：{char.char_class}　背景：{char.background}　種族：{char.species}",
            "",
            "── 屬性值 ──",
        ]
        for ab, label in ABILITY_ROWS:
            val = char.ability_scores.score(ab)
            mod = char.ability_scores.modifier(ab)
            sign = "+" if mod >= 0 else ""
            lines.append(f"  {label:<14} {val:>2}  ({sign}{mod})")

        lines += [
            "",
            f"HP     : {char.hp_current}",
            f"AC     : {char.ac}",
            f"被動感知 : {char.passive_perception}",
            "",
            "── 技能熟練 ──",
        ]
        for skill in char.skill_proficiencies:
            bonus = char.skill_bonus(skill)
            sign = "+" if bonus >= 0 else ""
            lines.append(f"  {skill.value:<22} {sign}{bonus}")

        return "\n".join(lines)

    # ── Step data collection ──────────────────────────────────────────────────

    def _collect_step_data(self, step: int) -> None:
        """讀取當步 widget 的值存入 _data。驗證失敗則 raise ValueError。"""
        if step == 1:
            val = self.query_one("#name-input", Input).value.strip()
            if not val:
                raise ValueError("角色名稱不能為空")
            self._data["name"] = val

        elif step == 2:
            rs = self.query_one("#bg-radio", RadioSet)
            idx = rs.pressed_index
            if idx is None:
                raise ValueError("請選擇背景")
            self._data["background"] = PHB_BACKGROUNDS[idx]

        elif step == 3:
            rs = self.query_one("#species-radio", RadioSet)
            idx = rs.pressed_index
            if idx is None:
                raise ValueError("請選擇種族")
            self._data["species"] = PHB_SPECIES[idx]

        elif step == 4:
            rs = self.query_one("#class-radio", RadioSet)
            idx = rs.pressed_index
            if idx is None:
                raise ValueError("請選擇職業")
            self._data["char_class"] = list(CLASS_REGISTRY.keys())[idx]

        elif step == 5:
            scores: dict[Ability, int] = {}
            for ability, label_text in ABILITY_ROWS:
                widget = self.query_one(f"#score-{ability.value}", Input)
                raw = widget.value.strip()
                try:
                    val = int(raw)
                except ValueError as exc:
                    raise ValueError(f"{label_text} 必須是整數") from exc
                if not (1 <= val <= 30):
                    raise ValueError(f"{label_text} 必須在 1–30 之間，收到 {val}")
                scores[ability] = val
            self._data["scores"] = scores

            # 護甲（可選）
            try:
                armor_rs = self.query_one("#armor-radio", RadioSet)
                idx = armor_rs.pressed_index
                if idx is not None:
                    self._data["armor_type"] = ARMOR_TYPES[idx]
            except Exception:
                pass

            # 子職業（可選）
            try:
                sub_inp = self.query_one("#subclass-input", Input)
                self._data["subclass"] = sub_inp.value.strip()
            except Exception:
                pass

        elif step == 6:
            sl = self.query_one("#skills-list", SelectionList)
            selected = list(sl.selected)
            char_class = self._data["char_class"]
            if char_class in CLASS_REGISTRY:
                num = CLASS_REGISTRY[char_class].num_skills
                if len(selected) != num:
                    raise ValueError(f"請選擇 {num} 個技能（目前選了 {len(selected)} 個）")
            self._data["skills"] = selected

    # ── Actions ───────────────────────────────────────────────────────────────

    async def action_next_step(self) -> None:
        """驗證 → 儲存 → 前往下一步。"""
        step = self._step
        if step == 7:
            self._finish()
            return
        try:
            self._collect_step_data(step)
        except ValueError as e:
            self.notify(str(e), severity="error")
            return
        self._step += 1
        await self._render_step()
        self._update_preview()
        self._update_title()

    async def action_prev_step(self) -> None:
        """退回上一步。"""
        if self._step > 1:
            self._step -= 1
            await self._render_step()
            self._update_preview()
            self._update_title()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按鈕點擊 → 委派 action。"""
        if event.button.id in ("next-btn", "confirm-btn"):
            await self.action_next_step()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Input 按下 Enter → 自動前往下一步（僅名稱欄位適用）。"""
        if event.input.id == "name-input":
            await self.action_next_step()

    def _finish(self) -> None:
        """呼叫 builder 建出角色並退出 app，回傳 Character。"""
        try:
            char = self._build_character()
            self.exit(result=char)
        except ValueError as e:
            self.notify(str(e), severity="error")
