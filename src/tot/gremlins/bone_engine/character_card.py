"""角色卡多層級純文字生成器。TUI 和 LLM 共用，不依賴任何 UI 元件。

從 Character 物件生成各情境的純文字角色卡：
- overview()     — 總覽（屬性、技能、法術概要）
- exploration()  — 探索情境（被動感知、技能檢定、工具檢定）
- combat()       — 戰鬥情境（武器、法術攻擊、法術位、資源）
- equipment()    — 裝備清單
- personal()     — 個人背景（種族/職業特性、專長）
- full()         — 完整版（以上全部）
"""

from __future__ import annotations

import re

from tot.data.classes import CLASS_DISPLAY
from tot.data.feats import ORIGIN_FEAT_REGISTRY
from tot.data.origins import (
    ABILITY_ZH,
    BACKGROUND_REGISTRY,
    SKILL_ZH,
    SPECIES_REGISTRY,
    TOOL_DATA,
    TOOL_ZH,
)
from tot.gremlins.bone_engine.character import CLASS_REGISTRY
from tot.gremlins.bone_engine.spells import get_spell_by_name, load_spell_db
from tot.models.creature import Character, Weapon
from tot.models.enums import (
    Ability,
    Skill,
)
from tot.models.source_pack import SpellCastingType, SpellGrant

# ─────────────────────────────────────────────────────────────────────────────
# 共用翻譯輔助（從 character_session 提取，避免依賴 session）
# ─────────────────────────────────────────────────────────────────────────────

SCHOOL_ZH: dict[str, str] = {
    "Abjuration": "防護",
    "Conjuration": "咒法",
    "Divination": "預言",
    "Enchantment": "惑控",
    "Evocation": "塑能",
    "Illusion": "幻術",
    "Necromancy": "死靈",
    "Transmutation": "變化",
}

EFFECT_TYPE_ZH: dict[str, str] = {
    "damage": "傷害",
    "healing": "治療",
    "condition": "狀態",
    "buff": "增益",
    "utility": "功能",
}

DAMAGE_TYPE_ZH: dict[str, str] = {
    "Acid": "強酸",
    "Bludgeoning": "鈍擊",
    "Cold": "寒冷",
    "Fire": "火焰",
    "Force": "力場",
    "Lightning": "閃電",
    "Necrotic": "黯蝕",
    "Piercing": "穿刺",
    "Poison": "毒素",
    "Psychic": "心靈",
    "Radiant": "光輝",
    "Slashing": "揮砍",
    "Thunder": "雷鳴",
}


def _translate_range(rng: str) -> str:
    """將法術範圍從英制轉為公制中文。5ft = 1.5m。"""
    if not rng:
        return ""
    if rng == "Self":
        return "自身"
    if rng == "Touch":
        return "觸碰"

    def _ft_to_m(match: re.Match) -> str:
        ft = int(match.group(1))
        m = ft * 0.3
        return f"{m:g}m"

    result = re.sub(r"(\d+)ft", _ft_to_m, rng)
    result = result.replace("Self", "自身")
    result = result.replace("cone", "錐形")
    result = result.replace("cube", "立方")
    result = result.replace("sphere", "球形")
    result = result.replace("line", "直線")
    result = result.replace("emanation", "散發")
    result = result.replace("(", "（").replace(")", "）")
    return result


def _translate_duration(dur: str) -> str:
    """將法術持續時間從英文轉為中文。"""
    if not dur:
        return ""
    if dur == "Instantaneous":
        return "立即"

    m = re.match(r"(\d+)\s+(round|minute|minutes|hour|hours|day|days)", dur)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        unit_zh = {
            "round": "回合",
            "minute": "分鐘",
            "minutes": "分鐘",
            "hour": "小時",
            "hours": "小時",
            "day": "天",
            "days": "天",
        }
        return f"{n} {unit_zh.get(unit, unit)}"

    return dur


def _fmt_mod(val: int) -> str:
    """格式化修正值：正數加 +，負數自帶 -。"""
    return f"+{val}" if val >= 0 else str(val)


# ─────────────────────────────────────────────────────────────────────────────
# 按屬性分組的技能列表（探索頁面排版用）
# ─────────────────────────────────────────────────────────────────────────────

_SKILL_GROUPS: list[tuple[str, list[Skill]]] = [
    ("力量系", [Skill.ATHLETICS]),
    (
        "敏捷系",
        [Skill.ACROBATICS, Skill.SLEIGHT_OF_HAND, Skill.STEALTH],
    ),
    (
        "智力系",
        [Skill.ARCANA, Skill.HISTORY, Skill.INVESTIGATION, Skill.NATURE, Skill.RELIGION],
    ),
    (
        "感知系",
        [
            Skill.ANIMAL_HANDLING,
            Skill.INSIGHT,
            Skill.MEDICINE,
            Skill.PERCEPTION,
            Skill.SURVIVAL,
        ],
    ),
    (
        "魅力系",
        [Skill.DECEPTION, Skill.INTIMIDATION, Skill.PERFORMANCE, Skill.PERSUASION],
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# CharacterCard
# ─────────────────────────────────────────────────────────────────────────────


class CharacterCard:
    """角色卡多層級生成器。從 Character 物件生成各情境的純文字。"""

    def __init__(self, char: Character) -> None:
        self.char = char

        # 查詢 registry 資料（容錯：找不到就 None）
        self._class_data = CLASS_REGISTRY.get(char.char_class)
        self._class_display = CLASS_DISPLAY.get(char.char_class)
        self._species_data = SPECIES_REGISTRY.get(char.species)
        self._bg_data = BACKGROUND_REGISTRY.get(char.background)

        # 確保法術資料庫已載入
        load_spell_db()

    # ── 總覽 ──────────────────────────────────────────────────────────────────

    def overview(self) -> str:
        """總覽：基本資訊、屬性值、熟練、法術概要。"""
        c = self.char
        lines: list[str] = []

        # 標題
        lines.append("═══ 角色總覽 ═══")

        # 基本資訊行
        class_zh = self._class_display.name_zh if self._class_display else c.char_class
        species_zh = self._species_data.name_zh if self._species_data else c.species
        bg_zh = self._bg_data.name_zh if self._bg_data else c.background
        lineage = c.subclass if c.subclass else ""
        species_str = f"{species_zh}（{lineage}）" if lineage else species_zh

        lines.append(
            f"名稱：{c.name}　職業：{class_zh} {c.level} 級　背景：{bg_zh}　種族：{species_str}"
        )

        # 戰鬥數值行
        init_bonus = c.initiative_bonus + c.ability_scores.modifier(Ability.DEX)
        lines.append(
            f"HP：{c.hp_current}/{c.hp_max}　AC：{c.ac}　"
            f"先攻：{_fmt_mod(init_bonus)}　速度：{c.speed}m　"
            f"熟練加值：+{c.proficiency_bonus}"
        )
        lines.append("")

        # 屬性值
        lines.append("屬性值：")
        row1_parts = []
        row2_parts = []
        for i, ab in enumerate(Ability):
            score = c.ability_scores.score(ab)
            mod = c.ability_scores.modifier(ab)
            text = f"{ABILITY_ZH[ab]} {score}({_fmt_mod(mod)})"
            if i < 3:
                row1_parts.append(text)
            else:
                row2_parts.append(text)
        lines.append(f"  {'  '.join(row1_parts)}")
        lines.append(f"  {'  '.join(row2_parts)}")
        lines.append("")

        # 豁免熟練
        save_list = [ABILITY_ZH[ab] for ab in Ability if ab in c.saving_throw_proficiencies]
        lines.append(f"豁免熟練：{', '.join(save_list) if save_list else '無'}")

        # 技能熟練
        skill_list = []
        for sk in c.skill_proficiencies:
            mark = "★" if sk in c.skill_expertise else ""
            skill_list.append(f"{SKILL_ZH.get(sk, sk.value)}{mark}")
        lines.append(f"技能熟練：{', '.join(skill_list) if skill_list else '無'}")

        # 工具熟練
        tool_list = [TOOL_ZH.get(t, t.value) for t in c.tool_proficiencies]
        lines.append(f"工具熟練：{', '.join(tool_list) if tool_list else '無'}")

        # 法術概要
        cantrips, spells_by_level = self._categorize_spells()

        if cantrips:
            lines.append("")
            lines.append(f"戲法：{', '.join(cantrips)}")

        for lvl in sorted(spells_by_level.keys()):
            names = spells_by_level[lvl]
            # 合併 spell_slots 和 pact_slots
            cur = c.spell_slots.current_slots.get(lvl, 0)
            mx = c.spell_slots.max_slots.get(lvl, 0)
            pact_cur = c.pact_slots.current_slots.get(lvl, 0)
            pact_mx = c.pact_slots.max_slots.get(lvl, 0)
            slot_parts = []
            if mx > 0:
                slot_parts.append(f"{cur}/{mx} 位")
            if pact_mx > 0:
                slot_parts.append(f"契約 {pact_cur}/{pact_mx} 位")
            slot_str = "＋".join(slot_parts) if slot_parts else "0 位"
            lines.append(f"{lvl} 環法術（{slot_str}）：{', '.join(names)}")

        # 祈喚（Warlock）
        invocations = self._get_invocations()
        if invocations:
            lines.append(f"祈喚：{', '.join(invocations)}")

        return "\n".join(lines)

    # ── 探索 ──────────────────────────────────────────────────────────────────

    def exploration(self) -> str:
        """探索情境：被動數值、技能檢定、工具檢定。"""
        c = self.char
        lines: list[str] = []

        lines.append("═══ 探索資訊 ═══")

        # 被動數值
        passive_perc = 10 + c.skill_bonus(Skill.PERCEPTION)
        passive_inv = 10 + c.skill_bonus(Skill.INVESTIGATION)
        passive_ins = 10 + c.skill_bonus(Skill.INSIGHT)
        lines.append(f"被動感知：{passive_perc}")
        lines.append(f"被動調查：{passive_inv}")
        lines.append(f"被動洞察：{passive_ins}")

        # 暗視（從種族特性判斷）
        if self._species_data:
            traits_desc = self._species_data.traits_description
            if "暗視" in self._species_data.traits:
                # 嘗試從描述中抓距離
                dv_match = re.search(r"(\d+)m\s*暗視", traits_desc)
                if dv_match:
                    lines.append(f"暗視：{dv_match.group(1)}m")
                else:
                    lines.append("暗視：有")
        lines.append("")

        # 技能檢定
        lines.append("能力檢定（● = 熟練，★ = 專精）：")
        for group_name, skills in _SKILL_GROUPS:
            parts: list[str] = []
            for sk in skills:
                bonus = c.skill_bonus(sk)
                if sk in c.skill_expertise:
                    mark = "★"
                elif sk in c.skill_proficiencies:
                    mark = "●"
                else:
                    mark = ""
                parts.append(f"{SKILL_ZH.get(sk, sk.value)} {_fmt_mod(bonus)}{mark}")
            lines.append(f"  {group_name}：{'　'.join(parts)}")
        lines.append("")

        # 工具檢定
        if c.tool_proficiencies:
            lines.append("工具檢定：")
            for tool in c.tool_proficiencies:
                tool_info = TOOL_DATA.get(tool)
                tool_name = TOOL_ZH.get(tool, tool.value)
                if tool_info:
                    # 從工具的 ability 中文推導屬性 bonus
                    ability_bonus = self._tool_ability_bonus(tool_info.ability)
                    total = ability_bonus + c.proficiency_bonus
                    lines.append(
                        f"  {tool_name}（{tool_info.ability} {_fmt_mod(total)}）"
                        f"— {tool_info.utilize}"
                    )
                else:
                    lines.append(f"  {tool_name}")

        return "\n".join(lines)

    # ── 戰鬥 ──────────────────────────────────────────────────────────────────

    def combat(self) -> str:
        """戰鬥情境：HP/AC、武器攻擊、法術攻擊、法術位、資源。"""
        c = self.char
        lines: list[str] = []

        lines.append("═══ 戰鬥資訊 ═══")

        # 基礎數值
        temp_str = f" 臨時：{c.hp_temp}" if c.hp_temp else ""
        init_bonus = c.initiative_bonus + c.ability_scores.modifier(Ability.DEX)
        lines.append(
            f"HP：{c.hp_current}/{c.hp_max}{temp_str}　AC：{c.ac}　"
            f"先攻：{_fmt_mod(init_bonus)}　速度：{c.speed}m"
        )
        lines.append("")

        # 從 SourcePack 建立所有法術行，按動作經濟分組
        spell_by_action = self._build_combat_spell_lines()

        # ── 動作 ──
        lines.append("── 動作（Action）──")

        # 武器攻擊
        for wpn in c.weapons:
            lines.append(f"  {self._format_weapon(wpn)}")

        # 動作法術（戲法 + 1 環以上）
        action_spells = spell_by_action.get("1 action", [])
        for text in action_spells:
            lines.append(f"  {text}")

        if not c.weapons and not action_spells:
            lines.append("  （無）")
        lines.append("")

        # ── 附贈動作 ──
        lines.append("── 附贈動作（Bonus Action）──")
        bonus_spells = spell_by_action.get("1 bonus action", [])
        bonus_items = self._get_bonus_actions_class_only()
        all_bonus = bonus_spells + bonus_items
        if all_bonus:
            for item in all_bonus:
                lines.append(f"  {item}")
        else:
            lines.append("  （無）")
        lines.append("")

        # ── 反應 ──
        lines.append("── 反應（Reaction）──")
        reaction_spells = spell_by_action.get("1 reaction", [])
        lines.append("  ⚔ 借機攻擊")
        for text in reaction_spells:
            lines.append(f"  {text}")
        lines.append("")

        # ── 法術位 ──
        slot_lines = self._format_spell_slots()
        if slot_lines:
            lines.append("── 法術位 ──")
            for sl in slot_lines:
                lines.append(f"  {sl}")
            lines.append("")

        # ── 有限使用資源 ──
        resource_lines = self._get_limited_resources()
        if resource_lines:
            lines.append("── 有限使用資源 ──")
            for rl in resource_lines:
                lines.append(f"  {rl}")

        return "\n".join(lines)

    # ── 裝備 ──────────────────────────────────────────────────────────────────

    def equipment(self) -> str:
        """裝備清單。"""
        c = self.char
        lines: list[str] = []

        lines.append("═══ 裝備清單 ═══")

        if c.weapons:
            lines.append("武器：")
            for wpn in c.weapons:
                props = ", ".join(p.value for p in wpn.properties)
                range_str = f"{wpn.range_normal:g}m"
                if wpn.range_long:
                    range_str += f"/{wpn.range_long:g}m"
                mastery_str = f"　專精：{wpn.mastery.value}" if wpn.mastery else ""
                lines.append(
                    f"  {wpn.name}　{wpn.damage_dice} "
                    f"{DAMAGE_TYPE_ZH.get(wpn.damage_type.value, wpn.damage_type.value)}"
                    f"　範圍 {range_str}"
                    f"{'　' + props if props else ''}"
                    f"{mastery_str}"
                )

        if c.inventory:
            lines.append("物品：")
            for item in c.inventory:
                qty = f"×{item.quantity}" if item.quantity > 1 else ""
                magic = " ✦" if item.is_magic else ""
                desc = f"　{item.description}" if item.description else ""
                lines.append(f"  {item.name}{qty}{magic}{desc}")

        if not c.weapons and not c.inventory:
            lines.append("  （空）")

        return "\n".join(lines)

    # ── 個人資訊 ────────────────────────────────────────────────────────────

    def personal(self) -> str:
        """個人資訊：種族/職業特性、起源專長。"""
        c = self.char
        lines: list[str] = []

        lines.append("═══ 個人資訊 ═══")

        # 基本身份
        class_zh = self._class_display.name_zh if self._class_display else c.char_class
        species_zh = self._species_data.name_zh if self._species_data else c.species
        bg_zh = self._bg_data.name_zh if self._bg_data else c.background
        lines.append(f"名稱：{c.name}")
        lines.append(f"種族：{species_zh}")
        lines.append(f"職業：{class_zh} {c.level} 級")
        if c.subclass:
            lines.append(f"子職業：{c.subclass}")
        lines.append(f"背景：{bg_zh}")
        lines.append("")

        # 種族特性
        if self._species_data:
            lines.append("種族特性：")
            for trait in self._species_data.traits:
                lines.append(f"  • {trait}")
            if self._species_data.traits_description:
                lines.append(f"  {self._species_data.traits_description}")
            lines.append("")

        # 職業特性
        if self._class_display and self._class_display.features_1st:
            lines.append("職業特性：")
            for feat in self._class_display.features_1st:
                lines.append(f"  • {feat}")
            lines.append("")

        # 起源專長
        if self._bg_data:
            feat_data = ORIGIN_FEAT_REGISTRY.get(self._bg_data.feat)
            if feat_data:
                lines.append(f"起源專長：{feat_data.name_zh}（{feat_data.name_en}）")
                lines.append(f"  {feat_data.description}")

        return "\n".join(lines)

    # ── 完整版 ────────────────────────────────────────────────────────────────

    def full(self) -> str:
        """完整版：所有區塊合併。"""
        sections = [
            self.overview(),
            self.exploration(),
            self.combat(),
            self.equipment(),
            self.personal(),
        ]
        return "\n\n".join(sections)

    # ═══════════════════════════════════════════════════════════════════════════
    # 內部輔助方法
    # ═══════════════════════════════════════════════════════════════════════════

    def _categorize_spells(self) -> tuple[list[str], dict[int, list[str]]]:
        """將角色法術分為戲法和各環級法術。

        優先從 SourcePack 讀取（含重複來源），fallback 到 flat list。
        只在同一法術出現在多個 Pack 時才標註來源。
        回傳 (戲法名稱列表, {環級: 名稱列表})。
        """
        cantrips: list[str] = []
        spells_by_level: dict[int, list[str]] = {}

        if self.char.source_packs:
            # 先統計每個 en_name 出現在幾個不同的 Pack
            from collections import Counter

            name_count: Counter[str] = Counter()
            for pack in self.char.source_packs:
                for sg in pack.spells:
                    name_count[sg.en_name] += 1

            # 再組裝顯示名稱，重複來源才加標記
            for pack in self.char.source_packs:
                for sg in pack.spells:
                    spell = get_spell_by_name(sg.en_name)
                    name = spell.name if spell else sg.en_name
                    level = spell.level if spell else 0
                    entry = f"{name}（{pack.source_name}）" if name_count[sg.en_name] > 1 else name
                    if level == 0:
                        cantrips.append(entry)
                    else:
                        spells_by_level.setdefault(level, []).append(entry)
        else:
            all_spells = list(set(self.char.spells_known + self.char.spells_prepared))
            for spell_name in sorted(all_spells):
                spell = get_spell_by_name(spell_name)
                if spell is None:
                    cantrips.append(spell_name)
                    continue
                if spell.level == 0:
                    cantrips.append(spell.name)
                else:
                    spells_by_level.setdefault(spell.level, []).append(spell.name)

        return cantrips, spells_by_level

    def _get_invocations(self) -> list[str]:
        """取得角色的魔能祈喚名稱列表（中文）。"""
        # 目前 Character model 沒有 invocations 欄位，
        # 從 class_levels 判斷是否為 Warlock
        if "Warlock" not in self.char.class_levels:
            return []

        # 嘗試從備妥法術中找祈喚（祈喚不是法術，未來可能需要擴展 Character model）
        # 暫時回傳空列表，待 Character model 加入 invocations 欄位後補齊
        return []

    def _tool_ability_bonus(self, ability_zh: str) -> int:
        """從工具的中文屬性名稱取得角色的屬性修正值。"""
        zh_to_ability: dict[str, Ability] = {v: k for k, v in ABILITY_ZH.items()}
        ab = zh_to_ability.get(ability_zh)
        if ab:
            return self.char.ability_scores.modifier(ab)
        return 0

    def _format_weapon(self, wpn: Weapon) -> str:
        """格式化單一武器的戰鬥顯示。"""
        c = self.char

        # 計算攻擊加值
        if wpn.is_finesse:
            # 靈巧武器取 STR/DEX 較高者
            str_mod = c.ability_scores.modifier(Ability.STR)
            dex_mod = c.ability_scores.modifier(Ability.DEX)
            ability_mod = max(str_mod, dex_mod)
        elif wpn.is_ranged:
            ability_mod = c.ability_scores.modifier(Ability.DEX)
        else:
            ability_mod = c.ability_scores.modifier(Ability.STR)

        attack_bonus = ability_mod + c.proficiency_bonus
        damage_mod = ability_mod

        # 範圍
        range_str = f"{wpn.range_normal:g}m"
        if wpn.range_long:
            range_str += f"/{wpn.range_long:g}m"

        # 傷害類型
        dmg_type = DAMAGE_TYPE_ZH.get(wpn.damage_type.value, wpn.damage_type.value)

        return (
            f"⚔ {wpn.name}　範圍 {range_str}　"
            f"{_fmt_mod(attack_bonus)} 命中　"
            f"{wpn.damage_dice}{_fmt_mod(damage_mod)} {dmg_type}"
        )

    def _compute_grant_dc_attack(self, sg: SpellGrant) -> tuple[int, int]:
        """根據 SpellGrant 的施法屬性計算 DC 和攻擊加值。

        如果 SpellGrant 沒有指定 spellcasting_ability，就用角色預設值。
        回傳 (dc, attack_bonus)。
        """
        c = self.char
        if sg.spellcasting_ability is not None:
            mod = c.ability_scores.modifier(sg.spellcasting_ability)
            dc = 8 + c.proficiency_bonus + mod
            attack = c.proficiency_bonus + mod
            return dc, attack
        return c.spell_dc, c.spell_attack

    def _format_slot_info(self, label: str, slots) -> str:
        """格式化法術位資訊：如「契約位 1/1」。"""
        total_cur = sum(slots.current_slots.values())
        total_max = sum(slots.max_slots.values())
        return f"{label} {total_cur}/{total_max}"

    def _format_cost_tag(self, sg: SpellGrant) -> str:
        """根據 SpellGrant 屬性產生消耗標記字串，含剩餘位數。"""
        c = self.char
        ct = sg.casting_type
        has_pact = bool(c.pact_slots.max_slots)
        has_slots = bool(c.spell_slots.max_slots)

        pact_info = self._format_slot_info("契約位", c.pact_slots) if has_pact else ""
        slot_info = self._format_slot_info("法術位", c.spell_slots) if has_slots else ""

        if ct == SpellCastingType.INVOCATION:
            return "【隨意施放】"

        if sg.free_uses_max > 0:
            tag = f"【免費 {sg.free_uses_current}/{sg.free_uses_max}，長休恢復"
            if sg.can_also_use_slot:
                ref = pact_info if has_pact else slot_info
                tag += f"，或消耗{ref}" if ref else "，或消耗法術位"
            tag += "】"
            return tag

        if ct == SpellCastingType.INNATE:
            return "【免費 1/1】"

        if ct == SpellCastingType.TOME and sg.can_ritual_cast:
            ref = pact_info if has_pact else slot_info
            return f"【儀式，或消耗{ref}】" if ref else "【儀式或法術位】"

        # KNOWN / PREPARED / FEAT / SPELLBOOK
        if ct in (SpellCastingType.KNOWN, SpellCastingType.PREPARED):
            if has_pact:
                return f"【{pact_info}】"
            if has_slots:
                return f"【{slot_info}】"
        if ct == SpellCastingType.FEAT:
            if has_slots:
                return f"【{slot_info}】"
            if has_pact:
                return f"【{pact_info}】"
        if has_pact:
            return f"【{pact_info}】"
        if has_slots:
            return f"【{slot_info}】"
        return "【法術位】"

    def _build_combat_spell_lines(self) -> dict[str, list[str]]:
        """從 SourcePack 讀取所有法術，按 casting_time 分組為戰鬥行。

        回傳 {"1 action": [...], "1 bonus action": [...], "1 reaction": [...]}。
        每個 SpellGrant 獨立一行（不同來源 = 不同行，DC 可能不同）。
        """
        c = self.char
        result: dict[str, list[str]] = {}

        if not c.source_packs:
            # fallback：用舊的 _get_combat_cantrips 邏輯
            for action_type in ("1 action", "1 bonus action", "1 reaction"):
                lines = self._get_combat_cantrips(action_type=action_type)
                if lines:
                    result[action_type] = lines
            return result

        # 收集所有 (pack, spell_grant, spell_data) 三元組
        entries: list[tuple[str, SpellGrant, object]] = []
        for pack in c.source_packs:
            for sg in pack.spells:
                spell = get_spell_by_name(sg.en_name)
                if spell is not None:
                    entries.append((pack.source_name, sg, spell))

        for _source_name, sg, spell in entries:
            casting_time = spell.casting_time
            level = spell.level
            dc, attack_bonus = self._compute_grant_dc_attack(sg)

            # 環級標記
            level_str = "戲法" if level == 0 else f"{level} 環"
            conc_str = "，專注" if spell.concentration else ""

            # 範圍
            rng = _translate_range(spell.range)

            # 攻擊/豁免資訊
            if spell.attack_type.value != "none":
                hit_str = f"{_fmt_mod(attack_bonus)} 命中"
            elif spell.save_ability:
                save_zh = ABILITY_ZH.get(spell.save_ability, spell.save_ability.value)
                hit_str = f"DC {dc} {save_zh}"
            else:
                hit_str = ""

            # 傷害骰
            dmg_str = ""
            if spell.damage_dice:
                dmg_type = DAMAGE_TYPE_ZH.get(
                    spell.damage_type.value if spell.damage_type else "", ""
                )
                dmg_str = f"　{spell.damage_dice}"
                if dmg_type:
                    dmg_str += f" {dmg_type}"

            # 消耗標記（戲法不需要）
            cost_str = ""
            if level > 0:
                cost_str = f"　{self._format_cost_tag(sg)}"

            # 組裝
            line = f"🔮 {spell.name}（{level_str}{conc_str}）範圍 {rng}"
            if hit_str:
                line += f"　{hit_str}"
            line += dmg_str
            line += cost_str

            result.setdefault(casting_time, []).append(line)

        return result

    def _get_combat_cantrips(self, *, action_type: str = "1 action") -> list[str]:
        """取得可用於戰鬥的攻擊型戲法列表（格式化後的文字）。"""
        c = self.char
        results: list[str] = []

        all_spells = list(set(c.spells_known + c.spells_prepared))
        for spell_name in sorted(all_spells):
            spell = get_spell_by_name(spell_name)
            if spell is None:
                continue
            if spell.level != 0:
                continue
            if spell.casting_time != action_type:
                continue
            if spell.effect_type.value not in ("damage", "condition"):
                continue

            rng = _translate_range(spell.range)
            dmg_type = DAMAGE_TYPE_ZH.get(spell.damage_type.value if spell.damage_type else "", "")

            # 攻擊型 vs 豁免型
            if spell.attack_type.value != "none":
                hit_str = f"{_fmt_mod(c.spell_attack)} 命中"
            elif spell.save_ability:
                save_zh = ABILITY_ZH.get(spell.save_ability, spell.save_ability.value)
                hit_str = f"DC {c.spell_dc} {save_zh}"
            else:
                hit_str = ""

            dmg_str = ""
            if spell.damage_dice:
                dmg_str = f"　{spell.damage_dice}"
                if dmg_type:
                    dmg_str += f" {dmg_type}"

            results.append(f"🔮 {spell.name}（戲法）範圍 {rng}　{hit_str}{dmg_str}")

        return results

    def _get_bonus_actions_class_only(self) -> list[str]:
        """取得職業特性的附贈動作列表（法術已由 _build_combat_spell_lines 處理）。"""
        items: list[str] = []

        cc = self.char.char_class
        if cc == "Barbarian":
            items.append("💢 狂暴（開始/維持）")
        elif cc == "Monk":
            items.append("👊 運氣連擊（1 氣）")
        elif cc == "Rogue":
            items.append("💨 靈活步伐（衝刺/脫離/躲藏）")

        return items

    def _format_spell_slots(self) -> list[str]:
        """格式化法術位顯示（■/□ 方塊表示）。"""
        lines: list[str] = []
        slots = self.char.spell_slots

        for lvl in sorted(slots.max_slots.keys()):
            mx = slots.max_slots[lvl]
            if mx <= 0:
                continue
            cur = slots.current_slots.get(lvl, 0)
            used = mx - cur
            blocks = "■" * cur + "□" * used
            lines.append(f"{lvl} 環：{blocks}（{cur}/{mx}）")

        # Warlock 契約法術欄位
        pact = self.char.pact_slots
        if pact.max_slots:
            for lvl in sorted(pact.max_slots.keys()):
                mx = pact.max_slots[lvl]
                if mx <= 0:
                    continue
                cur = pact.current_slots.get(lvl, 0)
                used = mx - cur
                blocks = "■" * cur + "□" * used
                lines.append(f"契約 {lvl} 環：{blocks}（{cur}/{mx}）")

        return lines

    def _get_limited_resources(self) -> list[str]:
        """取得有限使用資源列表。"""
        items: list[str] = []
        c = self.char
        cc = c.char_class

        # Hit Dice
        remaining = c.hit_dice_remaining_count
        total = c.hit_dice_total
        if total > 0:
            items.append(f"生命骰：{remaining}/{total}")

        # 英雄靈感
        if c.heroic_inspiration:
            items.append("英雄靈感：✓")

        # 職業特性（常見的有限使用能力）
        if cc == "Barbarian":
            # 1 級狂暴次數 = 熟練加值
            items.append(f"狂暴：{c.proficiency_bonus} 次/長休")
        elif cc == "Fighter":
            items.append("第二風：1 次/短休")
        elif cc == "Cleric":
            items.append("引導神力：1 次/短休")
        elif cc == "Monk":
            # 氣 = 等級（2 級起）
            if c.level >= 2:
                items.append(f"氣：{c.level} 點/短休")
        elif cc == "Paladin":
            # 聖療術 = 等級 × 5 HP
            pool = c.level * 5
            items.append(f"聖療術：{pool} HP/長休")
        elif cc == "Bard":
            # 鼓舞次數 = CHA 修正值（最少 1）
            cha_mod = max(1, c.ability_scores.modifier(Ability.CHA))
            items.append(f"吟遊鼓舞：{cha_mod} 次/長休")

        return items
