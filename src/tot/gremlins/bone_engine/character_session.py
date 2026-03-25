"""建角狀態機——純規則邏輯，不依賴任何 UI 元件。

TUI 和未來的 LLM Narrator 都呼叫同一套 API。
所有決策都在 set_*() 中立即生效並重算衍生值。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tot.data.classes import CLASS_DISPLAY, STANDARD_ARRAY_SUGGESTION
from tot.data.feats import ORIGIN_FEAT_REGISTRY, FeatData
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
    validate_spell_selection,
)
from tot.gremlins.bone_engine.dice import roll_ability_scores
from tot.gremlins.bone_engine.spells import list_spells
from tot.models.creature import AbilityScores, Character
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

DAMAGE_TYPE_ZH: dict[str, str] = {
    "Fire": "火焰",
    "Cold": "寒冷",
    "Lightning": "閃電",
    "Thunder": "雷鳴",
    "Acid": "酸液",
    "Poison": "毒素",
    "Necrotic": "黯蝕",
    "Radiant": "光輝",
    "Force": "力場",
    "Psychic": "心靈",
    "Bludgeoning": "鈍擊",
    "Piercing": "穿刺",
    "Slashing": "揮砍",
}

EFFECT_TYPE_ZH: dict[str, str] = {
    "damage": "傷害",
    "healing": "治療",
    "condition": "狀態",
    "buff": "增益",
    "utility": "功能",
}


# ── 建角資料 ──────────────────────────────────────────────────────────────────


@dataclass
class CharacterCreationData:
    """建角過程中的所有玩家選擇。"""

    char_class: str = ""
    background: str = ""
    species: str = ""
    lineage: str = ""
    score_method: str = "standard"  # "standard" / "point_buy" / "roll"
    scores: dict = field(default_factory=lambda: {a: 10 for a in Ability})
    bg_adjust_mode: str = "+1/+1/+1"  # "+1/+1/+1" or "+2/+1"
    bg_adjust: dict = field(default_factory=dict)  # {Ability: int}
    skills: list = field(default_factory=list)  # 專長 + 職業選位（不含背景固定）
    bg_equipment: str = ""  # "A" / "B"，空 = 未選
    class_equipment: str = ""  # "A" / "B"，空 = 未選
    cantrips: list = field(default_factory=list)  # en_name 列表
    spells: list = field(default_factory=list)  # en_name 列表
    name: str = ""
    # 內部暫存（各方法的 scores 持久化，切換方法時保留）
    rolled_values: list = field(default_factory=list)
    _scores_point_buy: dict = field(default_factory=dict)
    _scores_roll: dict = field(default_factory=dict)


# ── 狀態機 ────────────────────────────────────────────────────────────────────


class CharacterCreationSession:
    """建角狀態機。TUI 和 LLM 都呼叫同一套。不依賴任何 UI 元件。"""

    def __init__(self) -> None:
        self.data = CharacterCreationData()

    # ── 設定選擇 ──────────────────────────────────────────────────────────────

    def set_class(self, class_id: str) -> None:
        """設定職業。切換時清空依賴資料（skills, scores, rolled_values）。"""
        if class_id not in CLASS_REGISTRY:
            raise ValueError(f"未知職業: {class_id!r}")
        if class_id != self.data.char_class:
            self.data.skills = []
            self.data.scores = {a: 10 for a in Ability}
            self.data.rolled_values = []
            self.data.cantrips = []
            self.data.spells = []
        self.data.char_class = class_id

    def set_background(self, bg_id: str) -> None:
        """設定背景。切換時清空 skills。"""
        if bg_id not in BACKGROUND_REGISTRY:
            raise ValueError(f"未知背景: {bg_id!r}")
        if bg_id != self.data.background:
            self.data.skills = []
            # 重設背景調整
            self.data.bg_adjust_mode = "+1/+1/+1"
            self.data.bg_adjust = {}
        self.data.background = bg_id
        # 預設 +1/+1/+1
        bg = BACKGROUND_REGISTRY[bg_id]
        if not self.data.bg_adjust:
            self.data.bg_adjust = {a: 1 for a in bg.ability_tags}

    def set_species(self, species_id: str, lineage_id: str = "") -> None:
        """設定種族。若有血統選項但未指定，自動選第一個。"""
        if species_id not in SPECIES_REGISTRY:
            raise ValueError(f"未知種族: {species_id!r}")
        self.data.species = species_id
        sd = SPECIES_REGISTRY[species_id]
        if sd.lineage_options:
            if lineage_id:
                # 驗證 lineage_id 合法
                valid = {lo.id for lo in sd.lineage_options}
                if lineage_id not in valid:
                    raise ValueError(f"種族 {species_id} 無血統 {lineage_id!r}，可選：{valid}")
                self.data.lineage = lineage_id
            else:
                self.data.lineage = sd.lineage_options[0].id
        else:
            self.data.lineage = ""

    def set_ability_method(self, method: str) -> None:
        """設定屬性值生成方式。"standard" / "point_buy" / "roll"。

        切換方法時保存當前 scores 到對應暫存，恢復時載回。
        standard：自動帶入 STANDARD_ARRAY_SUGGESTION[class]。
        point_buy：首次預設標準陣列配法，之後恢復上次設定。
        roll：若尚無 rolled_values，自動擲骰並按職業優先度分配。
        """
        if method not in ("standard", "point_buy", "roll"):
            raise ValueError(f"不支援的屬性生成方式: {method!r}")

        # 保存當前方法的 scores
        old_method = self.data.score_method
        if old_method == "point_buy":
            self.data._scores_point_buy = dict(self.data.scores)
        elif old_method == "roll":
            self.data._scores_roll = dict(self.data.scores)

        self.data.score_method = method

        if method == "standard":
            self._apply_standard_array()
        elif method == "point_buy":
            if self.data._scores_point_buy:
                # 恢復上次的點數購買設定
                self.data.scores = dict(self.data._scores_point_buy)
            else:
                # 首次：預設標準陣列配法
                self._apply_standard_array()
                self.data._scores_point_buy = dict(self.data.scores)
        elif method == "roll":
            if self.data._scores_roll:
                # 恢復上次的擲骰分配
                self.data.scores = dict(self.data._scores_roll)
            elif not self.data.rolled_values:
                self.reroll_abilities()
            else:
                self._auto_assign_rolls(self.data.rolled_values)

    def set_point_buy_score(self, ability: Ability, value: int) -> None:
        """設定購點法的單一屬性值。"""
        if value not in POINT_BUY_COSTS:
            raise ValueError(f"{ability}: {value} 超出購點範圍（8-15）")
        self.data.scores[ability] = value

    def reroll_abilities(self) -> list[int]:
        """擲 6 組 4d6 取高 3，按職業優先度自動分配。回傳擲骰結果。"""
        rolled = roll_ability_scores()
        self.data.rolled_values = rolled
        self._auto_assign_rolls(rolled)
        return rolled

    def set_bg_adjust_mode(self, mode: str) -> None:
        """設定背景屬性調整模式。"+1/+1/+1" 或 "+2/+1"。"""
        if mode not in ("+1/+1/+1", "+2/+1"):
            raise ValueError(f"不支援的調整模式: {mode!r}")
        self.data.bg_adjust_mode = mode

        bg_id = self.data.background
        if not bg_id or bg_id not in BACKGROUND_REGISTRY:
            return

        bg = BACKGROUND_REGISTRY[bg_id]
        if mode == "+1/+1/+1":
            self.data.bg_adjust = {a: 1 for a in bg.ability_tags}
        else:
            # +2/+1 預設：第一項 +2，第二項 +1
            self.data.bg_adjust = {
                bg.ability_tags[0]: 2,
                bg.ability_tags[1]: 1,
            }

    def set_bg_adjust_plus2(self, ability: Ability) -> None:
        """設定 +2/+1 模式中 +2 的屬性。"""
        bg_id = self.data.background
        if not bg_id or bg_id not in BACKGROUND_REGISTRY:
            raise ValueError("請先選擇背景")
        bg = BACKGROUND_REGISTRY[bg_id]
        if ability not in bg.ability_tags:
            raise ValueError(
                f"{ABILITY_ZH.get(ability, ability.value)} 不在背景 {bg.name_zh} 的可調屬性中"
            )
        # 檢查不可與 +1 同一屬性
        current_plus1 = next((a for a, v in self.data.bg_adjust.items() if v == 1), None)
        if current_plus1 == ability:
            # 清掉衝突的 +1
            self.data.bg_adjust.pop(ability, None)
        # 移除舊的 +2
        old_plus2 = next((a for a, v in self.data.bg_adjust.items() if v == 2), None)
        if old_plus2 is not None:
            del self.data.bg_adjust[old_plus2]
        self.data.bg_adjust[ability] = 2

    def set_bg_adjust_plus1(self, ability: Ability) -> None:
        """設定 +2/+1 模式中 +1 的屬性。"""
        bg_id = self.data.background
        if not bg_id or bg_id not in BACKGROUND_REGISTRY:
            raise ValueError("請先選擇背景")
        bg = BACKGROUND_REGISTRY[bg_id]
        if ability not in bg.ability_tags:
            raise ValueError(
                f"{ABILITY_ZH.get(ability, ability.value)} 不在背景 {bg.name_zh} 的可調屬性中"
            )
        # 檢查不可與 +2 同一屬性
        current_plus2 = next((a for a, v in self.data.bg_adjust.items() if v == 2), None)
        if current_plus2 == ability:
            raise ValueError("+2 和 +1 不能選同一屬性")
        # 移除舊的 +1
        old_plus1 = next((a for a, v in self.data.bg_adjust.items() if v == 1), None)
        if old_plus1 is not None:
            del self.data.bg_adjust[old_plus1]
        self.data.bg_adjust[ability] = 1

    def set_skills(self, skills: list[Skill]) -> None:
        """設定技能選位（專長 + 職業合併）。驗證數量和合法性。"""
        total = self.get_total_skill_picks()
        if len(skills) != total:
            raise ValueError(f"需選 {total} 項技能，收到 {len(skills)}")

        # 驗證不在背景固定技能中
        bg_skills = self._get_bg_skills()
        bg_set = set(bg_skills)
        for s in skills:
            if s in bg_set:
                raise ValueError(f"技能 {SKILL_ZH.get(s, s.value)} 已由背景提供，不可重複選擇")

        # 驗證在可選池中
        available = set(self.get_available_skills())
        for s in skills:
            if s not in available:
                raise ValueError(f"技能 {SKILL_ZH.get(s, s.value)} 不在可選範圍內")

        self.data.skills = list(skills)

    def set_equipment(self, bg_choice: str, cls_choice: str) -> None:
        """設定裝備選擇。bg_choice / cls_choice = "A" 或 "B"。"""
        if bg_choice not in ("A", "B"):
            raise ValueError(f"背景裝備選擇必須是 A 或 B，收到 {bg_choice!r}")
        if cls_choice not in ("A", "B"):
            raise ValueError(f"職業裝備選擇必須是 A 或 B，收到 {cls_choice!r}")
        self.data.bg_equipment = bg_choice
        self.data.class_equipment = cls_choice

    def set_cantrips(self, cantrips: list[str]) -> None:
        """設定戲法選擇（en_name 列表）。"""
        self.data.cantrips = list(cantrips)

    def set_spells(self, spells: list[str]) -> None:
        """設定 1 環法術選擇（en_name 列表）。"""
        self.data.spells = list(spells)

    def set_name(self, name: str) -> None:
        """設定角色名稱。"""
        stripped = name.strip()
        if not stripped:
            raise ValueError("角色名稱不能為空")
        self.data.name = stripped

    # ── 查詢可選項 ────────────────────────────────────────────────────────────

    def get_available_skills(self) -> list[Skill]:
        """取得可選技能清單：(FeatPool ∪ ClassList) - BackgroundSkills。

        職業技能優先排列。
        """
        cc = self.data.char_class
        bg_skill_set = set(self._get_bg_skills())

        feat = self.get_origin_feat()
        feat_count = feat.skill_choice_count if feat and feat.skill_choice_count > 0 else 0

        candidate_set: set[Skill] = set()

        # 專長池
        if feat_count > 0:
            if feat.skill_choice_pool:
                candidate_set.update(feat.skill_choice_pool)
            else:
                candidate_set.update(Skill)  # 全 18 項

        # 職業池
        cls_set: set[Skill] = set()
        if cc and cc in CLASS_REGISTRY:
            cls_set = set(CLASS_REGISTRY[cc].skill_choices)
            candidate_set.update(cls_set)

        # 扣除背景已佔
        candidate_set -= bg_skill_set

        # 職業技能優先排列
        return sorted(candidate_set, key=lambda s: (s not in cls_set, s.value))

    def get_total_skill_picks(self) -> int:
        """取得總技能選位數 = feat_count + cls_count。"""
        feat = self.get_origin_feat()
        feat_count = feat.skill_choice_count if feat and feat.skill_choice_count > 0 else 0
        cls_count = 0
        cc = self.data.char_class
        if cc and cc in CLASS_REGISTRY:
            cls_count = CLASS_REGISTRY[cc].num_skills
        return feat_count + cls_count

    def get_available_cantrips(self) -> list[dict]:
        """取得可選戲法列表（dict 含 name, en_name, damage_type, effect_type 等）。"""
        cc = self.data.char_class
        if not cc:
            return []
        spells = list_spells(level=0, char_class=cc)
        return [_spell_to_dict(s) for s in spells]

    def get_available_spells(self) -> list[dict]:
        """取得可選 1 環法術列表。"""
        cc = self.data.char_class
        if not cc:
            return []
        spells = list_spells(level=1, char_class=cc)
        return [_spell_to_dict(s) for s in spells]

    def get_bg_adjust_tags(self) -> list[Ability]:
        """取得背景的三項可調屬性。"""
        bg_id = self.data.background
        if not bg_id or bg_id not in BACKGROUND_REGISTRY:
            return []
        return list(BACKGROUND_REGISTRY[bg_id].ability_tags)

    def get_point_buy_remaining(self) -> int:
        """取得購點法剩餘點數。"""
        total_cost = sum(POINT_BUY_COSTS.get(self.data.scores.get(a, 8), 0) for a in Ability)
        return POINT_BUY_BUDGET - total_cost

    def get_computed_scores(self) -> dict[Ability, int]:
        """取得最終屬性值（base + bg_adjust），上限 20。"""
        result: dict[Ability, int] = {}
        for ab in Ability:
            base = self.data.scores.get(ab, 10)
            adj = self.data.bg_adjust.get(ab, 0)
            result[ab] = min(base + adj, 20)
        return result

    def get_origin_feat(self) -> FeatData | None:
        """取得當前背景的起源專長資料。"""
        bg_id = self.data.background
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            feat_id = BACKGROUND_REGISTRY[bg_id].feat
            return ORIGIN_FEAT_REGISTRY.get(feat_id)
        return None

    def has_feat_skill_choices(self) -> bool:
        """當前起源專長是否有技能選位。"""
        feat = self.get_origin_feat()
        return feat is not None and feat.skill_choice_count > 0

    # ── 摘要 ──────────────────────────────────────────────────────────────────

    def get_summary(self) -> str:
        """取得角色摘要（純文字）。只輸出有值的區塊，不做步驟判斷。"""
        d = self.data
        lines: list[str] = []

        # 名稱
        if d.name:
            lines.append(f"角色名稱：{d.name}")

        # 職業
        if d.char_class and d.char_class in CLASS_DISPLAY:
            cd = CLASS_DISPLAY[d.char_class]
            cls = CLASS_REGISTRY.get(d.char_class)
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
            lines.append("")

        # 背景
        if d.background and d.background in BACKGROUND_REGISTRY:
            bg = BACKGROUND_REGISTRY[d.background]
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
            lines.append("")

        # 種族
        if d.species and d.species in SPECIES_REGISTRY:
            sd = SPECIES_REGISTRY[d.species]
            lines.append(f"種族：{sd.name_zh}（{sd.name_en}）")
            lines.append(f"  {sd.description}")
            lines.append(f"  體型：{sd.size}　速度：{sd.speed}")
            lines.append(f"  特性：{', '.join(sd.traits)}")
            lines.append(f"  {sd.traits_description}")
            if d.lineage and sd.lineage_options:
                lo = next(
                    (opt for opt in sd.lineage_options if opt.id == d.lineage),
                    None,
                )
                if lo:
                    lines.append(f"  血統：{lo.name_zh}（{lo.name_en}）— {lo.description}")
            lines.append("")

        # 屬性值
        scores = d.scores
        bg_adj = d.bg_adjust
        if any(v != 10 for v in scores.values()):
            lines.append("屬性值：")
            for ab in ABILITY_ORDER:
                base = scores.get(ab, 10)
                adj = bg_adj.get(ab, 0)
                total = min(base + adj, 20)
                mod = (total - 10) // 2
                sign = "+" if mod >= 0 else ""
                adj_str = f" (+{adj})" if adj > 0 else ""
                lines.append(
                    f"  {ab.value} {ABILITY_ZH[ab]:<4} {total:>2}{adj_str:<6} 修正值 {sign}{mod}"
                )
            lines.append("")

        # 技能
        if d.skills:
            sk_str = ", ".join(SKILL_ZH.get(s, s.value) for s in d.skills)
            lines.append(f"技能熟練：{sk_str}")
            lines.append("")

        # 裝備
        equip_lines: list[str] = []
        if d.bg_equipment and d.background and d.background in BACKGROUND_REGISTRY:
            bg_data = BACKGROUND_REGISTRY[d.background]
            eq_text = bg_data.equipment_a if d.bg_equipment == "A" else bg_data.equipment_b
            equip_lines.append(f"  背景（{d.bg_equipment}）：{eq_text}")
        if d.class_equipment and d.char_class and d.char_class in CLASS_DISPLAY:
            cd_data = CLASS_DISPLAY[d.char_class]
            eq_text = cd_data.equipment_a if d.class_equipment == "A" else cd_data.equipment_b
            equip_lines.append(f"  職業（{d.class_equipment}）：{eq_text}")
        if equip_lines:
            lines.append("裝備：")
            lines.extend(equip_lines)
            lines.append("")

        # 戲法與法術
        if d.cantrips or d.spells:
            spell_lines: list[str] = []
            if d.cantrips:
                # 嘗試用法術庫查中文名
                cantrip_names = self._resolve_spell_names(d.cantrips)
                spell_lines.append(f"戲法：{', '.join(cantrip_names)}")
            if d.spells:
                spell_names = self._resolve_spell_names(d.spells)
                spell_lines.append(f"1 環法術：{', '.join(spell_names)}")
            if spell_lines:
                lines.extend(spell_lines)
                lines.append("")

        return "\n".join(lines)

    # ── 建構 ──────────────────────────────────────────────────────────────────

    def validate(self) -> tuple[bool, str]:
        """驗證建角資料是否完整且合法。回傳 (是否通過, 錯誤訊息)。"""
        d = self.data

        if not d.char_class:
            return False, "請選擇職業"
        if d.char_class not in CLASS_REGISTRY:
            return False, f"未知職業: {d.char_class!r}"

        if not d.background:
            return False, "請選擇背景"
        if d.background not in BACKGROUND_REGISTRY:
            return False, f"未知背景: {d.background!r}"

        if not d.species:
            return False, "請選擇種族"
        if d.species not in SPECIES_REGISTRY:
            return False, f"未知種族: {d.species!r}"

        # 屬性值
        if d.score_method == "point_buy":
            ok, msg = validate_point_buy(d.scores)
            if not ok:
                return False, msg
        elif d.score_method == "standard":
            if all(v == 10 for v in d.scores.values()):
                return False, "屬性值尚未設定"

        # 技能
        total_picks = self.get_total_skill_picks()
        if total_picks > 0 and len(d.skills) != total_picks:
            return False, f"需選 {total_picks} 項技能，已選 {len(d.skills)}"

        # 法術
        cd = CLASS_DISPLAY.get(d.char_class)
        if cd:
            num_cantrips = cd.num_cantrips
            num_spells = cd.num_prepared_spells
            # 只在有法術資料庫時驗證
            has_cantrip_db = bool(list_spells(level=0, char_class=d.char_class))
            has_spell_db = bool(list_spells(level=1, char_class=d.char_class))
            ok, msg = validate_spell_selection(
                d.cantrips if has_cantrip_db else ["_"] * num_cantrips,
                d.spells if has_spell_db else ["_"] * num_spells,
                num_cantrips,
                num_spells,
            )
            if not ok:
                return False, msg

        if not d.name:
            return False, "角色名稱不能為空"

        return True, "OK"

    def build_character(self) -> Character:
        """從 data 建構完整 Character。呼叫前應先 validate()。"""
        d = self.data

        builder = CharacterBuilder()
        builder.set_name(d.name or "冒險者")
        builder.set_background(d.background or "Unknown")
        builder.set_species(d.species or "Unknown")
        builder.set_class(d.char_class)

        # 屬性值：先建基礎值，再用 bone_engine 套用背景加值（含上限 20 檢查）
        base = d.scores
        base_scores = AbilityScores(
            STR=base.get(Ability.STR, 10),
            DEX=base.get(Ability.DEX, 10),
            CON=base.get(Ability.CON, 10),
            INT=base.get(Ability.INT, 10),
            WIS=base.get(Ability.WIS, 10),
            CHA=base.get(Ability.CHA, 10),
        )
        bg_adj = d.bg_adjust
        if bg_adj:
            try:
                final_scores = apply_background_bonus(base_scores, bg_adj)
            except ValueError:
                # 加值導致超過 20 等異常，退回基礎值
                final_scores = base_scores
        else:
            final_scores = base_scores
        builder.set_ability_scores(final_scores)

        # 技能：背景（固定） + 選位（d.skills 合併了專長和職業）
        all_skills: list[Skill] = []
        bg_id = d.background
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            for s in BACKGROUND_REGISTRY[bg_id].skill_proficiencies:
                if s not in all_skills:
                    all_skills.append(s)
        for s in d.skills:
            if s not in all_skills:
                all_skills.append(s)

        # 確保數量至少足夠 CharacterBuilder
        cc = d.char_class
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
        equip_choice = d.class_equipment or "A"
        if equip_choice == "A" and cc in CLASS_DISPLAY:
            cd = CLASS_DISPLAY[cc]
            if cd.default_armor != "none":
                builder.set_armor(cd.default_armor)

        return builder.build()

    # ── 內部輔助 ──────────────────────────────────────────────────────────────

    def _get_bg_skills(self) -> list[Skill]:
        """取得背景固定技能。"""
        bg_id = self.data.background
        if bg_id and bg_id in BACKGROUND_REGISTRY:
            return list(BACKGROUND_REGISTRY[bg_id].skill_proficiencies)
        return []

    def _apply_standard_array(self) -> None:
        """依職業建議自動分配標準陣列。"""
        cc = self.data.char_class
        if cc in STANDARD_ARRAY_SUGGESTION:
            sug = STANDARD_ARRAY_SUGGESTION[cc]
            self.data.scores = dict(zip(ABILITY_ORDER, sug, strict=False))
        else:
            self.data.scores = dict(zip(ABILITY_ORDER, STANDARD_ARRAY, strict=False))

    def _auto_assign_rolls(self, rolled: list[int]) -> None:
        """依職業屬性優先順序自動分配擲骰結果。"""
        cc = self.data.char_class
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
        self.data.scores = assign

    def _resolve_spell_names(self, en_names: list[str]) -> list[str]:
        """將 en_name 列表轉為中文名（查不到的保留英文名）。"""
        from tot.gremlins.bone_engine.spells import load_spell_db

        db = load_spell_db()
        # 建 en_name → name 的反查表
        lookup: dict[str, str] = {}
        for spell in db.values():
            if spell.en_name:
                lookup[spell.en_name] = spell.name
        return [lookup.get(en, en) for en in en_names]


# ── 工具函式 ──────────────────────────────────────────────────────────────────


def _spell_to_dict(spell: object) -> dict:
    """將 Spell 物件轉為 dict（供 get_available_cantrips/spells 回傳）。"""
    return {
        "name": spell.name,
        "en_name": spell.en_name,
        "level": spell.level,
        "school": spell.school.value if hasattr(spell.school, "value") else str(spell.school),
        "damage_type": spell.damage_type.value if spell.damage_type else "",
        "effect_type": (
            spell.effect_type.value
            if hasattr(spell.effect_type, "value")
            else str(spell.effect_type)
        ),
        "description": spell.description,
        "damage_type_zh": DAMAGE_TYPE_ZH.get(
            spell.damage_type.value if spell.damage_type else "", ""
        ),
        "effect_type_zh": EFFECT_TYPE_ZH.get(
            spell.effect_type.value if hasattr(spell.effect_type, "value") else "", ""
        ),
    }
